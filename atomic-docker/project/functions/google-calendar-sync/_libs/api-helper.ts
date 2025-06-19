import got from "got"
import { authApiToken, bucketName, eventVectorName, googleCalendarResource, googleCalendarStopWatchUrl, googleClientIdAndroid, googleClientIdAtomicWeb, googleClientIdIos, googleClientIdWeb, googleClientSecretAtomicWeb, googleClientSecretWeb, googleColorUrl, googleMeetResource, googleTokenUrl, hasuraAdminSecret, hasuraGraphUrl, kafkaGoogleCalendarSyncGroupId, kafkaGoogleCalendarSyncTopic, searchIndex, selfGoogleCalendarWebhookPublicUrl, text2VectorUrl, vectorDimensions, zoomBaseTokenUrl, zoomBaseUrl, zoomClientId, zoomClientSecret, zoomIVForPass, zoomPassKey, zoomResourceName, zoomSaltForPass } from "./constants"
import { CalendarType, CalendarWebhookType, esResponseBody, EventPlusType, EventResourceType, EventType, GoogleAttachmentType, GoogleAttendeeType, GoogleConferenceDataType, GoogleEventType1, GoogleExtendedPropertiesType, GoogleReminderType, GoogleSendUpdatesType, GoogleSourceType, GoogleTransparencyType, GoogleVisibilityType, MeetingAssistAttendeeType, OverrideTypes, ReminderType, UserPreferenceType } from "./types"
import _ from 'lodash'
import { v4 as uuid } from 'uuid'
import { getISODay } from 'date-fns'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import duration from 'dayjs/plugin/duration'
// import isoWeek from 'dayjs/plugin/isoWeek'
import isBetween from 'dayjs/plugin/isBetween'
import timezone from 'dayjs/plugin/timezone'
import { AttendeeType, CalendarIntegrationType, CalendarWatchRequestResourceType, colorTypeResponse, ConferenceType } from "@/google-calendar-sync/_libs/types/googleCalendarSync/types"
import { google } from 'googleapis'
import { Client } from '@opensearch-project/opensearch'
import { initialGoogleCalendarSync2 } from "@google_calendar_sync/googleCalendarSync/google-calendar-sync-admin"
import { EventTriggerType } from '@/google-calendar-sync/_libs/types/googlePeopleSync/types'
import axios from "axios"
import qs from 'qs'
import crypto from 'crypto'
import { Readable } from "stream"
import { EventObjectForVectorType } from "@/google-calendar-sync/_libs/types/event2Vectors/types"
import { PutObjectCommand, S3Client } from "@aws-sdk/client-s3"
import { Kafka, logLevel } from 'kafkajs'
import ip from 'ip'

dayjs.extend(utc)
dayjs.extend(duration)
// dayjs.extend(isoWeek)
dayjs.extend(isBetween)
dayjs.extend(timezone)

const s3Client = new S3Client({
    credentials: {
        accessKeyId: process.env.S3_ACCESS_KEY,
        secretAccessKey: process.env.S3_SECRET_KEY,
    },
    endpoint: process.env.S3_ENDPOINT,
    forcePathStyle: true,
})



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
})

