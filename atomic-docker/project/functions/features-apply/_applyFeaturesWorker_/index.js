import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import { listEventsForUserGivenDates, listMeetingAssistAttendeesGivenMeetingId, listMeetingAssistEventsForAttendeeGivenDates, listMeetingAssistPreferredTimeRangesGivenMeetingId, listPreferredTimeRangesForEvent, listEventsForDate, convertMeetingAssistEventTypeToEventPlusType, processUserEventForCategoryDefaults, listCategoriesForEvent, processUserEventForCategoryDefaultsWithUserModifiedCategories, getEventFromPrimaryKey, processUserEventWithFoundPreviousEvent, processUserEventWithFoundPreviousEventWithUserModifiedCategories, getUserPreferences, processEventWithFoundPreviousEventWithoutCategories, listFutureMeetingAssists, meetingAttendeeCountGivenMeetingId, getMeetingAssist, generateNewMeetingEventForAttendee, createBufferTimeForNewMeetingEvent, createRemindersFromMinutesAndEvent, getGlobalCalendar, searchTrainingDataByVector, // updated
getEventVectorById, // updated
deleteTrainingDataById, // updated
addTrainingData, // added
 } from '@features_apply/_libs/api-helper';
// Remove redundant import of ReturnValueForEachMeetingAssistType if it's covered by the main import
// import { ReturnValueForEachMeetingAssistType } from '@features_apply/_libs/types';
import { processEventsForOptaPlanner } from '@features_apply/_libs/optaplanner/api-helper';
import { kafkaFeaturesApplyGroupId, kafkaFeaturesApplyTopic, } from '../_libs/constants';
import { Kafka, logLevel } from 'kafkajs';
dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);
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
const processEventsForPlanning = async (mainHostId, internalAttendees, meetingEventPlus, // events with a meetingId
newMeetingEventPlus, // generated events
newMeetingAssists, totalEvents, oldEvents, windowStartDate, windowEndDate, hostTimezone, externalAttendees, meetingAssistEvents) => {
    try {
        const events = _.cloneDeep(totalEvents);
        const userModifiedEvents = [];
        for (const event of events) {
            const preferredTimeRangesResponse = await listPreferredTimeRangesForEvent(event?.id);
            if (!preferredTimeRangesResponse.ok) {
                // Decide: throw, or log and continue with empty preferredTimeRanges?
                // For now, logging and continuing as preferredTimeRanges might not be critical for all events.
                console.warn(`Failed to get preferred time ranges for event ${event?.id}: ${preferredTimeRangesResponse.error?.message}`);
                userModifiedEvents.push(event); // Add event without preferredTimeRanges
            }
            else {
                const preferredTimeRanges = preferredTimeRangesResponse.data || [];
                userModifiedEvents.push({
                    ...event,
                    preferredTimeRanges: preferredTimeRanges,
                });
            }
        }
        const newHostReminders = [];
        const newHostBufferTimes = [];
        const newHostMeetingEventsPlus = [];
        for (const newMeetingAssist of newMeetingAssists) {
            let newHostMeetingEventPlus = newMeetingEventPlus
                ?.filter((me) => me?.meetingId === newMeetingAssist?.id)
                ?.find((me) => me?.userId === newMeetingAssist?.userId);
            let newBufferTimeForMeetingEventOrEmptyObject = {};
            let newModifiedReminderOrNull = null;
            if (newHostMeetingEventPlus?.id) {
                newModifiedReminderOrNull = newMeetingAssist?.reminders?.[0]
                    ? createRemindersFromMinutesAndEvent(newHostMeetingEventPlus.id, newMeetingAssist.reminders, newMeetingAssist.timezone, newMeetingAssist.useDefaultAlarms, newMeetingAssist.userId)
                    : null;
            }
            if (newModifiedReminderOrNull?.reminders?.[0]?.userId) {
                newHostReminders.push(newModifiedReminderOrNull);
            }
            const valuesToReturn = newMeetingAssist?.bufferTime?.afterEvent > 0 ||
                newMeetingAssist?.bufferTime?.beforeEvent > 0
                ? createBufferTimeForNewMeetingEvent(newHostMeetingEventPlus, newMeetingAssist.bufferTime)
                : null;
            if (valuesToReturn?.beforeEvent?.id) {
                newBufferTimeForMeetingEventOrEmptyObject.beforeEvent =
                    valuesToReturn.beforeEvent;
                newHostMeetingEventPlus = valuesToReturn.newEvent;
            }
            if (valuesToReturn?.afterEvent?.id) {
                newBufferTimeForMeetingEventOrEmptyObject.afterEvent =
                    valuesToReturn.afterEvent;
                newHostMeetingEventPlus = valuesToReturn.newEvent;
            }
            if (newBufferTimeForMeetingEventOrEmptyObject?.afterEvent?.id ||
                newBufferTimeForMeetingEventOrEmptyObject?.beforeEvent?.id) {
                newHostBufferTimes.push(newBufferTimeForMeetingEventOrEmptyObject);
            }
            if (newHostMeetingEventPlus?.preEventId ||
                newHostMeetingEventPlus?.postEventId) {
                newHostMeetingEventsPlus.push(newHostMeetingEventPlus);
            }
        }
        const newMeetingEventPlusRemovedHostEvents = _.differenceBy(newMeetingEventPlus, newHostMeetingEventsPlus, 'id');
        const newMeetingEventPlusModifiedHostEvents = newMeetingEventPlusRemovedHostEvents.concat(newHostMeetingEventsPlus);
        return processEventsForOptaPlanner(mainHostId, internalAttendees, meetingEventPlus, newMeetingEventPlusModifiedHostEvents, userModifiedEvents, windowStartDate, windowEndDate, hostTimezone, oldEvents, externalAttendees, meetingAssistEvents, newHostReminders?.length > 0 ? newHostReminders : [], newHostBufferTimes?.length > 0 ? newHostBufferTimes : []);
    }
    catch (e) {
        console.log(e, ' unable to process events for planning');
    }
};
const processEachMeetingAssist = async (windowStartDate, windowEndDate, hostTimezone, meetingId, meetingEvent, listedEvents) => {
    // This return type might need to become FeaturesApplyResponse as well if we want to propagate errors from it
    try {
        const attendeesResponse = await listMeetingAssistAttendeesGivenMeetingId(meetingId);
        if (!attendeesResponse.ok)
            throw new Error(`Failed to list attendees for meeting ${meetingId}: ${attendeesResponse.error?.message}`);
        const attendees = attendeesResponse.data || [];
        const externalAttendees = attendees.filter((a) => !!a?.externalAttendee);
        const internalAttendees = attendees.filter((a) => !a?.externalAttendee);
        const meetingAssistEvents = [];
        const events = [];
        const meetingEvents = [meetingEvent]; // Start with the initial meeting event
        if (externalAttendees.length > 0) {
            for (const attendee of externalAttendees) {
                const extEventsResponse = await listMeetingAssistEventsForAttendeeGivenDates(attendee.id, windowStartDate, windowEndDate, attendee.timezone, hostTimezone);
                if (!extEventsResponse.ok) {
                    console.warn(`Failed to list meeting assist events for external attendee ${attendee.id}: ${extEventsResponse.error?.message}`);
                    continue; // Skip this attendee or handle error more strictly
                }
                const newMeetingAssistEvents = extEventsResponse.data || [];
                const meetingAssistEventForMeeting = newMeetingAssistEvents.find((m) => m?.meetingId === meetingId);
                const filteredMeetingAssistEvents = newMeetingAssistEvents.filter((e) => e?.meetingId !== meetingId);
                if (filteredMeetingAssistEvents.length > 0)
                    meetingAssistEvents.push(...filteredMeetingAssistEvents);
                if (meetingAssistEventForMeeting?.id)
                    meetingEvents.push(convertMeetingAssistEventTypeToEventPlusType(meetingAssistEventForMeeting, attendee.userId));
            }
        }
        for (const attendee of internalAttendees) {
            const internalEventsResponse = await listEventsForUserGivenDates(attendee.userId, windowStartDate, windowEndDate, attendee.timezone, hostTimezone);
            if (!internalEventsResponse.ok) {
                console.warn(`Failed to list events for internal attendee ${attendee.userId}: ${internalEventsResponse.error?.message}`);
                continue; // Skip this attendee
            }
            const newEvents = internalEventsResponse.data || [];
            const meetingEventForCurrentAttendee = newEvents.find((e) => e?.meetingId === meetingId);
            const filteredNewEvents = newEvents.filter((e) => e?.meetingId !== meetingId);
            if (filteredNewEvents.length > 0)
                events.push(...filteredNewEvents);
            if (meetingEventForCurrentAttendee?.id)
                meetingEvents.push(meetingEventForCurrentAttendee);
        }
        const preferredTimesRangesResponse = await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);
        if (!preferredTimesRangesResponse.ok) {
            console.warn(`Failed to list preferred time ranges for meeting ${meetingId}: ${preferredTimesRangesResponse.error?.message}`);
        }
        const preferredTimesRanges = preferredTimesRangesResponse.ok && preferredTimesRangesResponse.data
            ? preferredTimesRangesResponse.data
            : [];
        const newUserModifiedMeetingEvents = meetingEvents.map((me) => ({
            ...me,
            preferredTimeRanges: preferredTimesRanges,
        }));
        const userModifiedEvents = [];
        for (const event of events) {
            const eventPreferredTimeRangesResponse = await listPreferredTimeRangesForEvent(event?.id);
            if (!eventPreferredTimeRangesResponse.ok) {
                console.warn(`Failed to list preferred time ranges for event ${event.id}: ${eventPreferredTimeRangesResponse.error?.message}`);
                userModifiedEvents.push(event); // Add with empty or no preferred time ranges
                continue;
            }
            const eventPreferredTimeRanges = eventPreferredTimeRangesResponse.ok &&
                eventPreferredTimeRangesResponse.data
                ? eventPreferredTimeRangesResponse.data
                : [];
            userModifiedEvents.push({
                ...event,
                preferredTimeRanges: eventPreferredTimeRanges,
            });
        }
        const filteredEvents = userModifiedEvents
            .map((e) => {
            const foundIndex = listedEvents?.findIndex((l) => l?.id === e?.id);
            if (foundIndex > -1) {
                return null;
            }
            return e;
        })
            ?.filter((e) => e !== null);
        return {
            events: filteredEvents,
            meetingAssistEvents,
            meetingEventsPlus: newUserModifiedMeetingEvents,
            internalAttendees,
            externalAttendees,
        };
    }
    catch (e) {
        console.log(e, ' unable to process each meeting assist');
    }
};
function getRandomInt(min, max) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min) + min); // The maximum is exclusive and the minimum is inclusive
}
const processEachFutureMeetingAssist = async (windowStartDate, windowEndDate, meetingId, listedEvents) => {
    try {
        const meetingAssistResponse = await getMeetingAssist(meetingId);
        if (!meetingAssistResponse.ok || !meetingAssistResponse.data)
            throw new Error(`Failed to get meeting assist ${meetingId}: ${meetingAssistResponse.error?.message}`);
        const meetingAssist = meetingAssistResponse.data;
        const preferredTimesRangesResponse = await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);
        if (!preferredTimesRangesResponse.ok)
            throw new Error(`Failed to list preferred time ranges for meeting ${meetingId}: ${preferredTimesRangesResponse.error?.message}`);
        const preferredTimesRanges = preferredTimesRangesResponse.data || [];
        const attendeesResponse = await listMeetingAssistAttendeesGivenMeetingId(meetingId);
        if (!attendeesResponse.ok)
            throw new Error(`Failed to list attendees for meeting ${meetingId}: ${attendeesResponse.error?.message}`);
        const attendees = attendeesResponse.data || [];
        const hostTimezone = meetingAssist?.timezone;
        if (!hostTimezone)
            throw new Error('Host timezone is missing from meeting assist data.');
        const newMeetingEvents = [];
        for (const attendee of attendees) {
            let calendarId = null;
            if (!attendee?.externalAttendee) {
                const globalCalendarResponse = await getGlobalCalendar(attendee?.userId);
                if (!globalCalendarResponse.ok) {
                    console.warn(`Failed to get global calendar for attendee ${attendee.userId}: ${globalCalendarResponse.error?.message}`);
                }
                calendarId =
                    globalCalendarResponse.ok && globalCalendarResponse.data
                        ? globalCalendarResponse.data.id
                        : null;
            }
            const newMeetingEvent = generateNewMeetingEventForAttendee(attendee, meetingAssist, windowStartDate, windowEndDate, hostTimezone, calendarId, preferredTimesRanges?.[getRandomInt(0, preferredTimesRanges.length)]);
            newMeetingEvents.push({ ...newMeetingEvent, preferredTimeRanges });
        }
        const externalAttendees = attendees.filter((a) => !!a?.externalAttendee);
        const internalAttendees = attendees.filter((a) => !a?.externalAttendee);
        const meetingAssistEvents = [];
        const events = [];
        if (externalAttendees.length > 0) {
            for (const attendee of externalAttendees) {
                const extEventsResponse = await listMeetingAssistEventsForAttendeeGivenDates(attendee.id, windowStartDate, windowEndDate, attendee.timezone, hostTimezone);
                if (!extEventsResponse.ok) {
                    console.warn(`Failed to list meeting assist events for external attendee ${attendee.id}: ${extEventsResponse.error?.message}`);
                    continue;
                }
                const newExtMeetingAssistEvents = extEventsResponse.data || [];
                if (newExtMeetingAssistEvents.length > 0)
                    meetingAssistEvents.push(...newExtMeetingAssistEvents);
            }
        }
        for (const attendee of internalAttendees) {
            const internalEventsResponse = await listEventsForUserGivenDates(attendee.userId, windowStartDate, windowEndDate, attendee.timezone, hostTimezone);
            if (!internalEventsResponse.ok) {
                console.warn(`Failed to list events for internal attendee ${attendee.userId}: ${internalEventsResponse.error?.message}`);
                continue;
            }
            const newInternalEvents = internalEventsResponse.data || [];
            if (newInternalEvents.length > 0)
                events.push(...newInternalEvents);
        }
        const filteredEvents = events
            ?.map((e) => {
            const foundIndex = listedEvents?.findIndex((l) => l?.id === e?.id);
            if (foundIndex > -1) {
                return null;
            }
            return e;
        })
            ?.filter((e) => e !== null);
        return {
            events: filteredEvents,
            meetingAssistEvents,
            newMeetingEventPlus: newMeetingEvents,
            internalAttendees,
            externalAttendees,
        };
    }
    catch (e) {
        console.log(e, ' unable to process each future meeting assist');
    }
};
const processApplyFeatures = async (body) => {
    try {
        const hostId = body?.userId;
        const windowStartDate = body?.windowStartDate;
        const windowEndDate = body?.windowEndDate;
        const hostTimezone = body?.timezone;
        const events = await listEventsForDate(hostId, windowStartDate, windowEndDate, hostTimezone);
        const eventsWithoutMeetingAssist = events?.filter((e) => !e?.meetingId);
        const userModifiedEvents = [];
        const newModifiedReminders = [];
        const newModifiedBufferTimes = [];
        for (const event of eventsWithoutMeetingAssist) {
            const preferredTimeRangesForEvent = await listPreferredTimeRangesForEvent(event?.id);
            if (preferredTimeRangesForEvent?.length > 0) {
                event.preferredTimeRanges = preferredTimeRangesForEvent;
            }
            // 1. get event
            const { userId } = event;
            const vector = await getEventVectorById(event?.id); // Use new function
            console.log(vector, ' vector');
            // 2. find closest event
            const trainingResult = await searchTrainingDataByVector(userId, vector); // Use new function
            console.log(trainingResult, ' trainingResult from LanceDB');
            // validate results
            if (!trainingResult?.id && !event?.userModifiedCategories) {
                console.log('no trainingResult found and no user modified categories');
                // no previous event found use CategoryDefaults
                const { newEvent, newReminders, newBufferTimes } = await processUserEventForCategoryDefaults(event, vector);
                console.log(newEvent, ' newEvent for processUserEventForCategoryDefaults');
                console.log(newReminders, ' newReminders for processUserEventForCategoryDefaults');
                userModifiedEvents.push(newEvent);
                if (newReminders) {
                    newModifiedReminders.push({
                        eventId: newEvent?.id,
                        reminders: newReminders,
                    });
                }
                if (newBufferTimes) {
                    newModifiedBufferTimes.push(newBufferTimes);
                }
                // Add current event to training data as no similar past event was found
                const newTrainingEntry = {
                    id: event.id,
                    userId: event.userId,
                    vector: vector,
                    source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
                    created_at: dayjs().toISOString(),
                };
                await addTrainingData(newTrainingEntry);
            }
            else if (!trainingResult?.id && event?.userModifiedCategories) {
                console.log('no trainingResult found but event has user modified categories');
                // no previous event found use user modified categories and category defaults
                const categories = await listCategoriesForEvent(event?.id);
                console.log(categories, ' categories');
                if (categories?.[0]?.id) {
                    const { newEvent, newReminders, newBufferTimes } = await processUserEventForCategoryDefaultsWithUserModifiedCategories(event, vector);
                    console.log(newEvent, ' newEvent for processUserEventForCategoryDefaultsWithUserModifiedCategories');
                    console.log(newReminders, ' newReminders for processUserEventForCategoryDefaultsWithUserModifiedCategories');
                    userModifiedEvents.push(newEvent);
                    if (newReminders) {
                        newModifiedReminders.push({
                            eventId: newEvent?.id,
                            reminders: newReminders,
                        });
                    }
                    if (newBufferTimes) {
                        newModifiedBufferTimes.push(newBufferTimes);
                    }
                }
                else {
                    // Add current event to training data as no similar past event was found and no categories to guide defaults
                    const newTrainingEntry = {
                        id: event.id,
                        userId: event.userId,
                        vector: vector,
                        source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
                        created_at: dayjs().toISOString(),
                    };
                    await addTrainingData(newTrainingEntry);
                    event.vector = vector; // ensure vector is part of the event if pushed directly
                    userModifiedEvents.push(event);
                }
            }
            else if (trainingResult?.id && !event?.userModifiedCategories) {
                // previous event found (via trainingResult) use previous event to copy over values
                const previousEventIdFromTraining = trainingResult.id; // This ID is from the training data, assumed to be the googleEventId of a previous similar event.
                const previousEvent = await getEventFromPrimaryKey(previousEventIdFromTraining);
                if (previousEvent?.id) {
                    const preferredTimeRanges = await listPreferredTimeRangesForEvent(previousEventIdFromTraining);
                    previousEvent.preferredTimeRanges = preferredTimeRanges;
                }
                if (!previousEvent) {
                    console.log(previousEventIdFromTraining, 'trainingResult.id inside !previousEvent && !event?.userModifiedCategories. This means the linked event was deleted.');
                    await deleteTrainingDataById(trainingResult.id); // Delete stale training entry
                    // Fallback to category defaults as the "similar" event is gone
                    const { newEvent, newReminders, newBufferTimes } = await processUserEventForCategoryDefaults(event, vector);
                    userModifiedEvents.push(newEvent);
                    if (newReminders) {
                        newModifiedReminders.push({
                            eventId: newEvent?.id,
                            reminders: newReminders,
                        });
                    }
                    if (newBufferTimes) {
                        newModifiedBufferTimes.push(newBufferTimes);
                    }
                    // Add current event to training data as the previously similar one was stale
                    const newTrainingEntry = {
                        id: event.id,
                        userId: event.userId,
                        vector: vector,
                        source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
                        created_at: dayjs().toISOString(),
                    };
                    await addTrainingData(newTrainingEntry);
                }
                else {
                    const { newEvent, newReminders, newBufferTimes } = await processUserEventWithFoundPreviousEvent(event, previousEventIdFromTraining);
                    userModifiedEvents.push(newEvent);
                    if (newReminders) {
                        newModifiedReminders.push({
                            eventId: newEvent?.id,
                            reminders: newReminders,
                        });
                    }
                    if (newBufferTimes) {
                        newModifiedBufferTimes.push(newBufferTimes);
                    }
                }
            }
            else if (trainingResult?.id && event?.userModifiedCategories) {
                const previousEventIdFromTraining = trainingResult.id;
                const previousEvent = await getEventFromPrimaryKey(previousEventIdFromTraining);
                if (previousEvent?.id) {
                    const preferredTimeRanges = await listPreferredTimeRangesForEvent(previousEventIdFromTraining);
                    previousEvent.preferredTimeRanges = preferredTimeRanges;
                }
                if (!previousEvent) {
                    console.log(previousEventIdFromTraining, 'trainingResult.id inside !previousEvent && event?.userModifiedCategories. This means the linked event was deleted.');
                    await deleteTrainingDataById(trainingResult.id); // Delete stale training entry
                    // Fallback to user modified categories as the "similar" event is gone
                    const categories = await listCategoriesForEvent(event?.id);
                    if (categories?.[0]?.id) {
                        const { newEvent, newReminders, newBufferTimes } = await processUserEventForCategoryDefaultsWithUserModifiedCategories(event, vector);
                        userModifiedEvents.push(newEvent);
                        if (newReminders) {
                            newModifiedReminders.push({
                                eventId: newEvent?.id,
                                reminders: newReminders,
                            });
                        }
                        if (newBufferTimes) {
                            newModifiedBufferTimes.push(newBufferTimes);
                        }
                    }
                    else {
                        // Add current event to training data as the previously similar one was stale and no categories to guide
                        const newTrainingEntry = {
                            id: event.id,
                            userId: event.userId,
                            vector: vector,
                            source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
                            created_at: dayjs().toISOString(),
                        };
                        await addTrainingData(newTrainingEntry);
                        event.vector = vector; // ensure vector is part of the event
                        userModifiedEvents.push(event);
                    }
                }
                else {
                    const categories = await listCategoriesForEvent(event?.id);
                    if (categories?.[0]?.id) {
                        const { newEvent, newReminders, newBufferTimes } = await processUserEventWithFoundPreviousEventWithUserModifiedCategories(event, previousEventIdFromTraining);
                        userModifiedEvents.push(newEvent);
                        if (newReminders) {
                            newModifiedReminders.push({
                                eventId: newEvent?.id,
                                reminders: newReminders,
                            });
                        }
                        if (newBufferTimes) {
                            newModifiedBufferTimes.push(newBufferTimes);
                        }
                    }
                    else {
                        // No categories, but a previous event was found.
                        const userPreferences = await getUserPreferences(userId);
                        const { newModifiedEvent: newModifiedEvent1, newReminders: newReminders1, newBufferTimes: newTimeBlocking1, } = await processEventWithFoundPreviousEventWithoutCategories(previousEvent, event, userPreferences, userId);
                        userModifiedEvents.push(newModifiedEvent1);
                        if (newReminders1) {
                            newModifiedReminders.push({
                                eventId: newModifiedEvent1?.id,
                                reminders: newReminders1,
                            });
                        }
                        if (newTimeBlocking1) {
                            newModifiedBufferTimes.push(newTimeBlocking1);
                        }
                    }
                }
            }
        }
        userModifiedEvents.forEach((e) => console.log(e, ' userModifiedEvent before processing for Optaplanner'));
        newModifiedReminders.forEach((e) => console.log(e, ' newModifiedReminders before processing for Optaplanner'));
        const eventsWithMeetingId = events.filter((e) => !!e?.meetingId);
        const meetingAssistEvents = [];
        const meetingEventPlus = [];
        const internalAttendees = [];
        const externalAttendees = [];
        const filteredEvents = [];
        /**
         * queue for each
         * parentKey: hostId/singletonId
         * oldChildKey: hostId/meetingId
         */
        filteredEvents.push(...userModifiedEvents);
        filteredEvents.push(...eventsWithMeetingId);
        for (const eventWithMeetingId of eventsWithMeetingId) {
            const returnValuesForEachMeeting = await processEachMeetingAssist(windowStartDate, windowEndDate, hostTimezone, eventWithMeetingId?.meetingId, eventWithMeetingId, events);
            if (returnValuesForEachMeeting?.events?.length > 0) {
                const newEvents = returnValuesForEachMeeting?.events;
                filteredEvents.push(...newEvents);
                events.push(...newEvents);
            }
            if (returnValuesForEachMeeting?.meetingAssistEvents?.length > 0) {
                meetingAssistEvents.push(...returnValuesForEachMeeting?.meetingAssistEvents);
            }
            if (returnValuesForEachMeeting?.meetingEventsPlus) {
                meetingEventPlus.push(...returnValuesForEachMeeting?.meetingEventsPlus);
            }
            if (returnValuesForEachMeeting?.internalAttendees) {
                internalAttendees.push(...returnValuesForEachMeeting?.internalAttendees);
            }
            if (returnValuesForEachMeeting?.externalAttendees) {
                externalAttendees.push(...returnValuesForEachMeeting?.externalAttendees);
            }
        }
        // future meeting assists
        const meetingIdsToNotInclude = eventsWithMeetingId.map((e) => e?.meetingId);
        console.log(meetingIdsToNotInclude, ' meetingIdsToNotInclude');
        const newMeetingAssistsNoThreshold = await listFutureMeetingAssists(hostId, dayjs(windowStartDate.slice(0, 19)).tz(hostTimezone).format(), dayjs(windowEndDate.slice(0, 19)).tz(hostTimezone).add(1, 'd').format(), meetingIdsToNotInclude);
        console.log(newMeetingAssistsNoThreshold, ' newMeetingAssistsNoThreshold');
        const newMeetingEventPlus = [];
        const newMeetingAssistsActive = [];
        for (const futureMeetingAssist of newMeetingAssistsNoThreshold) {
            const count = await meetingAttendeeCountGivenMeetingId(futureMeetingAssist?.id);
            if (count >= futureMeetingAssist?.minThresholdCount) {
                newMeetingAssistsActive.push(futureMeetingAssist);
            }
        }
        /**
         * queue for each
         * parentKey: hostId/singletonId
         * newChildKey: hostId/meetingId
         */
        for (const futureMeetingAssistActive of newMeetingAssistsActive) {
            const returnValuesFromFutureMeetingAssist = await processEachFutureMeetingAssist(windowStartDate, windowEndDate, futureMeetingAssistActive?.id, events);
            if (returnValuesFromFutureMeetingAssist?.events?.length > 0) {
                const newEvents = returnValuesFromFutureMeetingAssist?.events;
                filteredEvents.push(...newEvents);
                events.push(...newEvents);
            }
            if (returnValuesFromFutureMeetingAssist?.meetingAssistEvents?.length > 0) {
                meetingAssistEvents.push(...returnValuesFromFutureMeetingAssist?.meetingAssistEvents);
            }
            if (returnValuesFromFutureMeetingAssist?.newMeetingEventPlus?.length > 0) {
                newMeetingEventPlus.push(...returnValuesFromFutureMeetingAssist?.newMeetingEventPlus);
            }
            if (returnValuesFromFutureMeetingAssist?.internalAttendees) {
                internalAttendees.push(...returnValuesFromFutureMeetingAssist?.internalAttendees);
            }
            if (returnValuesFromFutureMeetingAssist?.externalAttendees) {
                externalAttendees.push(...returnValuesFromFutureMeetingAssist?.externalAttendees);
            }
        }
        return processEventsForPlanning(hostId, _.uniqWith(internalAttendees, _.isEqual), meetingEventPlus, newMeetingEventPlus, newMeetingAssistsActive, _.uniqWith(filteredEvents, _.isEqual), events, windowStartDate, windowEndDate, hostTimezone, _.uniqWith(externalAttendees, _.isEqual), meetingAssistEvents?.length > 0
            ? _.uniqWith(meetingAssistEvents, _.isEqual)
            : null);
    }
    catch (e) {
        console.log(e, ' unable to process meeting assist');
    }
};
const processQueueMessage = async (body) => {
    try {
        const userId = body?.userId;
        const windowStartDate = body?.windowStartDate;
        const windowEndDate = body?.windowEndDate;
        const timezone = body?.timezone;
        // Centralized validation for the message body itself
        if (!userId || !windowStartDate || !windowEndDate || !timezone) {
            const missingParams = [
                !userId && 'userId',
                !windowStartDate && 'windowStartDate',
                !windowEndDate && 'windowEndDate',
                !timezone && 'timezone',
            ]
                .filter(Boolean)
                .join(', ');
            const error = new Error(`Invalid message payload: Missing ${missingParams}`);
            // @ts-ignore // Add custom property for structured logging/handling if needed
            error.code = 'MESSAGE_VALIDATION_ERROR';
            throw error;
        }
        return await processApplyFeatures(body); // Propagate result or error
    }
    catch (e) {
        // Catch errors from processApplyFeatures or validation
        console.error(`Error in processQueueMessage for userId ${body?.userId}: ${e.message}`, e);
        // Re-throw the error to be caught by the Kafka consumer's eachMessage
        throw e;
    }
};
const scheduleMeetingWorker = async () => {
    try {
        const consumer = kafka.consumer({ groupId: kafkaFeaturesApplyGroupId });
        await consumer.connect();
        await consumer.subscribe({ topic: kafkaFeaturesApplyTopic });
        await consumer.run({
            eachMessage: async ({ topic, partition, message }) => {
                console.log({
                    key: message?.key?.toString(),
                    value: message?.value?.toString(),
                    headers: message?.headers,
                });
                let messagePayload = null;
                try {
                    if (!message?.value) {
                        // This error is about Kafka message integrity, not business logic validation
                        throw new Error('Kafka message value is null or undefined.');
                    }
                    messagePayload = JSON.parse(message.value.toString());
                    console.log(messagePayload, ' messagePayload');
                    await processQueueMessage(messagePayload);
                }
                catch (e) {
                    console.error(`Failed to process Kafka message from topic ${topic}, partition ${partition}: ${e.message}`, {
                        messageKey: message?.key?.toString(),
                        errorMessage: e.message,
                        errorCode: e.code,
                        errorStack: e.stack,
                        originalPayload: message?.value?.toString(),
                    });
                    // Re-throw the error to utilize Kafka's retry/DLQ mechanisms if configured.
                    throw e;
                }
            },
        });
    }
    catch (e) {
        console.error('Kafka consumer error in scheduleMeetingWorker:', e);
        // This error is likely a connection or subscription issue with Kafka itself.
        throw e; // Re-throw to make the worker crash and restart if managed by PM2/Kubernetes
    }
};
export default scheduleMeetingWorker;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEtBQUssTUFBTSxPQUFPLENBQUM7QUFDMUIsT0FBTyxPQUFPLE1BQU0sc0JBQXNCLENBQUM7QUFDM0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxTQUFTLE1BQU0sd0JBQXdCLENBQUM7QUFDL0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxHQUFHLE1BQU0sa0JBQWtCLENBQUM7QUFFbkMsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBQ3ZCLE9BQU8sRUFDTCwyQkFBMkIsRUFDM0Isd0NBQXdDLEVBQ3hDLDRDQUE0QyxFQUM1QyxrREFBa0QsRUFDbEQsK0JBQStCLEVBQy9CLGlCQUFpQixFQUNqQiw0Q0FBNEMsRUFDNUMsbUNBQW1DLEVBQ25DLHNCQUFzQixFQUN0Qiw2REFBNkQsRUFDN0Qsc0JBQXNCLEVBQ3RCLHNDQUFzQyxFQUN0QyxnRUFBZ0UsRUFDaEUsa0JBQWtCLEVBQ2xCLG1EQUFtRCxFQUNuRCx3QkFBd0IsRUFDeEIsa0NBQWtDLEVBQ2xDLGdCQUFnQixFQUNoQixrQ0FBa0MsRUFDbEMsa0NBQWtDLEVBQ2xDLGtDQUFrQyxFQUNsQyxpQkFBaUIsRUFDakIsMEJBQTBCLEVBQUUsVUFBVTtBQUN0QyxrQkFBa0IsRUFBRSxVQUFVO0FBQzlCLHNCQUFzQixFQUFFLFVBQVU7QUFDbEMsZUFBZSxFQUFFLFFBQVE7RUFDMUIsTUFBTSxrQ0FBa0MsQ0FBQztBQWlCMUMsb0dBQW9HO0FBQ3BHLHFGQUFxRjtBQUVyRixPQUFPLEVBQUUsMkJBQTJCLEVBQUUsTUFBTSw4Q0FBOEMsQ0FBQztBQUUzRixPQUFPLEVBQ0wseUJBQXlCLEVBQ3pCLHVCQUF1QixHQUN4QixNQUFNLG9CQUFvQixDQUFDO0FBQzVCLE9BQU8sRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLE1BQU0sU0FBUyxDQUFDO0FBSTFDLEtBQUssQ0FBQyxNQUFNLENBQUMsT0FBTyxDQUFDLENBQUM7QUFDdEIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsQ0FBQztBQUN2QixLQUFLLENBQUMsTUFBTSxDQUFDLFNBQVMsQ0FBQyxDQUFDO0FBQ3hCLEtBQUssQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLENBQUM7QUFDdkIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQztBQUVsQixNQUFNLEtBQUssR0FBRyxJQUFJLEtBQUssQ0FBQztJQUN0QixRQUFRLEVBQUUsUUFBUSxDQUFDLEtBQUs7SUFDeEIsT0FBTyxFQUFFLENBQUMsY0FBYyxDQUFDO0lBQ3pCLFFBQVEsRUFBRSxRQUFRO0lBQ2xCLGFBQWE7SUFDYixJQUFJLEVBQUU7UUFDSixTQUFTLEVBQUUsT0FBTyxFQUFFLGlDQUFpQztRQUNyRCxRQUFRLEVBQUUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxjQUFjO1FBQ3BDLFFBQVEsRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWM7S0FDckM7Q0FDRixDQUFDLENBQUM7QUFFSCxNQUFNLHdCQUF3QixHQUFHLEtBQUssRUFDcEMsVUFBa0IsRUFDbEIsaUJBQThDLEVBQzlDLGdCQUF3QyxFQUFFLDBCQUEwQjtBQUNwRSxtQkFBMkMsRUFBRSxtQkFBbUI7QUFDaEUsaUJBQXNDLEVBQ3RDLFdBQXdCLEVBQ3hCLFNBQXNCLEVBQ3RCLGVBQXVCLEVBQ3ZCLGFBQXFCLEVBQ3JCLFlBQW9CLEVBQ3BCLGlCQUErQyxFQUMvQyxtQkFBOEMsRUFDOUMsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sTUFBTSxHQUFvQixDQUFDLENBQUMsU0FBUyxDQUFDLFdBQVcsQ0FBQyxDQUFDO1FBQ3pELE1BQU0sa0JBQWtCLEdBQW9CLEVBQUUsQ0FBQztRQUUvQyxLQUFLLE1BQU0sS0FBSyxJQUFJLE1BQU0sRUFBRSxDQUFDO1lBQzNCLE1BQU0sMkJBQTJCLEdBQUcsTUFBTSwrQkFBK0IsQ0FDdkUsS0FBSyxFQUFFLEVBQUUsQ0FDVixDQUFDO1lBQ0YsSUFBSSxDQUFDLDJCQUEyQixDQUFDLEVBQUUsRUFBRSxDQUFDO2dCQUNwQyxxRUFBcUU7Z0JBQ3JFLCtGQUErRjtnQkFDL0YsT0FBTyxDQUFDLElBQUksQ0FDVixpREFBaUQsS0FBSyxFQUFFLEVBQUUsS0FBSywyQkFBMkIsQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQzVHLENBQUM7Z0JBQ0Ysa0JBQWtCLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDLENBQUMsd0NBQXdDO1lBQzFFLENBQUM7aUJBQU0sQ0FBQztnQkFDTixNQUFNLG1CQUFtQixHQUFHLDJCQUEyQixDQUFDLElBQUksSUFBSSxFQUFFLENBQUM7Z0JBQ25FLGtCQUFrQixDQUFDLElBQUksQ0FBQztvQkFDdEIsR0FBRyxLQUFLO29CQUNSLG1CQUFtQixFQUFFLG1CQUFtQjtpQkFDekMsQ0FBQyxDQUFDO1lBQ0wsQ0FBQztRQUNILENBQUM7UUFFRCxNQUFNLGdCQUFnQixHQUE0QixFQUFFLENBQUM7UUFDckQsTUFBTSxrQkFBa0IsR0FBMkIsRUFBRSxDQUFDO1FBQ3RELE1BQU0sd0JBQXdCLEdBQTJCLEVBQUUsQ0FBQztRQUU1RCxLQUFLLE1BQU0sZ0JBQWdCLElBQUksaUJBQWlCLEVBQUUsQ0FBQztZQUNqRCxJQUFJLHVCQUF1QixHQUFHLG1CQUFtQjtnQkFDL0MsRUFBRSxNQUFNLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRSxDQUFDLEVBQUUsRUFBRSxTQUFTLEtBQUssZ0JBQWdCLEVBQUUsRUFBRSxDQUFDO2dCQUN4RCxFQUFFLElBQUksQ0FBQyxDQUFDLEVBQUUsRUFBRSxFQUFFLENBQUMsRUFBRSxFQUFFLE1BQU0sS0FBSyxnQkFBZ0IsRUFBRSxNQUFNLENBQUMsQ0FBQztZQUMxRCxJQUFJLHlDQUF5QyxHQUF5QixFQUFFLENBQUM7WUFDekUsSUFBSSx5QkFBeUIsR0FBaUMsSUFBSSxDQUFDO1lBRW5FLElBQUksdUJBQXVCLEVBQUUsRUFBRSxFQUFFLENBQUM7Z0JBQ2hDLHlCQUF5QixHQUFHLGdCQUFnQixFQUFFLFNBQVMsRUFBRSxDQUFDLENBQUMsQ0FBQztvQkFDMUQsQ0FBQyxDQUFDLGtDQUFrQyxDQUNoQyx1QkFBdUIsQ0FBQyxFQUFFLEVBQzFCLGdCQUFnQixDQUFDLFNBQVMsRUFDMUIsZ0JBQWdCLENBQUMsUUFBUSxFQUN6QixnQkFBZ0IsQ0FBQyxnQkFBZ0IsRUFDakMsZ0JBQWdCLENBQUMsTUFBTSxDQUN4QjtvQkFDSCxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQ1gsQ0FBQztZQUVELElBQUkseUJBQXlCLEVBQUUsU0FBUyxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsTUFBTSxFQUFFLENBQUM7Z0JBQ3RELGdCQUFnQixDQUFDLElBQUksQ0FBQyx5QkFBeUIsQ0FBQyxDQUFDO1lBQ25ELENBQUM7WUFFRCxNQUFNLGNBQWMsR0FDbEIsZ0JBQWdCLEVBQUUsVUFBVSxFQUFFLFVBQVUsR0FBRyxDQUFDO2dCQUM1QyxnQkFBZ0IsRUFBRSxVQUFVLEVBQUUsV0FBVyxHQUFHLENBQUM7Z0JBQzNDLENBQUMsQ0FBQyxrQ0FBa0MsQ0FDaEMsdUJBQXVCLEVBQ3ZCLGdCQUFnQixDQUFDLFVBQVUsQ0FDNUI7Z0JBQ0gsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUVYLElBQUksY0FBYyxFQUFFLFdBQVcsRUFBRSxFQUFFLEVBQUUsQ0FBQztnQkFDcEMseUNBQXlDLENBQUMsV0FBVztvQkFDbkQsY0FBYyxDQUFDLFdBQVcsQ0FBQztnQkFDN0IsdUJBQXVCLEdBQUcsY0FBYyxDQUFDLFFBQVEsQ0FBQztZQUNwRCxDQUFDO1lBRUQsSUFBSSxjQUFjLEVBQUUsVUFBVSxFQUFFLEVBQUUsRUFBRSxDQUFDO2dCQUNuQyx5Q0FBeUMsQ0FBQyxVQUFVO29CQUNsRCxjQUFjLENBQUMsVUFBVSxDQUFDO2dCQUM1Qix1QkFBdUIsR0FBRyxjQUFjLENBQUMsUUFBUSxDQUFDO1lBQ3BELENBQUM7WUFFRCxJQUNFLHlDQUF5QyxFQUFFLFVBQVUsRUFBRSxFQUFFO2dCQUN6RCx5Q0FBeUMsRUFBRSxXQUFXLEVBQUUsRUFBRSxFQUMxRCxDQUFDO2dCQUNELGtCQUFrQixDQUFDLElBQUksQ0FBQyx5Q0FBeUMsQ0FBQyxDQUFDO1lBQ3JFLENBQUM7WUFFRCxJQUNFLHVCQUF1QixFQUFFLFVBQVU7Z0JBQ25DLHVCQUF1QixFQUFFLFdBQVcsRUFDcEMsQ0FBQztnQkFDRCx3QkFBd0IsQ0FBQyxJQUFJLENBQUMsdUJBQXVCLENBQUMsQ0FBQztZQUN6RCxDQUFDO1FBQ0gsQ0FBQztRQUVELE1BQU0sb0NBQW9DLEdBQUcsQ0FBQyxDQUFDLFlBQVksQ0FDekQsbUJBQW1CLEVBQ25CLHdCQUF3QixFQUN4QixJQUFJLENBQ0wsQ0FBQztRQUNGLE1BQU0scUNBQXFDLEdBQ3pDLG9DQUFvQyxDQUFDLE1BQU0sQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDO1FBRXhFLE9BQU8sMkJBQTJCLENBQ2hDLFVBQVUsRUFDVixpQkFBaUIsRUFDakIsZ0JBQWdCLEVBQ2hCLHFDQUFxQyxFQUNyQyxrQkFBa0IsRUFDbEIsZUFBZSxFQUNmLGFBQWEsRUFDYixZQUFZLEVBQ1osU0FBUyxFQUNULGlCQUFpQixFQUNqQixtQkFBbUIsRUFDbkIsZ0JBQWdCLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUMsZ0JBQWdCLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFDcEQsa0JBQWtCLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUMsa0JBQWtCLENBQUMsQ0FBQyxDQUFDLEVBQUUsQ0FDekQsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsd0NBQXdDLENBQUMsQ0FBQztJQUMzRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsTUFBTSx3QkFBd0IsR0FBRyxLQUFLLEVBQ3BDLGVBQXVCLEVBQ3ZCLGFBQXFCLEVBQ3JCLFlBQW9CLEVBQ3BCLFNBQWlCLEVBQ2pCLFlBQXVCLEVBQ3ZCLFlBQTZCLEVBQ2lCLEVBQUU7SUFDaEQsNkdBQTZHO0lBQzdHLElBQUksQ0FBQztRQUNILE1BQU0saUJBQWlCLEdBQ3JCLE1BQU0sd0NBQXdDLENBQUMsU0FBUyxDQUFDLENBQUM7UUFDNUQsSUFBSSxDQUFDLGlCQUFpQixDQUFDLEVBQUU7WUFDdkIsTUFBTSxJQUFJLEtBQUssQ0FDYix3Q0FBd0MsU0FBUyxLQUFLLGlCQUFpQixDQUFDLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FDekYsQ0FBQztRQUNKLE1BQU0sU0FBUyxHQUFHLGlCQUFpQixDQUFDLElBQUksSUFBSSxFQUFFLENBQUM7UUFFL0MsTUFBTSxpQkFBaUIsR0FBRyxTQUFTLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQyxFQUFFLGdCQUFnQixDQUFDLENBQUM7UUFDekUsTUFBTSxpQkFBaUIsR0FBRyxTQUFTLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxnQkFBZ0IsQ0FBQyxDQUFDO1FBRXhFLE1BQU0sbUJBQW1CLEdBQTZCLEVBQUUsQ0FBQztRQUN6RCxNQUFNLE1BQU0sR0FBZ0IsRUFBRSxDQUFDO1FBQy9CLE1BQU0sYUFBYSxHQUFnQixDQUFDLFlBQVksQ0FBQyxDQUFDLENBQUMsdUNBQXVDO1FBRTFGLElBQUksaUJBQWlCLENBQUMsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ2pDLEtBQUssTUFBTSxRQUFRLElBQUksaUJBQWlCLEVBQUUsQ0FBQztnQkFDekMsTUFBTSxpQkFBaUIsR0FDckIsTUFBTSw0Q0FBNEMsQ0FDaEQsUUFBUSxDQUFDLEVBQUUsRUFDWCxlQUFlLEVBQ2YsYUFBYSxFQUNiLFFBQVEsQ0FBQyxRQUFRLEVBQ2pCLFlBQVksQ0FDYixDQUFDO2dCQUNKLElBQUksQ0FBQyxpQkFBaUIsQ0FBQyxFQUFFLEVBQUUsQ0FBQztvQkFDMUIsT0FBTyxDQUFDLElBQUksQ0FDViw4REFBOEQsUUFBUSxDQUFDLEVBQUUsS0FBSyxpQkFBaUIsQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQ2pILENBQUM7b0JBQ0YsU0FBUyxDQUFDLG1EQUFtRDtnQkFDL0QsQ0FBQztnQkFDRCxNQUFNLHNCQUFzQixHQUFHLGlCQUFpQixDQUFDLElBQUksSUFBSSxFQUFFLENBQUM7Z0JBQzVELE1BQU0sNEJBQTRCLEdBQUcsc0JBQXNCLENBQUMsSUFBSSxDQUM5RCxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLFNBQVMsS0FBSyxTQUFTLENBQ2xDLENBQUM7Z0JBQ0YsTUFBTSwyQkFBMkIsR0FBRyxzQkFBc0IsQ0FBQyxNQUFNLENBQy9ELENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsU0FBUyxLQUFLLFNBQVMsQ0FDbEMsQ0FBQztnQkFFRixJQUFJLDJCQUEyQixDQUFDLE1BQU0sR0FBRyxDQUFDO29CQUN4QyxtQkFBbUIsQ0FBQyxJQUFJLENBQUMsR0FBRywyQkFBMkIsQ0FBQyxDQUFDO2dCQUMzRCxJQUFJLDRCQUE0QixFQUFFLEVBQUU7b0JBQ2xDLGFBQWEsQ0FBQyxJQUFJLENBQ2hCLDRDQUE0QyxDQUMxQyw0QkFBNEIsRUFDNUIsUUFBUSxDQUFDLE1BQU0sQ0FDaEIsQ0FDRixDQUFDO1lBQ04sQ0FBQztRQUNILENBQUM7UUFFRCxLQUFLLE1BQU0sUUFBUSxJQUFJLGlCQUFpQixFQUFFLENBQUM7WUFDekMsTUFBTSxzQkFBc0IsR0FBRyxNQUFNLDJCQUEyQixDQUM5RCxRQUFRLENBQUMsTUFBTSxFQUNmLGVBQWUsRUFDZixhQUFhLEVBQ2IsUUFBUSxDQUFDLFFBQVEsRUFDakIsWUFBWSxDQUNiLENBQUM7WUFDRixJQUFJLENBQUMsc0JBQXNCLENBQUMsRUFBRSxFQUFFLENBQUM7Z0JBQy9CLE9BQU8sQ0FBQyxJQUFJLENBQ1YsK0NBQStDLFFBQVEsQ0FBQyxNQUFNLEtBQUssc0JBQXNCLENBQUMsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUMzRyxDQUFDO2dCQUNGLFNBQVMsQ0FBQyxxQkFBcUI7WUFDakMsQ0FBQztZQUNELE1BQU0sU0FBUyxHQUFHLHNCQUFzQixDQUFDLElBQUksSUFBSSxFQUFFLENBQUM7WUFDcEQsTUFBTSw4QkFBOEIsR0FBRyxTQUFTLENBQUMsSUFBSSxDQUNuRCxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLFNBQVMsS0FBSyxTQUFTLENBQ2xDLENBQUM7WUFDRixNQUFNLGlCQUFpQixHQUFHLFNBQVMsQ0FBQyxNQUFNLENBQ3hDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsU0FBUyxLQUFLLFNBQVMsQ0FDbEMsQ0FBQztZQUVGLElBQUksaUJBQWlCLENBQUMsTUFBTSxHQUFHLENBQUM7Z0JBQUUsTUFBTSxDQUFDLElBQUksQ0FBQyxHQUFHLGlCQUFpQixDQUFDLENBQUM7WUFDcEUsSUFBSSw4QkFBOEIsRUFBRSxFQUFFO2dCQUNwQyxhQUFhLENBQUMsSUFBSSxDQUFDLDhCQUE4QixDQUFDLENBQUM7UUFDdkQsQ0FBQztRQUVELE1BQU0sNEJBQTRCLEdBQ2hDLE1BQU0sa0RBQWtELENBQUMsU0FBUyxDQUFDLENBQUM7UUFDdEUsSUFBSSxDQUFDLDRCQUE0QixDQUFDLEVBQUUsRUFBRSxDQUFDO1lBQ3JDLE9BQU8sQ0FBQyxJQUFJLENBQ1Ysb0RBQW9ELFNBQVMsS0FBSyw0QkFBNEIsQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQ2hILENBQUM7UUFDSixDQUFDO1FBQ0QsTUFBTSxvQkFBb0IsR0FDeEIsNEJBQTRCLENBQUMsRUFBRSxJQUFJLDRCQUE0QixDQUFDLElBQUk7WUFDbEUsQ0FBQyxDQUFDLDRCQUE0QixDQUFDLElBQUk7WUFDbkMsQ0FBQyxDQUFDLEVBQUUsQ0FBQztRQUVULE1BQU0sNEJBQTRCLEdBQ2hDLGFBQWEsQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDekIsR0FBRyxFQUFFO1lBQ0wsbUJBQW1CLEVBQUUsb0JBQW9CO1NBQzFDLENBQUMsQ0FBQyxDQUFDO1FBRU4sTUFBTSxrQkFBa0IsR0FBb0IsRUFBRSxDQUFDO1FBQy9DLEtBQUssTUFBTSxLQUFLLElBQUksTUFBTSxFQUFFLENBQUM7WUFDM0IsTUFBTSxnQ0FBZ0MsR0FDcEMsTUFBTSwrQkFBK0IsQ0FBQyxLQUFLLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDbkQsSUFBSSxDQUFDLGdDQUFnQyxDQUFDLEVBQUUsRUFBRSxDQUFDO2dCQUN6QyxPQUFPLENBQUMsSUFBSSxDQUNWLGtEQUFrRCxLQUFLLENBQUMsRUFBRSxLQUFLLGdDQUFnQyxDQUFDLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FDakgsQ0FBQztnQkFDRixrQkFBa0IsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUMsQ0FBQyw2Q0FBNkM7Z0JBQzdFLFNBQVM7WUFDWCxDQUFDO1lBQ0QsTUFBTSx3QkFBd0IsR0FDNUIsZ0NBQWdDLENBQUMsRUFBRTtnQkFDbkMsZ0NBQWdDLENBQUMsSUFBSTtnQkFDbkMsQ0FBQyxDQUFDLGdDQUFnQyxDQUFDLElBQUk7Z0JBQ3ZDLENBQUMsQ0FBQyxFQUFFLENBQUM7WUFDVCxrQkFBa0IsQ0FBQyxJQUFJLENBQUM7Z0JBQ3RCLEdBQUcsS0FBSztnQkFDUixtQkFBbUIsRUFBRSx3QkFBd0I7YUFDOUMsQ0FBQyxDQUFDO1FBQ0wsQ0FBQztRQUVELE1BQU0sY0FBYyxHQUFHLGtCQUFrQjthQUN0QyxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRTtZQUNULE1BQU0sVUFBVSxHQUFHLFlBQVksRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxFQUFFLEtBQUssQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1lBQ25FLElBQUksVUFBVSxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7Z0JBQ3BCLE9BQU8sSUFBSSxDQUFDO1lBQ2QsQ0FBQztZQUNELE9BQU8sQ0FBQyxDQUFDO1FBQ1gsQ0FBQyxDQUFDO1lBQ0YsRUFBRSxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxJQUFJLENBQUMsQ0FBQztRQUU5QixPQUFPO1lBQ0wsTUFBTSxFQUFFLGNBQWM7WUFDdEIsbUJBQW1CO1lBQ25CLGlCQUFpQixFQUFFLDRCQUE0QjtZQUMvQyxpQkFBaUI7WUFDakIsaUJBQWlCO1NBQ2xCLENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHdDQUF3QyxDQUFDLENBQUM7SUFDM0QsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLFNBQVMsWUFBWSxDQUFDLEdBQUcsRUFBRSxHQUFHO0lBQzVCLEdBQUcsR0FBRyxJQUFJLENBQUMsSUFBSSxDQUFDLEdBQUcsQ0FBQyxDQUFDO0lBQ3JCLEdBQUcsR0FBRyxJQUFJLENBQUMsS0FBSyxDQUFDLEdBQUcsQ0FBQyxDQUFDO0lBQ3RCLE9BQU8sSUFBSSxDQUFDLEtBQUssQ0FBQyxJQUFJLENBQUMsTUFBTSxFQUFFLEdBQUcsQ0FBQyxHQUFHLEdBQUcsR0FBRyxDQUFDLEdBQUcsR0FBRyxDQUFDLENBQUMsQ0FBQyx3REFBd0Q7QUFDaEgsQ0FBQztBQUVELE1BQU0sOEJBQThCLEdBQUcsS0FBSyxFQUMxQyxlQUF1QixFQUN2QixhQUFxQixFQUNyQixTQUFpQixFQUNqQixZQUF5QixFQUMyQixFQUFFO0lBQ3RELElBQUksQ0FBQztRQUNILE1BQU0scUJBQXFCLEdBQUcsTUFBTSxnQkFBZ0IsQ0FBQyxTQUFTLENBQUMsQ0FBQztRQUNoRSxJQUFJLENBQUMscUJBQXFCLENBQUMsRUFBRSxJQUFJLENBQUMscUJBQXFCLENBQUMsSUFBSTtZQUMxRCxNQUFNLElBQUksS0FBSyxDQUNiLGdDQUFnQyxTQUFTLEtBQUsscUJBQXFCLENBQUMsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUNyRixDQUFDO1FBQ0osTUFBTSxhQUFhLEdBQUcscUJBQXFCLENBQUMsSUFBSSxDQUFDO1FBRWpELE1BQU0sNEJBQTRCLEdBQ2hDLE1BQU0sa0RBQWtELENBQUMsU0FBUyxDQUFDLENBQUM7UUFDdEUsSUFBSSxDQUFDLDRCQUE0QixDQUFDLEVBQUU7WUFDbEMsTUFBTSxJQUFJLEtBQUssQ0FDYixvREFBb0QsU0FBUyxLQUFLLDRCQUE0QixDQUFDLEtBQUssRUFBRSxPQUFPLEVBQUUsQ0FDaEgsQ0FBQztRQUNKLE1BQU0sb0JBQW9CLEdBQUcsNEJBQTRCLENBQUMsSUFBSSxJQUFJLEVBQUUsQ0FBQztRQUVyRSxNQUFNLGlCQUFpQixHQUNyQixNQUFNLHdDQUF3QyxDQUFDLFNBQVMsQ0FBQyxDQUFDO1FBQzVELElBQUksQ0FBQyxpQkFBaUIsQ0FBQyxFQUFFO1lBQ3ZCLE1BQU0sSUFBSSxLQUFLLENBQ2Isd0NBQXdDLFNBQVMsS0FBSyxpQkFBaUIsQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQ3pGLENBQUM7UUFDSixNQUFNLFNBQVMsR0FBRyxpQkFBaUIsQ0FBQyxJQUFJLElBQUksRUFBRSxDQUFDO1FBRS9DLE1BQU0sWUFBWSxHQUFHLGFBQWEsRUFBRSxRQUFRLENBQUM7UUFDN0MsSUFBSSxDQUFDLFlBQVk7WUFDZixNQUFNLElBQUksS0FBSyxDQUFDLG9EQUFvRCxDQUFDLENBQUM7UUFFeEUsTUFBTSxnQkFBZ0IsR0FBMkIsRUFBRSxDQUFDO1FBQ3BELEtBQUssTUFBTSxRQUFRLElBQUksU0FBUyxFQUFFLENBQUM7WUFDakMsSUFBSSxVQUFVLEdBQWtCLElBQUksQ0FBQztZQUNyQyxJQUFJLENBQUMsUUFBUSxFQUFFLGdCQUFnQixFQUFFLENBQUM7Z0JBQ2hDLE1BQU0sc0JBQXNCLEdBQUcsTUFBTSxpQkFBaUIsQ0FDcEQsUUFBUSxFQUFFLE1BQU0sQ0FDakIsQ0FBQztnQkFDRixJQUFJLENBQUMsc0JBQXNCLENBQUMsRUFBRSxFQUFFLENBQUM7b0JBQy9CLE9BQU8sQ0FBQyxJQUFJLENBQ1YsOENBQThDLFFBQVEsQ0FBQyxNQUFNLEtBQUssc0JBQXNCLENBQUMsS0FBSyxFQUFFLE9BQU8sRUFBRSxDQUMxRyxDQUFDO2dCQUNKLENBQUM7Z0JBQ0QsVUFBVTtvQkFDUixzQkFBc0IsQ0FBQyxFQUFFLElBQUksc0JBQXNCLENBQUMsSUFBSTt3QkFDdEQsQ0FBQyxDQUFDLHNCQUFzQixDQUFDLElBQUksQ0FBQyxFQUFFO3dCQUNoQyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQ2IsQ0FBQztZQUNELE1BQU0sZUFBZSxHQUFHLGtDQUFrQyxDQUN4RCxRQUFRLEVBQ1IsYUFBYSxFQUNiLGVBQWUsRUFDZixhQUFhLEVBQ2IsWUFBWSxFQUNaLFVBQVUsRUFDVixvQkFBb0IsRUFBRSxDQUFDLFlBQVksQ0FBQyxDQUFDLEVBQUUsb0JBQW9CLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FDckUsQ0FBQztZQUNGLGdCQUFnQixDQUFDLElBQUksQ0FBQyxFQUFFLEdBQUcsZUFBZSxFQUFFLG1CQUFtQixFQUFFLENBQUMsQ0FBQztRQUNyRSxDQUFDO1FBRUQsTUFBTSxpQkFBaUIsR0FBRyxTQUFTLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQyxFQUFFLGdCQUFnQixDQUFDLENBQUM7UUFDekUsTUFBTSxpQkFBaUIsR0FBRyxTQUFTLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxnQkFBZ0IsQ0FBQyxDQUFDO1FBQ3hFLE1BQU0sbUJBQW1CLEdBQTZCLEVBQUUsQ0FBQztRQUN6RCxNQUFNLE1BQU0sR0FBZ0IsRUFBRSxDQUFDO1FBRS9CLElBQUksaUJBQWlCLENBQUMsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ2pDLEtBQUssTUFBTSxRQUFRLElBQUksaUJBQWlCLEVBQUUsQ0FBQztnQkFDekMsTUFBTSxpQkFBaUIsR0FDckIsTUFBTSw0Q0FBNEMsQ0FDaEQsUUFBUSxDQUFDLEVBQUUsRUFDWCxlQUFlLEVBQ2YsYUFBYSxFQUNiLFFBQVEsQ0FBQyxRQUFRLEVBQ2pCLFlBQVksQ0FDYixDQUFDO2dCQUNKLElBQUksQ0FBQyxpQkFBaUIsQ0FBQyxFQUFFLEVBQUUsQ0FBQztvQkFDMUIsT0FBTyxDQUFDLElBQUksQ0FDViw4REFBOEQsUUFBUSxDQUFDLEVBQUUsS0FBSyxpQkFBaUIsQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQ2pILENBQUM7b0JBQ0YsU0FBUztnQkFDWCxDQUFDO2dCQUNELE1BQU0seUJBQXlCLEdBQUcsaUJBQWlCLENBQUMsSUFBSSxJQUFJLEVBQUUsQ0FBQztnQkFDL0QsSUFBSSx5QkFBeUIsQ0FBQyxNQUFNLEdBQUcsQ0FBQztvQkFDdEMsbUJBQW1CLENBQUMsSUFBSSxDQUFDLEdBQUcseUJBQXlCLENBQUMsQ0FBQztZQUMzRCxDQUFDO1FBQ0gsQ0FBQztRQUVELEtBQUssTUFBTSxRQUFRLElBQUksaUJBQWlCLEVBQUUsQ0FBQztZQUN6QyxNQUFNLHNCQUFzQixHQUFHLE1BQU0sMkJBQTJCLENBQzlELFFBQVEsQ0FBQyxNQUFNLEVBQ2YsZUFBZSxFQUNmLGFBQWEsRUFDYixRQUFRLENBQUMsUUFBUSxFQUNqQixZQUFZLENBQ2IsQ0FBQztZQUNGLElBQUksQ0FBQyxzQkFBc0IsQ0FBQyxFQUFFLEVBQUUsQ0FBQztnQkFDL0IsT0FBTyxDQUFDLElBQUksQ0FDViwrQ0FBK0MsUUFBUSxDQUFDLE1BQU0sS0FBSyxzQkFBc0IsQ0FBQyxLQUFLLEVBQUUsT0FBTyxFQUFFLENBQzNHLENBQUM7Z0JBQ0YsU0FBUztZQUNYLENBQUM7WUFDRCxNQUFNLGlCQUFpQixHQUFHLHNCQUFzQixDQUFDLElBQUksSUFBSSxFQUFFLENBQUM7WUFDNUQsSUFBSSxpQkFBaUIsQ0FBQyxNQUFNLEdBQUcsQ0FBQztnQkFBRSxNQUFNLENBQUMsSUFBSSxDQUFDLEdBQUcsaUJBQWlCLENBQUMsQ0FBQztRQUN0RSxDQUFDO1FBRUQsTUFBTSxjQUFjLEdBQUcsTUFBTTtZQUMzQixFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFO1lBQ1YsTUFBTSxVQUFVLEdBQUcsWUFBWSxFQUFFLFNBQVMsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEVBQUUsS0FBSyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDbkUsSUFBSSxVQUFVLEdBQUcsQ0FBQyxDQUFDLEVBQUUsQ0FBQztnQkFDcEIsT0FBTyxJQUFJLENBQUM7WUFDZCxDQUFDO1lBQ0QsT0FBTyxDQUFDLENBQUM7UUFDWCxDQUFDLENBQUM7WUFDRixFQUFFLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLElBQUksQ0FBQyxDQUFDO1FBRTlCLE9BQU87WUFDTCxNQUFNLEVBQUUsY0FBYztZQUN0QixtQkFBbUI7WUFDbkIsbUJBQW1CLEVBQUUsZ0JBQWdCO1lBQ3JDLGlCQUFpQjtZQUNqQixpQkFBaUI7U0FDbEIsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsK0NBQStDLENBQUMsQ0FBQztJQUNsRSxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsTUFBTSxvQkFBb0IsR0FBRyxLQUFLLEVBQ2hDLElBQTRDLEVBQzVDLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLE1BQU0sR0FBRyxJQUFJLEVBQUUsTUFBTSxDQUFDO1FBQzVCLE1BQU0sZUFBZSxHQUFHLElBQUksRUFBRSxlQUFlLENBQUM7UUFDOUMsTUFBTSxhQUFhLEdBQUcsSUFBSSxFQUFFLGFBQWEsQ0FBQztRQUMxQyxNQUFNLFlBQVksR0FBRyxJQUFJLEVBQUUsUUFBUSxDQUFDO1FBRXBDLE1BQU0sTUFBTSxHQUFvQixNQUFNLGlCQUFpQixDQUNyRCxNQUFNLEVBQ04sZUFBZSxFQUNmLGFBQWEsRUFDYixZQUFZLENBQ2IsQ0FBQztRQUNGLE1BQU0sMEJBQTBCLEdBQW9CLE1BQU0sRUFBRSxNQUFNLENBQ2hFLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxTQUFTLENBQ3JCLENBQUM7UUFFRixNQUFNLGtCQUFrQixHQUFvQixFQUFFLENBQUM7UUFDL0MsTUFBTSxvQkFBb0IsR0FBNEIsRUFBRSxDQUFDO1FBQ3pELE1BQU0sc0JBQXNCLEdBQTJCLEVBQUUsQ0FBQztRQUUxRCxLQUFLLE1BQU0sS0FBSyxJQUFJLDBCQUEwQixFQUFFLENBQUM7WUFDL0MsTUFBTSwyQkFBMkIsR0FBRyxNQUFNLCtCQUErQixDQUN2RSxLQUFLLEVBQUUsRUFBRSxDQUNWLENBQUM7WUFFRixJQUFJLDJCQUEyQixFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztnQkFDNUMsS0FBSyxDQUFDLG1CQUFtQixHQUFHLDJCQUEyQixDQUFDO1lBQzFELENBQUM7WUFFRCxlQUFlO1lBQ2YsTUFBTSxFQUFFLE1BQU0sRUFBRSxHQUFHLEtBQUssQ0FBQztZQUN6QixNQUFNLE1BQU0sR0FBRyxNQUFNLGtCQUFrQixDQUFDLEtBQUssRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLG1CQUFtQjtZQUN2RSxPQUFPLENBQUMsR0FBRyxDQUFDLE1BQU0sRUFBRSxTQUFTLENBQUMsQ0FBQztZQUUvQix3QkFBd0I7WUFDeEIsTUFBTSxjQUFjLEdBQUcsTUFBTSwwQkFBMEIsQ0FBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxtQkFBbUI7WUFDNUYsT0FBTyxDQUFDLEdBQUcsQ0FBQyxjQUFjLEVBQUUsOEJBQThCLENBQUMsQ0FBQztZQUU1RCxtQkFBbUI7WUFDbkIsSUFBSSxDQUFDLGNBQWMsRUFBRSxFQUFFLElBQUksQ0FBQyxLQUFLLEVBQUUsc0JBQXNCLEVBQUUsQ0FBQztnQkFDMUQsT0FBTyxDQUFDLEdBQUcsQ0FBQyx5REFBeUQsQ0FBQyxDQUFDO2dCQUN2RSwrQ0FBK0M7Z0JBQy9DLE1BQU0sRUFBRSxRQUFRLEVBQUUsWUFBWSxFQUFFLGNBQWMsRUFBRSxHQUM5QyxNQUFNLG1DQUFtQyxDQUFDLEtBQUssRUFBRSxNQUFNLENBQUMsQ0FBQztnQkFDM0QsT0FBTyxDQUFDLEdBQUcsQ0FDVCxRQUFRLEVBQ1IsbURBQW1ELENBQ3BELENBQUM7Z0JBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FDVCxZQUFZLEVBQ1osdURBQXVELENBQ3hELENBQUM7Z0JBQ0Ysa0JBQWtCLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxDQUFDO2dCQUNsQyxJQUFJLFlBQVksRUFBRSxDQUFDO29CQUNqQixvQkFBb0IsQ0FBQyxJQUFJLENBQUM7d0JBQ3hCLE9BQU8sRUFBRSxRQUFRLEVBQUUsRUFBRTt3QkFDckIsU0FBUyxFQUFFLFlBQVk7cUJBQ3hCLENBQUMsQ0FBQztnQkFDTCxDQUFDO2dCQUNELElBQUksY0FBYyxFQUFFLENBQUM7b0JBQ25CLHNCQUFzQixDQUFDLElBQUksQ0FBQyxjQUFjLENBQUMsQ0FBQztnQkFDOUMsQ0FBQztnQkFDRCx3RUFBd0U7Z0JBQ3hFLE1BQU0sZ0JBQWdCLEdBQXdCO29CQUM1QyxFQUFFLEVBQUUsS0FBSyxDQUFDLEVBQUU7b0JBQ1osTUFBTSxFQUFFLEtBQUssQ0FBQyxNQUFNO29CQUNwQixNQUFNLEVBQUUsTUFBTTtvQkFDZCxpQkFBaUIsRUFBRSxHQUFHLEtBQUssQ0FBQyxLQUFLLElBQUksS0FBSyxDQUFDLE9BQU8sSUFBSSxLQUFLLENBQUMsS0FBSyxJQUFJLEVBQUUsRUFBRTtvQkFDekUsVUFBVSxFQUFFLEtBQUssRUFBRSxDQUFDLFdBQVcsRUFBRTtpQkFDbEMsQ0FBQztnQkFDRixNQUFNLGVBQWUsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQzFDLENBQUM7aUJBQU0sSUFBSSxDQUFDLGNBQWMsRUFBRSxFQUFFLElBQUksS0FBSyxFQUFFLHNCQUFzQixFQUFFLENBQUM7Z0JBQ2hFLE9BQU8sQ0FBQyxHQUFHLENBQ1QsZ0VBQWdFLENBQ2pFLENBQUM7Z0JBQ0YsNkVBQTZFO2dCQUM3RSxNQUFNLFVBQVUsR0FBbUIsTUFBTSxzQkFBc0IsQ0FDN0QsS0FBSyxFQUFFLEVBQUUsQ0FDVixDQUFDO2dCQUNGLE9BQU8sQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFLGFBQWEsQ0FBQyxDQUFDO2dCQUN2QyxJQUFJLFVBQVUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRSxDQUFDO29CQUN4QixNQUFNLEVBQUUsUUFBUSxFQUFFLFlBQVksRUFBRSxjQUFjLEVBQUUsR0FDOUMsTUFBTSw2REFBNkQsQ0FDakUsS0FBSyxFQUNMLE1BQU0sQ0FDUCxDQUFDO29CQUNKLE9BQU8sQ0FBQyxHQUFHLENBQ1QsUUFBUSxFQUNSLDZFQUE2RSxDQUM5RSxDQUFDO29CQUNGLE9BQU8sQ0FBQyxHQUFHLENBQ1QsWUFBWSxFQUNaLGlGQUFpRixDQUNsRixDQUFDO29CQUNGLGtCQUFrQixDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztvQkFDbEMsSUFBSSxZQUFZLEVBQUUsQ0FBQzt3QkFDakIsb0JBQW9CLENBQUMsSUFBSSxDQUFDOzRCQUN4QixPQUFPLEVBQUUsUUFBUSxFQUFFLEVBQUU7NEJBQ3JCLFNBQVMsRUFBRSxZQUFZO3lCQUN4QixDQUFDLENBQUM7b0JBQ0wsQ0FBQztvQkFDRCxJQUFJLGNBQWMsRUFBRSxDQUFDO3dCQUNuQixzQkFBc0IsQ0FBQyxJQUFJLENBQUMsY0FBYyxDQUFDLENBQUM7b0JBQzlDLENBQUM7Z0JBQ0gsQ0FBQztxQkFBTSxDQUFDO29CQUNOLDRHQUE0RztvQkFDNUcsTUFBTSxnQkFBZ0IsR0FBd0I7d0JBQzVDLEVBQUUsRUFBRSxLQUFLLENBQUMsRUFBRTt3QkFDWixNQUFNLEVBQUUsS0FBSyxDQUFDLE1BQU07d0JBQ3BCLE1BQU0sRUFBRSxNQUFNO3dCQUNkLGlCQUFpQixFQUFFLEdBQUcsS0FBSyxDQUFDLEtBQUssSUFBSSxLQUFLLENBQUMsT0FBTyxJQUFJLEtBQUssQ0FBQyxLQUFLLElBQUksRUFBRSxFQUFFO3dCQUN6RSxVQUFVLEVBQUUsS0FBSyxFQUFFLENBQUMsV0FBVyxFQUFFO3FCQUNsQyxDQUFDO29CQUNGLE1BQU0sZUFBZSxDQUFDLGdCQUFnQixDQUFDLENBQUM7b0JBQ3hDLEtBQUssQ0FBQyxNQUFNLEdBQUcsTUFBTSxDQUFDLENBQUMsd0RBQXdEO29CQUMvRSxrQkFBa0IsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7Z0JBQ2pDLENBQUM7WUFDSCxDQUFDO2lCQUFNLElBQUksY0FBYyxFQUFFLEVBQUUsSUFBSSxDQUFDLEtBQUssRUFBRSxzQkFBc0IsRUFBRSxDQUFDO2dCQUNoRSxtRkFBbUY7Z0JBQ25GLE1BQU0sMkJBQTJCLEdBQUcsY0FBYyxDQUFDLEVBQUUsQ0FBQyxDQUFDLGtHQUFrRztnQkFDekosTUFBTSxhQUFhLEdBQUcsTUFBTSxzQkFBc0IsQ0FDaEQsMkJBQTJCLENBQzVCLENBQUM7Z0JBRUYsSUFBSSxhQUFhLEVBQUUsRUFBRSxFQUFFLENBQUM7b0JBQ3RCLE1BQU0sbUJBQW1CLEdBQUcsTUFBTSwrQkFBK0IsQ0FDL0QsMkJBQTJCLENBQzVCLENBQUM7b0JBQ0YsYUFBYSxDQUFDLG1CQUFtQixHQUFHLG1CQUFtQixDQUFDO2dCQUMxRCxDQUFDO2dCQUVELElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQztvQkFDbkIsT0FBTyxDQUFDLEdBQUcsQ0FDVCwyQkFBMkIsRUFDM0IscUhBQXFILENBQ3RILENBQUM7b0JBQ0YsTUFBTSxzQkFBc0IsQ0FBQyxjQUFjLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQyw4QkFBOEI7b0JBQy9FLCtEQUErRDtvQkFDL0QsTUFBTSxFQUFFLFFBQVEsRUFBRSxZQUFZLEVBQUUsY0FBYyxFQUFFLEdBQzlDLE1BQU0sbUNBQW1DLENBQUMsS0FBSyxFQUFFLE1BQU0sQ0FBQyxDQUFDO29CQUMzRCxrQkFBa0IsQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLENBQUM7b0JBQ2xDLElBQUksWUFBWSxFQUFFLENBQUM7d0JBQ2pCLG9CQUFvQixDQUFDLElBQUksQ0FBQzs0QkFDeEIsT0FBTyxFQUFFLFFBQVEsRUFBRSxFQUFFOzRCQUNyQixTQUFTLEVBQUUsWUFBWTt5QkFDeEIsQ0FBQyxDQUFDO29CQUNMLENBQUM7b0JBQ0QsSUFBSSxjQUFjLEVBQUUsQ0FBQzt3QkFDbkIsc0JBQXNCLENBQUMsSUFBSSxDQUFDLGNBQWMsQ0FBQyxDQUFDO29CQUM5QyxDQUFDO29CQUNELDZFQUE2RTtvQkFDN0UsTUFBTSxnQkFBZ0IsR0FBd0I7d0JBQzVDLEVBQUUsRUFBRSxLQUFLLENBQUMsRUFBRTt3QkFDWixNQUFNLEVBQUUsS0FBSyxDQUFDLE1BQU07d0JBQ3BCLE1BQU0sRUFBRSxNQUFNO3dCQUNkLGlCQUFpQixFQUFFLEdBQUcsS0FBSyxDQUFDLEtBQUssSUFBSSxLQUFLLENBQUMsT0FBTyxJQUFJLEtBQUssQ0FBQyxLQUFLLElBQUksRUFBRSxFQUFFO3dCQUN6RSxVQUFVLEVBQUUsS0FBSyxFQUFFLENBQUMsV0FBVyxFQUFFO3FCQUNsQyxDQUFDO29CQUNGLE1BQU0sZUFBZSxDQUFDLGdCQUFnQixDQUFDLENBQUM7Z0JBQzFDLENBQUM7cUJBQU0sQ0FBQztvQkFDTixNQUFNLEVBQUUsUUFBUSxFQUFFLFlBQVksRUFBRSxjQUFjLEVBQUUsR0FDOUMsTUFBTSxzQ0FBc0MsQ0FDMUMsS0FBSyxFQUNMLDJCQUEyQixDQUM1QixDQUFDO29CQUNKLGtCQUFrQixDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztvQkFDbEMsSUFBSSxZQUFZLEVBQUUsQ0FBQzt3QkFDakIsb0JBQW9CLENBQUMsSUFBSSxDQUFDOzRCQUN4QixPQUFPLEVBQUUsUUFBUSxFQUFFLEVBQUU7NEJBQ3JCLFNBQVMsRUFBRSxZQUFZO3lCQUN4QixDQUFDLENBQUM7b0JBQ0wsQ0FBQztvQkFDRCxJQUFJLGNBQWMsRUFBRSxDQUFDO3dCQUNuQixzQkFBc0IsQ0FBQyxJQUFJLENBQUMsY0FBYyxDQUFDLENBQUM7b0JBQzlDLENBQUM7Z0JBQ0gsQ0FBQztZQUNILENBQUM7aUJBQU0sSUFBSSxjQUFjLEVBQUUsRUFBRSxJQUFJLEtBQUssRUFBRSxzQkFBc0IsRUFBRSxDQUFDO2dCQUMvRCxNQUFNLDJCQUEyQixHQUFHLGNBQWMsQ0FBQyxFQUFFLENBQUM7Z0JBQ3RELE1BQU0sYUFBYSxHQUFHLE1BQU0sc0JBQXNCLENBQ2hELDJCQUEyQixDQUM1QixDQUFDO2dCQUNGLElBQUksYUFBYSxFQUFFLEVBQUUsRUFBRSxDQUFDO29CQUN0QixNQUFNLG1CQUFtQixHQUFHLE1BQU0sK0JBQStCLENBQy9ELDJCQUEyQixDQUM1QixDQUFDO29CQUNGLGFBQWEsQ0FBQyxtQkFBbUIsR0FBRyxtQkFBbUIsQ0FBQztnQkFDMUQsQ0FBQztnQkFFRCxJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7b0JBQ25CLE9BQU8sQ0FBQyxHQUFHLENBQ1QsMkJBQTJCLEVBQzNCLG9IQUFvSCxDQUNySCxDQUFDO29CQUNGLE1BQU0sc0JBQXNCLENBQUMsY0FBYyxDQUFDLEVBQUUsQ0FBQyxDQUFDLENBQUMsOEJBQThCO29CQUMvRSxzRUFBc0U7b0JBQ3RFLE1BQU0sVUFBVSxHQUFtQixNQUFNLHNCQUFzQixDQUM3RCxLQUFLLEVBQUUsRUFBRSxDQUNWLENBQUM7b0JBQ0YsSUFBSSxVQUFVLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLEVBQUUsQ0FBQzt3QkFDeEIsTUFBTSxFQUFFLFFBQVEsRUFBRSxZQUFZLEVBQUUsY0FBYyxFQUFFLEdBQzlDLE1BQU0sNkRBQTZELENBQ2pFLEtBQUssRUFDTCxNQUFNLENBQ1AsQ0FBQzt3QkFDSixrQkFBa0IsQ0FBQyxJQUFJLENBQUMsUUFBUSxDQUFDLENBQUM7d0JBQ2xDLElBQUksWUFBWSxFQUFFLENBQUM7NEJBQ2pCLG9CQUFvQixDQUFDLElBQUksQ0FBQztnQ0FDeEIsT0FBTyxFQUFFLFFBQVEsRUFBRSxFQUFFO2dDQUNyQixTQUFTLEVBQUUsWUFBWTs2QkFDeEIsQ0FBQyxDQUFDO3dCQUNMLENBQUM7d0JBQ0QsSUFBSSxjQUFjLEVBQUUsQ0FBQzs0QkFDbkIsc0JBQXNCLENBQUMsSUFBSSxDQUFDLGNBQWMsQ0FBQyxDQUFDO3dCQUM5QyxDQUFDO29CQUNILENBQUM7eUJBQU0sQ0FBQzt3QkFDTix3R0FBd0c7d0JBQ3hHLE1BQU0sZ0JBQWdCLEdBQXdCOzRCQUM1QyxFQUFFLEVBQUUsS0FBSyxDQUFDLEVBQUU7NEJBQ1osTUFBTSxFQUFFLEtBQUssQ0FBQyxNQUFNOzRCQUNwQixNQUFNLEVBQUUsTUFBTTs0QkFDZCxpQkFBaUIsRUFBRSxHQUFHLEtBQUssQ0FBQyxLQUFLLElBQUksS0FBSyxDQUFDLE9BQU8sSUFBSSxLQUFLLENBQUMsS0FBSyxJQUFJLEVBQUUsRUFBRTs0QkFDekUsVUFBVSxFQUFFLEtBQUssRUFBRSxDQUFDLFdBQVcsRUFBRTt5QkFDbEMsQ0FBQzt3QkFDRixNQUFNLGVBQWUsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO3dCQUN4QyxLQUFLLENBQUMsTUFBTSxHQUFHLE1BQU0sQ0FBQyxDQUFDLHFDQUFxQzt3QkFDNUQsa0JBQWtCLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO29CQUNqQyxDQUFDO2dCQUNILENBQUM7cUJBQU0sQ0FBQztvQkFDTixNQUFNLFVBQVUsR0FBbUIsTUFBTSxzQkFBc0IsQ0FDN0QsS0FBSyxFQUFFLEVBQUUsQ0FDVixDQUFDO29CQUNGLElBQUksVUFBVSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxFQUFFLENBQUM7d0JBQ3hCLE1BQU0sRUFBRSxRQUFRLEVBQUUsWUFBWSxFQUFFLGNBQWMsRUFBRSxHQUM5QyxNQUFNLGdFQUFnRSxDQUNwRSxLQUFLLEVBQ0wsMkJBQTJCLENBQzVCLENBQUM7d0JBQ0osa0JBQWtCLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxDQUFDO3dCQUNsQyxJQUFJLFlBQVksRUFBRSxDQUFDOzRCQUNqQixvQkFBb0IsQ0FBQyxJQUFJLENBQUM7Z0NBQ3hCLE9BQU8sRUFBRSxRQUFRLEVBQUUsRUFBRTtnQ0FDckIsU0FBUyxFQUFFLFlBQVk7NkJBQ3hCLENBQUMsQ0FBQzt3QkFDTCxDQUFDO3dCQUNELElBQUksY0FBYyxFQUFFLENBQUM7NEJBQ25CLHNCQUFzQixDQUFDLElBQUksQ0FBQyxjQUFjLENBQUMsQ0FBQzt3QkFDOUMsQ0FBQztvQkFDSCxDQUFDO3lCQUFNLENBQUM7d0JBQ04saURBQWlEO3dCQUNqRCxNQUFNLGVBQWUsR0FBRyxNQUFNLGtCQUFrQixDQUFDLE1BQU0sQ0FBQyxDQUFDO3dCQUN6RCxNQUFNLEVBQ0osZ0JBQWdCLEVBQUUsaUJBQWlCLEVBQ25DLFlBQVksRUFBRSxhQUFhLEVBQzNCLGNBQWMsRUFBRSxnQkFBZ0IsR0FDakMsR0FBRyxNQUFNLG1EQUFtRCxDQUMzRCxhQUFhLEVBQ2IsS0FBSyxFQUNMLGVBQWUsRUFDZixNQUFNLENBQ1AsQ0FBQzt3QkFDRixrQkFBa0IsQ0FBQyxJQUFJLENBQUMsaUJBQWlCLENBQUMsQ0FBQzt3QkFDM0MsSUFBSSxhQUFhLEVBQUUsQ0FBQzs0QkFDbEIsb0JBQW9CLENBQUMsSUFBSSxDQUFDO2dDQUN4QixPQUFPLEVBQUUsaUJBQWlCLEVBQUUsRUFBRTtnQ0FDOUIsU0FBUyxFQUFFLGFBQWE7NkJBQ3pCLENBQUMsQ0FBQzt3QkFDTCxDQUFDO3dCQUNELElBQUksZ0JBQWdCLEVBQUUsQ0FBQzs0QkFDckIsc0JBQXNCLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7d0JBQ2hELENBQUM7b0JBQ0gsQ0FBQztnQkFDSCxDQUFDO1lBQ0gsQ0FBQztRQUNILENBQUM7UUFFRCxrQkFBa0IsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUMvQixPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxzREFBc0QsQ0FBQyxDQUN2RSxDQUFDO1FBQ0Ysb0JBQW9CLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FDakMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUseURBQXlELENBQUMsQ0FDMUUsQ0FBQztRQUVGLE1BQU0sbUJBQW1CLEdBQUcsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUMsRUFBRSxTQUFTLENBQUMsQ0FBQztRQUVqRSxNQUFNLG1CQUFtQixHQUE2QixFQUFFLENBQUM7UUFDekQsTUFBTSxnQkFBZ0IsR0FBMkIsRUFBRSxDQUFDO1FBQ3BELE1BQU0saUJBQWlCLEdBQWdDLEVBQUUsQ0FBQztRQUMxRCxNQUFNLGlCQUFpQixHQUFnQyxFQUFFLENBQUM7UUFDMUQsTUFBTSxjQUFjLEdBQWdCLEVBQUUsQ0FBQztRQUV2Qzs7OztXQUlHO1FBRUgsY0FBYyxDQUFDLElBQUksQ0FBQyxHQUFHLGtCQUFrQixDQUFDLENBQUM7UUFDM0MsY0FBYyxDQUFDLElBQUksQ0FBQyxHQUFHLG1CQUFtQixDQUFDLENBQUM7UUFFNUMsS0FBSyxNQUFNLGtCQUFrQixJQUFJLG1CQUFtQixFQUFFLENBQUM7WUFDckQsTUFBTSwwQkFBMEIsR0FBRyxNQUFNLHdCQUF3QixDQUMvRCxlQUFlLEVBQ2YsYUFBYSxFQUNiLFlBQVksRUFDWixrQkFBa0IsRUFBRSxTQUFTLEVBQzdCLGtCQUFrQixFQUNsQixNQUFNLENBQ1AsQ0FBQztZQUVGLElBQUksMEJBQTBCLEVBQUUsTUFBTSxFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztnQkFDbkQsTUFBTSxTQUFTLEdBQUcsMEJBQTBCLEVBQUUsTUFBTSxDQUFDO2dCQUVyRCxjQUFjLENBQUMsSUFBSSxDQUFDLEdBQUcsU0FBUyxDQUFDLENBQUM7Z0JBQ2xDLE1BQU0sQ0FBQyxJQUFJLENBQUMsR0FBRyxTQUFTLENBQUMsQ0FBQztZQUM1QixDQUFDO1lBRUQsSUFBSSwwQkFBMEIsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7Z0JBQ2hFLG1CQUFtQixDQUFDLElBQUksQ0FDdEIsR0FBRywwQkFBMEIsRUFBRSxtQkFBbUIsQ0FDbkQsQ0FBQztZQUNKLENBQUM7WUFFRCxJQUFJLDBCQUEwQixFQUFFLGlCQUFpQixFQUFFLENBQUM7Z0JBQ2xELGdCQUFnQixDQUFDLElBQUksQ0FBQyxHQUFHLDBCQUEwQixFQUFFLGlCQUFpQixDQUFDLENBQUM7WUFDMUUsQ0FBQztZQUVELElBQUksMEJBQTBCLEVBQUUsaUJBQWlCLEVBQUUsQ0FBQztnQkFDbEQsaUJBQWlCLENBQUMsSUFBSSxDQUNwQixHQUFHLDBCQUEwQixFQUFFLGlCQUFpQixDQUNqRCxDQUFDO1lBQ0osQ0FBQztZQUVELElBQUksMEJBQTBCLEVBQUUsaUJBQWlCLEVBQUUsQ0FBQztnQkFDbEQsaUJBQWlCLENBQUMsSUFBSSxDQUNwQixHQUFHLDBCQUEwQixFQUFFLGlCQUFpQixDQUNqRCxDQUFDO1lBQ0osQ0FBQztRQUNILENBQUM7UUFFRCx5QkFBeUI7UUFDekIsTUFBTSxzQkFBc0IsR0FBRyxtQkFBbUIsQ0FBQyxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxTQUFTLENBQUMsQ0FBQztRQUU1RSxPQUFPLENBQUMsR0FBRyxDQUFDLHNCQUFzQixFQUFFLHlCQUF5QixDQUFDLENBQUM7UUFFL0QsTUFBTSw0QkFBNEIsR0FBRyxNQUFNLHdCQUF3QixDQUNqRSxNQUFNLEVBQ04sS0FBSyxDQUFDLGVBQWUsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDLFlBQVksQ0FBQyxDQUFDLE1BQU0sRUFBRSxFQUM3RCxLQUFLLENBQUMsYUFBYSxDQUFDLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUMsWUFBWSxDQUFDLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQyxNQUFNLEVBQUUsRUFDdkUsc0JBQXNCLENBQ3ZCLENBQUM7UUFFRixPQUFPLENBQUMsR0FBRyxDQUFDLDRCQUE0QixFQUFFLCtCQUErQixDQUFDLENBQUM7UUFFM0UsTUFBTSxtQkFBbUIsR0FBMkIsRUFBRSxDQUFDO1FBQ3ZELE1BQU0sdUJBQXVCLEdBQXdCLEVBQUUsQ0FBQztRQUV4RCxLQUFLLE1BQU0sbUJBQW1CLElBQUksNEJBQTRCLEVBQUUsQ0FBQztZQUMvRCxNQUFNLEtBQUssR0FBRyxNQUFNLGtDQUFrQyxDQUNwRCxtQkFBbUIsRUFBRSxFQUFFLENBQ3hCLENBQUM7WUFFRixJQUFJLEtBQUssSUFBSSxtQkFBbUIsRUFBRSxpQkFBaUIsRUFBRSxDQUFDO2dCQUNwRCx1QkFBdUIsQ0FBQyxJQUFJLENBQUMsbUJBQW1CLENBQUMsQ0FBQztZQUNwRCxDQUFDO1FBQ0gsQ0FBQztRQUVEOzs7O1dBSUc7UUFDSCxLQUFLLE1BQU0seUJBQXlCLElBQUksdUJBQXVCLEVBQUUsQ0FBQztZQUNoRSxNQUFNLG1DQUFtQyxHQUN2QyxNQUFNLDhCQUE4QixDQUNsQyxlQUFlLEVBQ2YsYUFBYSxFQUNiLHlCQUF5QixFQUFFLEVBQUUsRUFDN0IsTUFBTSxDQUNQLENBQUM7WUFFSixJQUFJLG1DQUFtQyxFQUFFLE1BQU0sRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7Z0JBQzVELE1BQU0sU0FBUyxHQUFHLG1DQUFtQyxFQUFFLE1BQU0sQ0FBQztnQkFFOUQsY0FBYyxDQUFDLElBQUksQ0FBQyxHQUFHLFNBQVMsQ0FBQyxDQUFDO2dCQUNsQyxNQUFNLENBQUMsSUFBSSxDQUFDLEdBQUcsU0FBUyxDQUFDLENBQUM7WUFDNUIsQ0FBQztZQUVELElBQ0UsbUNBQW1DLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFDcEUsQ0FBQztnQkFDRCxtQkFBbUIsQ0FBQyxJQUFJLENBQ3RCLEdBQUcsbUNBQW1DLEVBQUUsbUJBQW1CLENBQzVELENBQUM7WUFDSixDQUFDO1lBRUQsSUFDRSxtQ0FBbUMsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUNwRSxDQUFDO2dCQUNELG1CQUFtQixDQUFDLElBQUksQ0FDdEIsR0FBRyxtQ0FBbUMsRUFBRSxtQkFBbUIsQ0FDNUQsQ0FBQztZQUNKLENBQUM7WUFFRCxJQUFJLG1DQUFtQyxFQUFFLGlCQUFpQixFQUFFLENBQUM7Z0JBQzNELGlCQUFpQixDQUFDLElBQUksQ0FDcEIsR0FBRyxtQ0FBbUMsRUFBRSxpQkFBaUIsQ0FDMUQsQ0FBQztZQUNKLENBQUM7WUFFRCxJQUFJLG1DQUFtQyxFQUFFLGlCQUFpQixFQUFFLENBQUM7Z0JBQzNELGlCQUFpQixDQUFDLElBQUksQ0FDcEIsR0FBRyxtQ0FBbUMsRUFBRSxpQkFBaUIsQ0FDMUQsQ0FBQztZQUNKLENBQUM7UUFDSCxDQUFDO1FBRUQsT0FBTyx3QkFBd0IsQ0FDN0IsTUFBTSxFQUNOLENBQUMsQ0FBQyxRQUFRLENBQUMsaUJBQWlCLEVBQUUsQ0FBQyxDQUFDLE9BQU8sQ0FBQyxFQUN4QyxnQkFBZ0IsRUFDaEIsbUJBQW1CLEVBQ25CLHVCQUF1QixFQUN2QixDQUFDLENBQUMsUUFBUSxDQUFDLGNBQWMsRUFBRSxDQUFDLENBQUMsT0FBTyxDQUFDLEVBQ3JDLE1BQU0sRUFDTixlQUFlLEVBQ2YsYUFBYSxFQUNiLFlBQVksRUFDWixDQUFDLENBQUMsUUFBUSxDQUFDLGlCQUFpQixFQUFFLENBQUMsQ0FBQyxPQUFPLENBQUMsRUFDeEMsbUJBQW1CLEVBQUUsTUFBTSxHQUFHLENBQUM7WUFDN0IsQ0FBQyxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsbUJBQW1CLEVBQUUsQ0FBQyxDQUFDLE9BQU8sQ0FBQztZQUM1QyxDQUFDLENBQUMsSUFBSSxDQUNULENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLG1DQUFtQyxDQUFDLENBQUM7SUFDdEQsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLE1BQU0sbUJBQW1CLEdBQUcsS0FBSyxFQUMvQixJQUE0QyxFQUM1QyxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxNQUFNLEdBQUcsSUFBSSxFQUFFLE1BQU0sQ0FBQztRQUM1QixNQUFNLGVBQWUsR0FBRyxJQUFJLEVBQUUsZUFBZSxDQUFDO1FBQzlDLE1BQU0sYUFBYSxHQUFHLElBQUksRUFBRSxhQUFhLENBQUM7UUFDMUMsTUFBTSxRQUFRLEdBQUcsSUFBSSxFQUFFLFFBQVEsQ0FBQztRQUVoQyxxREFBcUQ7UUFDckQsSUFBSSxDQUFDLE1BQU0sSUFBSSxDQUFDLGVBQWUsSUFBSSxDQUFDLGFBQWEsSUFBSSxDQUFDLFFBQVEsRUFBRSxDQUFDO1lBQy9ELE1BQU0sYUFBYSxHQUFHO2dCQUNwQixDQUFDLE1BQU0sSUFBSSxRQUFRO2dCQUNuQixDQUFDLGVBQWUsSUFBSSxpQkFBaUI7Z0JBQ3JDLENBQUMsYUFBYSxJQUFJLGVBQWU7Z0JBQ2pDLENBQUMsUUFBUSxJQUFJLFVBQVU7YUFDeEI7aUJBQ0UsTUFBTSxDQUFDLE9BQU8sQ0FBQztpQkFDZixJQUFJLENBQUMsSUFBSSxDQUFDLENBQUM7WUFDZCxNQUFNLEtBQUssR0FBRyxJQUFJLEtBQUssQ0FDckIsb0NBQW9DLGFBQWEsRUFBRSxDQUNwRCxDQUFDO1lBQ0YsOEVBQThFO1lBQzlFLEtBQUssQ0FBQyxJQUFJLEdBQUcsMEJBQTBCLENBQUM7WUFDeEMsTUFBTSxLQUFLLENBQUM7UUFDZCxDQUFDO1FBRUQsT0FBTyxNQUFNLG9CQUFvQixDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsNEJBQTRCO0lBQ3ZFLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLHVEQUF1RDtRQUN2RCxPQUFPLENBQUMsS0FBSyxDQUNYLDJDQUEyQyxJQUFJLEVBQUUsTUFBTSxLQUFLLENBQUMsQ0FBQyxPQUFPLEVBQUUsRUFDdkUsQ0FBQyxDQUNGLENBQUM7UUFDRixzRUFBc0U7UUFDdEUsTUFBTSxDQUFDLENBQUM7SUFDVixDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsTUFBTSxxQkFBcUIsR0FBRyxLQUFLLElBQUksRUFBRTtJQUN2QyxJQUFJLENBQUM7UUFDSCxNQUFNLFFBQVEsR0FBRyxLQUFLLENBQUMsUUFBUSxDQUFDLEVBQUUsT0FBTyxFQUFFLHlCQUF5QixFQUFFLENBQUMsQ0FBQztRQUN4RSxNQUFNLFFBQVEsQ0FBQyxPQUFPLEVBQUUsQ0FBQztRQUN6QixNQUFNLFFBQVEsQ0FBQyxTQUFTLENBQUMsRUFBRSxLQUFLLEVBQUUsdUJBQXVCLEVBQUUsQ0FBQyxDQUFDO1FBRTdELE1BQU0sUUFBUSxDQUFDLEdBQUcsQ0FBQztZQUNqQixXQUFXLEVBQUUsS0FBSyxFQUFFLEVBQUUsS0FBSyxFQUFFLFNBQVMsRUFBRSxPQUFPLEVBQUUsRUFBRSxFQUFFO2dCQUNuRCxPQUFPLENBQUMsR0FBRyxDQUFDO29CQUNWLEdBQUcsRUFBRSxPQUFPLEVBQUUsR0FBRyxFQUFFLFFBQVEsRUFBRTtvQkFDN0IsS0FBSyxFQUFFLE9BQU8sRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFO29CQUNqQyxPQUFPLEVBQUUsT0FBTyxFQUFFLE9BQU87aUJBQzFCLENBQUMsQ0FBQztnQkFFSCxJQUFJLGNBQWMsR0FDaEIsSUFBSSxDQUFDO2dCQUNQLElBQUksQ0FBQztvQkFDSCxJQUFJLENBQUMsT0FBTyxFQUFFLEtBQUssRUFBRSxDQUFDO3dCQUNwQiw2RUFBNkU7d0JBQzdFLE1BQU0sSUFBSSxLQUFLLENBQUMsMkNBQTJDLENBQUMsQ0FBQztvQkFDL0QsQ0FBQztvQkFDRCxjQUFjLEdBQUcsSUFBSSxDQUFDLEtBQUssQ0FBQyxPQUFPLENBQUMsS0FBSyxDQUFDLFFBQVEsRUFBRSxDQUFDLENBQUM7b0JBQ3RELE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYyxFQUFFLGlCQUFpQixDQUFDLENBQUM7b0JBQy9DLE1BQU0sbUJBQW1CLENBQUMsY0FBZSxDQUFDLENBQUM7Z0JBQzdDLENBQUM7Z0JBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztvQkFDaEIsT0FBTyxDQUFDLEtBQUssQ0FDWCw4Q0FBOEMsS0FBSyxlQUFlLFNBQVMsS0FBSyxDQUFDLENBQUMsT0FBTyxFQUFFLEVBQzNGO3dCQUNFLFVBQVUsRUFBRSxPQUFPLEVBQUUsR0FBRyxFQUFFLFFBQVEsRUFBRTt3QkFDcEMsWUFBWSxFQUFFLENBQUMsQ0FBQyxPQUFPO3dCQUN2QixTQUFTLEVBQUUsQ0FBQyxDQUFDLElBQUk7d0JBQ2pCLFVBQVUsRUFBRSxDQUFDLENBQUMsS0FBSzt3QkFDbkIsZUFBZSxFQUFFLE9BQU8sRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFO3FCQUM1QyxDQUNGLENBQUM7b0JBQ0YsNEVBQTRFO29CQUM1RSxNQUFNLENBQUMsQ0FBQztnQkFDVixDQUFDO1lBQ0gsQ0FBQztTQUNGLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLE9BQU8sQ0FBQyxLQUFLLENBQUMsZ0RBQWdELEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDbkUsNkVBQTZFO1FBQzdFLE1BQU0sQ0FBQyxDQUFDLENBQUMsNkVBQTZFO0lBQ3hGLENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixlQUFlLHFCQUFxQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGRheWpzIGZyb20gJ2RheWpzJztcbmltcG9ydCBpc29XZWVrIGZyb20gJ2RheWpzL3BsdWdpbi9pc29XZWVrJztcbmltcG9ydCBkdXJhdGlvbiBmcm9tICdkYXlqcy9wbHVnaW4vZHVyYXRpb24nO1xuaW1wb3J0IGlzQmV0d2VlbiBmcm9tICdkYXlqcy9wbHVnaW4vaXNCZXR3ZWVuJztcbmltcG9ydCB0aW1lem9uZSBmcm9tICdkYXlqcy9wbHVnaW4vdGltZXpvbmUnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcblxuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCB7XG4gIGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyxcbiAgbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNHaXZlbk1lZXRpbmdJZCxcbiAgbGlzdE1lZXRpbmdBc3Npc3RFdmVudHNGb3JBdHRlbmRlZUdpdmVuRGF0ZXMsXG4gIGxpc3RNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuTWVldGluZ0lkLFxuICBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50LFxuICBsaXN0RXZlbnRzRm9yRGF0ZSxcbiAgY29udmVydE1lZXRpbmdBc3Npc3RFdmVudFR5cGVUb0V2ZW50UGx1c1R5cGUsXG4gIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzLFxuICBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50LFxuICBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzLFxuICBnZXRFdmVudEZyb21QcmltYXJ5S2V5LFxuICBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudCxcbiAgcHJvY2Vzc1VzZXJFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnRXaXRoVXNlck1vZGlmaWVkQ2F0ZWdvcmllcyxcbiAgZ2V0VXNlclByZWZlcmVuY2VzLFxuICBwcm9jZXNzRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50V2l0aG91dENhdGVnb3JpZXMsXG4gIGxpc3RGdXR1cmVNZWV0aW5nQXNzaXN0cyxcbiAgbWVldGluZ0F0dGVuZGVlQ291bnRHaXZlbk1lZXRpbmdJZCxcbiAgZ2V0TWVldGluZ0Fzc2lzdCxcbiAgZ2VuZXJhdGVOZXdNZWV0aW5nRXZlbnRGb3JBdHRlbmRlZSxcbiAgY3JlYXRlQnVmZmVyVGltZUZvck5ld01lZXRpbmdFdmVudCxcbiAgY3JlYXRlUmVtaW5kZXJzRnJvbU1pbnV0ZXNBbmRFdmVudCxcbiAgZ2V0R2xvYmFsQ2FsZW5kYXIsXG4gIHNlYXJjaFRyYWluaW5nRGF0YUJ5VmVjdG9yLCAvLyB1cGRhdGVkXG4gIGdldEV2ZW50VmVjdG9yQnlJZCwgLy8gdXBkYXRlZFxuICBkZWxldGVUcmFpbmluZ0RhdGFCeUlkLCAvLyB1cGRhdGVkXG4gIGFkZFRyYWluaW5nRGF0YSwgLy8gYWRkZWRcbn0gZnJvbSAnQGZlYXR1cmVzX2FwcGx5L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHtcbiAgRXZlbnRQbHVzVHlwZSxcbiAgRXZlbnRUeXBlLFxuICBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlLFxuICBFdmVudE1lZXRpbmdQbHVzVHlwZSxcbiAgTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSxcbiAgUmVtaW5kZXJzRm9yRXZlbnRUeXBlLFxuICBCdWZmZXJUaW1lT2JqZWN0VHlwZSxcbiAgQ2F0ZWdvcnlUeXBlLFxuICBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgUmV0dXJuVmFsdWVGb3JFYWNoRnV0dXJlTWVldGluZ0Fzc2lzdFR5cGUsXG4gIFZhbHVlc1RvUmV0dXJuRm9yQnVmZmVyRXZlbnRzVHlwZSxcbiAgVHJhaW5pbmdFdmVudFNjaGVtYSxcbiAgRmVhdHVyZXNBcHBseVJlc3BvbnNlLFxuICBTa2lsbEVycm9yLCAvLyBBZGRlZCBmb3Igc3RhbmRhcmRpemVkIGVycm9yIGhhbmRsaW5nXG59IGZyb20gJ0BmZWF0dXJlc19hcHBseS9fbGlicy90eXBlcyc7XG4vLyBSZW1vdmUgcmVkdW5kYW50IGltcG9ydCBvZiBSZXR1cm5WYWx1ZUZvckVhY2hNZWV0aW5nQXNzaXN0VHlwZSBpZiBpdCdzIGNvdmVyZWQgYnkgdGhlIG1haW4gaW1wb3J0XG4vLyBpbXBvcnQgeyBSZXR1cm5WYWx1ZUZvckVhY2hNZWV0aW5nQXNzaXN0VHlwZSB9IGZyb20gJ0BmZWF0dXJlc19hcHBseS9fbGlicy90eXBlcyc7XG5cbmltcG9ydCB7IHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lciB9IGZyb20gJ0BmZWF0dXJlc19hcHBseS9fbGlicy9vcHRhcGxhbm5lci9hcGktaGVscGVyJztcblxuaW1wb3J0IHtcbiAga2Fma2FGZWF0dXJlc0FwcGx5R3JvdXBJZCxcbiAga2Fma2FGZWF0dXJlc0FwcGx5VG9waWMsXG59IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBLYWZrYSwgbG9nTGV2ZWwgfSBmcm9tICdrYWZrYWpzJztcbmltcG9ydCBpcCBmcm9tICdpcCc7XG5pbXBvcnQgeyBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZSB9IGZyb20gJ0AvYXV0b3BpbG90L19saWJzL3R5cGVzJztcblxuZGF5anMuZXh0ZW5kKGlzb1dlZWspO1xuZGF5anMuZXh0ZW5kKGR1cmF0aW9uKTtcbmRheWpzLmV4dGVuZChpc0JldHdlZW4pO1xuZGF5anMuZXh0ZW5kKHRpbWV6b25lKTtcbmRheWpzLmV4dGVuZCh1dGMpO1xuXG5jb25zdCBrYWZrYSA9IG5ldyBLYWZrYSh7XG4gIGxvZ0xldmVsOiBsb2dMZXZlbC5ERUJVRyxcbiAgYnJva2VyczogW2BrYWZrYTE6MjkwOTJgXSxcbiAgY2xpZW50SWQ6ICdhdG9taWMnLFxuICAvLyBzc2w6IHRydWUsXG4gIHNhc2w6IHtcbiAgICBtZWNoYW5pc206ICdwbGFpbicsIC8vIHNjcmFtLXNoYS0yNTYgb3Igc2NyYW0tc2hhLTUxMlxuICAgIHVzZXJuYW1lOiBwcm9jZXNzLmVudi5LQUZLQV9VU0VSTkFNRSxcbiAgICBwYXNzd29yZDogcHJvY2Vzcy5lbnYuS0FGS0FfUEFTU1dPUkQsXG4gIH0sXG59KTtcblxuY29uc3QgcHJvY2Vzc0V2ZW50c0ZvclBsYW5uaW5nID0gYXN5bmMgKFxuICBtYWluSG9zdElkOiBzdHJpbmcsXG4gIGludGVybmFsQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIG1lZXRpbmdFdmVudFBsdXM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10sIC8vIGV2ZW50cyB3aXRoIGEgbWVldGluZ0lkXG4gIG5ld01lZXRpbmdFdmVudFBsdXM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10sIC8vIGdlbmVyYXRlZCBldmVudHNcbiAgbmV3TWVldGluZ0Fzc2lzdHM6IE1lZXRpbmdBc3Npc3RUeXBlW10sXG4gIHRvdGFsRXZlbnRzOiBFdmVudFR5cGVbXSxcbiAgb2xkRXZlbnRzOiBFdmVudFR5cGVbXSxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGV4dGVybmFsQXR0ZW5kZWVzPzogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdLFxuICBtZWV0aW5nQXNzaXN0RXZlbnRzPzogTWVldGluZ0Fzc2lzdEV2ZW50VHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBldmVudHM6IEV2ZW50UGx1c1R5cGVbXSA9IF8uY2xvbmVEZWVwKHRvdGFsRXZlbnRzKTtcbiAgICBjb25zdCB1c2VyTW9kaWZpZWRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBldmVudCBvZiBldmVudHMpIHtcbiAgICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXNSZXNwb25zZSA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoXG4gICAgICAgIGV2ZW50Py5pZFxuICAgICAgKTtcbiAgICAgIGlmICghcHJlZmVycmVkVGltZVJhbmdlc1Jlc3BvbnNlLm9rKSB7XG4gICAgICAgIC8vIERlY2lkZTogdGhyb3csIG9yIGxvZyBhbmQgY29udGludWUgd2l0aCBlbXB0eSBwcmVmZXJyZWRUaW1lUmFuZ2VzP1xuICAgICAgICAvLyBGb3Igbm93LCBsb2dnaW5nIGFuZCBjb250aW51aW5nIGFzIHByZWZlcnJlZFRpbWVSYW5nZXMgbWlnaHQgbm90IGJlIGNyaXRpY2FsIGZvciBhbGwgZXZlbnRzLlxuICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgYEZhaWxlZCB0byBnZXQgcHJlZmVycmVkIHRpbWUgcmFuZ2VzIGZvciBldmVudCAke2V2ZW50Py5pZH06ICR7cHJlZmVycmVkVGltZVJhbmdlc1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgKTtcbiAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goZXZlbnQpOyAvLyBBZGQgZXZlbnQgd2l0aG91dCBwcmVmZXJyZWRUaW1lUmFuZ2VzXG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zdCBwcmVmZXJyZWRUaW1lUmFuZ2VzID0gcHJlZmVycmVkVGltZVJhbmdlc1Jlc3BvbnNlLmRhdGEgfHwgW107XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKHtcbiAgICAgICAgICAuLi5ldmVudCxcbiAgICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBwcmVmZXJyZWRUaW1lUmFuZ2VzLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBuZXdIb3N0UmVtaW5kZXJzOiBSZW1pbmRlcnNGb3JFdmVudFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG5ld0hvc3RCdWZmZXJUaW1lczogQnVmZmVyVGltZU9iamVjdFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG5ld0hvc3RNZWV0aW5nRXZlbnRzUGx1czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBuZXdNZWV0aW5nQXNzaXN0IG9mIG5ld01lZXRpbmdBc3Npc3RzKSB7XG4gICAgICBsZXQgbmV3SG9zdE1lZXRpbmdFdmVudFBsdXMgPSBuZXdNZWV0aW5nRXZlbnRQbHVzXG4gICAgICAgID8uZmlsdGVyKChtZSkgPT4gbWU/Lm1lZXRpbmdJZCA9PT0gbmV3TWVldGluZ0Fzc2lzdD8uaWQpXG4gICAgICAgID8uZmluZCgobWUpID0+IG1lPy51c2VySWQgPT09IG5ld01lZXRpbmdBc3Npc3Q/LnVzZXJJZCk7XG4gICAgICBsZXQgbmV3QnVmZmVyVGltZUZvck1lZXRpbmdFdmVudE9yRW1wdHlPYmplY3Q6IEJ1ZmZlclRpbWVPYmplY3RUeXBlID0ge307XG4gICAgICBsZXQgbmV3TW9kaWZpZWRSZW1pbmRlck9yTnVsbDogUmVtaW5kZXJzRm9yRXZlbnRUeXBlIHwgbnVsbCA9IG51bGw7XG5cbiAgICAgIGlmIChuZXdIb3N0TWVldGluZ0V2ZW50UGx1cz8uaWQpIHtcbiAgICAgICAgbmV3TW9kaWZpZWRSZW1pbmRlck9yTnVsbCA9IG5ld01lZXRpbmdBc3Npc3Q/LnJlbWluZGVycz8uWzBdXG4gICAgICAgICAgPyBjcmVhdGVSZW1pbmRlcnNGcm9tTWludXRlc0FuZEV2ZW50KFxuICAgICAgICAgICAgICBuZXdIb3N0TWVldGluZ0V2ZW50UGx1cy5pZCxcbiAgICAgICAgICAgICAgbmV3TWVldGluZ0Fzc2lzdC5yZW1pbmRlcnMsXG4gICAgICAgICAgICAgIG5ld01lZXRpbmdBc3Npc3QudGltZXpvbmUsXG4gICAgICAgICAgICAgIG5ld01lZXRpbmdBc3Npc3QudXNlRGVmYXVsdEFsYXJtcyxcbiAgICAgICAgICAgICAgbmV3TWVldGluZ0Fzc2lzdC51c2VySWRcbiAgICAgICAgICAgIClcbiAgICAgICAgICA6IG51bGw7XG4gICAgICB9XG5cbiAgICAgIGlmIChuZXdNb2RpZmllZFJlbWluZGVyT3JOdWxsPy5yZW1pbmRlcnM/LlswXT8udXNlcklkKSB7XG4gICAgICAgIG5ld0hvc3RSZW1pbmRlcnMucHVzaChuZXdNb2RpZmllZFJlbWluZGVyT3JOdWxsKTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgdmFsdWVzVG9SZXR1cm46IFZhbHVlc1RvUmV0dXJuRm9yQnVmZmVyRXZlbnRzVHlwZSA9XG4gICAgICAgIG5ld01lZXRpbmdBc3Npc3Q/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQgPiAwIHx8XG4gICAgICAgIG5ld01lZXRpbmdBc3Npc3Q/LmJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50ID4gMFxuICAgICAgICAgID8gY3JlYXRlQnVmZmVyVGltZUZvck5ld01lZXRpbmdFdmVudChcbiAgICAgICAgICAgICAgbmV3SG9zdE1lZXRpbmdFdmVudFBsdXMsXG4gICAgICAgICAgICAgIG5ld01lZXRpbmdBc3Npc3QuYnVmZmVyVGltZVxuICAgICAgICAgICAgKVxuICAgICAgICAgIDogbnVsbDtcblxuICAgICAgaWYgKHZhbHVlc1RvUmV0dXJuPy5iZWZvcmVFdmVudD8uaWQpIHtcbiAgICAgICAgbmV3QnVmZmVyVGltZUZvck1lZXRpbmdFdmVudE9yRW1wdHlPYmplY3QuYmVmb3JlRXZlbnQgPVxuICAgICAgICAgIHZhbHVlc1RvUmV0dXJuLmJlZm9yZUV2ZW50O1xuICAgICAgICBuZXdIb3N0TWVldGluZ0V2ZW50UGx1cyA9IHZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50O1xuICAgICAgfVxuXG4gICAgICBpZiAodmFsdWVzVG9SZXR1cm4/LmFmdGVyRXZlbnQ/LmlkKSB7XG4gICAgICAgIG5ld0J1ZmZlclRpbWVGb3JNZWV0aW5nRXZlbnRPckVtcHR5T2JqZWN0LmFmdGVyRXZlbnQgPVxuICAgICAgICAgIHZhbHVlc1RvUmV0dXJuLmFmdGVyRXZlbnQ7XG4gICAgICAgIG5ld0hvc3RNZWV0aW5nRXZlbnRQbHVzID0gdmFsdWVzVG9SZXR1cm4ubmV3RXZlbnQ7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgbmV3QnVmZmVyVGltZUZvck1lZXRpbmdFdmVudE9yRW1wdHlPYmplY3Q/LmFmdGVyRXZlbnQ/LmlkIHx8XG4gICAgICAgIG5ld0J1ZmZlclRpbWVGb3JNZWV0aW5nRXZlbnRPckVtcHR5T2JqZWN0Py5iZWZvcmVFdmVudD8uaWRcbiAgICAgICkge1xuICAgICAgICBuZXdIb3N0QnVmZmVyVGltZXMucHVzaChuZXdCdWZmZXJUaW1lRm9yTWVldGluZ0V2ZW50T3JFbXB0eU9iamVjdCk7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgbmV3SG9zdE1lZXRpbmdFdmVudFBsdXM/LnByZUV2ZW50SWQgfHxcbiAgICAgICAgbmV3SG9zdE1lZXRpbmdFdmVudFBsdXM/LnBvc3RFdmVudElkXG4gICAgICApIHtcbiAgICAgICAgbmV3SG9zdE1lZXRpbmdFdmVudHNQbHVzLnB1c2gobmV3SG9zdE1lZXRpbmdFdmVudFBsdXMpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG5ld01lZXRpbmdFdmVudFBsdXNSZW1vdmVkSG9zdEV2ZW50cyA9IF8uZGlmZmVyZW5jZUJ5KFxuICAgICAgbmV3TWVldGluZ0V2ZW50UGx1cyxcbiAgICAgIG5ld0hvc3RNZWV0aW5nRXZlbnRzUGx1cyxcbiAgICAgICdpZCdcbiAgICApO1xuICAgIGNvbnN0IG5ld01lZXRpbmdFdmVudFBsdXNNb2RpZmllZEhvc3RFdmVudHMgPVxuICAgICAgbmV3TWVldGluZ0V2ZW50UGx1c1JlbW92ZWRIb3N0RXZlbnRzLmNvbmNhdChuZXdIb3N0TWVldGluZ0V2ZW50c1BsdXMpO1xuXG4gICAgcmV0dXJuIHByb2Nlc3NFdmVudHNGb3JPcHRhUGxhbm5lcihcbiAgICAgIG1haW5Ib3N0SWQsXG4gICAgICBpbnRlcm5hbEF0dGVuZGVlcyxcbiAgICAgIG1lZXRpbmdFdmVudFBsdXMsXG4gICAgICBuZXdNZWV0aW5nRXZlbnRQbHVzTW9kaWZpZWRIb3N0RXZlbnRzLFxuICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLFxuICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIG9sZEV2ZW50cyxcbiAgICAgIGV4dGVybmFsQXR0ZW5kZWVzLFxuICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cyxcbiAgICAgIG5ld0hvc3RSZW1pbmRlcnM/Lmxlbmd0aCA+IDAgPyBuZXdIb3N0UmVtaW5kZXJzIDogW10sXG4gICAgICBuZXdIb3N0QnVmZmVyVGltZXM/Lmxlbmd0aCA+IDAgPyBuZXdIb3N0QnVmZmVyVGltZXMgOiBbXVxuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGV2ZW50cyBmb3IgcGxhbm5pbmcnKTtcbiAgfVxufTtcblxuY29uc3QgcHJvY2Vzc0VhY2hNZWV0aW5nQXNzaXN0ID0gYXN5bmMgKFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgbWVldGluZ0lkOiBzdHJpbmcsXG4gIG1lZXRpbmdFdmVudDogRXZlbnRUeXBlLFxuICBsaXN0ZWRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXVxuKTogUHJvbWlzZTxSZXR1cm5WYWx1ZUZvckVhY2hNZWV0aW5nQXNzaXN0VHlwZT4gPT4ge1xuICAvLyBUaGlzIHJldHVybiB0eXBlIG1pZ2h0IG5lZWQgdG8gYmVjb21lIEZlYXR1cmVzQXBwbHlSZXNwb25zZSBhcyB3ZWxsIGlmIHdlIHdhbnQgdG8gcHJvcGFnYXRlIGVycm9ycyBmcm9tIGl0XG4gIHRyeSB7XG4gICAgY29uc3QgYXR0ZW5kZWVzUmVzcG9uc2UgPVxuICAgICAgYXdhaXQgbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNHaXZlbk1lZXRpbmdJZChtZWV0aW5nSWQpO1xuICAgIGlmICghYXR0ZW5kZWVzUmVzcG9uc2Uub2spXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBGYWlsZWQgdG8gbGlzdCBhdHRlbmRlZXMgZm9yIG1lZXRpbmcgJHttZWV0aW5nSWR9OiAke2F0dGVuZGVlc1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgY29uc3QgYXR0ZW5kZWVzID0gYXR0ZW5kZWVzUmVzcG9uc2UuZGF0YSB8fCBbXTtcblxuICAgIGNvbnN0IGV4dGVybmFsQXR0ZW5kZWVzID0gYXR0ZW5kZWVzLmZpbHRlcigoYSkgPT4gISFhPy5leHRlcm5hbEF0dGVuZGVlKTtcbiAgICBjb25zdCBpbnRlcm5hbEF0dGVuZGVlcyA9IGF0dGVuZGVlcy5maWx0ZXIoKGEpID0+ICFhPy5leHRlcm5hbEF0dGVuZGVlKTtcblxuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IGV2ZW50czogRXZlbnRUeXBlW10gPSBbXTtcbiAgICBjb25zdCBtZWV0aW5nRXZlbnRzOiBFdmVudFR5cGVbXSA9IFttZWV0aW5nRXZlbnRdOyAvLyBTdGFydCB3aXRoIHRoZSBpbml0aWFsIG1lZXRpbmcgZXZlbnRcblxuICAgIGlmIChleHRlcm5hbEF0dGVuZGVlcy5sZW5ndGggPiAwKSB7XG4gICAgICBmb3IgKGNvbnN0IGF0dGVuZGVlIG9mIGV4dGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgIGNvbnN0IGV4dEV2ZW50c1Jlc3BvbnNlID1cbiAgICAgICAgICBhd2FpdCBsaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcyhcbiAgICAgICAgICAgIGF0dGVuZGVlLmlkLFxuICAgICAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgICAgIGF0dGVuZGVlLnRpbWV6b25lLFxuICAgICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgICAgKTtcbiAgICAgICAgaWYgKCFleHRFdmVudHNSZXNwb25zZS5vaykge1xuICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgIGBGYWlsZWQgdG8gbGlzdCBtZWV0aW5nIGFzc2lzdCBldmVudHMgZm9yIGV4dGVybmFsIGF0dGVuZGVlICR7YXR0ZW5kZWUuaWR9OiAke2V4dEV2ZW50c1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgICApO1xuICAgICAgICAgIGNvbnRpbnVlOyAvLyBTa2lwIHRoaXMgYXR0ZW5kZWUgb3IgaGFuZGxlIGVycm9yIG1vcmUgc3RyaWN0bHlcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBuZXdNZWV0aW5nQXNzaXN0RXZlbnRzID0gZXh0RXZlbnRzUmVzcG9uc2UuZGF0YSB8fCBbXTtcbiAgICAgICAgY29uc3QgbWVldGluZ0Fzc2lzdEV2ZW50Rm9yTWVldGluZyA9IG5ld01lZXRpbmdBc3Npc3RFdmVudHMuZmluZChcbiAgICAgICAgICAobSkgPT4gbT8ubWVldGluZ0lkID09PSBtZWV0aW5nSWRcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZmlsdGVyZWRNZWV0aW5nQXNzaXN0RXZlbnRzID0gbmV3TWVldGluZ0Fzc2lzdEV2ZW50cy5maWx0ZXIoXG4gICAgICAgICAgKGUpID0+IGU/Lm1lZXRpbmdJZCAhPT0gbWVldGluZ0lkXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKGZpbHRlcmVkTWVldGluZ0Fzc2lzdEV2ZW50cy5sZW5ndGggPiAwKVxuICAgICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMucHVzaCguLi5maWx0ZXJlZE1lZXRpbmdBc3Npc3RFdmVudHMpO1xuICAgICAgICBpZiAobWVldGluZ0Fzc2lzdEV2ZW50Rm9yTWVldGluZz8uaWQpXG4gICAgICAgICAgbWVldGluZ0V2ZW50cy5wdXNoKFxuICAgICAgICAgICAgY29udmVydE1lZXRpbmdBc3Npc3RFdmVudFR5cGVUb0V2ZW50UGx1c1R5cGUoXG4gICAgICAgICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudEZvck1lZXRpbmcsXG4gICAgICAgICAgICAgIGF0dGVuZGVlLnVzZXJJZFxuICAgICAgICAgICAgKVxuICAgICAgICAgICk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgZm9yIChjb25zdCBhdHRlbmRlZSBvZiBpbnRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgY29uc3QgaW50ZXJuYWxFdmVudHNSZXNwb25zZSA9IGF3YWl0IGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyhcbiAgICAgICAgYXR0ZW5kZWUudXNlcklkLFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIGF0dGVuZGVlLnRpbWV6b25lLFxuICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICk7XG4gICAgICBpZiAoIWludGVybmFsRXZlbnRzUmVzcG9uc2Uub2spIHtcbiAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgIGBGYWlsZWQgdG8gbGlzdCBldmVudHMgZm9yIGludGVybmFsIGF0dGVuZGVlICR7YXR0ZW5kZWUudXNlcklkfTogJHtpbnRlcm5hbEV2ZW50c1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgKTtcbiAgICAgICAgY29udGludWU7IC8vIFNraXAgdGhpcyBhdHRlbmRlZVxuICAgICAgfVxuICAgICAgY29uc3QgbmV3RXZlbnRzID0gaW50ZXJuYWxFdmVudHNSZXNwb25zZS5kYXRhIHx8IFtdO1xuICAgICAgY29uc3QgbWVldGluZ0V2ZW50Rm9yQ3VycmVudEF0dGVuZGVlID0gbmV3RXZlbnRzLmZpbmQoXG4gICAgICAgIChlKSA9PiBlPy5tZWV0aW5nSWQgPT09IG1lZXRpbmdJZFxuICAgICAgKTtcbiAgICAgIGNvbnN0IGZpbHRlcmVkTmV3RXZlbnRzID0gbmV3RXZlbnRzLmZpbHRlcihcbiAgICAgICAgKGUpID0+IGU/Lm1lZXRpbmdJZCAhPT0gbWVldGluZ0lkXG4gICAgICApO1xuXG4gICAgICBpZiAoZmlsdGVyZWROZXdFdmVudHMubGVuZ3RoID4gMCkgZXZlbnRzLnB1c2goLi4uZmlsdGVyZWROZXdFdmVudHMpO1xuICAgICAgaWYgKG1lZXRpbmdFdmVudEZvckN1cnJlbnRBdHRlbmRlZT8uaWQpXG4gICAgICAgIG1lZXRpbmdFdmVudHMucHVzaChtZWV0aW5nRXZlbnRGb3JDdXJyZW50QXR0ZW5kZWUpO1xuICAgIH1cblxuICAgIGNvbnN0IHByZWZlcnJlZFRpbWVzUmFuZ2VzUmVzcG9uc2UgPVxuICAgICAgYXdhaXQgbGlzdE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5NZWV0aW5nSWQobWVldGluZ0lkKTtcbiAgICBpZiAoIXByZWZlcnJlZFRpbWVzUmFuZ2VzUmVzcG9uc2Uub2spIHtcbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYEZhaWxlZCB0byBsaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlcyBmb3IgbWVldGluZyAke21lZXRpbmdJZH06ICR7cHJlZmVycmVkVGltZXNSYW5nZXNSZXNwb25zZS5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICApO1xuICAgIH1cbiAgICBjb25zdCBwcmVmZXJyZWRUaW1lc1JhbmdlcyA9XG4gICAgICBwcmVmZXJyZWRUaW1lc1Jhbmdlc1Jlc3BvbnNlLm9rICYmIHByZWZlcnJlZFRpbWVzUmFuZ2VzUmVzcG9uc2UuZGF0YVxuICAgICAgICA/IHByZWZlcnJlZFRpbWVzUmFuZ2VzUmVzcG9uc2UuZGF0YVxuICAgICAgICA6IFtdO1xuXG4gICAgY29uc3QgbmV3VXNlck1vZGlmaWVkTWVldGluZ0V2ZW50czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSA9XG4gICAgICBtZWV0aW5nRXZlbnRzLm1hcCgobWUpID0+ICh7XG4gICAgICAgIC4uLm1lLFxuICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBwcmVmZXJyZWRUaW1lc1JhbmdlcyxcbiAgICAgIH0pKTtcblxuICAgIGNvbnN0IHVzZXJNb2RpZmllZEV2ZW50czogRXZlbnRQbHVzVHlwZVtdID0gW107XG4gICAgZm9yIChjb25zdCBldmVudCBvZiBldmVudHMpIHtcbiAgICAgIGNvbnN0IGV2ZW50UHJlZmVycmVkVGltZVJhbmdlc1Jlc3BvbnNlID1cbiAgICAgICAgYXdhaXQgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudChldmVudD8uaWQpO1xuICAgICAgaWYgKCFldmVudFByZWZlcnJlZFRpbWVSYW5nZXNSZXNwb25zZS5vaykge1xuICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgYEZhaWxlZCB0byBsaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlcyBmb3IgZXZlbnQgJHtldmVudC5pZH06ICR7ZXZlbnRQcmVmZXJyZWRUaW1lUmFuZ2VzUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICApO1xuICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChldmVudCk7IC8vIEFkZCB3aXRoIGVtcHR5IG9yIG5vIHByZWZlcnJlZCB0aW1lIHJhbmdlc1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cbiAgICAgIGNvbnN0IGV2ZW50UHJlZmVycmVkVGltZVJhbmdlcyA9XG4gICAgICAgIGV2ZW50UHJlZmVycmVkVGltZVJhbmdlc1Jlc3BvbnNlLm9rICYmXG4gICAgICAgIGV2ZW50UHJlZmVycmVkVGltZVJhbmdlc1Jlc3BvbnNlLmRhdGFcbiAgICAgICAgICA/IGV2ZW50UHJlZmVycmVkVGltZVJhbmdlc1Jlc3BvbnNlLmRhdGFcbiAgICAgICAgICA6IFtdO1xuICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goe1xuICAgICAgICAuLi5ldmVudCxcbiAgICAgICAgcHJlZmVycmVkVGltZVJhbmdlczogZXZlbnRQcmVmZXJyZWRUaW1lUmFuZ2VzLFxuICAgICAgfSk7XG4gICAgfVxuXG4gICAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSB1c2VyTW9kaWZpZWRFdmVudHNcbiAgICAgIC5tYXAoKGUpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IGxpc3RlZEV2ZW50cz8uZmluZEluZGV4KChsKSA9PiBsPy5pZCA9PT0gZT8uaWQpO1xuICAgICAgICBpZiAoZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICAgIH1cbiAgICAgICAgcmV0dXJuIGU7XG4gICAgICB9KVxuICAgICAgPy5maWx0ZXIoKGUpID0+IGUgIT09IG51bGwpO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIGV2ZW50czogZmlsdGVyZWRFdmVudHMsXG4gICAgICBtZWV0aW5nQXNzaXN0RXZlbnRzLFxuICAgICAgbWVldGluZ0V2ZW50c1BsdXM6IG5ld1VzZXJNb2RpZmllZE1lZXRpbmdFdmVudHMsXG4gICAgICBpbnRlcm5hbEF0dGVuZGVlcyxcbiAgICAgIGV4dGVybmFsQXR0ZW5kZWVzLFxuICAgIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGVhY2ggbWVldGluZyBhc3Npc3QnKTtcbiAgfVxufTtcblxuZnVuY3Rpb24gZ2V0UmFuZG9tSW50KG1pbiwgbWF4KSB7XG4gIG1pbiA9IE1hdGguY2VpbChtaW4pO1xuICBtYXggPSBNYXRoLmZsb29yKG1heCk7XG4gIHJldHVybiBNYXRoLmZsb29yKE1hdGgucmFuZG9tKCkgKiAobWF4IC0gbWluKSArIG1pbik7IC8vIFRoZSBtYXhpbXVtIGlzIGV4Y2x1c2l2ZSBhbmQgdGhlIG1pbmltdW0gaXMgaW5jbHVzaXZlXG59XG5cbmNvbnN0IHByb2Nlc3NFYWNoRnV0dXJlTWVldGluZ0Fzc2lzdCA9IGFzeW5jIChcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgbWVldGluZ0lkOiBzdHJpbmcsXG4gIGxpc3RlZEV2ZW50czogRXZlbnRUeXBlW11cbik6IFByb21pc2U8UmV0dXJuVmFsdWVGb3JFYWNoRnV0dXJlTWVldGluZ0Fzc2lzdFR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0UmVzcG9uc2UgPSBhd2FpdCBnZXRNZWV0aW5nQXNzaXN0KG1lZXRpbmdJZCk7XG4gICAgaWYgKCFtZWV0aW5nQXNzaXN0UmVzcG9uc2Uub2sgfHwgIW1lZXRpbmdBc3Npc3RSZXNwb25zZS5kYXRhKVxuICAgICAgdGhyb3cgbmV3IEVycm9yKFxuICAgICAgICBgRmFpbGVkIHRvIGdldCBtZWV0aW5nIGFzc2lzdCAke21lZXRpbmdJZH06ICR7bWVldGluZ0Fzc2lzdFJlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgY29uc3QgbWVldGluZ0Fzc2lzdCA9IG1lZXRpbmdBc3Npc3RSZXNwb25zZS5kYXRhO1xuXG4gICAgY29uc3QgcHJlZmVycmVkVGltZXNSYW5nZXNSZXNwb25zZSA9XG4gICAgICBhd2FpdCBsaXN0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbk1lZXRpbmdJZChtZWV0aW5nSWQpO1xuICAgIGlmICghcHJlZmVycmVkVGltZXNSYW5nZXNSZXNwb25zZS5vaylcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgYEZhaWxlZCB0byBsaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlcyBmb3IgbWVldGluZyAke21lZXRpbmdJZH06ICR7cHJlZmVycmVkVGltZXNSYW5nZXNSZXNwb25zZS5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICApO1xuICAgIGNvbnN0IHByZWZlcnJlZFRpbWVzUmFuZ2VzID0gcHJlZmVycmVkVGltZXNSYW5nZXNSZXNwb25zZS5kYXRhIHx8IFtdO1xuXG4gICAgY29uc3QgYXR0ZW5kZWVzUmVzcG9uc2UgPVxuICAgICAgYXdhaXQgbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNHaXZlbk1lZXRpbmdJZChtZWV0aW5nSWQpO1xuICAgIGlmICghYXR0ZW5kZWVzUmVzcG9uc2Uub2spXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgIGBGYWlsZWQgdG8gbGlzdCBhdHRlbmRlZXMgZm9yIG1lZXRpbmcgJHttZWV0aW5nSWR9OiAke2F0dGVuZGVlc1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICk7XG4gICAgY29uc3QgYXR0ZW5kZWVzID0gYXR0ZW5kZWVzUmVzcG9uc2UuZGF0YSB8fCBbXTtcblxuICAgIGNvbnN0IGhvc3RUaW1lem9uZSA9IG1lZXRpbmdBc3Npc3Q/LnRpbWV6b25lO1xuICAgIGlmICghaG9zdFRpbWV6b25lKVxuICAgICAgdGhyb3cgbmV3IEVycm9yKCdIb3N0IHRpbWV6b25lIGlzIG1pc3NpbmcgZnJvbSBtZWV0aW5nIGFzc2lzdCBkYXRhLicpO1xuXG4gICAgY29uc3QgbmV3TWVldGluZ0V2ZW50czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSA9IFtdO1xuICAgIGZvciAoY29uc3QgYXR0ZW5kZWUgb2YgYXR0ZW5kZWVzKSB7XG4gICAgICBsZXQgY2FsZW5kYXJJZDogc3RyaW5nIHwgbnVsbCA9IG51bGw7XG4gICAgICBpZiAoIWF0dGVuZGVlPy5leHRlcm5hbEF0dGVuZGVlKSB7XG4gICAgICAgIGNvbnN0IGdsb2JhbENhbGVuZGFyUmVzcG9uc2UgPSBhd2FpdCBnZXRHbG9iYWxDYWxlbmRhcihcbiAgICAgICAgICBhdHRlbmRlZT8udXNlcklkXG4gICAgICAgICk7XG4gICAgICAgIGlmICghZ2xvYmFsQ2FsZW5kYXJSZXNwb25zZS5vaykge1xuICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgIGBGYWlsZWQgdG8gZ2V0IGdsb2JhbCBjYWxlbmRhciBmb3IgYXR0ZW5kZWUgJHthdHRlbmRlZS51c2VySWR9OiAke2dsb2JhbENhbGVuZGFyUmVzcG9uc2UuZXJyb3I/Lm1lc3NhZ2V9YFxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgICAgY2FsZW5kYXJJZCA9XG4gICAgICAgICAgZ2xvYmFsQ2FsZW5kYXJSZXNwb25zZS5vayAmJiBnbG9iYWxDYWxlbmRhclJlc3BvbnNlLmRhdGFcbiAgICAgICAgICAgID8gZ2xvYmFsQ2FsZW5kYXJSZXNwb25zZS5kYXRhLmlkXG4gICAgICAgICAgICA6IG51bGw7XG4gICAgICB9XG4gICAgICBjb25zdCBuZXdNZWV0aW5nRXZlbnQgPSBnZW5lcmF0ZU5ld01lZXRpbmdFdmVudEZvckF0dGVuZGVlKFxuICAgICAgICBhdHRlbmRlZSxcbiAgICAgICAgbWVldGluZ0Fzc2lzdCxcbiAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgIHByZWZlcnJlZFRpbWVzUmFuZ2VzPy5bZ2V0UmFuZG9tSW50KDAsIHByZWZlcnJlZFRpbWVzUmFuZ2VzLmxlbmd0aCldXG4gICAgICApO1xuICAgICAgbmV3TWVldGluZ0V2ZW50cy5wdXNoKHsgLi4ubmV3TWVldGluZ0V2ZW50LCBwcmVmZXJyZWRUaW1lUmFuZ2VzIH0pO1xuICAgIH1cblxuICAgIGNvbnN0IGV4dGVybmFsQXR0ZW5kZWVzID0gYXR0ZW5kZWVzLmZpbHRlcigoYSkgPT4gISFhPy5leHRlcm5hbEF0dGVuZGVlKTtcbiAgICBjb25zdCBpbnRlcm5hbEF0dGVuZGVlcyA9IGF0dGVuZGVlcy5maWx0ZXIoKGEpID0+ICFhPy5leHRlcm5hbEF0dGVuZGVlKTtcbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0RXZlbnRzOiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10gPSBbXTtcbiAgICBjb25zdCBldmVudHM6IEV2ZW50VHlwZVtdID0gW107XG5cbiAgICBpZiAoZXh0ZXJuYWxBdHRlbmRlZXMubGVuZ3RoID4gMCkge1xuICAgICAgZm9yIChjb25zdCBhdHRlbmRlZSBvZiBleHRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgICBjb25zdCBleHRFdmVudHNSZXNwb25zZSA9XG4gICAgICAgICAgYXdhaXQgbGlzdE1lZXRpbmdBc3Npc3RFdmVudHNGb3JBdHRlbmRlZUdpdmVuRGF0ZXMoXG4gICAgICAgICAgICBhdHRlbmRlZS5pZCxcbiAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgICAgICBhdHRlbmRlZS50aW1lem9uZSxcbiAgICAgICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgICAgICk7XG4gICAgICAgIGlmICghZXh0RXZlbnRzUmVzcG9uc2Uub2spIHtcbiAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICBgRmFpbGVkIHRvIGxpc3QgbWVldGluZyBhc3Npc3QgZXZlbnRzIGZvciBleHRlcm5hbCBhdHRlbmRlZSAke2F0dGVuZGVlLmlkfTogJHtleHRFdmVudHNSZXNwb25zZS5lcnJvcj8ubWVzc2FnZX1gXG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBuZXdFeHRNZWV0aW5nQXNzaXN0RXZlbnRzID0gZXh0RXZlbnRzUmVzcG9uc2UuZGF0YSB8fCBbXTtcbiAgICAgICAgaWYgKG5ld0V4dE1lZXRpbmdBc3Npc3RFdmVudHMubGVuZ3RoID4gMClcbiAgICAgICAgICBtZWV0aW5nQXNzaXN0RXZlbnRzLnB1c2goLi4ubmV3RXh0TWVldGluZ0Fzc2lzdEV2ZW50cyk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgZm9yIChjb25zdCBhdHRlbmRlZSBvZiBpbnRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgY29uc3QgaW50ZXJuYWxFdmVudHNSZXNwb25zZSA9IGF3YWl0IGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyhcbiAgICAgICAgYXR0ZW5kZWUudXNlcklkLFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIGF0dGVuZGVlLnRpbWV6b25lLFxuICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICk7XG4gICAgICBpZiAoIWludGVybmFsRXZlbnRzUmVzcG9uc2Uub2spIHtcbiAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgIGBGYWlsZWQgdG8gbGlzdCBldmVudHMgZm9yIGludGVybmFsIGF0dGVuZGVlICR7YXR0ZW5kZWUudXNlcklkfTogJHtpbnRlcm5hbEV2ZW50c1Jlc3BvbnNlLmVycm9yPy5tZXNzYWdlfWBcbiAgICAgICAgKTtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG4gICAgICBjb25zdCBuZXdJbnRlcm5hbEV2ZW50cyA9IGludGVybmFsRXZlbnRzUmVzcG9uc2UuZGF0YSB8fCBbXTtcbiAgICAgIGlmIChuZXdJbnRlcm5hbEV2ZW50cy5sZW5ndGggPiAwKSBldmVudHMucHVzaCguLi5uZXdJbnRlcm5hbEV2ZW50cyk7XG4gICAgfVxuXG4gICAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSBldmVudHNcbiAgICAgID8ubWFwKChlKSA9PiB7XG4gICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBsaXN0ZWRFdmVudHM/LmZpbmRJbmRleCgobCkgPT4gbD8uaWQgPT09IGU/LmlkKTtcbiAgICAgICAgaWYgKGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgIHJldHVybiBudWxsO1xuICAgICAgICB9XG4gICAgICAgIHJldHVybiBlO1xuICAgICAgfSlcbiAgICAgID8uZmlsdGVyKChlKSA9PiBlICE9PSBudWxsKTtcblxuICAgIHJldHVybiB7XG4gICAgICBldmVudHM6IGZpbHRlcmVkRXZlbnRzLFxuICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cyxcbiAgICAgIG5ld01lZXRpbmdFdmVudFBsdXM6IG5ld01lZXRpbmdFdmVudHMsXG4gICAgICBpbnRlcm5hbEF0dGVuZGVlcyxcbiAgICAgIGV4dGVybmFsQXR0ZW5kZWVzLFxuICAgIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGVhY2ggZnV0dXJlIG1lZXRpbmcgYXNzaXN0Jyk7XG4gIH1cbn07XG5cbmNvbnN0IHByb2Nlc3NBcHBseUZlYXR1cmVzID0gYXN5bmMgKFxuICBib2R5OiBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgaG9zdElkID0gYm9keT8udXNlcklkO1xuICAgIGNvbnN0IHdpbmRvd1N0YXJ0RGF0ZSA9IGJvZHk/LndpbmRvd1N0YXJ0RGF0ZTtcbiAgICBjb25zdCB3aW5kb3dFbmREYXRlID0gYm9keT8ud2luZG93RW5kRGF0ZTtcbiAgICBjb25zdCBob3N0VGltZXpvbmUgPSBib2R5Py50aW1lem9uZTtcblxuICAgIGNvbnN0IGV2ZW50czogRXZlbnRQbHVzVHlwZVtdID0gYXdhaXQgbGlzdEV2ZW50c0ZvckRhdGUoXG4gICAgICBob3N0SWQsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgaG9zdFRpbWV6b25lXG4gICAgKTtcbiAgICBjb25zdCBldmVudHNXaXRob3V0TWVldGluZ0Fzc2lzdDogRXZlbnRQbHVzVHlwZVtdID0gZXZlbnRzPy5maWx0ZXIoXG4gICAgICAoZSkgPT4gIWU/Lm1lZXRpbmdJZFxuICAgICk7XG5cbiAgICBjb25zdCB1c2VyTW9kaWZpZWRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG5ld01vZGlmaWVkUmVtaW5kZXJzOiBSZW1pbmRlcnNGb3JFdmVudFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG5ld01vZGlmaWVkQnVmZmVyVGltZXM6IEJ1ZmZlclRpbWVPYmplY3RUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgZXZlbnQgb2YgZXZlbnRzV2l0aG91dE1lZXRpbmdBc3Npc3QpIHtcbiAgICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoXG4gICAgICAgIGV2ZW50Py5pZFxuICAgICAgKTtcblxuICAgICAgaWYgKHByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudD8ubGVuZ3RoID4gMCkge1xuICAgICAgICBldmVudC5wcmVmZXJyZWRUaW1lUmFuZ2VzID0gcHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50O1xuICAgICAgfVxuXG4gICAgICAvLyAxLiBnZXQgZXZlbnRcbiAgICAgIGNvbnN0IHsgdXNlcklkIH0gPSBldmVudDtcbiAgICAgIGNvbnN0IHZlY3RvciA9IGF3YWl0IGdldEV2ZW50VmVjdG9yQnlJZChldmVudD8uaWQpOyAvLyBVc2UgbmV3IGZ1bmN0aW9uXG4gICAgICBjb25zb2xlLmxvZyh2ZWN0b3IsICcgdmVjdG9yJyk7XG5cbiAgICAgIC8vIDIuIGZpbmQgY2xvc2VzdCBldmVudFxuICAgICAgY29uc3QgdHJhaW5pbmdSZXN1bHQgPSBhd2FpdCBzZWFyY2hUcmFpbmluZ0RhdGFCeVZlY3Rvcih1c2VySWQsIHZlY3Rvcik7IC8vIFVzZSBuZXcgZnVuY3Rpb25cbiAgICAgIGNvbnNvbGUubG9nKHRyYWluaW5nUmVzdWx0LCAnIHRyYWluaW5nUmVzdWx0IGZyb20gTGFuY2VEQicpO1xuXG4gICAgICAvLyB2YWxpZGF0ZSByZXN1bHRzXG4gICAgICBpZiAoIXRyYWluaW5nUmVzdWx0Py5pZCAmJiAhZXZlbnQ/LnVzZXJNb2RpZmllZENhdGVnb3JpZXMpIHtcbiAgICAgICAgY29uc29sZS5sb2coJ25vIHRyYWluaW5nUmVzdWx0IGZvdW5kIGFuZCBubyB1c2VyIG1vZGlmaWVkIGNhdGVnb3JpZXMnKTtcbiAgICAgICAgLy8gbm8gcHJldmlvdXMgZXZlbnQgZm91bmQgdXNlIENhdGVnb3J5RGVmYXVsdHNcbiAgICAgICAgY29uc3QgeyBuZXdFdmVudCwgbmV3UmVtaW5kZXJzLCBuZXdCdWZmZXJUaW1lcyB9ID1cbiAgICAgICAgICBhd2FpdCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0cyhldmVudCwgdmVjdG9yKTtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICAgJyBuZXdFdmVudCBmb3IgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnXG4gICAgICAgICk7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgICAnIG5ld1JlbWluZGVycyBmb3IgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnXG4gICAgICAgICk7XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKG5ld0V2ZW50KTtcbiAgICAgICAgaWYgKG5ld1JlbWluZGVycykge1xuICAgICAgICAgIG5ld01vZGlmaWVkUmVtaW5kZXJzLnB1c2goe1xuICAgICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgICAgcmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgfSk7XG4gICAgICAgIH1cbiAgICAgICAgaWYgKG5ld0J1ZmZlclRpbWVzKSB7XG4gICAgICAgICAgbmV3TW9kaWZpZWRCdWZmZXJUaW1lcy5wdXNoKG5ld0J1ZmZlclRpbWVzKTtcbiAgICAgICAgfVxuICAgICAgICAvLyBBZGQgY3VycmVudCBldmVudCB0byB0cmFpbmluZyBkYXRhIGFzIG5vIHNpbWlsYXIgcGFzdCBldmVudCB3YXMgZm91bmRcbiAgICAgICAgY29uc3QgbmV3VHJhaW5pbmdFbnRyeTogVHJhaW5pbmdFdmVudFNjaGVtYSA9IHtcbiAgICAgICAgICBpZDogZXZlbnQuaWQsXG4gICAgICAgICAgdXNlcklkOiBldmVudC51c2VySWQsXG4gICAgICAgICAgdmVjdG9yOiB2ZWN0b3IsXG4gICAgICAgICAgc291cmNlX2V2ZW50X3RleHQ6IGAke2V2ZW50LnRpdGxlIHx8IGV2ZW50LnN1bW1hcnl9OiR7ZXZlbnQubm90ZXMgfHwgJyd9YCxcbiAgICAgICAgICBjcmVhdGVkX2F0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIH07XG4gICAgICAgIGF3YWl0IGFkZFRyYWluaW5nRGF0YShuZXdUcmFpbmluZ0VudHJ5KTtcbiAgICAgIH0gZWxzZSBpZiAoIXRyYWluaW5nUmVzdWx0Py5pZCAmJiBldmVudD8udXNlck1vZGlmaWVkQ2F0ZWdvcmllcykge1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAnbm8gdHJhaW5pbmdSZXN1bHQgZm91bmQgYnV0IGV2ZW50IGhhcyB1c2VyIG1vZGlmaWVkIGNhdGVnb3JpZXMnXG4gICAgICAgICk7XG4gICAgICAgIC8vIG5vIHByZXZpb3VzIGV2ZW50IGZvdW5kIHVzZSB1c2VyIG1vZGlmaWVkIGNhdGVnb3JpZXMgYW5kIGNhdGVnb3J5IGRlZmF1bHRzXG4gICAgICAgIGNvbnN0IGNhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdID0gYXdhaXQgbGlzdENhdGVnb3JpZXNGb3JFdmVudChcbiAgICAgICAgICBldmVudD8uaWRcbiAgICAgICAgKTtcbiAgICAgICAgY29uc29sZS5sb2coY2F0ZWdvcmllcywgJyBjYXRlZ29yaWVzJyk7XG4gICAgICAgIGlmIChjYXRlZ29yaWVzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgY29uc3QgeyBuZXdFdmVudCwgbmV3UmVtaW5kZXJzLCBuZXdCdWZmZXJUaW1lcyB9ID1cbiAgICAgICAgICAgIGF3YWl0IHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzV2l0aFVzZXJNb2RpZmllZENhdGVnb3JpZXMoXG4gICAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgICB2ZWN0b3JcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgICAgICcgbmV3RXZlbnQgZm9yIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzV2l0aFVzZXJNb2RpZmllZENhdGVnb3JpZXMnXG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgICcgbmV3UmVtaW5kZXJzIGZvciBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzJ1xuICAgICAgICAgICk7XG4gICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3RXZlbnQpO1xuICAgICAgICAgIGlmIChuZXdSZW1pbmRlcnMpIHtcbiAgICAgICAgICAgIG5ld01vZGlmaWVkUmVtaW5kZXJzLnB1c2goe1xuICAgICAgICAgICAgICBldmVudElkOiBuZXdFdmVudD8uaWQsXG4gICAgICAgICAgICAgIHJlbWluZGVyczogbmV3UmVtaW5kZXJzLFxuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgfVxuICAgICAgICAgIGlmIChuZXdCdWZmZXJUaW1lcykge1xuICAgICAgICAgICAgbmV3TW9kaWZpZWRCdWZmZXJUaW1lcy5wdXNoKG5ld0J1ZmZlclRpbWVzKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgLy8gQWRkIGN1cnJlbnQgZXZlbnQgdG8gdHJhaW5pbmcgZGF0YSBhcyBubyBzaW1pbGFyIHBhc3QgZXZlbnQgd2FzIGZvdW5kIGFuZCBubyBjYXRlZ29yaWVzIHRvIGd1aWRlIGRlZmF1bHRzXG4gICAgICAgICAgY29uc3QgbmV3VHJhaW5pbmdFbnRyeTogVHJhaW5pbmdFdmVudFNjaGVtYSA9IHtcbiAgICAgICAgICAgIGlkOiBldmVudC5pZCxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnQudXNlcklkLFxuICAgICAgICAgICAgdmVjdG9yOiB2ZWN0b3IsXG4gICAgICAgICAgICBzb3VyY2VfZXZlbnRfdGV4dDogYCR7ZXZlbnQudGl0bGUgfHwgZXZlbnQuc3VtbWFyeX06JHtldmVudC5ub3RlcyB8fCAnJ31gLFxuICAgICAgICAgICAgY3JlYXRlZF9hdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIH07XG4gICAgICAgICAgYXdhaXQgYWRkVHJhaW5pbmdEYXRhKG5ld1RyYWluaW5nRW50cnkpO1xuICAgICAgICAgIGV2ZW50LnZlY3RvciA9IHZlY3RvcjsgLy8gZW5zdXJlIHZlY3RvciBpcyBwYXJ0IG9mIHRoZSBldmVudCBpZiBwdXNoZWQgZGlyZWN0bHlcbiAgICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChldmVudCk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSBpZiAodHJhaW5pbmdSZXN1bHQ/LmlkICYmICFldmVudD8udXNlck1vZGlmaWVkQ2F0ZWdvcmllcykge1xuICAgICAgICAvLyBwcmV2aW91cyBldmVudCBmb3VuZCAodmlhIHRyYWluaW5nUmVzdWx0KSB1c2UgcHJldmlvdXMgZXZlbnQgdG8gY29weSBvdmVyIHZhbHVlc1xuICAgICAgICBjb25zdCBwcmV2aW91c0V2ZW50SWRGcm9tVHJhaW5pbmcgPSB0cmFpbmluZ1Jlc3VsdC5pZDsgLy8gVGhpcyBJRCBpcyBmcm9tIHRoZSB0cmFpbmluZyBkYXRhLCBhc3N1bWVkIHRvIGJlIHRoZSBnb29nbGVFdmVudElkIG9mIGEgcHJldmlvdXMgc2ltaWxhciBldmVudC5cbiAgICAgICAgY29uc3QgcHJldmlvdXNFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkoXG4gICAgICAgICAgcHJldmlvdXNFdmVudElkRnJvbVRyYWluaW5nXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKHByZXZpb3VzRXZlbnQ/LmlkKSB7XG4gICAgICAgICAgY29uc3QgcHJlZmVycmVkVGltZVJhbmdlcyA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoXG4gICAgICAgICAgICBwcmV2aW91c0V2ZW50SWRGcm9tVHJhaW5pbmdcbiAgICAgICAgICApO1xuICAgICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcyA9IHByZWZlcnJlZFRpbWVSYW5nZXM7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoIXByZXZpb3VzRXZlbnQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnRJZEZyb21UcmFpbmluZyxcbiAgICAgICAgICAgICd0cmFpbmluZ1Jlc3VsdC5pZCBpbnNpZGUgIXByZXZpb3VzRXZlbnQgJiYgIWV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzLiBUaGlzIG1lYW5zIHRoZSBsaW5rZWQgZXZlbnQgd2FzIGRlbGV0ZWQuJ1xuICAgICAgICAgICk7XG4gICAgICAgICAgYXdhaXQgZGVsZXRlVHJhaW5pbmdEYXRhQnlJZCh0cmFpbmluZ1Jlc3VsdC5pZCk7IC8vIERlbGV0ZSBzdGFsZSB0cmFpbmluZyBlbnRyeVxuICAgICAgICAgIC8vIEZhbGxiYWNrIHRvIGNhdGVnb3J5IGRlZmF1bHRzIGFzIHRoZSBcInNpbWlsYXJcIiBldmVudCBpcyBnb25lXG4gICAgICAgICAgY29uc3QgeyBuZXdFdmVudCwgbmV3UmVtaW5kZXJzLCBuZXdCdWZmZXJUaW1lcyB9ID1cbiAgICAgICAgICAgIGF3YWl0IHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzKGV2ZW50LCB2ZWN0b3IpO1xuICAgICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKG5ld0V2ZW50KTtcbiAgICAgICAgICBpZiAobmV3UmVtaW5kZXJzKSB7XG4gICAgICAgICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgIH1cbiAgICAgICAgICBpZiAobmV3QnVmZmVyVGltZXMpIHtcbiAgICAgICAgICAgIG5ld01vZGlmaWVkQnVmZmVyVGltZXMucHVzaChuZXdCdWZmZXJUaW1lcyk7XG4gICAgICAgICAgfVxuICAgICAgICAgIC8vIEFkZCBjdXJyZW50IGV2ZW50IHRvIHRyYWluaW5nIGRhdGEgYXMgdGhlIHByZXZpb3VzbHkgc2ltaWxhciBvbmUgd2FzIHN0YWxlXG4gICAgICAgICAgY29uc3QgbmV3VHJhaW5pbmdFbnRyeTogVHJhaW5pbmdFdmVudFNjaGVtYSA9IHtcbiAgICAgICAgICAgIGlkOiBldmVudC5pZCxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnQudXNlcklkLFxuICAgICAgICAgICAgdmVjdG9yOiB2ZWN0b3IsXG4gICAgICAgICAgICBzb3VyY2VfZXZlbnRfdGV4dDogYCR7ZXZlbnQudGl0bGUgfHwgZXZlbnQuc3VtbWFyeX06JHtldmVudC5ub3RlcyB8fCAnJ31gLFxuICAgICAgICAgICAgY3JlYXRlZF9hdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIH07XG4gICAgICAgICAgYXdhaXQgYWRkVHJhaW5pbmdEYXRhKG5ld1RyYWluaW5nRW50cnkpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGNvbnN0IHsgbmV3RXZlbnQsIG5ld1JlbWluZGVycywgbmV3QnVmZmVyVGltZXMgfSA9XG4gICAgICAgICAgICBhd2FpdCBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudChcbiAgICAgICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgICAgIHByZXZpb3VzRXZlbnRJZEZyb21UcmFpbmluZ1xuICAgICAgICAgICAgKTtcbiAgICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChuZXdFdmVudCk7XG4gICAgICAgICAgaWYgKG5ld1JlbWluZGVycykge1xuICAgICAgICAgICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMucHVzaCh7XG4gICAgICAgICAgICAgIGV2ZW50SWQ6IG5ld0V2ZW50Py5pZCxcbiAgICAgICAgICAgICAgcmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICB9XG4gICAgICAgICAgaWYgKG5ld0J1ZmZlclRpbWVzKSB7XG4gICAgICAgICAgICBuZXdNb2RpZmllZEJ1ZmZlclRpbWVzLnB1c2gobmV3QnVmZmVyVGltZXMpO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfSBlbHNlIGlmICh0cmFpbmluZ1Jlc3VsdD8uaWQgJiYgZXZlbnQ/LnVzZXJNb2RpZmllZENhdGVnb3JpZXMpIHtcbiAgICAgICAgY29uc3QgcHJldmlvdXNFdmVudElkRnJvbVRyYWluaW5nID0gdHJhaW5pbmdSZXN1bHQuaWQ7XG4gICAgICAgIGNvbnN0IHByZXZpb3VzRXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KFxuICAgICAgICAgIHByZXZpb3VzRXZlbnRJZEZyb21UcmFpbmluZ1xuICAgICAgICApO1xuICAgICAgICBpZiAocHJldmlvdXNFdmVudD8uaWQpIHtcbiAgICAgICAgICBjb25zdCBwcmVmZXJyZWRUaW1lUmFuZ2VzID0gYXdhaXQgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudChcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnRJZEZyb21UcmFpbmluZ1xuICAgICAgICAgICk7XG4gICAgICAgICAgcHJldmlvdXNFdmVudC5wcmVmZXJyZWRUaW1lUmFuZ2VzID0gcHJlZmVycmVkVGltZVJhbmdlcztcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghcHJldmlvdXNFdmVudCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgcHJldmlvdXNFdmVudElkRnJvbVRyYWluaW5nLFxuICAgICAgICAgICAgJ3RyYWluaW5nUmVzdWx0LmlkIGluc2lkZSAhcHJldmlvdXNFdmVudCAmJiBldmVudD8udXNlck1vZGlmaWVkQ2F0ZWdvcmllcy4gVGhpcyBtZWFucyB0aGUgbGlua2VkIGV2ZW50IHdhcyBkZWxldGVkLidcbiAgICAgICAgICApO1xuICAgICAgICAgIGF3YWl0IGRlbGV0ZVRyYWluaW5nRGF0YUJ5SWQodHJhaW5pbmdSZXN1bHQuaWQpOyAvLyBEZWxldGUgc3RhbGUgdHJhaW5pbmcgZW50cnlcbiAgICAgICAgICAvLyBGYWxsYmFjayB0byB1c2VyIG1vZGlmaWVkIGNhdGVnb3JpZXMgYXMgdGhlIFwic2ltaWxhclwiIGV2ZW50IGlzIGdvbmVcbiAgICAgICAgICBjb25zdCBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXSA9IGF3YWl0IGxpc3RDYXRlZ29yaWVzRm9yRXZlbnQoXG4gICAgICAgICAgICBldmVudD8uaWRcbiAgICAgICAgICApO1xuICAgICAgICAgIGlmIChjYXRlZ29yaWVzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld0J1ZmZlclRpbWVzIH0gPVxuICAgICAgICAgICAgICBhd2FpdCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzKFxuICAgICAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgICAgIHZlY3RvclxuICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3RXZlbnQpO1xuICAgICAgICAgICAgaWYgKG5ld1JlbWluZGVycykge1xuICAgICAgICAgICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgICAgICBldmVudElkOiBuZXdFdmVudD8uaWQsXG4gICAgICAgICAgICAgICAgcmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgaWYgKG5ld0J1ZmZlclRpbWVzKSB7XG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkQnVmZmVyVGltZXMucHVzaChuZXdCdWZmZXJUaW1lcyk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIC8vIEFkZCBjdXJyZW50IGV2ZW50IHRvIHRyYWluaW5nIGRhdGEgYXMgdGhlIHByZXZpb3VzbHkgc2ltaWxhciBvbmUgd2FzIHN0YWxlIGFuZCBubyBjYXRlZ29yaWVzIHRvIGd1aWRlXG4gICAgICAgICAgICBjb25zdCBuZXdUcmFpbmluZ0VudHJ5OiBUcmFpbmluZ0V2ZW50U2NoZW1hID0ge1xuICAgICAgICAgICAgICBpZDogZXZlbnQuaWQsXG4gICAgICAgICAgICAgIHVzZXJJZDogZXZlbnQudXNlcklkLFxuICAgICAgICAgICAgICB2ZWN0b3I6IHZlY3RvcixcbiAgICAgICAgICAgICAgc291cmNlX2V2ZW50X3RleHQ6IGAke2V2ZW50LnRpdGxlIHx8IGV2ZW50LnN1bW1hcnl9OiR7ZXZlbnQubm90ZXMgfHwgJyd9YCxcbiAgICAgICAgICAgICAgY3JlYXRlZF9hdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgfTtcbiAgICAgICAgICAgIGF3YWl0IGFkZFRyYWluaW5nRGF0YShuZXdUcmFpbmluZ0VudHJ5KTtcbiAgICAgICAgICAgIGV2ZW50LnZlY3RvciA9IHZlY3RvcjsgLy8gZW5zdXJlIHZlY3RvciBpcyBwYXJ0IG9mIHRoZSBldmVudFxuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goZXZlbnQpO1xuICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zdCBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXSA9IGF3YWl0IGxpc3RDYXRlZ29yaWVzRm9yRXZlbnQoXG4gICAgICAgICAgICBldmVudD8uaWRcbiAgICAgICAgICApO1xuICAgICAgICAgIGlmIChjYXRlZ29yaWVzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld0J1ZmZlclRpbWVzIH0gPVxuICAgICAgICAgICAgICBhd2FpdCBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudFdpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzKFxuICAgICAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgICAgIHByZXZpb3VzRXZlbnRJZEZyb21UcmFpbmluZ1xuICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3RXZlbnQpO1xuICAgICAgICAgICAgaWYgKG5ld1JlbWluZGVycykge1xuICAgICAgICAgICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgICAgICBldmVudElkOiBuZXdFdmVudD8uaWQsXG4gICAgICAgICAgICAgICAgcmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgaWYgKG5ld0J1ZmZlclRpbWVzKSB7XG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkQnVmZmVyVGltZXMucHVzaChuZXdCdWZmZXJUaW1lcyk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIC8vIE5vIGNhdGVnb3JpZXMsIGJ1dCBhIHByZXZpb3VzIGV2ZW50IHdhcyBmb3VuZC5cbiAgICAgICAgICAgIGNvbnN0IHVzZXJQcmVmZXJlbmNlcyA9IGF3YWl0IGdldFVzZXJQcmVmZXJlbmNlcyh1c2VySWQpO1xuICAgICAgICAgICAgY29uc3Qge1xuICAgICAgICAgICAgICBuZXdNb2RpZmllZEV2ZW50OiBuZXdNb2RpZmllZEV2ZW50MSxcbiAgICAgICAgICAgICAgbmV3UmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMxLFxuICAgICAgICAgICAgICBuZXdCdWZmZXJUaW1lczogbmV3VGltZUJsb2NraW5nMSxcbiAgICAgICAgICAgIH0gPSBhd2FpdCBwcm9jZXNzRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50V2l0aG91dENhdGVnb3JpZXMoXG4gICAgICAgICAgICAgIHByZXZpb3VzRXZlbnQsXG4gICAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKG5ld01vZGlmaWVkRXZlbnQxKTtcbiAgICAgICAgICAgIGlmIChuZXdSZW1pbmRlcnMxKSB7XG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkUmVtaW5kZXJzLnB1c2goe1xuICAgICAgICAgICAgICAgIGV2ZW50SWQ6IG5ld01vZGlmaWVkRXZlbnQxPy5pZCxcbiAgICAgICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVyczEsXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgaWYgKG5ld1RpbWVCbG9ja2luZzEpIHtcbiAgICAgICAgICAgICAgbmV3TW9kaWZpZWRCdWZmZXJUaW1lcy5wdXNoKG5ld1RpbWVCbG9ja2luZzEpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIHVzZXJNb2RpZmllZEV2ZW50cy5mb3JFYWNoKChlKSA9PlxuICAgICAgY29uc29sZS5sb2coZSwgJyB1c2VyTW9kaWZpZWRFdmVudCBiZWZvcmUgcHJvY2Vzc2luZyBmb3IgT3B0YXBsYW5uZXInKVxuICAgICk7XG4gICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMuZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgbmV3TW9kaWZpZWRSZW1pbmRlcnMgYmVmb3JlIHByb2Nlc3NpbmcgZm9yIE9wdGFwbGFubmVyJylcbiAgICApO1xuXG4gICAgY29uc3QgZXZlbnRzV2l0aE1lZXRpbmdJZCA9IGV2ZW50cy5maWx0ZXIoKGUpID0+ICEhZT8ubWVldGluZ0lkKTtcblxuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG1lZXRpbmdFdmVudFBsdXM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10gPSBbXTtcbiAgICBjb25zdCBpbnRlcm5hbEF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdID0gW107XG4gICAgY29uc3QgZXh0ZXJuYWxBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IGZpbHRlcmVkRXZlbnRzOiBFdmVudFR5cGVbXSA9IFtdO1xuXG4gICAgLyoqXG4gICAgICogcXVldWUgZm9yIGVhY2hcbiAgICAgKiBwYXJlbnRLZXk6IGhvc3RJZC9zaW5nbGV0b25JZFxuICAgICAqIG9sZENoaWxkS2V5OiBob3N0SWQvbWVldGluZ0lkXG4gICAgICovXG5cbiAgICBmaWx0ZXJlZEV2ZW50cy5wdXNoKC4uLnVzZXJNb2RpZmllZEV2ZW50cyk7XG4gICAgZmlsdGVyZWRFdmVudHMucHVzaCguLi5ldmVudHNXaXRoTWVldGluZ0lkKTtcblxuICAgIGZvciAoY29uc3QgZXZlbnRXaXRoTWVldGluZ0lkIG9mIGV2ZW50c1dpdGhNZWV0aW5nSWQpIHtcbiAgICAgIGNvbnN0IHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nID0gYXdhaXQgcHJvY2Vzc0VhY2hNZWV0aW5nQXNzaXN0KFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgZXZlbnRXaXRoTWVldGluZ0lkPy5tZWV0aW5nSWQsXG4gICAgICAgIGV2ZW50V2l0aE1lZXRpbmdJZCxcbiAgICAgICAgZXZlbnRzXG4gICAgICApO1xuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBjb25zdCBuZXdFdmVudHMgPSByZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uZXZlbnRzO1xuXG4gICAgICAgIGZpbHRlcmVkRXZlbnRzLnB1c2goLi4ubmV3RXZlbnRzKTtcbiAgICAgICAgZXZlbnRzLnB1c2goLi4ubmV3RXZlbnRzKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5tZWV0aW5nQXNzaXN0RXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMucHVzaChcbiAgICAgICAgICAuLi5yZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8ubWVldGluZ0Fzc2lzdEV2ZW50c1xuICAgICAgICApO1xuICAgICAgfVxuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/Lm1lZXRpbmdFdmVudHNQbHVzKSB7XG4gICAgICAgIG1lZXRpbmdFdmVudFBsdXMucHVzaCguLi5yZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8ubWVldGluZ0V2ZW50c1BsdXMpO1xuICAgICAgfVxuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmludGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgIGludGVybmFsQXR0ZW5kZWVzLnB1c2goXG4gICAgICAgICAgLi4ucmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmludGVybmFsQXR0ZW5kZWVzXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZXMucHVzaChcbiAgICAgICAgICAuLi5yZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uZXh0ZXJuYWxBdHRlbmRlZXNcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBmdXR1cmUgbWVldGluZyBhc3Npc3RzXG4gICAgY29uc3QgbWVldGluZ0lkc1RvTm90SW5jbHVkZSA9IGV2ZW50c1dpdGhNZWV0aW5nSWQubWFwKChlKSA9PiBlPy5tZWV0aW5nSWQpO1xuXG4gICAgY29uc29sZS5sb2cobWVldGluZ0lkc1RvTm90SW5jbHVkZSwgJyBtZWV0aW5nSWRzVG9Ob3RJbmNsdWRlJyk7XG5cbiAgICBjb25zdCBuZXdNZWV0aW5nQXNzaXN0c05vVGhyZXNob2xkID0gYXdhaXQgbGlzdEZ1dHVyZU1lZXRpbmdBc3Npc3RzKFxuICAgICAgaG9zdElkLFxuICAgICAgZGF5anMod2luZG93U3RhcnREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lKS5mb3JtYXQoKSxcbiAgICAgIGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUpLmFkZCgxLCAnZCcpLmZvcm1hdCgpLFxuICAgICAgbWVldGluZ0lkc1RvTm90SW5jbHVkZVxuICAgICk7XG5cbiAgICBjb25zb2xlLmxvZyhuZXdNZWV0aW5nQXNzaXN0c05vVGhyZXNob2xkLCAnIG5ld01lZXRpbmdBc3Npc3RzTm9UaHJlc2hvbGQnKTtcblxuICAgIGNvbnN0IG5ld01lZXRpbmdFdmVudFBsdXM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10gPSBbXTtcbiAgICBjb25zdCBuZXdNZWV0aW5nQXNzaXN0c0FjdGl2ZTogTWVldGluZ0Fzc2lzdFR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBmdXR1cmVNZWV0aW5nQXNzaXN0IG9mIG5ld01lZXRpbmdBc3Npc3RzTm9UaHJlc2hvbGQpIHtcbiAgICAgIGNvbnN0IGNvdW50ID0gYXdhaXQgbWVldGluZ0F0dGVuZGVlQ291bnRHaXZlbk1lZXRpbmdJZChcbiAgICAgICAgZnV0dXJlTWVldGluZ0Fzc2lzdD8uaWRcbiAgICAgICk7XG5cbiAgICAgIGlmIChjb3VudCA+PSBmdXR1cmVNZWV0aW5nQXNzaXN0Py5taW5UaHJlc2hvbGRDb3VudCkge1xuICAgICAgICBuZXdNZWV0aW5nQXNzaXN0c0FjdGl2ZS5wdXNoKGZ1dHVyZU1lZXRpbmdBc3Npc3QpO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8qKlxuICAgICAqIHF1ZXVlIGZvciBlYWNoXG4gICAgICogcGFyZW50S2V5OiBob3N0SWQvc2luZ2xldG9uSWRcbiAgICAgKiBuZXdDaGlsZEtleTogaG9zdElkL21lZXRpbmdJZFxuICAgICAqL1xuICAgIGZvciAoY29uc3QgZnV0dXJlTWVldGluZ0Fzc2lzdEFjdGl2ZSBvZiBuZXdNZWV0aW5nQXNzaXN0c0FjdGl2ZSkge1xuICAgICAgY29uc3QgcmV0dXJuVmFsdWVzRnJvbUZ1dHVyZU1lZXRpbmdBc3Npc3QgPVxuICAgICAgICBhd2FpdCBwcm9jZXNzRWFjaEZ1dHVyZU1lZXRpbmdBc3Npc3QoXG4gICAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgICAgZnV0dXJlTWVldGluZ0Fzc2lzdEFjdGl2ZT8uaWQsXG4gICAgICAgICAgZXZlbnRzXG4gICAgICAgICk7XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXNGcm9tRnV0dXJlTWVldGluZ0Fzc2lzdD8uZXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGNvbnN0IG5ld0V2ZW50cyA9IHJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5ldmVudHM7XG5cbiAgICAgICAgZmlsdGVyZWRFdmVudHMucHVzaCguLi5uZXdFdmVudHMpO1xuICAgICAgICBldmVudHMucHVzaCguLi5uZXdFdmVudHMpO1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIHJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5tZWV0aW5nQXNzaXN0RXZlbnRzPy5sZW5ndGggPiAwXG4gICAgICApIHtcbiAgICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cy5wdXNoKFxuICAgICAgICAgIC4uLnJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5tZWV0aW5nQXNzaXN0RXZlbnRzXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgcmV0dXJuVmFsdWVzRnJvbUZ1dHVyZU1lZXRpbmdBc3Npc3Q/Lm5ld01lZXRpbmdFdmVudFBsdXM/Lmxlbmd0aCA+IDBcbiAgICAgICkge1xuICAgICAgICBuZXdNZWV0aW5nRXZlbnRQbHVzLnB1c2goXG4gICAgICAgICAgLi4ucmV0dXJuVmFsdWVzRnJvbUZ1dHVyZU1lZXRpbmdBc3Npc3Q/Lm5ld01lZXRpbmdFdmVudFBsdXNcbiAgICAgICAgKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5pbnRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgICBpbnRlcm5hbEF0dGVuZGVlcy5wdXNoKFxuICAgICAgICAgIC4uLnJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5pbnRlcm5hbEF0dGVuZGVlc1xuICAgICAgICApO1xuICAgICAgfVxuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRnJvbUZ1dHVyZU1lZXRpbmdBc3Npc3Q/LmV4dGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzLnB1c2goXG4gICAgICAgICAgLi4ucmV0dXJuVmFsdWVzRnJvbUZ1dHVyZU1lZXRpbmdBc3Npc3Q/LmV4dGVybmFsQXR0ZW5kZWVzXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIHByb2Nlc3NFdmVudHNGb3JQbGFubmluZyhcbiAgICAgIGhvc3RJZCxcbiAgICAgIF8udW5pcVdpdGgoaW50ZXJuYWxBdHRlbmRlZXMsIF8uaXNFcXVhbCksXG4gICAgICBtZWV0aW5nRXZlbnRQbHVzLFxuICAgICAgbmV3TWVldGluZ0V2ZW50UGx1cyxcbiAgICAgIG5ld01lZXRpbmdBc3Npc3RzQWN0aXZlLFxuICAgICAgXy51bmlxV2l0aChmaWx0ZXJlZEV2ZW50cywgXy5pc0VxdWFsKSxcbiAgICAgIGV2ZW50cyxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBfLnVuaXFXaXRoKGV4dGVybmFsQXR0ZW5kZWVzLCBfLmlzRXF1YWwpLFxuICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cz8ubGVuZ3RoID4gMFxuICAgICAgICA/IF8udW5pcVdpdGgobWVldGluZ0Fzc2lzdEV2ZW50cywgXy5pc0VxdWFsKVxuICAgICAgICA6IG51bGxcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBtZWV0aW5nIGFzc2lzdCcpO1xuICB9XG59O1xuXG5jb25zdCBwcm9jZXNzUXVldWVNZXNzYWdlID0gYXN5bmMgKFxuICBib2R5OiBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgdXNlcklkID0gYm9keT8udXNlcklkO1xuICAgIGNvbnN0IHdpbmRvd1N0YXJ0RGF0ZSA9IGJvZHk/LndpbmRvd1N0YXJ0RGF0ZTtcbiAgICBjb25zdCB3aW5kb3dFbmREYXRlID0gYm9keT8ud2luZG93RW5kRGF0ZTtcbiAgICBjb25zdCB0aW1lem9uZSA9IGJvZHk/LnRpbWV6b25lO1xuXG4gICAgLy8gQ2VudHJhbGl6ZWQgdmFsaWRhdGlvbiBmb3IgdGhlIG1lc3NhZ2UgYm9keSBpdHNlbGZcbiAgICBpZiAoIXVzZXJJZCB8fCAhd2luZG93U3RhcnREYXRlIHx8ICF3aW5kb3dFbmREYXRlIHx8ICF0aW1lem9uZSkge1xuICAgICAgY29uc3QgbWlzc2luZ1BhcmFtcyA9IFtcbiAgICAgICAgIXVzZXJJZCAmJiAndXNlcklkJyxcbiAgICAgICAgIXdpbmRvd1N0YXJ0RGF0ZSAmJiAnd2luZG93U3RhcnREYXRlJyxcbiAgICAgICAgIXdpbmRvd0VuZERhdGUgJiYgJ3dpbmRvd0VuZERhdGUnLFxuICAgICAgICAhdGltZXpvbmUgJiYgJ3RpbWV6b25lJyxcbiAgICAgIF1cbiAgICAgICAgLmZpbHRlcihCb29sZWFuKVxuICAgICAgICAuam9pbignLCAnKTtcbiAgICAgIGNvbnN0IGVycm9yID0gbmV3IEVycm9yKFxuICAgICAgICBgSW52YWxpZCBtZXNzYWdlIHBheWxvYWQ6IE1pc3NpbmcgJHttaXNzaW5nUGFyYW1zfWBcbiAgICAgICk7XG4gICAgICAvLyBAdHMtaWdub3JlIC8vIEFkZCBjdXN0b20gcHJvcGVydHkgZm9yIHN0cnVjdHVyZWQgbG9nZ2luZy9oYW5kbGluZyBpZiBuZWVkZWRcbiAgICAgIGVycm9yLmNvZGUgPSAnTUVTU0FHRV9WQUxJREFUSU9OX0VSUk9SJztcbiAgICAgIHRocm93IGVycm9yO1xuICAgIH1cblxuICAgIHJldHVybiBhd2FpdCBwcm9jZXNzQXBwbHlGZWF0dXJlcyhib2R5KTsgLy8gUHJvcGFnYXRlIHJlc3VsdCBvciBlcnJvclxuICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAvLyBDYXRjaCBlcnJvcnMgZnJvbSBwcm9jZXNzQXBwbHlGZWF0dXJlcyBvciB2YWxpZGF0aW9uXG4gICAgY29uc29sZS5lcnJvcihcbiAgICAgIGBFcnJvciBpbiBwcm9jZXNzUXVldWVNZXNzYWdlIGZvciB1c2VySWQgJHtib2R5Py51c2VySWR9OiAke2UubWVzc2FnZX1gLFxuICAgICAgZVxuICAgICk7XG4gICAgLy8gUmUtdGhyb3cgdGhlIGVycm9yIHRvIGJlIGNhdWdodCBieSB0aGUgS2Fma2EgY29uc3VtZXIncyBlYWNoTWVzc2FnZVxuICAgIHRocm93IGU7XG4gIH1cbn07XG5cbmNvbnN0IHNjaGVkdWxlTWVldGluZ1dvcmtlciA9IGFzeW5jICgpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjb25zdW1lciA9IGthZmthLmNvbnN1bWVyKHsgZ3JvdXBJZDoga2Fma2FGZWF0dXJlc0FwcGx5R3JvdXBJZCB9KTtcbiAgICBhd2FpdCBjb25zdW1lci5jb25uZWN0KCk7XG4gICAgYXdhaXQgY29uc3VtZXIuc3Vic2NyaWJlKHsgdG9waWM6IGthZmthRmVhdHVyZXNBcHBseVRvcGljIH0pO1xuXG4gICAgYXdhaXQgY29uc3VtZXIucnVuKHtcbiAgICAgIGVhY2hNZXNzYWdlOiBhc3luYyAoeyB0b3BpYywgcGFydGl0aW9uLCBtZXNzYWdlIH0pID0+IHtcbiAgICAgICAgY29uc29sZS5sb2coe1xuICAgICAgICAgIGtleTogbWVzc2FnZT8ua2V5Py50b1N0cmluZygpLFxuICAgICAgICAgIHZhbHVlOiBtZXNzYWdlPy52YWx1ZT8udG9TdHJpbmcoKSxcbiAgICAgICAgICBoZWFkZXJzOiBtZXNzYWdlPy5oZWFkZXJzLFxuICAgICAgICB9KTtcblxuICAgICAgICBsZXQgbWVzc2FnZVBheWxvYWQ6IFNjaGVkdWxlQXNzaXN0V2l0aE1lZXRpbmdRdWV1ZUJvZHlUeXBlIHwgbnVsbCA9XG4gICAgICAgICAgbnVsbDtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICBpZiAoIW1lc3NhZ2U/LnZhbHVlKSB7XG4gICAgICAgICAgICAvLyBUaGlzIGVycm9yIGlzIGFib3V0IEthZmthIG1lc3NhZ2UgaW50ZWdyaXR5LCBub3QgYnVzaW5lc3MgbG9naWMgdmFsaWRhdGlvblxuICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdLYWZrYSBtZXNzYWdlIHZhbHVlIGlzIG51bGwgb3IgdW5kZWZpbmVkLicpO1xuICAgICAgICAgIH1cbiAgICAgICAgICBtZXNzYWdlUGF5bG9hZCA9IEpTT04ucGFyc2UobWVzc2FnZS52YWx1ZS50b1N0cmluZygpKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhtZXNzYWdlUGF5bG9hZCwgJyBtZXNzYWdlUGF5bG9hZCcpO1xuICAgICAgICAgIGF3YWl0IHByb2Nlc3NRdWV1ZU1lc3NhZ2UobWVzc2FnZVBheWxvYWQhKTtcbiAgICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICAgIGBGYWlsZWQgdG8gcHJvY2VzcyBLYWZrYSBtZXNzYWdlIGZyb20gdG9waWMgJHt0b3BpY30sIHBhcnRpdGlvbiAke3BhcnRpdGlvbn06ICR7ZS5tZXNzYWdlfWAsXG4gICAgICAgICAgICB7XG4gICAgICAgICAgICAgIG1lc3NhZ2VLZXk6IG1lc3NhZ2U/LmtleT8udG9TdHJpbmcoKSxcbiAgICAgICAgICAgICAgZXJyb3JNZXNzYWdlOiBlLm1lc3NhZ2UsXG4gICAgICAgICAgICAgIGVycm9yQ29kZTogZS5jb2RlLFxuICAgICAgICAgICAgICBlcnJvclN0YWNrOiBlLnN0YWNrLFxuICAgICAgICAgICAgICBvcmlnaW5hbFBheWxvYWQ6IG1lc3NhZ2U/LnZhbHVlPy50b1N0cmluZygpLFxuICAgICAgICAgICAgfVxuICAgICAgICAgICk7XG4gICAgICAgICAgLy8gUmUtdGhyb3cgdGhlIGVycm9yIHRvIHV0aWxpemUgS2Fma2EncyByZXRyeS9ETFEgbWVjaGFuaXNtcyBpZiBjb25maWd1cmVkLlxuICAgICAgICAgIHRocm93IGU7XG4gICAgICAgIH1cbiAgICAgIH0sXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoJ0thZmthIGNvbnN1bWVyIGVycm9yIGluIHNjaGVkdWxlTWVldGluZ1dvcmtlcjonLCBlKTtcbiAgICAvLyBUaGlzIGVycm9yIGlzIGxpa2VseSBhIGNvbm5lY3Rpb24gb3Igc3Vic2NyaXB0aW9uIGlzc3VlIHdpdGggS2Fma2EgaXRzZWxmLlxuICAgIHRocm93IGU7IC8vIFJlLXRocm93IHRvIG1ha2UgdGhlIHdvcmtlciBjcmFzaCBhbmQgcmVzdGFydCBpZiBtYW5hZ2VkIGJ5IFBNMi9LdWJlcm5ldGVzXG4gIH1cbn07XG5cbmV4cG9ydCBkZWZhdWx0IHNjaGVkdWxlTWVldGluZ1dvcmtlcjtcbiJdfQ==