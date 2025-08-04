import got from 'got';
// Mock OpenAI for local testing
let OpenAI;
try {
    const openaiModule = require('openai');
    OpenAI = openaiModule.OpenAI;
}
catch {
    // Use mock if OpenAI not available
    OpenAI = class MockOpenAI {
        constructor(config) { }
        chat = {
            completions: {
                create: async (params) => ({
                    choices: [
                        {
                            message: {
                                content: 'Mock response',
                            },
                        },
                    ],
                }),
            },
        };
    };
}
import { bucketName, eventVectorName, googleCalendarResource, googleCalendarStopWatchUrl, googleClientIdAndroid, googleClientIdAtomicWeb, googleClientIdIos, googleClientIdWeb, googleClientSecretAtomicWeb, googleClientSecretWeb, googleColorUrl, googleMeetResource, googleTokenUrl, hasuraAdminSecret, hasuraGraphUrl, kafkaGoogleCalendarSyncGroupId, kafkaGoogleCalendarSyncTopic, searchIndex, selfGoogleCalendarWebhookPublicUrl, vectorDimensions, zoomBaseTokenUrl, zoomBaseUrl, zoomClientId, zoomClientSecret, zoomIVForPass, zoomPassKey, zoomResourceName, zoomSaltForPass, } from './constants';
import _ from 'lodash';
import { v4 as uuid } from 'uuid';
// Mock date-fns for local testing
let getISODay;
try {
    const dateFns = require('date-fns');
    getISODay = dateFns.getISODay;
}
catch {
    getISODay = (date) => {
        const day = date.getDay();
        return day === 0 ? 7 : day;
    };
}
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import duration from 'dayjs/plugin/duration';
// import isoWeek from 'dayjs/plugin/isoWeek'
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
// Mock googleapis for local testing
let google;
try {
    const googleapis = require('googleapis');
    google = googleapis.google;
}
catch {
    google = {
        auth: {
            OAuth2: class MockOAuth2 {
                credentials = {};
                constructor(...args) { }
                setCredentials(tokens) {
                    this.credentials = tokens;
                }
                getAccessToken() {
                    return Promise.resolve({ token: 'mock-token' });
                }
            },
        },
        calendar: (options) => ({
            events: {
                list: async () => ({ data: { items: [] } }),
                insert: async () => ({ data: {} }),
                update: async () => ({ data: {} }),
                delete: async () => ({}),
            },
        }),
    };
}
// Mock OpenSearch for local testing
let Client;
try {
    const opensearch = require('@opensearch-project/opensearch');
    Client = opensearch.Client;
}
catch {
    Client = class MockClient {
        constructor(config) { }
        search = async () => ({ body: { hits: { hits: [] } } });
        index = async () => ({ body: {} });
    };
}
// Mock google-calendar-sync-admin
let initialGoogleCalendarSync2;
try {
    const gcalAdmin = require('@google_calendar_sync/googleCalendarSync/google-calendar-sync-admin');
    initialGoogleCalendarSync2 = gcalAdmin.initialGoogleCalendarSync2;
}
catch {
    initialGoogleCalendarSync2 = async () => ({ success: true });
}
import axios from 'axios';
import qs from 'qs';
import crypto from 'crypto';
// Mock AWS S3 for local testing
let S3Client, PutObjectCommand;
try {
    const s3 = require('@aws-sdk/client-s3');
    S3Client = s3.S3Client;
    PutObjectCommand = s3.PutObjectCommand;
}
catch {
    S3Client = class MockS3Client {
        constructor(config) { }
        send = async () => ({ ETag: '"mock-etag"' });
    };
    PutObjectCommand = class MockPutObjectCommand {
        constructor(params) { }
    };
}
// Mock Kafka for local testing
let Kafka, logLevel;
try {
    const kafkajs = require('kafkajs');
    Kafka = kafkajs.Kafka;
    logLevel = kafkajs.logLevel;
}
catch {
    Kafka = class MockKafka {
        constructor(config) { }
        producer() {
            return {
                connect: async () => { },
                send: async () => { },
                disconnect: async () => { },
            };
        }
    };
    logLevel = { INFO: 1 };
}
// Mock ip module for local testing
let ip;
try {
    ip = require('ip');
}
catch {
    ip = {
        address: () => '127.0.0.1',
    };
}
dayjs.extend(utc);
dayjs.extend(duration);
// dayjs.extend(isoWeek)
dayjs.extend(isBetween);
dayjs.extend(timezone);
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
});
const s3Client = new S3Client({
    credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY,
        secretAccessKey: process.env.S3_SECRET_KEY,
    },
    endpoint: process.env.S3_ENDPOINT,
    forcePathStyle: true,
});
const kafka = new Kafka({
    logLevel: logLevel.DEBUG,
    brokers: [`kafka1:29092`],
    clientId: 'atomic',
    // ssl: true,
    sasl: {
        mechanism: 'plain', // scram-sha-256 or scram-sha-512
        username: process.env.KAFKA_USERNAME,
        password: process.env.KAFKA_PASSWORD,
    },
});
export const insertEventTriggers = async (objects) => {
    try {
        const operationName = 'insertEventTriggers';
        const query = `
      mutation insertEventTriggers($objects: [Event_Trigger_insert_input!]!) {
        insert_Event_Trigger(objects: $objects) {
          affected_rows
        }
      }
    `;
        const variables = {
            objects,
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
        console.log(res, ' affected_rows inside insert event triggers');
    }
    catch (e) {
        console.log(e, ' unable to insert event trigger');
    }
};
export const getEventTriggerByResourceId = async (resourceId) => {
    try {
        if (!resourceId) {
            console.log('no resourceId inside getEventTriggerByResourceId');
            return;
        }
        const operationName = 'GetEventTriggerByResourceId';
        const query = `
    query GetEventTriggerByResourceId($resourceId: String) {
      Event_Trigger(where: {resourceId: {_eq: $resourceId}}) {
        createdAt
        id
        name
        resource
        resourceId
        updatedAt
        userId
      }
    }
    `;
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
                variables: {
                    resourceId,
                },
            },
        })
            .json();
        console.log(response, ' response inside getEventTriggerByResourceId');
        return response?.data?.Event_Trigger?.[0];
    }
    catch (e) {
        console.log(e, ' unable to getEventTriggerByResourceId');
    }
};
export const deleteEventTriggerById = async (id) => {
    try {
        const operationName = 'deleteEventTriggerById';
        const query = `
      mutation deleteEventTriggerById($id: uuid!) {
        delete_Event_Trigger_by_pk(id: $id) {
          id
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
        console.log(res, ' deleteEventTriggerById');
    }
    catch (e) {
        console.log(e, ' deleteEventTriggerById');
    }
};
export const resetGoogleSyncForCalendar = async (calendarId, userId, clientType) => {
    try {
        const operationName = 'updateCalendar';
        const query = `mutation updateCalendar($id: String!, $changes: Calendar_set_input) {
      update_Calendar_by_pk(pk_columns: {id: $id}, _set: $changes) {
        pageToken
        syncToken
      }
    }
    `;
        const variables = {
            id: calendarId,
            changes: {
                pageToken: null,
                syncToken: null,
            },
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
        console.log(response, ' this is response in resetGoogleIntegrationSync');
        // const { token: authToken } = await getGoogleIntegration(calendarIntegrationId)
        return initialGoogleCalendarSync2(calendarId, userId, clientType);
    }
    catch (e) {
        console.log(e, ' unable to reset google integration sync');
    }
};
export const deleteMeetingAssistsGivenIds = async (ids) => {
    try {
        const operationName = 'DeleteMeetingAssistsByIds';
        const query = `
            mutation DeleteMeetingAssistsByIds($ids: [uuid!]!) {
                delete_Meeting_Assist(where: {id: {_in: $ids}}) {
                    affected_rows
                    returning {
                    allowAttendeeUpdatePreferences
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
                    foregroundColor
                    frequency
                    guaranteeAvailability
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    id
                    interval
                    location
                    minThresholdCount
                    notes
                    originalMeetingId
                    priority
                    reminders
                    sendUpdates
                    startDate
                    summary
                    timezone
                    transparency
                    until
                    updatedAt
                    useDefaultAlarms
                    userId
                    visibility
                    windowEndDate
                    windowStartDate
                    }
                }
            }
        `;
        const variables = {
            ids,
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
        console.log(res, ' successfully deleted meetingassists with given ids');
    }
    catch (e) {
        console.log(e, ' unable to delete meeting assists given ids');
    }
};
export const addlocalItemsToEvent2VectorObjects = (localItems, event2VectorObjects, calendarId) => {
    for (const localItem of localItems) {
        const status = 'cancelled';
        if (localItem?.status === status) {
            event2VectorObjects.push({
                method: 'delete',
                event: localItem,
                calendarId,
            });
        }
        else {
            event2VectorObjects.push({
                method: 'upsert',
                event: localItem,
                calendarId,
            });
        }
    }
};
export const incrementalGoogleCalendarSync2 = async (calendarId, userId, clientType, parentSyncToken, parentPageToken, colorItem) => {
    try {
        let pageToken = parentPageToken;
        let syncToken = parentSyncToken;
        let localItems = [];
        const event2VectorObjects = [];
        const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType);
        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        const initialVariables = {
            // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
            calendarId,
            // Whether to include deleted events (with status equals "cancelled") in the result. Cancelled instances of recurring events (but not the underlying recurring event) will still be included if showDeleted and singleEvents are both False. If showDeleted and singleEvents are both True, only single instances of deleted events (but not the underlying recurring events) are returned. Optional. The default is False.
            showDeleted: true,
            // Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves. Optional. The default is False.
            singleEvents: true,
            syncToken,
        };
        if (parentPageToken) {
            initialVariables.pageToken = parentPageToken;
        }
        const res = await googleCalendar.events.list(initialVariables);
        console.log(res.data);
        // {
        //   "accessRole": "my_accessRole",
        //   "defaultReminders": [],
        //   "description": "my_description",
        //   "etag": "my_etag",
        //   "items": [],
        //   "kind": "my_kind",
        //   "nextPageToken": "my_nextPageToken",
        //   "nextSyncToken": "my_nextSyncToken",
        //   "summary": "my_summary",
        //   "timeZone": "my_timeZone",
        //   "updated": "my_updated"
        // }
        const { items, nextPageToken, nextSyncToken } = res.data;
        localItems = items;
        pageToken = nextPageToken;
        syncToken = nextSyncToken;
        addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId);
        await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
        const status = 'cancelled';
        const deletedEvents = localItems.filter((e) => e?.status === status);
        if (deletedEvents?.[0]?.id) {
            const returnedDeletedEventValues = await deleteEvents(deletedEvents, calendarId);
            const meetingIdsToDelete = returnedDeletedEventValues
                ?.filter((e) => !!e?.meetingId)
                ?.map((e) => e?.meetingId);
            if (meetingIdsToDelete && meetingIdsToDelete?.length > 0) {
                await deleteMeetingAssistsGivenIds(meetingIdsToDelete);
            }
            // delete any virtual conferences
            await deleteConferences(returnedDeletedEventValues);
            const promises = [
                deleteAttendees(deletedEvents, calendarId),
                deleteReminders(deletedEvents, userId, calendarId),
            ];
            await Promise.all(promises);
        }
        const eventsToUpsert = localItems?.filter((e) => e?.status !== status);
        // no events to upsert check next pagetoken
        if (!eventsToUpsert?.[0]?.id) {
            console.log('no events to upsert check next pagetoken');
            const variables = {
                // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
                calendarId,
                // Whether to include deleted events (with status equals "cancelled") in the result. Cancelled instances of recurring events (but not the underlying recurring event) will still be included if showDeleted and singleEvents are both False. If showDeleted and singleEvents are both True, only single instances of deleted events (but not the underlying recurring events) are returned. Optional. The default is False.
                showDeleted: true,
                // Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves. Optional. The default is False.
                singleEvents: true,
                syncToken,
            };
            if (pageToken) {
                variables.pageToken = pageToken;
                const res = await googleCalendar.events.list(variables);
                console.log(res.data);
                const { items, nextPageToken, nextSyncToken } = res.data;
                localItems = items;
                pageToken = nextPageToken;
                syncToken = nextSyncToken;
                addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId);
                await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
                const deletedEvents = localItems.filter((e) => e?.status === status);
                if (deletedEvents?.[0]?.id) {
                    const returnedDeletedEventValues = await deleteEvents(deletedEvents, calendarId);
                    const meetingIdsToDelete = returnedDeletedEventValues
                        ?.filter((e) => !!e?.meetingId)
                        ?.map((e) => e?.meetingId);
                    if (meetingIdsToDelete && meetingIdsToDelete?.length > 0) {
                        await deleteMeetingAssistsGivenIds(meetingIdsToDelete);
                    }
                    await deleteConferences(returnedDeletedEventValues);
                    const promises = [
                        deleteAttendees(deletedEvents, calendarId),
                        deleteReminders(deletedEvents, userId, calendarId),
                    ];
                    await Promise.all(promises);
                }
                const eventsToUpsert2 = localItems?.filter((e) => e?.status !== status);
                if (eventsToUpsert2?.[0]?.id) {
                    await upsertConference2(eventsToUpsert2, userId, calendarId);
                    await upsertEvents2(eventsToUpsert2, userId, calendarId, colorItem);
                    const promises = [
                        deleteReminders(eventsToUpsert2, userId, calendarId),
                        insertRemindersGivenEventResource(eventsToUpsert2, userId, calendarId),
                        upsertAttendees2(eventsToUpsert2, userId, calendarId),
                    ];
                    await Promise.all(promises);
                }
            }
        }
        else {
            await upsertConference2(eventsToUpsert, userId, calendarId);
            await upsertEvents2(eventsToUpsert, userId, calendarId, colorItem);
            await deleteReminders(eventsToUpsert, userId, calendarId);
            const promises = [
                insertRemindersGivenEventResource(eventsToUpsert, userId, calendarId),
                upsertAttendees2(eventsToUpsert, userId, calendarId),
            ];
            await Promise.all(promises);
        }
        if (pageToken) {
            // fetch all pages
            while (pageToken) {
                const variables = {
                    // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
                    calendarId,
                    // Token specifying which result page to return. Optional.
                    pageToken,
                    // Whether to include deleted events (with status equals "cancelled") in the result. Cancelled instances of recurring events (but not the underlying recurring event) will still be included if showDeleted and singleEvents are both False. If showDeleted and singleEvents are both True, only single instances of deleted events (but not the underlying recurring events) are returned. Optional. The default is False.
                    showDeleted: true,
                    // Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves. Optional. The default is False.
                    singleEvents: true,
                    syncToken,
                };
                const res = await googleCalendar.events.list(variables);
                console.log(res.data);
                const { items, nextPageToken, nextSyncToken } = res.data;
                localItems = items;
                pageToken = nextPageToken;
                syncToken = nextSyncToken;
                // tokens in case something goes wrong
                // update pageToken and syncToken
                addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId);
                await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
                const deletedEvents = localItems.filter((e) => e?.status === status);
                if (deletedEvents?.[0]?.id) {
                    const returnedDeletedEventValues = await deleteEvents(deletedEvents, calendarId);
                    const meetingIdsToDelete = returnedDeletedEventValues
                        ?.filter((e) => !!e?.meetingId)
                        ?.map((e) => e?.meetingId);
                    if (meetingIdsToDelete && meetingIdsToDelete?.length > 0) {
                        await deleteMeetingAssistsGivenIds(meetingIdsToDelete);
                    }
                    await deleteConferences(returnedDeletedEventValues);
                    const promises = [
                        deleteAttendees(deletedEvents, calendarId),
                        deleteReminders(deletedEvents, userId, calendarId),
                    ];
                    await Promise.all(promises);
                }
                const eventsToUpsert = localItems?.filter((e) => e?.status !== status);
                // no events to upsert check next pagetoken
                if (!eventsToUpsert?.[0]?.id) {
                    console.log('no events to upsert check next pagetoken');
                    const variables = {
                        // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
                        calendarId,
                        // Whether to include deleted events (with status equals "cancelled") in the result. Cancelled instances of recurring events (but not the underlying recurring event) will still be included if showDeleted and singleEvents are both False. If showDeleted and singleEvents are both True, only single instances of deleted events (but not the underlying recurring events) are returned. Optional. The default is False.
                        showDeleted: true,
                        // Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves. Optional. The default is False.
                        singleEvents: true,
                        syncToken,
                    };
                    if (pageToken) {
                        variables.pageToken = pageToken;
                        const res = await googleCalendar.events.list(variables);
                        console.log(res.data);
                        const { items, nextPageToken, nextSyncToken } = res.data;
                        localItems = items;
                        pageToken = nextPageToken;
                        syncToken = nextSyncToken;
                        addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId);
                        await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
                        const deletedEvents = localItems.filter((e) => e?.status === status);
                        if (deletedEvents?.[0]?.id) {
                            const returnedDeletedEventValues = await deleteEvents(deletedEvents, calendarId);
                            const meetingIdsToDelete = returnedDeletedEventValues
                                ?.filter((e) => !!e?.meetingId)
                                ?.map((e) => e?.meetingId);
                            if (meetingIdsToDelete && meetingIdsToDelete?.length > 0) {
                                await deleteMeetingAssistsGivenIds(meetingIdsToDelete);
                            }
                            await deleteConferences(returnedDeletedEventValues);
                            const promises = [
                                deleteAttendees(deletedEvents, calendarId),
                                deleteReminders(deletedEvents, userId, calendarId),
                            ];
                            await Promise.all(promises);
                        }
                        const eventsToUpsert2 = localItems?.filter((e) => e?.status !== status);
                        if (eventsToUpsert2) {
                            await upsertConference2(eventsToUpsert2, userId, calendarId);
                            await upsertEvents2(eventsToUpsert2, userId, calendarId, colorItem);
                            const promises = [
                                deleteReminders(eventsToUpsert2, userId, calendarId),
                                insertRemindersGivenEventResource(eventsToUpsert2, userId, calendarId),
                                upsertAttendees2(eventsToUpsert2, userId, calendarId),
                            ];
                            await Promise.all(promises);
                        }
                    }
                    continue;
                }
                await upsertConference2(eventsToUpsert, userId, calendarId);
                await upsertEvents2(eventsToUpsert, userId, calendarId, colorItem);
                const promises = [
                    deleteReminders(eventsToUpsert, userId, calendarId),
                    insertRemindersGivenEventResource(eventsToUpsert, userId, calendarId),
                    upsertAttendees2(eventsToUpsert, userId, calendarId),
                ];
                await Promise.all(promises);
            }
            await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
        }
        await addToQueueForVectorSearch(userId, event2VectorObjects);
        return true;
    }
    catch (e) {
        console.log(e, ' unable to incremental google sync');
        if (e.code === 410) {
            // reset sync
            await resetGoogleSyncForCalendar(calendarId, userId, clientType);
            return true;
        }
        return false;
    }
};
export const getCalendarWebhookById = async (channelId) => {
    try {
        const operationName = 'GetCalendarPushNotificationById';
        const query = `query GetCalendarPushNotificationById($id: String!) {
      Calendar_Push_Notification_by_pk(id: $id) {
        calendarId
        createdDate
        expiration
        id
        resourceId
        resourceUri
        token
        updatedAt
        userId
        calendarIntegrationId
      }
    }
    `;
        const variables = {
            id: channelId,
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
        console.log(res, ' res from getCalendarWebhook');
        return res?.data?.Calendar_Push_Notification_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to getCalendarWebhook');
    }
};
export const convertTextToVectorSpace2 = async (text) => {
    try {
        if (!text || text.trim() === '') {
            return [];
        }
        const embeddingResponse = await openai.embeddings.create({
            model: 'text-embedding-ada-002',
            input: text.replace(/\n/g, ' '),
        });
        const vector = embeddingResponse.data[0].embedding;
        return vector;
    }
    catch (e) {
        console.log(e, ' unable to convertTextToVectorSpace');
        throw e;
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
export const getSearchClient = async () => {
    try {
        return new Client({
            node: process.env.OPENSEARCH_ENDPOINT,
            auth: {
                username: process.env.OPENSEARCH_USERNAME,
                password: process.env.OPENSEARCH_PASSWORD,
            },
        });
    }
    catch (e) {
        console.log(e, ' unable to get credentials from getSearchClient');
    }
};
export const searchData3 = async (userId, searchVector) => {
    try {
        const client = await getSearchClient();
        const response = await client.search({
            index: searchIndex,
            body: {
                size: vectorDimensions,
                query: {
                    script_score: {
                        query: {
                            bool: {
                                filter: {
                                    term: {
                                        userId,
                                    },
                                },
                            },
                        },
                        script: {
                            lang: 'knn',
                            source: 'knn_score',
                            params: {
                                field: eventVectorName,
                                query_value: searchVector,
                                space_type: 'cosinesimil',
                            },
                        },
                    },
                },
                min_score: 1.2,
            },
        });
        console.log(response, ' search data in search engine');
        return response.body;
    }
    catch (e) {
        console.log(e, ' unable to search data');
    }
};
export const deleteCalendarWebhookById = async (channelId) => {
    try {
        const operationName = 'DeleteCalendarPushNotificationById';
        const query = `
      mutation DeleteCalendarPushNotificationById($id: String!) {
        delete_Calendar_Push_Notification_by_pk(id: $id) {
          calendarId
          createdDate
          expiration
          id
          resourceId
          resourceUri
          token
          updatedAt
          userId
        }
      }
      `;
        const variables = {
            id: channelId,
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
        console.log(res, ' res from  deleteCalendarWebhookById');
    }
    catch (e) {
        console.log(e, ' unable to delete calendar webhook by id');
    }
};
export const stopCalendarWatch = async (id, resourceId) => {
    try {
        const res = await got.post(googleCalendarStopWatchUrl, {
            headers: {
                'Content-Type': 'application/json',
            },
            json: {
                id,
                resourceId,
            },
        });
        console.log(res, ' res inside stopCalendarWatch');
    }
    catch (e) {
        console.log(e, ' unable to stop calendar watch');
    }
};
export const getCalendarWebhookByCalendarId = async (calendarId) => {
    try {
        const operationName = 'GetCalendarPushNotificationByCalendarId';
        const query = `
      query GetCalendarPushNotificationByCalendarId($calendarId: String!) {
        Calendar_Push_Notification(where: {calendarId: {_eq: $calendarId}}, limit: 1) {
          calendarId
          createdDate
          expiration
          id
          resourceId
          resourceUri
          token
          updatedAt
          userId
        }
      }
    `;
        const variables = {
            calendarId,
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
        console.log(res, ' res from getCalendarWebhook');
        return res?.data?.Calendar_Push_Notification?.[0];
    }
    catch (e) {
        console.log(e, ' unable to getCalendarWebhookByCalendarId');
    }
};
export const upsertEvents2 = async (events, userId, calendarId, colorItem) => {
    try {
        console.log(events, ' events inside upsertEvents');
        console.log(colorItem, ' colorItem inside upsertEvents');
        if (!events?.[0]?.id)
            return null;
        // format events for insert
        const formattedEvents = events
            .filter((e) => !!e?.id)
            ?.filter((e) => !!e?.start?.timeZone || !!e?.end?.timeZone)
            .map((event) => {
            return {
                id: `${event?.id}#${calendarId}`,
                userId,
                status: event?.status,
                htmlLink: event?.htmlLink,
                createdDate: event?.created,
                updatedAt: event?.updated,
                summary: event?.summary,
                notes: event?.description,
                location: {
                    title: event?.location,
                },
                colorId: event?.colorId,
                creator: event?.creator,
                organizer: event?.organizer,
                startDate: event?.start?.dateTime ||
                    dayjs(event?.start?.date)
                        .tz(event?.start?.timeZone || dayjs.tz.guess(), true)
                        .format(),
                endDate: event?.end?.dateTime ||
                    dayjs(event?.end?.date)
                        .tz(event?.end?.timeZone || dayjs.tz.guess(), true)
                        .format(),
                allDay: event?.start?.date ? true : false,
                timezone: event?.start?.timeZone || event?.end?.timeZone,
                endTimeUnspecified: event?.endTimeUnspecified,
                recurrence: event?.recurrence,
                recurringEventId: event?.recurringEventId,
                originalStartDate: event?.originalStartTime?.dateTime ||
                    event?.originalStartTime?.date,
                originalAllDay: event?.originalStartTime?.date ? true : false,
                originalTimezone: event?.originalStartTime?.timeZone,
                transparency: event?.transparency,
                visibility: event?.visibility,
                iCalUID: event?.iCalUID,
                attendeesOmitted: event?.attendeesOmitted,
                extendedProperties: event?.extendedProperties?.private ||
                    event?.extendedProperties?.shared
                    ? {
                        private: event?.extendedProperties?.private && {
                            keys: Object.keys(event?.extendedProperties?.private),
                            values: Object.values(event?.extendedProperties?.private),
                        },
                        shared: event?.extendedProperties?.shared && {
                            keys: Object.keys(event?.extendedProperties?.shared),
                            values: Object.values(event?.extendedProperties?.shared),
                        },
                    }
                    : null,
                hangoutLink: event?.hangoutLink,
                anyoneCanAddSelf: event?.anyoneCanAddSelf,
                guestsCanInviteOthers: event?.guestsCanInviteOthers,
                guestsCanModify: event?.guestsCanModify,
                guestsCanSeeOtherGuests: event?.guestsCanSeeOtherGuests,
                source: event?.source,
                attachments: event?.attachments,
                eventType: event?.eventType,
                privateCopy: event?.privateCopy,
                locked: event?.locked,
                calendarId,
                backgroundColor: colorItem?.event?.[`${event?.colorId}`]?.background,
                foregroundColor: colorItem?.event?.[`${event?.colorId}`]?.foreground,
                useDefaultAlarms: event?.reminders?.useDefault,
                eventId: event?.id,
                conferenceId: event?.conferenceData?.conferenceId,
            };
        });
        if (!(formattedEvents?.length > 0)) {
            return;
        }
        /*
              dynamically generate upsert query based on the number of columns
              and set the update_columns to the columns that are not undefined
            */
        const operationName = 'InsertEvent';
        const query = `
      mutation InsertEvent($events: [Event_insert_input!]!) {
        insert_Event(
            objects: $events,
            on_conflict: {
                constraint: Event_pkey,
                update_columns: [
                  startDate,
                  endDate,
                  allDay,
                  recurrence,
                  location,
                  notes,
                  attachments,
                  timezone,
                  attendeesOmitted,
                  anyoneCanAddSelf,
                  guestsCanInviteOthers,
                  guestsCanSeeOtherGuests,
                  originalStartDate,
                  originalTimezone,
                  originalAllDay,
                  status,
                  summary,
                  transparency,
                  visibility,
                  recurringEventId,
                  htmlLink,
                  colorId,
                  creator,
                  organizer,
                  endTimeUnspecified,
                  extendedProperties,
                  hangoutLink,
                  guestsCanModify,
                  locked,
                  source,
                  eventType,
                  privateCopy,
                  backgroundColor,
                  foregroundColor,
                  updatedAt,
                  iCalUID,
                  calendarId,
                  useDefaultAlarms,
                  eventId,
                  conferenceId,
                ]
            }){
            returning {
              id
            }
          }
        }
      `;
        const variables = {
            events: formattedEvents,
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
        console.log(response, ' this is response in upsertEvents');
        response?.errors?.forEach((e) => console.log(e));
    }
    catch (e) {
        console.log(e, ' unable to upsertEvents');
    }
};
export const upsertConference2 = async (events, userId, calendarId) => {
    try {
        const formattedConference = events.map((e) => {
            return {
                id: e?.conferenceData?.conferenceId,
                userId,
                type: e?.conferenceData?.conferenceSolution?.key?.type,
                status: e?.conferenceData?.createRequest?.status?.statusCode,
                calendarId,
                iconUri: e?.conferenceData?.conferenceSolution?.iconUri,
                name: e?.conferenceData?.conferenceSolution?.name,
                notes: e?.conferenceData?.notes,
                entryPoints: e?.conferenceData?.entryPoints,
                key: e?.conferenceData?.conferenceSolution?.key?.type,
                deleted: false,
                app: googleMeetResource,
                updatedAt: dayjs().utc().toISOString(),
                createdDate: dayjs().toISOString(),
                isHost: false,
            };
        });
        if (!(formattedConference?.filter((c) => !!c?.id)?.length > 0)) {
            return;
        }
        /*
            dynamically generate upsert query based on the number of columns
            and set the update_columns to the columns that are not undefined
            */
        const operationName = 'InsertConference';
        const query = `
      mutation InsertConference($conferences: [Conference_insert_input!]!) {
            insert_Conference(
                objects: $conferences,
                on_conflict: {
                    constraint: Conference_pkey,
                    update_columns: [
                      requestId,
                      type,
                      status,
                      calendarId,
                      iconUri,
                      name,
                      notes,
                      entryPoints,
                      parameters,
                      app,
                      key,
                      deleted,
                      updatedAt,
                    ]
                }) {
          returning {
            id
          }
        }
      }
      `;
        const variables = {
            conferences: formattedConference,
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
        console.log(response, ' this is response in upsertConference');
    }
    catch (e) {
        console.log(e, ' unable to upsert conference data');
    }
};
export const insertCalendarWebhook = async (webhook) => {
    try {
        const operationName = 'InsertCalendarPushNotification';
        const query = `mutation InsertCalendarPushNotification($webhook: Calendar_Push_Notification_insert_input!) {
      insert_Calendar_Push_Notification_one(object: $webhook,
        on_conflict: {
          constraint: Calendar_Push_Notification_calendarId_key,
          update_columns: [
            id,
            expiration,
            resourceId,
            resourceUri,
            token,
            updatedAt,
            userId,
            calendarIntegrationId,
          ]}) {
            calendarId
            createdDate
            expiration
            id
            resourceId
            resourceUri
            token
            updatedAt
            userId
            calendarIntegrationId
          }
        }
      `;
        const variables = {
            webhook,
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
        console.log(response, ' response after upserting calendar webhook');
        return response?.data?.insert_Calendar_Push_Notification_one;
    }
    catch (e) {
        console.log(e, ' unable to upsertCalendarWebhook');
    }
};
export const upsertAttendees2 = async (events, userId, calendarId) => {
    try {
        const attendees = [];
        events
            .filter((e) => !!e?.attendees?.[0]?.id)
            .forEach((e) => {
            e?.attendees?.forEach((a) => {
                attendees.push({
                    id: a?.id,
                    userId,
                    name: a?.displayName,
                    emails: [
                        {
                            primary: false,
                            value: a?.email,
                            displayName: a?.displayName,
                            type: '',
                        },
                    ],
                    eventId: `${e?.id}#${calendarId}`,
                    additionalGuests: a?.additionalGuests,
                    comment: a?.comment,
                    responseStatus: a?.responseStatus,
                    optional: a?.optional,
                    resource: a?.resource,
                    deleted: false,
                    updatedAt: dayjs().utc().toISOString(),
                    createdDate: dayjs().toISOString(),
                });
            });
        });
        if (!attendees?.[0]?.emails?.[0]) {
            return;
        }
        const operationName = 'InsertAttendee';
        const query = `
        mutation InsertAttendee($attendees: [Attendee_insert_input!]!) {
            insert_Attendee(
                objects: $attendees,
                on_conflict: {
                    constraint: Attendee_pkey,
                    update_columns: [
                      name,
                      contactId,
                      emails,
                      phoneNumbers,
                      imAddresses,
                      eventId,
                      additionalGuests,
                      optional,
                      resource,
                      responseStatus,
                      comment,
                      deleted,
                      updatedAt,
                    ]
                }){
                returning {
                  id
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
        console.log(response, ' this is response in upsertAttendees');
    }
    catch (e) {
        console.log(e, ' unable to upsertAttendees');
    }
};
export const updateGoogleIntegration = async (calendarIntegrationId, syncEnabled) => {
    try {
        const operationName = 'updateCalendarIntegration';
        const query = `mutation updateCalendarIntegration($id: uuid!, ${syncEnabled !== undefined ? ' $syncEnabled: Boolean,' : ''}) {
        update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {${syncEnabled !== undefined ? ' syncEnabled: $syncEnabled,' : ''} }) {
          id
          name
          refreshToken
          resource
          syncEnabled
          token
          updatedAt
          userId
          expiresAt
          enabled
          deleted
          createdDate
          clientType
        }
      }
    `;
        let variables = {
            id: calendarIntegrationId,
        };
        if (syncEnabled === false) {
            variables = { ...variables, syncEnabled };
        }
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
        console.log(response, ' this is response in updateGoogleIntegration');
    }
    catch (e) {
        console.log(e, ' unable to update google integration');
    }
};
export const updateGoogleCalendarTokensInDb = async (calendarId, syncToken, pageToken) => {
    try {
        const operationName = 'updateCalendar';
        const query = `mutation updateCalendar($id: String!, ${syncToken !== undefined ? ' $syncToken: String,' : ''} ${pageToken !== undefined ? ' $pageToken: String,' : ''}) {
        update_Calendar_by_pk(pk_columns: {id: $id}, _set: {${pageToken !== undefined ? ' pageToken : $pageToken,' : ''} ${syncToken !== undefined ? ' syncToken: $syncToken,' : ''} }) {
          id
          pageToken
          syncToken
          updatedAt
          userId
          deleted
          createdDate
        }
      }
    `;
        let variables = {
            id: calendarId,
        };
        if (syncToken?.length > 0) {
            variables = { ...variables, syncToken };
        }
        if (pageToken?.length > 0) {
            variables = { ...variables, pageToken };
        }
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
        console.log(response, ' this is response in updateGoogleIntegration');
    }
    catch (e) {
        console.log(e, ' unable to update google integration');
    }
};
export const getCalendarWithId = async (calendarId) => {
    try {
        // get Calendar
        const operationName = 'getCalendar';
        const query = `
    query getCalendar($id: String!) {
      Calendar_by_pk(id: $id) {
        resource
        updatedAt
        userId
        account
        colorId
        id
        modifiable
      }
    }
  `;
        const variables = {
            id: calendarId,
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
        console.log(res, ' res from getCalendarForEvent');
        return res?.data?.Calendar_by_pk;
    }
    catch (e) {
        console.log(e, ' getCalendarForEvent');
    }
};
export const requestCalendarWatch = async (calendarId, channelId, token, userId) => {
    try {
        const { resource } = await getCalendarWithId(calendarId);
        const calendarIntegration = await getCalendarIntegration(userId, resource);
        const clientType = calendarIntegration?.clientType;
        const authToken = await getGoogleAPIToken(userId, googleCalendarResource, clientType);
        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${authToken}`,
            },
        });
        const reqBody = {
            id: channelId,
            token,
            type: 'webhook',
            address: selfGoogleCalendarWebhookPublicUrl,
        };
        const res = await googleCalendar.events.watch({
            calendarId,
            singleEvents: true,
            requestBody: reqBody,
        });
        const response = res?.data;
        console.log(response, ' response inside requestCalendarWatch');
        return response;
    }
    catch (e) {
        console.log(e, ' unable to request calendar watch');
    }
};
export const listCalendarsForUser = async (userId) => {
    try {
        const operationName = 'ListCalendarsForUser';
        const query = `
      query ListCalendarsForUser($userId: uuid!) {
        Calendar(where: {userId: {_eq: $userId}}) {
          id
          title
          colorId
          account
          accessLevel
          modifiable
          resource
          defaultReminders
          globalPrimary
          deleted
          createdDate
          updatedAt
          userId
          foregroundColor
          backgroundColor
          pageToken
          syncToken
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
        return res.data.Calendar;
    }
    catch (e) {
        console.log(e, ' list calendars for user');
    }
};
export const insertRemindersGivenEventResource = async (events, userId, calendarId) => {
    try {
        if (!(events?.filter((e) => !!e?.id)?.length > 0)) {
            return;
        }
        const reminders = [];
        events
            .filter((e) => e?.reminders?.useDefault || e?.reminders?.overrides?.[0]?.minutes > -1)
            .forEach((event) => {
            const eventId = event?.id;
            const timezone = event?.start?.timeZone;
            console.log(eventId, calendarId, ' eventId, calendarId inside insertRemindersGivenEventResource');
            if (event?.reminders?.useDefault) {
                reminders.push({
                    eventId: `${eventId}#${calendarId}`,
                    userId,
                    useDefault: event?.reminders?.useDefault,
                    timezone,
                });
            }
            else {
                event?.reminders?.overrides.forEach((o) => {
                    reminders.push({
                        eventId: `${eventId}#${calendarId}`,
                        userId,
                        timezone,
                        method: o?.method,
                        minutes: o?.minutes,
                        useDefault: false,
                    });
                });
            }
        });
        console.log(reminders, ' reminders');
        if (!(reminders?.length > 0)) {
            return;
        }
        const operationName = 'InsertReminder';
        const query = `
    mutation InsertReminder($reminders: [Reminder_insert_input!]!) {
            insert_Reminder(
                objects: $reminders,
                ){
                returning {
                  id
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
        console.log(response, ' this is response in insertRemindersGivenResource');
    }
    catch (e) {
        console.log(e, ' unable to upsert reminder');
    }
};
export const getGoogleIntegration = async (calendarIntegrationId) => {
    try {
        const operationName = 'getCalendarIntegration';
        const query = `query getCalendarIntegration($id: uuid!){
      Calendar_Integration_by_pk(id: $id) {
        id
        name
        token
        refreshToken
        clientType
      }
    }`;
        const variables = { id: calendarIntegrationId };
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
        // just to check
        console.log(response, ' this is response in getGoogleIntegration');
        if (response?.data?.Calendar_Integration_by_pk) {
            const { data: { Calendar_Integration_by_pk: { token, refreshToken, clientType }, }, } = response;
            return { token, refreshToken, clientType };
        }
    }
    catch (e) {
        console.log(e, ' unable to get google token');
    }
};
export const getGoogleColor = async (token) => {
    try {
        const config = {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        };
        const body = await got
            .get(googleColorUrl, config)
            .json();
        console.log(body, ' body inside getGoogleColor');
        return body;
    }
    catch (e) {
        console.log(e, ' unable to get colors');
    }
};
export const getGoogleCalendarInDb = async (calendarId) => {
    try {
        const operationName = 'GetCalendarById';
        const query = `query GetCalendarById($id: String!) {
      Calendar_by_pk(id: $id) {
        id
        title
        colorId
        account
        accessLevel
        modifiable
        resource
        defaultReminders
        globalPrimary
        deleted
        createdDate
        updatedAt
        userId
        foregroundColor
        backgroundColor
        pageToken
        syncToken
      }
    }`;
        const variables = { id: calendarId };
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
        // just to check
        console.log(response, ' this is response in getGoogleCalendar');
        if (response?.data?.Calendar_by_pk) {
            const { data: { Calendar_by_pk: { pageToken, syncToken, id }, }, } = response;
            return { pageToken, syncToken, id };
        }
    }
    catch (e) {
        console.log(e, ' unable to get google token');
    }
};
export const deleteAttendees = async (events, calendarId) => {
    try {
        const eventIds = events.map((e) => `${e?.id}#${calendarId}`);
        if (!(eventIds?.filter((e) => !!e)?.length > 0)) {
            return;
        }
        const operationName = 'DeleteAttendees';
        const query = `
      mutation DeleteAttendees($eventIds: [String!]!) {
        delete_Attendee(where: {eventId: {_in: $eventIds}}) {
          affected_rows
        }
      }
      `;
        const variables = {
            eventIds,
        };
        const results = await got
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
        console.log(results, ' successfully deleted attendees');
    }
    catch (e) {
        console.log(e, ' unable to delete attendees');
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
export const deleteZoomMeeting = async (zoomToken, conferenceId, scheduleForReminder, cancelMeetingReminder) => {
    try {
        let params = {};
        if (cancelMeetingReminder || scheduleForReminder) {
            if (cancelMeetingReminder) {
                params = { cancel_meeting_reminder: cancelMeetingReminder };
            }
            if (scheduleForReminder) {
                params = { ...params, schedule_for_reminder: scheduleForReminder };
            }
        }
        const stringifiedObject = Object.keys(params)?.length > 0 ? qs.stringify(params) : '';
        if (stringifiedObject) {
            await got.delete(`${zoomBaseUrl}/meetings/` + conferenceId + '?' + stringifiedObject, {
                headers: {
                    Authorization: `Bearer ${zoomToken}`,
                    ContentType: 'application/json',
                },
            });
        }
        else {
            await got.delete(`${zoomBaseUrl}/meetings/` + conferenceId, {
                headers: {
                    Authorization: `Bearer ${zoomToken}`,
                    ContentType: 'application/json',
                },
            });
        }
        console.log(conferenceId, 'successfully deleted meeting');
    }
    catch (e) {
        console.log(e, ' unable to delete zoom meeting');
    }
};
export const listConferencesWithHosts = async (ids) => {
    try {
        const operationName = 'ListConferencesWithHostId';
        const query = `
            query ListConferencesWithHostId($ids: [String!]!) {
                Conference(where: {id: {_in: $ids}, isHost: {_eq: true}}) {
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
            ids,
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
        console.log(res, ' successfully listed conferences with hosts');
        return res?.data?.Conference;
    }
    catch (e) {
        console.log(e, ' unable to list conferences with hosts');
    }
};
export const deleteConferencesInDb = async (conferenceIds) => {
    try {
        const operationName = 'deleteConferences';
        const query = `
            mutation deleteConferences($ids: [String!]!) {
                delete_Conference(where: {id: {_in: $ids}}) {
                    affected_rows
                }
            }
        `;
        const variables = {
            ids: conferenceIds,
        };
        const results = await got
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
        console.log(results, ' successfully deleted multiple conferences');
    }
    catch (e) {
        console.log(e, ' unable to delete conferences in db');
    }
};
export const deleteConferences = async (events) => {
    try {
        const conferenceIds = events?.map((e) => e?.conferenceId);
        const truthy = conferenceIds.filter((cId) => !!cId);
        if (!truthy?.[0]) {
            return;
        }
        // delete zoom meetings if any
        const conferences = await listConferencesWithHosts(conferenceIds);
        for (const conference of conferences) {
            const zoomToken = await getZoomAPIToken(conference?.userId);
            if (zoomToken && typeof parseInt(conference?.id, 10) === 'number') {
                await deleteZoomMeeting(zoomToken, parseInt(conference?.id, 10));
            }
        }
        // delete in db
        await deleteConferencesInDb(conferenceIds);
    }
    catch (e) {
        console.log(e, ' unable to deleteConference');
    }
};
export const deleteEvents = async (events, calendarId) => {
    try {
        const eventIds = events.map((e) => `${e?.id}#${calendarId}`);
        console.log(eventIds, ' eventIds inside deleteEvents');
        if (!(eventIds?.filter((e) => !!e)?.length > 0)) {
            return;
        }
        const operationName = 'deleteEvents';
        const query = `
            mutation deleteEvents($eventIds: [String!]!) {
                delete_Event(where: {id: {_in: $eventIds}}) {
                    affected_rows
                    returning {
                        eventId
                        id
                        calendarId
                        meetingId
                        conferenceId
                    }
                }
            }

        `;
        const variables = {
            eventIds,
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
        console.log(res, ' this is response in deleteEvents');
        return res?.data?.delete_Event?.returning;
    }
    catch (e) {
        console.log(e, ' unable to delete events');
    }
};
export const deleteReminders = async (events, userId, calendarId) => {
    try {
        if (!(events?.filter((e) => !!e?.id)?.length > 0)) {
            return;
        }
        const operationName = 'deleteReminders';
        const delEvents = events.map((e) => `${e?.id}#${calendarId}`);
        const query = `
      mutation deleteReminders($userId: uuid!, $eventIds: [String!]!) {
        delete_Reminder(where: {userId: {_eq: $userId}, eventId: {_in: $eventIds}}) {
          affected_rows
        }
      }
    `;
        const variables = {
            userId,
            eventIds: delEvents,
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
        console.log(response, ' this is response in deleteReminders');
    }
    catch (e) {
        console.log(e, ' unable to delete reminders');
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
    }
};
export const convertToTotalWorkingHours = (userPreference, startDate, timezone) => {
    const startTimes = userPreference.startTimes;
    const endTimes = userPreference.endTimes;
    const dayOfWeekInt = getISODay(dayjs(startDate.slice(0, 19)).tz(timezone, true).toDate());
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
export const listEventsForDate = async (userId, startDate, endDate, timezone) => {
    try {
        const operationName = 'listEventsForDate';
        const query = `
        query listEventsForDate($userId: uuid!, $startDate: timestamp!, $endDate: timestamp!) {
          Event(where: {userId: {_eq: $userId}, startDate: {_gte: $startDate, _lt: $endDate}, deleted: {_eq: false}}) {
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
                    endDate: dayjs(endDate).tz(timezone, true).format(),
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
    const breakHoursAvailable = (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
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
    let hoursUsed = 0;
    for (const event of allEvents) {
        const duration = dayjs
            .duration(dayjs(dayjs(event.endDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')).diff(dayjs(event.startDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')))
            .asHours();
        hoursUsed += duration;
    }
    if (hoursUsed >= workingHours) {
        console.log('hoursUsed >= workingHours');
        return false;
    }
    return true;
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
            id: `${eventId}#${globalCalendarId || eventMirror.calendarId}}`,
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
export const generateBreakEventsForDay = async (userPreferences, userId, startDate, timezone, eventsToBeBreaks = [], globalCalendarId, isFirstDay) => {
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
        if (!startDate) {
            console.log('no startDate provided inside shouldGenerateBreakEvents');
            return null;
        }
        if (!timezone) {
            console.log('no timezone provided inside shouldGenerateBreakEvents');
            return null;
        }
        if (isFirstDay) {
            const endTimes = userPreferences.endTimes;
            const dayOfWeekInt = getISODay(dayjs(startDate.slice(0, 19)).tz(timezone, true).toDate());
            let startHour = dayjs(startDate.slice(0, 19)).tz(timezone, true).hour();
            let startMinute = dayjs(startDate.slice(0, 19))
                .tz(timezone, true)
                .minute();
            const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
            const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
            // validate values before calculating
            const startTimes = userPreferences.startTimes;
            const workStartHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
            const workStartMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
            if (dayjs(startDate.slice(0, 19)).isAfter(dayjs(startDate.slice(0, 19)).hour(endHour).minute(endMinute))) {
                // return empty as outside of work time
                return null;
            }
            // change to work start time as before start time
            if (dayjs(startDate.slice(0, 19)).isBefore(dayjs(startDate.slice(0, 19))
                .hour(workStartHour)
                .minute(workStartMinute))) {
                startHour = workStartHour;
                startMinute = workStartMinute;
            }
            const workingHours = convertToTotalWorkingHours(userPreferences, startDate, timezone);
            const allEvents = await listEventsForDate(userId, dayjs(startDate.slice(0, 19))
                .tz(timezone, true)
                .hour(startHour)
                .minute(startMinute)
                .format(), dayjs(startDate.slice(0, 19))
                .tz(timezone, true)
                .hour(endHour)
                .minute(endMinute)
                .format(), timezone);
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
                        .tz(timezone, true)
                        .diff(dayjs(allEvent.startDate.slice(0, 19)).tz(timezone, true)))
                        .asHours();
                    hoursUsed += duration;
                }
            }
            let hoursAvailable = workingHours - hoursUsed;
            hoursAvailable -= workingHours * userPreferences.maxWorkLoadPercent;
            // no hours available
            if (hoursAvailable <= 0) {
                console.log(hoursAvailable, ' no hours available');
                return null;
            }
            const oldBreakEvents = allEvents
                .filter((event) => event.isBreak)
                .filter((e) => dayjs(startDate.slice(0, 19))
                .tz(timezone, true)
                .isSame(dayjs(e.startDate.slice(0, 19)).tz(timezone, true), 'day'));
            const breakEvents = eventsToBeBreaks.concat(oldBreakEvents);
            const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks;
            console.log(numberOfBreaksPerDay, ' numberOfBreaksPerDay');
            const breakHoursToGenerate = (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
            let breakHoursUsed = 0;
            if (breakEvents?.length > 0) {
                for (const breakEvent of breakEvents) {
                    const duration = dayjs
                        .duration(dayjs(breakEvent.endDate.slice(0, 19))
                        .tz(timezone, true)
                        .diff(dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true)))
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
            const eventMirror = allEvents.find((event) => !event.isBreak);
            const newEvents = generateBreaks(userPreferences, numberOfBreaksToGenerate, eventMirror, globalCalendarId);
            return newEvents;
        }
        const endTimes = userPreferences.endTimes;
        const dayOfWeekInt = getISODay(dayjs(startDate.slice(0, 19)).tz(timezone, true).toDate());
        const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
        const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
        // validate values before calculating
        const startTimes = userPreferences.startTimes;
        const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
        const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const workingHours = convertToTotalWorkingHours(userPreferences, startDate, timezone);
        const allEvents = await listEventsForDate(userId, dayjs(startDate.slice(0, 19))
            .tz(timezone, true)
            .hour(startHour)
            .minute(startMinute)
            .format(), dayjs(startDate.slice(0, 19))
            .tz(timezone, true)
            .hour(endHour)
            .minute(endMinute)
            .format(), timezone);
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
                    .tz(timezone, true)
                    .diff(dayjs(allEvent.startDate.slice(0, 19)).tz(timezone, true)))
                    .asHours();
                hoursUsed += duration;
            }
        }
        let hoursAvailable = workingHours - hoursUsed;
        hoursAvailable -= workingHours * userPreferences.maxWorkLoadPercent;
        // no hours available
        if (hoursAvailable <= 0) {
            console.log(hoursAvailable, ' no hours available');
            return null;
        }
        const oldBreakEvents = allEvents
            .filter((event) => event.isBreak)
            .filter((e) => dayjs(startDate.slice(0, 19))
            .tz(timezone, true)
            .isSame(dayjs(e.startDate.slice(0, 19)).tz(timezone, true), 'day'));
        const breakEvents = eventsToBeBreaks.concat(oldBreakEvents);
        const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks;
        console.log(numberOfBreaksPerDay, ' numberOfBreaksPerDay');
        const breakHoursToGenerate = (userPreferences.breakLength / 60) * numberOfBreaksPerDay;
        let breakHoursUsed = 0;
        if (breakEvents?.length > 0) {
            for (const breakEvent of breakEvents) {
                const duration = dayjs
                    .duration(dayjs(breakEvent.endDate.slice(0, 19))
                    .tz(timezone, true)
                    .diff(dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true)))
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
        const eventMirror = allEvents.find((event) => !event.isBreak);
        const newEvents = generateBreaks(userPreferences, numberOfBreaksToGenerate, eventMirror, globalCalendarId);
        return newEvents;
    }
    catch (e) {
        console.log(e, ' unable to generate breaks for day');
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
export const generateBreakEventsForDate = async (userPreferences, userId, startDate, endDate, timezone, eventsToBeBreaks = [], globalCalendarId) => {
    try {
        const totalBreakEvents = [];
        const totalDays = dayjs(endDate.slice(0, 19))
            .tz(timezone, true)
            .diff(dayjs(startDate.slice(0, 19)).tz(timezone, true), 'day');
        console.log(totalDays, ' totalDays inside generateBreakEventsForDate');
        for (let i = 0; i < totalDays; i++) {
            const dayDate = dayjs(startDate.slice(0, 19))
                .tz(timezone, true)
                .add(i, 'day')
                .format();
            const eventsToBeBreaksForDay = eventsToBeBreaks.filter((e) => dayjs(e.startDate.slice(0, 19))
                .tz(e.timezone, true)
                .isSame(dayDate, 'day'));
            const newBreakEvents = await generateBreakEventsForDay(userPreferences, userId, dayDate, timezone, eventsToBeBreaksForDay, globalCalendarId, i === 0);
            if (i === 0) {
                const endTimes = userPreferences.endTimes;
                const dayOfWeekInt = getISODay(dayjs(dayDate.slice(0, 19)).tz(timezone, true).toDate());
                let startHour = dayjs(dayDate.slice(0, 19)).tz(timezone, true).hour();
                let startMinute = dayjs(dayDate.slice(0, 19))
                    .tz(timezone, true)
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
                    .tz(timezone, true)
                    .hour(startHour)
                    .minute(startMinute)
                    .format(), dayjs(dayDate.slice(0, 19))
                    .tz(timezone, true)
                    .hour(endHour)
                    .minute(endMinute)
                    .format(), timezone);
                const newBreakEventsAdjusted = await adjustStartDatesForBreakEventsForDay(allEvents, newBreakEvents, userPreferences, timezone);
                if (newBreakEventsAdjusted?.length > 0) {
                    newBreakEventsAdjusted.forEach((b) => console.log(b, ' newBreakEventsAdjusted'));
                    totalBreakEvents.push(...newBreakEventsAdjusted);
                }
                continue;
            }
            const endTimes = userPreferences.endTimes;
            const dayOfWeekInt = getISODay(dayjs(dayDate.slice(0, 19)).tz(timezone, true).toDate());
            const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
            const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
            // validate values before calculating
            const startTimes = userPreferences.startTimes;
            const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
            const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
            const allEvents = await listEventsForDate(userId, dayjs(dayDate.slice(0, 19))
                .tz(timezone, true)
                .hour(startHour)
                .minute(startMinute)
                .format(), dayjs(dayDate.slice(0, 19))
                .tz(timezone, true)
                .hour(endHour)
                .minute(endMinute)
                .format(), timezone);
            const newBreakEventsAdjusted = await adjustStartDatesForBreakEventsForDay(allEvents, newBreakEvents, userPreferences, timezone);
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
export const upsertEventsPostPlanner = async (events) => {
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
                    method,
                    unlink,
                    copyColor,
                    userModifiedColor,
                    byWeekDay,
                    localSynced,
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
export const formatRemindersForGoogle = (reminders) => {
    const googleOverrides = reminders.map((reminder) => {
        return {
            method: 'email',
            minutes: reminder.minutes,
        };
    });
    const googleReminders = {
        overrides: googleOverrides,
        useDefault: false,
    };
    return googleReminders;
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
export const patchGoogleEvent = async (userId, calendarId, eventId, clientType, endDateTime, // either endDateTime or endDate - all day vs specific period
startDateTime, conferenceDataVersion, maxAttendees, sendUpdates, anyoneCanAddSelf, attendees, conferenceData, summary, description, timezone, // required for recurrence
startDate, endDate, extendedProperties, guestsCanInviteOthers, guestsCanModify, guestsCanSeeOtherGuests, originalStartDateTime, originalStartDate, recurrence, reminders, source, status, transparency, visibility, iCalUID, attendeesOmitted, hangoutLink, privateCopy, locked, attachments, eventType, location, colorId) => {
    try {
        // get token =
        const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType);
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
                date: dayjs(endDateTime.slice(0, 19))
                    .tz(timezone, true)
                    .format('YYYY-MM-DD'),
                timeZone: timezone,
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
            console.log(eventId, endDateTime, timezone, ' eventId, endDateTime, timezone prior');
            const end = {
                dateTime: endDateTime,
                timeZone: timezone,
            };
            requestBody.end = end;
            console.log(eventId, end.dateTime, end.timeZone, ' eventId, endDateTime, timeZone after');
        }
        if (startDate && timezone && !startDateTime) {
            const start = {
                date: dayjs(startDateTime.slice(0, 19))
                    .tz(timezone, true)
                    .format('YYYY-MM-DD'),
                timeZone: timezone,
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
        if (startDateTime && timezone && !startDate) {
            console.log(eventId, startDateTime, timezone, ' eventId, startDateTime, timezone prior');
            const start = {
                dateTime: startDateTime,
                timeZone: timezone,
            };
            requestBody.start = start;
            console.log(eventId, start.dateTime, start.timeZone, ' eventId, startDateTime, timeZone after');
        }
        if (originalStartDate && timezone && !originalStartDateTime) {
            const originalStartTime = {
                date: dayjs(originalStartDate.slice(0, 19))
                    .tz(timezone, true)
                    .format('YYYY-MM-DD'),
                timeZone: timezone,
            };
            requestBody.originalStartTime = originalStartTime;
        }
        if (originalStartDateTime && timezone && !originalStartDate) {
            const originalStartTime = {
                dateTime: originalStartDateTime,
                timeZone: timezone,
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
                        type: conferenceData.type,
                    },
                    requestId: conferenceData?.requestId || uuid(),
                },
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
        console.log(eventId, requestBody, ' eventId, requestBody inside googlePatchEvent');
        const res = await googleCalendar.events.patch(variables);
        console.log(eventId, res.data, ' eventId, results from googlePatchEvent');
    }
    catch (e) {
        console.log(e, ' unable to patch google event');
    }
};
export const createGoogleEvent = async (userId, calendarId, clientType, generatedId, endDateTime, // either endDateTime or endDate - all day vs specific period
startDateTime, conferenceDataVersion, maxAttendees, sendUpdates, anyoneCanAddSelf, attendees, conferenceData, summary, description, timezone, // required for recurrence
startDate, // all day
endDate, // all day
extendedProperties, guestsCanInviteOthers, guestsCanModify, guestsCanSeeOtherGuests, originalStartDateTime, originalStartDate, recurrence, reminders, source, status, transparency, visibility, iCalUID, attendeesOmitted, hangoutLink, privateCopy, locked, attachments, eventType, location, colorId) => {
    try {
        // get token =
        const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType);
        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        // const token = await getAPIToken(userId, googleCalendarResource, googleCalendarName)
        // let url = `${googleUrl}/${encodeURI(calendarId)}/events`
        // const config = {
        //   headers: {
        //     Authorization: `Bearer ${token}`,
        //     'Content-Type': 'application/json',
        //     'Accept': 'application/json',
        //   },
        // }
        // if any query parameters build them
        // first
        if (maxAttendees || sendUpdates || conferenceDataVersion > 0) {
            // url = `${url}?`
            let params = {};
            if (maxAttendees) {
                params = { ...params, maxAttendees };
            }
            if (sendUpdates) {
                params = { ...params, sendUpdates };
            }
            if (conferenceDataVersion > 0) {
                params = { ...params, conferenceDataVersion };
            }
            if (params?.maxAttendees ||
                params?.sendUpdates ||
                params?.conferenceDataVersion > -1) {
                // url = `${url}${qs.stringify(params)}`
            }
        }
        // create request body
        let data = {};
        if (endDateTime && timezone && !endDate) {
            // BUG: calling dayjs here offsets endDateTime value
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
        if (reminders) {
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
        // if (id) {
        //   data = { ...data, id }
        // }
        // const results = await got.post<eventResponse>(
        //   url,
        //   {
        //     json: data,
        //     ...config,
        //   },
        // ).json()
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
        return { id: res?.data?.id, generatedId };
    }
    catch (e) {
        console.log(e, ' createGoogleEvent');
    }
};
export const postPlannerModifyEventInCalendar = async (newEvent, userId, method, resource, isTimeBlocking, clientType, newReminders, attendees, conference) => {
    try {
        console.log(newEvent, ' newEvent inside postPlannerModifyEventInCalendar');
        if (method === 'update') {
            // update event
            if (resource === googleCalendarResource) {
                const googleReminders = newReminders?.length > 0
                    ? formatRemindersForGoogle(newReminders)
                    : undefined;
                // update event
                await patchGoogleEvent(userId, newEvent.calendarId, newEvent.eventId, clientType, newEvent.endDate, newEvent.startDate, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, newEvent.timezone, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, googleReminders, undefined, undefined, newEvent.transparency, newEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, newEvent?.colorId);
                return newEvent.id;
            }
            // else if (resource === outlookCalendarResource) {
            //   // await updateOutlookEvent(newEvent)
            // }
        }
        else if (method === 'create') {
            console.log(newEvent, ' newEvent inside create inside postPlannerModifyEventInCalendar');
            // create task events only
            if (resource === googleCalendarResource) {
                const googleReminders = newReminders?.length > 0
                    ? formatRemindersForGoogle(newReminders)
                    : undefined;
                const idAndGenIdObject = await createGoogleEvent(userId, newEvent.calendarId, clientType, newEvent?.eventId, // generatedId
                newEvent?.endDate, newEvent?.startDate, undefined, undefined, undefined, undefined, attendees?.map((a) => ({
                    email: a?.primaryEmail,
                    id: a?.id,
                    displayName: a?.name,
                })), conference?.id
                    ? {
                        type: conference?.app === 'zoom' ? 'addOn' : 'hangoutsMeet',
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
                    : undefined, newEvent.summary || newEvent?.title, newEvent.notes, newEvent.timezone, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, newEvent?.recurrence, googleReminders, undefined, undefined, newEvent.transparency, undefined, undefined, undefined, undefined, undefined, undefined, undefined, isTimeBlocking ? 'focusTime' : 'default', undefined, newEvent?.colorId);
                console.log(idAndGenIdObject, newEvent?.endDate, newEvent?.startDate, ' idAndGenIdObject, newEvent?.endDate,  newEvent?.startDate');
                return idAndGenIdObject;
            }
        }
    }
    catch (e) {
        console.log(e, ' unable to update event');
        console.log(newEvent?.id, newEvent?.endDate, newEvent?.startDate, ' error - newEvent?.id, newEvent?.endDate,  newEvent?.startDate');
    }
};
export const generateBreakEventsForCalendarSync = async (userId, timezone, clientType) => {
    try {
        // validate
        if (!userId) {
            console.log('no userId inside generateBreakEventsForCalendarSync');
            return;
        }
        if (!timezone) {
            console.log('no timezone inside generateBreakEventsForCalendarSync');
            return;
        }
        if (!clientType) {
            console.log('no clientType inside generateBreakEventsForCalendarSync');
            return;
        }
        const userPreferences = await getUserPreferences(userId);
        const breakEvents = await generateBreakEventsForDate(userPreferences, userId, dayjs().tz(timezone, true).format(), dayjs().tz(timezone, true).add(7, 'd').format(), timezone);
        const results = (await Promise.all(breakEvents.map((b) => postPlannerModifyEventInCalendar(b, userId, 'create', googleCalendarResource, false, clientType))));
        console.log(results, ' results form modifying postPlannerModifyEventInCalendar inside generateBreakEventsForCalendarSync');
        if (!(breakEvents?.length > 0)) {
            console.log('no breakEvents to upsert');
            return;
        }
        const eventsToUpsert = [];
        for (const result of results) {
            const foundEvent = breakEvents?.find((e) => e?.eventId === result?.generatedId);
            if (foundEvent?.id) {
                foundEvent.id = `${result?.id}#${foundEvent?.calendarId}`;
                foundEvent.eventId = result?.id;
                eventsToUpsert.push(foundEvent);
            }
        }
        await upsertEventsPostPlanner(eventsToUpsert);
    }
    catch (e) {
        console.log(e, ' unable to generatezbreakEventsForCalendarSync');
    }
};
export async function directUpdateGoogleEventAndHasura(userId, calendarId, eventId, // This is Google's event ID
clientType, updates) {
    if (!eventId || Object.keys(updates).length === 0) {
        console.log('Missing eventId or empty updates object.');
        return false;
    }
    try {
        // 1. Prepare Google Calendar API patch request
        const patchRequestBody = {
            ...updates,
        };
        // 2. Get Google API Token
        const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType);
        if (!token) {
            console.error('Failed to get Google API token.');
            return false;
        }
        // 3. Initialize Google Calendar API
        const googleCalendar = google.calendar({
            version: 'v3',
            headers: { Authorization: `Bearer ${token}` },
        });
        // 4. Call Google Calendar API events.patch
        try {
            console.log(`Patching Google event ${eventId} in calendar ${calendarId} with updates:`, JSON.stringify(patchRequestBody));
            await googleCalendar.events.patch({
                calendarId,
                eventId,
                requestBody: patchRequestBody,
                conferenceDataVersion: 1, // Enable conference data modifications
            });
            console.log(`Google event ${eventId} patched successfully.`);
        }
        catch (googleError) {
            console.error(`Error patching Google event ${eventId}:`, googleError.response?.data || googleError.message);
            return false;
        }
        // 5. Prepare Hasura Update Payload
        const hasuraEventId = `${eventId}#${calendarId}`;
        const hasuraUpdatePayload = {
            updatedAt: new Date().toISOString(),
        };
        if (updates.summary !== undefined)
            hasuraUpdatePayload.summary = updates.summary;
        if (updates.description !== undefined)
            hasuraUpdatePayload.notes = updates.description; // Map description to notes
        if (updates.location !== undefined) {
            // Assuming Event.location in Hasura is a simple text field for direct updates.
            // If it's a JSONB type expecting { title: string }, then:
            // hasuraUpdatePayload.location = { title: updates.location };
            hasuraUpdatePayload.location = updates.location;
        }
        if (updates.status !== undefined)
            hasuraUpdatePayload.status = updates.status;
        if (updates.transparency !== undefined)
            hasuraUpdatePayload.transparency = updates.transparency;
        if (updates.visibility !== undefined)
            hasuraUpdatePayload.visibility = updates.visibility;
        if (updates.colorId !== undefined)
            hasuraUpdatePayload.colorId = updates.colorId;
        // Handle conferenceData
        if (updates.conferenceData === null) {
            hasuraUpdatePayload.hangoutLink = null;
            hasuraUpdatePayload.conferenceId = null;
            // Potentially clear other conference related fields in Hasura if they exist
        }
        else if (updates.conferenceData) {
            // Attempt to extract hangoutLink and conferenceId
            // This is a simplified extraction. Google's conferenceData can be complex.
            if (updates.conferenceData.entryPoints &&
                Array.isArray(updates.conferenceData.entryPoints)) {
                const videoEntryPoint = updates.conferenceData.entryPoints.find((ep) => ep.entryPointType === 'video');
                if (videoEntryPoint && videoEntryPoint.uri) {
                    hasuraUpdatePayload.hangoutLink = videoEntryPoint.uri;
                }
            }
            if (updates.conferenceData.conferenceId) {
                hasuraUpdatePayload.conferenceId = updates.conferenceData.conferenceId;
            }
            // If you store the full conferenceData object in Hasura (e.g., as JSONB)
            // hasuraUpdatePayload.conferenceData = updates.conferenceData;
        }
        // Remove undefined fields from payload to avoid Hasura errors
        Object.keys(hasuraUpdatePayload).forEach((key) => {
            if (hasuraUpdatePayload[key] === undefined) {
                delete hasuraUpdatePayload[key];
            }
        });
        if (Object.keys(hasuraUpdatePayload).length === 1 &&
            hasuraUpdatePayload.updatedAt) {
            console.log('No mappable fields to update in Hasura besides updatedAt.');
            // Still proceed to update 'updatedAt' or return true if Google update was the only goal
            // For now, let's proceed to update 'updatedAt'
        }
        // 6. Construct and execute Hasura update_Event_by_pk mutation
        const operationName = 'UpdateEventByPkDirect';
        const query = `
            mutation ${operationName}($id: String!, $changes: Event_set_input!) {
                update_Event_by_pk(pk_columns: {id: $id}, _set: $changes) {
                    id
                    updatedAt
                }
            }
        `;
        const variables = {
            id: hasuraEventId,
            changes: hasuraUpdatePayload,
        };
        console.log(`Updating Hasura event ${hasuraEventId} with payload:`, JSON.stringify(hasuraUpdatePayload));
        const hasuraResponse = await got
            .post(hasuraGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin', // Or appropriate user role
            },
            responseType: 'json',
        })
            .json();
        if (hasuraResponse.errors) {
            console.error(`Error updating Hasura event ${hasuraEventId}:`, JSON.stringify(hasuraResponse.errors, null, 2));
            // Google update was successful, but Hasura failed.
            // May need a reconciliation strategy or specific error handling.
            return false; // Indicate partial failure
        }
        console.log(`Hasura event ${hasuraEventId} updated successfully.`);
        return true;
    }
    catch (error) {
        console.error('An unexpected error occurred in directUpdateGoogleEventAndHasura:', error);
        return false;
    }
}
export async function streamToString(stream) {
    return await new Promise((resolve, reject) => {
        const chunks = [];
        stream.on('data', (chunk) => chunks.push(chunk));
        stream.on('error', reject);
        stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    });
}
export const addToQueueForVectorSearch = async (userId, events) => {
    const producer = kafka.producer({ maxInFlightRequests: 1, idempotent: true });
    await producer.connect();
    const transaction = await producer.transaction();
    try {
        // process.env.EVENT_TO_VECTOR_QUEUE_URL
        const singletonId = uuid();
        const params = {
            Body: JSON.stringify({
                events,
                userId,
            }),
            Bucket: bucketName,
            Key: `${userId}/${singletonId}.json`,
            ContentType: 'application/json',
        };
        const s3Command = new PutObjectCommand(params);
        const s3Response = await s3Client.send(s3Command);
        console.log(s3Response, ' s3Response');
        const response = await transaction.send({
            topic: kafkaGoogleCalendarSyncTopic,
            messages: [
                { value: JSON.stringify({ fileKey: `${userId}/${singletonId}.json` }) },
            ],
        });
        const admin = kafka.admin();
        await admin.connect();
        const partitions = await admin.fetchOffsets({
            groupId: kafkaGoogleCalendarSyncGroupId,
            topics: [kafkaGoogleCalendarSyncTopic],
        });
        console.log(partitions);
        await admin.disconnect();
        await transaction.sendOffsets({
            consumerGroupId: kafkaGoogleCalendarSyncGroupId,
            topics: [
                {
                    topic: kafkaGoogleCalendarSyncTopic,
                    partitions: partitions?.[0]?.partitions,
                },
            ],
        });
        await transaction.commit();
        console.log(response, ' response successfully added to queue inside addToQueueForVectorSearch');
    }
    catch (e) {
        console.log(e, ' unable to add to queue');
        await transaction.abort();
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBQ3RCLGdDQUFnQztBQUNoQyxJQUFJLE1BQVcsQ0FBQztBQUNoQixJQUFJLENBQUM7SUFDSCxNQUFNLFlBQVksR0FBRyxPQUFPLENBQUMsUUFBUSxDQUFDLENBQUM7SUFDdkMsTUFBTSxHQUFHLFlBQVksQ0FBQyxNQUFNLENBQUM7QUFDL0IsQ0FBQztBQUFDLE1BQU0sQ0FBQztJQUNQLG1DQUFtQztJQUNuQyxNQUFNLEdBQUcsTUFBTSxVQUFVO1FBQ3ZCLFlBQVksTUFBVyxJQUFHLENBQUM7UUFDM0IsSUFBSSxHQUFHO1lBQ0wsV0FBVyxFQUFFO2dCQUNYLE1BQU0sRUFBRSxLQUFLLEVBQUUsTUFBVyxFQUFFLEVBQUUsQ0FBQyxDQUFDO29CQUM5QixPQUFPLEVBQUU7d0JBQ1A7NEJBQ0UsT0FBTyxFQUFFO2dDQUNQLE9BQU8sRUFBRSxlQUFlOzZCQUN6Qjt5QkFDRjtxQkFDRjtpQkFDRixDQUFDO2FBQ0g7U0FDRixDQUFDO0tBQ0gsQ0FBQztBQUNKLENBQUM7QUFDRCxPQUFPLEVBRUwsVUFBVSxFQUNWLGVBQWUsRUFDZixzQkFBc0IsRUFDdEIsMEJBQTBCLEVBQzFCLHFCQUFxQixFQUNyQix1QkFBdUIsRUFDdkIsaUJBQWlCLEVBQ2pCLGlCQUFpQixFQUNqQiwyQkFBMkIsRUFDM0IscUJBQXFCLEVBQ3JCLGNBQWMsRUFDZCxrQkFBa0IsRUFDbEIsY0FBYyxFQUNkLGlCQUFpQixFQUNqQixjQUFjLEVBQ2QsOEJBQThCLEVBQzlCLDRCQUE0QixFQUM1QixXQUFXLEVBQ1gsa0NBQWtDLEVBQ2xDLGdCQUFnQixFQUNoQixnQkFBZ0IsRUFDaEIsV0FBVyxFQUNYLFlBQVksRUFDWixnQkFBZ0IsRUFDaEIsYUFBYSxFQUNiLFdBQVcsRUFDWCxnQkFBZ0IsRUFDaEIsZUFB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LENBQUMsT0FBTyxFQUFFLENBQUM7UUFDdEIsTUFBTSxVQUFVLEdBQUcsTUFBTSxLQUFLLENBQUMsWUFBWSxDQUFDO1lBQzFDLE9BQU8sRUFBRSw4QkFBOEI7WUFDdkMsTUFBTSxFQUFFLENBQUMsNEJBQTRCLENBQUM7U0FDdkMsQ0FBQyxDQUFDO1FBQ0gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxVQUFVLENBQUMsQ0FBQztRQUN4QixNQUFNLEtBQUssQ0FBQyxVQUFVLEVBQUUsQ0FBQztRQUV6QixNQUFNLFdBQVcsQ0FBQyxXQUFXLENBQUM7WUFDNUIsZUFBZSxFQUFFLDhCQUE4QjtZQUMvQyxNQUFNLEVBQUU7Z0JBQ047b0JBQ0UsS0FBSyxFQUFFLDRCQUE0QjtvQkFDbkMsVUFBVSxFQUFFLFVBQVUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLFVBQVU7aUJBQ3hDO2FBQ0Y7U0FDRixDQUFDLENBQUM7UUFFSCxNQUFNLFdBQVcsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUUzQixPQUFPLENBQUMsR0FBRyxDQUNULFFBQVEsRUFDUix3RUFBd0UsQ0FDekUsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUseUJBQXlCLENBQUMsQ0FBQztRQUMxQyxNQUFNLFdBQVcsQ0FBQyxLQUFLLEVBQUUsQ0FBQztJQUM1QixDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuLy8gTW9jayBPcGVuQUkgZm9yIGxvY2FsIHRlc3RpbmdcbmxldCBPcGVuQUk6IGFueTtcbnRyeSB7XG4gIGNvbnN0IG9wZW5haU1vZHVsZSA9IHJlcXVpcmUoJ29wZW5haScpO1xuICBPcGVuQUkgPSBvcGVuYWlNb2R1bGUuT3BlbkFJO1xufSBjYXRjaCB7XG4gIC8vIFVzZSBtb2NrIGlmIE9wZW5BSSBub3QgYXZhaWxhYmxlXG4gIE9wZW5BSSA9IGNsYXNzIE1vY2tPcGVuQUkge1xuICAgIGNvbnN0cnVjdG9yKGNvbmZpZzogYW55KSB7fVxuICAgIGNoYXQgPSB7XG4gICAgICBjb21wbGV0aW9uczoge1xuICAgICAgICBjcmVhdGU6IGFzeW5jIChwYXJhbXM6IGFueSkgPT4gKHtcbiAgICAgICAgICBjaG9pY2VzOiBbXG4gICAgICAgICAgICB7XG4gICAgICAgICAgICAgIG1lc3NhZ2U6IHtcbiAgICAgICAgICAgICAgICBjb250ZW50OiAnTW9jayByZXNwb25zZScsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIF0sXG4gICAgICAgIH0pLFxuICAgICAgfSxcbiAgICB9O1xuICB9O1xufVxuaW1wb3J0IHtcbiAgYXV0aEFwaVRva2VuLFxuICBidWNrZXROYW1lLFxuICBldmVudFZlY3Rvck5hbWUsXG4gIGdvb2dsZUNhbGVuZGFyUmVzb3VyY2UsXG4gIGdvb2dsZUNhbGVuZGFyU3RvcFdhdGNoVXJsLFxuICBnb29nbGVDbGllbnRJZEFuZHJvaWQsXG4gIGdvb2dsZUNsaWVudElkQXRvbWljV2ViLFxuICBnb29nbGVDbGllbnRJZElvcyxcbiAgZ29vZ2xlQ2xpZW50SWRXZWIsXG4gIGdvb2dsZUNsaWVudFNlY3JldEF0b21pY1dlYixcbiAgZ29vZ2xlQ2xpZW50U2VjcmV0V2ViLFxuICBnb29nbGVDb2xvclVybCxcbiAgZ29vZ2xlTWVldFJlc291cmNlLFxuICBnb29nbGVUb2tlblVybCxcbiAgaGFzdXJhQWRtaW5TZWNyZXQsXG4gIGhhc3VyYUdyYXBoVXJsLFxuICBrYWZrYUdvb2dsZUNhbGVuZGFyU3luY0dyb3VwSWQsXG4gIGthZmthR29vZ2xlQ2FsZW5kYXJTeW5jVG9waWMsXG4gIHNlYXJjaEluZGV4LFxuICBzZWxmR29vZ2xlQ2FsZW5kYXJXZWJob29rUHVibGljVXJsLFxuICB2ZWN0b3JEaW1lbnNpb25zLFxuICB6b29tQmFzZVRva2VuVXJsLFxuICB6b29tQmFzZVVybCxcbiAgem9vbUNsaWVudElkLFxuICB6b29tQ2xpZW50U2VjcmV0LFxuICB6b29tSVZGb3JQYXNzLFxuICB6b29tUGFzc0tleSxcbiAgem9vbVJlc291cmNlTmFtZSxcbiAgem9vbVNhbHRGb3JQYXNzLFxufSBmcm9tICcuL2NvbnN0YW50cyc7XG5pbXBvcnQge1xuICBDYWxlbmRhclR5cGUsXG4gIENhbGVuZGFyV2ViaG9va1R5cGUsXG4gIGVzUmVzcG9uc2VCb2R5LFxuICBFdmVudFBsdXNUeXBlLFxuICBFdmVudFJlc291cmNlVHlwZSxcbiAgRXZlbnRUeXBlLFxuICBHb29nbGVBdHRhY2htZW50VHlwZSxcbiAgR29vZ2xlQXR0ZW5kZWVUeXBlLFxuICBHb29nbGVDb25mZXJlbmNlRGF0YVR5cGUsXG4gIEdvb2dsZUV2ZW50VHlwZTEsXG4gIEdvb2dsZUV4dGVuZGVkUHJvcGVydGllc1R5cGUsXG4gIEdvb2dsZVJlbWluZGVyVHlwZSxcbiAgR29vZ2xlU2VuZFVwZGF0ZXNUeXBlLFxuICBHb29nbGVTb3VyY2VUeXBlLFxuICBHb29nbGVUcmFuc3BhcmVuY3lUeXBlLFxuICBHb29nbGVWaXNpYmlsaXR5VHlwZSxcbiAgTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSxcbiAgT3ZlcnJpZGVUeXBlcyxcbiAgUmVtaW5kZXJUeXBlLFxuICBVc2VyUHJlZmVyZW5jZVR5cGUsXG59IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbi8vIE1vY2sgZGF0ZS1mbnMgZm9yIGxvY2FsIHRlc3RpbmdcbmxldCBnZXRJU09EYXk6IGFueTtcbnRyeSB7XG4gIGNvbnN0IGRhdGVGbnMgPSByZXF1aXJlKCdkYXRlLWZucycpO1xuICBnZXRJU09EYXkgPSBkYXRlRm5zLmdldElTT0RheTtcbn0gY2F0Y2gge1xuICBnZXRJU09EYXkgPSAoZGF0ZTogRGF0ZSkgPT4ge1xuICAgIGNvbnN0IGRheSA9IGRhdGUuZ2V0RGF5KCk7XG4gICAgcmV0dXJuIGRheSA9PT0gMCA/IDcgOiBkYXk7XG4gIH07XG59XG5pbXBvcnQgZGF5anMgZnJvbSAnZGF5anMnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcbmltcG9ydCBkdXJhdGlvbiBmcm9tICdkYXlqcy9wbHVnaW4vZHVyYXRpb24nO1xuLy8gaW1wb3J0IGlzb1dlZWsgZnJvbSAnZGF5anMvcGx1Z2luL2lzb1dlZWsnXG5pbXBvcnQgaXNCZXR3ZWVuIGZyb20gJ2RheWpzL3BsdWdpbi9pc0JldHdlZW4nO1xuaW1wb3J0IHRpbWV6b25lIGZyb20gJ2RheWpzL3BsdWdpbi90aW1lem9uZSc7XG5pbXBvcnQge1xuICBBdHRlbmRlZVR5cGUsXG4gIENhbGVuZGFySW50ZWdyYXRpb25UeXBlLFxuICBDYWxlbmRhcldhdGNoUmVxdWVzdFJlc291cmNlVHlwZSxcbiAgY29sb3JUeXBlUmVzcG9uc2UsXG4gIENvbmZlcmVuY2VUeXBlLFxufSBmcm9tICdAL2dvb2dsZS1jYWxlbmRhci1zeW5jL19saWJzL3R5cGVzL2dvb2dsZUNhbGVuZGFyU3luYy90eXBlcyc7XG4vLyBNb2NrIGdvb2dsZWFwaXMgZm9yIGxvY2FsIHRlc3RpbmdcbmxldCBnb29nbGU6IGFueTtcbnRyeSB7XG4gIGNvbnN0IGdvb2dsZWFwaXMgPSByZXF1aXJlKCdnb29nbGVhcGlzJyk7XG4gIGdvb2dsZSA9IGdvb2dsZWFwaXMuZ29vZ2xlO1xufSBjYXRjaCB7XG4gIGdvb2dsZSA9IHtcbiAgICBhdXRoOiB7XG4gICAgICBPQXV0aDI6IGNsYXNzIE1vY2tPQXV0aDIge1xuICAgICAgICBjcmVkZW50aWFsczogYW55ID0ge307XG4gICAgICAgIGNvbnN0cnVjdG9yKC4uLmFyZ3M6IGFueVtdKSB7fVxuICAgICAgICBzZXRDcmVkZW50aWFscyh0b2tlbnM6IGFueSkge1xuICAgICAgICAgIHRoaXMuY3JlZGVudGlhbHMgPSB0b2tlbnM7XG4gICAgICAgIH1cbiAgICAgICAgZ2V0QWNjZXNzVG9rZW4oKSB7XG4gICAgICAgICAgcmV0dXJuIFByb21pc2UucmVzb2x2ZSh7IHRva2VuOiAnbW9jay10b2tlbicgfSk7XG4gICAgICAgIH1cbiAgICAgIH0sXG4gICAgfSxcbiAgICBjYWxlbmRhcjogKG9wdGlvbnM6IGFueSkgPT4gKHtcbiAgICAgIGV2ZW50czoge1xuICAgICAgICBsaXN0OiBhc3luYyAoKSA9PiAoeyBkYXRhOiB7IGl0ZW1zOiBbXSB9IH0pLFxuICAgICAgICBpbnNlcnQ6IGFzeW5jICgpID0+ICh7IGRhdGE6IHt9IH0pLFxuICAgICAgICB1cGRhdGU6IGFzeW5jICgpID0+ICh7IGRhdGE6IHt9IH0pLFxuICAgICAgICBkZWxldGU6IGFzeW5jICgpID0+ICh7fSksXG4gICAgICB9LFxuICAgIH0pLFxuICB9O1xufVxuXG4vLyBNb2NrIE9wZW5TZWFyY2ggZm9yIGxvY2FsIHRlc3RpbmdcbmxldCBDbGllbnQ6IGFueTtcbnRyeSB7XG4gIGNvbnN0IG9wZW5zZWFyY2ggPSByZXF1aXJlKCdAb3BlbnNlYXJjaC1wcm9qZWN0L29wZW5zZWFyY2gnKTtcbiAgQ2xpZW50ID0gb3BlbnNlYXJjaC5DbGllbnQ7XG59IGNhdGNoIHtcbiAgQ2xpZW50ID0gY2xhc3MgTW9ja0NsaWVudCB7XG4gICAgY29uc3RydWN0b3IoY29uZmlnOiBhbnkpIHt9XG4gICAgc2VhcmNoID0gYXN5bmMgKCkgPT4gKHsgYm9keTogeyBoaXRzOiB7IGhpdHM6IFtdIH0gfSB9KTtcbiAgICBpbmRleCA9IGFzeW5jICgpID0+ICh7IGJvZHk6IHt9IH0pO1xuICB9O1xufVxuXG4vLyBNb2NrIGdvb2dsZS1jYWxlbmRhci1zeW5jLWFkbWluXG5sZXQgaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzI6IGFueTtcbnRyeSB7XG4gIGNvbnN0IGdjYWxBZG1pbiA9IHJlcXVpcmUoJ0Bnb29nbGVfY2FsZW5kYXJfc3luYy9nb29nbGVDYWxlbmRhclN5bmMvZ29vZ2xlLWNhbGVuZGFyLXN5bmMtYWRtaW4nKTtcbiAgaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzIgPSBnY2FsQWRtaW4uaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzI7XG59IGNhdGNoIHtcbiAgaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzIgPSBhc3luYyAoKSA9PiAoeyBzdWNjZXNzOiB0cnVlIH0pO1xufVxuaW1wb3J0IHsgRXZlbnRUcmlnZ2VyVHlwZSB9IGZyb20gJ0AvZ29vZ2xlLWNhbGVuZGFyLXN5bmMvX2xpYnMvdHlwZXMvZ29vZ2xlUGVvcGxlU3luYy90eXBlcyc7XG5pbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnO1xuaW1wb3J0IHFzIGZyb20gJ3FzJztcbmltcG9ydCBjcnlwdG8gZnJvbSAnY3J5cHRvJztcbmltcG9ydCB7IFJlYWRhYmxlIH0gZnJvbSAnc3RyZWFtJztcbmltcG9ydCB7IEV2ZW50T2JqZWN0Rm9yVmVjdG9yVHlwZSB9IGZyb20gJ0AvZ29vZ2xlLWNhbGVuZGFyLXN5bmMvX2xpYnMvdHlwZXMvZXZlbnQyVmVjdG9ycy90eXBlcyc7XG4vLyBNb2NrIEFXUyBTMyBmb3IgbG9jYWwgdGVzdGluZ1xubGV0IFMzQ2xpZW50OiBhbnksIFB1dE9iamVjdENvbW1hbmQ6IGFueTtcbnRyeSB7XG4gIGNvbnN0IHMzID0gcmVxdWlyZSgnQGF3cy1zZGsvY2xpZW50LXMzJyk7XG4gIFMzQ2xpZW50ID0gczMuUzNDbGllbnQ7XG4gIFB1dE9iamVjdENvbW1hbmQgPSBzMy5QdXRPYmplY3RDb21tYW5kO1xufSBjYXRjaCB7XG4gIFMzQ2xpZW50ID0gY2xhc3MgTW9ja1MzQ2xpZW50IHtcbiAgICBjb25zdHJ1Y3Rvcihjb25maWc6IGFueSkge31cbiAgICBzZW5kID0gYXN5bmMgKCkgPT4gKHsgRVRhZzogJ1wibW9jay1ldGFnXCInIH0pO1xuICB9O1xuICBQdXRPYmplY3RDb21tYW5kID0gY2xhc3MgTW9ja1B1dE9iamVjdENvbW1hbmQge1xuICAgIGNvbnN0cnVjdG9yKHBhcmFtczogYW55KSB7fVxuICB9O1xufVxuXG4vLyBNb2NrIEthZmthIGZvciBsb2NhbCB0ZXN0aW5nXG5sZXQgS2Fma2E6IGFueSwgbG9nTGV2ZWw6IGFueTtcbnRyeSB7XG4gIGNvbnN0IGthZmthanMgPSByZXF1aXJlKCdrYWZrYWpzJyk7XG4gIEthZmthID0ga2Fma2Fqcy5LYWZrYTtcbiAgbG9nTGV2ZWwgPSBrYWZrYWpzLmxvZ0xldmVsO1xufSBjYXRjaCB7XG4gIEthZmthID0gY2xhc3MgTW9ja0thZmthIHtcbiAgICBjb25zdHJ1Y3Rvcihjb25maWc6IGFueSkge31cbiAgICBwcm9kdWNlcigpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIGNvbm5lY3Q6IGFzeW5jICgpID0+IHt9LFxuICAgICAgICBzZW5kOiBhc3luYyAoKSA9PiB7fSxcbiAgICAgICAgZGlzY29ubmVjdDogYXN5bmMgKCkgPT4ge30sXG4gICAgICB9O1xuICAgIH1cbiAgfTtcbiAgbG9nTGV2ZWwgPSB7IElORk86IDEgfTtcbn1cblxuLy8gTW9jayBpcCBtb2R1bGUgZm9yIGxvY2FsIHRlc3RpbmdcbmxldCBpcDogYW55O1xudHJ5IHtcbiAgaXAgPSByZXF1aXJlKCdpcCcpO1xufSBjYXRjaCB7XG4gIGlwID0ge1xuICAgIGFkZHJlc3M6ICgpID0+ICcxMjcuMC4wLjEnLFxuICB9O1xufVxuXG5kYXlqcy5leHRlbmQodXRjKTtcbmRheWpzLmV4dGVuZChkdXJhdGlvbik7XG4vLyBkYXlqcy5leHRlbmQoaXNvV2VlaylcbmRheWpzLmV4dGVuZChpc0JldHdlZW4pO1xuZGF5anMuZXh0ZW5kKHRpbWV6b25lKTtcblxuY29uc3Qgb3BlbmFpID0gbmV3IE9wZW5BSSh7XG4gIGFwaUtleTogcHJvY2Vzcy5lbnYuT1BFTkFJX0FQSV9LRVksXG59KTtcblxuY29uc3QgczNDbGllbnQgPSBuZXcgUzNDbGllbnQoe1xuICBjcmVkZW50aWFsczoge1xuICAgIGFjY2Vzc0tleUlkOiBwcm9jZXNzLmVudi5TM19BQ0NFU1NfS0VZLFxuICAgIHNlY3JldEFjY2Vzc0tleTogcHJvY2Vzcy5lbnYuUzNfU0VDUkVUX0tFWSxcbiAgfSxcbiAgZW5kcG9pbnQ6IHByb2Nlc3MuZW52LlMzX0VORFBPSU5ULFxuICBmb3JjZVBhdGhTdHlsZTogdHJ1ZSxcbn0pO1xuXG5jb25zdCBrYWZrYSA9IG5ldyBLYWZrYSh7XG4gIGxvZ0xldmVsOiBsb2dMZXZlbC5ERUJVRyxcbiAgYnJva2VyczogW2BrYWZrYTE6MjkwOTJgXSxcbiAgY2xpZW50SWQ6ICdhdG9taWMnLFxuICAvLyBzc2w6IHRydWUsXG4gIHNhc2w6IHtcbiAgICBtZWNoYW5pc206ICdwbGFpbicsIC8vIHNjcmFtLXNoYS0yNTYgb3Igc2NyYW0tc2hhLTUxMlxuICAgIHVzZXJuYW1lOiBwcm9jZXNzLmVudi5LQUZLQV9VU0VSTkFNRSxcbiAgICBwYXNzd29yZDogcHJvY2Vzcy5lbnYuS0FGS0FfUEFTU1dPUkQsXG4gIH0sXG59KTtcblxuZXhwb3J0IGNvbnN0IGluc2VydEV2ZW50VHJpZ2dlcnMgPSBhc3luYyAob2JqZWN0czogRXZlbnRUcmlnZ2VyVHlwZVtdKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdpbnNlcnRFdmVudFRyaWdnZXJzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIG11dGF0aW9uIGluc2VydEV2ZW50VHJpZ2dlcnMoJG9iamVjdHM6IFtFdmVudF9UcmlnZ2VyX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICBpbnNlcnRfRXZlbnRfVHJpZ2dlcihvYmplY3RzOiAkb2JqZWN0cykge1xuICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgb2JqZWN0cyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgaW5zZXJ0X0V2ZW50X1RyaWdnZXI6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyIH0gfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyBhZmZlY3RlZF9yb3dzIGluc2lkZSBpbnNlcnQgZXZlbnQgdHJpZ2dlcnMnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGluc2VydCBldmVudCB0cmlnZ2VyJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRFdmVudFRyaWdnZXJCeVJlc291cmNlSWQgPSBhc3luYyAocmVzb3VyY2VJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgaWYgKCFyZXNvdXJjZUlkKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gcmVzb3VyY2VJZCBpbnNpZGUgZ2V0RXZlbnRUcmlnZ2VyQnlSZXNvdXJjZUlkJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRFdmVudFRyaWdnZXJCeVJlc291cmNlSWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgIHF1ZXJ5IEdldEV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZCgkcmVzb3VyY2VJZDogU3RyaW5nKSB7XG4gICAgICBFdmVudF9UcmlnZ2VyKHdoZXJlOiB7cmVzb3VyY2VJZDoge19lcTogJHJlc291cmNlSWR9fSkge1xuICAgICAgICBjcmVhdGVkQXRcbiAgICAgICAgaWRcbiAgICAgICAgbmFtZVxuICAgICAgICByZXNvdXJjZVxuICAgICAgICByZXNvdXJjZUlkXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VySWRcbiAgICAgIH1cbiAgICB9XG4gICAgYDtcbiAgICBjb25zdCByZXNwb25zZTogeyBkYXRhOiB7IEV2ZW50X1RyaWdnZXI6IEV2ZW50VHJpZ2dlclR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgcmVzb3VyY2VJZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgcmVzcG9uc2UgaW5zaWRlIGdldEV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZCcpO1xuICAgIHJldHVybiByZXNwb25zZT8uZGF0YT8uRXZlbnRfVHJpZ2dlcj8uWzBdO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0RXZlbnRUcmlnZ2VyQnlSZXNvdXJjZUlkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVFdmVudFRyaWdnZXJCeUlkID0gYXN5bmMgKGlkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2RlbGV0ZUV2ZW50VHJpZ2dlckJ5SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgbXV0YXRpb24gZGVsZXRlRXZlbnRUcmlnZ2VyQnlJZCgkaWQ6IHV1aWQhKSB7XG4gICAgICAgIGRlbGV0ZV9FdmVudF9UcmlnZ2VyX2J5X3BrKGlkOiAkaWQpIHtcbiAgICAgICAgICBpZFxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCByZXMgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgaWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlcywgJyBkZWxldGVFdmVudFRyaWdnZXJCeUlkJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGRlbGV0ZUV2ZW50VHJpZ2dlckJ5SWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHJlc2V0R29vZ2xlU3luY0ZvckNhbGVuZGFyID0gYXN5bmMgKFxuICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ3VwZGF0ZUNhbGVuZGFyJztcbiAgICBjb25zdCBxdWVyeSA9IGBtdXRhdGlvbiB1cGRhdGVDYWxlbmRhcigkaWQ6IFN0cmluZyEsICRjaGFuZ2VzOiBDYWxlbmRhcl9zZXRfaW5wdXQpIHtcbiAgICAgIHVwZGF0ZV9DYWxlbmRhcl9ieV9wayhwa19jb2x1bW5zOiB7aWQ6ICRpZH0sIF9zZXQ6ICRjaGFuZ2VzKSB7XG4gICAgICAgIHBhZ2VUb2tlblxuICAgICAgICBzeW5jVG9rZW5cbiAgICAgIH1cbiAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZDogY2FsZW5kYXJJZCxcbiAgICAgIGNoYW5nZXM6IHtcbiAgICAgICAgcGFnZVRva2VuOiBudWxsLFxuICAgICAgICBzeW5jVG9rZW46IG51bGwsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHRoaXMgaXMgcmVzcG9uc2UgaW4gcmVzZXRHb29nbGVJbnRlZ3JhdGlvblN5bmMnKTtcbiAgICAvLyBjb25zdCB7IHRva2VuOiBhdXRoVG9rZW4gfSA9IGF3YWl0IGdldEdvb2dsZUludGVncmF0aW9uKGNhbGVuZGFySW50ZWdyYXRpb25JZClcbiAgICByZXR1cm4gaW5pdGlhbEdvb2dsZUNhbGVuZGFyU3luYzIoY2FsZW5kYXJJZCwgdXNlcklkLCBjbGllbnRUeXBlKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlc2V0IGdvb2dsZSBpbnRlZ3JhdGlvbiBzeW5jJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVNZWV0aW5nQXNzaXN0c0dpdmVuSWRzID0gYXN5bmMgKGlkczogc3RyaW5nW10pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0RlbGV0ZU1lZXRpbmdBc3Npc3RzQnlJZHMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gRGVsZXRlTWVldGluZ0Fzc2lzdHNCeUlkcygkaWRzOiBbdXVpZCFdISkge1xuICAgICAgICAgICAgICAgIGRlbGV0ZV9NZWV0aW5nX0Fzc2lzdCh3aGVyZToge2lkOiB7X2luOiAkaWRzfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgICBhbGxvd0F0dGVuZGVlVXBkYXRlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNvdW50XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGJ1ZmZlclRpbWVcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxJZkFueVJlZnVzZVxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxsZWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlQXBwXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGZyZXF1ZW5jeVxuICAgICAgICAgICAgICAgICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGludGVydmFsXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIG1pblRocmVzaG9sZENvdW50XG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsTWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdW50aWxcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgd2luZG93RW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICB3aW5kb3dTdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkcyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgc3VjY2Vzc2Z1bGx5IGRlbGV0ZWQgbWVldGluZ2Fzc2lzdHMgd2l0aCBnaXZlbiBpZHMnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBtZWV0aW5nIGFzc2lzdHMgZ2l2ZW4gaWRzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBhZGRsb2NhbEl0ZW1zVG9FdmVudDJWZWN0b3JPYmplY3RzID0gKFxuICBsb2NhbEl0ZW1zOiBFdmVudFJlc291cmNlVHlwZVtdLFxuICBldmVudDJWZWN0b3JPYmplY3RzOiBFdmVudE9iamVjdEZvclZlY3RvclR5cGVbXSxcbiAgY2FsZW5kYXJJZDogc3RyaW5nXG4pID0+IHtcbiAgZm9yIChjb25zdCBsb2NhbEl0ZW0gb2YgbG9jYWxJdGVtcykge1xuICAgIGNvbnN0IHN0YXR1cyA9ICdjYW5jZWxsZWQnO1xuICAgIGlmIChsb2NhbEl0ZW0/LnN0YXR1cyA9PT0gc3RhdHVzKSB7XG4gICAgICAoZXZlbnQyVmVjdG9yT2JqZWN0cyBhcyBFdmVudE9iamVjdEZvclZlY3RvclR5cGVbXSkucHVzaCh7XG4gICAgICAgIG1ldGhvZDogJ2RlbGV0ZScsXG4gICAgICAgIGV2ZW50OiBsb2NhbEl0ZW0sXG4gICAgICAgIGNhbGVuZGFySWQsXG4gICAgICB9KTtcbiAgICB9IGVsc2Uge1xuICAgICAgKGV2ZW50MlZlY3Rvck9iamVjdHMgYXMgRXZlbnRPYmplY3RGb3JWZWN0b3JUeXBlW10pLnB1c2goe1xuICAgICAgICBtZXRob2Q6ICd1cHNlcnQnLFxuICAgICAgICBldmVudDogbG9jYWxJdGVtLFxuICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgfSk7XG4gICAgfVxuICB9XG59O1xuXG5leHBvcnQgY29uc3QgaW5jcmVtZW50YWxHb29nbGVDYWxlbmRhclN5bmMyID0gYXN5bmMgKFxuICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInLFxuICBwYXJlbnRTeW5jVG9rZW46IHN0cmluZyxcbiAgcGFyZW50UGFnZVRva2VuPzogc3RyaW5nLFxuICBjb2xvckl0ZW0/OiBjb2xvclR5cGVSZXNwb25zZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IHBhZ2VUb2tlbiA9IHBhcmVudFBhZ2VUb2tlbjtcbiAgICBsZXQgc3luY1Rva2VuID0gcGFyZW50U3luY1Rva2VuO1xuICAgIGxldCBsb2NhbEl0ZW1zOiBFdmVudFJlc291cmNlVHlwZVtdIHwgW10gPSBbXTtcbiAgICBjb25zdCBldmVudDJWZWN0b3JPYmplY3RzOiBFdmVudE9iamVjdEZvclZlY3RvclR5cGVbXSB8IFtdID0gW107XG5cbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZUFQSVRva2VuKFxuICAgICAgdXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJSZXNvdXJjZSxcbiAgICAgIGNsaWVudFR5cGVcbiAgICApO1xuXG4gICAgY29uc3QgZ29vZ2xlQ2FsZW5kYXIgPSBnb29nbGUuY2FsZW5kYXIoe1xuICAgICAgdmVyc2lvbjogJ3YzJyxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc3QgaW5pdGlhbFZhcmlhYmxlczogYW55ID0ge1xuICAgICAgLy8gQ2FsZW5kYXIgaWRlbnRpZmllci4gVG8gcmV0cmlldmUgY2FsZW5kYXIgSURzIGNhbGwgdGhlIGNhbGVuZGFyTGlzdC5saXN0IG1ldGhvZC4gSWYgeW91IHdhbnQgdG8gYWNjZXNzIHRoZSBwcmltYXJ5IGNhbGVuZGFyIG9mIHRoZSBjdXJyZW50bHkgbG9nZ2VkIGluIHVzZXIsIHVzZSB0aGUgXCJwcmltYXJ5XCIga2V5d29yZC5cbiAgICAgIGNhbGVuZGFySWQsXG4gICAgICAvLyBXaGV0aGVyIHRvIGluY2x1ZGUgZGVsZXRlZCBldmVudHMgKHdpdGggc3RhdHVzIGVxdWFscyBcImNhbmNlbGxlZFwiKSBpbiB0aGUgcmVzdWx0LiBDYW5jZWxsZWQgaW5zdGFuY2VzIG9mIHJlY3VycmluZyBldmVudHMgKGJ1dCBub3QgdGhlIHVuZGVybHlpbmcgcmVjdXJyaW5nIGV2ZW50KSB3aWxsIHN0aWxsIGJlIGluY2x1ZGVkIGlmIHNob3dEZWxldGVkIGFuZCBzaW5nbGVFdmVudHMgYXJlIGJvdGggRmFsc2UuIElmIHNob3dEZWxldGVkIGFuZCBzaW5nbGVFdmVudHMgYXJlIGJvdGggVHJ1ZSwgb25seSBzaW5nbGUgaW5zdGFuY2VzIG9mIGRlbGV0ZWQgZXZlbnRzIChidXQgbm90IHRoZSB1bmRlcmx5aW5nIHJlY3VycmluZyBldmVudHMpIGFyZSByZXR1cm5lZC4gT3B0aW9uYWwuIFRoZSBkZWZhdWx0IGlzIEZhbHNlLlxuICAgICAgc2hvd0RlbGV0ZWQ6IHRydWUsXG4gICAgICAvLyBXaGV0aGVyIHRvIGV4cGFuZCByZWN1cnJpbmcgZXZlbnRzIGludG8gaW5zdGFuY2VzIGFuZCBvbmx5IHJldHVybiBzaW5nbGUgb25lLW9mZiBldmVudHMgYW5kIGluc3RhbmNlcyBvZiByZWN1cnJpbmcgZXZlbnRzLCBidXQgbm90IHRoZSB1bmRlcmx5aW5nIHJlY3VycmluZyBldmVudHMgdGhlbXNlbHZlcy4gT3B0aW9uYWwuIFRoZSBkZWZhdWx0IGlzIEZhbHNlLlxuICAgICAgc2luZ2xlRXZlbnRzOiB0cnVlLFxuICAgICAgc3luY1Rva2VuLFxuICAgIH07XG5cbiAgICBpZiAocGFyZW50UGFnZVRva2VuKSB7XG4gICAgICBpbml0aWFsVmFyaWFibGVzLnBhZ2VUb2tlbiA9IHBhcmVudFBhZ2VUb2tlbjtcbiAgICB9XG5cbiAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVDYWxlbmRhci5ldmVudHMubGlzdChpbml0aWFsVmFyaWFibGVzKTtcbiAgICBjb25zb2xlLmxvZyhyZXMuZGF0YSk7XG5cbiAgICAvLyB7XG4gICAgLy8gICBcImFjY2Vzc1JvbGVcIjogXCJteV9hY2Nlc3NSb2xlXCIsXG4gICAgLy8gICBcImRlZmF1bHRSZW1pbmRlcnNcIjogW10sXG4gICAgLy8gICBcImRlc2NyaXB0aW9uXCI6IFwibXlfZGVzY3JpcHRpb25cIixcbiAgICAvLyAgIFwiZXRhZ1wiOiBcIm15X2V0YWdcIixcbiAgICAvLyAgIFwiaXRlbXNcIjogW10sXG4gICAgLy8gICBcImtpbmRcIjogXCJteV9raW5kXCIsXG4gICAgLy8gICBcIm5leHRQYWdlVG9rZW5cIjogXCJteV9uZXh0UGFnZVRva2VuXCIsXG4gICAgLy8gICBcIm5leHRTeW5jVG9rZW5cIjogXCJteV9uZXh0U3luY1Rva2VuXCIsXG4gICAgLy8gICBcInN1bW1hcnlcIjogXCJteV9zdW1tYXJ5XCIsXG4gICAgLy8gICBcInRpbWVab25lXCI6IFwibXlfdGltZVpvbmVcIixcbiAgICAvLyAgIFwidXBkYXRlZFwiOiBcIm15X3VwZGF0ZWRcIlxuICAgIC8vIH1cbiAgICBjb25zdCB7IGl0ZW1zLCBuZXh0UGFnZVRva2VuLCBuZXh0U3luY1Rva2VuIH0gPSByZXMuZGF0YTtcblxuICAgIGxvY2FsSXRlbXMgPSBpdGVtcyBhcyBFdmVudFJlc291cmNlVHlwZVtdO1xuICAgIHBhZ2VUb2tlbiA9IG5leHRQYWdlVG9rZW47XG4gICAgc3luY1Rva2VuID0gbmV4dFN5bmNUb2tlbjtcblxuICAgIGFkZGxvY2FsSXRlbXNUb0V2ZW50MlZlY3Rvck9iamVjdHMoXG4gICAgICBsb2NhbEl0ZW1zLFxuICAgICAgZXZlbnQyVmVjdG9yT2JqZWN0cyxcbiAgICAgIGNhbGVuZGFySWRcbiAgICApO1xuXG4gICAgYXdhaXQgdXBkYXRlR29vZ2xlQ2FsZW5kYXJUb2tlbnNJbkRiKFxuICAgICAgY2FsZW5kYXJJZCxcbiAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICBuZXh0UGFnZVRva2VuXG4gICAgKTtcbiAgICBjb25zdCBzdGF0dXMgPSAnY2FuY2VsbGVkJztcblxuICAgIGNvbnN0IGRlbGV0ZWRFdmVudHMgPSBsb2NhbEl0ZW1zLmZpbHRlcigoZSkgPT4gZT8uc3RhdHVzID09PSBzdGF0dXMpO1xuXG4gICAgaWYgKGRlbGV0ZWRFdmVudHM/LlswXT8uaWQpIHtcbiAgICAgIGNvbnN0IHJldHVybmVkRGVsZXRlZEV2ZW50VmFsdWVzID0gYXdhaXQgZGVsZXRlRXZlbnRzKFxuICAgICAgICBkZWxldGVkRXZlbnRzLFxuICAgICAgICBjYWxlbmRhcklkXG4gICAgICApO1xuICAgICAgY29uc3QgbWVldGluZ0lkc1RvRGVsZXRlID0gcmV0dXJuZWREZWxldGVkRXZlbnRWYWx1ZXNcbiAgICAgICAgPy5maWx0ZXIoKGUpID0+ICEhZT8ubWVldGluZ0lkKVxuICAgICAgICA/Lm1hcCgoZSkgPT4gZT8ubWVldGluZ0lkKTtcblxuICAgICAgaWYgKG1lZXRpbmdJZHNUb0RlbGV0ZSAmJiBtZWV0aW5nSWRzVG9EZWxldGU/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgYXdhaXQgZGVsZXRlTWVldGluZ0Fzc2lzdHNHaXZlbklkcyhtZWV0aW5nSWRzVG9EZWxldGUpO1xuICAgICAgfVxuXG4gICAgICAvLyBkZWxldGUgYW55IHZpcnR1YWwgY29uZmVyZW5jZXNcbiAgICAgIGF3YWl0IGRlbGV0ZUNvbmZlcmVuY2VzKHJldHVybmVkRGVsZXRlZEV2ZW50VmFsdWVzKTtcblxuICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXG4gICAgICAgIGRlbGV0ZUF0dGVuZGVlcyhkZWxldGVkRXZlbnRzLCBjYWxlbmRhcklkKSxcbiAgICAgICAgZGVsZXRlUmVtaW5kZXJzKGRlbGV0ZWRFdmVudHMsIHVzZXJJZCwgY2FsZW5kYXJJZCksXG4gICAgICBdO1xuXG4gICAgICBhd2FpdCBQcm9taXNlLmFsbChwcm9taXNlcyk7XG4gICAgfVxuXG4gICAgY29uc3QgZXZlbnRzVG9VcHNlcnQgPSBsb2NhbEl0ZW1zPy5maWx0ZXIoKGUpID0+IGU/LnN0YXR1cyAhPT0gc3RhdHVzKTtcblxuICAgIC8vIG5vIGV2ZW50cyB0byB1cHNlcnQgY2hlY2sgbmV4dCBwYWdldG9rZW5cbiAgICBpZiAoIWV2ZW50c1RvVXBzZXJ0Py5bMF0/LmlkKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlbicpO1xuICAgICAgY29uc3QgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICAgIC8vIENhbGVuZGFyIGlkZW50aWZpZXIuIFRvIHJldHJpZXZlIGNhbGVuZGFyIElEcyBjYWxsIHRoZSBjYWxlbmRhckxpc3QubGlzdCBtZXRob2QuIElmIHlvdSB3YW50IHRvIGFjY2VzcyB0aGUgcHJpbWFyeSBjYWxlbmRhciBvZiB0aGUgY3VycmVudGx5IGxvZ2dlZCBpbiB1c2VyLCB1c2UgdGhlIFwicHJpbWFyeVwiIGtleXdvcmQuXG4gICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgIC8vIFdoZXRoZXIgdG8gaW5jbHVkZSBkZWxldGVkIGV2ZW50cyAod2l0aCBzdGF0dXMgZXF1YWxzIFwiY2FuY2VsbGVkXCIpIGluIHRoZSByZXN1bHQuIENhbmNlbGxlZCBpbnN0YW5jZXMgb2YgcmVjdXJyaW5nIGV2ZW50cyAoYnV0IG5vdCB0aGUgdW5kZXJseWluZyByZWN1cnJpbmcgZXZlbnQpIHdpbGwgc3RpbGwgYmUgaW5jbHVkZWQgaWYgc2hvd0RlbGV0ZWQgYW5kIHNpbmdsZUV2ZW50cyBhcmUgYm90aCBGYWxzZS4gSWYgc2hvd0RlbGV0ZWQgYW5kIHNpbmdsZUV2ZW50cyBhcmUgYm90aCBUcnVlLCBvbmx5IHNpbmdsZSBpbnN0YW5jZXMgb2YgZGVsZXRlZCBldmVudHMgKGJ1dCBub3QgdGhlIHVuZGVybHlpbmcgcmVjdXJyaW5nIGV2ZW50cykgYXJlIHJldHVybmVkLiBPcHRpb25hbC4gVGhlIGRlZmF1bHQgaXMgRmFsc2UuXG4gICAgICAgIHNob3dEZWxldGVkOiB0cnVlLFxuICAgICAgICAvLyBXaGV0aGVyIHRvIGV4cGFuZCByZWN1cnJpbmcgZXZlbnRzIGludG8gaW5zdGFuY2VzIGFuZCBvbmx5IHJldHVybiBzaW5nbGUgb25lLW9mZiBldmVudHMgYW5kIGluc3RhbmNlcyBvZiByZWN1cnJpbmcgZXZlbnRzLCBidXQgbm90IHRoZSB1bmRlcmx5aW5nIHJlY3VycmluZyBldmVudHMgdGhlbXNlbHZlcy4gT3B0aW9uYWwuIFRoZSBkZWZhdWx0IGlzIEZhbHNlLlxuICAgICAgICBzaW5nbGVFdmVudHM6IHRydWUsXG4gICAgICAgIHN5bmNUb2tlbixcbiAgICAgIH07XG5cbiAgICAgIGlmIChwYWdlVG9rZW4pIHtcbiAgICAgICAgdmFyaWFibGVzLnBhZ2VUb2tlbiA9IHBhZ2VUb2tlbjtcbiAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlQ2FsZW5kYXIuZXZlbnRzLmxpc3QodmFyaWFibGVzKTtcbiAgICAgICAgY29uc29sZS5sb2cocmVzLmRhdGEpO1xuXG4gICAgICAgIGNvbnN0IHsgaXRlbXMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuXG4gICAgICAgIGxvY2FsSXRlbXMgPSBpdGVtcyBhcyBFdmVudFJlc291cmNlVHlwZVtdO1xuICAgICAgICBwYWdlVG9rZW4gPSBuZXh0UGFnZVRva2VuO1xuICAgICAgICBzeW5jVG9rZW4gPSBuZXh0U3luY1Rva2VuO1xuXG4gICAgICAgIGFkZGxvY2FsSXRlbXNUb0V2ZW50MlZlY3Rvck9iamVjdHMoXG4gICAgICAgICAgbG9jYWxJdGVtcyxcbiAgICAgICAgICBldmVudDJWZWN0b3JPYmplY3RzLFxuICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgKTtcbiAgICAgICAgYXdhaXQgdXBkYXRlR29vZ2xlQ2FsZW5kYXJUb2tlbnNJbkRiKFxuICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICBuZXh0UGFnZVRva2VuXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRlbGV0ZWRFdmVudHMgPSBsb2NhbEl0ZW1zLmZpbHRlcigoZSkgPT4gZT8uc3RhdHVzID09PSBzdGF0dXMpO1xuXG4gICAgICAgIGlmIChkZWxldGVkRXZlbnRzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgY29uc3QgcmV0dXJuZWREZWxldGVkRXZlbnRWYWx1ZXMgPSBhd2FpdCBkZWxldGVFdmVudHMoXG4gICAgICAgICAgICBkZWxldGVkRXZlbnRzLFxuICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICk7XG4gICAgICAgICAgY29uc3QgbWVldGluZ0lkc1RvRGVsZXRlID0gcmV0dXJuZWREZWxldGVkRXZlbnRWYWx1ZXNcbiAgICAgICAgICAgID8uZmlsdGVyKChlKSA9PiAhIWU/Lm1lZXRpbmdJZClcbiAgICAgICAgICAgID8ubWFwKChlKSA9PiBlPy5tZWV0aW5nSWQpO1xuXG4gICAgICAgICAgaWYgKG1lZXRpbmdJZHNUb0RlbGV0ZSAmJiBtZWV0aW5nSWRzVG9EZWxldGU/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIGF3YWl0IGRlbGV0ZU1lZXRpbmdBc3Npc3RzR2l2ZW5JZHMobWVldGluZ0lkc1RvRGVsZXRlKTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBhd2FpdCBkZWxldGVDb25mZXJlbmNlcyhyZXR1cm5lZERlbGV0ZWRFdmVudFZhbHVlcyk7XG5cbiAgICAgICAgICBjb25zdCBwcm9taXNlcyA9IFtcbiAgICAgICAgICAgIGRlbGV0ZUF0dGVuZGVlcyhkZWxldGVkRXZlbnRzLCBjYWxlbmRhcklkKSxcbiAgICAgICAgICAgIGRlbGV0ZVJlbWluZGVycyhkZWxldGVkRXZlbnRzLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgIF07XG5cbiAgICAgICAgICBhd2FpdCBQcm9taXNlLmFsbChwcm9taXNlcyk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBldmVudHNUb1Vwc2VydDIgPSBsb2NhbEl0ZW1zPy5maWx0ZXIoKGUpID0+IGU/LnN0YXR1cyAhPT0gc3RhdHVzKTtcbiAgICAgICAgaWYgKGV2ZW50c1RvVXBzZXJ0Mj8uWzBdPy5pZCkge1xuICAgICAgICAgIGF3YWl0IHVwc2VydENvbmZlcmVuY2UyKGV2ZW50c1RvVXBzZXJ0MiwgdXNlcklkLCBjYWxlbmRhcklkKTtcbiAgICAgICAgICBhd2FpdCB1cHNlcnRFdmVudHMyKGV2ZW50c1RvVXBzZXJ0MiwgdXNlcklkLCBjYWxlbmRhcklkLCBjb2xvckl0ZW0pO1xuXG4gICAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXG4gICAgICAgICAgICBkZWxldGVSZW1pbmRlcnMoZXZlbnRzVG9VcHNlcnQyLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgaW5zZXJ0UmVtaW5kZXJzR2l2ZW5FdmVudFJlc291cmNlKFxuICAgICAgICAgICAgICBldmVudHNUb1Vwc2VydDIsXG4gICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgKSxcbiAgICAgICAgICAgIHVwc2VydEF0dGVuZGVlczIoZXZlbnRzVG9VcHNlcnQyLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgIF07XG5cbiAgICAgICAgICBhd2FpdCBQcm9taXNlLmFsbChwcm9taXNlcyk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZTIoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCk7XG4gICAgICBhd2FpdCB1cHNlcnRFdmVudHMyKGV2ZW50c1RvVXBzZXJ0LCB1c2VySWQsIGNhbGVuZGFySWQsIGNvbG9ySXRlbSk7XG5cbiAgICAgIGF3YWl0IGRlbGV0ZVJlbWluZGVycyhldmVudHNUb1Vwc2VydCwgdXNlcklkLCBjYWxlbmRhcklkKTtcbiAgICAgIGNvbnN0IHByb21pc2VzID0gW1xuICAgICAgICBpbnNlcnRSZW1pbmRlcnNHaXZlbkV2ZW50UmVzb3VyY2UoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCksXG4gICAgICAgIHVwc2VydEF0dGVuZGVlczIoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCksXG4gICAgICBdO1xuICAgICAgYXdhaXQgUHJvbWlzZS5hbGwocHJvbWlzZXMpO1xuICAgIH1cblxuICAgIGlmIChwYWdlVG9rZW4pIHtcbiAgICAgIC8vIGZldGNoIGFsbCBwYWdlc1xuICAgICAgd2hpbGUgKHBhZ2VUb2tlbikge1xuICAgICAgICBjb25zdCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgICAgICAvLyBDYWxlbmRhciBpZGVudGlmaWVyLiBUbyByZXRyaWV2ZSBjYWxlbmRhciBJRHMgY2FsbCB0aGUgY2FsZW5kYXJMaXN0Lmxpc3QgbWV0aG9kLiBJZiB5b3Ugd2FudCB0byBhY2Nlc3MgdGhlIHByaW1hcnkgY2FsZW5kYXIgb2YgdGhlIGN1cnJlbnRseSBsb2dnZWQgaW4gdXNlciwgdXNlIHRoZSBcInByaW1hcnlcIiBrZXl3b3JkLlxuICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgLy8gVG9rZW4gc3BlY2lmeWluZyB3aGljaCByZXN1bHQgcGFnZSB0byByZXR1cm4uIE9wdGlvbmFsLlxuICAgICAgICAgIHBhZ2VUb2tlbixcbiAgICAgICAgICAvLyBXaGV0aGVyIHRvIGluY2x1ZGUgZGVsZXRlZCBldmVudHMgKHdpdGggc3RhdHVzIGVxdWFscyBcImNhbmNlbGxlZFwiKSBpbiB0aGUgcmVzdWx0LiBDYW5jZWxsZWQgaW5zdGFuY2VzIG9mIHJlY3VycmluZyBldmVudHMgKGJ1dCBub3QgdGhlIHVuZGVybHlpbmcgcmVjdXJyaW5nIGV2ZW50KSB3aWxsIHN0aWxsIGJlIGluY2x1ZGVkIGlmIHNob3dEZWxldGVkIGFuZCBzaW5nbGVFdmVudHMgYXJlIGJvdGggRmFsc2UuIElmIHNob3dEZWxldGVkIGFuZCBzaW5nbGVFdmVudHMgYXJlIGJvdGggVHJ1ZSwgb25seSBzaW5nbGUgaW5zdGFuY2VzIG9mIGRlbGV0ZWQgZXZlbnRzIChidXQgbm90IHRoZSB1bmRlcmx5aW5nIHJlY3VycmluZyBldmVudHMpIGFyZSByZXR1cm5lZC4gT3B0aW9uYWwuIFRoZSBkZWZhdWx0IGlzIEZhbHNlLlxuICAgICAgICAgIHNob3dEZWxldGVkOiB0cnVlLFxuICAgICAgICAgIC8vIFdoZXRoZXIgdG8gZXhwYW5kIHJlY3VycmluZyBldmVudHMgaW50byBpbnN0YW5jZXMgYW5kIG9ubHkgcmV0dXJuIHNpbmdsZSBvbmUtb2ZmIGV2ZW50cyBhbmQgaW5zdGFuY2VzIG9mIHJlY3VycmluZyBldmVudHMsIGJ1dCBub3QgdGhlIHVuZGVybHlpbmcgcmVjdXJyaW5nIGV2ZW50cyB0aGVtc2VsdmVzLiBPcHRpb25hbC4gVGhlIGRlZmF1bHQgaXMgRmFsc2UuXG4gICAgICAgICAgc2luZ2xlRXZlbnRzOiB0cnVlLFxuICAgICAgICAgIHN5bmNUb2tlbixcbiAgICAgICAgfTtcblxuICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVDYWxlbmRhci5ldmVudHMubGlzdCh2YXJpYWJsZXMpO1xuICAgICAgICBjb25zb2xlLmxvZyhyZXMuZGF0YSk7XG5cbiAgICAgICAgY29uc3QgeyBpdGVtcywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG5cbiAgICAgICAgbG9jYWxJdGVtcyA9IGl0ZW1zIGFzIEV2ZW50UmVzb3VyY2VUeXBlW107XG4gICAgICAgIHBhZ2VUb2tlbiA9IG5leHRQYWdlVG9rZW47XG4gICAgICAgIHN5bmNUb2tlbiA9IG5leHRTeW5jVG9rZW47XG4gICAgICAgIC8vIHRva2VucyBpbiBjYXNlIHNvbWV0aGluZyBnb2VzIHdyb25nXG4gICAgICAgIC8vIHVwZGF0ZSBwYWdlVG9rZW4gYW5kIHN5bmNUb2tlblxuXG4gICAgICAgIGFkZGxvY2FsSXRlbXNUb0V2ZW50MlZlY3Rvck9iamVjdHMoXG4gICAgICAgICAgbG9jYWxJdGVtcyxcbiAgICAgICAgICBldmVudDJWZWN0b3JPYmplY3RzLFxuICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgKTtcblxuICAgICAgICBhd2FpdCB1cGRhdGVHb29nbGVDYWxlbmRhclRva2Vuc0luRGIoXG4gICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgICAgIG5leHRQYWdlVG9rZW5cbiAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBkZWxldGVkRXZlbnRzID0gbG9jYWxJdGVtcy5maWx0ZXIoKGUpID0+IGU/LnN0YXR1cyA9PT0gc3RhdHVzKTtcblxuICAgICAgICBpZiAoZGVsZXRlZEV2ZW50cz8uWzBdPy5pZCkge1xuICAgICAgICAgIGNvbnN0IHJldHVybmVkRGVsZXRlZEV2ZW50VmFsdWVzID0gYXdhaXQgZGVsZXRlRXZlbnRzKFxuICAgICAgICAgICAgZGVsZXRlZEV2ZW50cyxcbiAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICApO1xuICAgICAgICAgIGNvbnN0IG1lZXRpbmdJZHNUb0RlbGV0ZSA9IHJldHVybmVkRGVsZXRlZEV2ZW50VmFsdWVzXG4gICAgICAgICAgICA/LmZpbHRlcigoZSkgPT4gISFlPy5tZWV0aW5nSWQpXG4gICAgICAgICAgICA/Lm1hcCgoZSkgPT4gZT8ubWVldGluZ0lkKTtcblxuICAgICAgICAgIGlmIChtZWV0aW5nSWRzVG9EZWxldGUgJiYgbWVldGluZ0lkc1RvRGVsZXRlPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICBhd2FpdCBkZWxldGVNZWV0aW5nQXNzaXN0c0dpdmVuSWRzKG1lZXRpbmdJZHNUb0RlbGV0ZSk7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgYXdhaXQgZGVsZXRlQ29uZmVyZW5jZXMocmV0dXJuZWREZWxldGVkRXZlbnRWYWx1ZXMpO1xuXG4gICAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXG4gICAgICAgICAgICBkZWxldGVBdHRlbmRlZXMoZGVsZXRlZEV2ZW50cywgY2FsZW5kYXJJZCksXG4gICAgICAgICAgICBkZWxldGVSZW1pbmRlcnMoZGVsZXRlZEV2ZW50cywgdXNlcklkLCBjYWxlbmRhcklkKSxcbiAgICAgICAgICBdO1xuXG4gICAgICAgICAgYXdhaXQgUHJvbWlzZS5hbGwocHJvbWlzZXMpO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgZXZlbnRzVG9VcHNlcnQgPSBsb2NhbEl0ZW1zPy5maWx0ZXIoKGUpID0+IGU/LnN0YXR1cyAhPT0gc3RhdHVzKTtcblxuICAgICAgICAvLyBubyBldmVudHMgdG8gdXBzZXJ0IGNoZWNrIG5leHQgcGFnZXRva2VuXG4gICAgICAgIGlmICghZXZlbnRzVG9VcHNlcnQ/LlswXT8uaWQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlbicpO1xuICAgICAgICAgIGNvbnN0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgICAgICAgLy8gQ2FsZW5kYXIgaWRlbnRpZmllci4gVG8gcmV0cmlldmUgY2FsZW5kYXIgSURzIGNhbGwgdGhlIGNhbGVuZGFyTGlzdC5saXN0IG1ldGhvZC4gSWYgeW91IHdhbnQgdG8gYWNjZXNzIHRoZSBwcmltYXJ5IGNhbGVuZGFyIG9mIHRoZSBjdXJyZW50bHkgbG9nZ2VkIGluIHVzZXIsIHVzZSB0aGUgXCJwcmltYXJ5XCIga2V5d29yZC5cbiAgICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgICAvLyBXaGV0aGVyIHRvIGluY2x1ZGUgZGVsZXRlZCBldmVudHMgKHdpdGggc3RhdHVzIGVxdWFscyBcImNhbmNlbGxlZFwiKSBpbiB0aGUgcmVzdWx0LiBDYW5jZWxsZWQgaW5zdGFuY2VzIG9mIHJlY3VycmluZyBldmVudHMgKGJ1dCBub3QgdGhlIHVuZGVybHlpbmcgcmVjdXJyaW5nIGV2ZW50KSB3aWxsIHN0aWxsIGJlIGluY2x1ZGVkIGlmIHNob3dEZWxldGVkIGFuZCBzaW5nbGVFdmVudHMgYXJlIGJvdGggRmFsc2UuIElmIHNob3dEZWxldGVkIGFuZCBzaW5nbGVFdmVudHMgYXJlIGJvdGggVHJ1ZSwgb25seSBzaW5nbGUgaW5zdGFuY2VzIG9mIGRlbGV0ZWQgZXZlbnRzIChidXQgbm90IHRoZSB1bmRlcmx5aW5nIHJlY3VycmluZyBldmVudHMpIGFyZSByZXR1cm5lZC4gT3B0aW9uYWwuIFRoZSBkZWZhdWx0IGlzIEZhbHNlLlxuICAgICAgICAgICAgc2hvd0RlbGV0ZWQ6IHRydWUsXG4gICAgICAgICAgICAvLyBXaGV0aGVyIHRvIGV4cGFuZCByZWN1cnJpbmcgZXZlbnRzIGludG8gaW5zdGFuY2VzIGFuZCBvbmx5IHJldHVybiBzaW5nbGUgb25lLW9mZiBldmVudHMgYW5kIGluc3RhbmNlcyBvZiByZWN1cnJpbmcgZXZlbnRzLCBidXQgbm90IHRoZSB1bmRlcmx5aW5nIHJlY3VycmluZyBldmVudHMgdGhlbXNlbHZlcy4gT3B0aW9uYWwuIFRoZSBkZWZhdWx0IGlzIEZhbHNlLlxuICAgICAgICAgICAgc2luZ2xlRXZlbnRzOiB0cnVlLFxuICAgICAgICAgICAgc3luY1Rva2VuLFxuICAgICAgICAgIH07XG5cbiAgICAgICAgICBpZiAocGFnZVRva2VuKSB7XG4gICAgICAgICAgICB2YXJpYWJsZXMucGFnZVRva2VuID0gcGFnZVRva2VuO1xuICAgICAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlQ2FsZW5kYXIuZXZlbnRzLmxpc3QodmFyaWFibGVzKTtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKHJlcy5kYXRhKTtcblxuICAgICAgICAgICAgY29uc3QgeyBpdGVtcywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG5cbiAgICAgICAgICAgIGxvY2FsSXRlbXMgPSBpdGVtcyBhcyBFdmVudFJlc291cmNlVHlwZVtdO1xuICAgICAgICAgICAgcGFnZVRva2VuID0gbmV4dFBhZ2VUb2tlbjtcbiAgICAgICAgICAgIHN5bmNUb2tlbiA9IG5leHRTeW5jVG9rZW47XG5cbiAgICAgICAgICAgIGFkZGxvY2FsSXRlbXNUb0V2ZW50MlZlY3Rvck9iamVjdHMoXG4gICAgICAgICAgICAgIGxvY2FsSXRlbXMsXG4gICAgICAgICAgICAgIGV2ZW50MlZlY3Rvck9iamVjdHMsXG4gICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUNhbGVuZGFyVG9rZW5zSW5EYihcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICAgICAgbmV4dFBhZ2VUb2tlblxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGNvbnN0IGRlbGV0ZWRFdmVudHMgPSBsb2NhbEl0ZW1zLmZpbHRlcihcbiAgICAgICAgICAgICAgKGUpID0+IGU/LnN0YXR1cyA9PT0gc3RhdHVzXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICBpZiAoZGVsZXRlZEV2ZW50cz8uWzBdPy5pZCkge1xuICAgICAgICAgICAgICBjb25zdCByZXR1cm5lZERlbGV0ZWRFdmVudFZhbHVlcyA9IGF3YWl0IGRlbGV0ZUV2ZW50cyhcbiAgICAgICAgICAgICAgICBkZWxldGVkRXZlbnRzLFxuICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgY29uc3QgbWVldGluZ0lkc1RvRGVsZXRlID0gcmV0dXJuZWREZWxldGVkRXZlbnRWYWx1ZXNcbiAgICAgICAgICAgICAgICA/LmZpbHRlcigoZSkgPT4gISFlPy5tZWV0aW5nSWQpXG4gICAgICAgICAgICAgICAgPy5tYXAoKGUpID0+IGU/Lm1lZXRpbmdJZCk7XG5cbiAgICAgICAgICAgICAgaWYgKG1lZXRpbmdJZHNUb0RlbGV0ZSAmJiBtZWV0aW5nSWRzVG9EZWxldGU/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgICBhd2FpdCBkZWxldGVNZWV0aW5nQXNzaXN0c0dpdmVuSWRzKG1lZXRpbmdJZHNUb0RlbGV0ZSk7XG4gICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICBhd2FpdCBkZWxldGVDb25mZXJlbmNlcyhyZXR1cm5lZERlbGV0ZWRFdmVudFZhbHVlcyk7XG5cbiAgICAgICAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXG4gICAgICAgICAgICAgICAgZGVsZXRlQXR0ZW5kZWVzKGRlbGV0ZWRFdmVudHMsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgICAgIGRlbGV0ZVJlbWluZGVycyhkZWxldGVkRXZlbnRzLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgICBdO1xuXG4gICAgICAgICAgICAgIGF3YWl0IFByb21pc2UuYWxsKHByb21pc2VzKTtcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgY29uc3QgZXZlbnRzVG9VcHNlcnQyID0gbG9jYWxJdGVtcz8uZmlsdGVyKFxuICAgICAgICAgICAgICAoZSkgPT4gZT8uc3RhdHVzICE9PSBzdGF0dXNcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBpZiAoZXZlbnRzVG9VcHNlcnQyKSB7XG4gICAgICAgICAgICAgIGF3YWl0IHVwc2VydENvbmZlcmVuY2UyKGV2ZW50c1RvVXBzZXJ0MiwgdXNlcklkLCBjYWxlbmRhcklkKTtcbiAgICAgICAgICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzMihcbiAgICAgICAgICAgICAgICBldmVudHNUb1Vwc2VydDIsXG4gICAgICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgICAgICAgY29sb3JJdGVtXG4gICAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXG4gICAgICAgICAgICAgICAgZGVsZXRlUmVtaW5kZXJzKGV2ZW50c1RvVXBzZXJ0MiwgdXNlcklkLCBjYWxlbmRhcklkKSxcbiAgICAgICAgICAgICAgICBpbnNlcnRSZW1pbmRlcnNHaXZlbkV2ZW50UmVzb3VyY2UoXG4gICAgICAgICAgICAgICAgICBldmVudHNUb1Vwc2VydDIsXG4gICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgKSxcbiAgICAgICAgICAgICAgICB1cHNlcnRBdHRlbmRlZXMyKGV2ZW50c1RvVXBzZXJ0MiwgdXNlcklkLCBjYWxlbmRhcklkKSxcbiAgICAgICAgICAgICAgXTtcblxuICAgICAgICAgICAgICBhd2FpdCBQcm9taXNlLmFsbChwcm9taXNlcyk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICB9XG5cbiAgICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZTIoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCk7XG4gICAgICAgIGF3YWl0IHVwc2VydEV2ZW50czIoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCwgY29sb3JJdGVtKTtcblxuICAgICAgICBjb25zdCBwcm9taXNlcyA9IFtcbiAgICAgICAgICBkZWxldGVSZW1pbmRlcnMoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCksXG4gICAgICAgICAgaW5zZXJ0UmVtaW5kZXJzR2l2ZW5FdmVudFJlc291cmNlKGV2ZW50c1RvVXBzZXJ0LCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgIHVwc2VydEF0dGVuZGVlczIoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCksXG4gICAgICAgIF07XG5cbiAgICAgICAgYXdhaXQgUHJvbWlzZS5hbGwocHJvbWlzZXMpO1xuICAgICAgfVxuXG4gICAgICBhd2FpdCB1cGRhdGVHb29nbGVDYWxlbmRhclRva2Vuc0luRGIoXG4gICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgIG5leHRQYWdlVG9rZW5cbiAgICAgICk7XG4gICAgfVxuXG4gICAgYXdhaXQgYWRkVG9RdWV1ZUZvclZlY3RvclNlYXJjaCh1c2VySWQsIGV2ZW50MlZlY3Rvck9iamVjdHMpO1xuXG4gICAgcmV0dXJuIHRydWU7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBpbmNyZW1lbnRhbCBnb29nbGUgc3luYycpO1xuICAgIGlmIChlLmNvZGUgPT09IDQxMCkge1xuICAgICAgLy8gcmVzZXQgc3luY1xuICAgICAgYXdhaXQgcmVzZXRHb29nbGVTeW5jRm9yQ2FsZW5kYXIoY2FsZW5kYXJJZCwgdXNlcklkLCBjbGllbnRUeXBlKTtcbiAgICAgIHJldHVybiB0cnVlO1xuICAgIH1cbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRDYWxlbmRhcldlYmhvb2tCeUlkID0gYXN5bmMgKGNoYW5uZWxJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRDYWxlbmRhclB1c2hOb3RpZmljYXRpb25CeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBxdWVyeSBHZXRDYWxlbmRhclB1c2hOb3RpZmljYXRpb25CeUlkKCRpZDogU3RyaW5nISkge1xuICAgICAgQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb25fYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGV4cGlyYXRpb25cbiAgICAgICAgaWRcbiAgICAgICAgcmVzb3VyY2VJZFxuICAgICAgICByZXNvdXJjZVVyaVxuICAgICAgICB0b2tlblxuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlcklkXG4gICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZFxuICAgICAgfVxuICAgIH1cbiAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQ6IGNoYW5uZWxJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7IENhbGVuZGFyX1B1c2hfTm90aWZpY2F0aW9uX2J5X3BrOiBDYWxlbmRhcldlYmhvb2tUeXBlIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gZ2V0Q2FsZW5kYXJXZWJob29rJyk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb25fYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXRDYWxlbmRhcldlYmhvb2snKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNvbnZlcnRUZXh0VG9WZWN0b3JTcGFjZTIgPSBhc3luYyAoXG4gIHRleHQ6IHN0cmluZ1xuKTogUHJvbWlzZTxudW1iZXJbXT4gPT4ge1xuICB0cnkge1xuICAgIGlmICghdGV4dCB8fCB0ZXh0LnRyaW0oKSA9PT0gJycpIHtcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICBjb25zdCBlbWJlZGRpbmdSZXNwb25zZSA9IGF3YWl0IG9wZW5haS5lbWJlZGRpbmdzLmNyZWF0ZSh7XG4gICAgICBtb2RlbDogJ3RleHQtZW1iZWRkaW5nLWFkYS0wMDInLFxuICAgICAgaW5wdXQ6IHRleHQucmVwbGFjZSgvXFxuL2csICcgJyksXG4gICAgfSk7XG5cbiAgICBjb25zdCB2ZWN0b3IgPSBlbWJlZGRpbmdSZXNwb25zZS5kYXRhWzBdLmVtYmVkZGluZztcblxuICAgIHJldHVybiB2ZWN0b3I7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjb252ZXJ0VGV4dFRvVmVjdG9yU3BhY2UnKTtcbiAgICB0aHJvdyBlO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlRG9jSW5TZWFyY2gzID0gYXN5bmMgKGlkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjbGllbnQgPSBhd2FpdCBnZXRTZWFyY2hDbGllbnQoKTtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGNsaWVudC5kZWxldGUoe1xuICAgICAgaWQsXG4gICAgICBpbmRleDogc2VhcmNoSW5kZXgsXG4gICAgfSk7XG4gICAgY29uc29sZS5sb2coJ0RlbGV0aW5nIGRvY3VtZW50IGluIHNlYXJjaDonKTtcbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZS5ib2R5KTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBkb2MnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldFNlYXJjaENsaWVudCA9IGFzeW5jICgpID0+IHtcbiAgdHJ5IHtcbiAgICByZXR1cm4gbmV3IENsaWVudCh7XG4gICAgICBub2RlOiBwcm9jZXNzLmVudi5PUEVOU0VBUkNIX0VORFBPSU5ULFxuICAgICAgYXV0aDoge1xuICAgICAgICB1c2VybmFtZTogcHJvY2Vzcy5lbnYuT1BFTlNFQVJDSF9VU0VSTkFNRSxcbiAgICAgICAgcGFzc3dvcmQ6IHByb2Nlc3MuZW52Lk9QRU5TRUFSQ0hfUEFTU1dPUkQsXG4gICAgICB9LFxuICAgIH0pO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNyZWRlbnRpYWxzIGZyb20gZ2V0U2VhcmNoQ2xpZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBzZWFyY2hEYXRhMyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHNlYXJjaFZlY3RvcjogbnVtYmVyW11cbik6IFByb21pc2U8ZXNSZXNwb25zZUJvZHk+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjbGllbnQgPSBhd2FpdCBnZXRTZWFyY2hDbGllbnQoKTtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGNsaWVudC5zZWFyY2goe1xuICAgICAgaW5kZXg6IHNlYXJjaEluZGV4LFxuICAgICAgYm9keToge1xuICAgICAgICBzaXplOiB2ZWN0b3JEaW1lbnNpb25zLFxuICAgICAgICBxdWVyeToge1xuICAgICAgICAgIHNjcmlwdF9zY29yZToge1xuICAgICAgICAgICAgcXVlcnk6IHtcbiAgICAgICAgICAgICAgYm9vbDoge1xuICAgICAgICAgICAgICAgIGZpbHRlcjoge1xuICAgICAgICAgICAgICAgICAgdGVybToge1xuICAgICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgc2NyaXB0OiB7XG4gICAgICAgICAgICAgIGxhbmc6ICdrbm4nLFxuICAgICAgICAgICAgICBzb3VyY2U6ICdrbm5fc2NvcmUnLFxuICAgICAgICAgICAgICBwYXJhbXM6IHtcbiAgICAgICAgICAgICAgICBmaWVsZDogZXZlbnRWZWN0b3JOYW1lLFxuICAgICAgICAgICAgICAgIHF1ZXJ5X3ZhbHVlOiBzZWFyY2hWZWN0b3IsXG4gICAgICAgICAgICAgICAgc3BhY2VfdHlwZTogJ2Nvc2luZXNpbWlsJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgICAgbWluX3Njb3JlOiAxLjIsXG4gICAgICB9LFxuICAgIH0pO1xuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHNlYXJjaCBkYXRhIGluIHNlYXJjaCBlbmdpbmUnKTtcbiAgICByZXR1cm4gcmVzcG9uc2UuYm9keTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHNlYXJjaCBkYXRhJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVDYWxlbmRhcldlYmhvb2tCeUlkID0gYXN5bmMgKGNoYW5uZWxJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdEZWxldGVDYWxlbmRhclB1c2hOb3RpZmljYXRpb25CeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIG11dGF0aW9uIERlbGV0ZUNhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbkJ5SWQoJGlkOiBTdHJpbmchKSB7XG4gICAgICAgIGRlbGV0ZV9DYWxlbmRhcl9QdXNoX05vdGlmaWNhdGlvbl9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgZXhwaXJhdGlvblxuICAgICAgICAgIGlkXG4gICAgICAgICAgcmVzb3VyY2VJZFxuICAgICAgICAgIHJlc291cmNlVXJpXG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICB1c2VySWRcbiAgICAgICAgfVxuICAgICAgfVxuICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkOiBjaGFubmVsSWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YTogeyBkZWxldGVfQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb25fYnlfcGs6IENhbGVuZGFyV2ViaG9va1R5cGUgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSAgZGVsZXRlQ2FsZW5kYXJXZWJob29rQnlJZCcpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGVsZXRlIGNhbGVuZGFyIHdlYmhvb2sgYnkgaWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHN0b3BDYWxlbmRhcldhdGNoID0gYXN5bmMgKGlkOiBzdHJpbmcsIHJlc291cmNlSWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvdC5wb3N0KGdvb2dsZUNhbGVuZGFyU3RvcFdhdGNoVXJsLCB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgICAganNvbjoge1xuICAgICAgICBpZCxcbiAgICAgICAgcmVzb3VyY2VJZCxcbiAgICAgIH0sXG4gICAgfSk7XG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBpbnNpZGUgc3RvcENhbGVuZGFyV2F0Y2gnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHN0b3AgY2FsZW5kYXIgd2F0Y2gnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldENhbGVuZGFyV2ViaG9va0J5Q2FsZW5kYXJJZCA9IGFzeW5jIChjYWxlbmRhcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldENhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbkJ5Q2FsZW5kYXJJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBHZXRDYWxlbmRhclB1c2hOb3RpZmljYXRpb25CeUNhbGVuZGFySWQoJGNhbGVuZGFySWQ6IFN0cmluZyEpIHtcbiAgICAgICAgQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb24od2hlcmU6IHtjYWxlbmRhcklkOiB7X2VxOiAkY2FsZW5kYXJJZH19LCBsaW1pdDogMSkge1xuICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgIGV4cGlyYXRpb25cbiAgICAgICAgICBpZFxuICAgICAgICAgIHJlc291cmNlSWRcbiAgICAgICAgICByZXNvdXJjZVVyaVxuICAgICAgICAgIHRva2VuXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgdXNlcklkXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgY2FsZW5kYXJJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb246IENhbGVuZGFyV2ViaG9va1R5cGVbXSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGdldENhbGVuZGFyV2ViaG9vaycpO1xuICAgIHJldHVybiByZXM/LmRhdGE/LkNhbGVuZGFyX1B1c2hfTm90aWZpY2F0aW9uPy5bMF07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXRDYWxlbmRhcldlYmhvb2tCeUNhbGVuZGFySWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydEV2ZW50czIgPSBhc3luYyAoXG4gIGV2ZW50czogRXZlbnRSZXNvdXJjZVR5cGVbXSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgY29sb3JJdGVtPzogY29sb3JUeXBlUmVzcG9uc2VcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKGV2ZW50cywgJyBldmVudHMgaW5zaWRlIHVwc2VydEV2ZW50cycpO1xuICAgIGNvbnNvbGUubG9nKGNvbG9ySXRlbSwgJyBjb2xvckl0ZW0gaW5zaWRlIHVwc2VydEV2ZW50cycpO1xuICAgIGlmICghZXZlbnRzPy5bMF0/LmlkKSByZXR1cm4gbnVsbDtcblxuICAgIC8vIGZvcm1hdCBldmVudHMgZm9yIGluc2VydFxuICAgIGNvbnN0IGZvcm1hdHRlZEV2ZW50cyA9IGV2ZW50c1xuICAgICAgLmZpbHRlcigoZSkgPT4gISFlPy5pZClcbiAgICAgID8uZmlsdGVyKChlKSA9PiAhIWU/LnN0YXJ0Py50aW1lWm9uZSB8fCAhIWU/LmVuZD8udGltZVpvbmUpXG4gICAgICAubWFwKChldmVudCkgPT4ge1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIGlkOiBgJHtldmVudD8uaWR9IyR7Y2FsZW5kYXJJZH1gLFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICBzdGF0dXM6IGV2ZW50Py5zdGF0dXMsXG4gICAgICAgICAgaHRtbExpbms6IGV2ZW50Py5odG1sTGluayxcbiAgICAgICAgICBjcmVhdGVkRGF0ZTogZXZlbnQ/LmNyZWF0ZWQsXG4gICAgICAgICAgdXBkYXRlZEF0OiBldmVudD8udXBkYXRlZCxcbiAgICAgICAgICBzdW1tYXJ5OiBldmVudD8uc3VtbWFyeSxcbiAgICAgICAgICBub3RlczogZXZlbnQ/LmRlc2NyaXB0aW9uLFxuICAgICAgICAgIGxvY2F0aW9uOiB7XG4gICAgICAgICAgICB0aXRsZTogZXZlbnQ/LmxvY2F0aW9uLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgY29sb3JJZDogZXZlbnQ/LmNvbG9ySWQsXG4gICAgICAgICAgY3JlYXRvcjogZXZlbnQ/LmNyZWF0b3IsXG4gICAgICAgICAgb3JnYW5pemVyOiBldmVudD8ub3JnYW5pemVyLFxuICAgICAgICAgIHN0YXJ0RGF0ZTpcbiAgICAgICAgICAgIGV2ZW50Py5zdGFydD8uZGF0ZVRpbWUgfHxcbiAgICAgICAgICAgIGRheWpzKGV2ZW50Py5zdGFydD8uZGF0ZSlcbiAgICAgICAgICAgICAgLnR6KGV2ZW50Py5zdGFydD8udGltZVpvbmUgfHwgZGF5anMudHouZ3Vlc3MoKSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgIGVuZERhdGU6XG4gICAgICAgICAgICBldmVudD8uZW5kPy5kYXRlVGltZSB8fFxuICAgICAgICAgICAgZGF5anMoZXZlbnQ/LmVuZD8uZGF0ZSlcbiAgICAgICAgICAgICAgLnR6KGV2ZW50Py5lbmQ/LnRpbWVab25lIHx8IGRheWpzLnR6Lmd1ZXNzKCksIHRydWUpXG4gICAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICBhbGxEYXk6IGV2ZW50Py5zdGFydD8uZGF0ZSA/IHRydWUgOiBmYWxzZSxcbiAgICAgICAgICB0aW1lem9uZTogZXZlbnQ/LnN0YXJ0Py50aW1lWm9uZSB8fCBldmVudD8uZW5kPy50aW1lWm9uZSxcbiAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWQ6IGV2ZW50Py5lbmRUaW1lVW5zcGVjaWZpZWQsXG4gICAgICAgICAgcmVjdXJyZW5jZTogZXZlbnQ/LnJlY3VycmVuY2UsXG4gICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZDogZXZlbnQ/LnJlY3VycmluZ0V2ZW50SWQsXG4gICAgICAgICAgb3JpZ2luYWxTdGFydERhdGU6XG4gICAgICAgICAgICBldmVudD8ub3JpZ2luYWxTdGFydFRpbWU/LmRhdGVUaW1lIHx8XG4gICAgICAgICAgICBldmVudD8ub3JpZ2luYWxTdGFydFRpbWU/LmRhdGUsXG4gICAgICAgICAgb3JpZ2luYWxBbGxEYXk6IGV2ZW50Py5vcmlnaW5hbFN0YXJ0VGltZT8uZGF0ZSA/IHRydWUgOiBmYWxzZSxcbiAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lOiBldmVudD8ub3JpZ2luYWxTdGFydFRpbWU/LnRpbWVab25lLFxuICAgICAgICAgIHRyYW5zcGFyZW5jeTogZXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgICB2aXNpYmlsaXR5OiBldmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICBpQ2FsVUlEOiBldmVudD8uaUNhbFVJRCxcbiAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkOiBldmVudD8uYXR0ZW5kZWVzT21pdHRlZCxcbiAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXM6XG4gICAgICAgICAgICBldmVudD8uZXh0ZW5kZWRQcm9wZXJ0aWVzPy5wcml2YXRlIHx8XG4gICAgICAgICAgICBldmVudD8uZXh0ZW5kZWRQcm9wZXJ0aWVzPy5zaGFyZWRcbiAgICAgICAgICAgICAgPyB7XG4gICAgICAgICAgICAgICAgICBwcml2YXRlOiBldmVudD8uZXh0ZW5kZWRQcm9wZXJ0aWVzPy5wcml2YXRlICYmIHtcbiAgICAgICAgICAgICAgICAgICAga2V5czogT2JqZWN0LmtleXMoZXZlbnQ/LmV4dGVuZGVkUHJvcGVydGllcz8ucHJpdmF0ZSksXG4gICAgICAgICAgICAgICAgICAgIHZhbHVlczogT2JqZWN0LnZhbHVlcyhldmVudD8uZXh0ZW5kZWRQcm9wZXJ0aWVzPy5wcml2YXRlKSxcbiAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICBzaGFyZWQ6IGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXM/LnNoYXJlZCAmJiB7XG4gICAgICAgICAgICAgICAgICAgIGtleXM6IE9iamVjdC5rZXlzKGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXM/LnNoYXJlZCksXG4gICAgICAgICAgICAgICAgICAgIHZhbHVlczogT2JqZWN0LnZhbHVlcyhldmVudD8uZXh0ZW5kZWRQcm9wZXJ0aWVzPy5zaGFyZWQpLFxuICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIDogbnVsbCxcbiAgICAgICAgICBoYW5nb3V0TGluazogZXZlbnQ/LmhhbmdvdXRMaW5rLFxuICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICBndWVzdHNDYW5Nb2RpZnk6IGV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IGV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgICBzb3VyY2U6IGV2ZW50Py5zb3VyY2UsXG4gICAgICAgICAgYXR0YWNobWVudHM6IGV2ZW50Py5hdHRhY2htZW50cyxcbiAgICAgICAgICBldmVudFR5cGU6IGV2ZW50Py5ldmVudFR5cGUsXG4gICAgICAgICAgcHJpdmF0ZUNvcHk6IGV2ZW50Py5wcml2YXRlQ29weSxcbiAgICAgICAgICBsb2NrZWQ6IGV2ZW50Py5sb2NrZWQsXG4gICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3I6IGNvbG9ySXRlbT8uZXZlbnQ/LltgJHtldmVudD8uY29sb3JJZH1gXT8uYmFja2dyb3VuZCxcbiAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3I6IGNvbG9ySXRlbT8uZXZlbnQ/LltgJHtldmVudD8uY29sb3JJZH1gXT8uZm9yZWdyb3VuZCxcbiAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zOiBldmVudD8ucmVtaW5kZXJzPy51c2VEZWZhdWx0LFxuICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50Py5pZCxcbiAgICAgICAgICBjb25mZXJlbmNlSWQ6IGV2ZW50Py5jb25mZXJlbmNlRGF0YT8uY29uZmVyZW5jZUlkLFxuICAgICAgICB9O1xuICAgICAgfSk7XG5cbiAgICBpZiAoIShmb3JtYXR0ZWRFdmVudHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICByZXR1cm47XG4gICAgfVxuICAgIC8qXG4gICAgICAgICAgZHluYW1pY2FsbHkgZ2VuZXJhdGUgdXBzZXJ0IHF1ZXJ5IGJhc2VkIG9uIHRoZSBudW1iZXIgb2YgY29sdW1uc1xuICAgICAgICAgIGFuZCBzZXQgdGhlIHVwZGF0ZV9jb2x1bW5zIHRvIHRoZSBjb2x1bW5zIHRoYXQgYXJlIG5vdCB1bmRlZmluZWRcbiAgICAgICAgKi9cbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0luc2VydEV2ZW50JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIG11dGF0aW9uIEluc2VydEV2ZW50KCRldmVudHM6IFtFdmVudF9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgaW5zZXJ0X0V2ZW50KFxuICAgICAgICAgICAgb2JqZWN0czogJGV2ZW50cyxcbiAgICAgICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgICAgICAgY29uc3RyYWludDogRXZlbnRfcGtleSxcbiAgICAgICAgICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICAgc3RhcnREYXRlLFxuICAgICAgICAgICAgICAgICAgZW5kRGF0ZSxcbiAgICAgICAgICAgICAgICAgIGFsbERheSxcbiAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2UsXG4gICAgICAgICAgICAgICAgICBsb2NhdGlvbixcbiAgICAgICAgICAgICAgICAgIG5vdGVzLFxuICAgICAgICAgICAgICAgICAgYXR0YWNobWVudHMsXG4gICAgICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWQsXG4gICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAgICAgICAgICAgICAgIG9yaWdpbmFsVGltZXpvbmUsXG4gICAgICAgICAgICAgICAgICBvcmlnaW5hbEFsbERheSxcbiAgICAgICAgICAgICAgICAgIHN0YXR1cyxcbiAgICAgICAgICAgICAgICAgIHN1bW1hcnksXG4gICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5LFxuICAgICAgICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgIGh0bWxMaW5rLFxuICAgICAgICAgICAgICAgICAgY29sb3JJZCxcbiAgICAgICAgICAgICAgICAgIGNyZWF0b3IsXG4gICAgICAgICAgICAgICAgICBvcmdhbml6ZXIsXG4gICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWQsXG4gICAgICAgICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXMsXG4gICAgICAgICAgICAgICAgICBoYW5nb3V0TGluayxcbiAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgICAgICAgIGxvY2tlZCxcbiAgICAgICAgICAgICAgICAgIHNvdXJjZSxcbiAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZSxcbiAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5LFxuICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yLFxuICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yLFxuICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICAgICAgICAgICAgaUNhbFVJRCxcbiAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zLFxuICAgICAgICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VJZCxcbiAgICAgICAgICAgICAgICBdXG4gICAgICAgICAgICB9KXtcbiAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGV2ZW50czogZm9ybWF0dGVkRXZlbnRzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIHVwc2VydEV2ZW50cycpO1xuICAgIHJlc3BvbnNlPy5lcnJvcnM/LmZvckVhY2goKGUpID0+IGNvbnNvbGUubG9nKGUpKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwc2VydEV2ZW50cycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBzZXJ0Q29uZmVyZW5jZTIgPSBhc3luYyAoXG4gIGV2ZW50czogRXZlbnRSZXNvdXJjZVR5cGVbXSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZm9ybWF0dGVkQ29uZmVyZW5jZTogQ29uZmVyZW5jZVR5cGVbXSA9IGV2ZW50cy5tYXAoKGUpID0+IHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIGlkOiBlPy5jb25mZXJlbmNlRGF0YT8uY29uZmVyZW5jZUlkLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIHR5cGU6IGU/LmNvbmZlcmVuY2VEYXRhPy5jb25mZXJlbmNlU29sdXRpb24/LmtleT8udHlwZSxcbiAgICAgICAgc3RhdHVzOiBlPy5jb25mZXJlbmNlRGF0YT8uY3JlYXRlUmVxdWVzdD8uc3RhdHVzPy5zdGF0dXNDb2RlLFxuICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICBpY29uVXJpOiBlPy5jb25mZXJlbmNlRGF0YT8uY29uZmVyZW5jZVNvbHV0aW9uPy5pY29uVXJpLFxuICAgICAgICBuYW1lOiBlPy5jb25mZXJlbmNlRGF0YT8uY29uZmVyZW5jZVNvbHV0aW9uPy5uYW1lLFxuICAgICAgICBub3RlczogZT8uY29uZmVyZW5jZURhdGE/Lm5vdGVzLFxuICAgICAgICBlbnRyeVBvaW50czogZT8uY29uZmVyZW5jZURhdGE/LmVudHJ5UG9pbnRzLFxuICAgICAgICBrZXk6IGU/LmNvbmZlcmVuY2VEYXRhPy5jb25mZXJlbmNlU29sdXRpb24/LmtleT8udHlwZSxcbiAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgIGFwcDogZ29vZ2xlTWVldFJlc291cmNlLFxuICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudXRjKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgaXNIb3N0OiBmYWxzZSxcbiAgICAgIH07XG4gICAgfSk7XG4gICAgaWYgKCEoZm9ybWF0dGVkQ29uZmVyZW5jZT8uZmlsdGVyKChjKSA9PiAhIWM/LmlkKT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICAvKlxuICAgICAgICBkeW5hbWljYWxseSBnZW5lcmF0ZSB1cHNlcnQgcXVlcnkgYmFzZWQgb24gdGhlIG51bWJlciBvZiBjb2x1bW5zXG4gICAgICAgIGFuZCBzZXQgdGhlIHVwZGF0ZV9jb2x1bW5zIHRvIHRoZSBjb2x1bW5zIHRoYXQgYXJlIG5vdCB1bmRlZmluZWRcbiAgICAgICAgKi9cblxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0Q29uZmVyZW5jZSc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBtdXRhdGlvbiBJbnNlcnRDb25mZXJlbmNlKCRjb25mZXJlbmNlczogW0NvbmZlcmVuY2VfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgICAgICBpbnNlcnRfQ29uZmVyZW5jZShcbiAgICAgICAgICAgICAgICBvYmplY3RzOiAkY29uZmVyZW5jZXMsXG4gICAgICAgICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3RyYWludDogQ29uZmVyZW5jZV9wa2V5LFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICAgICAgIHJlcXVlc3RJZCxcbiAgICAgICAgICAgICAgICAgICAgICB0eXBlLFxuICAgICAgICAgICAgICAgICAgICAgIHN0YXR1cyxcbiAgICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICAgICAgICAgICAgICAgIGljb25VcmksXG4gICAgICAgICAgICAgICAgICAgICAgbmFtZSxcbiAgICAgICAgICAgICAgICAgICAgICBub3RlcyxcbiAgICAgICAgICAgICAgICAgICAgICBlbnRyeVBvaW50cyxcbiAgICAgICAgICAgICAgICAgICAgICBwYXJhbWV0ZXJzLFxuICAgICAgICAgICAgICAgICAgICAgIGFwcCxcbiAgICAgICAgICAgICAgICAgICAgICBrZXksXG4gICAgICAgICAgICAgICAgICAgICAgZGVsZXRlZCxcbiAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICAgICAgICAgIF1cbiAgICAgICAgICAgICAgICB9KSB7XG4gICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICB9XG4gICAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGNvbmZlcmVuY2VzOiBmb3JtYXR0ZWRDb25mZXJlbmNlLFxuICAgIH07XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIHVwc2VydENvbmZlcmVuY2UnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwc2VydCBjb25mZXJlbmNlIGRhdGEnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGluc2VydENhbGVuZGFyV2ViaG9vayA9IGFzeW5jICh3ZWJob29rOiBDYWxlbmRhcldlYmhvb2tUeXBlKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdJbnNlcnRDYWxlbmRhclB1c2hOb3RpZmljYXRpb24nO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYG11dGF0aW9uIEluc2VydENhbGVuZGFyUHVzaE5vdGlmaWNhdGlvbigkd2ViaG9vazogQ2FsZW5kYXJfUHVzaF9Ob3RpZmljYXRpb25faW5zZXJ0X2lucHV0ISkge1xuICAgICAgaW5zZXJ0X0NhbGVuZGFyX1B1c2hfTm90aWZpY2F0aW9uX29uZShvYmplY3Q6ICR3ZWJob29rLFxuICAgICAgICBvbl9jb25mbGljdDoge1xuICAgICAgICAgIGNvbnN0cmFpbnQ6IENhbGVuZGFyX1B1c2hfTm90aWZpY2F0aW9uX2NhbGVuZGFySWRfa2V5LFxuICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgICBpZCxcbiAgICAgICAgICAgIGV4cGlyYXRpb24sXG4gICAgICAgICAgICByZXNvdXJjZUlkLFxuICAgICAgICAgICAgcmVzb3VyY2VVcmksXG4gICAgICAgICAgICB0b2tlbixcbiAgICAgICAgICAgIHVwZGF0ZWRBdCxcbiAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgICBdfSkge1xuICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGV4cGlyYXRpb25cbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICByZXNvdXJjZUlkXG4gICAgICAgICAgICByZXNvdXJjZVVyaVxuICAgICAgICAgICAgdG9rZW5cbiAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWRcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgd2ViaG9vayxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IHtcbiAgICAgIGRhdGE6IHsgaW5zZXJ0X0NhbGVuZGFyX1B1c2hfTm90aWZpY2F0aW9uX29uZTogQ2FsZW5kYXJXZWJob29rVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHJlc3BvbnNlIGFmdGVyIHVwc2VydGluZyBjYWxlbmRhciB3ZWJob29rJyk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2U/LmRhdGE/Lmluc2VydF9DYWxlbmRhcl9QdXNoX05vdGlmaWNhdGlvbl9vbmU7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cHNlcnRDYWxlbmRhcldlYmhvb2snKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydEF0dGVuZGVlczIgPSBhc3luYyAoXG4gIGV2ZW50czogRXZlbnRSZXNvdXJjZVR5cGVbXSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgYXR0ZW5kZWVzOiBBdHRlbmRlZVR5cGVbXSA9IFtdO1xuICAgIGV2ZW50c1xuICAgICAgLmZpbHRlcigoZSkgPT4gISFlPy5hdHRlbmRlZXM/LlswXT8uaWQpXG4gICAgICAuZm9yRWFjaCgoZSkgPT4ge1xuICAgICAgICBlPy5hdHRlbmRlZXM/LmZvckVhY2goKGEpID0+IHtcbiAgICAgICAgICBhdHRlbmRlZXMucHVzaCh7XG4gICAgICAgICAgICBpZDogYT8uaWQsXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBuYW1lOiBhPy5kaXNwbGF5TmFtZSxcbiAgICAgICAgICAgIGVtYWlsczogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgcHJpbWFyeTogZmFsc2UsXG4gICAgICAgICAgICAgICAgdmFsdWU6IGE/LmVtYWlsLFxuICAgICAgICAgICAgICAgIGRpc3BsYXlOYW1lOiBhPy5kaXNwbGF5TmFtZSxcbiAgICAgICAgICAgICAgICB0eXBlOiAnJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgICBldmVudElkOiBgJHtlPy5pZH0jJHtjYWxlbmRhcklkfWAsXG4gICAgICAgICAgICBhZGRpdGlvbmFsR3Vlc3RzOiBhPy5hZGRpdGlvbmFsR3Vlc3RzLFxuICAgICAgICAgICAgY29tbWVudDogYT8uY29tbWVudCxcbiAgICAgICAgICAgIHJlc3BvbnNlU3RhdHVzOiBhPy5yZXNwb25zZVN0YXR1cyxcbiAgICAgICAgICAgIG9wdGlvbmFsOiBhPy5vcHRpb25hbCxcbiAgICAgICAgICAgIHJlc291cmNlOiBhPy5yZXNvdXJjZSxcbiAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnV0YygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIH0pO1xuICAgICAgICB9KTtcbiAgICAgIH0pO1xuXG4gICAgaWYgKCFhdHRlbmRlZXM/LlswXT8uZW1haWxzPy5bMF0pIHtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0luc2VydEF0dGVuZGVlJztcblxuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICBtdXRhdGlvbiBJbnNlcnRBdHRlbmRlZSgkYXR0ZW5kZWVzOiBbQXR0ZW5kZWVfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgICAgICBpbnNlcnRfQXR0ZW5kZWUoXG4gICAgICAgICAgICAgICAgb2JqZWN0czogJGF0dGVuZGVlcyxcbiAgICAgICAgICAgICAgICBvbl9jb25mbGljdDoge1xuICAgICAgICAgICAgICAgICAgICBjb25zdHJhaW50OiBBdHRlbmRlZV9wa2V5LFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICAgICAgIG5hbWUsXG4gICAgICAgICAgICAgICAgICAgICAgY29udGFjdElkLFxuICAgICAgICAgICAgICAgICAgICAgIGVtYWlscyxcbiAgICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnMsXG4gICAgICAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXMsXG4gICAgICAgICAgICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgICAgICBhZGRpdGlvbmFsR3Vlc3RzLFxuICAgICAgICAgICAgICAgICAgICAgIG9wdGlvbmFsLFxuICAgICAgICAgICAgICAgICAgICAgIHJlc291cmNlLFxuICAgICAgICAgICAgICAgICAgICAgIHJlc3BvbnNlU3RhdHVzLFxuICAgICAgICAgICAgICAgICAgICAgIGNvbW1lbnQsXG4gICAgICAgICAgICAgICAgICAgICAgZGVsZXRlZCxcbiAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICAgICAgICAgIF1cbiAgICAgICAgICAgICAgICB9KXtcbiAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH1cbiAgICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBhdHRlbmRlZXMsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIHVwc2VydEF0dGVuZGVlcycpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBzZXJ0QXR0ZW5kZWVzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbiA9IGFzeW5jIChcbiAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkOiBzdHJpbmcsXG4gIHN5bmNFbmFibGVkPzogYm9vbGVhblxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICd1cGRhdGVDYWxlbmRhckludGVncmF0aW9uJztcbiAgICBjb25zdCBxdWVyeSA9IGBtdXRhdGlvbiB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKCRpZDogdXVpZCEsICR7c3luY0VuYWJsZWQgIT09IHVuZGVmaW5lZCA/ICcgJHN5bmNFbmFibGVkOiBCb29sZWFuLCcgOiAnJ30pIHtcbiAgICAgICAgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDogeyR7c3luY0VuYWJsZWQgIT09IHVuZGVmaW5lZCA/ICcgc3luY0VuYWJsZWQ6ICRzeW5jRW5hYmxlZCwnIDogJyd9IH0pIHtcbiAgICAgICAgICBpZFxuICAgICAgICAgIG5hbWVcbiAgICAgICAgICByZWZyZXNoVG9rZW5cbiAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICB1c2VySWRcbiAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICBlbmFibGVkXG4gICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgY2xpZW50VHlwZVxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBsZXQgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICBpZDogY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgIH07XG5cbiAgICBpZiAoc3luY0VuYWJsZWQgPT09IGZhbHNlKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7IC4uLnZhcmlhYmxlcywgc3luY0VuYWJsZWQgfTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgdGhpcyBpcyByZXNwb25zZSBpbiB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbicpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIGdvb2dsZSBpbnRlZ3JhdGlvbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlR29vZ2xlQ2FsZW5kYXJUb2tlbnNJbkRiID0gYXN5bmMgKFxuICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gIHN5bmNUb2tlbj86IHN0cmluZyxcbiAgcGFnZVRva2VuPzogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ3VwZGF0ZUNhbGVuZGFyJztcbiAgICBjb25zdCBxdWVyeSA9IGBtdXRhdGlvbiB1cGRhdGVDYWxlbmRhcigkaWQ6IFN0cmluZyEsICR7c3luY1Rva2VuICE9PSB1bmRlZmluZWQgPyAnICRzeW5jVG9rZW46IFN0cmluZywnIDogJyd9ICR7cGFnZVRva2VuICE9PSB1bmRlZmluZWQgPyAnICRwYWdlVG9rZW46IFN0cmluZywnIDogJyd9KSB7XG4gICAgICAgIHVwZGF0ZV9DYWxlbmRhcl9ieV9wayhwa19jb2x1bW5zOiB7aWQ6ICRpZH0sIF9zZXQ6IHske3BhZ2VUb2tlbiAhPT0gdW5kZWZpbmVkID8gJyBwYWdlVG9rZW4gOiAkcGFnZVRva2VuLCcgOiAnJ30gJHtzeW5jVG9rZW4gIT09IHVuZGVmaW5lZCA/ICcgc3luY1Rva2VuOiAkc3luY1Rva2VuLCcgOiAnJ30gfSkge1xuICAgICAgICAgIGlkXG4gICAgICAgICAgcGFnZVRva2VuXG4gICAgICAgICAgc3luY1Rva2VuXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGxldCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgIGlkOiBjYWxlbmRhcklkLFxuICAgIH07XG5cbiAgICBpZiAoc3luY1Rva2VuPy5sZW5ndGggPiAwKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7IC4uLnZhcmlhYmxlcywgc3luY1Rva2VuIH07XG4gICAgfVxuXG4gICAgaWYgKHBhZ2VUb2tlbj8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFyaWFibGVzID0geyAuLi52YXJpYWJsZXMsIHBhZ2VUb2tlbiB9O1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIHVwZGF0ZUdvb2dsZUludGVncmF0aW9uJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgZ29vZ2xlIGludGVncmF0aW9uJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRDYWxlbmRhcldpdGhJZCA9IGFzeW5jIChjYWxlbmRhcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBnZXQgQ2FsZW5kYXJcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldENhbGVuZGFyJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICBxdWVyeSBnZXRDYWxlbmRhcigkaWQ6IFN0cmluZyEpIHtcbiAgICAgIENhbGVuZGFyX2J5X3BrKGlkOiAkaWQpIHtcbiAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgICBhY2NvdW50XG4gICAgICAgIGNvbG9ySWRcbiAgICAgICAgaWRcbiAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgfVxuICAgIH1cbiAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZDogY2FsZW5kYXJJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXJfYnlfcGs6IENhbGVuZGFyVHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGdldENhbGVuZGFyRm9yRXZlbnQnKTtcbiAgICByZXR1cm4gcmVzPy5kYXRhPy5DYWxlbmRhcl9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZ2V0Q2FsZW5kYXJGb3JFdmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcmVxdWVzdENhbGVuZGFyV2F0Y2ggPSBhc3luYyAoXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgY2hhbm5lbElkOiBzdHJpbmcsXG4gIHRva2VuOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IHJlc291cmNlIH0gPSBhd2FpdCBnZXRDYWxlbmRhcldpdGhJZChjYWxlbmRhcklkKTtcbiAgICBjb25zdCBjYWxlbmRhckludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbih1c2VySWQsIHJlc291cmNlKTtcbiAgICBjb25zdCBjbGllbnRUeXBlID0gY2FsZW5kYXJJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZTtcblxuICAgIGNvbnN0IGF1dGhUb2tlbiA9IGF3YWl0IGdldEdvb2dsZUFQSVRva2VuKFxuICAgICAgdXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJSZXNvdXJjZSxcbiAgICAgIGNsaWVudFR5cGVcbiAgICApO1xuXG4gICAgY29uc3QgZ29vZ2xlQ2FsZW5kYXIgPSBnb29nbGUuY2FsZW5kYXIoe1xuICAgICAgdmVyc2lvbjogJ3YzJyxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke2F1dGhUb2tlbn1gLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnN0IHJlcUJvZHk6IENhbGVuZGFyV2F0Y2hSZXF1ZXN0UmVzb3VyY2VUeXBlID0ge1xuICAgICAgaWQ6IGNoYW5uZWxJZCxcbiAgICAgIHRva2VuLFxuICAgICAgdHlwZTogJ3dlYmhvb2snLFxuICAgICAgYWRkcmVzczogc2VsZkdvb2dsZUNhbGVuZGFyV2ViaG9va1B1YmxpY1VybCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlQ2FsZW5kYXIuZXZlbnRzLndhdGNoKHtcbiAgICAgIGNhbGVuZGFySWQsXG4gICAgICBzaW5nbGVFdmVudHM6IHRydWUsXG4gICAgICByZXF1ZXN0Qm9keTogcmVxQm9keSxcbiAgICB9KTtcblxuICAgIGNvbnN0IHJlc3BvbnNlID0gcmVzPy5kYXRhO1xuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHJlc3BvbnNlIGluc2lkZSByZXF1ZXN0Q2FsZW5kYXJXYXRjaCcpO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlcXVlc3QgY2FsZW5kYXIgd2F0Y2gnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RDYWxlbmRhcnNGb3JVc2VyID0gYXN5bmMgKHVzZXJJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdMaXN0Q2FsZW5kYXJzRm9yVXNlcic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBMaXN0Q2FsZW5kYXJzRm9yVXNlcigkdXNlcklkOiB1dWlkISkge1xuICAgICAgICBDYWxlbmRhcih3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgICAgICAgaWRcbiAgICAgICAgICB0aXRsZVxuICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICBhY2NvdW50XG4gICAgICAgICAgYWNjZXNzTGV2ZWxcbiAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgIHN5bmNUb2tlblxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IENhbGVuZGFyOiBDYWxlbmRhclR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgcmV0dXJuIHJlcy5kYXRhLkNhbGVuZGFyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBsaXN0IGNhbGVuZGFycyBmb3IgdXNlcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgaW5zZXJ0UmVtaW5kZXJzR2l2ZW5FdmVudFJlc291cmNlID0gYXN5bmMgKFxuICBldmVudHM6IEV2ZW50UmVzb3VyY2VUeXBlW10sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYWxlbmRhcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGlmICghKGV2ZW50cz8uZmlsdGVyKChlKSA9PiAhIWU/LmlkKT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgY29uc3QgcmVtaW5kZXJzID0gW107XG4gICAgZXZlbnRzXG4gICAgICAuZmlsdGVyKFxuICAgICAgICAoZSkgPT5cbiAgICAgICAgICBlPy5yZW1pbmRlcnM/LnVzZURlZmF1bHQgfHwgZT8ucmVtaW5kZXJzPy5vdmVycmlkZXM/LlswXT8ubWludXRlcyA+IC0xXG4gICAgICApXG4gICAgICAuZm9yRWFjaCgoZXZlbnQpID0+IHtcbiAgICAgICAgY29uc3QgZXZlbnRJZCA9IGV2ZW50Py5pZDtcbiAgICAgICAgY29uc3QgdGltZXpvbmUgPSBldmVudD8uc3RhcnQ/LnRpbWVab25lO1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBldmVudElkLFxuICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgJyBldmVudElkLCBjYWxlbmRhcklkIGluc2lkZSBpbnNlcnRSZW1pbmRlcnNHaXZlbkV2ZW50UmVzb3VyY2UnXG4gICAgICAgICk7XG4gICAgICAgIGlmIChldmVudD8ucmVtaW5kZXJzPy51c2VEZWZhdWx0KSB7XG4gICAgICAgICAgcmVtaW5kZXJzLnB1c2goe1xuICAgICAgICAgICAgZXZlbnRJZDogYCR7ZXZlbnRJZH0jJHtjYWxlbmRhcklkfWAsXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICB1c2VEZWZhdWx0OiBldmVudD8ucmVtaW5kZXJzPy51c2VEZWZhdWx0LFxuICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgfSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgZXZlbnQ/LnJlbWluZGVycz8ub3ZlcnJpZGVzLmZvckVhY2goKG8pID0+IHtcbiAgICAgICAgICAgIHJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgICAgZXZlbnRJZDogYCR7ZXZlbnRJZH0jJHtjYWxlbmRhcklkfWAsXG4gICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIG1ldGhvZDogbz8ubWV0aG9kLFxuICAgICAgICAgICAgICBtaW51dGVzOiBvPy5taW51dGVzLFxuICAgICAgICAgICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgIH0pO1xuICAgICAgICB9XG4gICAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKHJlbWluZGVycywgJyByZW1pbmRlcnMnKTtcbiAgICBpZiAoIShyZW1pbmRlcnM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdJbnNlcnRSZW1pbmRlcic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgbXV0YXRpb24gSW5zZXJ0UmVtaW5kZXIoJHJlbWluZGVyczogW1JlbWluZGVyX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICAgICAgaW5zZXJ0X1JlbWluZGVyKFxuICAgICAgICAgICAgICAgIG9iamVjdHM6ICRyZW1pbmRlcnMsXG4gICAgICAgICAgICAgICAgKXtcbiAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH1cbiAgICAgICB9XG4gICAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHJlbWluZGVycyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIGluc2VydFJlbWluZGVyc0dpdmVuUmVzb3VyY2UnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwc2VydCByZW1pbmRlcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0R29vZ2xlSW50ZWdyYXRpb24gPSBhc3luYyAoY2FsZW5kYXJJbnRlZ3JhdGlvbklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldENhbGVuZGFySW50ZWdyYXRpb24nO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYHF1ZXJ5IGdldENhbGVuZGFySW50ZWdyYXRpb24oJGlkOiB1dWlkISl7XG4gICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgIGlkXG4gICAgICAgIG5hbWVcbiAgICAgICAgdG9rZW5cbiAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgIGNsaWVudFR5cGVcbiAgICAgIH1cbiAgICB9YDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7IGlkOiBjYWxlbmRhckludGVncmF0aW9uSWQgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiB7XG4gICAgICBkYXRhOiB7IENhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICAvLyBqdXN0IHRvIGNoZWNrXG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgdGhpcyBpcyByZXNwb25zZSBpbiBnZXRHb29nbGVJbnRlZ3JhdGlvbicpO1xuICAgIGlmIChyZXNwb25zZT8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGspIHtcbiAgICAgIGNvbnN0IHtcbiAgICAgICAgZGF0YToge1xuICAgICAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiB7IHRva2VuLCByZWZyZXNoVG9rZW4sIGNsaWVudFR5cGUgfSxcbiAgICAgICAgfSxcbiAgICAgIH0gPSByZXNwb25zZTtcblxuICAgICAgcmV0dXJuIHsgdG9rZW4sIHJlZnJlc2hUb2tlbiwgY2xpZW50VHlwZSB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBnb29nbGUgdG9rZW4nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEdvb2dsZUNvbG9yID0gYXN5bmMgKHRva2VuOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgfSxcbiAgICB9O1xuICAgIGNvbnN0IGJvZHk6IGNvbG9yVHlwZVJlc3BvbnNlID0gYXdhaXQgZ290XG4gICAgICAuZ2V0KGdvb2dsZUNvbG9yVXJsLCBjb25maWcpXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKGJvZHksICcgYm9keSBpbnNpZGUgZ2V0R29vZ2xlQ29sb3InKTtcbiAgICByZXR1cm4gYm9keTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBjb2xvcnMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEdvb2dsZUNhbGVuZGFySW5EYiA9IGFzeW5jIChjYWxlbmRhcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldENhbGVuZGFyQnlJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgcXVlcnkgR2V0Q2FsZW5kYXJCeUlkKCRpZDogU3RyaW5nISkge1xuICAgICAgQ2FsZW5kYXJfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgICBpZFxuICAgICAgICB0aXRsZVxuICAgICAgICBjb2xvcklkXG4gICAgICAgIGFjY291bnRcbiAgICAgICAgYWNjZXNzTGV2ZWxcbiAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICByZXNvdXJjZVxuICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgIGdsb2JhbFByaW1hcnlcbiAgICAgICAgZGVsZXRlZFxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlcklkXG4gICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgcGFnZVRva2VuXG4gICAgICAgIHN5bmNUb2tlblxuICAgICAgfVxuICAgIH1gO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHsgaWQ6IGNhbGVuZGFySWQgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiB7IGRhdGE6IHsgQ2FsZW5kYXJfYnlfcGs6IENhbGVuZGFyVHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICAvLyBqdXN0IHRvIGNoZWNrXG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgdGhpcyBpcyByZXNwb25zZSBpbiBnZXRHb29nbGVDYWxlbmRhcicpO1xuICAgIGlmIChyZXNwb25zZT8uZGF0YT8uQ2FsZW5kYXJfYnlfcGspIHtcbiAgICAgIGNvbnN0IHtcbiAgICAgICAgZGF0YToge1xuICAgICAgICAgIENhbGVuZGFyX2J5X3BrOiB7IHBhZ2VUb2tlbiwgc3luY1Rva2VuLCBpZCB9LFxuICAgICAgICB9LFxuICAgICAgfSA9IHJlc3BvbnNlO1xuXG4gICAgICByZXR1cm4geyBwYWdlVG9rZW4sIHN5bmNUb2tlbiwgaWQgfTtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgZ29vZ2xlIHRva2VuJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVBdHRlbmRlZXMgPSBhc3luYyAoXG4gIGV2ZW50czogRXZlbnRSZXNvdXJjZVR5cGVbXSxcbiAgY2FsZW5kYXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBldmVudElkcyA9IGV2ZW50cy5tYXAoKGUpID0+IGAke2U/LmlkfSMke2NhbGVuZGFySWR9YCk7XG5cbiAgICBpZiAoIShldmVudElkcz8uZmlsdGVyKChlKSA9PiAhIWUpPy5sZW5ndGggPiAwKSkge1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnRGVsZXRlQXR0ZW5kZWVzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIG11dGF0aW9uIERlbGV0ZUF0dGVuZGVlcygkZXZlbnRJZHM6IFtTdHJpbmchXSEpIHtcbiAgICAgICAgZGVsZXRlX0F0dGVuZGVlKHdoZXJlOiB7ZXZlbnRJZDoge19pbjogJGV2ZW50SWRzfX0pIHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgZXZlbnRJZHMsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhyZXN1bHRzLCAnIHN1Y2Nlc3NmdWxseSBkZWxldGVkIGF0dGVuZGVlcycpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGVsZXRlIGF0dGVuZGVlcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcmVmcmVzaFpvb21Ub2tlbiA9IGFzeW5jIChcbiAgcmVmcmVzaFRva2VuOiBzdHJpbmdcbik6IFByb21pc2U8e1xuICBhY2Nlc3NfdG9rZW46IHN0cmluZztcbiAgdG9rZW5fdHlwZTogJ2JlYXJlcic7XG4gIHJlZnJlc2hfdG9rZW46IHN0cmluZztcbiAgZXhwaXJlc19pbjogbnVtYmVyO1xuICBzY29wZTogc3RyaW5nO1xufT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHVzZXJuYW1lID0gem9vbUNsaWVudElkO1xuICAgIGNvbnN0IHBhc3N3b3JkID0gem9vbUNsaWVudFNlY3JldDtcblxuICAgIHJldHVybiBheGlvcyh7XG4gICAgICBkYXRhOiBuZXcgVVJMU2VhcmNoUGFyYW1zKHtcbiAgICAgICAgcmVmcmVzaF90b2tlbjogcmVmcmVzaFRva2VuLFxuICAgICAgICBncmFudF90eXBlOiAncmVmcmVzaF90b2tlbicsXG4gICAgICB9KS50b1N0cmluZygpLFxuICAgICAgYmFzZVVSTDogem9vbUJhc2VUb2tlblVybCxcbiAgICAgIHVybDogJy9vYXV0aC90b2tlbicsXG4gICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgfSxcbiAgICAgIGF1dGg6IHtcbiAgICAgICAgdXNlcm5hbWUsXG4gICAgICAgIHBhc3N3b3JkLFxuICAgICAgfSxcbiAgICB9KS50aGVuKCh7IGRhdGEgfSkgPT4gUHJvbWlzZS5yZXNvbHZlKGRhdGEpKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlZnJlc2ggem9vbSB0b2tlbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVjcnlwdFpvb21Ub2tlbnMgPSAoXG4gIGVuY3J5cHRlZFRva2VuOiBzdHJpbmcsXG4gIGVuY3J5cHRlZFJlZnJlc2hUb2tlbj86IHN0cmluZ1xuKSA9PiB7XG4gIGNvbnN0IGl2QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbUlWRm9yUGFzcywgJ2Jhc2U2NCcpO1xuICBjb25zdCBzYWx0QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbVNhbHRGb3JQYXNzLCAnYmFzZTY0Jyk7XG5cbiAgY29uc3Qga2V5ID0gY3J5cHRvLnBia2RmMlN5bmMoXG4gICAgem9vbVBhc3NLZXkgYXMgc3RyaW5nLFxuICAgIHNhbHRCdWZmZXIsXG4gICAgMTAwMDAsXG4gICAgMzIsXG4gICAgJ3NoYTI1NidcbiAgKTtcblxuICBjb25zdCBkZWNpcGhlclRva2VuID0gY3J5cHRvLmNyZWF0ZURlY2lwaGVyaXYoJ2Flcy0yNTYtY2JjJywga2V5LCBpdkJ1ZmZlcik7XG4gIGxldCBkZWNyeXB0ZWRUb2tlbiA9IGRlY2lwaGVyVG9rZW4udXBkYXRlKGVuY3J5cHRlZFRva2VuLCAnYmFzZTY0JywgJ3V0ZjgnKTtcbiAgZGVjcnlwdGVkVG9rZW4gKz0gZGVjaXBoZXJUb2tlbi5maW5hbCgndXRmOCcpO1xuXG4gIGlmIChlbmNyeXB0ZWRSZWZyZXNoVG9rZW4pIHtcbiAgICBjb25zdCBkZWNpcGhlclJlZnJlc2hUb2tlbiA9IGNyeXB0by5jcmVhdGVEZWNpcGhlcml2KFxuICAgICAgJ2Flcy0yNTYtY2JjJyxcbiAgICAgIGtleSxcbiAgICAgIGl2QnVmZmVyXG4gICAgKTtcbiAgICBsZXQgZGVjcnlwdGVkUmVmcmVzaFRva2VuID0gZGVjaXBoZXJSZWZyZXNoVG9rZW4udXBkYXRlKFxuICAgICAgZW5jcnlwdGVkUmVmcmVzaFRva2VuLFxuICAgICAgJ2Jhc2U2NCcsXG4gICAgICAndXRmOCdcbiAgICApO1xuICAgIGRlY3J5cHRlZFJlZnJlc2hUb2tlbiArPSBkZWNpcGhlclJlZnJlc2hUb2tlbi5maW5hbCgndXRmOCcpO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIHRva2VuOiBkZWNyeXB0ZWRUb2tlbixcbiAgICAgIHJlZnJlc2hUb2tlbjogZGVjcnlwdGVkUmVmcmVzaFRva2VuLFxuICAgIH07XG4gIH1cblxuICByZXR1cm4ge1xuICAgIHRva2VuOiBkZWNyeXB0ZWRUb2tlbixcbiAgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBlbmNyeXB0Wm9vbVRva2VucyA9ICh0b2tlbjogc3RyaW5nLCByZWZyZXNoVG9rZW4/OiBzdHJpbmcpID0+IHtcbiAgY29uc3QgaXZCdWZmZXIgPSBCdWZmZXIuZnJvbSh6b29tSVZGb3JQYXNzLCAnYmFzZTY0Jyk7XG4gIGNvbnN0IHNhbHRCdWZmZXIgPSBCdWZmZXIuZnJvbSh6b29tU2FsdEZvclBhc3MsICdiYXNlNjQnKTtcblxuICBjb25zdCBrZXkgPSBjcnlwdG8ucGJrZGYyU3luYyhcbiAgICB6b29tUGFzc0tleSBhcyBzdHJpbmcsXG4gICAgc2FsdEJ1ZmZlcixcbiAgICAxMDAwMCxcbiAgICAzMixcbiAgICAnc2hhMjU2J1xuICApO1xuICBjb25zdCBjaXBoZXJUb2tlbiA9IGNyeXB0by5jcmVhdGVDaXBoZXJpdignYWVzLTI1Ni1jYmMnLCBrZXksIGl2QnVmZmVyKTtcbiAgbGV0IGVuY3J5cHRlZFRva2VuID0gY2lwaGVyVG9rZW4udXBkYXRlKHRva2VuLCAndXRmOCcsICdiYXNlNjQnKTtcbiAgZW5jcnlwdGVkVG9rZW4gKz0gY2lwaGVyVG9rZW4uZmluYWwoJ2Jhc2U2NCcpO1xuXG4gIGxldCBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gPSAnJztcblxuICBpZiAocmVmcmVzaFRva2VuKSB7XG4gICAgY29uc3QgY2lwaGVyUmVmcmVzaFRva2VuID0gY3J5cHRvLmNyZWF0ZUNpcGhlcml2KFxuICAgICAgJ2Flcy0yNTYtY2JjJyxcbiAgICAgIGtleSxcbiAgICAgIGl2QnVmZmVyXG4gICAgKTtcbiAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gPSBjaXBoZXJSZWZyZXNoVG9rZW4udXBkYXRlKFxuICAgICAgcmVmcmVzaFRva2VuLFxuICAgICAgJ3V0ZjgnLFxuICAgICAgJ2Jhc2U2NCdcbiAgICApO1xuICAgIGVuY3J5cHRlZFJlZnJlc2hUb2tlbiArPSBjaXBoZXJSZWZyZXNoVG9rZW4uZmluYWwoJ2Jhc2U2NCcpO1xuICB9XG5cbiAgaWYgKGVuY3J5cHRlZFJlZnJlc2hUb2tlbikge1xuICAgIHJldHVybiB7XG4gICAgICBlbmNyeXB0ZWRUb2tlbixcbiAgICAgIGVuY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICB9O1xuICB9IGVsc2Uge1xuICAgIHJldHVybiB7IGVuY3J5cHRlZFRva2VuIH07XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRab29tSW50ZWdyYXRpb24gPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGlkLCB0b2tlbiwgZXhwaXJlc0F0LCByZWZyZXNoVG9rZW4gfSA9IGF3YWl0IGdldENhbGVuZGFySW50ZWdyYXRpb24oXG4gICAgICB1c2VySWQsXG4gICAgICB6b29tUmVzb3VyY2VOYW1lXG4gICAgKTtcblxuICAgIGNvbnN0IGRlY3J5cHRlZFRva2VucyA9IGRlY3J5cHRab29tVG9rZW5zKHRva2VuLCByZWZyZXNoVG9rZW4pO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIGlkLFxuICAgICAgZXhwaXJlc0F0LFxuICAgICAgLi4uZGVjcnlwdGVkVG9rZW5zLFxuICAgIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgem9vbSBpbnRlZ3JhdGlvbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlWm9vbUludGVncmF0aW9uID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICBhY2Nlc3NUb2tlbjogc3RyaW5nLFxuICBleHBpcmVzSW46IG51bWJlclxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBlbmNyeXB0ZWRUb2tlbiB9ID0gZW5jcnlwdFpvb21Ub2tlbnMoYWNjZXNzVG9rZW4pO1xuICAgIGF3YWl0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oaWQsIGVuY3J5cHRlZFRva2VuLCBleHBpcmVzSW4pO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIHpvb20gaW50ZWdyYXRpb24nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldFpvb21BUElUb2tlbiA9IGFzeW5jICh1c2VySWQ6IHN0cmluZykgPT4ge1xuICBsZXQgaW50ZWdyYXRpb25JZCA9ICcnO1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKCdnZXRab29tQVBJVG9rZW4gY2FsbGVkJyk7XG4gICAgY29uc3QgeyBpZCwgdG9rZW4sIGV4cGlyZXNBdCwgcmVmcmVzaFRva2VuIH0gPVxuICAgICAgYXdhaXQgZ2V0Wm9vbUludGVncmF0aW9uKHVzZXJJZCk7XG4gICAgaWYgKCFyZWZyZXNoVG9rZW4pIHtcbiAgICAgIGNvbnNvbGUubG9nKCd6b29tIG5vdCBhY3RpdmUsIG5vIHJlZnJlc2ggdG9rZW4nKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBpbnRlZ3JhdGlvbklkID0gaWQ7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBpZCxcbiAgICAgIHRva2VuLFxuICAgICAgZXhwaXJlc0F0LFxuICAgICAgcmVmcmVzaFRva2VuLFxuICAgICAgJyBpZCwgdG9rZW4sIGV4cGlyZXNBdCwgcmVmcmVzaFRva2VuJ1xuICAgICk7XG4gICAgaWYgKGRheWpzKCkuaXNBZnRlcihkYXlqcyhleHBpcmVzQXQpKSB8fCAhdG9rZW4pIHtcbiAgICAgIGNvbnN0IHJlcyA9IGF3YWl0IHJlZnJlc2hab29tVG9rZW4ocmVmcmVzaFRva2VuKTtcbiAgICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSByZWZyZXNoWm9vbVRva2VuJyk7XG4gICAgICBhd2FpdCB1cGRhdGVab29tSW50ZWdyYXRpb24oaWQsIHJlcy5hY2Nlc3NfdG9rZW4sIHJlcy5leHBpcmVzX2luKTtcbiAgICAgIHJldHVybiByZXMuYWNjZXNzX3Rva2VuO1xuICAgIH1cblxuICAgIHJldHVybiB0b2tlbjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCB6b29tIGFwaSB0b2tlbicpO1xuICAgIGF3YWl0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oaW50ZWdyYXRpb25JZCwgbnVsbCwgbnVsbCwgZmFsc2UpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlWm9vbU1lZXRpbmcgPSBhc3luYyAoXG4gIHpvb21Ub2tlbjogc3RyaW5nLFxuICBjb25mZXJlbmNlSWQ6IG51bWJlcixcbiAgc2NoZWR1bGVGb3JSZW1pbmRlcj86IGJvb2xlYW4sXG4gIGNhbmNlbE1lZXRpbmdSZW1pbmRlcj86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIGxldCBwYXJhbXM6IGFueSA9IHt9O1xuICAgIGlmIChjYW5jZWxNZWV0aW5nUmVtaW5kZXIgfHwgc2NoZWR1bGVGb3JSZW1pbmRlcikge1xuICAgICAgaWYgKGNhbmNlbE1lZXRpbmdSZW1pbmRlcikge1xuICAgICAgICBwYXJhbXMgPSB7IGNhbmNlbF9tZWV0aW5nX3JlbWluZGVyOiBjYW5jZWxNZWV0aW5nUmVtaW5kZXIgfTtcbiAgICAgIH1cblxuICAgICAgaWYgKHNjaGVkdWxlRm9yUmVtaW5kZXIpIHtcbiAgICAgICAgcGFyYW1zID0geyAuLi5wYXJhbXMsIHNjaGVkdWxlX2Zvcl9yZW1pbmRlcjogc2NoZWR1bGVGb3JSZW1pbmRlciB9O1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHN0cmluZ2lmaWVkT2JqZWN0ID1cbiAgICAgIE9iamVjdC5rZXlzKHBhcmFtcyk/Lmxlbmd0aCA+IDAgPyBxcy5zdHJpbmdpZnkocGFyYW1zKSA6ICcnO1xuXG4gICAgaWYgKHN0cmluZ2lmaWVkT2JqZWN0KSB7XG4gICAgICBhd2FpdCBnb3QuZGVsZXRlKFxuICAgICAgICBgJHt6b29tQmFzZVVybH0vbWVldGluZ3MvYCArIGNvbmZlcmVuY2VJZCArICc/JyArIHN0cmluZ2lmaWVkT2JqZWN0LFxuICAgICAgICB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3pvb21Ub2tlbn1gLFxuICAgICAgICAgICAgQ29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9XG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICBhd2FpdCBnb3QuZGVsZXRlKGAke3pvb21CYXNlVXJsfS9tZWV0aW5ncy9gICsgY29uZmVyZW5jZUlkLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7em9vbVRva2VufWAsXG4gICAgICAgICAgQ29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgfSxcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGNvbmZlcmVuY2VJZCwgJ3N1Y2Nlc3NmdWxseSBkZWxldGVkIG1lZXRpbmcnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSB6b29tIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RDb25mZXJlbmNlc1dpdGhIb3N0cyA9IGFzeW5jIChpZHM6IHN0cmluZ1tdKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdMaXN0Q29uZmVyZW5jZXNXaXRoSG9zdElkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IExpc3RDb25mZXJlbmNlc1dpdGhIb3N0SWQoJGlkczogW1N0cmluZyFdISkge1xuICAgICAgICAgICAgICAgIENvbmZlcmVuY2Uod2hlcmU6IHtpZDoge19pbjogJGlkc30sIGlzSG9zdDoge19lcTogdHJ1ZX19KSB7XG4gICAgICAgICAgICAgICAgICAgIGFwcFxuICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgZW50cnlQb2ludHNcbiAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgaWNvblVyaVxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBpc0hvc3RcbiAgICAgICAgICAgICAgICAgICAgam9pblVybFxuICAgICAgICAgICAgICAgICAgICBrZXlcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBwYXJhbWV0ZXJzXG4gICAgICAgICAgICAgICAgICAgIHJlcXVlc3RJZFxuICAgICAgICAgICAgICAgICAgICBzdGFydFVybFxuICAgICAgICAgICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgdHlwZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHpvb21Qcml2YXRlTWVldGluZ1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkcyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ29uZmVyZW5jZTogQ29uZmVyZW5jZVR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyBzdWNjZXNzZnVsbHkgbGlzdGVkIGNvbmZlcmVuY2VzIHdpdGggaG9zdHMnKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LkNvbmZlcmVuY2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IGNvbmZlcmVuY2VzIHdpdGggaG9zdHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUNvbmZlcmVuY2VzSW5EYiA9IGFzeW5jIChjb25mZXJlbmNlSWRzOiBzdHJpbmdbXSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZGVsZXRlQ29uZmVyZW5jZXMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gZGVsZXRlQ29uZmVyZW5jZXMoJGlkczogW1N0cmluZyFdISkge1xuICAgICAgICAgICAgICAgIGRlbGV0ZV9Db25mZXJlbmNlKHdoZXJlOiB7aWQ6IHtfaW46ICRpZHN9fSkge1xuICAgICAgICAgICAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkczogY29uZmVyZW5jZUlkcyxcbiAgICB9O1xuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgc3VjY2Vzc2Z1bGx5IGRlbGV0ZWQgbXVsdGlwbGUgY29uZmVyZW5jZXMnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBjb25mZXJlbmNlcyBpbiBkYicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlQ29uZmVyZW5jZXMgPSBhc3luYyAoXG4gIGV2ZW50czoge1xuICAgIGV2ZW50SWQ6IHN0cmluZztcbiAgICBpZDogc3RyaW5nO1xuICAgIGNhbGVuZGFySWQ6IHN0cmluZztcbiAgICBtZWV0aW5nSWQ6IHN0cmluZztcbiAgICBjb25mZXJlbmNlSWQ/OiBzdHJpbmc7XG4gIH1bXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgY29uZmVyZW5jZUlkcyA9IGV2ZW50cz8ubWFwKChlKSA9PiBlPy5jb25mZXJlbmNlSWQpO1xuXG4gICAgY29uc3QgdHJ1dGh5ID0gY29uZmVyZW5jZUlkcy5maWx0ZXIoKGNJZCkgPT4gISFjSWQpO1xuXG4gICAgaWYgKCF0cnV0aHk/LlswXSkge1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIC8vIGRlbGV0ZSB6b29tIG1lZXRpbmdzIGlmIGFueVxuXG4gICAgY29uc3QgY29uZmVyZW5jZXMgPSBhd2FpdCBsaXN0Q29uZmVyZW5jZXNXaXRoSG9zdHMoY29uZmVyZW5jZUlkcyk7XG5cbiAgICBmb3IgKGNvbnN0IGNvbmZlcmVuY2Ugb2YgY29uZmVyZW5jZXMpIHtcbiAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbihjb25mZXJlbmNlPy51c2VySWQpO1xuXG4gICAgICBpZiAoem9vbVRva2VuICYmIHR5cGVvZiBwYXJzZUludChjb25mZXJlbmNlPy5pZCwgMTApID09PSAnbnVtYmVyJykge1xuICAgICAgICBhd2FpdCBkZWxldGVab29tTWVldGluZyh6b29tVG9rZW4sIHBhcnNlSW50KGNvbmZlcmVuY2U/LmlkLCAxMCkpO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIGRlbGV0ZSBpbiBkYlxuICAgIGF3YWl0IGRlbGV0ZUNvbmZlcmVuY2VzSW5EYihjb25mZXJlbmNlSWRzKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZUNvbmZlcmVuY2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUV2ZW50cyA9IGFzeW5jIChcbiAgZXZlbnRzOiBFdmVudFJlc291cmNlVHlwZVtdLFxuICBjYWxlbmRhcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGV2ZW50SWRzID0gZXZlbnRzLm1hcCgoZSkgPT4gYCR7ZT8uaWR9IyR7Y2FsZW5kYXJJZH1gKTtcbiAgICBjb25zb2xlLmxvZyhldmVudElkcywgJyBldmVudElkcyBpbnNpZGUgZGVsZXRlRXZlbnRzJyk7XG4gICAgaWYgKCEoZXZlbnRJZHM/LmZpbHRlcigoZSkgPT4gISFlKT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdkZWxldGVFdmVudHMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gZGVsZXRlRXZlbnRzKCRldmVudElkczogW1N0cmluZyFdISkge1xuICAgICAgICAgICAgICAgIGRlbGV0ZV9FdmVudCh3aGVyZToge2lkOiB7X2luOiAkZXZlbnRJZHN9fSkge1xuICAgICAgICAgICAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlSWRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cblxuICAgICAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGV2ZW50SWRzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgZGVsZXRlX0V2ZW50OiB7XG4gICAgICAgICAgYWZmZWN0ZWRfcm93czogbnVtYmVyO1xuICAgICAgICAgIHJldHVybmluZzoge1xuICAgICAgICAgICAgZXZlbnRJZDogc3RyaW5nO1xuICAgICAgICAgICAgaWQ6IHN0cmluZztcbiAgICAgICAgICAgIGNhbGVuZGFySWQ6IHN0cmluZztcbiAgICAgICAgICAgIG1lZXRpbmdJZDogc3RyaW5nO1xuICAgICAgICAgICAgY29uZmVyZW5jZUlkPzogc3RyaW5nO1xuICAgICAgICAgIH1bXTtcbiAgICAgICAgfTtcbiAgICAgIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlcywgJyB0aGlzIGlzIHJlc3BvbnNlIGluIGRlbGV0ZUV2ZW50cycpO1xuICAgIHJldHVybiByZXM/LmRhdGE/LmRlbGV0ZV9FdmVudD8ucmV0dXJuaW5nO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGVsZXRlIGV2ZW50cycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlUmVtaW5kZXJzID0gYXN5bmMgKFxuICBldmVudHM6IEV2ZW50UmVzb3VyY2VUeXBlW10sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYWxlbmRhcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGlmICghKGV2ZW50cz8uZmlsdGVyKChlKSA9PiAhIWU/LmlkKT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdkZWxldGVSZW1pbmRlcnMnO1xuICAgIGNvbnN0IGRlbEV2ZW50cyA9IGV2ZW50cy5tYXAoKGUpID0+IGAke2U/LmlkfSMke2NhbGVuZGFySWR9YCk7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBtdXRhdGlvbiBkZWxldGVSZW1pbmRlcnMoJHVzZXJJZDogdXVpZCEsICRldmVudElkczogW1N0cmluZyFdISkge1xuICAgICAgICBkZWxldGVfUmVtaW5kZXIod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCBldmVudElkOiB7X2luOiAkZXZlbnRJZHN9fSkge1xuICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICBldmVudElkczogZGVsRXZlbnRzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHRoaXMgaXMgcmVzcG9uc2UgaW4gZGVsZXRlUmVtaW5kZXJzJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkZWxldGUgcmVtaW5kZXJzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRVc2VyUHJlZmVyZW5jZXMgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPFVzZXJQcmVmZXJlbmNlVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGlmICghdXNlcklkKSB7XG4gICAgICBjb25zb2xlLmxvZygndXNlcklkIGlzIG51bGwnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldFVzZXJQcmVmZXJlbmNlcyc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgZ2V0VXNlclByZWZlcmVuY2VzKCR1c2VySWQ6IHV1aWQhKSB7XG4gICAgICBVc2VyX1ByZWZlcmVuY2Uod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9fSkge1xuICAgICAgICBzdGFydFRpbWVzXG4gICAgICAgIGVuZFRpbWVzXG4gICAgICAgIGJhY2tUb0JhY2tNZWV0aW5nc1xuICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgZGVsZXRlZFxuICAgICAgICBmb2xsb3dVcFxuICAgICAgICBpZFxuICAgICAgICBpc1B1YmxpY0NhbGVuZGFyXG4gICAgICAgIG1heE51bWJlck9mTWVldGluZ3NcbiAgICAgICAgbWF4V29ya0xvYWRQZXJjZW50XG4gICAgICAgIHB1YmxpY0NhbGVuZGFyQ2F0ZWdvcmllc1xuICAgICAgICByZW1pbmRlcnNcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgICBtaW5OdW1iZXJPZkJyZWFrc1xuICAgICAgICBicmVha0NvbG9yXG4gICAgICAgIGJyZWFrTGVuZ3RoXG4gICAgICAgIGNvcHlDb2xvclxuICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICBvbkJvYXJkZWRcbiAgICAgIH1cbiAgICB9XG4gIGA7XG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgVXNlcl9QcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICByZXR1cm4gcmVzPy5kYXRhPy5Vc2VyX1ByZWZlcmVuY2U/LlswXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZ2V0VXNlclByZWZlcmVuY2VzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjb252ZXJ0VG9Ub3RhbFdvcmtpbmdIb3VycyA9IChcbiAgdXNlclByZWZlcmVuY2U6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgc3RhcnREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmdcbikgPT4ge1xuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcbiAgY29uc3QgZGF5T2ZXZWVrSW50ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiBzdGFydEhvdXIsXG4gICAgbWludXRlczogc3RhcnRNaW51dGUsXG4gIH0pO1xuICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGVuZEhvdXIsIG1pbnV0ZXM6IGVuZE1pbnV0ZSB9KTtcbiAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICByZXR1cm4gdG90YWxEdXJhdGlvbi5hc0hvdXJzKCk7XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdEV2ZW50c1dpdGhJZHMgPSBhc3luYyAoaWRzOiBzdHJpbmdbXSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnbGlzdEV2ZW50c1dpdGhJZHMnO1xuXG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgcXVlcnkgbGlzdEV2ZW50c1dpdGhJZHMoJGlkczogW1N0cmluZyFdISkge1xuICAgICAgRXZlbnQod2hlcmU6IHtpZDoge19pbjogJGlkc319KSB7XG4gICAgICAgIGFsbERheVxuICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgY29sb3JJZFxuICAgICAgICBjb25mZXJlbmNlSWRcbiAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBjcmVhdG9yXG4gICAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgICAgZGVsZXRlZFxuICAgICAgICBkdXJhdGlvblxuICAgICAgICBlbmREYXRlXG4gICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICBldmVudElkXG4gICAgICAgIGV2ZW50VHlwZVxuICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgZm9sbG93VXBFdmVudElkXG4gICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgIGh0bWxMaW5rXG4gICAgICAgIGlDYWxVSURcbiAgICAgICAgaWRcbiAgICAgICAgaXNCcmVha1xuICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgaXNGb2xsb3dVcFxuICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICBpc1Bvc3RFdmVudFxuICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgIGxpbmtzXG4gICAgICAgIGxvY2F0aW9uXG4gICAgICAgIGxvY2tlZFxuICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgbWVldGluZ0lkXG4gICAgICAgIG1ldGhvZFxuICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgIG5vdGVzXG4gICAgICAgIG9yZ2FuaXplclxuICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgIHBvc3RFdmVudElkXG4gICAgICAgIHByZUV2ZW50SWRcbiAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICAgIHByaW9yaXR5XG4gICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgc291cmNlXG4gICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICBzdGF0dXNcbiAgICAgICAgc3VtbWFyeVxuICAgICAgICB0YXNrSWRcbiAgICAgICAgdGFza1R5cGVcbiAgICAgICAgdGltZUJsb2NraW5nXG4gICAgICAgIHRpbWV6b25lXG4gICAgICAgIHRpdGxlXG4gICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICB1bmxpbmtcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgdXNlcklkXG4gICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICAgIGNvcHlDb2xvclxuICAgICAgfVxuICAgIH1cbiAgICBgO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICBpZHMsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uRXZlbnQ7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IGlkcyB3aXRoIGlkcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdEV2ZW50c0ZvckRhdGUgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2xpc3RFdmVudHNGb3JEYXRlJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgcXVlcnkgbGlzdEV2ZW50c0ZvckRhdGUoJHVzZXJJZDogdXVpZCEsICRzdGFydERhdGU6IHRpbWVzdGFtcCEsICRlbmREYXRlOiB0aW1lc3RhbXAhKSB7XG4gICAgICAgICAgRXZlbnQod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCBzdGFydERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlLCBfbHQ6ICRlbmREYXRlfSwgZGVsZXRlZDoge19lcTogZmFsc2V9fSkge1xuICAgICAgICAgICAgYWxsRGF5XG4gICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICBhdHRhY2htZW50c1xuICAgICAgICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICBjb25mZXJlbmNlSWRcbiAgICAgICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgY3JlYXRvclxuICAgICAgICAgICAgZGFpbHlUYXNrTGlzdFxuICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICAgIGVuZERhdGVcbiAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgICAgIGZvbGxvd1VwRXZlbnRJZFxuICAgICAgICAgICAgZm9yRXZlbnRJZFxuICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgIGhhbmdvdXRMaW5rXG4gICAgICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgICAgIGh0bWxMaW5rXG4gICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICBpZFxuICAgICAgICAgICAgaXNCcmVha1xuICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgaXNGb2xsb3dVcFxuICAgICAgICAgICAgaXNNZWV0aW5nXG4gICAgICAgICAgICBpc01lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICBpc1Bvc3RFdmVudFxuICAgICAgICAgICAgaXNQcmVFdmVudFxuICAgICAgICAgICAgbGlua3NcbiAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICBsb2NrZWRcbiAgICAgICAgICAgIG1heEF0dGVuZGVlc1xuICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgIG1vZGlmaWFibGVcbiAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFRpbWVcbiAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICBvcmdhbml6ZXJcbiAgICAgICAgICAgIG9yaWdpbmFsQWxsRGF5XG4gICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgcG9zdEV2ZW50SWRcbiAgICAgICAgICAgIHByZUV2ZW50SWRcbiAgICAgICAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgICAgcHJlZmVycmVkRW5kVGltZVJhbmdlXG4gICAgICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgICAgICByZWN1cnJlbmNlUnVsZVxuICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgICAgIHNvZnREZWFkbGluZVxuICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgIHN0YXR1c1xuICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgdGFza0lkXG4gICAgICAgICAgICB0YXNrVHlwZVxuICAgICAgICAgICAgdGltZUJsb2NraW5nXG4gICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgdGl0bGVcbiAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgdW5saW5rXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvblxuICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNCcmVha1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZVxuICAgICAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICB3ZWVrbHlUYXNrTGlzdFxuICAgICAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgICAgICBsb2NhbFN5bmNlZFxuICAgICAgICAgICAgdXNlck1vZGlmaWVkQ29sb3JcbiAgICAgICAgICAgIGNvcHlDb2xvclxuICAgICAgICAgICAgY29weUV4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZEV4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgICAgICBgO1xuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IEV2ZW50OiBFdmVudFR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgc3RhcnREYXRlOiBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICAgIGVuZERhdGU6IGRheWpzKGVuZERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gbGlzdEV2ZW50c2ZvclVzZXInKTtcbiAgICByZXR1cm4gcmVzPy5kYXRhPy5FdmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgZXZlbnRzIGZvciBkYXRlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5ID0gKFxuICB3b3JraW5nSG91cnM6IG51bWJlcixcbiAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIGFsbEV2ZW50czogRXZlbnRQbHVzVHlwZVtdXG4pID0+IHtcbiAgLy8gdmFsaWRhdGVcbiAgaWYgKCF1c2VyUHJlZmVyZW5jZXM/LmJyZWFrTGVuZ3RoKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICAnbm8gdXNlciBwcmVmZXJlbmNlcyBicmVha0xlbmd0aCBwcm92aWRlZCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50cydcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuXG4gIGlmICghKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gYWxsRXZlbnRzIHByZXNlbnQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXknKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cblxuICBjb25zdCBicmVha0V2ZW50cyA9IGFsbEV2ZW50cy5maWx0ZXIoKGV2ZW50KSA9PiBldmVudC5pc0JyZWFrKTtcbiAgY29uc3QgbnVtYmVyT2ZCcmVha3NQZXJEYXkgPSB1c2VyUHJlZmVyZW5jZXMubWluTnVtYmVyT2ZCcmVha3M7XG5cbiAgY29uc3QgYnJlYWtIb3Vyc0F2YWlsYWJsZSA9XG4gICAgKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwKSAqIG51bWJlck9mQnJlYWtzUGVyRGF5O1xuICBsZXQgYnJlYWtIb3Vyc1VzZWQgPSAwO1xuICBmb3IgKGNvbnN0IGJyZWFrRXZlbnQgb2YgYnJlYWtFdmVudHMpIHtcbiAgICBjb25zdCBkdXJhdGlvbiA9IGRheWpzXG4gICAgICAuZHVyYXRpb24oXG4gICAgICAgIGRheWpzKFxuICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpXG4gICAgICAgICkuZGlmZihcbiAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpXG4gICAgICAgIClcbiAgICAgIClcbiAgICAgIC5hc0hvdXJzKCk7XG4gICAgYnJlYWtIb3Vyc1VzZWQgKz0gZHVyYXRpb247XG4gIH1cblxuICBpZiAoYnJlYWtIb3Vyc1VzZWQgPj0gYnJlYWtIb3Vyc0F2YWlsYWJsZSkge1xuICAgIGNvbnNvbGUubG9nKCdicmVha0hvdXJzVXNlZCA+PSBicmVha0hvdXJzQXZhaWxhYmxlJyk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgaWYgKCEoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ3RoZXJlIGFyZSBubyBldmVudHMgZm9yIHRoaXMgZGF0ZSBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50cydcbiAgICApO1xuICAgIHJldHVybiBmYWxzZTtcbiAgfVxuICBsZXQgaG91cnNVc2VkID0gMDtcbiAgZm9yIChjb25zdCBldmVudCBvZiBhbGxFdmVudHMpIHtcbiAgICBjb25zdCBkdXJhdGlvbiA9IGRheWpzXG4gICAgICAuZHVyYXRpb24oXG4gICAgICAgIGRheWpzKFxuICAgICAgICAgIGRheWpzKGV2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW06c3MnKVxuICAgICAgICApLmRpZmYoXG4gICAgICAgICAgZGF5anMoZXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJylcbiAgICAgICAgKVxuICAgICAgKVxuICAgICAgLmFzSG91cnMoKTtcbiAgICBob3Vyc1VzZWQgKz0gZHVyYXRpb247XG4gIH1cblxuICBpZiAoaG91cnNVc2VkID49IHdvcmtpbmdIb3Vycykge1xuICAgIGNvbnNvbGUubG9nKCdob3Vyc1VzZWQgPj0gd29ya2luZ0hvdXJzJyk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgcmV0dXJuIHRydWU7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVCcmVha3MgPSAoXG4gIHVzZXJQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGU6IG51bWJlcixcbiAgZXZlbnRNaXJyb3I6IEV2ZW50UGx1c1R5cGUsXG4gIGdsb2JhbENhbGVuZGFySWQ/OiBzdHJpbmdcbik6IEV2ZW50UGx1c1R5cGVbXSA9PiB7XG4gIGNvbnN0IGJyZWFrcyA9IFtdO1xuICAvLyB2YWxpZGF0ZVxuICBpZiAoIXVzZXJQcmVmZXJlbmNlcz8uYnJlYWtMZW5ndGgpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICdubyB1c2VyIHByZWZlcmVuY2VzIGJyZWFrTGVuZ3RoIHByb3ZpZGVkIGluc2lkZSBnZW5lcmF0ZUJyZWFrcydcbiAgICApO1xuICAgIHJldHVybiBicmVha3M7XG4gIH1cblxuICBpZiAoIW51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ25vIG51bWJlciBvZiBicmVha3MgdG8gZ2VuZXJhdGUgcHJvdmlkZWQgaW5zaWRlIGdlbmVyYXRlQnJlYWtzJ1xuICAgICk7XG4gICAgcmV0dXJuIGJyZWFrcztcbiAgfVxuXG4gIGlmICghZXZlbnRNaXJyb3IpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gZXZlbnQgbWlycm9yIHByb3ZpZGVkIGluc2lkZSBnZW5lcmF0ZUJyZWFrcycpO1xuICAgIHJldHVybiBicmVha3M7XG4gIH1cbiAgY29uc29sZS5sb2coXG4gICAgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlLFxuICAgICcgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlIGluc2lkZSBnZW5lcmF0ZUJyZWFrcydcbiAgKTtcbiAgZm9yIChsZXQgaSA9IDA7IGkgPCBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGU7IGkrKykge1xuICAgIGNvbnN0IGV2ZW50SWQgPSB1dWlkKCk7XG4gICAgY29uc3QgYnJlYWtFdmVudDogRXZlbnRQbHVzVHlwZSA9IHtcbiAgICAgIGlkOiBgJHtldmVudElkfSMke2dsb2JhbENhbGVuZGFySWQgfHwgZXZlbnRNaXJyb3IuY2FsZW5kYXJJZH19YCxcbiAgICAgIHVzZXJJZDogdXNlclByZWZlcmVuY2VzLnVzZXJJZCxcbiAgICAgIHRpdGxlOiAnQnJlYWsnLFxuICAgICAgc3RhcnREYXRlOiBkYXlqcyhldmVudE1pcnJvci5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooZXZlbnRNaXJyb3IudGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGVuZERhdGU6IGRheWpzKGV2ZW50TWlycm9yLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihldmVudE1pcnJvci50aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmFkZCh1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGgsICdtaW51dGUnKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBhbGxEYXk6IGZhbHNlLFxuICAgICAgbm90ZXM6ICdCcmVhaycsXG4gICAgICB0aW1lem9uZTogZXZlbnRNaXJyb3IudGltZXpvbmUsXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgIHByaW9yaXR5OiAxLFxuICAgICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgIG1vZGlmaWFibGU6IHRydWUsXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZmFsc2UsXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogZmFsc2UsXG4gICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgY2FsZW5kYXJJZDogZ2xvYmFsQ2FsZW5kYXJJZCB8fCBldmVudE1pcnJvci5jYWxlbmRhcklkLFxuICAgICAgYmFja2dyb3VuZENvbG9yOiB1c2VyUHJlZmVyZW5jZXMuYnJlYWtDb2xvciB8fCAnI0Y3RUJGNycsXG4gICAgICBpc0JyZWFrOiB0cnVlLFxuICAgICAgZHVyYXRpb246IHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCxcbiAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uOiB0cnVlLFxuICAgICAgdXNlck1vZGlmaWVkQ29sb3I6IHRydWUsXG4gICAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgICBtZXRob2Q6ICdjcmVhdGUnLFxuICAgICAgZXZlbnRJZCxcbiAgICB9O1xuICAgIGJyZWFrcy5wdXNoKGJyZWFrRXZlbnQpO1xuICB9XG5cbiAgcmV0dXJuIGJyZWFrcztcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5ID0gYXN5bmMgKFxuICB1c2VyUHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBldmVudHNUb0JlQnJlYWtzOiBFdmVudFBsdXNUeXBlW10gPSBbXSxcbiAgZ2xvYmFsQ2FsZW5kYXJJZD86IHN0cmluZyxcbiAgaXNGaXJzdERheT86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCF1c2VyUHJlZmVyZW5jZXM/LmJyZWFrTGVuZ3RoKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ25vIHVzZXIgcHJlZmVyZW5jZXMgYnJlYWtMZW5ndGggcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnXG4gICAgICApO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyB1c2VySWQgcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGlmICghc3RhcnREYXRlKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gc3RhcnREYXRlIHByb3ZpZGVkIGluc2lkZSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBpZiAoIXRpbWV6b25lKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gdGltZXpvbmUgcHJvdmlkZWQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHMnKTtcbiAgICAgIHJldHVybiBudWxsO1xuICAgIH1cblxuICAgIGlmIChpc0ZpcnN0RGF5KSB7XG4gICAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcztcbiAgICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgICAgZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgICApO1xuXG4gICAgICBsZXQgc3RhcnRIb3VyID0gZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmhvdXIoKTtcbiAgICAgIGxldCBzdGFydE1pbnV0ZSA9IGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLm1pbnV0ZSgpO1xuICAgICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgICBjb25zdCB3b3JrU3RhcnRIb3VyID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5ob3VyO1xuICAgICAgY29uc3Qgd29ya1N0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKFxuICAgICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICAgKS5taW51dGVzO1xuXG4gICAgICBpZiAoXG4gICAgICAgIGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLmlzQWZ0ZXIoXG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkuaG91cihlbmRIb3VyKS5taW51dGUoZW5kTWludXRlKVxuICAgICAgICApXG4gICAgICApIHtcbiAgICAgICAgLy8gcmV0dXJuIGVtcHR5IGFzIG91dHNpZGUgb2Ygd29yayB0aW1lXG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIGJlZm9yZSBzdGFydCB0aW1lXG4gICAgICBpZiAoXG4gICAgICAgIGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGUpXG4gICAgICAgIClcbiAgICAgICkge1xuICAgICAgICBzdGFydEhvdXIgPSB3b3JrU3RhcnRIb3VyO1xuICAgICAgICBzdGFydE1pbnV0ZSA9IHdvcmtTdGFydE1pbnV0ZTtcbiAgICAgIH1cblxuICAgICAgY29uc3Qgd29ya2luZ0hvdXJzID0gY29udmVydFRvVG90YWxXb3JraW5nSG91cnMoXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgc3RhcnREYXRlLFxuICAgICAgICB0aW1lem9uZVxuICAgICAgKTtcbiAgICAgIGNvbnN0IGFsbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgIHRpbWV6b25lXG4gICAgICApO1xuICAgICAgaWYgKCEoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAnbm8gYWxsRXZlbnRzIHByZXNlbnQgaW5zaWRlIHNob3VsZEdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXknXG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuICAgICAgY29uc3Qgc2hvdWxkR2VuZXJhdGVCcmVha3MgPSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgICB3b3JraW5nSG91cnMsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgYWxsRXZlbnRzXG4gICAgICApO1xuICAgICAgLy8gdmFsaWRhdGVcbiAgICAgIGlmICghc2hvdWxkR2VuZXJhdGVCcmVha3MpIHtcbiAgICAgICAgY29uc29sZS5sb2coJ3Nob3VsZCBub3QgZ2VuZXJhdGUgYnJlYWtzJyk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICBsZXQgaG91cnNVc2VkID0gMDtcblxuICAgICAgaWYgKGFsbEV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBmb3IgKGNvbnN0IGFsbEV2ZW50IG9mIGFsbEV2ZW50cykge1xuICAgICAgICAgIGNvbnN0IGR1cmF0aW9uID0gZGF5anNcbiAgICAgICAgICAgIC5kdXJhdGlvbihcbiAgICAgICAgICAgICAgZGF5anMoYWxsRXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAgIC5kaWZmKGRheWpzKGFsbEV2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKSlcbiAgICAgICAgICAgIClcbiAgICAgICAgICAgIC5hc0hvdXJzKCk7XG4gICAgICAgICAgaG91cnNVc2VkICs9IGR1cmF0aW9uO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGxldCBob3Vyc0F2YWlsYWJsZSA9IHdvcmtpbmdIb3VycyAtIGhvdXJzVXNlZDtcbiAgICAgIGhvdXJzQXZhaWxhYmxlIC09IHdvcmtpbmdIb3VycyAqIHVzZXJQcmVmZXJlbmNlcy5tYXhXb3JrTG9hZFBlcmNlbnQ7XG4gICAgICAvLyBubyBob3VycyBhdmFpbGFibGVcbiAgICAgIGlmIChob3Vyc0F2YWlsYWJsZSA8PSAwKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKGhvdXJzQXZhaWxhYmxlLCAnIG5vIGhvdXJzIGF2YWlsYWJsZScpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgY29uc3Qgb2xkQnJlYWtFdmVudHMgPSBhbGxFdmVudHNcbiAgICAgICAgLmZpbHRlcigoZXZlbnQpID0+IGV2ZW50LmlzQnJlYWspXG4gICAgICAgIC5maWx0ZXIoKGUpID0+XG4gICAgICAgICAgZGF5anMoc3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5pc1NhbWUoZGF5anMoZS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksICdkYXknKVxuICAgICAgICApO1xuXG4gICAgICBjb25zdCBicmVha0V2ZW50cyA9IGV2ZW50c1RvQmVCcmVha3MuY29uY2F0KG9sZEJyZWFrRXZlbnRzKTtcblxuICAgICAgY29uc3QgbnVtYmVyT2ZCcmVha3NQZXJEYXkgPSB1c2VyUHJlZmVyZW5jZXMubWluTnVtYmVyT2ZCcmVha3M7XG4gICAgICBjb25zb2xlLmxvZyhudW1iZXJPZkJyZWFrc1BlckRheSwgJyBudW1iZXJPZkJyZWFrc1BlckRheScpO1xuICAgICAgY29uc3QgYnJlYWtIb3Vyc1RvR2VuZXJhdGUgPVxuICAgICAgICAodXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIC8gNjApICogbnVtYmVyT2ZCcmVha3NQZXJEYXk7XG4gICAgICBsZXQgYnJlYWtIb3Vyc1VzZWQgPSAwO1xuXG4gICAgICBpZiAoYnJlYWtFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqc1xuICAgICAgICAgICAgLmR1cmF0aW9uKFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAuZGlmZihcbiAgICAgICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgICAgKVxuICAgICAgICAgICAgKVxuICAgICAgICAgICAgLmFzSG91cnMoKTtcbiAgICAgICAgICBicmVha0hvdXJzVXNlZCArPSBkdXJhdGlvbjtcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBjb25zdCBhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSA9IGJyZWFrSG91cnNUb0dlbmVyYXRlIC0gYnJlYWtIb3Vyc1VzZWQ7XG5cbiAgICAgIGlmIChhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSA+IGhvdXJzQXZhaWxhYmxlKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKCcgbm8gaG91cnMgYXZhaWxhYmxlIHRvIGdlbmVyYXRlIGJyZWFrJyk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICBjb25zb2xlLmxvZyhicmVha0hvdXJzVXNlZCwgJyBicmVha0hvdXJzVXNlZCcpO1xuICAgICAgY29uc29sZS5sb2coYnJlYWtIb3Vyc1RvR2VuZXJhdGUsICcgYnJlYWtIb3Vyc0F2YWlsYWJsZScpO1xuICAgICAgY29uc3QgYnJlYWtMZW5ndGhBc0hvdXJzID0gdXNlclByZWZlcmVuY2VzLmJyZWFrTGVuZ3RoIC8gNjA7XG4gICAgICBjb25zb2xlLmxvZyhicmVha0xlbmd0aEFzSG91cnMsICcgYnJlYWtMZW5ndGhBc0hvdXJzJyk7XG4gICAgICBjb25zdCBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUgPSBNYXRoLmZsb29yKFxuICAgICAgICBhY3R1YWxCcmVha0hvdXJzVG9HZW5lcmF0ZSAvIGJyZWFrTGVuZ3RoQXNIb3Vyc1xuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSwgJyBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUnKTtcblxuICAgICAgaWYgKG51bWJlck9mQnJlYWtzVG9HZW5lcmF0ZSA8IDEpIHtcbiAgICAgICAgY29uc29sZS5sb2coJ3Nob3VsZCBub3QgZ2VuZXJhdGUgYnJlYWtzJyk7XG4gICAgICAgIHJldHVybiBudWxsO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBldmVudE1pcnJvciA9IGFsbEV2ZW50cy5maW5kKChldmVudCkgPT4gIWV2ZW50LmlzQnJlYWspO1xuXG4gICAgICBjb25zdCBuZXdFdmVudHMgPSBnZW5lcmF0ZUJyZWFrcyhcbiAgICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgICBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsXG4gICAgICAgIGV2ZW50TWlycm9yLFxuICAgICAgICBnbG9iYWxDYWxlbmRhcklkXG4gICAgICApO1xuXG4gICAgICByZXR1cm4gbmV3RXZlbnRzO1xuICAgIH1cblxuICAgIGNvbnN0IGVuZFRpbWVzID0gdXNlclByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICk7XG5cbiAgICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgLy8gdmFsaWRhdGUgdmFsdWVzIGJlZm9yZSBjYWxjdWxhdGluZ1xuICAgIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgY29uc3Qgc3RhcnRNaW51dGUgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLm1pbnV0ZXM7XG5cbiAgICBjb25zdCB3b3JraW5nSG91cnMgPSBjb252ZXJ0VG9Ub3RhbFdvcmtpbmdIb3VycyhcbiAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIHRpbWV6b25lXG4gICAgKTtcbiAgICBjb25zdCBhbGxFdmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzRm9yRGF0ZShcbiAgICAgIHVzZXJJZCxcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyKVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAuZm9ybWF0KCksXG4gICAgICB0aW1lem9uZVxuICAgICk7XG4gICAgaWYgKCEoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICdubyBhbGxFdmVudHMgcHJlc2VudCBpbnNpZGUgc2hvdWxkR2VuZXJhdGVCcmVha0V2ZW50c0ZvckRheSdcbiAgICAgICk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gICAgY29uc3Qgc2hvdWxkR2VuZXJhdGVCcmVha3MgPSBzaG91bGRHZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgd29ya2luZ0hvdXJzLFxuICAgICAgdXNlclByZWZlcmVuY2VzLFxuICAgICAgYWxsRXZlbnRzXG4gICAgKTtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghc2hvdWxkR2VuZXJhdGVCcmVha3MpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdzaG91bGQgbm90IGdlbmVyYXRlIGJyZWFrcycpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgbGV0IGhvdXJzVXNlZCA9IDA7XG5cbiAgICBpZiAoYWxsRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBmb3IgKGNvbnN0IGFsbEV2ZW50IG9mIGFsbEV2ZW50cykge1xuICAgICAgICBjb25zdCBkdXJhdGlvbiA9IGRheWpzXG4gICAgICAgICAgLmR1cmF0aW9uKFxuICAgICAgICAgICAgZGF5anMoYWxsRXZlbnQuZW5kRGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgICAgLmRpZmYoZGF5anMoYWxsRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpKVxuICAgICAgICAgIClcbiAgICAgICAgICAuYXNIb3VycygpO1xuICAgICAgICBob3Vyc1VzZWQgKz0gZHVyYXRpb247XG4gICAgICB9XG4gICAgfVxuXG4gICAgbGV0IGhvdXJzQXZhaWxhYmxlID0gd29ya2luZ0hvdXJzIC0gaG91cnNVc2VkO1xuICAgIGhvdXJzQXZhaWxhYmxlIC09IHdvcmtpbmdIb3VycyAqIHVzZXJQcmVmZXJlbmNlcy5tYXhXb3JrTG9hZFBlcmNlbnQ7XG5cbiAgICAvLyBubyBob3VycyBhdmFpbGFibGVcbiAgICBpZiAoaG91cnNBdmFpbGFibGUgPD0gMCkge1xuICAgICAgY29uc29sZS5sb2coaG91cnNBdmFpbGFibGUsICcgbm8gaG91cnMgYXZhaWxhYmxlJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBjb25zdCBvbGRCcmVha0V2ZW50cyA9IGFsbEV2ZW50c1xuICAgICAgLmZpbHRlcigoZXZlbnQpID0+IGV2ZW50LmlzQnJlYWspXG4gICAgICAuZmlsdGVyKChlKSA9PlxuICAgICAgICBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuaXNTYW1lKGRheWpzKGUuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLCAnZGF5JylcbiAgICAgICk7XG5cbiAgICBjb25zdCBicmVha0V2ZW50cyA9IGV2ZW50c1RvQmVCcmVha3MuY29uY2F0KG9sZEJyZWFrRXZlbnRzKTtcblxuICAgIGNvbnN0IG51bWJlck9mQnJlYWtzUGVyRGF5ID0gdXNlclByZWZlcmVuY2VzLm1pbk51bWJlck9mQnJlYWtzO1xuICAgIGNvbnNvbGUubG9nKG51bWJlck9mQnJlYWtzUGVyRGF5LCAnIG51bWJlck9mQnJlYWtzUGVyRGF5Jyk7XG4gICAgY29uc3QgYnJlYWtIb3Vyc1RvR2VuZXJhdGUgPVxuICAgICAgKHVzZXJQcmVmZXJlbmNlcy5icmVha0xlbmd0aCAvIDYwKSAqIG51bWJlck9mQnJlYWtzUGVyRGF5O1xuICAgIGxldCBicmVha0hvdXJzVXNlZCA9IDA7XG5cbiAgICBpZiAoYnJlYWtFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGZvciAoY29uc3QgYnJlYWtFdmVudCBvZiBicmVha0V2ZW50cykge1xuICAgICAgICBjb25zdCBkdXJhdGlvbiA9IGRheWpzXG4gICAgICAgICAgLmR1cmF0aW9uKFxuICAgICAgICAgICAgZGF5anMoYnJlYWtFdmVudC5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAuZGlmZihkYXlqcyhicmVha0V2ZW50LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKSlcbiAgICAgICAgICApXG4gICAgICAgICAgLmFzSG91cnMoKTtcbiAgICAgICAgYnJlYWtIb3Vyc1VzZWQgKz0gZHVyYXRpb247XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgYWN0dWFsQnJlYWtIb3Vyc1RvR2VuZXJhdGUgPSBicmVha0hvdXJzVG9HZW5lcmF0ZSAtIGJyZWFrSG91cnNVc2VkO1xuXG4gICAgaWYgKGFjdHVhbEJyZWFrSG91cnNUb0dlbmVyYXRlID4gaG91cnNBdmFpbGFibGUpIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgbm8gaG91cnMgYXZhaWxhYmxlIHRvIGdlbmVyYXRlIGJyZWFrJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhicmVha0hvdXJzVXNlZCwgJyBicmVha0hvdXJzVXNlZCcpO1xuICAgIGNvbnNvbGUubG9nKGJyZWFrSG91cnNUb0dlbmVyYXRlLCAnIGJyZWFrSG91cnNBdmFpbGFibGUnKTtcbiAgICBjb25zdCBicmVha0xlbmd0aEFzSG91cnMgPSB1c2VyUHJlZmVyZW5jZXMuYnJlYWtMZW5ndGggLyA2MDtcbiAgICBjb25zb2xlLmxvZyhicmVha0xlbmd0aEFzSG91cnMsICcgYnJlYWtMZW5ndGhBc0hvdXJzJyk7XG4gICAgY29uc3QgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlID0gTWF0aC5mbG9vcihcbiAgICAgIGFjdHVhbEJyZWFrSG91cnNUb0dlbmVyYXRlIC8gYnJlYWtMZW5ndGhBc0hvdXJzXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsICcgbnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlJyk7XG5cbiAgICBpZiAobnVtYmVyT2ZCcmVha3NUb0dlbmVyYXRlIDwgMSkge1xuICAgICAgY29uc29sZS5sb2coJ3Nob3VsZCBub3QgZ2VuZXJhdGUgYnJlYWtzJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG5cbiAgICBjb25zdCBldmVudE1pcnJvciA9IGFsbEV2ZW50cy5maW5kKChldmVudCkgPT4gIWV2ZW50LmlzQnJlYWspO1xuXG4gICAgY29uc3QgbmV3RXZlbnRzID0gZ2VuZXJhdGVCcmVha3MoXG4gICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICBudW1iZXJPZkJyZWFrc1RvR2VuZXJhdGUsXG4gICAgICBldmVudE1pcnJvcixcbiAgICAgIGdsb2JhbENhbGVuZGFySWRcbiAgICApO1xuXG4gICAgcmV0dXJuIG5ld0V2ZW50cztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdlbmVyYXRlIGJyZWFrcyBmb3IgZGF5Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBhZGp1c3RTdGFydERhdGVzRm9yQnJlYWtFdmVudHNGb3JEYXkgPSAoXG4gIGFsbEV2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICBicmVha0V2ZW50czogRXZlbnRQbHVzVHlwZVtdLFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICB0aW1lem9uZTogc3RyaW5nXG4pOiBFdmVudFBsdXNUeXBlW10gPT4ge1xuICAvLyB2YWxpZGF0ZVxuICBpZiAoIWFsbEV2ZW50cz8uWzBdPy5pZCkge1xuICAgIGNvbnNvbGUubG9nKCdubyBhbGxFdmVudHMgaW5zaWRlIGFkanVzdFN0YXJ0RGF0ZXNGb3JCcmVha0V2ZW50cycpO1xuICAgIHJldHVybjtcbiAgfVxuXG4gIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZS5zdGFydFRpbWVzO1xuICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlLmVuZFRpbWVzO1xuICBjb25zdCBkYXlPZldlZWtJbnQgPSBnZXRJU09EYXkoXG4gICAgZGF5anMoYWxsRXZlbnRzPy5bMF0/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICApO1xuICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlID0gc3RhcnRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgY29uc3QgbmV3QnJlYWtFdmVudHMgPSBbXTtcbiAgLyoqXG4gICAgICogY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IHN0YXJ0SG91ciwgbWludXRlczogc3RhcnRNaW51dGUgfSlcbiAgICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oeyBob3VyczogZW5kSG91ciwgbWludXRlczogZW5kTWludXRlIH0pXG4gICAgICBjb25zdCB0b3RhbER1cmF0aW9uID0gZW5kRHVyYXRpb24uc3VidHJhY3Qoc3RhcnREdXJhdGlvbilcbiAgICAgIHJldHVybiB0b3RhbER1cmF0aW9uLmFzSG91cnMoKVxuICAgICAqL1xuXG4gIGNvbnN0IHN0YXJ0T2ZXb3JraW5nRGF5ID0gZGF5anMoYWxsRXZlbnRzWzBdPy5zdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAuaG91cihzdGFydEhvdXIpXG4gICAgLm1pbnV0ZShzdGFydE1pbnV0ZSk7XG5cbiAgY29uc3QgZW5kT2ZXb3JraW5nRGF5ID0gZGF5anMoYWxsRXZlbnRzWzBdPy5lbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgLmhvdXIoZW5kSG91cilcbiAgICAubWludXRlKGVuZE1pbnV0ZSk7XG5cbiAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSBhbGxFdmVudHMuZmlsdGVyKChlKSA9PiAhZS5pc0JyZWFrKTtcbiAgaWYgKGJyZWFrRXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgZm9yIChjb25zdCBicmVha0V2ZW50IG9mIGJyZWFrRXZlbnRzKSB7XG4gICAgICBsZXQgZm91bmRTcGFjZSA9IGZhbHNlO1xuICAgICAgbGV0IGluZGV4ID0gMDtcbiAgICAgIHdoaWxlICghZm91bmRTcGFjZSAmJiBpbmRleCA8IGZpbHRlcmVkRXZlbnRzLmxlbmd0aCkge1xuICAgICAgICBjb25zdCBwb3NzaWJsZUVuZERhdGUgPSBkYXlqcyhcbiAgICAgICAgICBmaWx0ZXJlZEV2ZW50c1tpbmRleF0uc3RhcnREYXRlLnNsaWNlKDAsIDE5KVxuICAgICAgICApLnR6KHRpbWV6b25lLCB0cnVlKTtcblxuICAgICAgICBjb25zdCBwb3NzaWJsZVN0YXJ0RGF0ZSA9IGRheWpzKHBvc3NpYmxlRW5kRGF0ZS5mb3JtYXQoKS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5zdWJ0cmFjdCh1c2VyUHJlZmVyZW5jZS5icmVha0xlbmd0aCwgJ21pbnV0ZScpO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuU3RhcnQgPSB0cnVlO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuRW5kID0gdHJ1ZTtcbiAgICAgICAgbGV0IGJldHdlZW5JbmRleCA9IDA7XG4gICAgICAgIGxldCBiZXR3ZWVuV29ya2luZ0RheVN0YXJ0ID0gdHJ1ZTtcbiAgICAgICAgbGV0IGJldHdlZW5Xb3JraW5nRGF5RW5kID0gdHJ1ZTtcbiAgICAgICAgbGV0IGlzQmV0d2VlbkJyZWFrU3RhcnQgPSB0cnVlO1xuICAgICAgICBsZXQgaXNCZXR3ZWVuQnJlYWtFbmQgPSB0cnVlO1xuXG4gICAgICAgIHdoaWxlIChcbiAgICAgICAgICAoaXNCZXR3ZWVuU3RhcnQgfHxcbiAgICAgICAgICAgIGlzQmV0d2VlbkVuZCB8fFxuICAgICAgICAgICAgIWJldHdlZW5Xb3JraW5nRGF5U3RhcnQgfHxcbiAgICAgICAgICAgICFiZXR3ZWVuV29ya2luZ0RheUVuZCB8fFxuICAgICAgICAgICAgaXNCZXR3ZWVuQnJlYWtTdGFydCB8fFxuICAgICAgICAgICAgaXNCZXR3ZWVuQnJlYWtFbmQpICYmXG4gICAgICAgICAgYmV0d2VlbkluZGV4IDwgZmlsdGVyZWRFdmVudHMubGVuZ3RoXG4gICAgICAgICkge1xuICAgICAgICAgIGlzQmV0d2VlblN0YXJ0ID0gcG9zc2libGVTdGFydERhdGUuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMoZmlsdGVyZWRFdmVudHNbYmV0d2VlbkluZGV4XS5zdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICksXG4gICAgICAgICAgICBkYXlqcyhmaWx0ZXJlZEV2ZW50c1tiZXR3ZWVuSW5kZXhdLmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgIHRydWVcbiAgICAgICAgICAgICksXG4gICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICdbKSdcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgaXNCZXR3ZWVuRW5kID0gcG9zc2libGVFbmREYXRlLmlzQmV0d2VlbihcbiAgICAgICAgICAgIGRheWpzKGZpbHRlcmVkRXZlbnRzW2JldHdlZW5JbmRleF0uc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICApLFxuICAgICAgICAgICAgZGF5anMoZmlsdGVyZWRFdmVudHNbYmV0d2VlbkluZGV4XS5lbmREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICB0cnVlXG4gICAgICAgICAgICApLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnKF0nXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGJldHdlZW5Xb3JraW5nRGF5U3RhcnQgPSBwb3NzaWJsZVN0YXJ0RGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICBzdGFydE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgIGVuZE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgICBiZXR3ZWVuV29ya2luZ0RheUVuZCA9IHBvc3NpYmxlRW5kRGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICBzdGFydE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgIGVuZE9mV29ya2luZ0RheSxcbiAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgJyhdJ1xuICAgICAgICAgICk7XG5cbiAgICAgICAgICBmb3IgKGNvbnN0IGJyZWFrRXZlbnQgb2YgYnJlYWtFdmVudHMpIHtcbiAgICAgICAgICAgIGlzQmV0d2VlbkJyZWFrU3RhcnQgPSBwb3NzaWJsZVN0YXJ0RGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICBpc0JldHdlZW5CcmVha0VuZCA9IHBvc3NpYmxlRW5kRGF0ZS5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKGJyZWFrRXZlbnQuc3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLFxuICAgICAgICAgICAgICBkYXlqcyhicmVha0V2ZW50LmVuZERhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnKF0nXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGJldHdlZW5JbmRleCsrO1xuICAgICAgICB9XG5cbiAgICAgICAgZm91bmRTcGFjZSA9XG4gICAgICAgICAgIWlzQmV0d2VlblN0YXJ0ICYmXG4gICAgICAgICAgIWlzQmV0d2VlbkVuZCAmJlxuICAgICAgICAgIGJldHdlZW5Xb3JraW5nRGF5U3RhcnQgJiZcbiAgICAgICAgICBiZXR3ZWVuV29ya2luZ0RheUVuZCAmJlxuICAgICAgICAgICFpc0JldHdlZW5CcmVha1N0YXJ0ICYmXG4gICAgICAgICAgIWlzQmV0d2VlbkJyZWFrRW5kO1xuXG4gICAgICAgIGlmIChmb3VuZFNwYWNlKSB7XG4gICAgICAgICAgY29uc3QgbmV3QnJlYWtFdmVudCA9IHtcbiAgICAgICAgICAgIC4uLmJyZWFrRXZlbnQsXG4gICAgICAgICAgICBzdGFydERhdGU6IHBvc3NpYmxlU3RhcnREYXRlLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBlbmREYXRlOiBwb3NzaWJsZUVuZERhdGUudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICB9O1xuICAgICAgICAgIG5ld0JyZWFrRXZlbnRzLnB1c2gobmV3QnJlYWtFdmVudCk7XG4gICAgICAgIH1cblxuICAgICAgICBpbmRleCsrO1xuICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIHJldHVybiBuZXdCcmVha0V2ZW50cztcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yRGF0ZSA9IGFzeW5jIChcbiAgdXNlclByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBldmVudHNUb0JlQnJlYWtzOiBFdmVudFBsdXNUeXBlW10gPSBbXSxcbiAgZ2xvYmFsQ2FsZW5kYXJJZD86IHN0cmluZ1xuKTogUHJvbWlzZTxFdmVudFBsdXNUeXBlW10gfCBbXT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRvdGFsQnJlYWtFdmVudHMgPSBbXTtcbiAgICBjb25zdCB0b3RhbERheXMgPSBkYXlqcyhlbmREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5kaWZmKGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKSwgJ2RheScpO1xuICAgIGNvbnNvbGUubG9nKHRvdGFsRGF5cywgJyB0b3RhbERheXMgaW5zaWRlIGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXRlJyk7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbERheXM7IGkrKykge1xuICAgICAgY29uc3QgZGF5RGF0ZSA9IGRheWpzKHN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmFkZChpLCAnZGF5JylcbiAgICAgICAgLmZvcm1hdCgpO1xuICAgICAgY29uc3QgZXZlbnRzVG9CZUJyZWFrc0ZvckRheSA9IGV2ZW50c1RvQmVCcmVha3MuZmlsdGVyKChlKSA9PlxuICAgICAgICBkYXlqcyhlLnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGUudGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmlzU2FtZShkYXlEYXRlLCAnZGF5JylcbiAgICAgICk7XG4gICAgICBjb25zdCBuZXdCcmVha0V2ZW50cyA9IGF3YWl0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JEYXkoXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBkYXlEYXRlLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZXZlbnRzVG9CZUJyZWFrc0ZvckRheSxcbiAgICAgICAgZ2xvYmFsQ2FsZW5kYXJJZCxcbiAgICAgICAgaSA9PT0gMFxuICAgICAgKTtcblxuICAgICAgaWYgKGkgPT09IDApIHtcbiAgICAgICAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuZW5kVGltZXM7XG4gICAgICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICAgICAgICk7XG5cbiAgICAgICAgbGV0IHN0YXJ0SG91ciA9IGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKS50eih0aW1lem9uZSwgdHJ1ZSkuaG91cigpO1xuICAgICAgICBsZXQgc3RhcnRNaW51dGUgPSBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLm1pbnV0ZSgpO1xuICAgICAgICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICAgICAgY29uc3QgZW5kTWludXRlID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcblxuICAgICAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgICAgIGNvbnN0IHN0YXJ0VGltZXMgPSB1c2VyUHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgICAgICAgY29uc3Qgd29ya1N0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICAgICApLmhvdXI7XG4gICAgICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgICAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludFxuICAgICAgICApLm1pbnV0ZXM7XG5cbiAgICAgICAgaWYgKFxuICAgICAgICAgIGRheWpzKGRheURhdGUuc2xpY2UoMCwgMTkpKS5pc0FmdGVyKFxuICAgICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLmhvdXIoZW5kSG91cikubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICApXG4gICAgICAgICkge1xuICAgICAgICAgIC8vIHJldHVybiBlbXB0eSBhcyBvdXRzaWRlIG9mIHdvcmsgdGltZVxuICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICB9XG5cbiAgICAgICAgLy8gY2hhbmdlIHRvIHdvcmsgc3RhcnQgdGltZSBhcyBiZWZvcmUgc3RhcnQgdGltZVxuICAgICAgICBpZiAoXG4gICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLmlzQmVmb3JlKFxuICAgICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXIpXG4gICAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlKVxuICAgICAgICAgIClcbiAgICAgICAgKSB7XG4gICAgICAgICAgc3RhcnRIb3VyID0gd29ya1N0YXJ0SG91cjtcbiAgICAgICAgICBzdGFydE1pbnV0ZSA9IHdvcmtTdGFydE1pbnV0ZTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IGFsbEV2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICBkYXlqcyhkYXlEYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGUpXG4gICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgbmV3QnJlYWtFdmVudHNBZGp1c3RlZCA9XG4gICAgICAgICAgYXdhaXQgYWRqdXN0U3RhcnREYXRlc0ZvckJyZWFrRXZlbnRzRm9yRGF5KFxuICAgICAgICAgICAgYWxsRXZlbnRzLFxuICAgICAgICAgICAgbmV3QnJlYWtFdmVudHMsXG4gICAgICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICk7XG4gICAgICAgIGlmIChuZXdCcmVha0V2ZW50c0FkanVzdGVkPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgbmV3QnJlYWtFdmVudHNBZGp1c3RlZC5mb3JFYWNoKChiKSA9PlxuICAgICAgICAgICAgY29uc29sZS5sb2coYiwgJyBuZXdCcmVha0V2ZW50c0FkanVzdGVkJylcbiAgICAgICAgICApO1xuICAgICAgICAgIHRvdGFsQnJlYWtFdmVudHMucHVzaCguLi5uZXdCcmVha0V2ZW50c0FkanVzdGVkKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBlbmRUaW1lcyA9IHVzZXJQcmVmZXJlbmNlcy5lbmRUaW1lcztcbiAgICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGdldElTT0RheShcbiAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKVxuICAgICAgKTtcblxuICAgICAgY29uc3QgZW5kSG91ciA9IGVuZFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgICBjb25zdCBzdGFydEhvdXIgPSBzdGFydFRpbWVzLmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnQpLmhvdXI7XG4gICAgICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZChcbiAgICAgICAgKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRcbiAgICAgICkubWludXRlcztcblxuICAgICAgY29uc3QgYWxsRXZlbnRzID0gYXdhaXQgbGlzdEV2ZW50c0ZvckRhdGUoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZGF5anMoZGF5RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5ob3VyKGVuZEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGUpXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICB0aW1lem9uZVxuICAgICAgKTtcbiAgICAgIGNvbnN0IG5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQgPSBhd2FpdCBhZGp1c3RTdGFydERhdGVzRm9yQnJlYWtFdmVudHNGb3JEYXkoXG4gICAgICAgIGFsbEV2ZW50cyxcbiAgICAgICAgbmV3QnJlYWtFdmVudHMsXG4gICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgdGltZXpvbmVcbiAgICAgICk7XG4gICAgICBpZiAobmV3QnJlYWtFdmVudHNBZGp1c3RlZD8ubGVuZ3RoID4gMCkge1xuICAgICAgICBuZXdCcmVha0V2ZW50c0FkanVzdGVkLmZvckVhY2goKGIpID0+XG4gICAgICAgICAgY29uc29sZS5sb2coYiwgJyBuZXdCcmVha0V2ZW50c0FkanVzdGVkJylcbiAgICAgICAgKTtcbiAgICAgICAgdG90YWxCcmVha0V2ZW50cy5wdXNoKC4uLm5ld0JyZWFrRXZlbnRzQWRqdXN0ZWQpO1xuICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiB0b3RhbEJyZWFrRXZlbnRzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2VuZXJhdGVCcmVha0V2ZW50c0ZvckRhdGUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydEV2ZW50c1Bvc3RQbGFubmVyID0gYXN5bmMgKGV2ZW50czogRXZlbnRUeXBlW10pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0luc2VydEV2ZW50JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIG11dGF0aW9uIEluc2VydEV2ZW50KCRldmVudHM6IFtFdmVudF9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgaW5zZXJ0X0V2ZW50KFxuICAgICAgICAgICAgb2JqZWN0czogJGV2ZW50cyxcbiAgICAgICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgICAgICAgY29uc3RyYWludDogRXZlbnRfcGtleSxcbiAgICAgICAgICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlLFxuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGUsXG4gICAgICAgICAgICAgICAgICAgIGVuZERhdGUsXG4gICAgICAgICAgICAgICAgICAgIGFsbERheSxcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGUsXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uLFxuICAgICAgICAgICAgICAgICAgICBub3RlcyxcbiAgICAgICAgICAgICAgICAgICAgYXR0YWNobWVudHMsXG4gICAgICAgICAgICAgICAgICAgIGxpbmtzLFxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGUsXG4gICAgICAgICAgICAgICAgICAgIGRlbGV0ZWQsXG4gICAgICAgICAgICAgICAgICAgIHRhc2tJZCxcbiAgICAgICAgICAgICAgICAgICAgdGFza1R5cGUsXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5LFxuICAgICAgICAgICAgICAgICAgICBmb2xsb3dVcEV2ZW50SWQsXG4gICAgICAgICAgICAgICAgICAgIGlzRm9sbG93VXAsXG4gICAgICAgICAgICAgICAgICAgIGlzUHJlRXZlbnQsXG4gICAgICAgICAgICAgICAgICAgIGlzUG9zdEV2ZW50LFxuICAgICAgICAgICAgICAgICAgICBwcmVFdmVudElkLFxuICAgICAgICAgICAgICAgICAgICBwb3N0RXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZSxcbiAgICAgICAgICAgICAgICAgICAgZm9yRXZlbnRJZCxcbiAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkLFxuICAgICAgICAgICAgICAgICAgICBtYXhBdHRlbmRlZXMsXG4gICAgICAgICAgICAgICAgICAgIHNlbmRVcGRhdGVzLFxuICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXksXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1cyxcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeSxcbiAgICAgICAgICAgICAgICAgICAgdHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5LFxuICAgICAgICAgICAgICAgICAgICByZWN1cnJpbmdFdmVudElkLFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICAgICAgICAgIGlDYWxVSUQsXG4gICAgICAgICAgICAgICAgICAgIGh0bWxMaW5rLFxuICAgICAgICAgICAgICAgICAgICBjb2xvcklkLFxuICAgICAgICAgICAgICAgICAgICBjcmVhdG9yLFxuICAgICAgICAgICAgICAgICAgICBvcmdhbml6ZXIsXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZCxcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZSxcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZSxcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVzT21pdHRlZCxcbiAgICAgICAgICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzLFxuICAgICAgICAgICAgICAgICAgICBoYW5nb3V0TGluayxcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgICAgICAgICBsb2NrZWQsXG4gICAgICAgICAgICAgICAgICAgIHNvdXJjZSxcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRUeXBlLFxuICAgICAgICAgICAgICAgICAgICBwcml2YXRlQ29weSxcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yLFxuICAgICAgICAgICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3IsXG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXMsXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmUsXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmUsXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZERheU9mV2VlayxcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZSxcbiAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgICAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nLFxuICAgICAgICAgICAgICAgICAgICBkYWlseVRhc2tMaXN0LFxuICAgICAgICAgICAgICAgICAgICB3ZWVrbHlUYXNrTGlzdCxcbiAgICAgICAgICAgICAgICAgICAgaXNCcmVhayxcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICAgICAgICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eSxcbiAgICAgICAgICAgICAgICAgICAgY29weVRpbWVCbG9ja2luZyxcbiAgICAgICAgICAgICAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlLFxuICAgICAgICAgICAgICAgICAgICBjb3B5UmVtaW5kZXJzLFxuICAgICAgICAgICAgICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbCxcbiAgICAgICAgICAgICAgICAgICAgY29weU1vZGlmaWFibGUsXG4gICAgICAgICAgICAgICAgICAgIGNvcHlDYXRlZ29yaWVzLFxuICAgICAgICAgICAgICAgICAgICBjb3B5SXNCcmVhayxcbiAgICAgICAgICAgICAgICAgICAgdGltZUJsb2NraW5nLFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHksXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZyxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UsXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFJlbWluZGVycyxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbCxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllcyxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZSxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNCcmVhayxcbiAgICAgICAgICAgICAgICAgICAgaGFyZERlYWRsaW5lLFxuICAgICAgICAgICAgICAgICAgICBzb2Z0RGVhZGxpbmUsXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmcsXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZyxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nLFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZyxcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb24sXG4gICAgICAgICAgICAgICAgICAgIGNvcHlEdXJhdGlvbixcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb24sXG4gICAgICAgICAgICAgICAgICAgIG1ldGhvZCxcbiAgICAgICAgICAgICAgICAgICAgdW5saW5rLFxuICAgICAgICAgICAgICAgICAgICBjb3B5Q29sb3IsXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENvbG9yLFxuICAgICAgICAgICAgICAgICAgICBieVdlZWtEYXksXG4gICAgICAgICAgICAgICAgICAgIGxvY2FsU3luY2VkLFxuICAgICAgICAgICAgICAgIF1cbiAgICAgICAgICAgIH0pe1xuICAgICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIGA7XG4gICAgXy51bmlxQnkoZXZlbnRzLCAnaWQnKS5mb3JFYWNoKChlKSA9PlxuICAgICAgY29uc29sZS5sb2coZT8uaWQsIGUsICdpZCwgZSBpbnNpZGUgdXBzZXJ0RXZlbnRzUG9zdFBsYW5uZXIgJylcbiAgICApO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGV2ZW50czogXy51bmlxQnkoZXZlbnRzLCAnaWQnKSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgaW5zZXJ0X0V2ZW50OiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlcjsgcmV0dXJuaW5nOiB7IGlkOiBzdHJpbmcgfVtdIH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlc3BvbnNlLFxuICAgICAgcmVzcG9uc2U/LmRhdGE/Lmluc2VydF9FdmVudD8uYWZmZWN0ZWRfcm93cyxcbiAgICAgICcgcmVzcG9uc2UgYWZ0ZXIgdXBzZXJ0aW5nIGV2ZW50cydcbiAgICApO1xuICAgIHJlc3BvbnNlPy5kYXRhPy5pbnNlcnRfRXZlbnQ/LnJldHVybmluZz8uZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgcmV0dXJuaW5nICByZXNwb25zZSBhZnRlciB1cHNlcnRpbmcgZXZlbnRzJylcbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZm9ybWF0UmVtaW5kZXJzRm9yR29vZ2xlID0gKFxuICByZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdXG4pOiBHb29nbGVSZW1pbmRlclR5cGUgPT4ge1xuICBjb25zdCBnb29nbGVPdmVycmlkZXM6IE92ZXJyaWRlVHlwZXMgPSByZW1pbmRlcnMubWFwKChyZW1pbmRlcikgPT4ge1xuICAgIHJldHVybiB7XG4gICAgICBtZXRob2Q6ICdlbWFpbCcsXG4gICAgICBtaW51dGVzOiByZW1pbmRlci5taW51dGVzLFxuICAgIH07XG4gIH0pO1xuICBjb25zdCBnb29nbGVSZW1pbmRlcnM6IEdvb2dsZVJlbWluZGVyVHlwZSA9IHtcbiAgICBvdmVycmlkZXM6IGdvb2dsZU92ZXJyaWRlcyxcbiAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgfTtcbiAgcmV0dXJuIGdvb2dsZVJlbWluZGVycztcbn07XG5cbmV4cG9ydCBjb25zdCByZWZyZXNoR29vZ2xlVG9rZW4gPSBhc3luYyAoXG4gIHJlZnJlc2hUb2tlbjogc3RyaW5nLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pOiBQcm9taXNlPHtcbiAgYWNjZXNzX3Rva2VuOiBzdHJpbmc7XG4gIGV4cGlyZXNfaW46IG51bWJlcjsgLy8gYWRkIHNlY29uZHMgdG8gbm93XG4gIHNjb3BlOiBzdHJpbmc7XG4gIHRva2VuX3R5cGU6IHN0cmluZztcbn0+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZygncmVmcmVzaEdvb2dsZVRva2VuIGNhbGxlZCcsIHJlZnJlc2hUb2tlbik7XG4gICAgY29uc29sZS5sb2coJ2NsaWVudFR5cGUnLCBjbGllbnRUeXBlKTtcbiAgICBjb25zb2xlLmxvZygnZ29vZ2xlQ2xpZW50SWRJb3MnLCBnb29nbGVDbGllbnRJZElvcyk7XG4gICAgc3dpdGNoIChjbGllbnRUeXBlKSB7XG4gICAgICBjYXNlICdpb3MnOlxuICAgICAgICByZXR1cm4gZ290XG4gICAgICAgICAgLnBvc3QoZ29vZ2xlVG9rZW5VcmwsIHtcbiAgICAgICAgICAgIGZvcm06IHtcbiAgICAgICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgICAgIGNsaWVudF9pZDogZ29vZ2xlQ2xpZW50SWRJb3MsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL3gtd3d3LWZvcm0tdXJsZW5jb2RlZCcsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pXG4gICAgICAgICAgLmpzb24oKTtcbiAgICAgIGNhc2UgJ2FuZHJvaWQnOlxuICAgICAgICByZXR1cm4gZ290XG4gICAgICAgICAgLnBvc3QoZ29vZ2xlVG9rZW5VcmwsIHtcbiAgICAgICAgICAgIGZvcm06IHtcbiAgICAgICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgICAgIGNsaWVudF9pZDogZ29vZ2xlQ2xpZW50SWRBbmRyb2lkLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KVxuICAgICAgICAgIC5qc29uKCk7XG4gICAgICBjYXNlICd3ZWInOlxuICAgICAgICByZXR1cm4gZ290XG4gICAgICAgICAgLnBvc3QoZ29vZ2xlVG9rZW5VcmwsIHtcbiAgICAgICAgICAgIGZvcm06IHtcbiAgICAgICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgICAgICByZWZyZXNoX3Rva2VuOiByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgICAgIGNsaWVudF9pZDogZ29vZ2xlQ2xpZW50SWRXZWIsXG4gICAgICAgICAgICAgIGNsaWVudF9zZWNyZXQ6IGdvb2dsZUNsaWVudFNlY3JldFdlYixcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24veC13d3ctZm9ybS11cmxlbmNvZGVkJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSlcbiAgICAgICAgICAuanNvbigpO1xuICAgICAgY2FzZSAnYXRvbWljLXdlYic6XG4gICAgICAgIHJldHVybiBnb3RcbiAgICAgICAgICAucG9zdChnb29nbGVUb2tlblVybCwge1xuICAgICAgICAgICAgZm9ybToge1xuICAgICAgICAgICAgICBncmFudF90eXBlOiAncmVmcmVzaF90b2tlbicsXG4gICAgICAgICAgICAgIHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbixcbiAgICAgICAgICAgICAgY2xpZW50X2lkOiBnb29nbGVDbGllbnRJZEF0b21pY1dlYixcbiAgICAgICAgICAgICAgY2xpZW50X3NlY3JldDogZ29vZ2xlQ2xpZW50U2VjcmV0QXRvbWljV2ViLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi94LXd3dy1mb3JtLXVybGVuY29kZWQnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KVxuICAgICAgICAgIC5qc29uKCk7XG4gICAgfVxuXG4gICAgLypcbiAgICAgICAge1xuICAgICAgICAgIFwiYWNjZXNzX3Rva2VuXCI6IFwiMS9mRkFHUk5KcnUxRlR6NzBCemhUM1pnXCIsXG4gICAgICAgICAgXCJleHBpcmVzX2luXCI6IDM5MjAsIC8vIGFkZCBzZWNvbmRzIHRvIG5vd1xuICAgICAgICAgIFwic2NvcGVcIjogXCJodHRwczovL3d3dy5nb29nbGVhcGlzLmNvbS9hdXRoL2RyaXZlLm1ldGFkYXRhLnJlYWRvbmx5XCIsXG4gICAgICAgICAgXCJ0b2tlbl90eXBlXCI6IFwiQmVhcmVyXCJcbiAgICAgICAgfVxuICAgICAgICAqL1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcmVmcmVzaCBnb29nbGUgdG9rZW4nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24gPSBhc3luYyAoXG4gIGlkOiBzdHJpbmcsXG4gIHRva2VuPzogc3RyaW5nLFxuICBleHBpcmVzSW4/OiBudW1iZXIsXG4gIGVuYWJsZWQ/OiBib29sZWFuXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ3VwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24nO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgbXV0YXRpb24gdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbigkaWQ6IHV1aWQhLCR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICcgJHRva2VuOiBTdHJpbmcsJyA6ICcnfSR7ZXhwaXJlc0luICE9PSB1bmRlZmluZWQgPyAnICRleHBpcmVzQXQ6IHRpbWVzdGFtcHR6LCcgOiAnJ30ke2VuYWJsZWQgIT09IHVuZGVmaW5lZCA/ICcgJGVuYWJsZWQ6IEJvb2xlYW4sJyA6ICcnfSkge1xuICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiB7JHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJ3Rva2VuOiAkdG9rZW4sJyA6ICcnfSR7ZXhwaXJlc0luICE9PSB1bmRlZmluZWQgPyAnIGV4cGlyZXNBdDogJGV4cGlyZXNBdCwnIDogJyd9JHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnIGVuYWJsZWQ6ICRlbmFibGVkLCcgOiAnJ319KSB7XG4gICAgICAgICAgaWRcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgICAgdG9rZW4sXG4gICAgICBleHBpcmVzQXQ6IGRheWpzKCkuYWRkKGV4cGlyZXNJbiwgJ3NlY29uZHMnKS50b0lTT1N0cmluZygpLFxuICAgICAgZW5hYmxlZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24nKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSBjYWxlbmRhciBpbnRlZ3JhdGlvbicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbiA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHJlc291cmNlOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBxdWVyeSBnZXRDYWxlbmRhckludGVncmF0aW9uKCR1c2VySWQ6IHV1aWQhLCAkcmVzb3VyY2U6IFN0cmluZyEpIHtcbiAgICAgICAgQ2FsZW5kYXJfSW50ZWdyYXRpb24od2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCByZXNvdXJjZToge19lcTogJHJlc291cmNlfX0pIHtcbiAgICAgICAgICB0b2tlblxuICAgICAgICAgIGV4cGlyZXNBdFxuICAgICAgICAgIGlkXG4gICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgY2xpZW50VHlwZVxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICByZXNvdXJjZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgQ2FsZW5kYXJfSW50ZWdyYXRpb246IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGdldENhbGVuZGFySW50ZWdyYXRpb24nKTtcbiAgICBpZiAocmVzPy5kYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8ubGVuZ3RoID4gMCkge1xuICAgICAgcmV0dXJuIHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/LlswXTtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgY2FsZW5kYXIgaW50ZWdyYXRpb24nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEdvb2dsZUFQSVRva2VuID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcmVzb3VyY2U6IHN0cmluZyxcbiAgY2xpZW50VHlwZTogJ2lvcycgfCAnYW5kcm9pZCcgfCAnd2ViJyB8ICdhdG9taWMtd2ViJ1xuKSA9PiB7XG4gIGxldCBpbnRlZ3JhdGlvbklkID0gJyc7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBpZCwgdG9rZW4sIGV4cGlyZXNBdCwgcmVmcmVzaFRva2VuIH0gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uKFxuICAgICAgdXNlcklkLFxuICAgICAgcmVzb3VyY2VcbiAgICApO1xuICAgIGludGVncmF0aW9uSWQgPSBpZDtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGlkLFxuICAgICAgdG9rZW4sXG4gICAgICBleHBpcmVzQXQsXG4gICAgICByZWZyZXNoVG9rZW4sXG4gICAgICAnIGlkLCB0b2tlbiwgZXhwaXJlc0F0LCByZWZyZXNoVG9rZW4nXG4gICAgKTtcbiAgICBpZiAoZGF5anMoKS5pc0FmdGVyKGRheWpzKGV4cGlyZXNBdCkpIHx8ICF0b2tlbikge1xuICAgICAgY29uc3QgcmVzID0gYXdhaXQgcmVmcmVzaEdvb2dsZVRva2VuKHJlZnJlc2hUb2tlbiwgY2xpZW50VHlwZSk7XG4gICAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gcmVmcmVzaEdvb2dsZVRva2VuJyk7XG4gICAgICBhd2FpdCB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKGlkLCByZXMuYWNjZXNzX3Rva2VuLCByZXMuZXhwaXJlc19pbik7XG4gICAgICByZXR1cm4gcmVzLmFjY2Vzc190b2tlbjtcbiAgICB9XG4gICAgcmV0dXJuIHRva2VuO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGFwaSB0b2tlbicpO1xuICAgIGF3YWl0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oaW50ZWdyYXRpb25JZCwgbnVsbCwgbnVsbCwgZmFsc2UpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcGF0Y2hHb29nbGVFdmVudCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgZXZlbnRJZDogc3RyaW5nLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInLFxuICBlbmREYXRlVGltZT86IHN0cmluZywgLy8gZWl0aGVyIGVuZERhdGVUaW1lIG9yIGVuZERhdGUgLSBhbGwgZGF5IHZzIHNwZWNpZmljIHBlcmlvZFxuICBzdGFydERhdGVUaW1lPzogc3RyaW5nLFxuICBjb25mZXJlbmNlRGF0YVZlcnNpb24/OiAwIHwgMSxcbiAgbWF4QXR0ZW5kZWVzPzogbnVtYmVyLFxuICBzZW5kVXBkYXRlcz86IEdvb2dsZVNlbmRVcGRhdGVzVHlwZSxcbiAgYW55b25lQ2FuQWRkU2VsZj86IGJvb2xlYW4sXG4gIGF0dGVuZGVlcz86IEdvb2dsZUF0dGVuZGVlVHlwZVtdLFxuICBjb25mZXJlbmNlRGF0YT86IEdvb2dsZUNvbmZlcmVuY2VEYXRhVHlwZSxcbiAgc3VtbWFyeT86IHN0cmluZyxcbiAgZGVzY3JpcHRpb24/OiBzdHJpbmcsXG4gIHRpbWV6b25lPzogc3RyaW5nLCAvLyByZXF1aXJlZCBmb3IgcmVjdXJyZW5jZVxuICBzdGFydERhdGU/OiBzdHJpbmcsXG4gIGVuZERhdGU/OiBzdHJpbmcsXG4gIGV4dGVuZGVkUHJvcGVydGllcz86IEdvb2dsZUV4dGVuZGVkUHJvcGVydGllc1R5cGUsXG4gIGd1ZXN0c0Nhbkludml0ZU90aGVycz86IGJvb2xlYW4sXG4gIGd1ZXN0c0Nhbk1vZGlmeT86IGJvb2xlYW4sXG4gIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzPzogYm9vbGVhbixcbiAgb3JpZ2luYWxTdGFydERhdGVUaW1lPzogc3RyaW5nLFxuICBvcmlnaW5hbFN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgcmVjdXJyZW5jZT86IHN0cmluZ1tdLFxuICByZW1pbmRlcnM/OiBHb29nbGVSZW1pbmRlclR5cGUsXG4gIHNvdXJjZT86IEdvb2dsZVNvdXJjZVR5cGUsXG4gIHN0YXR1cz86IHN0cmluZyxcbiAgdHJhbnNwYXJlbmN5PzogR29vZ2xlVHJhbnNwYXJlbmN5VHlwZSxcbiAgdmlzaWJpbGl0eT86IEdvb2dsZVZpc2liaWxpdHlUeXBlLFxuICBpQ2FsVUlEPzogc3RyaW5nLFxuICBhdHRlbmRlZXNPbWl0dGVkPzogYm9vbGVhbixcbiAgaGFuZ291dExpbms/OiBzdHJpbmcsXG4gIHByaXZhdGVDb3B5PzogYm9vbGVhbixcbiAgbG9ja2VkPzogYm9vbGVhbixcbiAgYXR0YWNobWVudHM/OiBHb29nbGVBdHRhY2htZW50VHlwZVtdLFxuICBldmVudFR5cGU/OiBHb29nbGVFdmVudFR5cGUxLFxuICBsb2NhdGlvbj86IHN0cmluZyxcbiAgY29sb3JJZD86IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHRva2VuID1cbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZUFQSVRva2VuKFxuICAgICAgdXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJSZXNvdXJjZSxcbiAgICAgIGNsaWVudFR5cGVcbiAgICApO1xuICAgIC8vIGxldCB1cmwgPSBgJHtnb29nbGVVcmx9LyR7ZW5jb2RlVVJJKGNhbGVuZGFySWQpfS9ldmVudHMvJHtlbmNvZGVVUkkoZXZlbnRJZCl9YFxuXG4gICAgLy8gY29uc3QgY29uZmlnID0ge1xuICAgIC8vICAgaGVhZGVyczoge1xuICAgIC8vICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAvLyAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAvLyAgICAgJ0FjY2VwdCc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAvLyAgIH0sXG4gICAgLy8gfVxuXG4gICAgY29uc3QgZ29vZ2xlQ2FsZW5kYXIgPSBnb29nbGUuY2FsZW5kYXIoe1xuICAgICAgdmVyc2lvbjogJ3YzJyxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgbGV0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgLy8gQ2FsZW5kYXIgaWRlbnRpZmllci4gVG8gcmV0cmlldmUgY2FsZW5kYXIgSURzIGNhbGwgdGhlIGNhbGVuZGFyTGlzdC5saXN0IG1ldGhvZC4gSWYgeW91IHdhbnQgdG8gYWNjZXNzIHRoZSBwcmltYXJ5IGNhbGVuZGFyIG9mIHRoZSBjdXJyZW50bHkgbG9nZ2VkIGluIHVzZXIsIHVzZSB0aGUgXCJwcmltYXJ5XCIga2V5d29yZC5cbiAgICAgIGNhbGVuZGFySWQsXG4gICAgICAvLyBWZXJzaW9uIG51bWJlciBvZiBjb25mZXJlbmNlIGRhdGEgc3VwcG9ydGVkIGJ5IHRoZSBBUEkgY2xpZW50LiBWZXJzaW9uIDAgYXNzdW1lcyBubyBjb25mZXJlbmNlIGRhdGEgc3VwcG9ydCBhbmQgaWdub3JlcyBjb25mZXJlbmNlIGRhdGEgaW4gdGhlIGV2ZW50J3MgYm9keS4gVmVyc2lvbiAxIGVuYWJsZXMgc3VwcG9ydCBmb3IgY29weWluZyBvZiBDb25mZXJlbmNlRGF0YSBhcyB3ZWxsIGFzIGZvciBjcmVhdGluZyBuZXcgY29uZmVyZW5jZXMgdXNpbmcgdGhlIGNyZWF0ZVJlcXVlc3QgZmllbGQgb2YgY29uZmVyZW5jZURhdGEuIFRoZSBkZWZhdWx0IGlzIDAuXG4gICAgICBjb25mZXJlbmNlRGF0YVZlcnNpb24sXG4gICAgICAvLyBFdmVudCBpZGVudGlmaWVyLlxuICAgICAgZXZlbnRJZCxcbiAgICAgIC8vIFRoZSBtYXhpbXVtIG51bWJlciBvZiBhdHRlbmRlZXMgdG8gaW5jbHVkZSBpbiB0aGUgcmVzcG9uc2UuIElmIHRoZXJlIGFyZSBtb3JlIHRoYW4gdGhlIHNwZWNpZmllZCBudW1iZXIgb2YgYXR0ZW5kZWVzLCBvbmx5IHRoZSBwYXJ0aWNpcGFudCBpcyByZXR1cm5lZC4gT3B0aW9uYWwuXG4gICAgICBtYXhBdHRlbmRlZXMsXG4gICAgICAvLyBHdWVzdHMgd2hvIHNob3VsZCByZWNlaXZlIG5vdGlmaWNhdGlvbnMgYWJvdXQgdGhlIGV2ZW50IHVwZGF0ZSAoZm9yIGV4YW1wbGUsIHRpdGxlIGNoYW5nZXMsIGV0Yy4pLlxuICAgICAgc2VuZFVwZGF0ZXMsXG4gICAgICAvLyBSZXF1ZXN0IGJvZHkgbWV0YWRhdGFcbiAgICAgIHJlcXVlc3RCb2R5OiB7XG4gICAgICAgIC8vIHJlcXVlc3QgYm9keSBwYXJhbWV0ZXJzXG4gICAgICAgIC8vIHtcbiAgICAgICAgLy8gICBcImFueW9uZUNhbkFkZFNlbGZcIjogZmFsc2UsXG4gICAgICAgIC8vICAgXCJhdHRhY2htZW50c1wiOiBbXSxcbiAgICAgICAgLy8gICBcImF0dGVuZGVlc1wiOiBbXSxcbiAgICAgICAgLy8gICBcImF0dGVuZGVlc09taXR0ZWRcIjogZmFsc2UsXG4gICAgICAgIC8vICAgXCJjb2xvcklkXCI6IFwibXlfY29sb3JJZFwiLFxuICAgICAgICAvLyAgIFwiY29uZmVyZW5jZURhdGFcIjoge30sXG4gICAgICAgIC8vICAgXCJjcmVhdGVkXCI6IFwibXlfY3JlYXRlZFwiLFxuICAgICAgICAvLyAgIFwiY3JlYXRvclwiOiB7fSxcbiAgICAgICAgLy8gICBcImRlc2NyaXB0aW9uXCI6IFwibXlfZGVzY3JpcHRpb25cIixcbiAgICAgICAgLy8gICBcImVuZFwiOiB7fSxcbiAgICAgICAgLy8gICBcImVuZFRpbWVVbnNwZWNpZmllZFwiOiBmYWxzZSxcbiAgICAgICAgLy8gICBcImV0YWdcIjogXCJteV9ldGFnXCIsXG4gICAgICAgIC8vICAgXCJldmVudFR5cGVcIjogXCJteV9ldmVudFR5cGVcIixcbiAgICAgICAgLy8gICBcImV4dGVuZGVkUHJvcGVydGllc1wiOiB7fSxcbiAgICAgICAgLy8gICBcImdhZGdldFwiOiB7fSxcbiAgICAgICAgLy8gICBcImd1ZXN0c0Nhbkludml0ZU90aGVyc1wiOiBmYWxzZSxcbiAgICAgICAgLy8gICBcImd1ZXN0c0Nhbk1vZGlmeVwiOiBmYWxzZSxcbiAgICAgICAgLy8gICBcImd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXCI6IGZhbHNlLFxuICAgICAgICAvLyAgIFwiaGFuZ291dExpbmtcIjogXCJteV9oYW5nb3V0TGlua1wiLFxuICAgICAgICAvLyAgIFwiaHRtbExpbmtcIjogXCJteV9odG1sTGlua1wiLFxuICAgICAgICAvLyAgIFwiaUNhbFVJRFwiOiBcIm15X2lDYWxVSURcIixcbiAgICAgICAgLy8gICBcImlkXCI6IFwibXlfaWRcIixcbiAgICAgICAgLy8gICBcImtpbmRcIjogXCJteV9raW5kXCIsXG4gICAgICAgIC8vICAgXCJsb2NhdGlvblwiOiBcIm15X2xvY2F0aW9uXCIsXG4gICAgICAgIC8vICAgXCJsb2NrZWRcIjogZmFsc2UsXG4gICAgICAgIC8vICAgXCJvcmdhbml6ZXJcIjoge30sXG4gICAgICAgIC8vICAgXCJvcmlnaW5hbFN0YXJ0VGltZVwiOiB7fSxcbiAgICAgICAgLy8gICBcInByaXZhdGVDb3B5XCI6IGZhbHNlLFxuICAgICAgICAvLyAgIFwicmVjdXJyZW5jZVwiOiBbXSxcbiAgICAgICAgLy8gICBcInJlY3VycmluZ0V2ZW50SWRcIjogXCJteV9yZWN1cnJpbmdFdmVudElkXCIsXG4gICAgICAgIC8vICAgXCJyZW1pbmRlcnNcIjoge30sXG4gICAgICAgIC8vICAgXCJzZXF1ZW5jZVwiOiAwLFxuICAgICAgICAvLyAgIFwic291cmNlXCI6IHt9LFxuICAgICAgICAvLyAgIFwic3RhcnRcIjoge30sXG4gICAgICAgIC8vICAgXCJzdGF0dXNcIjogXCJteV9zdGF0dXNcIixcbiAgICAgICAgLy8gICBcInN1bW1hcnlcIjogXCJteV9zdW1tYXJ5XCIsXG4gICAgICAgIC8vICAgXCJ0cmFuc3BhcmVuY3lcIjogXCJteV90cmFuc3BhcmVuY3lcIixcbiAgICAgICAgLy8gICBcInVwZGF0ZWRcIjogXCJteV91cGRhdGVkXCIsXG4gICAgICAgIC8vICAgXCJ2aXNpYmlsaXR5XCI6IFwibXlfdmlzaWJpbGl0eVwiXG4gICAgICAgIC8vIH1cbiAgICAgIH0sXG4gICAgfTtcblxuICAgIC8vIGNyZWF0ZSByZXF1ZXN0IGJvZHlcbiAgICBsZXQgcmVxdWVzdEJvZHk6IGFueSA9IHt9O1xuXG4gICAgaWYgKGVuZERhdGUgJiYgdGltZXpvbmUgJiYgIWVuZERhdGVUaW1lKSB7XG4gICAgICBjb25zdCBlbmQgPSB7XG4gICAgICAgIGRhdGU6IGRheWpzKGVuZERhdGVUaW1lLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgcmVxdWVzdEJvZHkuZW5kID0gZW5kO1xuICAgIH1cblxuICAgIC8vIGlmIChlbmREYXRlVGltZSAmJiB0aW1lem9uZSAmJiAhZW5kRGF0ZSAmJiAocmVjdXJyZW5jZT8ubGVuZ3RoID4gMCkpIHtcbiAgICAvLyAgIGNvbnN0IGVuZCA9IHtcbiAgICAvLyAgICAgZGF0ZVRpbWU6IGRheWpzKGVuZERhdGVUaW1lKS50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAvLyAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgLy8gICAgIHRpbWV6b25lXG4gICAgLy8gICB9XG4gICAgLy8gICByZXF1ZXN0Qm9keS5lbmQgPSBlbmRcbiAgICAvLyB9XG5cbiAgICBpZiAoZW5kRGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIWVuZERhdGUpIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBldmVudElkLFxuICAgICAgICBlbmREYXRlVGltZSxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICcgZXZlbnRJZCwgZW5kRGF0ZVRpbWUsIHRpbWV6b25lIHByaW9yJ1xuICAgICAgKTtcbiAgICAgIGNvbnN0IGVuZCA9IHtcbiAgICAgICAgZGF0ZVRpbWU6IGVuZERhdGVUaW1lLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgcmVxdWVzdEJvZHkuZW5kID0gZW5kO1xuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgZW5kLmRhdGVUaW1lLFxuICAgICAgICBlbmQudGltZVpvbmUsXG4gICAgICAgICcgZXZlbnRJZCwgZW5kRGF0ZVRpbWUsIHRpbWVab25lIGFmdGVyJ1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoc3RhcnREYXRlICYmIHRpbWV6b25lICYmICFzdGFydERhdGVUaW1lKSB7XG4gICAgICBjb25zdCBzdGFydCA9IHtcbiAgICAgICAgZGF0ZTogZGF5anMoc3RhcnREYXRlVGltZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcbiAgICAgIHJlcXVlc3RCb2R5LnN0YXJ0ID0gc3RhcnQ7XG4gICAgfVxuXG4gICAgLy8gaWYgKHN0YXJ0RGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIXN0YXJ0RGF0ZSAmJiAocmVjdXJyZW5jZT8ubGVuZ3RoID4gMCkpIHtcbiAgICAvLyAgIGNvbnN0IHN0YXJ0ID0ge1xuICAgIC8vICAgICBkYXRlVGltZTogZGF5anMoc3RhcnREYXRlVGltZSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgIC8vICAgICB0aW1lem9uZSxcbiAgICAvLyAgIH1cbiAgICAvLyAgIHJlcXVlc3RCb2R5LnN0YXJ0ID0gc3RhcnRcbiAgICAvLyB9XG5cbiAgICBpZiAoc3RhcnREYXRlVGltZSAmJiB0aW1lem9uZSAmJiAhc3RhcnREYXRlKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgc3RhcnREYXRlVGltZSxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICcgZXZlbnRJZCwgc3RhcnREYXRlVGltZSwgdGltZXpvbmUgcHJpb3InXG4gICAgICApO1xuICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBzdGFydERhdGVUaW1lLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgcmVxdWVzdEJvZHkuc3RhcnQgPSBzdGFydDtcblxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICAgIHN0YXJ0LmRhdGVUaW1lLFxuICAgICAgICBzdGFydC50aW1lWm9uZSxcbiAgICAgICAgJyBldmVudElkLCBzdGFydERhdGVUaW1lLCB0aW1lWm9uZSBhZnRlcidcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKG9yaWdpbmFsU3RhcnREYXRlICYmIHRpbWV6b25lICYmICFvcmlnaW5hbFN0YXJ0RGF0ZVRpbWUpIHtcbiAgICAgIGNvbnN0IG9yaWdpbmFsU3RhcnRUaW1lID0ge1xuICAgICAgICBkYXRlOiBkYXlqcyhvcmlnaW5hbFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcbiAgICAgIHJlcXVlc3RCb2R5Lm9yaWdpbmFsU3RhcnRUaW1lID0gb3JpZ2luYWxTdGFydFRpbWU7XG4gICAgfVxuXG4gICAgaWYgKG9yaWdpbmFsU3RhcnREYXRlVGltZSAmJiB0aW1lem9uZSAmJiAhb3JpZ2luYWxTdGFydERhdGUpIHtcbiAgICAgIGNvbnN0IG9yaWdpbmFsU3RhcnRUaW1lID0ge1xuICAgICAgICBkYXRlVGltZTogb3JpZ2luYWxTdGFydERhdGVUaW1lLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgcmVxdWVzdEJvZHkub3JpZ2luYWxTdGFydFRpbWUgPSBvcmlnaW5hbFN0YXJ0VGltZTtcbiAgICB9XG5cbiAgICBpZiAoYW55b25lQ2FuQWRkU2VsZikge1xuICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgYW55b25lQ2FuQWRkU2VsZiB9XG4gICAgICByZXF1ZXN0Qm9keS5hbnlvbmVDYW5BZGRTZWxmID0gYW55b25lQ2FuQWRkU2VsZjtcbiAgICB9XG5cbiAgICBpZiAoYXR0ZW5kZWVzPy5bMF0/LmVtYWlsKSB7XG4gICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBhdHRlbmRlZXMgfVxuICAgICAgcmVxdWVzdEJvZHkuYXR0ZW5kZWVzID0gYXR0ZW5kZWVzO1xuICAgIH1cblxuICAgIGlmIChjb25mZXJlbmNlRGF0YT8uY3JlYXRlUmVxdWVzdCkge1xuICAgICAgLy8gZGF0YSA9IHtcbiAgICAgIC8vICAgLi4uZGF0YSxcbiAgICAgIC8vICAgY29uZmVyZW5jZURhdGE6IHtcbiAgICAgIC8vICAgICBjcmVhdGVSZXF1ZXN0OiB7XG4gICAgICAvLyAgICAgICBjb25mZXJlbmNlU29sdXRpb25LZXk6IHtcbiAgICAgIC8vICAgICAgICAgdHlwZTogY29uZmVyZW5jZURhdGEudHlwZVxuICAgICAgLy8gICAgICAgfSxcbiAgICAgIC8vICAgICAgIHJlcXVlc3RJZDogY29uZmVyZW5jZURhdGE/LnJlcXVlc3RJZCB8fCB1dWlkdjEoKSxcbiAgICAgIC8vICAgICB9XG4gICAgICAvLyAgIH1cbiAgICAgIC8vIH1cbiAgICAgIHJlcXVlc3RCb2R5LmNvbmZlcmVuY2VEYXRhID0ge1xuICAgICAgICBjcmVhdGVSZXF1ZXN0OiB7XG4gICAgICAgICAgY29uZmVyZW5jZVNvbHV0aW9uS2V5OiB7XG4gICAgICAgICAgICB0eXBlOiBjb25mZXJlbmNlRGF0YS50eXBlLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgcmVxdWVzdElkOiBjb25mZXJlbmNlRGF0YT8ucmVxdWVzdElkIHx8IHV1aWQoKSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgfSBlbHNlIGlmIChjb25mZXJlbmNlRGF0YT8uZW50cnlQb2ludHM/LlswXSkge1xuICAgICAgLy8gZGF0YSA9IHtcbiAgICAgIC8vICAgLi4uZGF0YSxcbiAgICAgIC8vICAgY29uZmVyZW5jZURhdGE6IHtcbiAgICAgIC8vICAgICBjb25mZXJlbmNlU29sdXRpb246IHtcbiAgICAgIC8vICAgICAgIGljb25Vcmk6IGNvbmZlcmVuY2VEYXRhPy5pY29uVXJpLFxuICAgICAgLy8gICAgICAga2V5OiB7XG4gICAgICAvLyAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2VEYXRhPy50eXBlLFxuICAgICAgLy8gICAgICAgfSxcbiAgICAgIC8vICAgICAgIG5hbWU6IGNvbmZlcmVuY2VEYXRhPy5uYW1lLFxuICAgICAgLy8gICAgIH0sXG4gICAgICAvLyAgICAgZW50cnlQb2ludHM6IGNvbmZlcmVuY2VEYXRhPy5lbnRyeVBvaW50cyxcbiAgICAgIC8vICAgfSxcbiAgICAgIC8vIH1cbiAgICAgIHJlcXVlc3RCb2R5LmNvbmZlcmVuY2VEYXRhID0ge1xuICAgICAgICBjb25mZXJlbmNlU29sdXRpb246IHtcbiAgICAgICAgICBpY29uVXJpOiBjb25mZXJlbmNlRGF0YT8uaWNvblVyaSxcbiAgICAgICAgICBrZXk6IHtcbiAgICAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2VEYXRhPy50eXBlLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgbmFtZTogY29uZmVyZW5jZURhdGE/Lm5hbWUsXG4gICAgICAgIH0sXG4gICAgICAgIGVudHJ5UG9pbnRzOiBjb25mZXJlbmNlRGF0YT8uZW50cnlQb2ludHMsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChkZXNjcmlwdGlvbj8ubGVuZ3RoID4gMCkge1xuICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgZGVzY3JpcHRpb24gfVxuICAgICAgcmVxdWVzdEJvZHkuZGVzY3JpcHRpb24gPSBkZXNjcmlwdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoZXh0ZW5kZWRQcm9wZXJ0aWVzPy5wcml2YXRlIHx8IGV4dGVuZGVkUHJvcGVydGllcz8uc2hhcmVkKSB7XG4gICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBleHRlbmRlZFByb3BlcnRpZXMgfVxuICAgICAgcmVxdWVzdEJvZHkuZXh0ZW5kZWRQcm9wZXJ0aWVzID0gZXh0ZW5kZWRQcm9wZXJ0aWVzO1xuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5JbnZpdGVPdGhlcnMpIHtcbiAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGd1ZXN0c0Nhbkludml0ZU90aGVycyB9XG4gICAgICByZXF1ZXN0Qm9keS5ndWVzdHNDYW5JbnZpdGVPdGhlcnMgPSBndWVzdHNDYW5JbnZpdGVPdGhlcnM7XG4gICAgfVxuXG4gICAgaWYgKGd1ZXN0c0Nhbk1vZGlmeSkge1xuICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgZ3Vlc3RzQ2FuTW9kaWZ5IH1cbiAgICAgIHJlcXVlc3RCb2R5Lmd1ZXN0c0Nhbk1vZGlmeSA9IGd1ZXN0c0Nhbk1vZGlmeTtcbiAgICB9XG5cbiAgICBpZiAoZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMpIHtcbiAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzIH1cbiAgICAgIHJlcXVlc3RCb2R5Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzID0gZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM7XG4gICAgfVxuXG4gICAgaWYgKGxvY2tlZCkge1xuICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgbG9ja2VkIH1cbiAgICAgIHJlcXVlc3RCb2R5LmxvY2tlZCA9IGxvY2tlZDtcbiAgICB9XG5cbiAgICBpZiAocHJpdmF0ZUNvcHkpIHtcbiAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIHByaXZhdGVDb3B5IH1cbiAgICAgIHJlcXVlc3RCb2R5LnByaXZhdGVDb3B5ID0gcHJpdmF0ZUNvcHk7XG4gICAgfVxuXG4gICAgaWYgKHJlY3VycmVuY2U/LlswXSkge1xuICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgcmVjdXJyZW5jZSB9XG4gICAgICByZXF1ZXN0Qm9keS5yZWN1cnJlbmNlID0gcmVjdXJyZW5jZTtcbiAgICB9XG5cbiAgICBpZiAocmVtaW5kZXJzKSB7XG4gICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCByZW1pbmRlcnMgfVxuICAgICAgcmVxdWVzdEJvZHkucmVtaW5kZXJzID0gcmVtaW5kZXJzO1xuICAgIH1cblxuICAgIGlmIChzb3VyY2U/LnRpdGxlIHx8IHNvdXJjZT8udXJsKSB7XG4gICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBzb3VyY2UgfVxuICAgICAgcmVxdWVzdEJvZHkuc291cmNlID0gc291cmNlO1xuICAgIH1cblxuICAgIGlmIChhdHRhY2htZW50cz8uWzBdPy5maWxlSWQpIHtcbiAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGF0dGFjaG1lbnRzIH1cbiAgICAgIHJlcXVlc3RCb2R5LmF0dGFjaG1lbnRzID0gYXR0YWNobWVudHM7XG4gICAgfVxuXG4gICAgaWYgKGV2ZW50VHlwZT8ubGVuZ3RoID4gMCkge1xuICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgZXZlbnRUeXBlIH1cbiAgICAgIHJlcXVlc3RCb2R5LmV2ZW50VHlwZSA9IGV2ZW50VHlwZTtcbiAgICB9XG5cbiAgICBpZiAoc3RhdHVzKSB7XG4gICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBzdGF0dXMgfVxuICAgICAgcmVxdWVzdEJvZHkuc3RhdHVzID0gc3RhdHVzO1xuICAgIH1cblxuICAgIGlmICh0cmFuc3BhcmVuY3kpIHtcbiAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIHRyYW5zcGFyZW5jeSB9XG4gICAgICByZXF1ZXN0Qm9keS50cmFuc3BhcmVuY3kgPSB0cmFuc3BhcmVuY3k7XG4gICAgfVxuXG4gICAgaWYgKHZpc2liaWxpdHkpIHtcbiAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIHZpc2liaWxpdHkgfVxuICAgICAgcmVxdWVzdEJvZHkudmlzaWJpbGl0eSA9IHZpc2liaWxpdHk7XG4gICAgfVxuXG4gICAgaWYgKGlDYWxVSUQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGlDYWxVSUQgfVxuICAgICAgcmVxdWVzdEJvZHkuaUNhbFVJRCA9IGlDYWxVSUQ7XG4gICAgfVxuXG4gICAgaWYgKGF0dGVuZGVlc09taXR0ZWQpIHtcbiAgICAgIC8vIGRhdGEgPSB7IC4uLmRhdGEsIGF0dGVuZGVlc09taXR0ZWQgfVxuICAgICAgcmVxdWVzdEJvZHkuYXR0ZW5kZWVzT21pdHRlZCA9IGF0dGVuZGVlc09taXR0ZWQ7XG4gICAgfVxuXG4gICAgaWYgKGhhbmdvdXRMaW5rPy5sZW5ndGggPiAwKSB7XG4gICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBoYW5nb3V0TGluayB9XG4gICAgICByZXF1ZXN0Qm9keS5oYW5nb3V0TGluayA9IGhhbmdvdXRMaW5rO1xuICAgIH1cblxuICAgIGlmIChzdW1tYXJ5Py5sZW5ndGggPiAwKSB7XG4gICAgICAvLyBkYXRhID0geyAuLi5kYXRhLCBzdW1tYXJ5IH1cbiAgICAgIHJlcXVlc3RCb2R5LnN1bW1hcnkgPSBzdW1tYXJ5O1xuICAgIH1cblxuICAgIGlmIChsb2NhdGlvbj8ubGVuZ3RoID4gMCkge1xuICAgICAgLy8gZGF0YSA9IHsgLi4uZGF0YSwgbG9jYXRpb24gfVxuICAgICAgcmVxdWVzdEJvZHkubG9jYXRpb24gPSBsb2NhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoY29sb3JJZCkge1xuICAgICAgcmVxdWVzdEJvZHkuY29sb3JJZCA9IGNvbG9ySWQ7XG4gICAgfVxuXG4gICAgdmFyaWFibGVzLnJlcXVlc3RCb2R5ID0gcmVxdWVzdEJvZHk7XG4gICAgLy8gRG8gdGhlIG1hZ2ljXG4gICAgY29uc29sZS5sb2coXG4gICAgICBldmVudElkLFxuICAgICAgcmVxdWVzdEJvZHksXG4gICAgICAnIGV2ZW50SWQsIHJlcXVlc3RCb2R5IGluc2lkZSBnb29nbGVQYXRjaEV2ZW50J1xuICAgICk7XG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlQ2FsZW5kYXIuZXZlbnRzLnBhdGNoKHZhcmlhYmxlcyk7XG4gICAgY29uc29sZS5sb2coZXZlbnRJZCwgcmVzLmRhdGEsICcgZXZlbnRJZCwgcmVzdWx0cyBmcm9tIGdvb2dsZVBhdGNoRXZlbnQnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHBhdGNoIGdvb2dsZSBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlR29vZ2xlRXZlbnQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYicsXG4gIGdlbmVyYXRlZElkPzogc3RyaW5nLFxuICBlbmREYXRlVGltZT86IHN0cmluZywgLy8gZWl0aGVyIGVuZERhdGVUaW1lIG9yIGVuZERhdGUgLSBhbGwgZGF5IHZzIHNwZWNpZmljIHBlcmlvZFxuICBzdGFydERhdGVUaW1lPzogc3RyaW5nLFxuICBjb25mZXJlbmNlRGF0YVZlcnNpb24/OiAwIHwgMSxcbiAgbWF4QXR0ZW5kZWVzPzogbnVtYmVyLFxuICBzZW5kVXBkYXRlcz86IEdvb2dsZVNlbmRVcGRhdGVzVHlwZSxcbiAgYW55b25lQ2FuQWRkU2VsZj86IGJvb2xlYW4sXG4gIGF0dGVuZGVlcz86IEdvb2dsZUF0dGVuZGVlVHlwZVtdLFxuICBjb25mZXJlbmNlRGF0YT86IEdvb2dsZUNvbmZlcmVuY2VEYXRhVHlwZSxcbiAgc3VtbWFyeT86IHN0cmluZyxcbiAgZGVzY3JpcHRpb24/OiBzdHJpbmcsXG4gIHRpbWV6b25lPzogc3RyaW5nLCAvLyByZXF1aXJlZCBmb3IgcmVjdXJyZW5jZVxuICBzdGFydERhdGU/OiBzdHJpbmcsIC8vIGFsbCBkYXlcbiAgZW5kRGF0ZT86IHN0cmluZywgLy8gYWxsIGRheVxuICBleHRlbmRlZFByb3BlcnRpZXM/OiBHb29nbGVFeHRlbmRlZFByb3BlcnRpZXNUeXBlLFxuICBndWVzdHNDYW5JbnZpdGVPdGhlcnM/OiBib29sZWFuLFxuICBndWVzdHNDYW5Nb2RpZnk/OiBib29sZWFuLFxuICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0cz86IGJvb2xlYW4sXG4gIG9yaWdpbmFsU3RhcnREYXRlVGltZT86IHN0cmluZyxcbiAgb3JpZ2luYWxTdGFydERhdGU/OiBzdHJpbmcsXG4gIHJlY3VycmVuY2U/OiBzdHJpbmdbXSxcbiAgcmVtaW5kZXJzPzogR29vZ2xlUmVtaW5kZXJUeXBlLFxuICBzb3VyY2U/OiBHb29nbGVTb3VyY2VUeXBlLFxuICBzdGF0dXM/OiBzdHJpbmcsXG4gIHRyYW5zcGFyZW5jeT86IEdvb2dsZVRyYW5zcGFyZW5jeVR5cGUsXG4gIHZpc2liaWxpdHk/OiBHb29nbGVWaXNpYmlsaXR5VHlwZSxcbiAgaUNhbFVJRD86IHN0cmluZyxcbiAgYXR0ZW5kZWVzT21pdHRlZD86IGJvb2xlYW4sXG4gIGhhbmdvdXRMaW5rPzogc3RyaW5nLFxuICBwcml2YXRlQ29weT86IGJvb2xlYW4sXG4gIGxvY2tlZD86IGJvb2xlYW4sXG4gIGF0dGFjaG1lbnRzPzogR29vZ2xlQXR0YWNobWVudFR5cGVbXSxcbiAgZXZlbnRUeXBlPzogR29vZ2xlRXZlbnRUeXBlMSxcbiAgbG9jYXRpb24/OiBzdHJpbmcsXG4gIGNvbG9ySWQ/OiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIC8vIGdldCB0b2tlbiA9XG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRHb29nbGVBUElUb2tlbihcbiAgICAgIHVzZXJJZCxcbiAgICAgIGdvb2dsZUNhbGVuZGFyUmVzb3VyY2UsXG4gICAgICBjbGllbnRUeXBlXG4gICAgKTtcblxuICAgIGNvbnN0IGdvb2dsZUNhbGVuZGFyID0gZ29vZ2xlLmNhbGVuZGFyKHtcbiAgICAgIHZlcnNpb246ICd2MycsXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIC8vIGNvbnN0IHRva2VuID0gYXdhaXQgZ2V0QVBJVG9rZW4odXNlcklkLCBnb29nbGVDYWxlbmRhclJlc291cmNlLCBnb29nbGVDYWxlbmRhck5hbWUpXG4gICAgLy8gbGV0IHVybCA9IGAke2dvb2dsZVVybH0vJHtlbmNvZGVVUkkoY2FsZW5kYXJJZCl9L2V2ZW50c2BcblxuICAgIC8vIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAvLyAgIGhlYWRlcnM6IHtcbiAgICAvLyAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgLy8gICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgLy8gICAgICdBY2NlcHQnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgLy8gICB9LFxuICAgIC8vIH1cblxuICAgIC8vIGlmIGFueSBxdWVyeSBwYXJhbWV0ZXJzIGJ1aWxkIHRoZW1cbiAgICAvLyBmaXJzdFxuICAgIGlmIChtYXhBdHRlbmRlZXMgfHwgc2VuZFVwZGF0ZXMgfHwgY29uZmVyZW5jZURhdGFWZXJzaW9uID4gMCkge1xuICAgICAgLy8gdXJsID0gYCR7dXJsfT9gXG4gICAgICBsZXQgcGFyYW1zOiBhbnkgPSB7fTtcblxuICAgICAgaWYgKG1heEF0dGVuZGVlcykge1xuICAgICAgICBwYXJhbXMgPSB7IC4uLnBhcmFtcywgbWF4QXR0ZW5kZWVzIH07XG4gICAgICB9XG5cbiAgICAgIGlmIChzZW5kVXBkYXRlcykge1xuICAgICAgICBwYXJhbXMgPSB7IC4uLnBhcmFtcywgc2VuZFVwZGF0ZXMgfTtcbiAgICAgIH1cblxuICAgICAgaWYgKGNvbmZlcmVuY2VEYXRhVmVyc2lvbiA+IDApIHtcbiAgICAgICAgcGFyYW1zID0geyAuLi5wYXJhbXMsIGNvbmZlcmVuY2VEYXRhVmVyc2lvbiB9O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIHBhcmFtcz8ubWF4QXR0ZW5kZWVzIHx8XG4gICAgICAgIHBhcmFtcz8uc2VuZFVwZGF0ZXMgfHxcbiAgICAgICAgcGFyYW1zPy5jb25mZXJlbmNlRGF0YVZlcnNpb24gPiAtMVxuICAgICAgKSB7XG4gICAgICAgIC8vIHVybCA9IGAke3VybH0ke3FzLnN0cmluZ2lmeShwYXJhbXMpfWBcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBjcmVhdGUgcmVxdWVzdCBib2R5XG4gICAgbGV0IGRhdGE6IGFueSA9IHt9O1xuXG4gICAgaWYgKGVuZERhdGVUaW1lICYmIHRpbWV6b25lICYmICFlbmREYXRlKSB7XG4gICAgICAvLyBCVUc6IGNhbGxpbmcgZGF5anMgaGVyZSBvZmZzZXRzIGVuZERhdGVUaW1lIHZhbHVlXG4gICAgICBjb25zdCBlbmQgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBlbmREYXRlVGltZSxcbiAgICAgICAgdGltZVpvbmU6IHRpbWV6b25lLFxuICAgICAgfTtcblxuICAgICAgZGF0YS5lbmQgPSBlbmQ7XG4gICAgfVxuXG4gICAgaWYgKGVuZERhdGUgJiYgdGltZXpvbmUgJiYgIWVuZERhdGVUaW1lKSB7XG4gICAgICBjb25zdCBlbmQgPSB7XG4gICAgICAgIGRhdGU6IGRheWpzKGVuZERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG5cbiAgICAgIGRhdGEuZW5kID0gZW5kO1xuICAgIH1cblxuICAgIGlmIChzdGFydERhdGUgJiYgdGltZXpvbmUgJiYgIXN0YXJ0RGF0ZVRpbWUpIHtcbiAgICAgIGNvbnN0IHN0YXJ0ID0ge1xuICAgICAgICBkYXRlOiBkYXlqcyhzdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG4gICAgICBkYXRhLnN0YXJ0ID0gc3RhcnQ7XG4gICAgfVxuXG4gICAgaWYgKHN0YXJ0RGF0ZVRpbWUgJiYgdGltZXpvbmUgJiYgIXN0YXJ0RGF0ZSkge1xuICAgICAgY29uc3Qgc3RhcnQgPSB7XG4gICAgICAgIGRhdGVUaW1lOiBzdGFydERhdGVUaW1lLFxuICAgICAgICB0aW1lWm9uZTogdGltZXpvbmUsXG4gICAgICB9O1xuICAgICAgZGF0YS5zdGFydCA9IHN0YXJ0O1xuICAgIH1cblxuICAgIGlmIChvcmlnaW5hbFN0YXJ0RGF0ZSAmJiB0aW1lem9uZSAmJiAhb3JpZ2luYWxTdGFydERhdGVUaW1lKSB7XG4gICAgICBjb25zdCBvcmlnaW5hbFN0YXJ0VGltZSA9IHtcbiAgICAgICAgZGF0ZTogb3JpZ2luYWxTdGFydERhdGUsXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG4gICAgICBkYXRhLm9yaWdpbmFsU3RhcnRUaW1lID0gb3JpZ2luYWxTdGFydFRpbWU7XG4gICAgfVxuXG4gICAgaWYgKG9yaWdpbmFsU3RhcnREYXRlVGltZSAmJiB0aW1lem9uZSAmJiAhb3JpZ2luYWxTdGFydERhdGUpIHtcbiAgICAgIGNvbnN0IG9yaWdpbmFsU3RhcnRUaW1lID0ge1xuICAgICAgICBkYXRlVGltZTogZGF5anMob3JpZ2luYWxTdGFydERhdGVUaW1lKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCksXG4gICAgICAgIHRpbWVab25lOiB0aW1lem9uZSxcbiAgICAgIH07XG4gICAgICBkYXRhLm9yaWdpbmFsU3RhcnRUaW1lID0gb3JpZ2luYWxTdGFydFRpbWU7XG4gICAgfVxuXG4gICAgaWYgKGFueW9uZUNhbkFkZFNlbGYpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGFueW9uZUNhbkFkZFNlbGYgfTtcbiAgICB9XG5cbiAgICBpZiAoYXR0ZW5kZWVzPy5bMF0/LmVtYWlsKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBhdHRlbmRlZXMgfTtcbiAgICB9XG5cbiAgICBpZiAoY29uZmVyZW5jZURhdGE/LmNyZWF0ZVJlcXVlc3QpIHtcbiAgICAgIGRhdGEgPSB7XG4gICAgICAgIC4uLmRhdGEsXG4gICAgICAgIGNvbmZlcmVuY2VEYXRhOiB7XG4gICAgICAgICAgY3JlYXRlUmVxdWVzdDoge1xuICAgICAgICAgICAgY29uZmVyZW5jZVNvbHV0aW9uS2V5OiB7XG4gICAgICAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2VEYXRhLnR5cGUsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgcmVxdWVzdElkOiBjb25mZXJlbmNlRGF0YT8ucmVxdWVzdElkIHx8IHV1aWQoKSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9IGVsc2UgaWYgKGNvbmZlcmVuY2VEYXRhPy5lbnRyeVBvaW50cz8uWzBdKSB7XG4gICAgICBkYXRhID0ge1xuICAgICAgICAuLi5kYXRhLFxuICAgICAgICBjb25mZXJlbmNlRGF0YToge1xuICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbjoge1xuICAgICAgICAgICAgaWNvblVyaTogY29uZmVyZW5jZURhdGE/Lmljb25VcmksXG4gICAgICAgICAgICBrZXk6IHtcbiAgICAgICAgICAgICAgdHlwZTogY29uZmVyZW5jZURhdGE/LnR5cGUsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgbmFtZTogY29uZmVyZW5jZURhdGE/Lm5hbWUsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBlbnRyeVBvaW50czogY29uZmVyZW5jZURhdGE/LmVudHJ5UG9pbnRzLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoZGVzY3JpcHRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGRlc2NyaXB0aW9uIH07XG4gICAgfVxuXG4gICAgaWYgKGV4dGVuZGVkUHJvcGVydGllcz8ucHJpdmF0ZSB8fCBleHRlbmRlZFByb3BlcnRpZXM/LnNoYXJlZCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZXh0ZW5kZWRQcm9wZXJ0aWVzIH07XG4gICAgfVxuXG4gICAgaWYgKGd1ZXN0c0Nhbkludml0ZU90aGVycykge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzIH07XG4gICAgfVxuXG4gICAgaWYgKGd1ZXN0c0Nhbk1vZGlmeSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZ3Vlc3RzQ2FuTW9kaWZ5IH07XG4gICAgfVxuXG4gICAgaWYgKGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyB9O1xuICAgIH1cblxuICAgIGlmIChsb2NrZWQpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGxvY2tlZCB9O1xuICAgIH1cblxuICAgIGlmIChwcml2YXRlQ29weSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgcHJpdmF0ZUNvcHkgfTtcbiAgICB9XG5cbiAgICBpZiAocmVjdXJyZW5jZT8uWzBdKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCByZWN1cnJlbmNlIH07XG4gICAgfVxuXG4gICAgaWYgKHJlbWluZGVycykge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgcmVtaW5kZXJzIH07XG4gICAgfVxuXG4gICAgaWYgKHNvdXJjZT8udGl0bGUgfHwgc291cmNlPy51cmwpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHNvdXJjZSB9O1xuICAgIH1cblxuICAgIGlmIChhdHRhY2htZW50cz8uWzBdPy5maWxlSWQpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIGF0dGFjaG1lbnRzIH07XG4gICAgfVxuXG4gICAgaWYgKGV2ZW50VHlwZT8ubGVuZ3RoID4gMCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgZXZlbnRUeXBlIH07XG4gICAgfVxuXG4gICAgaWYgKHN0YXR1cykge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgc3RhdHVzIH07XG4gICAgfVxuXG4gICAgaWYgKHRyYW5zcGFyZW5jeSkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgdHJhbnNwYXJlbmN5IH07XG4gICAgfVxuXG4gICAgaWYgKHZpc2liaWxpdHkpIHtcbiAgICAgIGRhdGEgPSB7IC4uLmRhdGEsIHZpc2liaWxpdHkgfTtcbiAgICB9XG5cbiAgICBpZiAoaUNhbFVJRD8ubGVuZ3RoID4gMCkge1xuICAgICAgZGF0YSA9IHsgLi4uZGF0YSwgaUNhbFVJRCB9O1xuICAgIH1cblxuICAgIGlmIChhdHRlbmRlZXNPbWl0dGVkKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBhdHRlbmRlZXNPbWl0dGVkIH07XG4gICAgfVxuXG4gICAgaWYgKGhhbmdvdXRMaW5rPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBoYW5nb3V0TGluayB9O1xuICAgIH1cblxuICAgIGlmIChzdW1tYXJ5Py5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBzdW1tYXJ5IH07XG4gICAgfVxuXG4gICAgaWYgKGxvY2F0aW9uPy5sZW5ndGggPiAwKSB7XG4gICAgICBkYXRhID0geyAuLi5kYXRhLCBsb2NhdGlvbiB9O1xuICAgIH1cblxuICAgIGlmIChjb2xvcklkKSB7XG4gICAgICBkYXRhLmNvbG9ySWQgPSBjb2xvcklkO1xuICAgIH1cblxuICAgIC8vIGlmIChpZCkge1xuICAgIC8vICAgZGF0YSA9IHsgLi4uZGF0YSwgaWQgfVxuICAgIC8vIH1cblxuICAgIC8vIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBnb3QucG9zdDxldmVudFJlc3BvbnNlPihcbiAgICAvLyAgIHVybCxcbiAgICAvLyAgIHtcbiAgICAvLyAgICAganNvbjogZGF0YSxcbiAgICAvLyAgICAgLi4uY29uZmlnLFxuICAgIC8vICAgfSxcbiAgICAvLyApLmpzb24oKVxuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlQ2FsZW5kYXIuZXZlbnRzLmluc2VydCh7XG4gICAgICAvLyBDYWxlbmRhciBpZGVudGlmaWVyLiBUbyByZXRyaWV2ZSBjYWxlbmRhciBJRHMgY2FsbCB0aGUgY2FsZW5kYXJMaXN0Lmxpc3QgbWV0aG9kLiBJZiB5b3Ugd2FudCB0byBhY2Nlc3MgdGhlIHByaW1hcnkgY2FsZW5kYXIgb2YgdGhlIGN1cnJlbnRseSBsb2dnZWQgaW4gdXNlciwgdXNlIHRoZSBcInByaW1hcnlcIiBrZXl3b3JkLlxuICAgICAgY2FsZW5kYXJJZCxcbiAgICAgIC8vIFZlcnNpb24gbnVtYmVyIG9mIGNvbmZlcmVuY2UgZGF0YSBzdXBwb3J0ZWQgYnkgdGhlIEFQSSBjbGllbnQuIFZlcnNpb24gMCBhc3N1bWVzIG5vIGNvbmZlcmVuY2UgZGF0YSBzdXBwb3J0IGFuZCBpZ25vcmVzIGNvbmZlcmVuY2UgZGF0YSBpbiB0aGUgZXZlbnQncyBib2R5LiBWZXJzaW9uIDEgZW5hYmxlcyBzdXBwb3J0IGZvciBjb3B5aW5nIG9mIENvbmZlcmVuY2VEYXRhIGFzIHdlbGwgYXMgZm9yIGNyZWF0aW5nIG5ldyBjb25mZXJlbmNlcyB1c2luZyB0aGUgY3JlYXRlUmVxdWVzdCBmaWVsZCBvZiBjb25mZXJlbmNlRGF0YS4gVGhlIGRlZmF1bHQgaXMgMC5cbiAgICAgIGNvbmZlcmVuY2VEYXRhVmVyc2lvbixcbiAgICAgIC8vIFRoZSBtYXhpbXVtIG51bWJlciBvZiBhdHRlbmRlZXMgdG8gaW5jbHVkZSBpbiB0aGUgcmVzcG9uc2UuIElmIHRoZXJlIGFyZSBtb3JlIHRoYW4gdGhlIHNwZWNpZmllZCBudW1iZXIgb2YgYXR0ZW5kZWVzLCBvbmx5IHRoZSBwYXJ0aWNpcGFudCBpcyByZXR1cm5lZC4gT3B0aW9uYWwuXG4gICAgICBtYXhBdHRlbmRlZXMsXG4gICAgICAvLyBXaGV0aGVyIHRvIHNlbmQgbm90aWZpY2F0aW9ucyBhYm91dCB0aGUgY3JlYXRpb24gb2YgdGhlIG5ldyBldmVudC4gTm90ZSB0aGF0IHNvbWUgZW1haWxzIG1pZ2h0IHN0aWxsIGJlIHNlbnQuIFRoZSBkZWZhdWx0IGlzIGZhbHNlLlxuICAgICAgc2VuZFVwZGF0ZXMsXG5cbiAgICAgIC8vIFJlcXVlc3QgYm9keSBtZXRhZGF0YVxuICAgICAgcmVxdWVzdEJvZHk6IGRhdGEsXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMuZGF0YSk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXM/LmRhdGEsICcgcmVzPy5kYXRhIGZyb20gZ29vZ2xlQ3JlYXRlRXZlbnQnKTtcbiAgICByZXR1cm4geyBpZDogcmVzPy5kYXRhPy5pZCwgZ2VuZXJhdGVkSWQgfTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgY3JlYXRlR29vZ2xlRXZlbnQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHBvc3RQbGFubmVyTW9kaWZ5RXZlbnRJbkNhbGVuZGFyID0gYXN5bmMgKFxuICBuZXdFdmVudDogRXZlbnRQbHVzVHlwZSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG1ldGhvZDogJ3VwZGF0ZScgfCAnY3JlYXRlJyxcbiAgcmVzb3VyY2U6IHN0cmluZyxcbiAgaXNUaW1lQmxvY2tpbmc6IGJvb2xlYW4sXG4gIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYicsXG4gIG5ld1JlbWluZGVycz86IFJlbWluZGVyVHlwZVtdLFxuICBhdHRlbmRlZXM/OiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIGNvbmZlcmVuY2U/OiBDb25mZXJlbmNlVHlwZVxuKTogUHJvbWlzZTxzdHJpbmcgfCB7IGlkOiBzdHJpbmc7IGdlbmVyYXRlZElkOiBzdHJpbmcgfT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKG5ld0V2ZW50LCAnIG5ld0V2ZW50IGluc2lkZSBwb3N0UGxhbm5lck1vZGlmeUV2ZW50SW5DYWxlbmRhcicpO1xuICAgIGlmIChtZXRob2QgPT09ICd1cGRhdGUnKSB7XG4gICAgICAvLyB1cGRhdGUgZXZlbnRcblxuICAgICAgaWYgKHJlc291cmNlID09PSBnb29nbGVDYWxlbmRhclJlc291cmNlKSB7XG4gICAgICAgIGNvbnN0IGdvb2dsZVJlbWluZGVyczogR29vZ2xlUmVtaW5kZXJUeXBlID1cbiAgICAgICAgICBuZXdSZW1pbmRlcnM/Lmxlbmd0aCA+IDBcbiAgICAgICAgICAgID8gZm9ybWF0UmVtaW5kZXJzRm9yR29vZ2xlKG5ld1JlbWluZGVycylcbiAgICAgICAgICAgIDogdW5kZWZpbmVkO1xuXG4gICAgICAgIC8vIHVwZGF0ZSBldmVudFxuICAgICAgICBhd2FpdCBwYXRjaEdvb2dsZUV2ZW50KFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICBuZXdFdmVudC5jYWxlbmRhcklkLFxuICAgICAgICAgIG5ld0V2ZW50LmV2ZW50SWQsXG4gICAgICAgICAgY2xpZW50VHlwZSxcbiAgICAgICAgICBuZXdFdmVudC5lbmREYXRlLFxuICAgICAgICAgIG5ld0V2ZW50LnN0YXJ0RGF0ZSxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIG5ld0V2ZW50LnRpbWV6b25lLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIGdvb2dsZVJlbWluZGVycyxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIG5ld0V2ZW50LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgICBuZXdFdmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIG5ld0V2ZW50Py5jb2xvcklkXG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiBuZXdFdmVudC5pZDtcbiAgICAgIH1cbiAgICAgIC8vIGVsc2UgaWYgKHJlc291cmNlID09PSBvdXRsb29rQ2FsZW5kYXJSZXNvdXJjZSkge1xuICAgICAgLy8gICAvLyBhd2FpdCB1cGRhdGVPdXRsb29rRXZlbnQobmV3RXZlbnQpXG4gICAgICAvLyB9XG4gICAgfSBlbHNlIGlmIChtZXRob2QgPT09ICdjcmVhdGUnKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICcgbmV3RXZlbnQgaW5zaWRlIGNyZWF0ZSBpbnNpZGUgcG9zdFBsYW5uZXJNb2RpZnlFdmVudEluQ2FsZW5kYXInXG4gICAgICApO1xuICAgICAgLy8gY3JlYXRlIHRhc2sgZXZlbnRzIG9ubHlcbiAgICAgIGlmIChyZXNvdXJjZSA9PT0gZ29vZ2xlQ2FsZW5kYXJSZXNvdXJjZSkge1xuICAgICAgICBjb25zdCBnb29nbGVSZW1pbmRlcnM6IEdvb2dsZVJlbWluZGVyVHlwZSA9XG4gICAgICAgICAgbmV3UmVtaW5kZXJzPy5sZW5ndGggPiAwXG4gICAgICAgICAgICA/IGZvcm1hdFJlbWluZGVyc0Zvckdvb2dsZShuZXdSZW1pbmRlcnMpXG4gICAgICAgICAgICA6IHVuZGVmaW5lZDtcblxuICAgICAgICBjb25zdCBpZEFuZEdlbklkT2JqZWN0ID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIG5ld0V2ZW50LmNhbGVuZGFySWQsXG4gICAgICAgICAgY2xpZW50VHlwZSxcbiAgICAgICAgICBuZXdFdmVudD8uZXZlbnRJZCwgLy8gZ2VuZXJhdGVkSWRcbiAgICAgICAgICBuZXdFdmVudD8uZW5kRGF0ZSxcbiAgICAgICAgICBuZXdFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICBhdHRlbmRlZXM/Lm1hcCgoYSkgPT4gKHtcbiAgICAgICAgICAgIGVtYWlsOiBhPy5wcmltYXJ5RW1haWwsXG4gICAgICAgICAgICBpZDogYT8uaWQsXG4gICAgICAgICAgICBkaXNwbGF5TmFtZTogYT8ubmFtZSxcbiAgICAgICAgICB9KSksXG4gICAgICAgICAgY29uZmVyZW5jZT8uaWRcbiAgICAgICAgICAgID8ge1xuICAgICAgICAgICAgICAgIHR5cGU6IGNvbmZlcmVuY2U/LmFwcCA9PT0gJ3pvb20nID8gJ2FkZE9uJyA6ICdoYW5nb3V0c01lZXQnLFxuICAgICAgICAgICAgICAgIG5hbWU6IGNvbmZlcmVuY2U/Lm5hbWUsXG4gICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkOiBjb25mZXJlbmNlPy5pZCxcbiAgICAgICAgICAgICAgICBlbnRyeVBvaW50czogY29uZmVyZW5jZT8uZW50cnlQb2ludHMsXG4gICAgICAgICAgICAgICAgY3JlYXRlUmVxdWVzdDpcbiAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2U/LmFwcCA9PT0gJ2dvb2dsZSdcbiAgICAgICAgICAgICAgICAgICAgPyB7XG4gICAgICAgICAgICAgICAgICAgICAgICByZXF1ZXN0SWQ6IGNvbmZlcmVuY2U/LnJlcXVlc3RJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbktleToge1xuICAgICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiAnaGFuZ291dHNNZWV0JyxcbiAgICAgICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICA6IHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgICAgICAgbmV3RXZlbnQuc3VtbWFyeSB8fCBuZXdFdmVudD8udGl0bGUsXG4gICAgICAgICAgbmV3RXZlbnQubm90ZXMsXG4gICAgICAgICAgbmV3RXZlbnQudGltZXpvbmUsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICBuZXdFdmVudD8ucmVjdXJyZW5jZSxcbiAgICAgICAgICBnb29nbGVSZW1pbmRlcnMsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICBuZXdFdmVudC50cmFuc3BhcmVuY3ksXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIGlzVGltZUJsb2NraW5nID8gJ2ZvY3VzVGltZScgOiAnZGVmYXVsdCcsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIG5ld0V2ZW50Py5jb2xvcklkXG4gICAgICAgICk7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGlkQW5kR2VuSWRPYmplY3QsXG4gICAgICAgICAgbmV3RXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgbmV3RXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICAnIGlkQW5kR2VuSWRPYmplY3QsIG5ld0V2ZW50Py5lbmREYXRlLCAgbmV3RXZlbnQ/LnN0YXJ0RGF0ZSdcbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIGlkQW5kR2VuSWRPYmplY3Q7XG4gICAgICB9XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIGV2ZW50Jyk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBuZXdFdmVudD8uaWQsXG4gICAgICBuZXdFdmVudD8uZW5kRGF0ZSxcbiAgICAgIG5ld0V2ZW50Py5zdGFydERhdGUsXG4gICAgICAnIGVycm9yIC0gbmV3RXZlbnQ/LmlkLCBuZXdFdmVudD8uZW5kRGF0ZSwgIG5ld0V2ZW50Py5zdGFydERhdGUnXG4gICAgKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQnJlYWtFdmVudHNGb3JDYWxlbmRhclN5bmMgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghdXNlcklkKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gdXNlcklkIGluc2lkZSBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yQ2FsZW5kYXJTeW5jJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCF0aW1lem9uZSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIHRpbWV6b25lIGluc2lkZSBnZW5lcmF0ZUJyZWFrRXZlbnRzRm9yQ2FsZW5kYXJTeW5jJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCFjbGllbnRUeXBlKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gY2xpZW50VHlwZSBpbnNpZGUgZ2VuZXJhdGVCcmVha0V2ZW50c0ZvckNhbGVuZGFyU3luYycpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cbiAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZXModXNlcklkKTtcblxuICAgIGNvbnN0IGJyZWFrRXZlbnRzID0gYXdhaXQgZ2VuZXJhdGVCcmVha0V2ZW50c0ZvckRhdGUoXG4gICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICB1c2VySWQsXG4gICAgICBkYXlqcygpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoKSxcbiAgICAgIGRheWpzKCkudHoodGltZXpvbmUsIHRydWUpLmFkZCg3LCAnZCcpLmZvcm1hdCgpLFxuICAgICAgdGltZXpvbmVcbiAgICApO1xuXG4gICAgY29uc3QgcmVzdWx0cyA9IChhd2FpdCBQcm9taXNlLmFsbChcbiAgICAgIGJyZWFrRXZlbnRzLm1hcCgoYikgPT5cbiAgICAgICAgcG9zdFBsYW5uZXJNb2RpZnlFdmVudEluQ2FsZW5kYXIoXG4gICAgICAgICAgYixcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgJ2NyZWF0ZScsXG4gICAgICAgICAgZ29vZ2xlQ2FsZW5kYXJSZXNvdXJjZSxcbiAgICAgICAgICBmYWxzZSxcbiAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgIClcbiAgICAgIClcbiAgICApKSBhcyB7XG4gICAgICBpZDogc3RyaW5nO1xuICAgICAgZ2VuZXJhdGVkSWQ6IHN0cmluZztcbiAgICB9W107XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlc3VsdHMsXG4gICAgICAnIHJlc3VsdHMgZm9ybSBtb2RpZnlpbmcgcG9zdFBsYW5uZXJNb2RpZnlFdmVudEluQ2FsZW5kYXIgaW5zaWRlIGdlbmVyYXRlQnJlYWtFdmVudHNGb3JDYWxlbmRhclN5bmMnXG4gICAgKTtcbiAgICBpZiAoIShicmVha0V2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyBicmVha0V2ZW50cyB0byB1cHNlcnQnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgY29uc3QgZXZlbnRzVG9VcHNlcnQgPSBbXTtcbiAgICBmb3IgKGNvbnN0IHJlc3VsdCBvZiByZXN1bHRzKSB7XG4gICAgICBjb25zdCBmb3VuZEV2ZW50ID0gKGJyZWFrRXZlbnRzIGFzIEV2ZW50UGx1c1R5cGVbXSk/LmZpbmQoXG4gICAgICAgIChlKSA9PiBlPy5ldmVudElkID09PSByZXN1bHQ/LmdlbmVyYXRlZElkXG4gICAgICApO1xuICAgICAgaWYgKGZvdW5kRXZlbnQ/LmlkKSB7XG4gICAgICAgIGZvdW5kRXZlbnQuaWQgPSBgJHtyZXN1bHQ/LmlkfSMke2ZvdW5kRXZlbnQ/LmNhbGVuZGFySWR9YDtcbiAgICAgICAgZm91bmRFdmVudC5ldmVudElkID0gcmVzdWx0Py5pZDtcbiAgICAgICAgZXZlbnRzVG9VcHNlcnQucHVzaChmb3VuZEV2ZW50KTtcbiAgICAgIH1cbiAgICB9XG4gICAgYXdhaXQgdXBzZXJ0RXZlbnRzUG9zdFBsYW5uZXIoZXZlbnRzVG9VcHNlcnQpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2VuZXJhdGV6YnJlYWtFdmVudHNGb3JDYWxlbmRhclN5bmMnKTtcbiAgfVxufTtcblxuLy8gRGVmaW5lIEdvb2dsZUV2ZW50UGF0Y2hBdHRyaWJ1dGVzIGludGVyZmFjZVxuaW50ZXJmYWNlIEdvb2dsZUV2ZW50UGF0Y2hBdHRyaWJ1dGVzIHtcbiAgc3VtbWFyeT86IHN0cmluZztcbiAgZGVzY3JpcHRpb24/OiBzdHJpbmc7XG4gIGxvY2F0aW9uPzogc3RyaW5nO1xuICBzdGF0dXM/OiAnY29uZmlybWVkJyB8ICd0ZW50YXRpdmUnIHwgJ2NhbmNlbGxlZCc7XG4gIHRyYW5zcGFyZW5jeT86ICdvcGFxdWUnIHwgJ3RyYW5zcGFyZW50JztcbiAgdmlzaWJpbGl0eT86ICdkZWZhdWx0JyB8ICdwdWJsaWMnIHwgJ3ByaXZhdGUnIHwgJ2NvbmZpZGVudGlhbCc7XG4gIGNvbG9ySWQ/OiBzdHJpbmc7XG4gIGNvbmZlcmVuY2VEYXRhPzogUmVjb3JkPHN0cmluZywgYW55PiB8IG51bGw7XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBkaXJlY3RVcGRhdGVHb29nbGVFdmVudEFuZEhhc3VyYShcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgZXZlbnRJZDogc3RyaW5nLCAvLyBUaGlzIGlzIEdvb2dsZSdzIGV2ZW50IElEXG4gIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYicsXG4gIHVwZGF0ZXM6IFBhcnRpYWw8R29vZ2xlRXZlbnRQYXRjaEF0dHJpYnV0ZXM+XG4pOiBQcm9taXNlPGJvb2xlYW4+IHtcbiAgaWYgKCFldmVudElkIHx8IE9iamVjdC5rZXlzKHVwZGF0ZXMpLmxlbmd0aCA9PT0gMCkge1xuICAgIGNvbnNvbGUubG9nKCdNaXNzaW5nIGV2ZW50SWQgb3IgZW1wdHkgdXBkYXRlcyBvYmplY3QuJyk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG5cbiAgdHJ5IHtcbiAgICAvLyAxLiBQcmVwYXJlIEdvb2dsZSBDYWxlbmRhciBBUEkgcGF0Y2ggcmVxdWVzdFxuICAgIGNvbnN0IHBhdGNoUmVxdWVzdEJvZHk6IFBhcnRpYWw8R29vZ2xlRXZlbnRQYXRjaEF0dHJpYnV0ZXM+ID0ge1xuICAgICAgLi4udXBkYXRlcyxcbiAgICB9O1xuXG4gICAgLy8gMi4gR2V0IEdvb2dsZSBBUEkgVG9rZW5cbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZUFQSVRva2VuKFxuICAgICAgdXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJSZXNvdXJjZSxcbiAgICAgIGNsaWVudFR5cGVcbiAgICApO1xuICAgIGlmICghdG9rZW4pIHtcbiAgICAgIGNvbnNvbGUuZXJyb3IoJ0ZhaWxlZCB0byBnZXQgR29vZ2xlIEFQSSB0b2tlbi4nKTtcbiAgICAgIHJldHVybiBmYWxzZTtcbiAgICB9XG5cbiAgICAvLyAzLiBJbml0aWFsaXplIEdvb2dsZSBDYWxlbmRhciBBUElcbiAgICBjb25zdCBnb29nbGVDYWxlbmRhciA9IGdvb2dsZS5jYWxlbmRhcih7XG4gICAgICB2ZXJzaW9uOiAndjMnLFxuICAgICAgaGVhZGVyczogeyBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCB9LFxuICAgIH0pO1xuXG4gICAgLy8gNC4gQ2FsbCBHb29nbGUgQ2FsZW5kYXIgQVBJIGV2ZW50cy5wYXRjaFxuICAgIHRyeSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYFBhdGNoaW5nIEdvb2dsZSBldmVudCAke2V2ZW50SWR9IGluIGNhbGVuZGFyICR7Y2FsZW5kYXJJZH0gd2l0aCB1cGRhdGVzOmAsXG4gICAgICAgIEpTT04uc3RyaW5naWZ5KHBhdGNoUmVxdWVzdEJvZHkpXG4gICAgICApO1xuICAgICAgYXdhaXQgZ29vZ2xlQ2FsZW5kYXIuZXZlbnRzLnBhdGNoKHtcbiAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgcmVxdWVzdEJvZHk6IHBhdGNoUmVxdWVzdEJvZHksXG4gICAgICAgIGNvbmZlcmVuY2VEYXRhVmVyc2lvbjogMSwgLy8gRW5hYmxlIGNvbmZlcmVuY2UgZGF0YSBtb2RpZmljYXRpb25zXG4gICAgICB9KTtcbiAgICAgIGNvbnNvbGUubG9nKGBHb29nbGUgZXZlbnQgJHtldmVudElkfSBwYXRjaGVkIHN1Y2Nlc3NmdWxseS5gKTtcbiAgICB9IGNhdGNoIChnb29nbGVFcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYEVycm9yIHBhdGNoaW5nIEdvb2dsZSBldmVudCAke2V2ZW50SWR9OmAsXG4gICAgICAgIGdvb2dsZUVycm9yLnJlc3BvbnNlPy5kYXRhIHx8IGdvb2dsZUVycm9yLm1lc3NhZ2VcbiAgICAgICk7XG4gICAgICByZXR1cm4gZmFsc2U7XG4gICAgfVxuXG4gICAgLy8gNS4gUHJlcGFyZSBIYXN1cmEgVXBkYXRlIFBheWxvYWRcbiAgICBjb25zdCBoYXN1cmFFdmVudElkID0gYCR7ZXZlbnRJZH0jJHtjYWxlbmRhcklkfWA7XG4gICAgY29uc3QgaGFzdXJhVXBkYXRlUGF5bG9hZDogYW55ID0ge1xuICAgICAgdXBkYXRlZEF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgfTtcblxuICAgIGlmICh1cGRhdGVzLnN1bW1hcnkgIT09IHVuZGVmaW5lZClcbiAgICAgIGhhc3VyYVVwZGF0ZVBheWxvYWQuc3VtbWFyeSA9IHVwZGF0ZXMuc3VtbWFyeTtcbiAgICBpZiAodXBkYXRlcy5kZXNjcmlwdGlvbiAhPT0gdW5kZWZpbmVkKVxuICAgICAgaGFzdXJhVXBkYXRlUGF5bG9hZC5ub3RlcyA9IHVwZGF0ZXMuZGVzY3JpcHRpb247IC8vIE1hcCBkZXNjcmlwdGlvbiB0byBub3Rlc1xuICAgIGlmICh1cGRhdGVzLmxvY2F0aW9uICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIC8vIEFzc3VtaW5nIEV2ZW50LmxvY2F0aW9uIGluIEhhc3VyYSBpcyBhIHNpbXBsZSB0ZXh0IGZpZWxkIGZvciBkaXJlY3QgdXBkYXRlcy5cbiAgICAgIC8vIElmIGl0J3MgYSBKU09OQiB0eXBlIGV4cGVjdGluZyB7IHRpdGxlOiBzdHJpbmcgfSwgdGhlbjpcbiAgICAgIC8vIGhhc3VyYVVwZGF0ZVBheWxvYWQubG9jYXRpb24gPSB7IHRpdGxlOiB1cGRhdGVzLmxvY2F0aW9uIH07XG4gICAgICBoYXN1cmFVcGRhdGVQYXlsb2FkLmxvY2F0aW9uID0gdXBkYXRlcy5sb2NhdGlvbjtcbiAgICB9XG4gICAgaWYgKHVwZGF0ZXMuc3RhdHVzICE9PSB1bmRlZmluZWQpXG4gICAgICBoYXN1cmFVcGRhdGVQYXlsb2FkLnN0YXR1cyA9IHVwZGF0ZXMuc3RhdHVzO1xuICAgIGlmICh1cGRhdGVzLnRyYW5zcGFyZW5jeSAhPT0gdW5kZWZpbmVkKVxuICAgICAgaGFzdXJhVXBkYXRlUGF5bG9hZC50cmFuc3BhcmVuY3kgPSB1cGRhdGVzLnRyYW5zcGFyZW5jeTtcbiAgICBpZiAodXBkYXRlcy52aXNpYmlsaXR5ICE9PSB1bmRlZmluZWQpXG4gICAgICBoYXN1cmFVcGRhdGVQYXlsb2FkLnZpc2liaWxpdHkgPSB1cGRhdGVzLnZpc2liaWxpdHk7XG4gICAgaWYgKHVwZGF0ZXMuY29sb3JJZCAhPT0gdW5kZWZpbmVkKVxuICAgICAgaGFzdXJhVXBkYXRlUGF5bG9hZC5jb2xvcklkID0gdXBkYXRlcy5jb2xvcklkO1xuXG4gICAgLy8gSGFuZGxlIGNvbmZlcmVuY2VEYXRhXG4gICAgaWYgKHVwZGF0ZXMuY29uZmVyZW5jZURhdGEgPT09IG51bGwpIHtcbiAgICAgIGhhc3VyYVVwZGF0ZVBheWxvYWQuaGFuZ291dExpbmsgPSBudWxsO1xuICAgICAgaGFzdXJhVXBkYXRlUGF5bG9hZC5jb25mZXJlbmNlSWQgPSBudWxsO1xuICAgICAgLy8gUG90ZW50aWFsbHkgY2xlYXIgb3RoZXIgY29uZmVyZW5jZSByZWxhdGVkIGZpZWxkcyBpbiBIYXN1cmEgaWYgdGhleSBleGlzdFxuICAgIH0gZWxzZSBpZiAodXBkYXRlcy5jb25mZXJlbmNlRGF0YSkge1xuICAgICAgLy8gQXR0ZW1wdCB0byBleHRyYWN0IGhhbmdvdXRMaW5rIGFuZCBjb25mZXJlbmNlSWRcbiAgICAgIC8vIFRoaXMgaXMgYSBzaW1wbGlmaWVkIGV4dHJhY3Rpb24uIEdvb2dsZSdzIGNvbmZlcmVuY2VEYXRhIGNhbiBiZSBjb21wbGV4LlxuICAgICAgaWYgKFxuICAgICAgICB1cGRhdGVzLmNvbmZlcmVuY2VEYXRhLmVudHJ5UG9pbnRzICYmXG4gICAgICAgIEFycmF5LmlzQXJyYXkodXBkYXRlcy5jb25mZXJlbmNlRGF0YS5lbnRyeVBvaW50cylcbiAgICAgICkge1xuICAgICAgICBjb25zdCB2aWRlb0VudHJ5UG9pbnQgPSB1cGRhdGVzLmNvbmZlcmVuY2VEYXRhLmVudHJ5UG9pbnRzLmZpbmQoXG4gICAgICAgICAgKGVwKSA9PiBlcC5lbnRyeVBvaW50VHlwZSA9PT0gJ3ZpZGVvJ1xuICAgICAgICApO1xuICAgICAgICBpZiAodmlkZW9FbnRyeVBvaW50ICYmIHZpZGVvRW50cnlQb2ludC51cmkpIHtcbiAgICAgICAgICBoYXN1cmFVcGRhdGVQYXlsb2FkLmhhbmdvdXRMaW5rID0gdmlkZW9FbnRyeVBvaW50LnVyaTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgICAgaWYgKHVwZGF0ZXMuY29uZmVyZW5jZURhdGEuY29uZmVyZW5jZUlkKSB7XG4gICAgICAgIGhhc3VyYVVwZGF0ZVBheWxvYWQuY29uZmVyZW5jZUlkID0gdXBkYXRlcy5jb25mZXJlbmNlRGF0YS5jb25mZXJlbmNlSWQ7XG4gICAgICB9XG4gICAgICAvLyBJZiB5b3Ugc3RvcmUgdGhlIGZ1bGwgY29uZmVyZW5jZURhdGEgb2JqZWN0IGluIEhhc3VyYSAoZS5nLiwgYXMgSlNPTkIpXG4gICAgICAvLyBoYXN1cmFVcGRhdGVQYXlsb2FkLmNvbmZlcmVuY2VEYXRhID0gdXBkYXRlcy5jb25mZXJlbmNlRGF0YTtcbiAgICB9XG5cbiAgICAvLyBSZW1vdmUgdW5kZWZpbmVkIGZpZWxkcyBmcm9tIHBheWxvYWQgdG8gYXZvaWQgSGFzdXJhIGVycm9yc1xuICAgIE9iamVjdC5rZXlzKGhhc3VyYVVwZGF0ZVBheWxvYWQpLmZvckVhY2goKGtleSkgPT4ge1xuICAgICAgaWYgKGhhc3VyYVVwZGF0ZVBheWxvYWRba2V5XSA9PT0gdW5kZWZpbmVkKSB7XG4gICAgICAgIGRlbGV0ZSBoYXN1cmFVcGRhdGVQYXlsb2FkW2tleV07XG4gICAgICB9XG4gICAgfSk7XG5cbiAgICBpZiAoXG4gICAgICBPYmplY3Qua2V5cyhoYXN1cmFVcGRhdGVQYXlsb2FkKS5sZW5ndGggPT09IDEgJiZcbiAgICAgIGhhc3VyYVVwZGF0ZVBheWxvYWQudXBkYXRlZEF0XG4gICAgKSB7XG4gICAgICBjb25zb2xlLmxvZygnTm8gbWFwcGFibGUgZmllbGRzIHRvIHVwZGF0ZSBpbiBIYXN1cmEgYmVzaWRlcyB1cGRhdGVkQXQuJyk7XG4gICAgICAvLyBTdGlsbCBwcm9jZWVkIHRvIHVwZGF0ZSAndXBkYXRlZEF0JyBvciByZXR1cm4gdHJ1ZSBpZiBHb29nbGUgdXBkYXRlIHdhcyB0aGUgb25seSBnb2FsXG4gICAgICAvLyBGb3Igbm93LCBsZXQncyBwcm9jZWVkIHRvIHVwZGF0ZSAndXBkYXRlZEF0J1xuICAgIH1cblxuICAgIC8vIDYuIENvbnN0cnVjdCBhbmQgZXhlY3V0ZSBIYXN1cmEgdXBkYXRlX0V2ZW50X2J5X3BrIG11dGF0aW9uXG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdVcGRhdGVFdmVudEJ5UGtEaXJlY3QnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gJHtvcGVyYXRpb25OYW1lfSgkaWQ6IFN0cmluZyEsICRjaGFuZ2VzOiBFdmVudF9zZXRfaW5wdXQhKSB7XG4gICAgICAgICAgICAgICAgdXBkYXRlX0V2ZW50X2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDogJGNoYW5nZXMpIHtcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkOiBoYXN1cmFFdmVudElkLFxuICAgICAgY2hhbmdlczogaGFzdXJhVXBkYXRlUGF5bG9hZCxcbiAgICB9O1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgVXBkYXRpbmcgSGFzdXJhIGV2ZW50ICR7aGFzdXJhRXZlbnRJZH0gd2l0aCBwYXlsb2FkOmAsXG4gICAgICBKU09OLnN0cmluZ2lmeShoYXN1cmFVcGRhdGVQYXlsb2FkKVxuICAgICk7XG5cbiAgICBjb25zdCBoYXN1cmFSZXNwb25zZTogYW55ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsIC8vIE9yIGFwcHJvcHJpYXRlIHVzZXIgcm9sZVxuICAgICAgICB9LFxuICAgICAgICByZXNwb25zZVR5cGU6ICdqc29uJyxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgaWYgKGhhc3VyYVJlc3BvbnNlLmVycm9ycykge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYEVycm9yIHVwZGF0aW5nIEhhc3VyYSBldmVudCAke2hhc3VyYUV2ZW50SWR9OmAsXG4gICAgICAgIEpTT04uc3RyaW5naWZ5KGhhc3VyYVJlc3BvbnNlLmVycm9ycywgbnVsbCwgMilcbiAgICAgICk7XG4gICAgICAvLyBHb29nbGUgdXBkYXRlIHdhcyBzdWNjZXNzZnVsLCBidXQgSGFzdXJhIGZhaWxlZC5cbiAgICAgIC8vIE1heSBuZWVkIGEgcmVjb25jaWxpYXRpb24gc3RyYXRlZ3kgb3Igc3BlY2lmaWMgZXJyb3IgaGFuZGxpbmcuXG4gICAgICByZXR1cm4gZmFsc2U7IC8vIEluZGljYXRlIHBhcnRpYWwgZmFpbHVyZVxuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGBIYXN1cmEgZXZlbnQgJHtoYXN1cmFFdmVudElkfSB1cGRhdGVkIHN1Y2Nlc3NmdWxseS5gKTtcbiAgICByZXR1cm4gdHJ1ZTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ0FuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQgaW4gZGlyZWN0VXBkYXRlR29vZ2xlRXZlbnRBbmRIYXN1cmE6JyxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHN0cmVhbVRvU3RyaW5nKHN0cmVhbTogUmVhZGFibGUpOiBQcm9taXNlPHN0cmluZz4ge1xuICByZXR1cm4gYXdhaXQgbmV3IFByb21pc2UoKHJlc29sdmUsIHJlamVjdCkgPT4ge1xuICAgIGNvbnN0IGNodW5rczogVWludDhBcnJheVtdID0gW107XG4gICAgc3RyZWFtLm9uKCdkYXRhJywgKGNodW5rKSA9PiBjaHVua3MucHVzaChjaHVuaykpO1xuICAgIHN0cmVhbS5vbignZXJyb3InLCByZWplY3QpO1xuICAgIHN0cmVhbS5vbignZW5kJywgKCkgPT4gcmVzb2x2ZShCdWZmZXIuY29uY2F0KGNodW5rcykudG9TdHJpbmcoJ3V0Zi04JykpKTtcbiAgfSk7XG59XG5cbmV4cG9ydCBjb25zdCBhZGRUb1F1ZXVlRm9yVmVjdG9yU2VhcmNoID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZXZlbnRzOiBFdmVudE9iamVjdEZvclZlY3RvclR5cGVbXVxuKSA9PiB7XG4gIGNvbnN0IHByb2R1Y2VyID0ga2Fma2EucHJvZHVjZXIoeyBtYXhJbkZsaWdodFJlcXVlc3RzOiAxLCBpZGVtcG90ZW50OiB0cnVlIH0pO1xuICBhd2FpdCBwcm9kdWNlci5jb25uZWN0KCk7XG5cbiAgY29uc3QgdHJhbnNhY3Rpb24gPSBhd2FpdCBwcm9kdWNlci50cmFuc2FjdGlvbigpO1xuXG4gIHRyeSB7XG4gICAgLy8gcHJvY2Vzcy5lbnYuRVZFTlRfVE9fVkVDVE9SX1FVRVVFX1VSTFxuICAgIGNvbnN0IHNpbmdsZXRvbklkID0gdXVpZCgpO1xuICAgIGNvbnN0IHBhcmFtcyA9IHtcbiAgICAgIEJvZHk6IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgZXZlbnRzLFxuICAgICAgICB1c2VySWQsXG4gICAgICB9KSxcbiAgICAgIEJ1Y2tldDogYnVja2V0TmFtZSxcbiAgICAgIEtleTogYCR7dXNlcklkfS8ke3NpbmdsZXRvbklkfS5qc29uYCxcbiAgICAgIENvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgfTtcblxuICAgIGNvbnN0IHMzQ29tbWFuZCA9IG5ldyBQdXRPYmplY3RDb21tYW5kKHBhcmFtcyk7XG5cbiAgICBjb25zdCBzM1Jlc3BvbnNlID0gYXdhaXQgczNDbGllbnQuc2VuZChzM0NvbW1hbmQpO1xuXG4gICAgY29uc29sZS5sb2coczNSZXNwb25zZSwgJyBzM1Jlc3BvbnNlJyk7XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHRyYW5zYWN0aW9uLnNlbmQoe1xuICAgICAgdG9waWM6IGthZmthR29vZ2xlQ2FsZW5kYXJTeW5jVG9waWMsXG4gICAgICBtZXNzYWdlczogW1xuICAgICAgICB7IHZhbHVlOiBKU09OLnN0cmluZ2lmeSh7IGZpbGVLZXk6IGAke3VzZXJJZH0vJHtzaW5nbGV0b25JZH0uanNvbmAgfSkgfSxcbiAgICAgIF0sXG4gICAgfSk7XG5cbiAgICBjb25zdCBhZG1pbiA9IGthZmthLmFkbWluKCk7XG5cbiAgICBhd2FpdCBhZG1pbi5jb25uZWN0KCk7XG4gICAgY29uc3QgcGFydGl0aW9ucyA9IGF3YWl0IGFkbWluLmZldGNoT2Zmc2V0cyh7XG4gICAgICBncm91cElkOiBrYWZrYUdvb2dsZUNhbGVuZGFyU3luY0dyb3VwSWQsXG4gICAgICB0b3BpY3M6IFtrYWZrYUdvb2dsZUNhbGVuZGFyU3luY1RvcGljXSxcbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhwYXJ0aXRpb25zKTtcbiAgICBhd2FpdCBhZG1pbi5kaXNjb25uZWN0KCk7XG5cbiAgICBhd2FpdCB0cmFuc2FjdGlvbi5zZW5kT2Zmc2V0cyh7XG4gICAgICBjb25zdW1lckdyb3VwSWQ6IGthZmthR29vZ2xlQ2FsZW5kYXJTeW5jR3JvdXBJZCxcbiAgICAgIHRvcGljczogW1xuICAgICAgICB7XG4gICAgICAgICAgdG9waWM6IGthZmthR29vZ2xlQ2FsZW5kYXJTeW5jVG9waWMsXG4gICAgICAgICAgcGFydGl0aW9uczogcGFydGl0aW9ucz8uWzBdPy5wYXJ0aXRpb25zLFxuICAgICAgICB9LFxuICAgICAgXSxcbiAgICB9KTtcblxuICAgIGF3YWl0IHRyYW5zYWN0aW9uLmNvbW1pdCgpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXNwb25zZSxcbiAgICAgICcgcmVzcG9uc2Ugc3VjY2Vzc2Z1bGx5IGFkZGVkIHRvIHF1ZXVlIGluc2lkZSBhZGRUb1F1ZXVlRm9yVmVjdG9yU2VhcmNoJ1xuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBhZGQgdG8gcXVldWUnKTtcbiAgICBhd2FpdCB0cmFuc2FjdGlvbi5hYm9ydCgpO1xuICB9XG59O1xuIl19