export const insertEventTriggers = async (
    objects: EventTriggerType[],
) => {
    try {
        const operationName = 'insertEventTriggers'
        const query = `
      mutation insertEventTriggers($objects: [Event_Trigger_insert_input!]!) {
        insert_Event_Trigger(objects: $objects) {
          affected_rows
        }
      }
    `
        const variables = {
            objects
        }

        const res: { data: { insert_Event_Trigger: { affected_rows: number } } } = await got.post(
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

        console.log(res, ' affected_rows inside insert event triggers')
    } catch (e) {
        console.log(e, ' unable to insert event trigger')
    }
}

export const getEventTriggerByResourceId = async (
    resourceId: string,
) => {
    try {
        if (!resourceId) {
            console.log('no resourceId inside getEventTriggerByResourceId')
            return
        }

        const operationName = 'GetEventTriggerByResourceId'
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
    `
        const response: { data: { Event_Trigger: EventTriggerType[] } } = await got.post(
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
                        resourceId,
                    },
                },
            },
        ).json()
        console.log(response, ' response inside getEventTriggerByResourceId')
        return response?.data?.Event_Trigger?.[0]

    } catch (e) {
        console.log(e, ' unable to getEventTriggerByResourceId')
    }
}

export const deleteEventTriggerById = async (
    id: string,
) => {
    try {
        const operationName = 'deleteEventTriggerById'
        const query = `
      mutation deleteEventTriggerById($id: uuid!) {
        delete_Event_Trigger_by_pk(id: $id) {
          id
        }
      }
    `
        const res = await got.post(
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
        console.log(res, ' deleteEventTriggerById')
    } catch (e) {
        console.log(e, ' deleteEventTriggerById')
    }
}

export const resetGoogleSyncForCalendar = async (
    calendarId: string,
    userId: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    try {
        const operationName = 'updateCalendar'
        const query = `mutation updateCalendar($id: String!, $changes: Calendar_set_input) {
      update_Calendar_by_pk(pk_columns: {id: $id}, _set: $changes) {
        pageToken
        syncToken
      }
    }
    `
        const variables = {
            id: calendarId,
            changes: {
                pageToken: null,
                syncToken: null
            }
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
        console.log(response, ' this is response in resetGoogleIntegrationSync')
        // const { token: authToken } = await getGoogleIntegration(calendarIntegrationId)
        return initialGoogleCalendarSync2(
            calendarId,
            userId,
            clientType,
        )
    } catch (e) {
        console.log(e, ' unable to reset google integration sync')
    }

}

export const deleteMeetingAssistsGivenIds = async (
    ids: string[],
) => {
    try {
        const operationName = 'DeleteMeetingAssistsByIds'
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
        `

        const variables = {
            ids,
        }

        const res = await got.post(hasuraGraphUrl, {
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

        console.log(res, ' successfully deleted meetingassists with given ids')
    } catch (e) {
        console.log(e, ' unable to delete meeting assists given ids')
    }
}

export const addlocalItemsToEvent2VectorObjects =  (
    localItems: EventResourceType[],
    event2VectorObjects: EventObjectForVectorType[],
    calendarId: string,
  ) => {
    for (const localItem of localItems) {
      const status = 'cancelled'
      if (localItem?.status === status) {
        (event2VectorObjects as EventObjectForVectorType[]).push({
          method: 'delete',
          event: localItem,
          calendarId,
        })
      } else { 
        (event2VectorObjects as EventObjectForVectorType[]).push({
          method: 'upsert',
          event: localItem,
          calendarId,
        })
      }
    }
  }

export const incrementalGoogleCalendarSync2 = async (
    calendarId: string,
    userId: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
    parentSyncToken: string,
    parentPageToken?: string,
    colorItem?: colorTypeResponse,
) => {
    try {
        let pageToken = parentPageToken
        let syncToken = parentSyncToken
        let localItems: EventResourceType[] | [] = []
        const event2VectorObjects: EventObjectForVectorType[] | [] = []


        const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType)

        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        })

        const initialVariables: any = {
            // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
            calendarId,
            // Whether to include deleted events (with status equals "cancelled") in the result. Cancelled instances of recurring events (but not the underlying recurring event) will still be included if showDeleted and singleEvents are both False. If showDeleted and singleEvents are both True, only single instances of deleted events (but not the underlying recurring events) are returned. Optional. The default is False.
            showDeleted: true,
            // Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves. Optional. The default is False.
            singleEvents: true,
            syncToken,
        }

        if (parentPageToken) {
            initialVariables.pageToken = parentPageToken
        }

        const res = await googleCalendar.events.list(initialVariables)
        console.log(res.data)

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
        const { items, nextPageToken, nextSyncToken } = res.data

        localItems = items as EventResourceType[]
        pageToken = nextPageToken
        syncToken = nextSyncToken

        addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId)

        await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)
        const status = 'cancelled'

        const deletedEvents = localItems.filter((e) => (e?.status === status))

        if (deletedEvents?.[0]?.id) {
            const returnedDeletedEventValues = await deleteEvents(deletedEvents, calendarId)
            const meetingIdsToDelete = returnedDeletedEventValues
                ?.filter(e => !!(e?.meetingId))
                ?.map(e => (e?.meetingId))

            if (meetingIdsToDelete && (meetingIdsToDelete?.length > 0)) {
                await deleteMeetingAssistsGivenIds(meetingIdsToDelete)
            }

            // delete any virtual conferences
            await deleteConferences(returnedDeletedEventValues)
            

            const promises = [
                deleteAttendees(deletedEvents, calendarId),
                deleteReminders(deletedEvents, userId, calendarId)
            ]

            await Promise.all(promises)
        }

        const eventsToUpsert = localItems?.filter((e) => (e?.status !== status))

        // no events to upsert check next pagetoken
        if (!(eventsToUpsert?.[0]?.id)) {
            console.log('no events to upsert check next pagetoken')
            const variables: any = {
                // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
                calendarId,
                // Whether to include deleted events (with status equals "cancelled") in the result. Cancelled instances of recurring events (but not the underlying recurring event) will still be included if showDeleted and singleEvents are both False. If showDeleted and singleEvents are both True, only single instances of deleted events (but not the underlying recurring events) are returned. Optional. The default is False.
                showDeleted: true,
                // Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves. Optional. The default is False.
                singleEvents: true,
                syncToken,
            }

            if (pageToken) {
                variables.pageToken = pageToken
                const res = await googleCalendar.events.list(variables)
                console.log(res.data)

                const { items, nextPageToken, nextSyncToken } = res.data

                localItems = items as EventResourceType[]
                pageToken = nextPageToken
                syncToken = nextSyncToken

                addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId)
                await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)
                const deletedEvents = localItems.filter((e) => (e?.status === status))

                if (deletedEvents?.[0]?.id) {

                    const returnedDeletedEventValues = await deleteEvents(deletedEvents, calendarId)
                    const meetingIdsToDelete = returnedDeletedEventValues
                        ?.filter(e => !!(e?.meetingId))
                        ?.map(e => (e?.meetingId))

                    if (meetingIdsToDelete && (meetingIdsToDelete?.length > 0)) {
                        await deleteMeetingAssistsGivenIds(meetingIdsToDelete)
                    }
                    
                    await deleteConferences(returnedDeletedEventValues)

                    const promises = [
                        deleteAttendees(deletedEvents, calendarId),
                        deleteReminders(deletedEvents, userId, calendarId)
                    ]

                    await Promise.all(promises)
                }

                const eventsToUpsert2 = localItems?.filter((e) => (e?.status !== status))
                if (eventsToUpsert2?.[0]?.id) {

                    await upsertConference2(eventsToUpsert2, userId, calendarId)
                    await upsertEvents2(eventsToUpsert2, userId, calendarId, colorItem)
                    

                    const promises = [
                        deleteReminders(eventsToUpsert2, userId, calendarId),
                        insertRemindersGivenEventResource(eventsToUpsert2, userId, calendarId),
                        upsertAttendees2(eventsToUpsert2, userId, calendarId),

                    ]

                    await Promise.all(promises)
                }
            }
        } else {

            await upsertConference2(eventsToUpsert, userId, calendarId)
            await upsertEvents2(eventsToUpsert, userId, calendarId, colorItem)
            
            await deleteReminders(eventsToUpsert, userId, calendarId)
            const promises = [
                insertRemindersGivenEventResource(eventsToUpsert, userId, calendarId),
                upsertAttendees2(eventsToUpsert, userId, calendarId),
            ]
            await Promise.all(promises)

        }

        if (pageToken) {
            // fetch all pages
            while (pageToken) {
                const variables: any = {
                    // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
                    calendarId,
                    // Token specifying which result page to return. Optional.
                    pageToken,
                    // Whether to include deleted events (with status equals "cancelled") in the result. Cancelled instances of recurring events (but not the underlying recurring event) will still be included if showDeleted and singleEvents are both False. If showDeleted and singleEvents are both True, only single instances of deleted events (but not the underlying recurring events) are returned. Optional. The default is False.
                    showDeleted: true,
                    // Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves. Optional. The default is False.
                    singleEvents: true,
                    syncToken,
                }

                const res = await googleCalendar.events.list(variables)
                console.log(res.data)

                const { items, nextPageToken, nextSyncToken } = res.data

                localItems = items as EventResourceType[]
                pageToken = nextPageToken
                syncToken = nextSyncToken
                // tokens in case something goes wrong
                // update pageToken and syncToken

                addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId)

                await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)

                const deletedEvents = localItems.filter((e) => (e?.status === status))

                if (deletedEvents?.[0]?.id) {

                    const returnedDeletedEventValues = await deleteEvents(deletedEvents, calendarId)
                    const meetingIdsToDelete = returnedDeletedEventValues
                        ?.filter(e => !!(e?.meetingId))
                        ?.map(e => (e?.meetingId))

                    if (meetingIdsToDelete && (meetingIdsToDelete?.length > 0)) {
                        await deleteMeetingAssistsGivenIds(meetingIdsToDelete)
                    }
                    
                    await deleteConferences(returnedDeletedEventValues)

                    const promises = [
                        deleteAttendees(deletedEvents, calendarId),
                        deleteReminders(deletedEvents, userId, calendarId)
                    ]

                    await Promise.all(promises)
                }

                const eventsToUpsert = localItems?.filter((e) => (e?.status !== status))

                // no events to upsert check next pagetoken
                if (!(eventsToUpsert?.[0]?.id)) {
                    console.log('no events to upsert check next pagetoken')
                    const variables: any = {
                        // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
                        calendarId,
                        // Whether to include deleted events (with status equals "cancelled") in the result. Cancelled instances of recurring events (but not the underlying recurring event) will still be included if showDeleted and singleEvents are both False. If showDeleted and singleEvents are both True, only single instances of deleted events (but not the underlying recurring events) are returned. Optional. The default is False.
                        showDeleted: true,
                        // Whether to expand recurring events into instances and only return single one-off events and instances of recurring events, but not the underlying recurring events themselves. Optional. The default is False.
                        singleEvents: true,
                        syncToken,
                    }

                    if (pageToken) {
                        variables.pageToken = pageToken
                        const res = await googleCalendar.events.list(variables)
                        console.log(res.data)

                        const { items, nextPageToken, nextSyncToken } = res.data

                        localItems = items as EventResourceType[]
                        pageToken = nextPageToken
                        syncToken = nextSyncToken

                        addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId)

                        await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)
                        const deletedEvents = localItems.filter((e) => (e?.status === status))

                        if (deletedEvents?.[0]?.id) {

                            const returnedDeletedEventValues = await deleteEvents(deletedEvents, calendarId)
                            const meetingIdsToDelete = returnedDeletedEventValues
                                ?.filter(e => !!(e?.meetingId))
                                ?.map(e => (e?.meetingId))

                            if (meetingIdsToDelete && (meetingIdsToDelete?.length > 0)) {
                                await deleteMeetingAssistsGivenIds(meetingIdsToDelete)
                            }
                            
                            await deleteConferences(returnedDeletedEventValues)

                            const promises = [
                                deleteAttendees(deletedEvents, calendarId),
                                deleteReminders(deletedEvents, userId, calendarId)
                            ]

                            await Promise.all(promises)
                        }

                        const eventsToUpsert2 = localItems?.filter((e) => (e?.status !== status))
                        if (eventsToUpsert2) {

                            await upsertConference2(eventsToUpsert2, userId, calendarId)
                            await upsertEvents2(eventsToUpsert2, userId, calendarId, colorItem)
                           

                            const promises = [
                                deleteReminders(eventsToUpsert2, userId, calendarId),
                                insertRemindersGivenEventResource(eventsToUpsert2, userId, calendarId),
                                upsertAttendees2(eventsToUpsert2, userId, calendarId),
                            ]

                            await Promise.all(promises)

                        }
                    }
                    continue
                }

                await upsertConference2(eventsToUpsert, userId, calendarId)
                await upsertEvents2(eventsToUpsert, userId, calendarId, colorItem)
                

                const promises = [
                    deleteReminders(eventsToUpsert, userId, calendarId),
                    insertRemindersGivenEventResource(eventsToUpsert, userId, calendarId),
                    upsertAttendees2(eventsToUpsert, userId, calendarId),
                ]

                await Promise.all(promises)

            }

            await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)
        }

        await addToQueueForVectorSearch(userId, event2VectorObjects)

        return true
    } catch (e) {
        console.log(e, ' unable to incremental google sync')
        if (e.code === 410) {
            // reset sync
            await resetGoogleSyncForCalendar(calendarId, userId, clientType)
            return true
        }
        return false
    }
}

export const getCalendarWebhookById = async (
    channelId: string,
) => {
    try {
        const operationName = 'GetCalendarPushNotificationById'
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
    `

        const variables = {
            id: channelId,
        }

        const res: { data: { Calendar_Push_Notification_by_pk: CalendarWebhookType } } = await got.post(
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

        console.log(res, ' res from getCalendarWebhook')
        return res?.data?.Calendar_Push_Notification_by_pk
    } catch (e) {

        console.log(e, ' unable to getCalendarWebhook')
    }
}

export const convertTextToVectorSpace2 = async (
    text: string,
): Promise<number[]> => {
    try {
        if (!text) {
            throw new Error('no text provided insdie convertTextToVectorSpace')
        }

        const vector: number[] = await got.post(
            text2VectorUrl,
            {
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Basic ${Buffer.from(`admin:${authApiToken}`).toString('base64')}`,
                },
                json: {
                    sentences: [text]
                },
            }
        ).json()

        console.log(vector, ' vector inside convertTextToVectorSpace2')
        return vector
    } catch (e) {
        console.log(e, ' unable to convertTextToVectorSpace')
    }
}

export const deleteDocInSearch3 = async (
    id: string,
) => {
    try {
        const client = await getSearchClient()
        const response = await client.delete({
            id,
            index: searchIndex,
        })
        console.log('Deleting document in search:')
        console.log(response.body)
    } catch (e) {
        console.log(e, ' unable to delete doc')
    }
}

export const getSearchClient = async () => {
    try {
        return new Client({
            node: process.env.OPENSEARCH_ENDPOINT,
            auth: {
                username: process.env.OPENSEARCH_USERNAME,
                password: process.env.OPENSEARCH_PASSWORD,
              }
        })
    } catch (e) {
        console.log(e, ' unable to get credentials from getSearchClient')
    }
    
}

