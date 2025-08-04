import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { google } from 'googleapis';
import { v4 as uuidv4 } from 'uuid';
import { deleteAttendees, deleteConferences, deleteEvents, deleteReminders, getGoogleAPIToken, getGoogleCalendarInDb, getGoogleColor, getGoogleIntegration, insertRemindersGivenEventResource, requestCalendarWatch, updateGoogleCalendarTokensInDb, updateGoogleIntegration, upsertAttendees2, insertCalendarWebhook, upsertConference2, upsertEvents2, getCalendarWebhookByCalendarId, stopCalendarWatch, deleteCalendarWebhookById, addToQueueForVectorSearch, addlocalItemsToEvent2VectorObjects, resetGoogleSyncForCalendar, // Added for 410 GONE error handling
 } from './api-helper';
import { googleCalendarResource } from './constants';
dayjs.extend(utc);
dayjs.extend(timezone);
export const initialGoogleCalendarSync2 = async (calendarId, userId, clientType, colorItem) => {
    try {
        let pageToken = '';
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
            calendarId,
            showDeleted: true,
            singleEvents: true,
        };
        const res = await googleCalendar.events.list(initialVariables);
        console.log(res.data);
        const { items, nextPageToken, nextSyncToken } = res.data;
        console.log(' initial events list');
        localItems = items;
        pageToken = nextPageToken;
        addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId);
        await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
        const status = 'cancelled';
        const deletedEvents = localItems.filter((e) => e?.status === status);
        if (deletedEvents?.[0]?.id) {
            console.log(' initial delete events');
            const promises = [
                deleteAttendees(deletedEvents, calendarId),
                deleteReminders(deletedEvents, userId, calendarId),
            ];
            await Promise.all(promises);
            const alreadyDeletedEvents = await deleteEvents(deletedEvents, calendarId);
            await deleteConferences(alreadyDeletedEvents);
        }
        const eventsToUpsert = localItems?.filter((e) => e?.status !== status);
        // no events to upsert exit
        if (!eventsToUpsert?.[0]?.id) {
            console.log('no events to upsert check next pagetoken');
            const variables = {
                calendarId,
                showDeleted: true,
                singleEvents: true,
            };
            if (pageToken) {
                variables.pageToken = pageToken;
                const res = await googleCalendar.events.list(variables);
                console.log(res.data);
                const { items, nextPageToken, nextSyncToken } = res.data;
                localItems = items;
                pageToken = nextPageToken;
                await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
                const deletedEvents = localItems.filter((e) => e?.status === status);
                if (deletedEvents?.[0]?.id) {
                    const promises = [
                        deleteAttendees(deletedEvents, calendarId),
                        deleteReminders(deletedEvents, userId, calendarId),
                    ];
                    await Promise.all(promises);
                    const alreadyDeletedEvents = await deleteEvents(deletedEvents, calendarId);
                    await deleteConferences(alreadyDeletedEvents);
                }
                const eventsToUpsert2 = localItems?.filter((e) => e?.status !== status);
                if (eventsToUpsert2?.[0]?.id) {
                    const promises = [
                        deleteReminders(eventsToUpsert2, userId, calendarId),
                        insertRemindersGivenEventResource(eventsToUpsert2, userId, calendarId),
                        upsertAttendees2(eventsToUpsert2, userId, calendarId),
                    ];
                    await upsertConference2(eventsToUpsert2, userId, calendarId);
                    await Promise.all(promises);
                    await upsertEvents2(eventsToUpsert2, userId, calendarId, colorItem);
                }
            }
        }
        else {
            console.log(' initial events upsert');
            const promises = [
                deleteReminders(eventsToUpsert, userId, calendarId),
                insertRemindersGivenEventResource(eventsToUpsert, userId, calendarId),
                upsertAttendees2(eventsToUpsert, userId, calendarId),
            ];
            await upsertConference2(eventsToUpsert, userId, calendarId);
            await Promise.all(promises);
            await upsertEvents2(eventsToUpsert, userId, calendarId, colorItem);
        }
        let count = 0;
        if (pageToken) {
            // fetch all pages
            while (pageToken) {
                const variables = {
                    calendarId,
                    showDeleted: true,
                    singleEvents: true,
                    pageToken,
                };
                const res = await googleCalendar.events.list(variables);
                console.log(res.data);
                const { items, nextPageToken, nextSyncToken } = res.data;
                localItems = items;
                pageToken = nextPageToken;
                addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId);
                await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
                const deletedEvents = localItems.filter((e) => e?.status === status);
                if (deletedEvents?.[0]?.id) {
                    console.log(count, '- loop count,  deleted events');
                    const promises = [
                        deleteAttendees(deletedEvents, calendarId),
                        deleteReminders(deletedEvents, userId, calendarId),
                    ];
                    await Promise.all(promises);
                    const alreadyDeletedEvents = await deleteEvents(deletedEvents, calendarId);
                    await deleteConferences(alreadyDeletedEvents);
                }
                const eventsToUpsert = localItems?.filter((e) => e?.status !== status);
                if (!eventsToUpsert?.[0]?.id) {
                    console.log('no events to upsert check next pagetoken');
                    const variables = {
                        calendarId,
                        showDeleted: true,
                        singleEvents: true,
                    };
                    if (pageToken) {
                        variables.pageToken = pageToken;
                        const res = await googleCalendar.events.list(variables);
                        console.log(res.data);
                        const { items, nextPageToken, nextSyncToken } = res.data;
                        localItems = items;
                        pageToken = nextPageToken;
                        addlocalItemsToEvent2VectorObjects(localItems, event2VectorObjects, calendarId);
                        await updateGoogleCalendarTokensInDb(calendarId, nextSyncToken, nextPageToken);
                        const deletedEvents = localItems.filter((e) => e?.status === status);
                        if (deletedEvents?.[0]?.id) {
                            const promises = [
                                deleteAttendees(deletedEvents, calendarId),
                                deleteReminders(deletedEvents, userId, calendarId),
                            ];
                            await Promise.all(promises);
                            const alreadyDeletedEvents = await deleteEvents(deletedEvents, calendarId);
                            await deleteConferences(alreadyDeletedEvents);
                        }
                        const eventsToUpsert2 = localItems?.filter((e) => e?.status !== status);
                        if (eventsToUpsert2?.[0]?.id) {
                            const promises = [
                                deleteReminders(eventsToUpsert2, userId, calendarId),
                                insertRemindersGivenEventResource(eventsToUpsert2, userId, calendarId),
                                upsertAttendees2(eventsToUpsert2, userId, calendarId),
                            ];
                            await upsertConference2(eventsToUpsert2, userId, calendarId);
                            await Promise.all(promises);
                            await upsertEvents2(eventsToUpsert2, userId, calendarId, colorItem);
                        }
                    }
                    count++;
                    continue;
                }
                console.log(count, '- loop count,  upsert events');
                const promises = [
                    deleteReminders(eventsToUpsert, userId, calendarId),
                    insertRemindersGivenEventResource(eventsToUpsert, userId, calendarId),
                    upsertAttendees2(eventsToUpsert, userId, calendarId),
                ];
                await upsertConference2(eventsToUpsert, userId, calendarId);
                await Promise.all(promises);
                await upsertEvents2(eventsToUpsert, userId, calendarId, colorItem);
                count++;
            }
        }
        await addToQueueForVectorSearch(userId, event2VectorObjects);
        return true;
    }
    catch (e) {
        // Added :any to access e.code
        if (e.code === 410) {
            console.log(`Google API returned 410 (GONE) for calendar ${calendarId}. Attempting full resync.`);
            // Assuming resetGoogleSyncForCalendar is designed to handle a full resync
            // and returns true on success, false on failure.
            return await resetGoogleSyncForCalendar(calendarId, userId, clientType, colorItem);
        }
        else {
            console.log(e, ' unable to initial google sync');
            return false;
        }
    }
};
export const performCalendarSync = async (params) => {
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
        const response = await requestCalendarWatch(calendarId, channelId, notificationToken, // Use renamed token
        userId);
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
    }
    catch (e) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3luYy1sb2dpYy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInN5bmMtbG9naWMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBQzFCLE9BQU8sR0FBRyxNQUFNLGtCQUFrQixDQUFDO0FBQ25DLE9BQU8sUUFBUSxNQUFNLHVCQUF1QixDQUFDO0FBQzdDLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxZQUFZLENBQUM7QUFDcEMsT0FBTyxFQUFFLEVBQUUsSUFBSSxNQUFNLEVBQUUsTUFBTSxNQUFNLENBQUM7QUFFcEMsT0FBTyxFQUNMLGVBQWUsRUFDZixpQkFBaUIsRUFDakIsWUFBWSxFQUNaLGVBQWUsRUFDZixpQkFBaUIsRUFDakIscUJBQXFCLEVBQ3JCLGNBQWMsRUFDZCxvQkFBb0IsRUFDcEIsaUNBQWlDLEVBQ2pDLG9CQUFvQixFQUNwQiw4QkFBOEIsRUFDOUIsdUJBQXVCLEVBQ3ZCLGdCQUFnQixFQUNoQixxQkFBcUIsRUFDckIsaUJBQWlCLEVBQ2pCLGFBQWEsRUFDYiw4QkFBOEIsRUFDOUIsaUJBQWlCLEVBQ2pCLHlCQUF5QixFQUN6Qix5QkFBeUIsRUFDekIsa0NBQWtDLEVBQ2xDLDBCQUEwQixFQUFFLG9DQUFvQztFQUNqRSxNQUFNLGNBQWMsQ0FBQztBQUt0QixPQUFPLEVBQUUsc0JBQXNCLEVBQUUsTUFBTSxhQUFhLENBQUM7QUFHckQsS0FBSyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQztBQUNsQixLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBRXZCLE1BQU0sQ0FBQyxNQUFNLDBCQUEwQixHQUFHLEtBQUssRUFDN0MsVUFBa0IsRUFDbEIsTUFBYyxFQUNkLFVBQW9ELEVBQ3BELFNBQTZCLEVBQzdCLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxJQUFJLFNBQVMsR0FBRyxFQUFFLENBQUM7UUFDbkIsSUFBSSxVQUFVLEdBQTZCLEVBQUUsQ0FB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QUUsUUFBUSxFQUFFLFVBQVU7WUFDaEMsV0FBVyxFQUFFLFFBQVEsRUFBRSxXQUFXO1lBQ2xDLEtBQUssRUFBRSxpQkFBaUIsRUFBRSxvQkFBb0I7WUFDOUMsU0FBUyxFQUFFLEtBQUssRUFBRSxDQUFDLE1BQU0sRUFBRTtZQUMzQixNQUFNO1lBQ04scUJBQXFCO1NBQ3RCLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGlDQUFpQyxDQUFDLENBQUM7UUFDbEQsT0FBTztZQUNMLE9BQU8sRUFBRSxLQUFLO1lBQ2QsT0FBTyxFQUFFLG1DQUFtQyxHQUFHLENBQUMsQ0FBQyxPQUFPO1lBQ3hELE1BQU0sRUFBRSxHQUFHO1NBQ1osQ0FBQztJQUNKLENBQUM7SUFFRCxPQUFPO1FBQ0wsT0FBTyxFQUFFLElBQUk7UUFDYixPQUFPLEVBQUUsaURBQWlEO1FBQzFELE1BQU0sRUFBRSxHQUFHO0tBQ1osQ0FBQztBQUNKLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG5pbXBvcnQgdXRjIGZyb20gJ2RheWpzL3BsdWdpbi91dGMnO1xuaW1wb3J0IHRpbWV6b25lIGZyb20gJ2RheWpzL3BsdWdpbi90aW1lem9uZSc7XG5pbXBvcnQgeyBnb29nbGUgfSBmcm9tICdnb29nbGVhcGlzJztcbmltcG9ydCB7IHY0IGFzIHV1aWR2NCB9IGZyb20gJ3V1aWQnO1xuXG5pbXBvcnQge1xuICBkZWxldGVBdHRlbmRlZXMsXG4gIGRlbGV0ZUNvbmZlcmVuY2VzLFxuICBkZWxldGVFdmVudHMsXG4gIGRlbGV0ZVJlbWluZGVycyxcbiAgZ2V0R29vZ2xlQVBJVG9rZW4sXG4gIGdldEdvb2dsZUNhbGVuZGFySW5EYixcbiAgZ2V0R29vZ2xlQ29sb3IsXG4gIGdldEdvb2dsZUludGVncmF0aW9uLFxuICBpbnNlcnRSZW1pbmRlcnNHaXZlbkV2ZW50UmVzb3VyY2UsXG4gIHJlcXVlc3RDYWxlbmRhcldhdGNoLFxuICB1cGRhdGVHb29nbGVDYWxlbmRhclRva2Vuc0luRGIsXG4gIHVwZGF0ZUdvb2dsZUludGVncmF0aW9uLFxuICB1cHNlcnRBdHRlbmRlZXMyLFxuICBpbnNlcnRDYWxlbmRhcldlYmhvb2ssXG4gIHVwc2VydENvbmZlcmVuY2UyLFxuICB1cHNlcnRFdmVudHMyLFxuICBnZXRDYWxlbmRhcldlYmhvb2tCeUNhbGVuZGFySWQsXG4gIHN0b3BDYWxlbmRhcldhdGNoLFxuICBkZWxldGVDYWxlbmRhcldlYmhvb2tCeUlkLFxuICBhZGRUb1F1ZXVlRm9yVmVjdG9yU2VhcmNoLFxuICBhZGRsb2NhbEl0ZW1zVG9FdmVudDJWZWN0b3JPYmplY3RzLFxuICByZXNldEdvb2dsZVN5bmNGb3JDYWxlbmRhciwgLy8gQWRkZWQgZm9yIDQxMCBHT05FIGVycm9yIGhhbmRsaW5nXG59IGZyb20gJy4vYXBpLWhlbHBlcic7XG5pbXBvcnQge1xuICBFdmVudFJlc291cmNlVHlwZSxcbiAgY29sb3JUeXBlUmVzcG9uc2UsXG59IGZyb20gJy4vdHlwZXMvZ29vZ2xlQ2FsZW5kYXJTeW5jL3R5cGVzJztcbmltcG9ydCB7IGdvb2dsZUNhbGVuZGFyUmVzb3VyY2UgfSBmcm9tICcuL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBFdmVudE9iamVjdEZvclZlY3RvclR5cGUgfSBmcm9tICcuL3R5cGVzL2V2ZW50MlZlY3RvcnMvdHlwZXMnO1xuXG5kYXlqcy5leHRlbmQodXRjKTtcbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5cbmV4cG9ydCBjb25zdCBpbml0aWFsR29vZ2xlQ2FsZW5kYXJTeW5jMiA9IGFzeW5jIChcbiAgY2FsZW5kYXJJZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY2xpZW50VHlwZTogJ2lvcycgfCAnYW5kcm9pZCcgfCAnd2ViJyB8ICdhdG9taWMtd2ViJyxcbiAgY29sb3JJdGVtPzogY29sb3JUeXBlUmVzcG9uc2VcbikgPT4ge1xuICB0cnkge1xuICAgIGxldCBwYWdlVG9rZW4gPSAnJztcbiAgICBsZXQgbG9jYWxJdGVtczogRXZlbnRSZXNvdXJjZVR5cGVbXSB8IFtdID0gW107XG4gICAgY29uc3QgZXZlbnQyVmVjdG9yT2JqZWN0czogRXZlbnRPYmplY3RGb3JWZWN0b3JUeXBlW10gfCBbXSA9IFtdO1xuXG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRHb29nbGVBUElUb2tlbihcbiAgICAgIHVzZXJJZCxcbiAgICAgIGdvb2dsZUNhbGVuZGFyUmVzb3VyY2UsXG4gICAgICBjbGllbnRUeXBlXG4gICAgKTtcblxuICAgIGNvbnN0IGdvb2dsZUNhbGVuZGFyID0gZ29vZ2xlLmNhbGVuZGFyKHtcbiAgICAgIHZlcnNpb246ICd2MycsXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgfSxcbiAgICB9KTtcbiAgICBjb25zdCBpbml0aWFsVmFyaWFibGVzID0ge1xuICAgICAgY2FsZW5kYXJJZCxcbiAgICAgIHNob3dEZWxldGVkOiB0cnVlLFxuICAgICAgc2luZ2xlRXZlbnRzOiB0cnVlLFxuICAgIH07XG5cbiAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVDYWxlbmRhci5ldmVudHMubGlzdChpbml0aWFsVmFyaWFibGVzKTtcbiAgICBjb25zb2xlLmxvZyhyZXMuZGF0YSk7XG5cbiAgICBjb25zdCB7IGl0ZW1zLCBuZXh0UGFnZVRva2VuLCBuZXh0U3luY1Rva2VuIH0gPSByZXMuZGF0YTtcbiAgICBjb25zb2xlLmxvZygnIGluaXRpYWwgZXZlbnRzIGxpc3QnKTtcbiAgICBsb2NhbEl0ZW1zID0gaXRlbXMgYXMgRXZlbnRSZXNvdXJjZVR5cGVbXTtcbiAgICBwYWdlVG9rZW4gPSBuZXh0UGFnZVRva2VuO1xuXG4gICAgYWRkbG9jYWxJdGVtc1RvRXZlbnQyVmVjdG9yT2JqZWN0cyhcbiAgICAgIGxvY2FsSXRlbXMsXG4gICAgICBldmVudDJWZWN0b3JPYmplY3RzLFxuICAgICAgY2FsZW5kYXJJZFxuICAgICk7XG5cbiAgICBhd2FpdCB1cGRhdGVHb29nbGVDYWxlbmRhclRva2Vuc0luRGIoXG4gICAgICBjYWxlbmRhcklkLFxuICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgIG5leHRQYWdlVG9rZW5cbiAgICApO1xuICAgIGNvbnN0IHN0YXR1cyA9ICdjYW5jZWxsZWQnO1xuXG4gICAgY29uc3QgZGVsZXRlZEV2ZW50cyA9IGxvY2FsSXRlbXMuZmlsdGVyKChlKSA9PiBlPy5zdGF0dXMgPT09IHN0YXR1cyk7XG5cbiAgICBpZiAoZGVsZXRlZEV2ZW50cz8uWzBdPy5pZCkge1xuICAgICAgY29uc29sZS5sb2coJyBpbml0aWFsIGRlbGV0ZSBldmVudHMnKTtcbiAgICAgIGNvbnN0IHByb21pc2VzID0gW1xuICAgICAgICBkZWxldGVBdHRlbmRlZXMoZGVsZXRlZEV2ZW50cywgY2FsZW5kYXJJZCksXG4gICAgICAgIGRlbGV0ZVJlbWluZGVycyhkZWxldGVkRXZlbnRzLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgXTtcblxuICAgICAgYXdhaXQgUHJvbWlzZS5hbGwocHJvbWlzZXMpO1xuXG4gICAgICBjb25zdCBhbHJlYWR5RGVsZXRlZEV2ZW50cyA9IGF3YWl0IGRlbGV0ZUV2ZW50cyhcbiAgICAgICAgZGVsZXRlZEV2ZW50cyxcbiAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgKTtcbiAgICAgIGF3YWl0IGRlbGV0ZUNvbmZlcmVuY2VzKGFscmVhZHlEZWxldGVkRXZlbnRzKTtcbiAgICB9XG5cbiAgICBjb25zdCBldmVudHNUb1Vwc2VydCA9IGxvY2FsSXRlbXM/LmZpbHRlcigoZSkgPT4gZT8uc3RhdHVzICE9PSBzdGF0dXMpO1xuXG4gICAgLy8gbm8gZXZlbnRzIHRvIHVwc2VydCBleGl0XG4gICAgaWYgKCFldmVudHNUb1Vwc2VydD8uWzBdPy5pZCkge1xuICAgICAgY29uc29sZS5sb2coJ25vIGV2ZW50cyB0byB1cHNlcnQgY2hlY2sgbmV4dCBwYWdldG9rZW4nKTtcbiAgICAgIGNvbnN0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICBzaG93RGVsZXRlZDogdHJ1ZSxcbiAgICAgICAgc2luZ2xlRXZlbnRzOiB0cnVlLFxuICAgICAgfTtcblxuICAgICAgaWYgKHBhZ2VUb2tlbikge1xuICAgICAgICB2YXJpYWJsZXMucGFnZVRva2VuID0gcGFnZVRva2VuO1xuICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVDYWxlbmRhci5ldmVudHMubGlzdCh2YXJpYWJsZXMpO1xuICAgICAgICBjb25zb2xlLmxvZyhyZXMuZGF0YSk7XG5cbiAgICAgICAgY29uc3QgeyBpdGVtcywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG5cbiAgICAgICAgbG9jYWxJdGVtcyA9IGl0ZW1zIGFzIEV2ZW50UmVzb3VyY2VUeXBlW107XG4gICAgICAgIHBhZ2VUb2tlbiA9IG5leHRQYWdlVG9rZW47XG5cbiAgICAgICAgYXdhaXQgdXBkYXRlR29vZ2xlQ2FsZW5kYXJUb2tlbnNJbkRiKFxuICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICBuZXh0UGFnZVRva2VuXG4gICAgICAgICk7XG5cbiAgICAgICAgY29uc3QgZGVsZXRlZEV2ZW50cyA9IGxvY2FsSXRlbXMuZmlsdGVyKChlKSA9PiBlPy5zdGF0dXMgPT09IHN0YXR1cyk7XG5cbiAgICAgICAgaWYgKGRlbGV0ZWRFdmVudHM/LlswXT8uaWQpIHtcbiAgICAgICAgICBjb25zdCBwcm9taXNlcyA9IFtcbiAgICAgICAgICAgIGRlbGV0ZUF0dGVuZGVlcyhkZWxldGVkRXZlbnRzLCBjYWxlbmRhcklkKSxcbiAgICAgICAgICAgIGRlbGV0ZVJlbWluZGVycyhkZWxldGVkRXZlbnRzLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgIF07XG5cbiAgICAgICAgICBhd2FpdCBQcm9taXNlLmFsbChwcm9taXNlcyk7XG5cbiAgICAgICAgICBjb25zdCBhbHJlYWR5RGVsZXRlZEV2ZW50cyA9IGF3YWl0IGRlbGV0ZUV2ZW50cyhcbiAgICAgICAgICAgIGRlbGV0ZWRFdmVudHMsXG4gICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgKTtcbiAgICAgICAgICBhd2FpdCBkZWxldGVDb25mZXJlbmNlcyhhbHJlYWR5RGVsZXRlZEV2ZW50cyk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBldmVudHNUb1Vwc2VydDIgPSBsb2NhbEl0ZW1zPy5maWx0ZXIoKGUpID0+IGU/LnN0YXR1cyAhPT0gc3RhdHVzKTtcblxuICAgICAgICBpZiAoZXZlbnRzVG9VcHNlcnQyPy5bMF0/LmlkKSB7XG4gICAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXG4gICAgICAgICAgICBkZWxldGVSZW1pbmRlcnMoZXZlbnRzVG9VcHNlcnQyLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgaW5zZXJ0UmVtaW5kZXJzR2l2ZW5FdmVudFJlc291cmNlKFxuICAgICAgICAgICAgICBldmVudHNUb1Vwc2VydDIsXG4gICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgKSxcbiAgICAgICAgICAgIHVwc2VydEF0dGVuZGVlczIoZXZlbnRzVG9VcHNlcnQyLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgIF07XG4gICAgICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZTIoZXZlbnRzVG9VcHNlcnQyLCB1c2VySWQsIGNhbGVuZGFySWQpO1xuICAgICAgICAgIGF3YWl0IFByb21pc2UuYWxsKHByb21pc2VzKTtcbiAgICAgICAgICBhd2FpdCB1cHNlcnRFdmVudHMyKGV2ZW50c1RvVXBzZXJ0MiwgdXNlcklkLCBjYWxlbmRhcklkLCBjb2xvckl0ZW0pO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgaW5pdGlhbCBldmVudHMgdXBzZXJ0Jyk7XG4gICAgICBjb25zdCBwcm9taXNlcyA9IFtcbiAgICAgICAgZGVsZXRlUmVtaW5kZXJzKGV2ZW50c1RvVXBzZXJ0LCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICBpbnNlcnRSZW1pbmRlcnNHaXZlbkV2ZW50UmVzb3VyY2UoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCksXG4gICAgICAgIHVwc2VydEF0dGVuZGVlczIoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCksXG4gICAgICBdO1xuICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZTIoZXZlbnRzVG9VcHNlcnQsIHVzZXJJZCwgY2FsZW5kYXJJZCk7XG4gICAgICBhd2FpdCBQcm9taXNlLmFsbChwcm9taXNlcyk7XG4gICAgICBhd2FpdCB1cHNlcnRFdmVudHMyKGV2ZW50c1RvVXBzZXJ0LCB1c2VySWQsIGNhbGVuZGFySWQsIGNvbG9ySXRlbSk7XG4gICAgfVxuICAgIGxldCBjb3VudCA9IDA7XG4gICAgaWYgKHBhZ2VUb2tlbikge1xuICAgICAgLy8gZmV0Y2ggYWxsIHBhZ2VzXG4gICAgICB3aGlsZSAocGFnZVRva2VuKSB7XG4gICAgICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICAgIHNob3dEZWxldGVkOiB0cnVlLFxuICAgICAgICAgIHNpbmdsZUV2ZW50czogdHJ1ZSxcbiAgICAgICAgICBwYWdlVG9rZW4sXG4gICAgICAgIH07XG4gICAgICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvb2dsZUNhbGVuZGFyLmV2ZW50cy5saXN0KHZhcmlhYmxlcyk7XG4gICAgICAgIGNvbnNvbGUubG9nKHJlcy5kYXRhKTtcblxuICAgICAgICBjb25zdCB7IGl0ZW1zLCBuZXh0UGFnZVRva2VuLCBuZXh0U3luY1Rva2VuIH0gPSByZXMuZGF0YTtcblxuICAgICAgICBsb2NhbEl0ZW1zID0gaXRlbXMgYXMgRXZlbnRSZXNvdXJjZVR5cGVbXTtcbiAgICAgICAgcGFnZVRva2VuID0gbmV4dFBhZ2VUb2tlbjtcbiAgICAgICAgYWRkbG9jYWxJdGVtc1RvRXZlbnQyVmVjdG9yT2JqZWN0cyhcbiAgICAgICAgICBsb2NhbEl0ZW1zLFxuICAgICAgICAgIGV2ZW50MlZlY3Rvck9iamVjdHMsXG4gICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICApO1xuXG4gICAgICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUNhbGVuZGFyVG9rZW5zSW5EYihcbiAgICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgbmV4dFBhZ2VUb2tlblxuICAgICAgICApO1xuXG4gICAgICAgIGNvbnN0IGRlbGV0ZWRFdmVudHMgPSBsb2NhbEl0ZW1zLmZpbHRlcigoZSkgPT4gZT8uc3RhdHVzID09PSBzdGF0dXMpO1xuXG4gICAgICAgIGlmIChkZWxldGVkRXZlbnRzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coY291bnQsICctIGxvb3AgY291bnQsICBkZWxldGVkIGV2ZW50cycpO1xuICAgICAgICAgIGNvbnN0IHByb21pc2VzID0gW1xuICAgICAgICAgICAgZGVsZXRlQXR0ZW5kZWVzKGRlbGV0ZWRFdmVudHMsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgZGVsZXRlUmVtaW5kZXJzKGRlbGV0ZWRFdmVudHMsIHVzZXJJZCwgY2FsZW5kYXJJZCksXG4gICAgICAgICAgXTtcbiAgICAgICAgICBhd2FpdCBQcm9taXNlLmFsbChwcm9taXNlcyk7XG5cbiAgICAgICAgICBjb25zdCBhbHJlYWR5RGVsZXRlZEV2ZW50cyA9IGF3YWl0IGRlbGV0ZUV2ZW50cyhcbiAgICAgICAgICAgIGRlbGV0ZWRFdmVudHMsXG4gICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgKTtcbiAgICAgICAgICBhd2FpdCBkZWxldGVDb25mZXJlbmNlcyhhbHJlYWR5RGVsZXRlZEV2ZW50cyk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBldmVudHNUb1Vwc2VydCA9IGxvY2FsSXRlbXM/LmZpbHRlcigoZSkgPT4gZT8uc3RhdHVzICE9PSBzdGF0dXMpO1xuXG4gICAgICAgIGlmICghZXZlbnRzVG9VcHNlcnQ/LlswXT8uaWQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlbicpO1xuICAgICAgICAgIGNvbnN0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICAgIHNob3dEZWxldGVkOiB0cnVlLFxuICAgICAgICAgICAgc2luZ2xlRXZlbnRzOiB0cnVlLFxuICAgICAgICAgIH07XG5cbiAgICAgICAgICBpZiAocGFnZVRva2VuKSB7XG4gICAgICAgICAgICB2YXJpYWJsZXMucGFnZVRva2VuID0gcGFnZVRva2VuO1xuICAgICAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlQ2FsZW5kYXIuZXZlbnRzLmxpc3QodmFyaWFibGVzKTtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKHJlcy5kYXRhKTtcblxuICAgICAgICAgICAgY29uc3QgeyBpdGVtcywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG5cbiAgICAgICAgICAgIGxvY2FsSXRlbXMgPSBpdGVtcyBhcyBFdmVudFJlc291cmNlVHlwZVtdO1xuICAgICAgICAgICAgcGFnZVRva2VuID0gbmV4dFBhZ2VUb2tlbjtcblxuICAgICAgICAgICAgYWRkbG9jYWxJdGVtc1RvRXZlbnQyVmVjdG9yT2JqZWN0cyhcbiAgICAgICAgICAgICAgbG9jYWxJdGVtcyxcbiAgICAgICAgICAgICAgZXZlbnQyVmVjdG9yT2JqZWN0cyxcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgYXdhaXQgdXBkYXRlR29vZ2xlQ2FsZW5kYXJUb2tlbnNJbkRiKFxuICAgICAgICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICAgICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgICAgICAgICBuZXh0UGFnZVRva2VuXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICBjb25zdCBkZWxldGVkRXZlbnRzID0gbG9jYWxJdGVtcy5maWx0ZXIoXG4gICAgICAgICAgICAgIChlKSA9PiBlPy5zdGF0dXMgPT09IHN0YXR1c1xuICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgaWYgKGRlbGV0ZWRFdmVudHM/LlswXT8uaWQpIHtcbiAgICAgICAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXG4gICAgICAgICAgICAgICAgZGVsZXRlQXR0ZW5kZWVzKGRlbGV0ZWRFdmVudHMsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgICAgIGRlbGV0ZVJlbWluZGVycyhkZWxldGVkRXZlbnRzLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgICBdO1xuXG4gICAgICAgICAgICAgIGF3YWl0IFByb21pc2UuYWxsKHByb21pc2VzKTtcblxuICAgICAgICAgICAgICBjb25zdCBhbHJlYWR5RGVsZXRlZEV2ZW50cyA9IGF3YWl0IGRlbGV0ZUV2ZW50cyhcbiAgICAgICAgICAgICAgICBkZWxldGVkRXZlbnRzLFxuICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgYXdhaXQgZGVsZXRlQ29uZmVyZW5jZXMoYWxyZWFkeURlbGV0ZWRFdmVudHMpO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBjb25zdCBldmVudHNUb1Vwc2VydDIgPSBsb2NhbEl0ZW1zPy5maWx0ZXIoXG4gICAgICAgICAgICAgIChlKSA9PiBlPy5zdGF0dXMgIT09IHN0YXR1c1xuICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgaWYgKGV2ZW50c1RvVXBzZXJ0Mj8uWzBdPy5pZCkge1xuICAgICAgICAgICAgICBjb25zdCBwcm9taXNlcyA9IFtcbiAgICAgICAgICAgICAgICBkZWxldGVSZW1pbmRlcnMoZXZlbnRzVG9VcHNlcnQyLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgICAgIGluc2VydFJlbWluZGVyc0dpdmVuRXZlbnRSZXNvdXJjZShcbiAgICAgICAgICAgICAgICAgIGV2ZW50c1RvVXBzZXJ0MixcbiAgICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICApLFxuICAgICAgICAgICAgICAgIHVwc2VydEF0dGVuZGVlczIoZXZlbnRzVG9VcHNlcnQyLCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgICAgICBdO1xuICAgICAgICAgICAgICBhd2FpdCB1cHNlcnRDb25mZXJlbmNlMihldmVudHNUb1Vwc2VydDIsIHVzZXJJZCwgY2FsZW5kYXJJZCk7XG4gICAgICAgICAgICAgIGF3YWl0IFByb21pc2UuYWxsKHByb21pc2VzKTtcbiAgICAgICAgICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzMihcbiAgICAgICAgICAgICAgICBldmVudHNUb1Vwc2VydDIsXG4gICAgICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgICAgICAgICAgY29sb3JJdGVtXG4gICAgICAgICAgICAgICk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAgIGNvdW50Kys7XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zb2xlLmxvZyhjb3VudCwgJy0gbG9vcCBjb3VudCwgIHVwc2VydCBldmVudHMnKTtcbiAgICAgICAgY29uc3QgcHJvbWlzZXMgPSBbXG4gICAgICAgICAgZGVsZXRlUmVtaW5kZXJzKGV2ZW50c1RvVXBzZXJ0LCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICAgIGluc2VydFJlbWluZGVyc0dpdmVuRXZlbnRSZXNvdXJjZShldmVudHNUb1Vwc2VydCwgdXNlcklkLCBjYWxlbmRhcklkKSxcbiAgICAgICAgICB1cHNlcnRBdHRlbmRlZXMyKGV2ZW50c1RvVXBzZXJ0LCB1c2VySWQsIGNhbGVuZGFySWQpLFxuICAgICAgICBdO1xuICAgICAgICBhd2FpdCB1cHNlcnRDb25mZXJlbmNlMihldmVudHNUb1Vwc2VydCwgdXNlcklkLCBjYWxlbmRhcklkKTtcbiAgICAgICAgYXdhaXQgUHJvbWlzZS5hbGwocHJvbWlzZXMpO1xuICAgICAgICBhd2FpdCB1cHNlcnRFdmVudHMyKGV2ZW50c1RvVXBzZXJ0LCB1c2VySWQsIGNhbGVuZGFySWQsIGNvbG9ySXRlbSk7XG4gICAgICAgIGNvdW50Kys7XG4gICAgICB9XG4gICAgfVxuICAgIGF3YWl0IGFkZFRvUXVldWVGb3JWZWN0b3JTZWFyY2godXNlcklkLCBldmVudDJWZWN0b3JPYmplY3RzKTtcbiAgICByZXR1cm4gdHJ1ZTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgLy8gQWRkZWQgOmFueSB0byBhY2Nlc3MgZS5jb2RlXG4gICAgaWYgKGUuY29kZSA9PT0gNDEwKSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYEdvb2dsZSBBUEkgcmV0dXJuZWQgNDEwIChHT05FKSBmb3IgY2FsZW5kYXIgJHtjYWxlbmRhcklkfS4gQXR0ZW1wdGluZyBmdWxsIHJlc3luYy5gXG4gICAgICApO1xuICAgICAgLy8gQXNzdW1pbmcgcmVzZXRHb29nbGVTeW5jRm9yQ2FsZW5kYXIgaXMgZGVzaWduZWQgdG8gaGFuZGxlIGEgZnVsbCByZXN5bmNcbiAgICAgIC8vIGFuZCByZXR1cm5zIHRydWUgb24gc3VjY2VzcywgZmFsc2Ugb24gZmFpbHVyZS5cbiAgICAgIHJldHVybiBhd2FpdCByZXNldEdvb2dsZVN5bmNGb3JDYWxlbmRhcihcbiAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBjbGllbnRUeXBlLFxuICAgICAgICBjb2xvckl0ZW1cbiAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGluaXRpYWwgZ29vZ2xlIHN5bmMnKTtcbiAgICAgIHJldHVybiBmYWxzZTtcbiAgICB9XG4gIH1cbn07XG5cbmV4cG9ydCBpbnRlcmZhY2UgUGVyZm9ybUNhbGVuZGFyU3luY1BhcmFtcyB7XG4gIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nO1xuICBjYWxlbmRhcklkOiBzdHJpbmc7XG4gIHVzZXJJZDogc3RyaW5nO1xuICB0aW1lem9uZTogc3RyaW5nOyAvLyBBbHJlYWR5IHByZXNlbnQgaW4gdGhlIGhhbmRsZXIsIGVuc3VyZSBpdCdzIHVzZWQgb3IgcGFzc2VkIGlmIG5lZWRlZFxufVxuXG5leHBvcnQgY29uc3QgcGVyZm9ybUNhbGVuZGFyU3luYyA9IGFzeW5jIChcbiAgcGFyYW1zOiBQZXJmb3JtQ2FsZW5kYXJTeW5jUGFyYW1zXG4pID0+IHtcbiAgY29uc3QgeyBjYWxlbmRhckludGVncmF0aW9uSWQsIGNhbGVuZGFySWQsIHVzZXJJZCwgdGltZXpvbmUgfSA9IHBhcmFtcztcblxuICAvLyBWYWxpZGF0ZSB0aW1lem9uZSAoYWxyZWFkeSBkb25lIGluIGhhbmRsZXIsIGJ1dCBnb29kIHByYWN0aWNlIGZvciBhIHNoYXJlZCBmdW5jdGlvbilcbiAgaWYgKCF0aW1lem9uZSkge1xuICAgIHJldHVybiB7XG4gICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgIG1lc3NhZ2U6ICdubyB0aW1lem9uZSBwcmVzZW50JyxcbiAgICAgIHN0YXR1czogNDAwLFxuICAgIH07XG4gIH1cblxuICBjb25zdCBnb29nbGVJbnRlZ3JhdGlvbiA9IGF3YWl0IGdldEdvb2dsZUludGVncmF0aW9uKGNhbGVuZGFySW50ZWdyYXRpb25JZCk7XG4gIGlmICghZ29vZ2xlSW50ZWdyYXRpb24pIHtcbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOiAnR29vZ2xlIGludGVncmF0aW9uIG5vdCBmb3VuZCcsXG4gICAgICBzdGF0dXM6IDQwNCwgLy8gT3IgYXBwcm9wcmlhdGUgZXJyb3IgY29kZVxuICAgIH07XG4gIH1cbiAgY29uc3QgY2xpZW50VHlwZSA9IGdvb2dsZUludGVncmF0aW9uPy5jbGllbnRUeXBlO1xuXG4gIGNvbnN0IGNhbGVuZGFySW5EYiA9IGF3YWl0IGdldEdvb2dsZUNhbGVuZGFySW5EYihjYWxlbmRhcklkKTtcbiAgY29uc3QgaWQgPSBjYWxlbmRhckluRGI/LmlkO1xuXG4gIGlmICghaWQpIHtcbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOiBgJHtpZH0gLWlkLCBjYWxlbmRhciB3YXMgZGVsZXRlZGAsXG4gICAgICBzdGF0dXM6IDQwMCwgLy8gT3IgYXBwcm9wcmlhdGUgZXJyb3IgY29kZVxuICAgIH07XG4gIH1cblxuICBpZiAoIWNsaWVudFR5cGUpIHtcbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOiAnY2xpZW50VHlwZSBpcyBub3QgYXZhaWxhYmxlJyxcbiAgICAgIHN0YXR1czogNDAwLFxuICAgIH07XG4gIH1cblxuICBjb25zdCBhdXRoVG9rZW4gPSBhd2FpdCBnZXRHb29nbGVBUElUb2tlbihcbiAgICB1c2VySWQsXG4gICAgZ29vZ2xlQ2FsZW5kYXJSZXNvdXJjZSxcbiAgICBjbGllbnRUeXBlXG4gICk7XG4gIGNvbnN0IGNvbG9ySXRlbSA9IGF3YWl0IGdldEdvb2dsZUNvbG9yKGF1dGhUb2tlbik7XG4gIGNvbnNvbGUubG9nKGNvbG9ySXRlbSwgJyBjb2xvckl0ZW0gaW5zaWRlIHBlcmZvcm1DYWxlbmRhclN5bmMnKTtcblxuICBjb25zdCBzeW5jRW5hYmxlZCA9IGF3YWl0IGluaXRpYWxHb29nbGVDYWxlbmRhclN5bmMyKFxuICAgIGNhbGVuZGFySWQsXG4gICAgdXNlcklkLFxuICAgIGNsaWVudFR5cGUsXG4gICAgY29sb3JJdGVtXG4gICk7XG5cbiAgaWYgKHN5bmNFbmFibGVkID09PSBmYWxzZSkge1xuICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUludGVncmF0aW9uKGNhbGVuZGFySW50ZWdyYXRpb25JZCwgc3luY0VuYWJsZWQpO1xuICAgIHJldHVybiB7XG4gICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgbWVzc2FnZTogYHN5bmMgaXMgZGlzYWJsZWQgZm9yIGdvb2dsZUNhbGVuZGFyU3luY2AsXG4gICAgICBzdGF0dXM6IDIwMCxcbiAgICAgIHN5bmNEaXNhYmxlZDogdHJ1ZSxcbiAgICB9O1xuICB9XG5cbiAgdHJ5IHtcbiAgICAvLyBDcmVhdGUgcHVzaCBub3RpZmljYXRpb25cbiAgICBjb25zdCBjaGFubmVsSWQgPSB1dWlkdjQoKTtcbiAgICBjb25zdCBub3RpZmljYXRpb25Ub2tlbiA9IHV1aWR2NCgpOyAvLyBSZW5hbWVkIGZyb20gdG9rZW4gdG8gYXZvaWQgY29uZmxpY3Qgd2l0aCBhdXRoVG9rZW5cblxuICAgIGNvbnNvbGUubG9nKGNoYW5uZWxJZCwgbm90aWZpY2F0aW9uVG9rZW4sICcgY2hhbm5lbElkLCBub3RpZmljYXRpb25Ub2tlbicpO1xuXG4gICAgY29uc3Qgd2ViaG9vayA9IGF3YWl0IGdldENhbGVuZGFyV2ViaG9va0J5Q2FsZW5kYXJJZChjYWxlbmRhcklkKTtcblxuICAgIGlmICh3ZWJob29rPy5pZCkge1xuICAgICAgYXdhaXQgc3RvcENhbGVuZGFyV2F0Y2god2ViaG9vaz8uaWQsIHdlYmhvb2s/LnJlc291cmNlSWQpO1xuICAgICAgYXdhaXQgZGVsZXRlQ2FsZW5kYXJXZWJob29rQnlJZCh3ZWJob29rPy5pZCk7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCByZXF1ZXN0Q2FsZW5kYXJXYXRjaChcbiAgICAgIGNhbGVuZGFySWQsXG4gICAgICBjaGFubmVsSWQsXG4gICAgICBub3RpZmljYXRpb25Ub2tlbiwgLy8gVXNlIHJlbmFtZWQgdG9rZW5cbiAgICAgIHVzZXJJZFxuICAgICk7XG5cbiAgICBhd2FpdCBpbnNlcnRDYWxlbmRhcldlYmhvb2soe1xuICAgICAgY2FsZW5kYXJJZCxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgZXhwaXJhdGlvbjogZGF5anMoKS5hZGQoNjA0ODAwLCAncycpLmZvcm1hdCgpLCAvLyA3IGRheXNcbiAgICAgIGlkOiBjaGFubmVsSWQsXG4gICAgICByZXNvdXJjZUlkOiByZXNwb25zZT8ucmVzb3VyY2VJZCxcbiAgICAgIHJlc291cmNlVXJpOiByZXNwb25zZT8ucmVzb3VyY2VVcmksXG4gICAgICB0b2tlbjogbm90aWZpY2F0aW9uVG9rZW4sIC8vIFVzZSByZW5hbWVkIHRva2VuXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICB1c2VySWQsXG4gICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUubG9nKGUsICdFcnJvciBtYW5hZ2luZyBjYWxlbmRhciB3ZWJob29rJyk7XG4gICAgcmV0dXJuIHtcbiAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgbWVzc2FnZTogJ0Vycm9yIG1hbmFnaW5nIGNhbGVuZGFyIHdlYmhvb2s6ICcgKyBlLm1lc3NhZ2UsXG4gICAgICBzdGF0dXM6IDUwMCxcbiAgICB9O1xuICB9XG5cbiAgcmV0dXJuIHtcbiAgICBzdWNjZXNzOiB0cnVlLFxuICAgIG1lc3NhZ2U6ICdzdWNjZXNzZnVsbHkgdGFrZW4gY2FyZSBvZiBnb29nbGVDYWxlbmRhcnlTeW5jIScsXG4gICAgc3RhdHVzOiAyMDAsXG4gIH07XG59O1xuIl19