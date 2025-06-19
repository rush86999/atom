import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone';
import { google } from 'googleapis'
import { v4 as uuidv4 } from 'uuid'

import {
    deleteAttendees,
    deleteConferences,
    deleteEvents,
    deleteReminders,
    getGoogleAPIToken,
    getGoogleCalendarInDb,
    getGoogleColor,
    getGoogleIntegration,
    insertRemindersGivenEventResource,
    requestCalendarWatch,
    updateGoogleCalendarTokensInDb,
    updateGoogleIntegration,
    upsertAttendees2,
    insertCalendarWebhook,
    upsertConference2,
    upsertEvents2,
    getCalendarWebhookByCalendarId,
    stopCalendarWatch,
    deleteCalendarWebhookById,
    addToQueueForVectorSearch,
    addlocalItemsToEvent2VectorObjects,
    resetGoogleSyncForCalendar // Added for 410 GONE error handling
} from './api-helper';
import {
  EventResourceType,
  colorTypeResponse,
} from './types/googleCalendarSync/types'
import {
  googleCalendarResource,
} from './constants'
import { EventObjectForVectorType } from './types/event2Vectors/types';

dayjs.extend(utc)
dayjs.extend(timezone)

export const initialGoogleCalendarSync2 = async (
  calendarId: string,
  userId: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web',
  colorItem?: colorTypeResponse,
) => {
  try {
    let pageToken = ''
    let localItems: EventResourceType[] | [] = []
    const event2VectorObjects: EventObjectForVectorType[] | [] = []

    const token = await getGoogleAPIToken(userId, googleCalendarResource, clientType)

    const googleCalendar = google.calendar({
      version: 'v3',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
    const initialVariables = {
      calendarId,
      showDeleted: true,
      singleEvents: true,
    }

    const res = await googleCalendar.events.list(initialVariables)
    console.log(res.data)

    const { items, nextPageToken, nextSyncToken } = res.data
    console.log(' initial events list')
    localItems = items as EventResourceType[]
    pageToken = nextPageToken

    addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId)

    await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)
    const status = 'cancelled'

    const deletedEvents = localItems.filter((e) => (e?.status === status))

    if (deletedEvents?.[0]?.id) {
      console.log(' initial delete events')
      const promises = [
        deleteAttendees(deletedEvents, calendarId),
        deleteReminders(deletedEvents, userId, calendarId)
      ]

      await Promise.all(promises)

      const alreadyDeletedEvents = await deleteEvents(deletedEvents, calendarId)
      await deleteConferences(alreadyDeletedEvents)
    }

    const eventsToUpsert = localItems?.filter((e) => (e?.status !== status))

    // no events to upsert exit
    if (!(eventsToUpsert?.[0]?.id)) {
      console.log('no events to upsert check next pagetoken')
      const variables: any = {
        calendarId,
        showDeleted: true,
        singleEvents: true,
      }

      if (pageToken) {
        variables.pageToken = pageToken
        const res = await googleCalendar.events.list(variables)
        console.log(res.data)

        const { items, nextPageToken, nextSyncToken } = res.data

        localItems = items as EventResourceType[]
        pageToken = nextPageToken

        await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)

        const deletedEvents = localItems.filter((e) => (e?.status === status))

        if (deletedEvents?.[0]?.id) {
          const promises = [
            deleteAttendees(deletedEvents, calendarId),
            deleteReminders(deletedEvents, userId, calendarId)
          ]

          await Promise.all(promises)

          const alreadyDeletedEvents = await deleteEvents(deletedEvents, calendarId)
          await deleteConferences(alreadyDeletedEvents)
        }

        const eventsToUpsert2 = localItems?.filter((e) => (e?.status !== status))

        if (eventsToUpsert2?.[0]?.id) {
          const promises = [
            deleteReminders(eventsToUpsert2, userId, calendarId),
            insertRemindersGivenEventResource(eventsToUpsert2, userId, calendarId),
            upsertAttendees2(eventsToUpsert2, userId, calendarId),
          ]
          await upsertConference2(eventsToUpsert2, userId, calendarId)
          await Promise.all(promises)
          await upsertEvents2(eventsToUpsert2, userId, calendarId, colorItem)
        }
      }
    } else {
      console.log(' initial events upsert')
      const promises = [
        deleteReminders(eventsToUpsert, userId, calendarId),
        insertRemindersGivenEventResource(eventsToUpsert, userId, calendarId),
        upsertAttendees2(eventsToUpsert, userId, calendarId),
      ]
      await upsertConference2(eventsToUpsert, userId, calendarId)
      await Promise.all(promises)
      await upsertEvents2(eventsToUpsert, userId, calendarId, colorItem)
    }
    let count = 0
    if (pageToken) {
      // fetch all pages
      while (pageToken) {

        const variables = {
          calendarId,
          showDeleted: true,
          singleEvents: true,
          pageToken,
        }
        const res = await googleCalendar.events.list(variables)
        console.log(res.data)

        const { items, nextPageToken, nextSyncToken } = res.data

        localItems = items as EventResourceType[]
        pageToken = nextPageToken
        addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId)

        await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)

        const deletedEvents = localItems.filter((e) => (e?.status === status))

        if (deletedEvents?.[0]?.id) {
          console.log(count, '- loop count,  deleted events')
          const promises = [
            deleteAttendees(deletedEvents, calendarId),
            deleteReminders(deletedEvents, userId, calendarId)
          ]
          await Promise.all(promises)

          const alreadyDeletedEvents = await deleteEvents(deletedEvents, calendarId)
          await deleteConferences(alreadyDeletedEvents)
        }

        const eventsToUpsert = localItems?.filter((e) => (e?.status !== status))

        if (!(eventsToUpsert?.[0]?.id)) {
          console.log('no events to upsert check next pagetoken')
          const variables: any = {
            calendarId,
            showDeleted: true,
            singleEvents: true,
          }

          if (pageToken) {
            variables.pageToken = pageToken
            const res = await googleCalendar.events.list(variables)
            console.log(res.data)

            const { items, nextPageToken, nextSyncToken } = res.data

            localItems = items as EventResourceType[]
            pageToken = nextPageToken

            addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId)

            await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken)

            const deletedEvents = localItems.filter((e) => (e?.status === status))

            if (deletedEvents?.[0]?.id) {
              const promises = [
                deleteAttendees(deletedEvents, calendarId),
                deleteReminders(deletedEvents, userId, calendarId)
              ]

              await Promise.all(promises)

              const alreadyDeletedEvents = await deleteEvents(deletedEvents, calendarId)
              await deleteConferences(alreadyDeletedEvents)
            }

            const eventsToUpsert2 = localItems?.filter((e) => (e?.status !== status))

            if (eventsToUpsert2?.[0]?.id) {
              const promises = [
                deleteReminders(eventsToUpsert2, userId, calendarId),
                insertRemindersGivenEventResource(eventsToUpsert2, userId, calendarId),
                upsertAttendees2(eventsToUpsert2, userId, calendarId),
              ]
              await upsertConference2(eventsToUpsert2, userId, calendarId)
              await Promise.all(promises)
              await upsertEvents2(eventsToUpsert2, userId, calendarId, colorItem)
            }
          }
          count++
          continue
        }

        console.log(count, '- loop count,  upsert events')
        const promises = [
          deleteReminders(eventsToUpsert, userId, calendarId),
          insertRemindersGivenEventResource(eventsToUpsert, userId, calendarId),
          upsertAttendees2(eventsToUpsert, userId, calendarId),
        ]
        await upsertConference2(eventsToUpsert, userId, calendarId)
        await Promise.all(promises)
        await upsertEvents2(eventsToUpsert, userId, calendarId, colorItem)
        count++
      }
    }
    await addToQueueForVectorSearch(userId, event2VectorObjects)
    return true
  } catch (e: any) { // Added :any to access e.code
    if (e.code === 410) {
      console.log(`Google API returned 410 (GONE) for calendar ${calendarId}. Attempting full resync.`);
      // Assuming resetGoogleSyncForCalendar is designed to handle a full resync
      // and returns true on success, false on failure.
      return await resetGoogleSyncForCalendar(calendarId, userId, clientType, colorItem);
    } else {
      console.log(e, ' unable to initial google sync');
      return false;
    }
  }
}