export const searchData3 = async (
    userId: string,
    searchVector: number[],
): Promise<esResponseBody> => {
    try {
        const client = await getSearchClient()
        const response = await client.search({
            index: searchIndex,
            body: {
                "size": vectorDimensions,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": {
                                    "term": {
                                        userId,
                                    }
                                }
                            }
                        },
                        "script": {
                            "lang": "knn",
                            "source": "knn_score",
                            "params": {
                                "field": eventVectorName,
                                "query_value": searchVector,
                                "space_type": "cosinesimil"
                            }
                        }
                    }
                },
                "min_score": 1.2
            }
        })
        console.log(response, ' search data in search engine')
        return response.body
    } catch (e) {
        console.log(e, ' unable to search data')
    }
}

export const deleteCalendarWebhookById = async (
    channelId: string,
) => {
    try {
        const operationName = 'DeleteCalendarPushNotificationById'
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
      `

        const variables = {
            id: channelId,
        }

        const res: { data: { delete_Calendar_Push_Notification_by_pk: CalendarWebhookType } } = await got.post(
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

        console.log(res, ' res from  deleteCalendarWebhookById')

    } catch (e) {
        console.log(e, ' unable to delete calendar webhook by id')
    }
}

export const stopCalendarWatch = async (
    id: string,
    resourceId: string,
) => {
    try {
        const res = await got.post(
            googleCalendarStopWatchUrl,
            {
                headers: {
                    'Content-Type': 'application/json',
                },
                json: {
                    id,
                    resourceId,
                },
            },
        )
        console.log(res, ' res inside stopCalendarWatch')
    } catch (e) {
        console.log(e, ' unable to stop calendar watch')
    }
}

export const getCalendarWebhookByCalendarId = async (
    calendarId: string,
) => {
    try {
        const operationName = 'GetCalendarPushNotificationByCalendarId'
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
    `

        const variables = {
            calendarId,
        }

        const res: { data: { Calendar_Push_Notification: CalendarWebhookType[] } } = await got.post(
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

        console.log(res, ' res from getCalendarWebhook')
        return res?.data?.Calendar_Push_Notification?.[0]
    } catch (e) {
        console.log(e, ' unable to getCalendarWebhookByCalendarId')
    }
}

export const upsertEvents2 = async (
    events: EventResourceType[],
    userId: string,
    calendarId: string,
    colorItem?: colorTypeResponse,
) => {
    try {
        console.log(events, ' events inside upsertEvents')
        console.log(colorItem, ' colorItem inside upsertEvents')
        if (!events?.[0]?.id) return null

        // format events for insert
        const formattedEvents = events
            .filter(e => !!e?.id)
            ?.filter(e => (!!e?.start?.timeZone || !!e?.end?.timeZone))
            .map(event => {
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
                    startDate: event?.start?.dateTime || dayjs(event?.start?.date).tz(event?.start?.timeZone || dayjs.tz.guess(), true).format(),
                    endDate: event?.end?.dateTime || dayjs(event?.end?.date).tz(event?.end?.timeZone || dayjs.tz.guess(), true).format(),
                    allDay: event?.start?.date ? true : false,
                    timezone: event?.start?.timeZone || event?.end?.timeZone,
                    endTimeUnspecified: event?.endTimeUnspecified,
                    recurrence: event?.recurrence,
                    recurringEventId: event?.recurringEventId,
                    originalStartDate: event?.originalStartTime?.dateTime || event?.originalStartTime?.date,
                    originalAllDay: event?.originalStartTime?.date ? true : false,
                    originalTimezone: event?.originalStartTime?.timeZone,
                    transparency: event?.transparency,
                    visibility: event?.visibility,
                    iCalUID: event?.iCalUID,
                    attendeesOmitted: event?.attendeesOmitted,
                    extendedProperties: (event?.extendedProperties?.private
                        || event?.extendedProperties?.shared)
                        ? {
                            private: event?.extendedProperties?.private && {
                                keys: Object.keys(event?.extendedProperties?.private),
                                values: Object.values(event?.extendedProperties?.private),
                            },
                            shared: event?.extendedProperties?.shared && {
                                keys: Object.keys(event?.extendedProperties?.shared),
                                values: Object.values(event?.extendedProperties?.shared),
                            }
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
                }
            })

        if (!(formattedEvents?.length > 0)) {
            return
        }
        /*
          dynamically generate upsert query based on the number of columns
          and set the update_columns to the columns that are not undefined
        */
        const operationName = 'InsertEvent'
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
      `
        const variables = {
            events: formattedEvents
        }


        const response: any = await got.post(hasuraGraphUrl, {
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


        console.log(response, ' this is response in upsertEvents')
        response?.errors?.forEach(e => console.log(e))
    } catch (e) {
        console.log(e, ' unable to upsertEvents')
    }
}

export const upsertConference2 = async (
    events: EventResourceType[],
    userId: string,
    calendarId: string,
) => {
    try {
        const formattedConference: ConferenceType[] = events.map((e) => {
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
            }
        })
        if (!(formattedConference?.filter(c => !!(c?.id))?.length > 0)) {
            return
        }

        /*
        dynamically generate upsert query based on the number of columns
        and set the update_columns to the columns that are not undefined
        */

        const operationName = 'InsertConference'
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
      `
        const variables = {
            conferences: formattedConference
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
        console.log(response, ' this is response in upsertConference')

    } catch (e) {
        console.log(e, ' unable to upsert conference data')
    }
}


export const insertCalendarWebhook = async (
    webhook: CalendarWebhookType,
) => {
    try {
        const operationName = 'InsertCalendarPushNotification'
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
      `
        const variables = {
            webhook,
        }

        const response: { data: { insert_Calendar_Push_Notification_one: CalendarWebhookType } } = await got.post(hasuraGraphUrl, {
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

        console.log(response, ' response after upserting calendar webhook')

        return response?.data?.insert_Calendar_Push_Notification_one

    } catch (e) {
        console.log(e, ' unable to upsertCalendarWebhook')
    }
}

export const upsertAttendees2 = async (
    events: EventResourceType[],
    userId: string,
    calendarId: string,
) => {
    try {
        const attendees: AttendeeType[] = []
        events
            .filter(e => !!(e?.attendees?.[0]?.id))
            .forEach((e) => {
                e?.attendees?.forEach((a) => {
                    attendees.push({
                        id: a?.id,
                        userId,
                        name: a?.displayName,
                        emails: [{ primary: false, value: a?.email, displayName: a?.displayName, type: '' }],
                        eventId: `${e?.id}#${calendarId}`,
                        additionalGuests: a?.additionalGuests,
                        comment: a?.comment,
                        responseStatus: a?.responseStatus,
                        optional: a?.optional,
                        resource: a?.resource,
                        deleted: false,
                        updatedAt: dayjs().utc().toISOString(),
                        createdDate: dayjs().toISOString(),
                    })
                })
            })

        if (!(attendees?.[0]?.emails?.[0])) {
            return
        }

        const operationName = 'InsertAttendee'

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
    `
        const variables = {
            attendees,
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

        console.log(response, ' this is response in upsertAttendees')

    } catch (e) {
        console.log(e, ' unable to upsertAttendees')
    }
}

export const updateGoogleIntegration = async (
    calendarIntegrationId: string,
    syncEnabled?: boolean,
) => {
    try {
        const operationName = 'updateCalendarIntegration'
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
    `
        let variables: any = {
            id: calendarIntegrationId
        }

        if (syncEnabled === false) {
            variables = { ...variables, syncEnabled }
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

        console.log(response, ' this is response in updateGoogleIntegration')
    } catch (e) {
        console.log(e, ' unable to update google integration')
    }
}


export const updateGoogleCalendarTokensInDb = async (
    calendarId: string,
    syncToken?: string,
    pageToken?: string,
) => {
    try {
        const operationName = 'updateCalendar'
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
    `
        let variables: any = {
            id: calendarId,
        }

        if (syncToken?.length > 0) {
            variables = { ...variables, syncToken }
        }

        if (pageToken?.length > 0) {
            variables = { ...variables, pageToken }
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

        console.log(response, ' this is response in updateGoogleIntegration')
    } catch (e) {
        console.log(e, ' unable to update google integration')
    }
}

export const getCalendarWithId = async (
    calendarId: string,
) => {
    try {
        // get Calendar
        const operationName = 'getCalendar'
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
  `
        const variables = {
            id: calendarId,
        }

        const res: { data: { Calendar_by_pk: CalendarType } } = await got.post(
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

        console.log(res, ' res from getCalendarForEvent')
        return res?.data?.Calendar_by_pk


    } catch (e) {
        console.log(e, ' getCalendarForEvent')
    }
}

export const requestCalendarWatch = async (
    calendarId: string,
    channelId: string,
    token: string,
    userId: string,
) => {
    try {
        const { resource } = await getCalendarWithId(calendarId)
        const calendarIntegration = await getCalendarIntegration(userId, resource)
        const clientType = calendarIntegration?.clientType

        const authToken = await getGoogleAPIToken(userId, googleCalendarResource, clientType)

        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${authToken}`,
            },
        })

        const reqBody: CalendarWatchRequestResourceType = {
            id: channelId,
            token,
            type: 'webhook',
            address: selfGoogleCalendarWebhookPublicUrl,
        }

        const res = await googleCalendar.events.watch({
            calendarId,
            singleEvents: true,
            requestBody: reqBody,
        })

        const response = res?.data
        console.log(response, ' response inside requestCalendarWatch')
        return response
    } catch (e) {
        console.log(e, ' unable to request calendar watch')
    }
}

export const listCalendarsForUser = async (
    userId: string,
) => {
    try {
        const operationName = 'ListCalendarsForUser'
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
    `
        const variables = {
            userId,
        }

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
                    variables,
                },
            }).json()

        return res.data.Calendar
    } catch (e) {
        console.log(e, ' list calendars for user')
    }
}

