"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createGoogleEvent = exports.patchGoogleEvent = exports.clearGoogleCalendar = exports.getGoogleColors = exports.deleteGoogleCalendar = exports.deleteGoogleEvent = exports.getGoogleCalendar = exports.createGoogleCalendar = exports.patchGoogleCalendar = exports.getGoogleToken = exports.googleMeetAvailable = exports.houseKeepSyncEnabledGoogleCalendar = exports.getGoogleCalendarSyncApiToken = exports.getCalendarWebhook = exports.deleteCalendarWebhook = exports.enableCalendarWebhook = exports.checkIfCalendarWebhookExpired = void 0;
const axios_1 = __importDefault(require("axios"));
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
const date_utils_1 = require("@lib/date-utils");
const qs_1 = __importDefault(require("qs"));
const uuid_1 = require("uuid");
const constants_1 = require("@lib/constants");
const constants_2 = require("@lib/calendarLib/constants");
const api_helper_1 = require("@lib/api-helper");
const constants_3 = require("@lib/constants");
const client_1 = require("@apollo/client");
const getCalendarIntegrationByResourceAndName_1 = __importDefault(require("@lib/apollo/gql/getCalendarIntegrationByResourceAndName"));
const getCalendarPushNotificationByCalendarId_1 = __importDefault(require("@lib/apollo/gql/getCalendarPushNotificationByCalendarId"));
const listCalendarPushNotificationsByUserId_1 = __importDefault(require("@lib/apollo/gql/listCalendarPushNotificationsByUserId"));
const deleteCalendarPushNotificationByCalendarId_1 = __importDefault(require("@lib/apollo/gql/deleteCalendarPushNotificationByCalendarId"));
// type Collections = {
//     [key: string]: RxCollection;
// }
// type Internals = any
// type InstanceCreationOptions = any
// const result = await axios.post(url, data, config)
const checkIfCalendarWebhookExpired = async (client, userId) => {
    try {
        const calendarWebhooks = (await client.query({
            query: listCalendarPushNotificationsByUserId_1.default,
            variables: {
                userId,
            },
        }))?.data?.Calendar_Push_Notification;
        // loop through each and refresh expired webhooks
        for (let i = 0; i < calendarWebhooks.length; i++) {
            if ((0, date_utils_1.dayjs)().isAfter((0, date_utils_1.dayjs)(calendarWebhooks[i]?.expiration))) {
                await (0, exports.enableCalendarWebhook)(calendarWebhooks[i]);
            }
        }
    }
    catch (e) {
        console.log(e, ' unable to check if calendar webhook expired');
    }
};
exports.checkIfCalendarWebhookExpired = checkIfCalendarWebhookExpired;
const enableCalendarWebhook = async (webhook) => {
    try {
        const token = await session_1.default.getAccessToken();
        const url = constants_2.selfGoogleCalendarWatchUrl;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
            },
        };
        const data = {
            calendarId: webhook?.calendarId,
            userId: webhook?.userId,
            channelId: webhook?.id,
        };
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' results inside enableCalendarWebhook');
    }
    catch (e) {
        console.log(e, ' unable to enable calendar webhook');
    }
};
exports.enableCalendarWebhook = enableCalendarWebhook;
const deleteCalendarWebhook = async (client, calendarId) => {
    try {
        /**
         * const googleInteg = (await client.query<{ Calendar_Integration: CalendarIntegrationType[] }>({
          query: getCalendarIntegrationByResource,
          variables: {
            userId,
            name: googleCalendarName,
            resource: googleCalendarResource,
          }
        }))?.data?.Calendar_Integration?.[0]
         */
        const res = await client.mutate({
            mutation: deleteCalendarPushNotificationByCalendarId_1.default,
            variables: {
                calendarId,
            },
        });
        console.log(res, ' res inside deleteCalendarWebhookByCalendarId');
    }
    catch (e) {
        console.log(e, ' unable to delete calendar web hook');
    }
};
exports.deleteCalendarWebhook = deleteCalendarWebhook;
const getCalendarWebhook = async (client, calendarId) => {
    try {
        const calendarWebhook = (await client.query({
            query: getCalendarPushNotificationByCalendarId_1.default,
            variables: {
                calendarId,
            },
        }))?.data?.Calendar_Push_Notification?.[0];
        console.log(calendarWebhook, ' calendarWebhook');
        return calendarWebhook;
    }
    catch (e) {
        console.log(e, ' unable to get calendar webhook');
    }
};
exports.getCalendarWebhook = getCalendarWebhook;
const getGoogleCalendarSyncApiToken = async () => {
    try {
        const token = await session_1.default.getAccessToken();
        const url = constants_3.hasuraApiUrl;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        const operationName = 'GetGoogleCalendarSyncToken';
        const query = `
      query GetGoogleCalendarSyncToken($name: String!, $resource: String!) {
        Admin(where: {name: {_eq: $name}, resource: {_eq: $resource}}) {
          id
          name
          token
          resource
        }
      }
    `;
        const variables = {
            name: 'googleCalendarSync',
            resource: 'aws',
        };
        const data = {
            operationName,
            query,
            variables,
        };
        const results = await axios_1.default.post(url, data, config);
        if (results?.data?.Admin?.[0]?.id) {
            const token = results?.data?.Admin?.[0]?.token;
            return token;
        }
    }
    catch (e) {
        console.log(e, ' unable to get apiToken');
    }
};
exports.getGoogleCalendarSyncApiToken = getGoogleCalendarSyncApiToken;
const houseKeepSyncEnabledGoogleCalendar = async (client, userId) => {
    try {
        // get token and expiresAt
        const googleInteg = (await client.query({
            query: getCalendarIntegrationByResourceAndName_1.default,
            variables: {
                userId,
                name: constants_2.googleCalendarName,
                resource: constants_2.googleResourceName,
            },
        }))?.data?.Calendar_Integration?.[0];
        const oldEnabled = googleInteg?.enabled;
        const oldSyncEnabled = googleInteg?.syncEnabled;
        const updatedAt = (0, date_utils_1.dayjs)().toISOString();
        const updateIntegration = (0, client_1.gql) `
      mutation UpdateCalendarIntegrationById(
        $id: uuid!
        $syncEnabled: Boolean
      ) {
        update_Calendar_Integration_by_pk(
          _set: { syncEnabled: $syncEnabled }
          pk_columns: { id: $id }
        ) {
          appAccountId
          appEmail
          appId
          colors
          contactEmail
          contactName
          createdDate
          deleted
          enabled
          expiresAt
          id
          name
          pageToken
          password
          refreshToken
          syncEnabled
          resource
          token
          syncToken
          updatedAt
          userId
          username
          clientType
        }
      }
    `;
        let variables = {
            id: googleInteg?.id,
        };
        if (oldEnabled && !oldSyncEnabled) {
            variables = {
                ...variables,
                syncEnabled: true,
                updatedAt,
            };
        }
        else if (!oldEnabled && oldSyncEnabled) {
            variables = {
                ...variables,
                syncEnabled: false,
                updatedAt,
            };
        }
        if (variables?.updatedAt) {
            await client.mutate({
                mutation: updateIntegration,
                variables,
            });
        }
        if (oldEnabled && !oldSyncEnabled) {
            await (0, exports.getGoogleToken)(client, userId);
        }
    }
    catch (e) {
        console.log(e, ' unable to housekeep sync enabled for google calendar integration');
    }
};
exports.houseKeepSyncEnabledGoogleCalendar = houseKeepSyncEnabledGoogleCalendar;
const googleMeetAvailable = async (client, userId) => {
    try {
        const token = await (0, exports.getGoogleToken)(client, userId);
        if (token && token?.length > 0) {
            return true;
        }
        return false;
    }
    catch (e) {
        console.log(e, ' google meet is not avilable');
    }
};
exports.googleMeetAvailable = googleMeetAvailable;
const getGoogleToken = async (client, userId) => {
    try {
        // get token and expiresAt
        const googleInteg = (await client.query({
            query: getCalendarIntegrationByResourceAndName_1.default,
            variables: {
                userId,
                name: constants_2.googleCalendarName,
                resource: constants_2.googleResourceName,
            },
        }))?.data?.Calendar_Integration?.[0];
        const token = googleInteg?.token;
        const expiresAt = googleInteg?.expiresAt;
        const oldRefreshToken = googleInteg?.refreshToken;
        if ((0, date_utils_1.dayjs)().isAfter((0, date_utils_1.dayjs)(expiresAt))) {
            let newAccessToken = '';
            let newRefreshToken = '';
            let newExpiresAt = '';
            if (googleInteg?.clientType === 'ios' && oldRefreshToken) {
                const url = constants_1.googleCalendarIosAuthRefreshUrl;
                const token = await session_1.default.getAccessToken();
                const config = {
                    headers: {
                        Authorization: `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                };
                const data = {
                    refreshToken: oldRefreshToken,
                };
                const results = await axios_1.default.post(url, data, config);
                console.log(results, ' results inside enableGoogleCalendarSync');
                newAccessToken = results?.data?.event?.access_token;
                newRefreshToken = oldRefreshToken;
                newExpiresAt = (0, date_utils_1.dayjs)()
                    .add(results?.data?.event?.expires_in, 'seconds')
                    .toISOString();
            }
            else if ((googleInteg?.clientType === 'web' ||
                googleInteg?.clientType === 'android') &&
                oldRefreshToken) {
                const url = constants_1.googleCalendarAndroidAuthRefreshUrl;
                const token = await session_1.default.getAccessToken();
                const config = {
                    headers: {
                        Authorization: `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                };
                const data = {
                    refreshToken: oldRefreshToken,
                };
                const results = await axios_1.default.post(url, data, config);
                console.log(results, ' results inside enableGoogleCalendarSync');
                newAccessToken = results?.data?.event?.access_token;
                newRefreshToken = oldRefreshToken;
                newExpiresAt = (0, date_utils_1.dayjs)()
                    .add(results?.data?.event?.expires_in, 'seconds')
                    .toISOString();
            }
            else if (googleInteg?.clientType === 'atomic-web' && oldRefreshToken) {
                const url = constants_1.googleAtomicWebAuthRefreshUrl;
                const token = await session_1.default.getAccessToken();
                const config = {
                    headers: {
                        Authorization: `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                };
                const data = {
                    refreshToken: oldRefreshToken,
                };
                const results = await axios_1.default.post(url, data, config);
                console.log(results, ' results inside enableGoogleCalendarSync');
                newAccessToken = results?.data?.event?.access_token;
                newRefreshToken = oldRefreshToken;
                newExpiresAt = (0, date_utils_1.dayjs)()
                    .add(results?.data?.event?.expires_in, 'seconds')
                    .toISOString();
            }
            //googleAtomicWebAuthRefreshUrl
            await (0, api_helper_1.updateCalendarIntegration)(client, googleInteg?.id, undefined, newAccessToken, newRefreshToken, newExpiresAt, googleInteg?.clientType === 'android' ? 'web' : googleInteg?.clientType);
            return newAccessToken;
        }
        return token;
    }
    catch (e) {
        console.log(e, ' unable to getGoogleToken');
    }
};
exports.getGoogleToken = getGoogleToken;
const patchGoogleCalendar = async (client, userId, calendarId, summary, description, location, timeZone, allowedConferenceSolutionTypes) => {
    try {
        // get token =
        const token = await (0, exports.getGoogleToken)(client, userId);
        let url = `${constants_2.googleCalendarURL}/${encodeURI(calendarId)}`;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        let data = {};
        if (summary && summary?.length > 0) {
            data = { ...data, summary };
        }
        if (description && description?.length > 0) {
            data = { ...data, description };
        }
        if (location && location?.length > 0) {
            data = { ...data, location };
        }
        if (timeZone && timeZone?.length > 0) {
            data = { ...data, timeZone };
        }
        if (allowedConferenceSolutionTypes &&
            allowedConferenceSolutionTypes?.[0]?.length > 0) {
            data = {
                ...data,
                conferenceProperties: {
                    allowedConferenceSolutionTypes,
                },
            };
        }
        const results = await axios_1.default.patch(url, data, config);
        console.log(results, ' results after patching calendar');
    }
    catch (e) {
        console.log(e, ' unable to patch google calendar');
    }
};
exports.patchGoogleCalendar = patchGoogleCalendar;
// create calendar
const createGoogleCalendar = async (client, userId, id, summary, defaultReminders, notifications) => {
    try {
        // get token =
        const token = await (0, exports.getGoogleToken)(client, userId);
        let url = constants_2.googleCalendarURL;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        let data = { id, summaryOverride: summary, selected: true };
        if (defaultReminders && defaultReminders?.[0]?.method?.length > 0) {
            data = { ...data, defaultReminders };
        }
        if (notifications && notifications?.[0]?.method?.length > 0) {
            data = {
                ...data,
                notificationSettings: {
                    notifications,
                },
            };
        }
        const result = await axios_1.default.post(url, data, config);
        console.log(result, ' successfully created secondary google calendar');
    }
    catch (e) {
        console.log(e, ' unable to create google calendar');
    }
};
exports.createGoogleCalendar = createGoogleCalendar;
// get calendar info
const getGoogleCalendar = async (client, userId, calendarId) => {
    try {
        // get token =
        const token = await (0, exports.getGoogleToken)(client, userId);
        let url = `${constants_2.googleCalendarURL}/${encodeURI(calendarId)}`;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        const results = await axios_1.default.get(url, config);
        console.log(results, ' results for get calendar');
        return results;
    }
    catch (e) {
        console.log(e, ' unable to get calendar');
    }
};
exports.getGoogleCalendar = getGoogleCalendar;
const deleteGoogleEvent = async (client, userId, calendarId, googleEventId, sendUpdates = 'all') => {
    try {
        // get token =
        const token = await (0, exports.getGoogleToken)(client, userId);
        let url = `${constants_2.googleURL}/${encodeURI(calendarId)}/events/${encodeURI(googleEventId)}`;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        // path params
        if (sendUpdates) {
            url = `${url}?`;
            let params = { sendUpdates };
            url = `${url}${qs_1.default.stringify(params)}`;
        }
        const result = await axios_1.default.delete(url, config);
        console.log(result, ' result after delete event');
    }
    catch (e) {
        console.log(e, ' unable to delete google event');
    }
};
exports.deleteGoogleEvent = deleteGoogleEvent;
// delete secondary calendar
const deleteGoogleCalendar = async (client, userId, calendarId) => {
    try {
        // get token =
        const token = await (0, exports.getGoogleToken)(client, userId);
        let url = `${constants_2.googleCalendarURL}/${encodeURI(calendarId)}`;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        const results = await axios_1.default.delete(url, config);
        console.log(results, ' successfully deleted secondary calendar');
    }
    catch (e) {
        console.log(e, ' unable to catch google calendar');
    }
};
exports.deleteGoogleCalendar = deleteGoogleCalendar;
const getGoogleColors = async (token) => {
    try {
        const url = constants_2.googleColorUrl;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        const { data } = await axios_1.default.get(url, config);
        console.log(data, ' data for get colors');
        return data;
    }
    catch (e) {
        console.log(e, ' unable to get google colors');
    }
};
exports.getGoogleColors = getGoogleColors;
const clearGoogleCalendar = async (client, userId, calendarId) => {
    try {
        // get token =
        const token = await (0, exports.getGoogleToken)(client, userId);
        let url = `${constants_2.googleURL}/${encodeURI(calendarId)}/clear`;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        const results = await axios_1.default.post(url, undefined, config);
        console.log(results, ' results from post');
    }
    catch (e) {
        console.log(e, ' unable to delete google event');
    }
};
exports.clearGoogleCalendar = clearGoogleCalendar;
const patchGoogleEvent = async (client, userId, calendarId, eventId, endDateTime, // either endDateTime or endDate - all day vs specific period
startDateTime, conferenceDataVersion, maxAttendees, sendUpdates, anyoneCanAddSelf, attendees, conferenceData, summary, description, timezone, // required for recurrence
startDate, endDate, extendedProperties, guestsCanInviteOthers, guestsCanModify, guestsCanSeeOtherGuests, originalStartDateTime, originalStartDate, recurrence, reminders, source, status, transparency, visibility, iCalUID, attendeesOmitted, hangoutLink, privateCopy, locked, attachments, eventType, location) => {
    try {
        // get token =
        const token = await (0, exports.getGoogleToken)(client, userId);
        let url = `${constants_2.googleURL}/${encodeURI(calendarId)}/events/${encodeURI(eventId)}`;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        // if any query parameters build them
        if (maxAttendees ||
            sendUpdates ||
            (typeof conferenceDataVersion === 'number' && conferenceDataVersion > -1)) {
            url = `${url}?`;
            let params = {};
            if (maxAttendees) {
                params.maxAttendees = maxAttendees;
            }
            if (sendUpdates) {
                params.sendUpdates = sendUpdates;
            }
            if (typeof conferenceDataVersion === 'number' &&
                conferenceDataVersion > -1) {
                params.conferenceDataVersion = conferenceDataVersion;
            }
            if (params?.maxAttendees ||
                params?.sendUpdates ||
                params?.conferenceDataVersion > -1) {
                url = `${url}${qs_1.default.stringify(params)}`;
            }
        }
        // create request body
        let data = {};
        if (endDate && timezone && !endDateTime) {
            const end = {
                date: (0, date_utils_1.dayjs)(endDate).format('YYYY-MM-DD'),
                timeZone: timezone,
            };
            data.end = end;
        }
        if (endDateTime && timezone && !endDate) {
            const end = {
                dateTime: (0, date_utils_1.dayjs)(endDateTime).format(),
                timeZone: timezone,
            };
            data.end = end;
        }
        if (startDate && timezone && !startDateTime) {
            const start = {
                date: (0, date_utils_1.dayjs)(startDate).format('YYYY-MM-DD'),
                timeZone: timezone,
            };
            data.start = start;
        }
        if (startDateTime && timezone && !startDate) {
            const start = {
                dateTime: (0, date_utils_1.dayjs)(startDateTime).format(),
                timeZone: timezone,
            };
            data.start = start;
        }
        if (originalStartDate && timezone && !originalStartDateTime) {
            const originalStartTime = {
                date: (0, date_utils_1.dayjs)(originalStartDate).format('YYYY-MM-DD'),
                timeZone: timezone,
            };
            data.originalStartTime = originalStartTime;
        }
        if (originalStartDateTime && timezone && !originalStartDate) {
            const originalStartTime = {
                dateTime: (0, date_utils_1.dayjs)(originalStartDateTime).format(),
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
                        requestId: conferenceData?.requestId || (0, uuid_1.v4)(),
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
        if (description && description?.length > 0) {
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
        if (reminders) {
            data = { ...data, reminders };
        }
        if (source?.title || source?.url) {
            data = { ...data, source };
        }
        if (attachments?.[0]?.fileId) {
            data = { ...data, attachments };
        }
        if (eventType && eventType?.length > 0) {
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
        if (iCalUID && iCalUID?.length > 0) {
            data = { ...data, iCalUID };
        }
        if (attendeesOmitted) {
            data = { ...data, attendeesOmitted };
        }
        if (hangoutLink && hangoutLink?.length > 0) {
            data = { ...data, hangoutLink };
        }
        if (summary && summary?.length > 0) {
            data = { ...data, summary };
        }
        if (location && location?.length > 0) {
            data = { ...data, location };
        }
        console.log(url, data, ' url, data inside google patch');
        const results = await axios_1.default.patch(url, data, config);
        console.log(results, ' results from patch google event');
    }
    catch (e) {
        console.log(e, ' unable to patch google event');
    }
};
exports.patchGoogleEvent = patchGoogleEvent;
const createGoogleEvent = async (client, userId, calendarId, endDateTime, // either endDateTime or endDate - all day vs specific period
startDateTime, conferenceDataVersion, maxAttendees, sendUpdates, anyoneCanAddSelf, attendees, conferenceData, summary, description, timezone, // required for recurrence
startDate, endDate, extendedProperties, guestsCanInviteOthers, guestsCanModify, guestsCanSeeOtherGuests, originalStartDateTime, originalStartDate, recurrence, reminders, source, status, transparency, visibility, iCalUID, attendeesOmitted, hangoutLink, privateCopy, locked, attachments, eventType, location) => {
    try {
        // get token =
        const token = await (0, exports.getGoogleToken)(client, userId);
        let url = `${constants_2.googleURL}/${encodeURI(calendarId)}/events`;
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        // if any query parameters build them
        // first
        if (maxAttendees ||
            sendUpdates ||
            (typeof conferenceDataVersion === 'number' && conferenceDataVersion > 0)) {
            url = `${url}?`;
            let params = {};
            if (maxAttendees) {
                params = { ...params, maxAttendees };
            }
            if (sendUpdates) {
                params = { ...params, sendUpdates };
            }
            if (typeof conferenceDataVersion === 'number' &&
                conferenceDataVersion > -1) {
                params = { ...params, conferenceDataVersion };
            }
            if (params?.maxAttendees ||
                params?.sendUpdates ||
                params?.conferenceDataVersion > -1) {
                url = `${url}${qs_1.default.stringify(params)}`;
            }
        }
        // create request body
        let data = {};
        if (endDateTime && timezone && !endDate) {
            const end = {
                dateTime: (0, date_utils_1.dayjs)(endDateTime).format(),
                timeZone: timezone,
            };
            data.end = end;
        }
        if (endDate && timezone && !endDateTime) {
            const end = {
                date: (0, date_utils_1.dayjs)(endDate).format('YYYY-MM-DD'),
                timeZone: timezone,
            };
            data.end = end;
        }
        if (startDate && timezone && !startDateTime) {
            const start = {
                date: (0, date_utils_1.dayjs)(startDate).format('YYYY-MM-DD'),
                timeZone: timezone,
            };
            data.start = start;
        }
        if (startDateTime && timezone && !startDate) {
            const start = {
                dateTime: (0, date_utils_1.dayjs)(startDateTime).format(),
                timeZone: timezone,
            };
            data.start = start;
        }
        if (originalStartDate && timezone && !originalStartDateTime) {
            const originalStartTime = {
                date: (0, date_utils_1.dayjs)(originalStartDate).format('YYYY-MM-DD'),
                timeZone: timezone,
            };
            data.originalStartTime = originalStartTime;
        }
        if (originalStartDateTime && timezone && !originalStartDate) {
            const originalStartTime = {
                dateTime: (0, date_utils_1.dayjs)(originalStartDateTime).format(),
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
                        requestId: conferenceData?.requestId || (0, uuid_1.v4)(),
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
        if (description && description?.length > 0) {
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
        if (reminders) {
            data = { ...data, reminders };
        }
        if (source?.title || source?.url) {
            data = { ...data, source };
        }
        if (attachments?.[0]?.fileId) {
            data = { ...data, attachments };
        }
        if (eventType && eventType?.length > 0) {
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
        if (iCalUID && iCalUID?.length > 0) {
            data = { ...data, iCalUID };
        }
        if (attendeesOmitted) {
            data = { ...data, attendeesOmitted };
        }
        if (hangoutLink && hangoutLink?.length > 0) {
            data = { ...data, hangoutLink };
        }
        if (summary && summary?.length > 0) {
            data = { ...data, summary };
        }
        if (location && location?.length > 0) {
            data = { ...data, location };
        }
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' results from googleCreateEvent');
        return results?.data?.id;
    }
    catch (e) {
        console.log(e, ' createGoogleEvent');
        console.log(e?.response?.data?.error?.message, ' error from googleCreateEvent');
        console.log(e?.toJSON(), ' error from googleCreateEvent');
    }
};
exports.createGoogleEvent = createGoogleEvent;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ29vZ2xlQ2FsZW5kYXJIZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnb29nbGVDYWxlbmRhckhlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSxrREFBMEI7QUFDMUIsZ0ZBQXdEO0FBRXhELGdEQUF3QztBQUN4Qyw0Q0FBb0I7QUFDcEIsK0JBQWtDO0FBQ2xDLDhDQUl3QjtBQUt4QiwwREFPb0M7QUF3QnBDLGdEQUE0RDtBQUU1RCw4Q0FBOEM7QUFDOUMsMkNBQTBFO0FBQzFFLHNJQUF1RztBQUV2RyxzSUFBOEc7QUFFOUcsa0lBQTBHO0FBQzFHLDRJQUFvSDtBQUVwSCx1QkFBdUI7QUFDdkIsbUNBQW1DO0FBQ25DLElBQUk7QUFDSix1QkFBdUI7QUFDdkIscUNBQXFDO0FBRXJDLHFEQUFxRDtBQUU5QyxNQUFNLDZCQUE2QixHQUFHLEtBQUssRUFDaEQsTUFBMkMsRUFDM0MsTUFBYyxFQUNkLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLGdCQUFnQixHQUFHLENBQ3ZCLE1BQU0sTUFBTSxDQUFDLEtBQUssQ0FDaEI7WUFDRSxLQUFLLEVBQUUsK0NBQXFDO1lBQzVDLFNBQVMsRUFBRTtnQkFDVCxNQUFNO2FBQ1A7U0FDRixDQUNGLENBQ0YsRUFBRSxJQUFJLEVBQUUsMEJBQTBCLENBQUM7UUFFcEMsaURBQWlEO1FBQ2pELEtBQUssSUFBSSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsR0FBRyxnQkFBZ0IsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztZQUNqRCxJQUFJLElBQUEsa0JBQUssR0FBRSxDQUFDLE9BQU8sQ0FBQyxJQUFBLGtCQUFLLEVBQUMsZ0JBQWdCLENBQUMsQ0FBQyxDQUFDLEVBQUUsVUFBVSxDQUFDLENBQUMsRUFBRSxDQUFDO2dCQUM1RCxNQUFNLElBQUEsNkJBQXFCLEVBQUMsZ0JBQWdCLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUNuRCxDQUFDO1FBQ0gs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QUVELElBQUksUUFBUSxJQUFJLFFBQVEsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7WUFDckMsSUFBSSxHQUFHLEVBQUUsR0FBRyxJQUFJLEVBQUUsUUFBUSxFQUFFLENBQUM7UUFDL0IsQ0FBQztRQUVELE1BQU0sT0FBTyxHQUFHLE1BQU0sZUFBSyxDQUFDLElBQUksQ0FBZ0IsR0FBRyxFQUFFLElBQUksRUFBRSxNQUFNLENBQUMsQ0FBQztRQUVuRSxPQUFPLENBQUMsR0FBRyxDQUFDLE9BQU8sRUFBRSxpQ0FBaUMsQ0FBQyxDQUFDO1FBQ3hELE9BQU8sT0FBTyxFQUFFLElBQUksRUFBRSxFQUFFLENBQUM7SUFDM0IsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsb0JBQW9CLENBQUMsQ0FBQztRQUNyQyxPQUFPLENBQUMsR0FBRyxDQUNULENBQUMsRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQ2pDLCtCQUErQixDQUNoQyxDQUFDO1FBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsTUFBTSxFQUFFLEVBQUUsK0JBQStCLENBQUMsQ0FBQztJQUM1RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBMVFXLFFBQUEsaUJBQWlCLHFCQTBRNUIiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnO1xuaW1wb3J0IFNlc3Npb24gZnJvbSAnc3VwZXJ0b2tlbnMtd2ViLWpzL3JlY2lwZS9zZXNzaW9uJztcblxuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAbGliL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHFzIGZyb20gJ3FzJztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCB7XG4gIGdvb2dsZUF0b21pY1dlYkF1dGhSZWZyZXNoVXJsLFxuICBnb29nbGVDYWxlbmRhckFuZHJvaWRBdXRoUmVmcmVzaFVybCxcbiAgZ29vZ2xlQ2FsZW5kYXJJb3NBdXRoUmVmcmVzaFVybCxcbn0gZnJvbSAnQGxpYi9jb25zdGFudHMnO1xuLy8gZGF5anMuZXh0ZW5kKHV0YylcblxuaW1wb3J0IHsgZ29vZ2xlQ29uZmlnIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvY29uZmlncyc7XG5cbmltcG9ydCB7XG4gIGdvb2dsZVVSTCxcbiAgZ29vZ2xlQ2FsZW5kYXJVUkwsXG4gIGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgZ29vZ2xlUmVzb3VyY2VOYW1lLFxuICBnb29nbGVDb2xvclVybCxcbiAgc2VsZkdvb2dsZUNhbGVuZGFyV2F0Y2hVcmwsXG59IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIGNhbGVuZGFyUmVzcG9uc2UsXG4gIGV2ZW50UmVzcG9uc2UsXG4gIEdvb2dsZUF0dGVuZGVlVHlwZSxcbiAgQ29uZmVyZW5jZURhdGFUeXBlLFxuICBleHRlbmRlZFByb3BlcnRpZXMsXG4gIEdvb2dsZVJlbWluZGVyVHlwZSxcbiAgc291cmNlLFxuICBUcmFuc3BhcmVuY3lUeXBlLFxuICBWaXNpYmlsaXR5VHlwZSxcbiAgU2VuZFVwZGF0ZXNUeXBlLFxuICBhbGxvd2VkQ29uZmVyZW5jZVNvbHV0aW9uVHlwZSxcbiAgYXR0YWNobWVudCxcbiAgZXZlbnRUeXBlMSxcbiAgLy8gQ29sbGVjdGlvbnMsXG4gIC8vIEludGVybmFscyxcbiAgLy8gSW5zdGFuY2VDcmVhdGlvbk9wdGlvbnMsXG4gIERlZmF1bHRSZW1pbmRlclR5cGUsXG4gIE5vdGlmaWNhdGlvblR5cGUsXG4gIGNvbG9yUmVzcG9uc2VUeXBlLFxuICBSZWZyZXNoVG9rZW5SZXNwb25zZUJvZHlUeXBlLFxufSBmcm9tICdAbGliL2NhbGVuZGFyTGliL3R5cGVzJztcblxuaW1wb3J0IHsgdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbiB9IGZyb20gJ0BsaWIvYXBpLWhlbHBlcic7XG5cbmltcG9ydCB7IGhhc3VyYUFwaVVybCB9IGZyb20gJ0BsaWIvY29uc3RhbnRzJztcbmltcG9ydCB7IEFwb2xsb0NsaWVudCwgZ3FsLCBOb3JtYWxpemVkQ2FjaGVPYmplY3QgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5pbXBvcnQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2UgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldENhbGVuZGFySW50ZWdyYXRpb25CeVJlc291cmNlQW5kTmFtZSc7XG5pbXBvcnQgeyBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhbGVuZGFyX0ludGVncmF0aW9uVHlwZSc7XG5pbXBvcnQgZ2V0Q2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlDYWxlbmRhcklkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRDYWxlbmRhclB1c2hOb3RpZmljYXRpb25CeUNhbGVuZGFySWQnO1xuaW1wb3J0IHsgQ2FsZW5kYXJXZWJob29rVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhbGVuZGFyV2ViaG9va1R5cGUnO1xuaW1wb3J0IGxpc3RDYWxlbmRhclB1c2hOb3RpZmljYXRpb25zQnlVc2VySWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2xpc3RDYWxlbmRhclB1c2hOb3RpZmljYXRpb25zQnlVc2VySWQnO1xuaW1wb3J0IGRlbGV0ZUNhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbkJ5Q2FsZW5kYXJJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlQ2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlDYWxlbmRhcklkJztcblxuLy8gdHlwZSBDb2xsZWN0aW9ucyA9IHtcbi8vICAgICBba2V5OiBzdHJpbmddOiBSeENvbGxlY3Rpb247XG4vLyB9XG4vLyB0eXBlIEludGVybmFscyA9IGFueVxuLy8gdHlwZSBJbnN0YW5jZUNyZWF0aW9uT3B0aW9ucyA9IGFueVxuXG4vLyBjb25zdCByZXN1bHQgPSBhd2FpdCBheGlvcy5wb3N0KHVybCwgZGF0YSwgY29uZmlnKVxuXG5leHBvcnQgY29uc3QgY2hlY2tJZkNhbGVuZGFyV2ViaG9va0V4cGlyZWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjYWxlbmRhcldlYmhvb2tzID0gKFxuICAgICAgYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb246IENhbGVuZGFyV2ViaG9va1R5cGVbXSB9PihcbiAgICAgICAge1xuICAgICAgICAgIHF1ZXJ5OiBsaXN0Q2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uc0J5VXNlcklkLFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH1cbiAgICAgIClcbiAgICApPy5kYXRhPy5DYWxlbmRhcl9QdXNoX05vdGlmaWNhdGlvbjtcblxuICAgIC8vIGxvb3AgdGhyb3VnaCBlYWNoIGFuZCByZWZyZXNoIGV4cGlyZWQgd2ViaG9va3NcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGNhbGVuZGFyV2ViaG9va3MubGVuZ3RoOyBpKyspIHtcbiAgICAgIGlmIChkYXlqcygpLmlzQWZ0ZXIoZGF5anMoY2FsZW5kYXJXZWJob29rc1tpXT8uZXhwaXJhdGlvbikpKSB7XG4gICAgICAgIGF3YWl0IGVuYWJsZUNhbGVuZGFyV2ViaG9vayhjYWxlbmRhcldlYmhvb2tzW2ldKTtcbiAgICAgIH1cbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjaGVjayBpZiBjYWxlbmRhciB3ZWJob29rIGV4cGlyZWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGVuYWJsZUNhbGVuZGFyV2ViaG9vayA9IGFzeW5jICh3ZWJob29rOiBDYWxlbmRhcldlYmhvb2tUeXBlKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBTZXNzaW9uLmdldEFjY2Vzc1Rva2VuKCk7XG4gICAgY29uc3QgdXJsID0gc2VsZkdvb2dsZUNhbGVuZGFyV2F0Y2hVcmw7XG4gICAgY29uc3QgY29uZmlnID0ge1xuICAgICAgaGVhZGVyczoge1xuICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IGRhdGEgPSB7XG4gICAgICBjYWxlbmRhcklkOiB3ZWJob29rPy5jYWxlbmRhcklkLFxuICAgICAgdXNlcklkOiB3ZWJob29rPy51c2VySWQsXG4gICAgICBjaGFubmVsSWQ6IHdlYmhvb2s/LmlkLFxuICAgIH07XG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGF4aW9zLnBvc3QodXJsLCBkYXRhLCBjb25maWcpO1xuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgcmVzdWx0cyBpbnNpZGUgZW5hYmxlQ2FsZW5kYXJXZWJob29rJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBlbmFibGUgY2FsZW5kYXIgd2ViaG9vaycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlQ2FsZW5kYXJXZWJob29rID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYWxlbmRhcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIC8qKlxuICAgICAqIGNvbnN0IGdvb2dsZUludGVnID0gKGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH0+KHtcbiAgICAgIHF1ZXJ5OiBnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICB1c2VySWQsXG4gICAgICAgIG5hbWU6IGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgICAgICAgcmVzb3VyY2U6IGdvb2dsZUNhbGVuZGFyUmVzb3VyY2UsXG4gICAgICB9XG4gICAgfSkpPy5kYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8uWzBdXG4gICAgICovXG4gICAgY29uc3QgcmVzID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICBkZWxldGVfQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb246IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IGRlbGV0ZUNhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbkJ5Q2FsZW5kYXJJZCxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgfSxcbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSBkZWxldGVDYWxlbmRhcldlYmhvb2tCeUNhbGVuZGFySWQnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBjYWxlbmRhciB3ZWIgaG9vaycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0Q2FsZW5kYXJXZWJob29rID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYWxlbmRhcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGNhbGVuZGFyV2ViaG9vayA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyX1B1c2hfTm90aWZpY2F0aW9uOiBDYWxlbmRhcldlYmhvb2tUeXBlW10gfT4oXG4gICAgICAgIHtcbiAgICAgICAgICBxdWVyeTogZ2V0Q2FsZW5kYXJQdXNoTm90aWZpY2F0aW9uQnlDYWxlbmRhcklkLFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9XG4gICAgICApXG4gICAgKT8uZGF0YT8uQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb24/LlswXTtcblxuICAgIGNvbnNvbGUubG9nKGNhbGVuZGFyV2ViaG9vaywgJyBjYWxlbmRhcldlYmhvb2snKTtcbiAgICByZXR1cm4gY2FsZW5kYXJXZWJob29rO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNhbGVuZGFyIHdlYmhvb2snKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEdvb2dsZUNhbGVuZGFyU3luY0FwaVRva2VuID0gYXN5bmMgKCkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRva2VuID0gYXdhaXQgU2Vzc2lvbi5nZXRBY2Nlc3NUb2tlbigpO1xuICAgIGNvbnN0IHVybCA9IGhhc3VyYUFwaVVybDtcbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBBY2NlcHQ6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldEdvb2dsZUNhbGVuZGFyU3luY1Rva2VuJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIHF1ZXJ5IEdldEdvb2dsZUNhbGVuZGFyU3luY1Rva2VuKCRuYW1lOiBTdHJpbmchLCAkcmVzb3VyY2U6IFN0cmluZyEpIHtcbiAgICAgICAgQWRtaW4od2hlcmU6IHtuYW1lOiB7X2VxOiAkbmFtZX0sIHJlc291cmNlOiB7X2VxOiAkcmVzb3VyY2V9fSkge1xuICAgICAgICAgIGlkXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIHRva2VuXG4gICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgbmFtZTogJ2dvb2dsZUNhbGVuZGFyU3luYycsXG4gICAgICByZXNvdXJjZTogJ2F3cycsXG4gICAgfTtcblxuICAgIGNvbnN0IGRhdGEgPSB7XG4gICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgcXVlcnksXG4gICAgICB2YXJpYWJsZXMsXG4gICAgfTtcbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgYXhpb3MucG9zdCh1cmwsIGRhdGEsIGNvbmZpZyk7XG5cbiAgICBpZiAocmVzdWx0cz8uZGF0YT8uQWRtaW4/LlswXT8uaWQpIHtcbiAgICAgIGNvbnN0IHRva2VuID0gcmVzdWx0cz8uZGF0YT8uQWRtaW4/LlswXT8udG9rZW47XG4gICAgICByZXR1cm4gdG9rZW47XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGFwaVRva2VuJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBob3VzZUtlZXBTeW5jRW5hYmxlZEdvb2dsZUNhbGVuZGFyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHRva2VuIGFuZCBleHBpcmVzQXRcbiAgICBjb25zdCBnb29nbGVJbnRlZyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldENhbGVuZGFySW50ZWdyYXRpb25CeVJlc291cmNlLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgbmFtZTogZ29vZ2xlQ2FsZW5kYXJOYW1lLFxuICAgICAgICAgIHJlc291cmNlOiBnb29nbGVSZXNvdXJjZU5hbWUsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICk/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5bMF07XG5cbiAgICBjb25zdCBvbGRFbmFibGVkID0gZ29vZ2xlSW50ZWc/LmVuYWJsZWQ7XG4gICAgY29uc3Qgb2xkU3luY0VuYWJsZWQgPSBnb29nbGVJbnRlZz8uc3luY0VuYWJsZWQ7XG4gICAgY29uc3QgdXBkYXRlZEF0ID0gZGF5anMoKS50b0lTT1N0cmluZygpO1xuXG4gICAgY29uc3QgdXBkYXRlSW50ZWdyYXRpb24gPSBncWxgXG4gICAgICBtdXRhdGlvbiBVcGRhdGVDYWxlbmRhckludGVncmF0aW9uQnlJZChcbiAgICAgICAgJGlkOiB1dWlkIVxuICAgICAgICAkc3luY0VuYWJsZWQ6IEJvb2xlYW5cbiAgICAgICkge1xuICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsoXG4gICAgICAgICAgX3NldDogeyBzeW5jRW5hYmxlZDogJHN5bmNFbmFibGVkIH1cbiAgICAgICAgICBwa19jb2x1bW5zOiB7IGlkOiAkaWQgfVxuICAgICAgICApIHtcbiAgICAgICAgICBhcHBBY2NvdW50SWRcbiAgICAgICAgICBhcHBFbWFpbFxuICAgICAgICAgIGFwcElkXG4gICAgICAgICAgY29sb3JzXG4gICAgICAgICAgY29udGFjdEVtYWlsXG4gICAgICAgICAgY29udGFjdE5hbWVcbiAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICBlbmFibGVkXG4gICAgICAgICAgZXhwaXJlc0F0XG4gICAgICAgICAgaWRcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgcGFnZVRva2VuXG4gICAgICAgICAgcGFzc3dvcmRcbiAgICAgICAgICByZWZyZXNoVG9rZW5cbiAgICAgICAgICBzeW5jRW5hYmxlZFxuICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICB1c2VySWRcbiAgICAgICAgICB1c2VybmFtZVxuICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgbGV0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgaWQ6IGdvb2dsZUludGVnPy5pZCxcbiAgICB9O1xuXG4gICAgaWYgKG9sZEVuYWJsZWQgJiYgIW9sZFN5bmNFbmFibGVkKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7XG4gICAgICAgIC4uLnZhcmlhYmxlcyxcbiAgICAgICAgc3luY0VuYWJsZWQ6IHRydWUsXG4gICAgICAgIHVwZGF0ZWRBdCxcbiAgICAgIH07XG4gICAgfSBlbHNlIGlmICghb2xkRW5hYmxlZCAmJiBvbGRTeW5jRW5hYmxlZCkge1xuICAgICAgdmFyaWFibGVzID0ge1xuICAgICAgICAuLi52YXJpYWJsZXMsXG4gICAgICAgIHN5bmNFbmFibGVkOiBmYWxzZSxcbiAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAodmFyaWFibGVzPy51cGRhdGVkQXQpIHtcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGUoe1xuICAgICAgICBtdXRhdGlvbjogdXBkYXRlSW50ZWdyYXRpb24sXG4gICAgICAgIHZhcmlhYmxlcyxcbiAgICAgIH0pO1xuICAgIH1cbiAgICBpZiAob2xkRW5hYmxlZCAmJiAhb2xkU3luY0VuYWJsZWQpIHtcbiAgICAgIGF3YWl0IGdldEdvb2dsZVRva2VuKGNsaWVudCwgdXNlcklkKTtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBob3VzZWtlZXAgc3luYyBlbmFibGVkIGZvciBnb29nbGUgY2FsZW5kYXIgaW50ZWdyYXRpb24nXG4gICAgKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdvb2dsZU1lZXRBdmFpbGFibGUgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZVRva2VuKGNsaWVudCwgdXNlcklkKTtcblxuICAgIGlmICh0b2tlbiAmJiB0b2tlbj8ubGVuZ3RoID4gMCkge1xuICAgICAgcmV0dXJuIHRydWU7XG4gICAgfVxuICAgIHJldHVybiBmYWxzZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZ29vZ2xlIG1lZXQgaXMgbm90IGF2aWxhYmxlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRHb29nbGVUb2tlbiA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIC8vIGdldCB0b2tlbiBhbmQgZXhwaXJlc0F0XG4gICAgY29uc3QgZ29vZ2xlSW50ZWcgPSAoXG4gICAgICBhd2FpdCBjbGllbnQucXVlcnk8eyBDYWxlbmRhcl9JbnRlZ3JhdGlvbjogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGVbXSB9Pih7XG4gICAgICAgIHF1ZXJ5OiBnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIG5hbWU6IGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgICAgICAgICByZXNvdXJjZTogZ29vZ2xlUmVzb3VyY2VOYW1lLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApPy5kYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8uWzBdO1xuXG4gICAgY29uc3QgdG9rZW4gPSBnb29nbGVJbnRlZz8udG9rZW47XG4gICAgY29uc3QgZXhwaXJlc0F0ID0gZ29vZ2xlSW50ZWc/LmV4cGlyZXNBdDtcbiAgICBjb25zdCBvbGRSZWZyZXNoVG9rZW4gPSBnb29nbGVJbnRlZz8ucmVmcmVzaFRva2VuO1xuXG4gICAgaWYgKGRheWpzKCkuaXNBZnRlcihkYXlqcyhleHBpcmVzQXQpKSkge1xuICAgICAgbGV0IG5ld0FjY2Vzc1Rva2VuID0gJyc7XG4gICAgICBsZXQgbmV3UmVmcmVzaFRva2VuID0gJyc7XG4gICAgICBsZXQgbmV3RXhwaXJlc0F0ID0gJyc7XG5cbiAgICAgIGlmIChnb29nbGVJbnRlZz8uY2xpZW50VHlwZSA9PT0gJ2lvcycgJiYgb2xkUmVmcmVzaFRva2VuKSB7XG4gICAgICAgIGNvbnN0IHVybCA9IGdvb2dsZUNhbGVuZGFySW9zQXV0aFJlZnJlc2hVcmw7XG4gICAgICAgIGNvbnN0IHRva2VuID0gYXdhaXQgU2Vzc2lvbi5nZXRBY2Nlc3NUb2tlbigpO1xuICAgICAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgIH0sXG4gICAgICAgIH07XG5cbiAgICAgICAgY29uc3QgZGF0YSA9IHtcbiAgICAgICAgICByZWZyZXNoVG9rZW46IG9sZFJlZnJlc2hUb2tlbixcbiAgICAgICAgfTtcblxuICAgICAgICBjb25zdCByZXN1bHRzOiB7XG4gICAgICAgICAgZGF0YToge1xuICAgICAgICAgICAgbWVzc2FnZTogc3RyaW5nO1xuICAgICAgICAgICAgZXZlbnQ6IFJlZnJlc2hUb2tlblJlc3BvbnNlQm9keVR5cGU7XG4gICAgICAgICAgfTtcbiAgICAgICAgfSA9IGF3YWl0IGF4aW9zLnBvc3QodXJsLCBkYXRhLCBjb25maWcpO1xuICAgICAgICBjb25zb2xlLmxvZyhyZXN1bHRzLCAnIHJlc3VsdHMgaW5zaWRlIGVuYWJsZUdvb2dsZUNhbGVuZGFyU3luYycpO1xuXG4gICAgICAgIG5ld0FjY2Vzc1Rva2VuID0gcmVzdWx0cz8uZGF0YT8uZXZlbnQ/LmFjY2Vzc190b2tlbjtcbiAgICAgICAgbmV3UmVmcmVzaFRva2VuID0gb2xkUmVmcmVzaFRva2VuO1xuICAgICAgICBuZXdFeHBpcmVzQXQgPSBkYXlqcygpXG4gICAgICAgICAgLmFkZChyZXN1bHRzPy5kYXRhPy5ldmVudD8uZXhwaXJlc19pbiwgJ3NlY29uZHMnKVxuICAgICAgICAgIC50b0lTT1N0cmluZygpO1xuICAgICAgfSBlbHNlIGlmIChcbiAgICAgICAgKGdvb2dsZUludGVnPy5jbGllbnRUeXBlID09PSAnd2ViJyB8fFxuICAgICAgICAgIGdvb2dsZUludGVnPy5jbGllbnRUeXBlID09PSAnYW5kcm9pZCcpICYmXG4gICAgICAgIG9sZFJlZnJlc2hUb2tlblxuICAgICAgKSB7XG4gICAgICAgIGNvbnN0IHVybCA9IGdvb2dsZUNhbGVuZGFyQW5kcm9pZEF1dGhSZWZyZXNoVXJsO1xuICAgICAgICBjb25zdCB0b2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcbiAgICAgICAgY29uc3QgY29uZmlnID0ge1xuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9O1xuXG4gICAgICAgIGNvbnN0IGRhdGEgPSB7XG4gICAgICAgICAgcmVmcmVzaFRva2VuOiBvbGRSZWZyZXNoVG9rZW4sXG4gICAgICAgIH07XG5cbiAgICAgICAgY29uc3QgcmVzdWx0czoge1xuICAgICAgICAgIGRhdGE6IHtcbiAgICAgICAgICAgIG1lc3NhZ2U6IHN0cmluZztcbiAgICAgICAgICAgIGV2ZW50OiBSZWZyZXNoVG9rZW5SZXNwb25zZUJvZHlUeXBlO1xuICAgICAgICAgIH07XG4gICAgICAgIH0gPSBhd2FpdCBheGlvcy5wb3N0KHVybCwgZGF0YSwgY29uZmlnKTtcbiAgICAgICAgY29uc29sZS5sb2cocmVzdWx0cywgJyByZXN1bHRzIGluc2lkZSBlbmFibGVHb29nbGVDYWxlbmRhclN5bmMnKTtcblxuICAgICAgICBuZXdBY2Nlc3NUb2tlbiA9IHJlc3VsdHM/LmRhdGE/LmV2ZW50Py5hY2Nlc3NfdG9rZW47XG4gICAgICAgIG5ld1JlZnJlc2hUb2tlbiA9IG9sZFJlZnJlc2hUb2tlbjtcbiAgICAgICAgbmV3RXhwaXJlc0F0ID0gZGF5anMoKVxuICAgICAgICAgIC5hZGQocmVzdWx0cz8uZGF0YT8uZXZlbnQ/LmV4cGlyZXNfaW4sICdzZWNvbmRzJylcbiAgICAgICAgICAudG9JU09TdHJpbmcoKTtcbiAgICAgIH0gZWxzZSBpZiAoZ29vZ2xlSW50ZWc/LmNsaWVudFR5cGUgPT09ICdhdG9taWMtd2ViJyAmJiBvbGRSZWZyZXNoVG9rZW4pIHtcbiAgICAgICAgY29uc3QgdXJsID0gZ29vZ2xlQXRvbWljV2ViQXV0aFJlZnJlc2hVcmw7XG4gICAgICAgIGNvbnN0IHRva2VuID0gYXdhaXQgU2Vzc2lvbi5nZXRBY2Nlc3NUb2tlbigpO1xuICAgICAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgIH0sXG4gICAgICAgIH07XG5cbiAgICAgICAgY29uc3QgZGF0YSA9IHtcbiAgICAgICAgICByZWZyZXNoVG9rZW46IG9sZFJlZnJlc2hUb2tlbixcbiAgICAgICAgfTtcblxuICAgICAgICBjb25zdCByZXN1bHRzOiB7XG4gICAgICAgICAgZGF0YToge1xuICAgICAgICAgICAgbWVzc2FnZTogc3RyaW5nO1xuICAgICAgICAgICAgZXZlbnQ6IFJlZnJlc2hUb2tlblJlc3BvbnNlQm9keVR5cGU7XG4gICAgICAgICAgfTtcbiAgICAgICAgfSA9IGF3YWl0IGF4aW9zLnBvc3QodXJsLCBkYXRhLCBjb25maWcpO1xuICAgICAgICBjb25zb2xlLmxvZyhyZXN1bHRzLCAnIHJlc3VsdHMgaW5zaWRlIGVuYWJsZUdvb2dsZUNhbGVuZGFyU3luYycpO1xuXG4gICAgICAgIG5ld0FjY2Vzc1Rva2VuID0gcmVzdWx0cz8uZGF0YT8uZXZlbnQ/LmFjY2Vzc190b2tlbjtcbiAgICAgICAgbmV3UmVmcmVzaFRva2VuID0gb2xkUmVmcmVzaFRva2VuO1xuICAgICAgICBuZXdFeHBpcmVzQXQgPSBkYXlqcygpXG4gICAgICAgICAgLmFkZChyZXN1bHRzPy5kYXRhPy5ldmVudD8uZXhwaXJlc19pbiwgJ3NlY29uZHMnKVxuICAgICAgICAgIC50b0lTT1N0cmluZygpO1xuICAgICAgfVxuXG4gICAgICAvL2dvb2dsZUF0b21pY1dlYkF1dGhSZWZyZXNoVXJsXG5cbiAgICAgIGF3YWl0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oXG4gICAgICAgIGNsaWVudCxcbiAgICAgICAgZ29vZ2xlSW50ZWc/LmlkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIG5ld0FjY2Vzc1Rva2VuLFxuICAgICAgICBuZXdSZWZyZXNoVG9rZW4sXG4gICAgICAgIG5ld0V4cGlyZXNBdCxcbiAgICAgICAgZ29vZ2xlSW50ZWc/LmNsaWVudFR5cGUgPT09ICdhbmRyb2lkJyA/ICd3ZWInIDogZ29vZ2xlSW50ZWc/LmNsaWVudFR5cGVcbiAgICAgICk7XG5cbiAgICAgIHJldHVybiBuZXdBY2Nlc3NUb2tlbjtcbiAgICB9XG5cbiAgICByZXR1cm4gdG9rZW47XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXRHb29nbGVUb2tlbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcGF0Y2hHb29nbGVDYWxlbmRhciA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgc3VtbWFyeT86IHN0cmluZyxcbiAgZGVzY3JpcHRpb24/OiBzdHJpbmcsXG4gIGxvY2F0aW9uPzogc3RyaW5nLFxuICB0aW1lWm9uZT86IHN0cmluZyxcbiAgYWxsb3dlZENvbmZlcmVuY2VTb2x1dGlvblR5cGVzPzogYWxsb3dlZENvbmZlcmVuY2VTb2x1dGlvblR5cGVbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHRva2VuID1cbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZVRva2VuKGNsaWVudCwgdXNlcklkKTtcbiAgICBsZXQgdXJsID0gYCR7Z29vZ2xlQ2FsZW5kYXJVUkx9LyR7ZW5jb2RlVVJJKGNhbGVuZGFySWQpfWA7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBBY2NlcHQ6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGxldCBkYXRhOiBhbnkgPSB7fTtcblxuICAgIGlmIChzdW1tYXJ5ICYmIHN1bW1hcnk/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHN1bW1hcnkgfTtcbiAgICB9XG5cbiAgICBpZiAoZGVzY3JpcHRpb24gJiYgZGVzY3JpcHRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGRlc2NyaXB0aW9uIH07XG4gICAgfVxuXG4gICAgaWYgKGxvY2F0aW9uICYmIGxvY2F0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBsb2NhdGlvbiB9O1xuICAgIH1cblxuICAgIGlmICh0aW1lWm9uZSAmJiB0aW1lWm9uZT8ubGVuZ3RoID4gMCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgdGltZVpvbmUgfTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICBhbGxvd2VkQ29uZmVyZW5jZVNvbHV0aW9uVHlwZXMgJiZcbiAgICAgIGFsbG93ZWRDb25mZXJlbmNlU29sdXRpb25UeXBlcz8uWzBdPy5sZW5ndGggPiAwXG4gICAgKSB7XG4gICAgICBkYXRhID0ge1xuICAgICAgICAuLi5kYXRhLFxuICAgICAgICBjb25mZXJlbmNlUHJvcGVydGllczoge1xuICAgICAgICAgIGFsbG93ZWRDb25mZXJlbmNlU29sdXRpb25UeXBlcyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGF4aW9zLnBhdGNoPGNhbGVuZGFyUmVzcG9uc2U+KHVybCwgZGF0YSwgY29uZmlnKTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgcmVzdWx0cyBhZnRlciBwYXRjaGluZyBjYWxlbmRhcicpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcGF0Y2ggZ29vZ2xlIGNhbGVuZGFyJyk7XG4gIH1cbn07XG5cbi8vIGNyZWF0ZSBjYWxlbmRhclxuZXhwb3J0IGNvbnN0IGNyZWF0ZUdvb2dsZUNhbGVuZGFyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZyxcbiAgaWQ6IHN0cmluZyxcbiAgc3VtbWFyeTogc3RyaW5nLFxuICBkZWZhdWx0UmVtaW5kZXJzPzogRGVmYXVsdFJlbWluZGVyVHlwZVtdLFxuICBub3RpZmljYXRpb25zPzogTm90aWZpY2F0aW9uVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBnZXQgdG9rZW4gPVxuICAgIGNvbnN0IHRva2VuID0gYXdhaXQgZ2V0R29vZ2xlVG9rZW4oY2xpZW50LCB1c2VySWQpO1xuICAgIGxldCB1cmwgPSBnb29nbGVDYWxlbmRhclVSTDtcblxuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIEFjY2VwdDogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgbGV0IGRhdGE6IGFueSA9IHsgaWQsIHN1bW1hcnlPdmVycmlkZTogc3VtbWFyeSwgc2VsZWN0ZWQ6IHRydWUgfTtcblxuICAgIGlmIChkZWZhdWx0UmVtaW5kZXJzICYmIGRlZmF1bHRSZW1pbmRlcnM/LlswXT8ubWV0aG9kPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBkZWZhdWx0UmVtaW5kZXJzIH07XG4gICAgfVxuXG4gICAgaWYgKG5vdGlmaWNhdGlvbnMgJiYgbm90aWZpY2F0aW9ucz8uWzBdPy5tZXRob2Q/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGRhdGEgPSB7XG4gICAgICAgIC4uLmRhdGEsXG4gICAgICAgIG5vdGlmaWNhdGlvblNldHRpbmdzOiB7XG4gICAgICAgICAgbm90aWZpY2F0aW9ucyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgYXhpb3MucG9zdCh1cmwsIGRhdGEsIGNvbmZpZyk7XG4gICAgY29uc29sZS5sb2cocmVzdWx0LCAnIHN1Y2Nlc3NmdWxseSBjcmVhdGVkIHNlY29uZGFyeSBnb29nbGUgY2FsZW5kYXInKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSBnb29nbGUgY2FsZW5kYXInKTtcbiAgfVxufTtcblxuLy8gZ2V0IGNhbGVuZGFyIGluZm9cbmV4cG9ydCBjb25zdCBnZXRHb29nbGVDYWxlbmRhciA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHRva2VuID1cbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZVRva2VuKGNsaWVudCwgdXNlcklkKTtcbiAgICBsZXQgdXJsID0gYCR7Z29vZ2xlQ2FsZW5kYXJVUkx9LyR7ZW5jb2RlVVJJKGNhbGVuZGFySWQpfWA7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBBY2NlcHQ6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBheGlvcy5nZXQodXJsLCBjb25maWcpO1xuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgcmVzdWx0cyBmb3IgZ2V0IGNhbGVuZGFyJyk7XG4gICAgcmV0dXJuIHJlc3VsdHM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgY2FsZW5kYXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUdvb2dsZUV2ZW50ID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY2FsZW5kYXJJZDogc3RyaW5nLFxuICBnb29nbGVFdmVudElkOiBzdHJpbmcsXG4gIHNlbmRVcGRhdGVzOiBTZW5kVXBkYXRlc1R5cGUgPSAnYWxsJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHRva2VuID1cbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZVRva2VuKGNsaWVudCwgdXNlcklkKTtcbiAgICBsZXQgdXJsID0gYCR7Z29vZ2xlVVJMfS8ke2VuY29kZVVSSShjYWxlbmRhcklkKX0vZXZlbnRzLyR7ZW5jb2RlVVJJKGdvb2dsZUV2ZW50SWQpfWA7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBBY2NlcHQ6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgICAvLyBwYXRoIHBhcmFtc1xuICAgIGlmIChzZW5kVXBkYXRlcykge1xuICAgICAgdXJsID0gYCR7dXJsfT9gO1xuICAgICAgbGV0IHBhcmFtcyA9IHsgc2VuZFVwZGF0ZXMgfTtcblxuICAgICAgdXJsID0gYCR7dXJsfSR7cXMuc3RyaW5naWZ5KHBhcmFtcyl9YDtcbiAgICB9XG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBheGlvcy5kZWxldGUodXJsLCBjb25maWcpO1xuICAgIGNvbnNvbGUubG9nKHJlc3VsdCwgJyByZXN1bHQgYWZ0ZXIgZGVsZXRlIGV2ZW50Jyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkZWxldGUgZ29vZ2xlIGV2ZW50Jyk7XG4gIH1cbn07XG5cbi8vIGRlbGV0ZSBzZWNvbmRhcnkgY2FsZW5kYXJcbmV4cG9ydCBjb25zdCBkZWxldGVHb29nbGVDYWxlbmRhciA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHRva2VuID1cbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZVRva2VuKGNsaWVudCwgdXNlcklkKTtcbiAgICBsZXQgdXJsID0gYCR7Z29vZ2xlQ2FsZW5kYXJVUkx9LyR7ZW5jb2RlVVJJKGNhbGVuZGFySWQpfWA7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBBY2NlcHQ6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBheGlvcy5kZWxldGUodXJsLCBjb25maWcpO1xuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgc3VjY2Vzc2Z1bGx5IGRlbGV0ZWQgc2Vjb25kYXJ5IGNhbGVuZGFyJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjYXRjaCBnb29nbGUgY2FsZW5kYXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEdvb2dsZUNvbG9ycyA9IGFzeW5jICh0b2tlbjogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgdXJsID0gZ29vZ2xlQ29sb3JVcmw7XG4gICAgY29uc3QgY29uZmlnID0ge1xuICAgICAgaGVhZGVyczoge1xuICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgQWNjZXB0OiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGF4aW9zLmdldDxjb2xvclJlc3BvbnNlVHlwZT4odXJsLCBjb25maWcpO1xuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgZGF0YSBmb3IgZ2V0IGNvbG9ycycpO1xuICAgIHJldHVybiBkYXRhO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGdvb2dsZSBjb2xvcnMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNsZWFyR29vZ2xlQ2FsZW5kYXIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYWxlbmRhcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIC8vIGdldCB0b2tlbiA9XG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRHb29nbGVUb2tlbihjbGllbnQsIHVzZXJJZCk7XG4gICAgbGV0IHVybCA9IGAke2dvb2dsZVVSTH0vJHtlbmNvZGVVUkkoY2FsZW5kYXJJZCl9L2NsZWFyYDtcblxuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIEFjY2VwdDogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGF4aW9zLnBvc3QodXJsLCB1bmRlZmluZWQsIGNvbmZpZyk7XG4gICAgY29uc29sZS5sb2cocmVzdWx0cywgJyByZXN1bHRzIGZyb20gcG9zdCcpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGVsZXRlIGdvb2dsZSBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcGF0Y2hHb29nbGVFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgZXZlbnRJZDogc3RyaW5nLFxuICBlbmREYXRlVGltZT86IHN0cmluZywgLy8gZWl0aGVyIGVuZERhdGVUaW1lIG9yIGVuZERhdGUgLSBhbGwgZGF5IHZzIHNwZWNpZmljIHBlcmlvZFxuICBzdGFydERhdGVUaW1lPzogc3RyaW5nLFxuICBjb25mZXJlbmNlRGF0YVZlcnNpb24/OiAwIHwgMSxcbiAgbWF4QXR0ZW5kZWVzPzogbnVtYmVyLFxuICBzZW5kVXBkYXRlcz86IFNlbmRVcGRhdGVzVHlwZSxcbiAgYW55b25lQ2FuQWRkU2VsZj86IGJvb2xlYW4sXG4gIGF0dGVuZGVlcz86IEdvb2dsZUF0dGVuZGVlVHlwZVtdLFxuICBjb25mZXJlbmNlRGF0YT86IENvbmZlcmVuY2VEYXRhVHlwZSxcbiAgc3VtbWFyeT86IHN0cmluZyxcbiAgZGVzY3JpcHRpb24/OiBzdHJpbmcsXG4gIHRpbWV6b25lPzogc3RyaW5nLCAvLyByZXF1aXJlZCBmb3IgcmVjdXJyZW5jZVxuICBzdGFydERhdGU/OiBzdHJpbmcsXG4gIGVuZERhdGU/OiBzdHJpbmcsXG4gIGV4dGVuZGVkUHJvcGVydGllcz86IGV4dGVuZGVkUHJvcGVydGllcyxcbiAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzPzogYm9vbGVhbixcbiAgZ3Vlc3RzQ2FuTW9kaWZ5PzogYm9vbGVhbixcbiAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM/OiBib29sZWFuLFxuICBvcmlnaW5hbFN0YXJ0RGF0ZVRpbWU/OiBzdHJpbmcsXG4gIG9yaWdpbmFsU3RhcnREYXRlPzogc3RyaW5nLFxuICByZWN1cnJlbmNlPzogc3RyaW5nW10sXG4gIHJlbWluZGVycz86IEdvb2dsZVJlbWluZGVyVHlwZSxcbiAgc291cmNlPzogc291cmNlLFxuICBzdGF0dXM/OiBzdHJpbmcsXG4gIHRyYW5zcGFyZW5jeT86IFRyYW5zcGFyZW5jeVR5cGUsXG4gIHZpc2liaWxpdHk/OiBWaXNpYmlsaXR5VHlwZSxcbiAgaUNhbFVJRD86IHN0cmluZyxcbiAgYXR0ZW5kZWVzT21pdHRlZD86IGJvb2xlYW4sXG4gIGhhbmdvdXRMaW5rPzogc3RyaW5nLFxuICBwcml2YXRlQ29weT86IGJvb2xlYW4sXG4gIGxvY2tlZD86IGJvb2xlYW4sXG4gIGF0dGFjaG1lbnRzPzogYXR0YWNobWVudFtdLFxuICBldmVudFR5cGU/OiBldmVudFR5cGUxLFxuICBsb2NhdGlvbj86IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHRva2VuID1cbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZVRva2VuKGNsaWVudCwgdXNlcklkKTtcbiAgICBsZXQgdXJsID0gYCR7Z29vZ2xlVVJMfS8ke2VuY29kZVVSSShjYWxlbmRhcklkKX0vZXZlbnRzLyR7ZW5jb2RlVVJJKGV2ZW50SWQpfWA7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBBY2NlcHQ6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIC8vIGlmIGFueSBxdWVyeSBwYXJhbWV0ZXJzIGJ1aWxkIHRoZW1cbiAgICBpZiAoXG4gICAgICBtYXhBdHRlbmRlZXMgfHxcbiAgICAgIHNlbmRVcGRhdGVzIHx8XG4gICAgICAodHlwZW9mIGNvbmZlcmVuY2VEYXRhVmVyc2lvbiA9PT0gJ251bWJlcicgJiYgY29uZmVyZW5jZURhdGFWZXJzaW9uID4gLTEpXG4gICAgKSB7XG4gICAgICB1cmwgPSBgJHt1cmx9P2A7XG4gICAgICBsZXQgcGFyYW1zOiBhbnkgPSB7fTtcblxuICAgICAgaWYgKG1heEF0dGVuZGVlcykge1xuICAgICAgICBwYXJhbXMubWF4QXR0ZW5kZWVzID0gbWF4QXR0ZW5kZWVzO1xuICAgICAgfVxuXG4gICAgICBpZiAoc2VuZFVwZGF0ZXMpIHtcbiAgICAgICAgcGFyYW1zLnNlbmRVcGRhdGVzID0gc2VuZFVwZGF0ZXM7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgdHlwZW9mIGNvbmZlcmVuY2VEYXRhVmVyc2lvbiA9PT0gJ251bWJlcicgJiZcbiAgICAgICAgY29uZmVyZW5jZURhdGFWZXJzaW9uID4gLTFcbiAgICAgICkge1xuICAgICAgICBwYXJhbXMuY29uZmVyZW5jZURhdGFWZXJzaW9uID0gY29uZmVyZW5jZURhdGFWZXJzaW9uO1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIHBhcmFtcz8ubWF4QXR0ZW5kZWVzIHx8XG4gICAgICAgIHBhcmFtcz8uc2VuZFVwZGF0ZXMgfHxcbiAgICAgICAgcGFyYW1zPy5jb25mZXJlbmNlRGF0YVZlcnNpb24gPiAtMVxuICAgICAgKSB7XG4gICAgICAgIHVybCA9IGAke3VybH0ke3FzLnN0cmluZ2lmeShwYXJhbXMpfWA7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gY3JlYXRlIHJlcXVlc3QgYm9keVxuICAgIGxldCBkYXRhOiBhbnkgPSB7fTtcblxuICAgIGlmIChlbmREYXRlICYmIHRpbWV6b25lICYmICFlbmREYXRlVGltZSkge1xuICAgICAgY29uc3QgZW5kID0ge1xuICAgICAgICBkYXRlOiBkYXlqcyhlbmREYXRlKS5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcbiAgICAgIGRhdGEuZW5kID0gZW5kO1xuICAgIH1cblxuICAgIGlmIChlbmREYXRlVGltZSAmJiB0aW1lem9uZSAmJiAhZW5kRGF0ZSkge1xuICAgICAgY29uc3QgZW5kID0ge1xuICAgICAgICBkYXRlVGltZTogZGF5anMoZW5kRGF0ZVRpbWUpLmZvcm1hdCgpLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgZGF0YS5lbmQgPSBlbmQ7XG4gICAgfVxuXG4gICAgaWYgKHN0YXJ0RGF0ZSAmJiB0aW1lem9uZSAmJiAhc3RhcnREYXRlVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgIGRhdGU6IGRheWpzKHN0YXJ0RGF0ZSkuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG4gICAgICBkYXRhLnN0YXJ0ID0gc3RhcnQ7XG4gICAgfVxuXG4gICAgaWYgKHN0YXJ0RGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIXN0YXJ0RGF0ZSkge1xuICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBkYXlqcyhzdGFydERhdGVUaW1lKS5mb3JtYXQoKSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcbiAgICAgIGRhdGEuc3RhcnQgPSBzdGFydDtcbiAgICB9XG5cbiAgICBpZiAob3JpZ2luYWxTdGFydERhdGUgJiYgdGltZXpvbmUgJiYgIW9yaWdpbmFsU3RhcnREYXRlVGltZSkge1xuICAgICAgY29uc3Qgb3JpZ2luYWxTdGFydFRpbWUgPSB7XG4gICAgICAgIGRhdGU6IGRheWpzKG9yaWdpbmFsU3RhcnREYXRlKS5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcbiAgICAgIGRhdGEub3JpZ2luYWxTdGFydFRpbWUgPSBvcmlnaW5hbFN0YXJ0VGltZTtcbiAgICB9XG5cbiAgICBpZiAob3JpZ2luYWxTdGFydERhdGVUaW1lICYmIHRpbWV6b25lICYmICFvcmlnaW5hbFN0YXJ0RGF0ZSkge1xuICAgICAgY29uc3Qgb3JpZ2luYWxTdGFydFRpbWUgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBkYXlqcyhvcmlnaW5hbFN0YXJ0RGF0ZVRpbWUpLmZvcm1hdCgpLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgZGF0YS5vcmlnaW5hbFN0YXJ0VGltZSA9IG9yaWdpbmFsU3RhcnRUaW1lO1xuICAgIH1cblxuICAgIGlmIChhbnlvbmVDYW5BZGRTZWxmKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBhbnlvbmVDYW5BZGRTZWxmIH07XG4gICAgfVxuXG4gICAgaWYgKGF0dGVuZGVlcz8uWzBdPy5lbWFpbCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgYXR0ZW5kZWVzIH07XG4gICAgfVxuXG4gICAgaWYgKGNvbmZlcmVuY2VEYXRhPy5jcmVhdGVSZXF1ZXN0KSB7XG4gICAgICBkYXRhID0ge1xuICAgICAgICAuLi5kYXRhLFxuICAgICAgICBjb25mZXJlbmNlRGF0YToge1xuICAgICAgICAgIGNyZWF0ZVJlcXVlc3Q6IHtcbiAgICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbktleToge1xuICAgICAgICAgICAgICB0eXBlOiBjb25mZXJlbmNlRGF0YS50eXBlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIHJlcXVlc3RJZDogY29uZmVyZW5jZURhdGE/LnJlcXVlc3RJZCB8fCB1dWlkKCksXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfSBlbHNlIGlmIChjb25mZXJlbmNlRGF0YT8uZW50cnlQb2ludHM/LlswXSkge1xuICAgICAgZGF0YSA9IHtcbiAgICAgICAgLi4uZGF0YSxcbiAgICAgICAgY29uZmVyZW5jZURhdGE6IHtcbiAgICAgICAgICBjb25mZXJlbmNlU29sdXRpb246IHtcbiAgICAgICAgICAgIGljb25Vcmk6IGNvbmZlcmVuY2VEYXRhPy5pY29uVXJpLFxuICAgICAgICAgICAga2V5OiB7XG4gICAgICAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2VEYXRhPy50eXBlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIG5hbWU6IGNvbmZlcmVuY2VEYXRhPy5uYW1lLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgZW50cnlQb2ludHM6IGNvbmZlcmVuY2VEYXRhPy5lbnRyeVBvaW50cyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGRlc2NyaXB0aW9uICYmIGRlc2NyaXB0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBkZXNjcmlwdGlvbiB9O1xuICAgIH1cblxuICAgIGlmIChleHRlbmRlZFByb3BlcnRpZXM/LnByaXZhdGUgfHwgZXh0ZW5kZWRQcm9wZXJ0aWVzPy5zaGFyZWQpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGV4dGVuZGVkUHJvcGVydGllcyB9O1xuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5JbnZpdGVPdGhlcnMpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGd1ZXN0c0Nhbkludml0ZU90aGVycyB9O1xuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5Nb2RpZnkpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGd1ZXN0c0Nhbk1vZGlmeSB9O1xuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5TZWVPdGhlckd1ZXN0cykge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMgfTtcbiAgICB9XG5cbiAgICBpZiAobG9ja2VkKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBsb2NrZWQgfTtcbiAgICB9XG5cbiAgICBpZiAocHJpdmF0ZUNvcHkpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHByaXZhdGVDb3B5IH07XG4gICAgfVxuXG4gICAgaWYgKHJlY3VycmVuY2U/LlswXSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgcmVjdXJyZW5jZSB9O1xuICAgIH1cblxuICAgIGlmIChyZW1pbmRlcnMpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHJlbWluZGVycyB9O1xuICAgIH1cblxuICAgIGlmIChzb3VyY2U/LnRpdGxlIHx8IHNvdXJjZT8udXJsKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBzb3VyY2UgfTtcbiAgICB9XG5cbiAgICBpZiAoYXR0YWNobWVudHM/LlswXT8uZmlsZUlkKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBhdHRhY2htZW50cyB9O1xuICAgIH1cblxuICAgIGlmIChldmVudFR5cGUgJiYgZXZlbnRUeXBlPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBldmVudFR5cGUgfTtcbiAgICB9XG5cbiAgICBpZiAoc3RhdHVzKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBzdGF0dXMgfTtcbiAgICB9XG5cbiAgICBpZiAodHJhbnNwYXJlbmN5KSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCB0cmFuc3BhcmVuY3kgfTtcbiAgICB9XG5cbiAgICBpZiAodmlzaWJpbGl0eSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgdmlzaWJpbGl0eSB9O1xuICAgIH1cblxuICAgIGlmIChpQ2FsVUlEICYmIGlDYWxVSUQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGlDYWxVSUQgfTtcbiAgICB9XG5cbiAgICBpZiAoYXR0ZW5kZWVzT21pdHRlZCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgYXR0ZW5kZWVzT21pdHRlZCB9O1xuICAgIH1cblxuICAgIGlmIChoYW5nb3V0TGluayAmJiBoYW5nb3V0TGluaz8ubGVuZ3RoID4gMCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgaGFuZ291dExpbmsgfTtcbiAgICB9XG5cbiAgICBpZiAoc3VtbWFyeSAmJiBzdW1tYXJ5Py5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBzdW1tYXJ5IH07XG4gICAgfVxuXG4gICAgaWYgKGxvY2F0aW9uICYmIGxvY2F0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBsb2NhdGlvbiB9O1xuICAgIH1cbiAgICBjb25zb2xlLmxvZyh1cmwsIGRhdGEsICcgdXJsLCBkYXRhIGluc2lkZSBnb29nbGUgcGF0Y2gnKTtcbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgYXhpb3MucGF0Y2godXJsLCBkYXRhLCBjb25maWcpO1xuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgcmVzdWx0cyBmcm9tIHBhdGNoIGdvb2dsZSBldmVudCcpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcGF0Y2ggZ29vZ2xlIGV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVHb29nbGVFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgZW5kRGF0ZVRpbWU/OiBzdHJpbmcsIC8vIGVpdGhlciBlbmREYXRlVGltZSBvciBlbmREYXRlIC0gYWxsIGRheSB2cyBzcGVjaWZpYyBwZXJpb2RcbiAgc3RhcnREYXRlVGltZT86IHN0cmluZyxcbiAgY29uZmVyZW5jZURhdGFWZXJzaW9uPzogMCB8IDEsXG4gIG1heEF0dGVuZGVlcz86IG51bWJlcixcbiAgc2VuZFVwZGF0ZXM/OiBTZW5kVXBkYXRlc1R5cGUsXG4gIGFueW9uZUNhbkFkZFNlbGY/OiBib29sZWFuLFxuICBhdHRlbmRlZXM/OiBHb29nbGVBdHRlbmRlZVR5cGVbXSxcbiAgY29uZmVyZW5jZURhdGE/OiBDb25mZXJlbmNlRGF0YVR5cGUsXG4gIHN1bW1hcnk/OiBzdHJpbmcsXG4gIGRlc2NyaXB0aW9uPzogc3RyaW5nLFxuICB0aW1lem9uZT86IHN0cmluZywgLy8gcmVxdWlyZWQgZm9yIHJlY3VycmVuY2VcbiAgc3RhcnREYXRlPzogc3RyaW5nLFxuICBlbmREYXRlPzogc3RyaW5nLFxuICBleHRlbmRlZFByb3BlcnRpZXM/OiBleHRlbmRlZFByb3BlcnRpZXMsXG4gIGd1ZXN0c0Nhbkludml0ZU90aGVycz86IGJvb2xlYW4sXG4gIGd1ZXN0c0Nhbk1vZGlmeT86IGJvb2xlYW4sXG4gIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzPzogYm9vbGVhbixcbiAgb3JpZ2luYWxTdGFydERhdGVUaW1lPzogc3RyaW5nLFxuICBvcmlnaW5hbFN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgcmVjdXJyZW5jZT86IHN0cmluZ1tdLFxuICByZW1pbmRlcnM/OiBHb29nbGVSZW1pbmRlclR5cGUsXG4gIHNvdXJjZT86IHNvdXJjZSxcbiAgc3RhdHVzPzogc3RyaW5nLFxuICB0cmFuc3BhcmVuY3k/OiBUcmFuc3BhcmVuY3lUeXBlLFxuICB2aXNpYmlsaXR5PzogVmlzaWJpbGl0eVR5cGUsXG4gIGlDYWxVSUQ/OiBzdHJpbmcsXG4gIGF0dGVuZGVlc09taXR0ZWQ/OiBib29sZWFuLFxuICBoYW5nb3V0TGluaz86IHN0cmluZyxcbiAgcHJpdmF0ZUNvcHk/OiBib29sZWFuLFxuICBsb2NrZWQ/OiBib29sZWFuLFxuICBhdHRhY2htZW50cz86IGF0dGFjaG1lbnRbXSxcbiAgZXZlbnRUeXBlPzogZXZlbnRUeXBlMSxcbiAgbG9jYXRpb24/OiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIC8vIGdldCB0b2tlbiA9XG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRHb29nbGVUb2tlbihjbGllbnQsIHVzZXJJZCk7XG4gICAgbGV0IHVybCA9IGAke2dvb2dsZVVSTH0vJHtlbmNvZGVVUkkoY2FsZW5kYXJJZCl9L2V2ZW50c2A7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBBY2NlcHQ6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIC8vIGlmIGFueSBxdWVyeSBwYXJhbWV0ZXJzIGJ1aWxkIHRoZW1cbiAgICAvLyBmaXJzdFxuICAgIGlmIChcbiAgICAgIG1heEF0dGVuZGVlcyB8fFxuICAgICAgc2VuZFVwZGF0ZXMgfHxcbiAgICAgICh0eXBlb2YgY29uZmVyZW5jZURhdGFWZXJzaW9uID09PSAnbnVtYmVyJyAmJiBjb25mZXJlbmNlRGF0YVZlcnNpb24gPiAwKVxuICAgICkge1xuICAgICAgdXJsID0gYCR7dXJsfT9gO1xuICAgICAgbGV0IHBhcmFtczogYW55ID0ge307XG5cbiAgICAgIGlmIChtYXhBdHRlbmRlZXMpIHtcbiAgICAgICAgcGFyYW1zID0geyAuLi5wYXJhbXMsIG1heEF0dGVuZGVlcyB9O1xuICAgICAgfVxuXG4gICAgICBpZiAoc2VuZFVwZGF0ZXMpIHtcbiAgICAgICAgcGFyYW1zID0geyAuLi5wYXJhbXMsIHNlbmRVcGRhdGVzIH07XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgdHlwZW9mIGNvbmZlcmVuY2VEYXRhVmVyc2lvbiA9PT0gJ251bWJlcicgJiZcbiAgICAgICAgY29uZmVyZW5jZURhdGFWZXJzaW9uID4gLTFcbiAgICAgICkge1xuICAgICAgICBwYXJhbXMgPSB7IC4uLnBhcmFtcywgY29uZmVyZW5jZURhdGFWZXJzaW9uIH07XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgcGFyYW1zPy5tYXhBdHRlbmRlZXMgfHxcbiAgICAgICAgcGFyYW1zPy5zZW5kVXBkYXRlcyB8fFxuICAgICAgICBwYXJhbXM/LmNvbmZlcmVuY2VEYXRhVmVyc2lvbiA+IC0xXG4gICAgICApIHtcbiAgICAgICAgdXJsID0gYCR7dXJsfSR7cXMuc3RyaW5naWZ5KHBhcmFtcyl9YDtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBjcmVhdGUgcmVxdWVzdCBib2R5XG4gICAgbGV0IGRhdGE6IGFueSA9IHt9O1xuXG4gICAgaWYgKGVuZERhdGVUaW1lICYmIHRpbWV6b25lICYmICFlbmREYXRlKSB7XG4gICAgICBjb25zdCBlbmQgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBkYXlqcyhlbmREYXRlVGltZSkuZm9ybWF0KCksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG5cbiAgICAgIGRhdGEuZW5kID0gZW5kO1xuICAgIH1cblxuICAgIGlmIChlbmREYXRlICYmIHRpbWV6b25lICYmICFlbmREYXRlVGltZSkge1xuICAgICAgY29uc3QgZW5kID0ge1xuICAgICAgICBkYXRlOiBkYXlqcyhlbmREYXRlKS5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcblxuICAgICAgZGF0YS5lbmQgPSBlbmQ7XG4gICAgfVxuXG4gICAgaWYgKHN0YXJ0RGF0ZSAmJiB0aW1lem9uZSAmJiAhc3RhcnREYXRlVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgIGRhdGU6IGRheWpzKHN0YXJ0RGF0ZSkuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG4gICAgICBkYXRhLnN0YXJ0ID0gc3RhcnQ7XG4gICAgfVxuXG4gICAgaWYgKHN0YXJ0RGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIXN0YXJ0RGF0ZSkge1xuICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBkYXlqcyhzdGFydERhdGVUaW1lKS5mb3JtYXQoKSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcbiAgICAgIGRhdGEuc3RhcnQgPSBzdGFydDtcbiAgICB9XG5cbiAgICBpZiAob3JpZ2luYWxTdGFydERhdGUgJiYgdGltZXpvbmUgJiYgIW9yaWdpbmFsU3RhcnREYXRlVGltZSkge1xuICAgICAgY29uc3Qgb3JpZ2luYWxTdGFydFRpbWUgPSB7XG4gICAgICAgIGRhdGU6IGRheWpzKG9yaWdpbmFsU3RhcnREYXRlKS5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcbiAgICAgIGRhdGEub3JpZ2luYWxTdGFydFRpbWUgPSBvcmlnaW5hbFN0YXJ0VGltZTtcbiAgICB9XG5cbiAgICBpZiAob3JpZ2luYWxTdGFydERhdGVUaW1lICYmIHRpbWV6b25lICYmICFvcmlnaW5hbFN0YXJ0RGF0ZSkge1xuICAgICAgY29uc3Qgb3JpZ2luYWxTdGFydFRpbWUgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBkYXlqcyhvcmlnaW5hbFN0YXJ0RGF0ZVRpbWUpLmZvcm1hdCgpLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgZGF0YS5vcmlnaW5hbFN0YXJ0VGltZSA9IG9yaWdpbmFsU3RhcnRUaW1lO1xuICAgIH1cblxuICAgIGlmIChhbnlvbmVDYW5BZGRTZWxmKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBhbnlvbmVDYW5BZGRTZWxmIH07XG4gICAgfVxuXG4gICAgaWYgKGF0dGVuZGVlcz8uWzBdPy5lbWFpbCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgYXR0ZW5kZWVzIH07XG4gICAgfVxuXG4gICAgaWYgKGNvbmZlcmVuY2VEYXRhPy5jcmVhdGVSZXF1ZXN0KSB7XG4gICAgICBkYXRhID0ge1xuICAgICAgICAuLi5kYXRhLFxuICAgICAgICBjb25mZXJlbmNlRGF0YToge1xuICAgICAgICAgIGNyZWF0ZVJlcXVlc3Q6IHtcbiAgICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbktleToge1xuICAgICAgICAgICAgICB0eXBlOiBjb25mZXJlbmNlRGF0YS50eXBlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIHJlcXVlc3RJZDogY29uZmVyZW5jZURhdGE/LnJlcXVlc3RJZCB8fCB1dWlkKCksXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfSBlbHNlIGlmIChjb25mZXJlbmNlRGF0YT8uZW50cnlQb2ludHM/LlswXSkge1xuICAgICAgZGF0YSA9IHtcbiAgICAgICAgLi4uZGF0YSxcbiAgICAgICAgY29uZmVyZW5jZURhdGE6IHtcbiAgICAgICAgICBjb25mZXJlbmNlU29sdXRpb246IHtcbiAgICAgICAgICAgIGljb25Vcmk6IGNvbmZlcmVuY2VEYXRhPy5pY29uVXJpLFxuICAgICAgICAgICAga2V5OiB7XG4gICAgICAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2VEYXRhPy50eXBlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIG5hbWU6IGNvbmZlcmVuY2VEYXRhPy5uYW1lLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgZW50cnlQb2ludHM6IGNvbmZlcmVuY2VEYXRhPy5lbnRyeVBvaW50cyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGRlc2NyaXB0aW9uICYmIGRlc2NyaXB0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBkZXNjcmlwdGlvbiB9O1xuICAgIH1cblxuICAgIGlmIChleHRlbmRlZFByb3BlcnRpZXM/LnByaXZhdGUgfHwgZXh0ZW5kZWRQcm9wZXJ0aWVzPy5zaGFyZWQpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGV4dGVuZGVkUHJvcGVydGllcyB9O1xuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5JbnZpdGVPdGhlcnMpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGd1ZXN0c0Nhbkludml0ZU90aGVycyB9O1xuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5Nb2RpZnkpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGd1ZXN0c0Nhbk1vZGlmeSB9O1xuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5TZWVPdGhlckd1ZXN0cykge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMgfTtcbiAgICB9XG5cbiAgICBpZiAobG9ja2VkKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBsb2NrZWQgfTtcbiAgICB9XG5cbiAgICBpZiAocHJpdmF0ZUNvcHkpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHByaXZhdGVDb3B5IH07XG4gICAgfVxuXG4gICAgaWYgKHJlY3VycmVuY2U/LlswXSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgcmVjdXJyZW5jZSB9O1xuICAgIH1cblxuICAgIGlmIChyZW1pbmRlcnMpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHJlbWluZGVycyB9O1xuICAgIH1cblxuICAgIGlmIChzb3VyY2U/LnRpdGxlIHx8IHNvdXJjZT8udXJsKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBzb3VyY2UgfTtcbiAgICB9XG5cbiAgICBpZiAoYXR0YWNobWVudHM/LlswXT8uZmlsZUlkKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBhdHRhY2htZW50cyB9O1xuICAgIH1cblxuICAgIGlmIChldmVudFR5cGUgJiYgZXZlbnRUeXBlPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBldmVudFR5cGUgfTtcbiAgICB9XG5cbiAgICBpZiAoc3RhdHVzKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBzdGF0dXMgfTtcbiAgICB9XG5cbiAgICBpZiAodHJhbnNwYXJlbmN5KSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCB0cmFuc3BhcmVuY3kgfTtcbiAgICB9XG5cbiAgICBpZiAodmlzaWJpbGl0eSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgdmlzaWJpbGl0eSB9O1xuICAgIH1cblxuICAgIGlmIChpQ2FsVUlEICYmIGlDYWxVSUQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGlDYWxVSUQgfTtcbiAgICB9XG5cbiAgICBpZiAoYXR0ZW5kZWVzT21pdHRlZCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgYXR0ZW5kZWVzT21pdHRlZCB9O1xuICAgIH1cblxuICAgIGlmIChoYW5nb3V0TGluayAmJiBoYW5nb3V0TGluaz8ubGVuZ3RoID4gMCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgaGFuZ291dExpbmsgfTtcbiAgICB9XG5cbiAgICBpZiAoc3VtbWFyeSAmJiBzdW1tYXJ5Py5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBzdW1tYXJ5IH07XG4gICAgfVxuXG4gICAgaWYgKGxvY2F0aW9uICYmIGxvY2F0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBsb2NhdGlvbiB9O1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBheGlvcy5wb3N0PGV2ZW50UmVzcG9uc2U+KHVybCwgZGF0YSwgY29uZmlnKTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgcmVzdWx0cyBmcm9tIGdvb2dsZUNyZWF0ZUV2ZW50Jyk7XG4gICAgcmV0dXJuIHJlc3VsdHM/LmRhdGE/LmlkO1xuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGNyZWF0ZUdvb2dsZUV2ZW50Jyk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlPy5yZXNwb25zZT8uZGF0YT8uZXJyb3I/Lm1lc3NhZ2UsXG4gICAgICAnIGVycm9yIGZyb20gZ29vZ2xlQ3JlYXRlRXZlbnQnXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhlPy50b0pTT04oKSwgJyBlcnJvciBmcm9tIGdvb2dsZUNyZWF0ZUV2ZW50Jyk7XG4gIH1cbn07XG4iXX0=