export interface PerformCalendarSyncParams {
  calendarIntegrationId: string;
  calendarId: string;
  userId: string;
  timezone: string; // Already present in the handler, ensure it's used or passed if needed
}

export const performCalendarSync = async (params: PerformCalendarSyncParams) => {
  const { calendarIntegrationId, calendarId, userId, timezone } = params;

  // Validate timezone (already done in handler, but good practice for a shared function)
  if (!timezone) {
    return {
      success: false,
      message: 'no timezone present',
      status: 400,
    };
  }

  const googleIntegration = await getGoogleIntegration(calendarIntegrationId);
  if (!googleIntegration) {
    return {
      success: false,
      message: 'Google integration not found',
      status: 404, // Or appropriate error code
    };
  }
  const clientType = googleIntegration?.clientType;

  const calendarInDb = await getGoogleCalendarInDb(calendarId);
  const id = calendarInDb?.id;

  if (!id) {
    return {
      success: false,
      message: `${id} -id, calendar was deleted`,
      status: 400, // Or appropriate error code
    };
  }

  if (!clientType) {
    return {
      success: false,
      message: 'clientType is not available',
      status: 400,
    };
  }

  const authToken = await getGoogleAPIToken(userId, googleCalendarResource, clientType);
  const colorItem = await getGoogleColor(authToken);
  console.log(colorItem, ' colorItem inside performCalendarSync');

  const syncEnabled = await initialGoogleCalendarSync2(calendarId, userId, clientType, colorItem);

  if (syncEnabled === false) {
    await updateGoogleIntegration(calendarIntegrationId, syncEnabled);
    return {
      success: true,
      message: `sync is disabled for googleCalendarSync`,
      status: 200,
      syncDisabled: true,
    };
  }

  try {
    // Create push notification
    const channelId = uuidv4();
    const notificationToken = uuidv4(); // Renamed from token to avoid conflict with authToken

    console.log(channelId, notificationToken, ' channelId, notificationToken');

    const webhook = await getCalendarWebhookByCalendarId(calendarId);

    if (webhook?.id) {
      await stopCalendarWatch(webhook?.id, webhook?.resourceId);
      await deleteCalendarWebhookById(webhook?.id);
    }

    const response = await requestCalendarWatch(
      calendarId,
      channelId,
      notificationToken, // Use renamed token
      userId,
    );

    await insertCalendarWebhook({
      calendarId,
      createdDate: dayjs().format(),
      expiration: dayjs().add(604800, 's').format(), // 7 days
      id: channelId,
      resourceId: response?.resourceId,
      resourceUri: response?.resourceUri,
      token: notificationToken, // Use renamed token
      updatedAt: dayjs().format(),
      userId,
      calendarIntegrationId,
    });
  } catch (e: any) {
    console.log(e, 'Error managing calendar webhook');
    return {
      success: false,
      message: 'Error managing calendar webhook: ' + e.message,
      status: 500,
    };
  }

  return {
    success: true,
    message: 'successfully taken care of googleCalendarySync!',
    status: 200,
  };
};