export const insertRemindersGivenEventResource = async (
    events: EventResourceType[],
    userId: string,
    calendarId: string,
) => {
    try {
        if (!(events?.filter(e => !!(e?.id))?.length > 0)) {
            return
        }
        const reminders = []
        events
            .filter(e => ((e?.reminders?.useDefault) || (e?.reminders?.overrides?.[0]?.minutes > -1)))
            .forEach((event) => {

                const eventId = event?.id
                const timezone = event?.start?.timeZone
                console.log(eventId, calendarId, ' eventId, calendarId inside insertRemindersGivenEventResource')
                if (event?.reminders?.useDefault) {
                    reminders.push({
                        eventId: `${eventId}#${calendarId}`,
                        userId,
                        useDefault: event?.reminders?.useDefault,
                        timezone,
                    })
                } else {

                    event?.reminders?.overrides.forEach((o) => {
                        reminders.push({
                            eventId: `${eventId}#${calendarId}`,
                            userId,
                            timezone,
                            method: o?.method,
                            minutes: o?.minutes,
                            useDefault: false,
                        })
                    })
                }
            })

        console.log(reminders, ' reminders')
        if (!(reminders?.length > 0)) {
            return
        }

        const operationName = 'InsertReminder'
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
      `
        const variables = {
            reminders
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
        console.log(response, ' this is response in insertRemindersGivenResource')
    } catch (e) {
        console.log(e, ' unable to upsert reminder')
    }
}

export const getGoogleIntegration = async (
    calendarIntegrationId: string,
) => {
    try {
        const operationName = 'getCalendarIntegration'
        const query = `query getCalendarIntegration($id: uuid!){
      Calendar_Integration_by_pk(id: $id) {
        id
        name
        token
        refreshToken
        clientType
      }
    }`
        const variables = { id: calendarIntegrationId }

        const response: { data: { Calendar_Integration_by_pk: CalendarIntegrationType } } = await got.post(hasuraGraphUrl, {
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
        // just to check
        console.log(response, ' this is response in getGoogleIntegration')
        if (response?.data?.Calendar_Integration_by_pk) {
            const {
                data:
                {
                    Calendar_Integration_by_pk: {
                        token,
                        refreshToken,
                        clientType,
                    },
                },
            } = response

            return { token, refreshToken, clientType }
        }
    } catch (e) {
        console.log(e, ' unable to get google token')
    }
}

export const getGoogleColor = async (
    token: string,
) => {
    try {
        const config = {
            headers: {
                Authorization: `Bearer ${token}`
            }
        }
        const body: colorTypeResponse = await got.get(googleColorUrl, config).json()
        console.log(body, ' body inside getGoogleColor')
        return body
    } catch (e) {
        console.log(e, ' unable to get colors')
    }
}

export const getGoogleCalendarInDb = async (
    calendarId: string,
) => {
    try {
        const operationName = 'GetCalendarById'
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
    }`
        const variables = { id: calendarId }

        const response: { data: { Calendar_by_pk: CalendarType } } = await got.post(hasuraGraphUrl, {
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
        // just to check
        console.log(response, ' this is response in getGoogleCalendar')
        if (response?.data?.Calendar_by_pk) {
            const {
                data:
                {
                    Calendar_by_pk: {
                        pageToken,
                        syncToken,
                        id,
                    },
                },
            } = response

            return { pageToken, syncToken, id }
        }
    } catch (e) {
        console.log(e, ' unable to get google token')
    }
}



export const deleteAttendees = async (
    events: EventResourceType[],
    calendarId: string,
) => {
    try {
        const eventIds = events.map(e => `${e?.id}#${calendarId}`)

        if (!(eventIds?.filter(e => !!e)?.length > 0)) {
            return
        }

        const operationName = 'DeleteAttendees'
        const query = `
      mutation DeleteAttendees($eventIds: [String!]!) {
        delete_Attendee(where: {eventId: {_in: $eventIds}}) {
          affected_rows
        }
      }            
      `
        const variables = {
            eventIds,
        }

        const results = await got.post(hasuraGraphUrl, {
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
        console.log(results, ' successfully deleted attendees')
    } catch (e) {
        console.log(e, ' unable to delete attendees')
    }
}

export const refreshZoomToken = async (
    refreshToken: string,
):Promise<{
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

export const getZoomIntegration = async (
    userId: string,
) => {
    try {
        const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(userId, zoomResourceName)

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

export const deleteZoomMeeting = async (
    zoomToken: string,
    conferenceId: number,
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
                `${zoomBaseUrl}/meetings/` + conferenceId + '?' + stringifiedObject,
                {
                    headers: {
                        Authorization: `Bearer ${zoomToken}`,
                        ContentType: 'application/json',
                    }
                }
            )
        } else {
            await got.delete(
                `${zoomBaseUrl}/meetings/` + conferenceId,
                {
                    headers: {
                        Authorization: `Bearer ${zoomToken}`,
                        ContentType: 'application/json',
                    }
                }
            )
        }
        

        console.log(conferenceId, 'successfully deleted meeting')
    } catch (e) {
        console.log(e, ' unable to delete zoom meeting')
    }
}

export const listConferencesWithHosts = async (
    ids: string[]
) => {
    try {
        const operationName = 'ListConferencesWithHostId'
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
        `

        const variables = {
            ids,
        }

        const res: { data: { Conference: ConferenceType[] } } = await got.post(hasuraGraphUrl, {
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
    
        console.log(res, ' successfully listed conferences with hosts')

        return res?.data?.Conference
    } catch (e) {
        console.log(e, ' unable to list conferences with hosts')
    }
}

export const deleteConferencesInDb = async (
    conferenceIds: string[]
) => {
    try {
        const operationName = 'deleteConferences'
        const query = `
            mutation deleteConferences($ids: [String!]!) {
                delete_Conference(where: {id: {_in: $ids}}) {
                    affected_rows
                }
            }    
        `
        const variables = {
            ids: conferenceIds
        }
        const results = await got.post(hasuraGraphUrl, {
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

        console.log(results, ' successfully deleted multiple conferences')
    } catch (e) {
        console.log(e, ' unable to delete conferences in db')
    }
}

export const deleteConferences = async (
    events: {
                eventId: string,
                id: string,
                calendarId: string,
                meetingId: string,
                conferenceId?: string,
            }[],
) => {
    try {

        const conferenceIds = events?.map(e => (e?.conferenceId))

        const truthy = conferenceIds.filter(cId => !!cId)
        
        if (!(truthy?.[0])) {
            return
        }

        // delete zoom meetings if any

        const conferences = await listConferencesWithHosts(conferenceIds)

        for (const conference of conferences) {
            const zoomToken = await getZoomAPIToken(conference?.userId)

            if (zoomToken && (typeof parseInt(conference?.id, 10) === 'number')) {
                await deleteZoomMeeting(zoomToken, parseInt(conference?.id, 10))
            }
        }

        // delete in db
        await deleteConferencesInDb(conferenceIds)

    } catch (e) {
        console.log(e, ' unable to deleteConference')
    }
}

export const deleteEvents = async (
    events: EventResourceType[],
    calendarId: string,
) => {
    try {
        const eventIds = events.map(e => `${e?.id}#${calendarId}`)
        console.log(eventIds, ' eventIds inside deleteEvents')
        if (!(eventIds?.filter(e => !!e)?.length > 0)) {
            return
        }
        const operationName = 'deleteEvents'
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

        `
        const variables = {
            eventIds
        }

        const res: {
            data: {
                delete_Event: {
                    affected_rows: number,
                    returning: {
                        eventId: string,
                        id: string,
                        calendarId: string,
                        meetingId: string,
                        conferenceId?: string,
                    }[]
                }
            }
        } = await got.post(hasuraGraphUrl, {
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
        console.log(res, ' this is response in deleteEvents')
        return res?.data?.delete_Event?.returning
    } catch (e) {
        console.log(e, ' unable to delete events')
    }
}

export const deleteReminders = async (
    events: EventResourceType[],
    userId: string,
    calendarId: string,
) => {
    try {
        if (!(events?.filter(e => !!(e?.id))?.length > 0)) {
            return
        }
        const operationName = 'deleteReminders'
        const delEvents = events.map(e => (`${e?.id}#${calendarId}`))
        const query = `
      mutation deleteReminders($userId: uuid!, $eventIds: [String!]!) {
        delete_Reminder(where: {userId: {_eq: $userId}, eventId: {_in: $eventIds}}) {
          affected_rows
        }
      }    
    `

        const variables = {
            userId,
            eventIds: delEvents
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
        console.log(response, ' this is response in deleteReminders')
    } catch (e) {
        console.log(e, ' unable to delete reminders')
    }
}

export const getUserPreferences = async (userId: string): Promise<UserPreferenceType> => {
    try {
        if (!userId) {
            console.log('userId is null')
            return null
        }
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
        return res?.data?.User_Preference?.[0]
    } catch (e) {
        console.log(e, ' getUserPreferences')
    }
}

export const convertToTotalWorkingHours = (
    userPreference: UserPreferenceType,
    startDate: string,
    timezone: string,
) => {
    const startTimes = userPreference.startTimes
    const endTimes = userPreference.endTimes
    const dayOfWeekInt = getISODay(dayjs(startDate.slice(0, 19)).tz(timezone, true).toDate())
    const startHour = startTimes.find(i => (i.day === dayOfWeekInt)).hour
    const startMinute = startTimes.find(i => (i.day === dayOfWeekInt)).minutes
    const endHour = endTimes.find(i => (i.day === dayOfWeekInt)).hour
    const endMinute = endTimes.find(i => (i.day === dayOfWeekInt)).minutes

    const startDuration = dayjs.duration({ hours: startHour, minutes: startMinute })
    const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute })
    const totalDuration = endDuration.subtract(startDuration)
    return totalDuration.asHours()
}

export const listEventsWithIds = async (ids: string[]) => {
    try {
        const operationName = 'listEventsWithIds'

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
    `

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
                        ids,
                    },
                },
            },
        ).json()

        return res?.data?.Event
    } catch (e) {
        console.log(e, ' unable to list ids with ids')
    }
}

export const listEventsForDate = async (
    userId: string,
    startDate: string,
    endDate: string,
    timezone: string,
) => {
    try {
        const operationName = 'listEventsForDate'
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
            `
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
                        startDate: dayjs(startDate.slice(0, 19)).tz(timezone, true).format(),
                        endDate: dayjs(endDate).tz(timezone, true).format(),
                    },
                },
            },
        ).json()

        console.log(res, ' res from listEventsforUser')
        return res?.data?.Event

    } catch (e) {
        console.log(e, ' unable to list events for date')
    }
}

export const shouldGenerateBreakEventsForDay = (
    workingHours: number,
    userPreferences: UserPreferenceType,
    allEvents: EventPlusType[],
) => {
    // validate
    if (!userPreferences?.breakLength) {
        console.log('no user preferences breakLength provided inside shouldGenerateBreakEvents')
        return false
    }

    if (!(allEvents?.length > 0)) {
        console.log('no allEvents present inside shouldGenerateBreakEventsForDay')
        return false
    }

    const breakEvents = allEvents.filter((event) => event.isBreak)
    const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks

    const breakHoursAvailable = (userPreferences.breakLength / 60) * numberOfBreaksPerDay
    let breakHoursUsed = 0
    for (const breakEvent of breakEvents) {
        const duration = dayjs.duration(dayjs(dayjs(breakEvent.endDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')).diff(dayjs(breakEvent.startDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss'))).asHours()
        breakHoursUsed += duration
    }

    if (breakHoursUsed >= breakHoursAvailable) {
        console.log('breakHoursUsed >= breakHoursAvailable')
        return false
    }

    if (!(allEvents?.length > 0)) {
        console.log('there are no events for this date inside shouldGenerateBreakEvents')
        return false
    }
    let hoursUsed = 0
    for (const event of allEvents) {
        const duration = dayjs.duration(dayjs(dayjs(event.endDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss')).diff(dayjs(event.startDate.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss'))).asHours()
        hoursUsed += duration
    }

    if (hoursUsed >= workingHours) {
        console.log('hoursUsed >= workingHours')
        return false
    }

    return true
}

export const generateBreaks = (
    userPreferences: UserPreferenceType,
    numberOfBreaksToGenerate: number,
    eventMirror: EventPlusType,
    globalCalendarId?: string,
): EventPlusType[] => {
    const breaks = []
    // validate
    if (!userPreferences?.breakLength) {
        console.log('no user preferences breakLength provided inside generateBreaks')
        return breaks
    }

    if (!numberOfBreaksToGenerate) {
        console.log('no number of breaks to generate provided inside generateBreaks')
        return breaks
    }

    if (!eventMirror) {
        console.log('no event mirror provided inside generateBreaks')
        return breaks
    }
    console.log(numberOfBreaksToGenerate, ' numberOfBreaksToGenerate inside generateBreaks')
    for (let i = 0; i < numberOfBreaksToGenerate; i++) {
        const eventId = uuid()
        const breakEvent: EventPlusType = {
            id: `${eventId}#${globalCalendarId || eventMirror.calendarId}}`,
            userId: userPreferences.userId,
            title: 'Break',
            startDate: dayjs(eventMirror.startDate.slice(0, 19)).tz(eventMirror.timezone, true).format(),
            endDate: dayjs(eventMirror.startDate.slice(0, 19)).tz(eventMirror.timezone, true).add(userPreferences.breakLength, 'minute').format(),
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
        }
        breaks.push(breakEvent)
    }

    return breaks
}

export const generateBreakEventsForDay = async (
    userPreferences: UserPreferenceType,
    userId: string,
    startDate: string,
    timezone: string,
    eventsToBeBreaks: EventPlusType[] = [],
    globalCalendarId?: string,
    isFirstDay?: boolean,
) => {
    try {
        // validate
        if (!userPreferences?.breakLength) {
            console.log('no user preferences breakLength provided inside shouldGenerateBreakEvents')
            return null
        }

        if (!userId) {
            console.log('no userId provided inside shouldGenerateBreakEvents')
            return null
        }

        if (!startDate) {
            console.log('no startDate provided inside shouldGenerateBreakEvents')
            return null
        }

        if (!timezone) {
            console.log('no timezone provided inside shouldGenerateBreakEvents')
            return null
        }

        if (isFirstDay) {
            const endTimes = userPreferences.endTimes
            const dayOfWeekInt = getISODay(dayjs(startDate.slice(0, 19)).tz(timezone, true).toDate())

            let startHour = dayjs(startDate.slice(0, 19)).tz(timezone, true).hour()
            let startMinute = dayjs(startDate.slice(0, 19)).tz(timezone, true).minute()
            const endHour = endTimes.find(i => (i.day === dayOfWeekInt)).hour
            const endMinute = endTimes.find(i => (i.day === dayOfWeekInt)).minutes

            // validate values before calculating
            const startTimes = userPreferences.startTimes
            const workStartHour = startTimes.find(i => (i.day === dayOfWeekInt)).hour
            const workStartMinute = startTimes.find(i => (i.day === dayOfWeekInt)).minutes

            if (dayjs(startDate.slice(0, 19)).isAfter(dayjs(startDate.slice(0, 19)).hour(endHour).minute(endMinute))) {
                // return empty as outside of work time
                return null
            }

            // change to work start time as before start time
            if (dayjs(startDate.slice(0, 19)).isBefore(dayjs(startDate.slice(0, 19)).hour(workStartHour).minute(workStartMinute))) {
                startHour = workStartHour
                startMinute = workStartMinute
            }

            const workingHours = convertToTotalWorkingHours(userPreferences, startDate, timezone)
            const allEvents = await listEventsForDate(userId, dayjs(startDate.slice(0, 19)).tz(timezone, true).hour(startHour).minute(startMinute).format(), dayjs(startDate.slice(0, 19)).tz(timezone, true).hour(endHour).minute(endMinute).format(), timezone)
            if (!(allEvents?.length > 0)) {
                console.log('no allEvents present inside shouldGenerateBreakEventsForDay')
                return null
            }
            const shouldGenerateBreaks = shouldGenerateBreakEventsForDay(workingHours, userPreferences, allEvents)
            // validate
            if (!shouldGenerateBreaks) {
                console.log('should not generate breaks')
                return null
            }

            let hoursUsed = 0

            if (allEvents?.length > 0) {
                for (const allEvent of allEvents) {
                    const duration = dayjs.duration(dayjs(allEvent.endDate.slice(0, 19)).tz(timezone, true).diff(dayjs(allEvent.startDate.slice(0, 19)).tz(timezone, true))).asHours()
                    hoursUsed += duration
                }
            }

            let hoursAvailable = workingHours - hoursUsed
            hoursAvailable -= (workingHours * userPreferences.maxWorkLoadPercent)
            // no hours available
            if (hoursAvailable <= 0) {
                console.log(hoursAvailable, ' no hours available')
                return null
            }

            const oldBreakEvents = allEvents.filter((event) => event.isBreak)
                .filter(e => (dayjs(startDate.slice(0, 19)).tz(timezone, true).isSame(dayjs(e.startDate.slice(0, 19)).tz(timezone, true), 'day')))

            const breakEvents = eventsToBeBreaks.concat(oldBreakEvents)

            const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks
            console.log(numberOfBreaksPerDay, ' numberOfBreaksPerDay')
            const breakHoursToGenerate = (userPreferences.breakLength / 60) * numberOfBreaksPerDay
            let breakHoursUsed = 0

            if (breakEvents?.length > 0) {
                for (const breakEvent of breakEvents) {
                    const duration = dayjs.duration(dayjs(breakEvent.endDate.slice(0, 19)).tz(timezone, true).diff(dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true))).asHours()
                    breakHoursUsed += duration
                }
            }

            const actualBreakHoursToGenerate = breakHoursToGenerate - breakHoursUsed

            if (actualBreakHoursToGenerate > hoursAvailable) {
                console.log(' no hours available to generate break')
                return null
            }

            console.log(breakHoursUsed, ' breakHoursUsed')
            console.log(breakHoursToGenerate, ' breakHoursAvailable')
            const breakLengthAsHours = userPreferences.breakLength / 60
            console.log(breakLengthAsHours, ' breakLengthAsHours')
            const numberOfBreaksToGenerate = Math.floor(actualBreakHoursToGenerate / breakLengthAsHours)
            console.log(numberOfBreaksToGenerate, ' numberOfBreaksToGenerate')

            if (numberOfBreaksToGenerate < 1) {
                console.log('should not generate breaks')
                return null
            }

            const eventMirror = allEvents.find((event) => !event.isBreak)

            const newEvents = generateBreaks(
                userPreferences,
                numberOfBreaksToGenerate,
                eventMirror,
                globalCalendarId,
            )

            return newEvents

        }

        const endTimes = userPreferences.endTimes
        const dayOfWeekInt = getISODay(dayjs(startDate.slice(0, 19)).tz(timezone, true).toDate())

        const endHour = endTimes.find(i => (i.day === dayOfWeekInt)).hour
        const endMinute = endTimes.find(i => (i.day === dayOfWeekInt)).minutes

        // validate values before calculating
        const startTimes = userPreferences.startTimes
        const startHour = startTimes.find(i => (i.day === dayOfWeekInt)).hour
        const startMinute = startTimes.find(i => (i.day === dayOfWeekInt)).minutes

        const workingHours = convertToTotalWorkingHours(userPreferences, startDate, timezone)
        const allEvents = await listEventsForDate(userId, dayjs(startDate.slice(0, 19)).tz(timezone, true).hour(startHour).minute(startMinute).format(), dayjs(startDate.slice(0, 19)).tz(timezone, true).hour(endHour).minute(endMinute).format(), timezone)
        if (!(allEvents?.length > 0)) {
            console.log('no allEvents present inside shouldGenerateBreakEventsForDay')
            return null
        }
        const shouldGenerateBreaks = shouldGenerateBreakEventsForDay(workingHours, userPreferences, allEvents)
        // validate
        if (!shouldGenerateBreaks) {
            console.log('should not generate breaks')
            return null
        }

        let hoursUsed = 0

        if (allEvents?.length > 0) {
            for (const allEvent of allEvents) {
                const duration = dayjs.duration(dayjs(allEvent.endDate.slice(0, 19)).tz(timezone, true).diff(dayjs(allEvent.startDate.slice(0, 19)).tz(timezone, true))).asHours()
                hoursUsed += duration
            }
        }

        let hoursAvailable = workingHours - hoursUsed
        hoursAvailable -= (workingHours * userPreferences.maxWorkLoadPercent)

        // no hours available
        if (hoursAvailable <= 0) {
            console.log(hoursAvailable, ' no hours available')
            return null
        }

        const oldBreakEvents = allEvents.filter((event) => event.isBreak)
            .filter(e => (dayjs(startDate.slice(0, 19)).tz(timezone, true).isSame(dayjs(e.startDate.slice(0, 19)).tz(timezone, true), 'day')))

        const breakEvents = eventsToBeBreaks.concat(oldBreakEvents)

        const numberOfBreaksPerDay = userPreferences.minNumberOfBreaks
        console.log(numberOfBreaksPerDay, ' numberOfBreaksPerDay')
        const breakHoursToGenerate = (userPreferences.breakLength / 60) * numberOfBreaksPerDay
        let breakHoursUsed = 0

        if (breakEvents?.length > 0) {
            for (const breakEvent of breakEvents) {
                const duration = dayjs.duration(dayjs(breakEvent.endDate.slice(0, 19)).tz(timezone, true).diff(dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true))).asHours()
                breakHoursUsed += duration
            }
        }

        const actualBreakHoursToGenerate = breakHoursToGenerate - breakHoursUsed

        if (actualBreakHoursToGenerate > hoursAvailable) {
            console.log(' no hours available to generate break')
            return null
        }

        console.log(breakHoursUsed, ' breakHoursUsed')
        console.log(breakHoursToGenerate, ' breakHoursAvailable')
        const breakLengthAsHours = userPreferences.breakLength / 60
        console.log(breakLengthAsHours, ' breakLengthAsHours')
        const numberOfBreaksToGenerate = Math.floor(actualBreakHoursToGenerate / breakLengthAsHours)
        console.log(numberOfBreaksToGenerate, ' numberOfBreaksToGenerate')

        if (numberOfBreaksToGenerate < 1) {
            console.log('should not generate breaks')
            return null
        }

        const eventMirror = allEvents.find((event) => !event.isBreak)

        const newEvents = generateBreaks(
            userPreferences,
            numberOfBreaksToGenerate,
            eventMirror,
            globalCalendarId,
        )

        return newEvents

    } catch (e) {
        console.log(e, ' unable to generate breaks for day')
    }
}

export const adjustStartDatesForBreakEventsForDay = (
    allEvents: EventPlusType[],
    breakEvents: EventPlusType[],
    userPreference: UserPreferenceType,
    timezone: string,
): EventPlusType[] => {
    // validate 
    if (!allEvents?.[0]?.id) {
        console.log('no allEvents inside adjustStartDatesForBreakEvents')
        return
    }


    const startTimes = userPreference.startTimes
    const endTimes = userPreference.endTimes
    const dayOfWeekInt = getISODay(dayjs(allEvents?.[0]?.startDate.slice(0, 19)).tz(timezone, true).toDate())
    const startHour = startTimes.find(i => (i.day === dayOfWeekInt)).hour
    const startMinute = startTimes.find(i => (i.day === dayOfWeekInt)).minutes
    const endHour = endTimes.find(i => (i.day === dayOfWeekInt)).hour
    const endMinute = endTimes.find(i => (i.day === dayOfWeekInt)).minutes
    const newBreakEvents = []
    /**
     * const startDuration = dayjs.duration({ hours: startHour, minutes: startMinute })
      const endDuration = dayjs.duration({ hours: endHour, minutes: endMinute })
      const totalDuration = endDuration.subtract(startDuration)
      return totalDuration.asHours()
     */

    const startOfWorkingDay = dayjs(allEvents[0]?.startDate.slice(0, 19)).tz(timezone, true)
        .hour(startHour).minute(startMinute)

    const endOfWorkingDay = dayjs(allEvents[0]?.endDate.slice(0, 19)).tz(timezone, true)
        .hour(endHour).minute(endMinute)

    const filteredEvents = allEvents.filter(e => (!e.isBreak))
    if (breakEvents?.length > 0) {
        for (const breakEvent of breakEvents) {
            let foundSpace = false
            let index = 0
            while ((!foundSpace) && (index < filteredEvents.length)) {
                const possibleEndDate = dayjs(filteredEvents[index].startDate.slice(0, 19)).tz(timezone, true)

                const possibleStartDate = dayjs(possibleEndDate.format().slice(0, 19)).tz(timezone, true).subtract(userPreference.breakLength, 'minute')
                let isBetweenStart = true
                let isBetweenEnd = true
                let betweenIndex = 0
                let betweenWorkingDayStart = true
                let betweenWorkingDayEnd = true
                let isBetweenBreakStart = true
                let isBetweenBreakEnd = true

                while ((isBetweenStart || isBetweenEnd || !betweenWorkingDayStart || !betweenWorkingDayEnd || isBetweenBreakStart || isBetweenBreakEnd) && (betweenIndex < filteredEvents.length)) {
                    isBetweenStart = possibleStartDate.isBetween(dayjs(filteredEvents[betweenIndex].startDate.slice(0, 19)).tz(timezone, true), dayjs(filteredEvents[betweenIndex].endDate.slice(0, 19)).tz(timezone, true), 'minute', '[)')

                    isBetweenEnd = possibleEndDate.isBetween(dayjs(filteredEvents[betweenIndex].startDate.slice(0, 19)).tz(timezone, true), dayjs(filteredEvents[betweenIndex].endDate.slice(0, 19)).tz(timezone, true), 'minute', '(]')

                    betweenWorkingDayStart = possibleStartDate.isBetween(startOfWorkingDay, endOfWorkingDay, 'minute', '[)')

                    betweenWorkingDayEnd = possibleEndDate.isBetween(startOfWorkingDay, endOfWorkingDay, 'minute', '(]')

                    for (const breakEvent of breakEvents) {
                        isBetweenBreakStart = possibleStartDate.isBetween(dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true), dayjs(breakEvent.endDate.slice(0, 19)).tz(timezone, true), 'minute', '[)')

                        isBetweenBreakEnd = possibleEndDate.isBetween(dayjs(breakEvent.startDate.slice(0, 19)).tz(timezone, true), dayjs(breakEvent.endDate.slice(0, 19)).tz(timezone, true), 'minute', '(]')
                    }

                    betweenIndex++
                }

                foundSpace = (!isBetweenStart && !isBetweenEnd && betweenWorkingDayStart && betweenWorkingDayEnd && !isBetweenBreakStart && !isBetweenBreakEnd)

                if (foundSpace) {
                    const newBreakEvent = {
                        ...breakEvent,
                        startDate: possibleStartDate.toISOString(),
                        endDate: possibleEndDate.toISOString(),
                    }
                    newBreakEvents.push(newBreakEvent)
                }

                index++
            }
        }
    }

    return newBreakEvents
}

export const generateBreakEventsForDate = async (
    userPreferences: UserPreferenceType,
    userId: string,
    startDate: string,
    endDate: string,
    timezone: string,
    eventsToBeBreaks: EventPlusType[] = [],
    globalCalendarId?: string,
): Promise<EventPlusType[] | []> => {
    try {
        const totalBreakEvents = []
        const totalDays = dayjs(endDate.slice(0, 19)).tz(timezone, true).diff(dayjs(startDate.slice(0, 19)).tz(timezone, true), 'day')
        console.log(totalDays, ' totalDays inside generateBreakEventsForDate')
        for (let i = 0; i < totalDays; i++) {
            const dayDate = dayjs(startDate.slice(0, 19)).tz(timezone, true)
                .add(i, 'day').format()
            const eventsToBeBreaksForDay = eventsToBeBreaks.filter(e => dayjs(e.startDate.slice(0, 19)).tz(e.timezone, true).isSame(dayDate, 'day'))
            const newBreakEvents = await generateBreakEventsForDay(userPreferences, userId, dayDate, timezone, eventsToBeBreaksForDay, globalCalendarId, i === 0)

            if (i === 0) {
                const endTimes = userPreferences.endTimes
                const dayOfWeekInt = getISODay(dayjs(dayDate.slice(0, 19)).tz(timezone, true).toDate())

                let startHour = dayjs(dayDate.slice(0, 19)).tz(timezone, true).hour()
                let startMinute = dayjs(dayDate.slice(0, 19)).tz(timezone, true).minute()
                const endHour = endTimes.find(i => (i.day === dayOfWeekInt)).hour
                const endMinute = endTimes.find(i => (i.day === dayOfWeekInt)).minutes

                // validate values before calculating
                const startTimes = userPreferences.startTimes
                const workStartHour = startTimes.find(i => (i.day === dayOfWeekInt)).hour
                const workStartMinute = startTimes.find(i => (i.day === dayOfWeekInt)).minutes

                if (dayjs(dayDate.slice(0, 19)).isAfter(dayjs(dayDate.slice(0, 19)).hour(endHour).minute(endMinute))) {
                    // return empty as outside of work time
                    continue
                }

                // change to work start time as before start time
                if (dayjs(dayDate.slice(0, 19)).isBefore(dayjs(dayDate.slice(0, 19)).hour(workStartHour).minute(workStartMinute))) {
                    startHour = workStartHour
                    startMinute = workStartMinute
                }

                const allEvents = await listEventsForDate(userId, dayjs(dayDate.slice(0, 19)).tz(timezone, true).hour(startHour).minute(startMinute).format(), dayjs(dayDate.slice(0, 19)).tz(timezone, true).hour(endHour).minute(endMinute).format(), timezone)
                const newBreakEventsAdjusted = await adjustStartDatesForBreakEventsForDay(allEvents,
                    newBreakEvents, userPreferences, timezone)
                if (newBreakEventsAdjusted?.length > 0) {
                    newBreakEventsAdjusted.forEach(b => console.log(b, ' newBreakEventsAdjusted'))
                    totalBreakEvents.push(...newBreakEventsAdjusted)
                }

                continue
            }

            const endTimes = userPreferences.endTimes
            const dayOfWeekInt = getISODay(dayjs(dayDate.slice(0, 19)).tz(timezone, true).toDate())

            const endHour = endTimes.find(i => (i.day === dayOfWeekInt)).hour
            const endMinute = endTimes.find(i => (i.day === dayOfWeekInt)).minutes

            // validate values before calculating
            const startTimes = userPreferences.startTimes
            const startHour = startTimes.find(i => (i.day === dayOfWeekInt)).hour
            const startMinute = startTimes.find(i => (i.day === dayOfWeekInt)).minutes

            const allEvents = await listEventsForDate(userId, dayjs(dayDate.slice(0, 19)).tz(timezone, true).hour(startHour).minute(startMinute).format(), dayjs(dayDate.slice(0, 19)).tz(timezone, true).hour(endHour).minute(endMinute).format(), timezone)
            const newBreakEventsAdjusted = await adjustStartDatesForBreakEventsForDay(allEvents,
                newBreakEvents, userPreferences, timezone)
            if (newBreakEventsAdjusted?.length > 0) {
                newBreakEventsAdjusted.forEach(b => console.log(b, ' newBreakEventsAdjusted'))
                totalBreakEvents.push(...newBreakEventsAdjusted)
            }
        }

        return totalBreakEvents
    } catch (e) {
        console.log(e, ' unable to generateBreakEventsForDate')
    }
}

export const upsertEventsPostPlanner = async (
    events: EventType[]
) => {
    try {
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

export const formatRemindersForGoogle = (reminders: ReminderType[]): GoogleReminderType => {
    const googleOverrides: OverrideTypes = reminders.map(reminder => {
        return {
            method: 'email',
            minutes: reminder.minutes,
        }
    })
    const googleReminders: GoogleReminderType = {
        overrides: googleOverrides,
        useDefault: false,
    }
    return googleReminders
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

export const getCalendarIntegration = async (
    userId: string,
    resource: string,
) => {
    try {
        const operationName = 'getCalendarIntegration'
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

export const getGoogleAPIToken = async (
    userId: string,
    resource: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    let integrationId = ''
    try {
        const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(userId, resource)
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
        const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType)
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
                timeZone: timezone,
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
                timeZone: timezone
            }
            requestBody.end = end

            console.log(eventId, end.dateTime, end.timeZone, ' eventId, endDateTime, timeZone after')
        }

        if (startDate && timezone && !startDateTime) {
            const start = {
                date: dayjs(startDateTime.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'),
                timeZone: timezone,
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
                timeZone: timezone,
            }
            requestBody.start = start

            console.log(eventId, start.dateTime, start.timeZone, ' eventId, startDateTime, timeZone after')
        }

        if (originalStartDate && timezone && !originalStartDateTime) {
            const originalStartTime = {
                date: dayjs(originalStartDate.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DD'),
                timeZone: timezone,
            }
            requestBody.originalStartTime = originalStartTime
        }

        if (originalStartDateTime && timezone && !originalStartDate) {
            const originalStartTime = {
                dateTime: originalStartDateTime,
                timeZone: timezone,
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
) => {
    try {
        // get token =
        const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType)

        const googleCalendar = google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        })

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
        if (
            maxAttendees
            || sendUpdates
            || (conferenceDataVersion > 0)
        ) {
            // url = `${url}?`
            let params: any = {}

            if (maxAttendees) {
                params = { ...params, maxAttendees }
            }

            if (sendUpdates) {
                params = { ...params, sendUpdates }
            }

            if (conferenceDataVersion > 0) {
                params = { ...params, conferenceDataVersion }
            }

            if (
                params?.maxAttendees
                || params?.sendUpdates
                || (params?.conferenceDataVersion > -1)
            ) {
                // url = `${url}${qs.stringify(params)}`
            }
        }


        // create request body
        let data: any = {}

        if (endDateTime && timezone && !endDate) {
            // BUG: calling dayjs here offsets endDateTime value
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
                date: originalStartDate,
                timeZone: timezone,
            }
            data.originalStartTime = originalStartTime
        }

        if (originalStartDateTime && timezone && !originalStartDate) {
            const originalStartTime = {
                dateTime: dayjs(originalStartDateTime).tz(timezone, true).format(),
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

        if (reminders) {
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
        })

        console.log(res.data)

        console.log(res?.data, ' res?.data from googleCreateEvent')
        return { id: res?.data?.id, generatedId }
    } catch (e) {
        console.log(e, ' createGoogleEvent')
    }
}

export const postPlannerModifyEventInCalendar = async (
    newEvent: EventPlusType,
    userId: string,
    method: 'update' | 'create',
    resource: string, isTimeBlocking: boolean,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
    newReminders?: ReminderType[],
    attendees?: MeetingAssistAttendeeType[],
    conference?: ConferenceType,
): Promise<string | { id: string, generatedId: string }> => {
    try {
        console.log(newEvent, ' newEvent inside postPlannerModifyEventInCalendar')
        if (method === 'update') {
            // update event

            if (resource === googleCalendarResource) {
                const googleReminders: GoogleReminderType = newReminders?.length > 0 ? formatRemindersForGoogle(newReminders) : undefined

                // update event
                await patchGoogleEvent(
                    userId,
                    newEvent.calendarId,
                    newEvent.eventId,
                    clientType,
                    newEvent.endDate,
                    newEvent.startDate,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    newEvent.timezone,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    googleReminders,
                    undefined,
                    undefined,
                    newEvent.transparency,
                    newEvent?.visibility,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    newEvent?.colorId,
                )
                return newEvent.id
            }
            // else if (resource === outlookCalendarResource) {
            //   // await updateOutlookEvent(newEvent)
            // }
        } else if (method === 'create') {
            console.log(newEvent, ' newEvent inside create inside postPlannerModifyEventInCalendar')
            // create task events only
            if (resource === googleCalendarResource) {
                const googleReminders: GoogleReminderType = newReminders?.length > 0 ? formatRemindersForGoogle(newReminders) : undefined

                const idAndGenIdObject = await createGoogleEvent(
                    userId,
                    newEvent.calendarId,
                    clientType,
                    newEvent?.eventId, // generatedId
                    newEvent?.endDate,
                    newEvent?.startDate,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    attendees?.map(a => ({ email: a?.primaryEmail, id: a?.id, displayName: a?.name })),
                    conference?.id ? {
                        type: conference?.app === 'zoom' ? 'addOn' : 'hangoutsMeet',
                        name: conference?.name,
                        conferenceId: conference?.id,
                        entryPoints: conference?.entryPoints,
                        createRequest: conference?.app === 'google' ? {
                            requestId: conference?.requestId,
                            conferenceSolutionKey: {
                                type: 'hangoutsMeet',
                            }
                        } : undefined,
                    } : undefined,
                    newEvent.summary || newEvent?.title,
                    newEvent.notes,
                    newEvent.timezone,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    newEvent?.recurrence,
                    googleReminders,
                    undefined,
                    undefined,
                    newEvent.transparency,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    undefined,
                    isTimeBlocking ? 'focusTime' : 'default',
                    undefined,
                    newEvent?.colorId,
                )
                console.log(idAndGenIdObject, newEvent?.endDate,
                    newEvent?.startDate, ' idAndGenIdObject, newEvent?.endDate,  newEvent?.startDate')
                return idAndGenIdObject
            }
        }
    } catch (e) {
        console.log(e, ' unable to update event')
        console.log(newEvent?.id, newEvent?.endDate,
            newEvent?.startDate, ' error - newEvent?.id, newEvent?.endDate,  newEvent?.startDate')
    }
}

export const generateBreakEventsForCalendarSync = async (
    userId: string,
    timezone: string,
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
) => {
    try {
        // validate
        if (!userId) {
            console.log('no userId inside generateBreakEventsForCalendarSync')
            return
        }

        if (!timezone) {
            console.log('no timezone inside generateBreakEventsForCalendarSync')
            return
        }

        if (!clientType) {
            console.log('no clientType inside generateBreakEventsForCalendarSync')
            return
        }
        const userPreferences = await getUserPreferences(userId)

        const breakEvents = await generateBreakEventsForDate(userPreferences, userId, dayjs().tz(timezone, true).format(), dayjs().tz(timezone, true).add(7, 'd').format(), timezone)

        const results = await Promise.all(breakEvents.map(b => postPlannerModifyEventInCalendar(b, userId, 'create', googleCalendarResource, false, clientType))) as {
            id: string;
            generatedId: string;
        }[]

        console.log(results, ' results form modifying postPlannerModifyEventInCalendar inside generateBreakEventsForCalendarSync')
        if (!(breakEvents?.length > 0)) {
            console.log('no breakEvents to upsert')
            return
        }
        const eventsToUpsert = []
        for (const result of results) {
            const foundEvent = (breakEvents as EventPlusType[])?.find(e => (e?.eventId === result?.generatedId))
            if (foundEvent?.id) {
                foundEvent.id = `${result?.id}#${foundEvent?.calendarId}`
                foundEvent.eventId = result?.id
                eventsToUpsert.push(foundEvent)
            }
        }
        await upsertEventsPostPlanner(eventsToUpsert)
    } catch (e) {
        console.log(e, ' unable to generatezbreakEventsForCalendarSync')
    }
}

// Define GoogleEventPatchAttributes interface
interface GoogleEventPatchAttributes {
  summary?: string;
  description?: string;
  location?: string;
  status?: 'confirmed' | 'tentative' | 'cancelled';
  transparency?: 'opaque' | 'transparent';
  visibility?: 'default' | 'public' | 'private' | 'confidential';
  colorId?: string;
  conferenceData?: Record<string, any> | null;
}

export async function directUpdateGoogleEventAndHasura(
    userId: string,
    calendarId: string,
    eventId: string, // This is Google's event ID
    clientType: 'ios' | 'android' | 'web' | 'atomic-web',
    updates: Partial<GoogleEventPatchAttributes>
): Promise<boolean> {
    if (!eventId || Object.keys(updates).length === 0) {
        console.log('Missing eventId or empty updates object.');
        return false;
    }

    try {
        // 1. Prepare Google Calendar API patch request
        const patchRequestBody: Partial<GoogleEventPatchAttributes> = { ...updates };

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
        } catch (googleError) {
            console.error(`Error patching Google event ${eventId}:`, googleError.response?.data || googleError.message);
            return false;
        }

        // 5. Prepare Hasura Update Payload
        const hasuraEventId = `${eventId}#${calendarId}`;
        const hasuraUpdatePayload: any = {
            updatedAt: new Date().toISOString(),
        };

        if (updates.summary !== undefined) hasuraUpdatePayload.summary = updates.summary;
        if (updates.description !== undefined) hasuraUpdatePayload.notes = updates.description; // Map description to notes
        if (updates.location !== undefined) {
            // Assuming Event.location in Hasura is a simple text field for direct updates.
            // If it's a JSONB type expecting { title: string }, then:
            // hasuraUpdatePayload.location = { title: updates.location };
            hasuraUpdatePayload.location = updates.location;
        }
        if (updates.status !== undefined) hasuraUpdatePayload.status = updates.status;
        if (updates.transparency !== undefined) hasuraUpdatePayload.transparency = updates.transparency;
        if (updates.visibility !== undefined) hasuraUpdatePayload.visibility = updates.visibility;
        if (updates.colorId !== undefined) hasuraUpdatePayload.colorId = updates.colorId;

        // Handle conferenceData
        if (updates.conferenceData === null) {
            hasuraUpdatePayload.hangoutLink = null;
            hasuraUpdatePayload.conferenceId = null;
            // Potentially clear other conference related fields in Hasura if they exist
        } else if (updates.conferenceData) {
            // Attempt to extract hangoutLink and conferenceId
            // This is a simplified extraction. Google's conferenceData can be complex.
            if (updates.conferenceData.entryPoints && Array.isArray(updates.conferenceData.entryPoints)) {
                const videoEntryPoint = updates.conferenceData.entryPoints.find(ep => ep.entryPointType === 'video');
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
        Object.keys(hasuraUpdatePayload).forEach(key => {
            if (hasuraUpdatePayload[key] === undefined) {
                delete hasuraUpdatePayload[key];
            }
        });

        if (Object.keys(hasuraUpdatePayload).length === 1 && hasuraUpdatePayload.updatedAt) {
            console.log("No mappable fields to update in Hasura besides updatedAt.");
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

        const hasuraResponse: any = await got.post(hasuraGraphUrl, {
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
        }).json();

        if (hasuraResponse.errors) {
            console.error(`Error updating Hasura event ${hasuraEventId}:`, JSON.stringify(hasuraResponse.errors, null, 2));
            // Google update was successful, but Hasura failed.
            // May need a reconciliation strategy or specific error handling.
            return false; // Indicate partial failure
        }

        console.log(`Hasura event ${hasuraEventId} updated successfully.`);
        return true;

    } catch (error) {
        console.error('An unexpected error occurred in directUpdateGoogleEventAndHasura:', error);
        return false;
    }
}


export async function streamToString(stream: Readable): Promise<string> {
    return await new Promise((resolve, reject) => {
        const chunks: Uint8Array[] = [];
        stream.on('data', (chunk) => chunks.push(chunk));
        stream.on('error', reject);
        stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
    });
}

export const addToQueueForVectorSearch = async (
    userId: string,
    events: EventObjectForVectorType[],
) => {
    const producer = kafka.producer({ maxInFlightRequests: 1, idempotent: true })
    await producer.connect()

    const  transaction = await producer.transaction()

    try {
        // process.env.EVENT_TO_VECTOR_QUEUE_URL
        const singletonId = uuid()
        const params = {
            Body: JSON.stringify({
                events,
                userId,
            }),
            Bucket: bucketName,
            Key: `${userId}/${singletonId}.json`,
            ContentType: 'application/json',
          }

        const s3Command = new PutObjectCommand(params)

        const s3Response = await s3Client.send(s3Command)

        console.log(s3Response, ' s3Response')
        
        const response = await transaction.send({
            topic: kafkaGoogleCalendarSyncTopic,
            messages: [{ value: JSON.stringify({ fileKey: `${userId}/${singletonId}.json` })}]
        })

        const admin = kafka.admin()

        await admin.connect()
        const partitions = await admin.fetchOffsets({ groupId: kafkaGoogleCalendarSyncGroupId, topics: [kafkaGoogleCalendarSyncTopic] })
        console.log(partitions)
        await admin.disconnect()

        await transaction.sendOffsets({
            consumerGroupId: kafkaGoogleCalendarSyncGroupId, topics: [{ topic: kafkaGoogleCalendarSyncTopic, partitions: partitions?.[0]?.partitions}]
        })

        await transaction.commit()

        console.log(response, ' response successfully added to queue inside addToQueueForVectorSearch')
    } catch (e) {
        console.log(e, ' unable to add to queue')
        await transaction.abort()
    }
}
