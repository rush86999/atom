import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import { listEventsForUserGivenDates, listMeetingAssistAttendeesGivenMeetingId, listMeetingAssistEventsForAttendeeGivenDates, listMeetingAssistPreferredTimeRangesGivenMeetingId, listPreferredTimeRangesForEvent, processEventsForOptaPlanner, listEventsForDate, convertMeetingAssistEventTypeToEventPlusType, processUserEventForCategoryDefaults, listCategoriesForEvent, processUserEventForCategoryDefaultsWithUserModifiedCategories, getEventFromPrimaryKey, 
// deleteDocInSearch3, // Replaced
processUserEventWithFoundPreviousEvent, processUserEventWithFoundPreviousEventWithUserModifiedCategories, getUserPreferences, processEventWithFoundPreviousEventWithoutCategories, 
// searchTrainEventIndexInOpenSearch, // Replaced
// getVectorInAllEventIndexInOpenSearch, // Replaced
searchTrainingDataByVector, // Added
getEventVectorById, // Added
deleteTrainingDataById, // Added
addTrainingData, // Added
 } from '@schedule_event/_libs/api-helper';
import { kafkaScheduleEventGroupId, kafkaScheduleEventTopic, } from '../_libs/constants';
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
totalEvents, oldEvents, windowStartDate, windowEndDate, hostTimezone, externalAttendees, meetingAssistEvents) => {
    try {
        const events = _.cloneDeep(totalEvents);
        const userModifiedEvents = [];
        for (const event of events) {
            // get preferredTimeRanges
            const preferredTimeRanges = await listPreferredTimeRangesForEvent(event?.id);
            preferredTimeRanges?.map((pt) => console.log(pt, ' preferredTimeRange inside processUserEventsForPlanning'));
            if (preferredTimeRanges?.length > 0) {
                preferredTimeRanges?.map((pt) => console.log(pt, ' preferredTimeRange inside processUserEventsForPlanning'));
                userModifiedEvents.push({
                    ...event,
                    preferredTimeRanges: preferredTimeRanges,
                });
            }
            else {
                userModifiedEvents.push(event);
            }
        }
        return processEventsForOptaPlanner(mainHostId, internalAttendees, meetingEventPlus, [], userModifiedEvents, windowStartDate, windowEndDate, hostTimezone, oldEvents, externalAttendees, meetingAssistEvents, [], []);
    }
    catch (e) {
        console.log(e, ' unable to process events for planning');
    }
};
const processEachMeetingAssist = async (windowStartDate, windowEndDate, hostTimezone, meetingId, meetingEvent, listedEvents) => {
    try {
        const attendees = await listMeetingAssistAttendeesGivenMeetingId(meetingId);
        const externalAttendees = attendees.filter((a) => !!a?.externalAttendee);
        const internalAttendees = attendees.filter((a) => !a?.externalAttendee);
        // original meeting asssit events
        const meetingAssistEvents = [];
        // events for each user
        const events = [];
        // events with a meetingId
        const meetingEvents = [];
        meetingEvents.push(meetingEvent);
        // get events
        if (externalAttendees?.length > 0) {
            for (let i = 0; i < externalAttendees?.length; i++) {
                const newMeetingAssistEvents = await listMeetingAssistEventsForAttendeeGivenDates(externalAttendees[i].id, windowStartDate, windowEndDate, externalAttendees[i].timezone, hostTimezone);
                const meetingAssistEventForMeeting = newMeetingAssistEvents.find((m) => m.meetingId === meetingId);
                const filteredMeetingAssistEvents = newMeetingAssistEvents.filter((e) => e?.meetingId !== meetingId);
                meetingAssistEvents.push(...filteredMeetingAssistEvents);
                if (meetingAssistEventForMeeting?.id) {
                    meetingEvents.push(convertMeetingAssistEventTypeToEventPlusType(meetingAssistEventForMeeting, externalAttendees[i]?.userId));
                }
            }
        }
        for (let i = 0; i < internalAttendees.length; i++) {
            const newEvents = await listEventsForUserGivenDates(internalAttendees[i].userId, windowStartDate, windowEndDate, internalAttendees[i].timezone, hostTimezone);
            const meetingAssistEventForMeeting = newEvents.find((e) => e?.meetingId === meetingId);
            const filteredNewEvents = newEvents.filter((e) => e?.meetingId !== meetingId);
            events.push(...filteredNewEvents);
            if (meetingAssistEventForMeeting?.id) {
                meetingEvents.push(meetingAssistEventForMeeting);
            }
        }
        const preferredTimesRanges = await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);
        const newUserModifiedMeetingEvents = meetingEvents.map((me) => ({
            ...me,
            preferredTimeRanges: preferredTimesRanges,
        }));
        const userModifiedEvents = [];
        for (const event of events) {
            // get preferredTimeRanges
            const preferredTimeRanges = await listPreferredTimeRangesForEvent(event?.id);
            if (preferredTimeRanges?.length > 0) {
                preferredTimeRanges?.map((pt) => console.log(pt, ' preferredTimeRange inside processUserEventsForPlanning'));
                userModifiedEvents.push({
                    ...event,
                    preferredTimeRanges: preferredTimeRanges,
                });
            }
            else {
                userModifiedEvents.push(event);
            }
        }
        const filteredEvents = userModifiedEvents
            ?.map((e) => {
            const foundIndex = listedEvents.findIndex((l) => l?.id === e?.id);
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
const processEventApplyFeatures = async (event) => {
    try {
        const hostId = event?.userId;
        const windowStartDate = dayjs(event?.startDate?.slice(0, 19))
            .tz(event?.timezone, true)
            .add(1, 'h')
            .minute(0)
            .format();
        const windowEndDate = dayjs(event?.startDate?.slice(0, 19))
            .tz(event?.timezone, true)
            .add(6, 'd')
            .format();
        const hostTimezone = event?.timezone;
        const preferredTimeRangesForEvent = await listPreferredTimeRangesForEvent(event?.id);
        event.preferredTimeRanges = preferredTimeRangesForEvent;
        const events = await listEventsForDate(hostId, windowStartDate, windowEndDate, hostTimezone);
        const userModifiedEvents = [];
        const newModifiedReminders = [];
        const newModifiedTimeBlockings = [];
        userModifiedEvents.push(...events);
        // 1. convert to vector space
        const { userId } = event;
        const vector = await getEventVectorById(event?.id);
        console.log(vector, ' vector');
        if (!vector) {
            // If no vector, cannot find similar events or add to training.
            // Proceed with default category processing or just push the event.
            console.log(`No vector found for event ${event.id}. Applying default category processing.`);
            if (!event?.userModifiedCategories) {
                const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaults(event, null); // Pass null for vector
                userModifiedEvents.push(newEvent);
                if (newReminders)
                    newModifiedReminders.push({
                        eventId: newEvent?.id,
                        reminders: newReminders,
                    });
                if (newTimeBlocking)
                    newModifiedTimeBlockings.push(newTimeBlocking);
            }
            else {
                const categories = await listCategoriesForEvent(event?.id);
                if (categories?.[0]?.id) {
                    const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaultsWithUserModifiedCategories(event, null); // Pass null for vector
                    userModifiedEvents.push(newEvent);
                    if (newReminders)
                        newModifiedReminders.push({
                            eventId: newEvent?.id,
                            reminders: newReminders,
                        });
                    if (newTimeBlocking)
                        newModifiedTimeBlockings.push(newTimeBlocking);
                }
                else {
                    userModifiedEvents.push(event); // No categories, no vector, push as is
                }
            }
        }
        else {
            // Vector exists, proceed with search/training logic
            const trainingResult = await searchTrainingDataByVector(userId, vector);
            console.log(trainingResult, ' trainingResult from LanceDB');
            if (!trainingResult?.id && !event?.userModifiedCategories) {
                console.log('no training result found and no user modified categories');
                const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaults(event, vector);
                userModifiedEvents.push(newEvent);
                if (newReminders)
                    newModifiedReminders.push({
                        eventId: newEvent?.id,
                        reminders: newReminders,
                    });
                if (newTimeBlocking)
                    newModifiedTimeBlockings.push(newTimeBlocking);
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
                console.log('no training result found but event has user modified categories');
                const categories = await listCategoriesForEvent(event?.id);
                if (categories?.[0]?.id) {
                    const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaultsWithUserModifiedCategories(event, vector);
                    userModifiedEvents.push(newEvent);
                    if (newReminders)
                        newModifiedReminders.push({
                            eventId: newEvent?.id,
                            reminders: newReminders,
                        });
                    if (newTimeBlocking)
                        newModifiedTimeBlockings.push(newTimeBlocking);
                }
                else {
                    const newTrainingEntry = {
                        id: event.id,
                        userId: event.userId,
                        vector: vector,
                        source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
                        created_at: dayjs().toISOString(),
                    };
                    await addTrainingData(newTrainingEntry);
                    event.vector = vector;
                    userModifiedEvents.push(event);
                }
            }
            else if (trainingResult?.id && !event?.userModifiedCategories) {
                const previousEventIdFromTraining = trainingResult.id;
                const previousEvent = await getEventFromPrimaryKey(previousEventIdFromTraining);
                if (previousEvent?.id) {
                    const preferredTimeRanges = await listPreferredTimeRangesForEvent(previousEventIdFromTraining);
                    previousEvent.preferredTimeRanges = preferredTimeRanges;
                }
                if (!previousEvent) {
                    console.log(previousEventIdFromTraining, 'trainingResult.id points to a deleted event.');
                    await deleteTrainingDataById(trainingResult.id);
                    const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaults(event, vector);
                    userModifiedEvents.push(newEvent);
                    if (newReminders)
                        newModifiedReminders.push({
                            eventId: newEvent?.id,
                            reminders: newReminders,
                        });
                    if (newTimeBlocking)
                        newModifiedTimeBlockings.push(newTimeBlocking);
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
                    const { newEvent, newReminders, newTimeBlocking } = await processUserEventWithFoundPreviousEvent(event, previousEventIdFromTraining);
                    userModifiedEvents.push(newEvent);
                    if (newReminders)
                        newModifiedReminders.push({
                            eventId: newEvent?.id,
                            reminders: newReminders,
                        });
                    if (newTimeBlocking)
                        newModifiedTimeBlockings.push(newTimeBlocking);
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
                    console.log(previousEventIdFromTraining, 'trainingResult.id points to a deleted event and event has user modified categories.');
                    await deleteTrainingDataById(trainingResult.id);
                    const categories = await listCategoriesForEvent(event?.id);
                    if (categories?.[0]?.id) {
                        const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaultsWithUserModifiedCategories(event, vector);
                        userModifiedEvents.push(newEvent);
                        if (newReminders)
                            newModifiedReminders.push({
                                eventId: newEvent?.id,
                                reminders: newReminders,
                            });
                        if (newTimeBlocking)
                            newModifiedTimeBlockings.push(newTimeBlocking);
                    }
                    else {
                        const newTrainingEntry = {
                            id: event.id,
                            userId: event.userId,
                            vector: vector,
                            source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
                            created_at: dayjs().toISOString(),
                        };
                        await addTrainingData(newTrainingEntry);
                        event.vector = vector;
                        userModifiedEvents.push(event);
                    }
                }
                else {
                    const categories = await listCategoriesForEvent(event?.id);
                    if (categories?.[0]?.id) {
                        const { newEvent, newReminders, newTimeBlocking } = await processUserEventWithFoundPreviousEventWithUserModifiedCategories(event, previousEventIdFromTraining);
                        userModifiedEvents.push(newEvent);
                        if (newReminders)
                            newModifiedReminders.push({
                                eventId: newEvent?.id,
                                reminders: newReminders,
                            });
                        if (newTimeBlocking)
                            newModifiedTimeBlockings.push(newTimeBlocking);
                    }
                    else {
                        console.log('no categories found, but previous event found');
                        const userPreferences = await getUserPreferences(userId);
                        const { newModifiedEvent: newModifiedEvent1, newReminders: newReminders1, newTimeBlocking: newTimeBlocking1, } = await processEventWithFoundPreviousEventWithoutCategories(previousEvent, event, userPreferences, userId);
                        userModifiedEvents.push(newModifiedEvent1);
                        if (newReminders1)
                            newModifiedReminders.push({
                                eventId: newModifiedEvent1?.id,
                                reminders: newReminders1,
                            });
                        if (newTimeBlocking1)
                            newModifiedTimeBlockings.push(newTimeBlocking1);
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
        return processEventsForPlanning(hostId, _.uniqWith(internalAttendees, _.isEqual), meetingEventPlus, _.uniqWith(filteredEvents, _.isEqual), events, windowStartDate, windowEndDate, hostTimezone, _.uniqWith(externalAttendees, _.isEqual), meetingAssistEvents?.length > 0
            ? _.uniqWith(meetingAssistEvents, _.isEqual)
            : null);
    }
    catch (e) {
        console.log(e, ' unable to process meeting assist');
    }
};
const processQueueMessage = async (event) => {
    try {
        if (!event?.id) {
            throw new Error('no userId provided inside atomic meeting assist');
        }
        return processEventApplyFeatures(event);
    }
    catch (e) {
        console.log(e, ' unable to processQueueMessage inside atomic meeting assist');
    }
};
const scheduleEventWorker = async (event) => {
    try {
        const consumer = kafka.consumer({ groupId: kafkaScheduleEventGroupId });
        await consumer.connect();
        await consumer.subscribe({ topic: kafkaScheduleEventTopic });
        await consumer.run({
            eachMessage: async ({ topic, partition, message }) => {
                console.log({
                    key: message?.key?.toString(),
                    value: message?.value?.toString(),
                    headers: message?.headers,
                });
                const body = JSON.parse(message?.value?.toString());
                console.log(body, ' body');
                await processQueueMessage(body);
            },
        });
    }
    catch (e) {
        console.log(e, ' unable to assist for meeting');
    }
};
export default scheduleEventWorker;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEtBQUssTUFBTSxPQUFPLENBQUM7QUFDMUIsT0FBTyxPQUFPLE1BQU0sc0JBQXNCLENBQUM7QUFDM0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxTQUFTLE1BQU0sd0JBQXdCLENBQUM7QUFDL0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxHQUFHLE1BQU0sa0JBQWtCLENBQUM7QUFHbkMsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBQ3ZCLE9BQU8sRUFDTCwyQkFBMkIsRUFDM0Isd0NBQXdDLEVBQ3hDLDRDQUE0QyxFQUM1QyxrREFBa0QsRUFDbEQsK0JBQStCLEVBQy9CLDJCQUEyQixFQUMzQixpQkFBaUIsRUFDakIsNENBQTRDLEVBQzVDLG1DQUFtQyxFQUNuQyxzQkFBc0IsRUFDdEIsNkRBQTZELEVBQzdELHNCQUFzQjtBQUN0QixrQ0FBa0M7QUFDbEMsc0NBQXNDLEVBQ3RDLGdFQUFnRSxFQUNoRSxrQkFBa0IsRUFDbEIsbURBQW1EO0FBQ25ELGlEQUFpRDtBQUNqRCxvREFBb0Q7QUFDcEQsMEJBQTBCLEVBQUUsUUFBUTtBQUNwQyxrQkFBa0IsRUFBRSxRQUFRO0FBQzVCLHNCQUFzQixFQUFFLFFBQVE7QUFDaEMsZUFBZSxFQUFFLFFBQVE7RUFDMUIsTUFBTSxrQ0FBa0MsQ0FBQztBQWExQyxPQUFPLEVBQ0wseUJBQXlCLEVBQ3pCLHVCQUF1QixHQUN4QixNQUFNLG9CQUFvQixDQUFDO0FBQzVCLE9BQU8sRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLE1BQU0sU0FBUyxDQUFDO0FBRzFDLEtBQUssQ0FBQyxNQUFNLENBQUMsT0FBTyxDQUFDLENBQUM7QUFDdEIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsQ0FBQztBQUN2QixLQUFLLENBQUMsTUFB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QyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSwrQkFBK0IsQ0FBQyxDQUFDO0lBQ2xELENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixlQUFlLG1CQUFtQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGRheWpzIGZyb20gJ2RheWpzJztcbmltcG9ydCBpc29XZWVrIGZyb20gJ2RheWpzL3BsdWdpbi9pc29XZWVrJztcbmltcG9ydCBkdXJhdGlvbiBmcm9tICdkYXlqcy9wbHVnaW4vZHVyYXRpb24nO1xuaW1wb3J0IGlzQmV0d2VlbiBmcm9tICdkYXlqcy9wbHVnaW4vaXNCZXR3ZWVuJztcbmltcG9ydCB0aW1lem9uZSBmcm9tICdkYXlqcy9wbHVnaW4vdGltZXpvbmUnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcblxuaW1wb3J0IHsgTWVzc2FnZVF1ZXVlVHlwZSB9IGZyb20gJ0BzY2hlZHVsZV9ldmVudC9fbGlicy90eXBlcy9zY2hlZHVsZUV2ZW50V29ya2VyL3R5cGVzJztcbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG5pbXBvcnQge1xuICBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMsXG4gIGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzR2l2ZW5NZWV0aW5nSWQsXG4gIGxpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzLFxuICBsaXN0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbk1lZXRpbmdJZCxcbiAgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCxcbiAgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyLFxuICBsaXN0RXZlbnRzRm9yRGF0ZSxcbiAgY29udmVydE1lZXRpbmdBc3Npc3RFdmVudFR5cGVUb0V2ZW50UGx1c1R5cGUsXG4gIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzLFxuICBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50LFxuICBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzLFxuICBnZXRFdmVudEZyb21QcmltYXJ5S2V5LFxuICAvLyBkZWxldGVEb2NJblNlYXJjaDMsIC8vIFJlcGxhY2VkXG4gIHByb2Nlc3NVc2VyRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50LFxuICBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudFdpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzLFxuICBnZXRVc2VyUHJlZmVyZW5jZXMsXG4gIHByb2Nlc3NFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnRXaXRob3V0Q2F0ZWdvcmllcyxcbiAgLy8gc2VhcmNoVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoLCAvLyBSZXBsYWNlZFxuICAvLyBnZXRWZWN0b3JJbkFsbEV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsIC8vIFJlcGxhY2VkXG4gIHNlYXJjaFRyYWluaW5nRGF0YUJ5VmVjdG9yLCAvLyBBZGRlZFxuICBnZXRFdmVudFZlY3RvckJ5SWQsIC8vIEFkZGVkXG4gIGRlbGV0ZVRyYWluaW5nRGF0YUJ5SWQsIC8vIEFkZGVkXG4gIGFkZFRyYWluaW5nRGF0YSwgLy8gQWRkZWRcbn0gZnJvbSAnQHNjaGVkdWxlX2V2ZW50L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHtcbiAgRXZlbnRQbHVzVHlwZSxcbiAgRXZlbnRUeXBlLFxuICBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlLFxuICBFdmVudE1lZXRpbmdQbHVzVHlwZSxcbiAgTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSxcbiAgUmVtaW5kZXJzRm9yRXZlbnRUeXBlLFxuICBCdWZmZXJUaW1lT2JqZWN0VHlwZSxcbiAgQ2F0ZWdvcnlUeXBlLFxuICBUcmFpbmluZ0V2ZW50U2NoZW1hLFxufSBmcm9tICdAc2NoZWR1bGVfZXZlbnQvX2xpYnMvdHlwZXMnOyAvLyBBZGRlZCBUcmFpbmluZ0V2ZW50U2NoZW1hXG5pbXBvcnQgeyBSZXR1cm5WYWx1ZUZvckVhY2hNZWV0aW5nQXNzaXN0VHlwZSB9IGZyb20gJ0BzY2hlZHVsZV9ldmVudC9fbGlicy90eXBlcyc7XG5pbXBvcnQge1xuICBrYWZrYVNjaGVkdWxlRXZlbnRHcm91cElkLFxuICBrYWZrYVNjaGVkdWxlRXZlbnRUb3BpYyxcbn0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IEthZmthLCBsb2dMZXZlbCB9IGZyb20gJ2thZmthanMnO1xuaW1wb3J0IGlwIGZyb20gJ2lwJztcblxuZGF5anMuZXh0ZW5kKGlzb1dlZWspO1xuZGF5anMuZXh0ZW5kKGR1cmF0aW9uKTtcbmRheWpzLmV4dGVuZChpc0JldHdlZW4pO1xuZGF5anMuZXh0ZW5kKHRpbWV6b25lKTtcbmRheWpzLmV4dGVuZCh1dGMpO1xuXG5jb25zdCBrYWZrYSA9IG5ldyBLYWZrYSh7XG4gIGxvZ0xldmVsOiBsb2dMZXZlbC5ERUJVRyxcbiAgYnJva2VyczogW2BrYWZrYTE6MjkwOTJgXSxcbiAgY2xpZW50SWQ6ICdhdG9taWMnLFxuICAvLyBzc2w6IHRydWUsXG4gIHNhc2w6IHtcbiAgICBtZWNoYW5pc206ICdwbGFpbicsIC8vIHNjcmFtLXNoYS0yNTYgb3Igc2NyYW0tc2hhLTUxMlxuICAgIHVzZXJuYW1lOiBwcm9jZXNzLmVudi5LQUZLQV9VU0VSTkFNRSxcbiAgICBwYXNzd29yZDogcHJvY2Vzcy5lbnYuS0FGS0FfUEFTU1dPUkQsXG4gIH0sXG59KTtcblxuY29uc3QgcHJvY2Vzc0V2ZW50c0ZvclBsYW5uaW5nID0gYXN5bmMgKFxuICBtYWluSG9zdElkOiBzdHJpbmcsXG4gIGludGVybmFsQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIG1lZXRpbmdFdmVudFBsdXM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10sIC8vIGV2ZW50cyB3aXRoIGEgbWVldGluZ0lkXG4gIHRvdGFsRXZlbnRzOiBFdmVudFR5cGVbXSxcbiAgb2xkRXZlbnRzOiBFdmVudFR5cGVbXSxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIGV4dGVybmFsQXR0ZW5kZWVzPzogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdLFxuICBtZWV0aW5nQXNzaXN0RXZlbnRzPzogTWVldGluZ0Fzc2lzdEV2ZW50VHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBldmVudHM6IEV2ZW50UGx1c1R5cGVbXSA9IF8uY2xvbmVEZWVwKHRvdGFsRXZlbnRzKTtcbiAgICBjb25zdCB1c2VyTW9kaWZpZWRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBldmVudCBvZiBldmVudHMpIHtcbiAgICAgIC8vIGdldCBwcmVmZXJyZWRUaW1lUmFuZ2VzXG4gICAgICBjb25zdCBwcmVmZXJyZWRUaW1lUmFuZ2VzID0gYXdhaXQgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudChcbiAgICAgICAgZXZlbnQ/LmlkXG4gICAgICApO1xuICAgICAgcHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChwdCkgPT5cbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgcHQsXG4gICAgICAgICAgJyBwcmVmZXJyZWRUaW1lUmFuZ2UgaW5zaWRlIHByb2Nlc3NVc2VyRXZlbnRzRm9yUGxhbm5pbmcnXG4gICAgICAgIClcbiAgICAgICk7XG4gICAgICBpZiAocHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzPy5tYXAoKHB0KSA9PlxuICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgcHQsXG4gICAgICAgICAgICAnIHByZWZlcnJlZFRpbWVSYW5nZSBpbnNpZGUgcHJvY2Vzc1VzZXJFdmVudHNGb3JQbGFubmluZydcbiAgICAgICAgICApXG4gICAgICAgICk7XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKHtcbiAgICAgICAgICAuLi5ldmVudCxcbiAgICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBwcmVmZXJyZWRUaW1lUmFuZ2VzLFxuICAgICAgICB9KTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKGV2ZW50KTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICByZXR1cm4gcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyKFxuICAgICAgbWFpbkhvc3RJZCxcbiAgICAgIGludGVybmFsQXR0ZW5kZWVzLFxuICAgICAgbWVldGluZ0V2ZW50UGx1cyxcbiAgICAgIFtdLFxuICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLFxuICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIG9sZEV2ZW50cyxcbiAgICAgIGV4dGVybmFsQXR0ZW5kZWVzLFxuICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cyxcbiAgICAgIFtdLFxuICAgICAgW11cbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBldmVudHMgZm9yIHBsYW5uaW5nJyk7XG4gIH1cbn07XG5cbmNvbnN0IHByb2Nlc3NFYWNoTWVldGluZ0Fzc2lzdCA9IGFzeW5jIChcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIG1lZXRpbmdJZDogc3RyaW5nLFxuICBtZWV0aW5nRXZlbnQ6IEV2ZW50VHlwZSxcbiAgbGlzdGVkRXZlbnRzOiBFdmVudFBsdXNUeXBlW11cbik6IFByb21pc2U8UmV0dXJuVmFsdWVGb3JFYWNoTWVldGluZ0Fzc2lzdFR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBhdHRlbmRlZXMgPSBhd2FpdCBsaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlc0dpdmVuTWVldGluZ0lkKG1lZXRpbmdJZCk7XG5cbiAgICBjb25zdCBleHRlcm5hbEF0dGVuZGVlcyA9IGF0dGVuZGVlcy5maWx0ZXIoKGEpID0+ICEhYT8uZXh0ZXJuYWxBdHRlbmRlZSk7XG5cbiAgICBjb25zdCBpbnRlcm5hbEF0dGVuZGVlcyA9IGF0dGVuZGVlcy5maWx0ZXIoKGEpID0+ICFhPy5leHRlcm5hbEF0dGVuZGVlKTtcbiAgICAvLyBvcmlnaW5hbCBtZWV0aW5nIGFzc3NpdCBldmVudHNcbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0RXZlbnRzOiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10gPSBbXTtcbiAgICAvLyBldmVudHMgZm9yIGVhY2ggdXNlclxuICAgIGNvbnN0IGV2ZW50czogRXZlbnRUeXBlW10gPSBbXTtcbiAgICAvLyBldmVudHMgd2l0aCBhIG1lZXRpbmdJZFxuICAgIGNvbnN0IG1lZXRpbmdFdmVudHM6IEV2ZW50VHlwZVtdID0gW107XG4gICAgbWVldGluZ0V2ZW50cy5wdXNoKG1lZXRpbmdFdmVudCk7XG4gICAgLy8gZ2V0IGV2ZW50c1xuICAgIGlmIChleHRlcm5hbEF0dGVuZGVlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBleHRlcm5hbEF0dGVuZGVlcz8ubGVuZ3RoOyBpKyspIHtcbiAgICAgICAgY29uc3QgbmV3TWVldGluZ0Fzc2lzdEV2ZW50cyA9XG4gICAgICAgICAgYXdhaXQgbGlzdE1lZXRpbmdBc3Npc3RFdmVudHNGb3JBdHRlbmRlZUdpdmVuRGF0ZXMoXG4gICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlc1tpXS5pZCxcbiAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlc1tpXS50aW1lem9uZSxcbiAgICAgICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgICAgICk7XG5cbiAgICAgICAgY29uc3QgbWVldGluZ0Fzc2lzdEV2ZW50Rm9yTWVldGluZyA9IG5ld01lZXRpbmdBc3Npc3RFdmVudHMuZmluZChcbiAgICAgICAgICAobSkgPT4gbS5tZWV0aW5nSWQgPT09IG1lZXRpbmdJZFxuICAgICAgICApO1xuICAgICAgICBjb25zdCBmaWx0ZXJlZE1lZXRpbmdBc3Npc3RFdmVudHMgPSBuZXdNZWV0aW5nQXNzaXN0RXZlbnRzLmZpbHRlcihcbiAgICAgICAgICAoZSkgPT4gZT8ubWVldGluZ0lkICE9PSBtZWV0aW5nSWRcbiAgICAgICAgKTtcbiAgICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cy5wdXNoKC4uLmZpbHRlcmVkTWVldGluZ0Fzc2lzdEV2ZW50cyk7XG4gICAgICAgIGlmIChtZWV0aW5nQXNzaXN0RXZlbnRGb3JNZWV0aW5nPy5pZCkge1xuICAgICAgICAgIG1lZXRpbmdFdmVudHMucHVzaChcbiAgICAgICAgICAgIGNvbnZlcnRNZWV0aW5nQXNzaXN0RXZlbnRUeXBlVG9FdmVudFBsdXNUeXBlKFxuICAgICAgICAgICAgICBtZWV0aW5nQXNzaXN0RXZlbnRGb3JNZWV0aW5nLFxuICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlc1tpXT8udXNlcklkXG4gICAgICAgICAgICApXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgaW50ZXJuYWxBdHRlbmRlZXMubGVuZ3RoOyBpKyspIHtcbiAgICAgIGNvbnN0IG5ld0V2ZW50cyA9IGF3YWl0IGxpc3RFdmVudHNGb3JVc2VyR2l2ZW5EYXRlcyhcbiAgICAgICAgaW50ZXJuYWxBdHRlbmRlZXNbaV0udXNlcklkLFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIGludGVybmFsQXR0ZW5kZWVzW2ldLnRpbWV6b25lLFxuICAgICAgICBob3N0VGltZXpvbmVcbiAgICAgICk7XG4gICAgICBjb25zdCBtZWV0aW5nQXNzaXN0RXZlbnRGb3JNZWV0aW5nID0gbmV3RXZlbnRzLmZpbmQoXG4gICAgICAgIChlKSA9PiBlPy5tZWV0aW5nSWQgPT09IG1lZXRpbmdJZFxuICAgICAgKTtcbiAgICAgIGNvbnN0IGZpbHRlcmVkTmV3RXZlbnRzID0gbmV3RXZlbnRzLmZpbHRlcihcbiAgICAgICAgKGUpID0+IGU/Lm1lZXRpbmdJZCAhPT0gbWVldGluZ0lkXG4gICAgICApO1xuICAgICAgZXZlbnRzLnB1c2goLi4uZmlsdGVyZWROZXdFdmVudHMpO1xuICAgICAgaWYgKG1lZXRpbmdBc3Npc3RFdmVudEZvck1lZXRpbmc/LmlkKSB7XG4gICAgICAgIG1lZXRpbmdFdmVudHMucHVzaChtZWV0aW5nQXNzaXN0RXZlbnRGb3JNZWV0aW5nKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBwcmVmZXJyZWRUaW1lc1JhbmdlcyA9XG4gICAgICBhd2FpdCBsaXN0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbk1lZXRpbmdJZChtZWV0aW5nSWQpO1xuXG4gICAgY29uc3QgbmV3VXNlck1vZGlmaWVkTWVldGluZ0V2ZW50czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSA9XG4gICAgICBtZWV0aW5nRXZlbnRzLm1hcCgobWUpID0+ICh7XG4gICAgICAgIC4uLm1lLFxuICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBwcmVmZXJyZWRUaW1lc1JhbmdlcyxcbiAgICAgIH0pKTtcblxuICAgIGNvbnN0IHVzZXJNb2RpZmllZEV2ZW50czogRXZlbnRQbHVzVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGV2ZW50IG9mIGV2ZW50cykge1xuICAgICAgLy8gZ2V0IHByZWZlcnJlZFRpbWVSYW5nZXNcbiAgICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXMgPSBhd2FpdCBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KFxuICAgICAgICBldmVudD8uaWRcbiAgICAgICk7XG4gICAgICBpZiAocHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzPy5tYXAoKHB0KSA9PlxuICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgcHQsXG4gICAgICAgICAgICAnIHByZWZlcnJlZFRpbWVSYW5nZSBpbnNpZGUgcHJvY2Vzc1VzZXJFdmVudHNGb3JQbGFubmluZydcbiAgICAgICAgICApXG4gICAgICAgICk7XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKHtcbiAgICAgICAgICAuLi5ldmVudCxcbiAgICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBwcmVmZXJyZWRUaW1lUmFuZ2VzLFxuICAgICAgICB9KTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKGV2ZW50KTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IHVzZXJNb2RpZmllZEV2ZW50c1xuICAgICAgPy5tYXAoKGUpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IGxpc3RlZEV2ZW50cy5maW5kSW5kZXgoKGwpID0+IGw/LmlkID09PSBlPy5pZCk7XG4gICAgICAgIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4gZTtcbiAgICAgIH0pXG4gICAgICA/LmZpbHRlcigoZSkgPT4gZSAhPT0gbnVsbCk7XG5cbiAgICByZXR1cm4ge1xuICAgICAgZXZlbnRzOiBmaWx0ZXJlZEV2ZW50cyxcbiAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMsXG4gICAgICBtZWV0aW5nRXZlbnRzUGx1czogbmV3VXNlck1vZGlmaWVkTWVldGluZ0V2ZW50cyxcbiAgICAgIGludGVybmFsQXR0ZW5kZWVzLFxuICAgICAgZXh0ZXJuYWxBdHRlbmRlZXMsXG4gICAgfTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgZWFjaCBtZWV0aW5nIGFzc2lzdCcpO1xuICB9XG59O1xuXG5jb25zdCBwcm9jZXNzRXZlbnRBcHBseUZlYXR1cmVzID0gYXN5bmMgKGV2ZW50OiBFdmVudFBsdXNUeXBlKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgaG9zdElkID0gZXZlbnQ/LnVzZXJJZDtcbiAgICBjb25zdCB3aW5kb3dTdGFydERhdGUgPSBkYXlqcyhldmVudD8uc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQ/LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmFkZCgxLCAnaCcpXG4gICAgICAubWludXRlKDApXG4gICAgICAuZm9ybWF0KCk7XG4gICAgY29uc3Qgd2luZG93RW5kRGF0ZSA9IGRheWpzKGV2ZW50Py5zdGFydERhdGU/LnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihldmVudD8udGltZXpvbmUsIHRydWUpXG4gICAgICAuYWRkKDYsICdkJylcbiAgICAgIC5mb3JtYXQoKTtcbiAgICBjb25zdCBob3N0VGltZXpvbmUgPSBldmVudD8udGltZXpvbmU7XG5cbiAgICBjb25zdCBwcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQgPSBhd2FpdCBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KFxuICAgICAgZXZlbnQ/LmlkXG4gICAgKTtcbiAgICBldmVudC5wcmVmZXJyZWRUaW1lUmFuZ2VzID0gcHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50O1xuXG4gICAgY29uc3QgZXZlbnRzOiBFdmVudFBsdXNUeXBlW10gPSBhd2FpdCBsaXN0RXZlbnRzRm9yRGF0ZShcbiAgICAgIGhvc3RJZCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICBob3N0VGltZXpvbmVcbiAgICApO1xuXG4gICAgY29uc3QgdXNlck1vZGlmaWVkRXZlbnRzOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcbiAgICBjb25zdCBuZXdNb2RpZmllZFJlbWluZGVyczogUmVtaW5kZXJzRm9yRXZlbnRUeXBlW10gPSBbXTtcbiAgICBjb25zdCBuZXdNb2RpZmllZFRpbWVCbG9ja2luZ3M6IEJ1ZmZlclRpbWVPYmplY3RUeXBlW10gPSBbXTtcblxuICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKC4uLmV2ZW50cyk7XG5cbiAgICAvLyAxLiBjb252ZXJ0IHRvIHZlY3RvciBzcGFjZVxuICAgIGNvbnN0IHsgdXNlcklkIH0gPSBldmVudDtcbiAgICBjb25zdCB2ZWN0b3IgPSBhd2FpdCBnZXRFdmVudFZlY3RvckJ5SWQoZXZlbnQ/LmlkKTtcbiAgICBjb25zb2xlLmxvZyh2ZWN0b3IsICcgdmVjdG9yJyk7XG5cbiAgICBpZiAoIXZlY3Rvcikge1xuICAgICAgLy8gSWYgbm8gdmVjdG9yLCBjYW5ub3QgZmluZCBzaW1pbGFyIGV2ZW50cyBvciBhZGQgdG8gdHJhaW5pbmcuXG4gICAgICAvLyBQcm9jZWVkIHdpdGggZGVmYXVsdCBjYXRlZ29yeSBwcm9jZXNzaW5nIG9yIGp1c3QgcHVzaCB0aGUgZXZlbnQuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgYE5vIHZlY3RvciBmb3VuZCBmb3IgZXZlbnQgJHtldmVudC5pZH0uIEFwcGx5aW5nIGRlZmF1bHQgY2F0ZWdvcnkgcHJvY2Vzc2luZy5gXG4gICAgICApO1xuICAgICAgaWYgKCFldmVudD8udXNlck1vZGlmaWVkQ2F0ZWdvcmllcykge1xuICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld1RpbWVCbG9ja2luZyB9ID1cbiAgICAgICAgICBhd2FpdCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0cyhldmVudCwgbnVsbCk7IC8vIFBhc3MgbnVsbCBmb3IgdmVjdG9yXG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKG5ld0V2ZW50KTtcbiAgICAgICAgaWYgKG5ld1JlbWluZGVycylcbiAgICAgICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgIGV2ZW50SWQ6IG5ld0V2ZW50Py5pZCxcbiAgICAgICAgICAgIHJlbWluZGVyczogbmV3UmVtaW5kZXJzLFxuICAgICAgICAgIH0pO1xuICAgICAgICBpZiAobmV3VGltZUJsb2NraW5nKSBuZXdNb2RpZmllZFRpbWVCbG9ja2luZ3MucHVzaChuZXdUaW1lQmxvY2tpbmcpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc3QgY2F0ZWdvcmllczogQ2F0ZWdvcnlUeXBlW10gPSBhd2FpdCBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50KFxuICAgICAgICAgIGV2ZW50Py5pZFxuICAgICAgICApO1xuICAgICAgICBpZiAoY2F0ZWdvcmllcz8uWzBdPy5pZCkge1xuICAgICAgICAgIGNvbnN0IHsgbmV3RXZlbnQsIG5ld1JlbWluZGVycywgbmV3VGltZUJsb2NraW5nIH0gPVxuICAgICAgICAgICAgYXdhaXQgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHNXaXRoVXNlck1vZGlmaWVkQ2F0ZWdvcmllcyhcbiAgICAgICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgICAgIG51bGxcbiAgICAgICAgICAgICk7IC8vIFBhc3MgbnVsbCBmb3IgdmVjdG9yXG4gICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3RXZlbnQpO1xuICAgICAgICAgIGlmIChuZXdSZW1pbmRlcnMpXG4gICAgICAgICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgIGlmIChuZXdUaW1lQmxvY2tpbmcpIG5ld01vZGlmaWVkVGltZUJsb2NraW5ncy5wdXNoKG5ld1RpbWVCbG9ja2luZyk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goZXZlbnQpOyAvLyBObyBjYXRlZ29yaWVzLCBubyB2ZWN0b3IsIHB1c2ggYXMgaXNcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICAvLyBWZWN0b3IgZXhpc3RzLCBwcm9jZWVkIHdpdGggc2VhcmNoL3RyYWluaW5nIGxvZ2ljXG4gICAgICBjb25zdCB0cmFpbmluZ1Jlc3VsdCA9IGF3YWl0IHNlYXJjaFRyYWluaW5nRGF0YUJ5VmVjdG9yKHVzZXJJZCwgdmVjdG9yKTtcbiAgICAgIGNvbnNvbGUubG9nKHRyYWluaW5nUmVzdWx0LCAnIHRyYWluaW5nUmVzdWx0IGZyb20gTGFuY2VEQicpO1xuXG4gICAgICBpZiAoIXRyYWluaW5nUmVzdWx0Py5pZCAmJiAhZXZlbnQ/LnVzZXJNb2RpZmllZENhdGVnb3JpZXMpIHtcbiAgICAgICAgY29uc29sZS5sb2coJ25vIHRyYWluaW5nIHJlc3VsdCBmb3VuZCBhbmQgbm8gdXNlciBtb2RpZmllZCBjYXRlZ29yaWVzJyk7XG4gICAgICAgIGNvbnN0IHsgbmV3RXZlbnQsIG5ld1JlbWluZGVycywgbmV3VGltZUJsb2NraW5nIH0gPVxuICAgICAgICAgIGF3YWl0IHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzKGV2ZW50LCB2ZWN0b3IpO1xuICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChuZXdFdmVudCk7XG4gICAgICAgIGlmIChuZXdSZW1pbmRlcnMpXG4gICAgICAgICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMucHVzaCh7XG4gICAgICAgICAgICBldmVudElkOiBuZXdFdmVudD8uaWQsXG4gICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgICAgICB9KTtcbiAgICAgICAgaWYgKG5ld1RpbWVCbG9ja2luZykgbmV3TW9kaWZpZWRUaW1lQmxvY2tpbmdzLnB1c2gobmV3VGltZUJsb2NraW5nKTtcblxuICAgICAgICBjb25zdCBuZXdUcmFpbmluZ0VudHJ5OiBUcmFpbmluZ0V2ZW50U2NoZW1hID0ge1xuICAgICAgICAgIGlkOiBldmVudC5pZCxcbiAgICAgICAgICB1c2VySWQ6IGV2ZW50LnVzZXJJZCxcbiAgICAgICAgICB2ZWN0b3I6IHZlY3RvcixcbiAgICAgICAgICBzb3VyY2VfZXZlbnRfdGV4dDogYCR7ZXZlbnQudGl0bGUgfHwgZXZlbnQuc3VtbWFyeX06JHtldmVudC5ub3RlcyB8fCAnJ31gLFxuICAgICAgICAgIGNyZWF0ZWRfYXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgfTtcbiAgICAgICAgYXdhaXQgYWRkVHJhaW5pbmdEYXRhKG5ld1RyYWluaW5nRW50cnkpO1xuICAgICAgfSBlbHNlIGlmICghdHJhaW5pbmdSZXN1bHQ/LmlkICYmIGV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICdubyB0cmFpbmluZyByZXN1bHQgZm91bmQgYnV0IGV2ZW50IGhhcyB1c2VyIG1vZGlmaWVkIGNhdGVnb3JpZXMnXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IGNhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdID0gYXdhaXQgbGlzdENhdGVnb3JpZXNGb3JFdmVudChcbiAgICAgICAgICBldmVudD8uaWRcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGNhdGVnb3JpZXM/LlswXT8uaWQpIHtcbiAgICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld1RpbWVCbG9ja2luZyB9ID1cbiAgICAgICAgICAgIGF3YWl0IHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzV2l0aFVzZXJNb2RpZmllZENhdGVnb3JpZXMoXG4gICAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgICB2ZWN0b3JcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3RXZlbnQpO1xuICAgICAgICAgIGlmIChuZXdSZW1pbmRlcnMpXG4gICAgICAgICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgIGlmIChuZXdUaW1lQmxvY2tpbmcpIG5ld01vZGlmaWVkVGltZUJsb2NraW5ncy5wdXNoKG5ld1RpbWVCbG9ja2luZyk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc3QgbmV3VHJhaW5pbmdFbnRyeTogVHJhaW5pbmdFdmVudFNjaGVtYSA9IHtcbiAgICAgICAgICAgIGlkOiBldmVudC5pZCxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnQudXNlcklkLFxuICAgICAgICAgICAgdmVjdG9yOiB2ZWN0b3IsXG4gICAgICAgICAgICBzb3VyY2VfZXZlbnRfdGV4dDogYCR7ZXZlbnQudGl0bGUgfHwgZXZlbnQuc3VtbWFyeX06JHtldmVudC5ub3RlcyB8fCAnJ31gLFxuICAgICAgICAgICAgY3JlYXRlZF9hdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIH07XG4gICAgICAgICAgYXdhaXQgYWRkVHJhaW5pbmdEYXRhKG5ld1RyYWluaW5nRW50cnkpO1xuICAgICAgICAgIGV2ZW50LnZlY3RvciA9IHZlY3RvcjtcbiAgICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChldmVudCk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSBpZiAodHJhaW5pbmdSZXN1bHQ/LmlkICYmICFldmVudD8udXNlck1vZGlmaWVkQ2F0ZWdvcmllcykge1xuICAgICAgICBjb25zdCBwcmV2aW91c0V2ZW50SWRGcm9tVHJhaW5pbmcgPSB0cmFpbmluZ1Jlc3VsdC5pZDtcbiAgICAgICAgY29uc3QgcHJldmlvdXNFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkoXG4gICAgICAgICAgcHJldmlvdXNFdmVudElkRnJvbVRyYWluaW5nXG4gICAgICAgICk7XG4gICAgICAgIGlmIChwcmV2aW91c0V2ZW50Py5pZCkge1xuICAgICAgICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXMgPSBhd2FpdCBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KFxuICAgICAgICAgICAgcHJldmlvdXNFdmVudElkRnJvbVRyYWluaW5nXG4gICAgICAgICAgKTtcbiAgICAgICAgICBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMgPSBwcmVmZXJyZWRUaW1lUmFuZ2VzO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmV2aW91c0V2ZW50KSB7XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBwcmV2aW91c0V2ZW50SWRGcm9tVHJhaW5pbmcsXG4gICAgICAgICAgICAndHJhaW5pbmdSZXN1bHQuaWQgcG9pbnRzIHRvIGEgZGVsZXRlZCBldmVudC4nXG4gICAgICAgICAgKTtcbiAgICAgICAgICBhd2FpdCBkZWxldGVUcmFpbmluZ0RhdGFCeUlkKHRyYWluaW5nUmVzdWx0LmlkKTtcbiAgICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld1RpbWVCbG9ja2luZyB9ID1cbiAgICAgICAgICAgIGF3YWl0IHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzKGV2ZW50LCB2ZWN0b3IpO1xuICAgICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKG5ld0V2ZW50KTtcbiAgICAgICAgICBpZiAobmV3UmVtaW5kZXJzKVxuICAgICAgICAgICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMucHVzaCh7XG4gICAgICAgICAgICAgIGV2ZW50SWQ6IG5ld0V2ZW50Py5pZCxcbiAgICAgICAgICAgICAgcmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICBpZiAobmV3VGltZUJsb2NraW5nKSBuZXdNb2RpZmllZFRpbWVCbG9ja2luZ3MucHVzaChuZXdUaW1lQmxvY2tpbmcpO1xuXG4gICAgICAgICAgY29uc3QgbmV3VHJhaW5pbmdFbnRyeTogVHJhaW5pbmdFdmVudFNjaGVtYSA9IHtcbiAgICAgICAgICAgIGlkOiBldmVudC5pZCxcbiAgICAgICAgICAgIHVzZXJJZDogZXZlbnQudXNlcklkLFxuICAgICAgICAgICAgdmVjdG9yOiB2ZWN0b3IsXG4gICAgICAgICAgICBzb3VyY2VfZXZlbnRfdGV4dDogYCR7ZXZlbnQudGl0bGUgfHwgZXZlbnQuc3VtbWFyeX06JHtldmVudC5ub3RlcyB8fCAnJ31gLFxuICAgICAgICAgICAgY3JlYXRlZF9hdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIH07XG4gICAgICAgICAgYXdhaXQgYWRkVHJhaW5pbmdEYXRhKG5ld1RyYWluaW5nRW50cnkpO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGNvbnN0IHsgbmV3RXZlbnQsIG5ld1JlbWluZGVycywgbmV3VGltZUJsb2NraW5nIH0gPVxuICAgICAgICAgICAgYXdhaXQgcHJvY2Vzc1VzZXJFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnQoXG4gICAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgICBwcmV2aW91c0V2ZW50SWRGcm9tVHJhaW5pbmdcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3RXZlbnQpO1xuICAgICAgICAgIGlmIChuZXdSZW1pbmRlcnMpXG4gICAgICAgICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgIGlmIChuZXdUaW1lQmxvY2tpbmcpIG5ld01vZGlmaWVkVGltZUJsb2NraW5ncy5wdXNoKG5ld1RpbWVCbG9ja2luZyk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSBpZiAodHJhaW5pbmdSZXN1bHQ/LmlkICYmIGV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzKSB7XG4gICAgICAgIGNvbnN0IHByZXZpb3VzRXZlbnRJZEZyb21UcmFpbmluZyA9IHRyYWluaW5nUmVzdWx0LmlkO1xuICAgICAgICBjb25zdCBwcmV2aW91c0V2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShcbiAgICAgICAgICBwcmV2aW91c0V2ZW50SWRGcm9tVHJhaW5pbmdcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKHByZXZpb3VzRXZlbnQ/LmlkKSB7XG4gICAgICAgICAgY29uc3QgcHJlZmVycmVkVGltZVJhbmdlcyA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoXG4gICAgICAgICAgICBwcmV2aW91c0V2ZW50SWRGcm9tVHJhaW5pbmdcbiAgICAgICAgICApO1xuICAgICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcyA9IHByZWZlcnJlZFRpbWVSYW5nZXM7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoIXByZXZpb3VzRXZlbnQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgIHByZXZpb3VzRXZlbnRJZEZyb21UcmFpbmluZyxcbiAgICAgICAgICAgICd0cmFpbmluZ1Jlc3VsdC5pZCBwb2ludHMgdG8gYSBkZWxldGVkIGV2ZW50IGFuZCBldmVudCBoYXMgdXNlciBtb2RpZmllZCBjYXRlZ29yaWVzLidcbiAgICAgICAgICApO1xuICAgICAgICAgIGF3YWl0IGRlbGV0ZVRyYWluaW5nRGF0YUJ5SWQodHJhaW5pbmdSZXN1bHQuaWQpO1xuICAgICAgICAgIGNvbnN0IGNhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdID0gYXdhaXQgbGlzdENhdGVnb3JpZXNGb3JFdmVudChcbiAgICAgICAgICAgIGV2ZW50Py5pZFxuICAgICAgICAgICk7XG4gICAgICAgICAgaWYgKGNhdGVnb3JpZXM/LlswXT8uaWQpIHtcbiAgICAgICAgICAgIGNvbnN0IHsgbmV3RXZlbnQsIG5ld1JlbWluZGVycywgbmV3VGltZUJsb2NraW5nIH0gPVxuICAgICAgICAgICAgICBhd2FpdCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzKFxuICAgICAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgICAgIHZlY3RvclxuICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3RXZlbnQpO1xuICAgICAgICAgICAgaWYgKG5ld1JlbWluZGVycylcbiAgICAgICAgICAgICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMucHVzaCh7XG4gICAgICAgICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgICAgICAgIHJlbWluZGVyczogbmV3UmVtaW5kZXJzLFxuICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIGlmIChuZXdUaW1lQmxvY2tpbmcpIG5ld01vZGlmaWVkVGltZUJsb2NraW5ncy5wdXNoKG5ld1RpbWVCbG9ja2luZyk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnN0IG5ld1RyYWluaW5nRW50cnk6IFRyYWluaW5nRXZlbnRTY2hlbWEgPSB7XG4gICAgICAgICAgICAgIGlkOiBldmVudC5pZCxcbiAgICAgICAgICAgICAgdXNlcklkOiBldmVudC51c2VySWQsXG4gICAgICAgICAgICAgIHZlY3RvcjogdmVjdG9yLFxuICAgICAgICAgICAgICBzb3VyY2VfZXZlbnRfdGV4dDogYCR7ZXZlbnQudGl0bGUgfHwgZXZlbnQuc3VtbWFyeX06JHtldmVudC5ub3RlcyB8fCAnJ31gLFxuICAgICAgICAgICAgICBjcmVhdGVkX2F0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICB9O1xuICAgICAgICAgICAgYXdhaXQgYWRkVHJhaW5pbmdEYXRhKG5ld1RyYWluaW5nRW50cnkpO1xuICAgICAgICAgICAgZXZlbnQudmVjdG9yID0gdmVjdG9yO1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goZXZlbnQpO1xuICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zdCBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXSA9IGF3YWl0IGxpc3RDYXRlZ29yaWVzRm9yRXZlbnQoXG4gICAgICAgICAgICBldmVudD8uaWRcbiAgICAgICAgICApO1xuICAgICAgICAgIGlmIChjYXRlZ29yaWVzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld1RpbWVCbG9ja2luZyB9ID1cbiAgICAgICAgICAgICAgYXdhaXQgcHJvY2Vzc1VzZXJFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnRXaXRoVXNlck1vZGlmaWVkQ2F0ZWdvcmllcyhcbiAgICAgICAgICAgICAgICBldmVudCxcbiAgICAgICAgICAgICAgICBwcmV2aW91c0V2ZW50SWRGcm9tVHJhaW5pbmdcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKG5ld0V2ZW50KTtcbiAgICAgICAgICAgIGlmIChuZXdSZW1pbmRlcnMpXG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkUmVtaW5kZXJzLnB1c2goe1xuICAgICAgICAgICAgICAgIGV2ZW50SWQ6IG5ld0V2ZW50Py5pZCxcbiAgICAgICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICBpZiAobmV3VGltZUJsb2NraW5nKSBuZXdNb2RpZmllZFRpbWVCbG9ja2luZ3MucHVzaChuZXdUaW1lQmxvY2tpbmcpO1xuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjb25zb2xlLmxvZygnbm8gY2F0ZWdvcmllcyBmb3VuZCwgYnV0IHByZXZpb3VzIGV2ZW50IGZvdW5kJyk7XG4gICAgICAgICAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZXModXNlcklkKTtcbiAgICAgICAgICAgIGNvbnN0IHtcbiAgICAgICAgICAgICAgbmV3TW9kaWZpZWRFdmVudDogbmV3TW9kaWZpZWRFdmVudDEsXG4gICAgICAgICAgICAgIG5ld1JlbWluZGVyczogbmV3UmVtaW5kZXJzMSxcbiAgICAgICAgICAgICAgbmV3VGltZUJsb2NraW5nOiBuZXdUaW1lQmxvY2tpbmcxLFxuICAgICAgICAgICAgfSA9IGF3YWl0IHByb2Nlc3NFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnRXaXRob3V0Q2F0ZWdvcmllcyhcbiAgICAgICAgICAgICAgcHJldmlvdXNFdmVudCxcbiAgICAgICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgICAgIHVzZXJQcmVmZXJlbmNlcyxcbiAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3TW9kaWZpZWRFdmVudDEpO1xuICAgICAgICAgICAgaWYgKG5ld1JlbWluZGVyczEpXG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkUmVtaW5kZXJzLnB1c2goe1xuICAgICAgICAgICAgICAgIGV2ZW50SWQ6IG5ld01vZGlmaWVkRXZlbnQxPy5pZCxcbiAgICAgICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVyczEsXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgaWYgKG5ld1RpbWVCbG9ja2luZzEpXG4gICAgICAgICAgICAgIG5ld01vZGlmaWVkVGltZUJsb2NraW5ncy5wdXNoKG5ld1RpbWVCbG9ja2luZzEpO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIHVzZXJNb2RpZmllZEV2ZW50cy5mb3JFYWNoKChlKSA9PlxuICAgICAgY29uc29sZS5sb2coZSwgJyB1c2VyTW9kaWZpZWRFdmVudCBiZWZvcmUgcHJvY2Vzc2luZyBmb3IgT3B0YXBsYW5uZXInKVxuICAgICk7XG4gICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMuZm9yRWFjaCgoZSkgPT5cbiAgICAgIGNvbnNvbGUubG9nKGUsICcgbmV3TW9kaWZpZWRSZW1pbmRlcnMgYmVmb3JlIHByb2Nlc3NpbmcgZm9yIE9wdGFwbGFubmVyJylcbiAgICApO1xuXG4gICAgY29uc3QgZXZlbnRzV2l0aE1lZXRpbmdJZCA9IGV2ZW50cy5maWx0ZXIoKGUpID0+ICEhZT8ubWVldGluZ0lkKTtcblxuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG1lZXRpbmdFdmVudFBsdXM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10gPSBbXTtcbiAgICBjb25zdCBpbnRlcm5hbEF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdID0gW107XG4gICAgY29uc3QgZXh0ZXJuYWxBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IGZpbHRlcmVkRXZlbnRzOiBFdmVudFR5cGVbXSA9IFtdO1xuXG4gICAgLyoqXG4gICAgICogcXVldWUgZm9yIGVhY2hcbiAgICAgKiBwYXJlbnRLZXk6IGhvc3RJZC9zaW5nbGV0b25JZFxuICAgICAqIG9sZENoaWxkS2V5OiBob3N0SWQvbWVldGluZ0lkXG4gICAgICovXG5cbiAgICBmaWx0ZXJlZEV2ZW50cy5wdXNoKC4uLnVzZXJNb2RpZmllZEV2ZW50cyk7XG4gICAgZmlsdGVyZWRFdmVudHMucHVzaCguLi5ldmVudHNXaXRoTWVldGluZ0lkKTtcblxuICAgIGZvciAoY29uc3QgZXZlbnRXaXRoTWVldGluZ0lkIG9mIGV2ZW50c1dpdGhNZWV0aW5nSWQpIHtcbiAgICAgIGNvbnN0IHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nID0gYXdhaXQgcHJvY2Vzc0VhY2hNZWV0aW5nQXNzaXN0KFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgZXZlbnRXaXRoTWVldGluZ0lkPy5tZWV0aW5nSWQsXG4gICAgICAgIGV2ZW50V2l0aE1lZXRpbmdJZCxcbiAgICAgICAgZXZlbnRzXG4gICAgICApO1xuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBjb25zdCBuZXdFdmVudHMgPSByZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uZXZlbnRzO1xuXG4gICAgICAgIGZpbHRlcmVkRXZlbnRzLnB1c2goLi4ubmV3RXZlbnRzKTtcbiAgICAgICAgZXZlbnRzLnB1c2goLi4ubmV3RXZlbnRzKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5tZWV0aW5nQXNzaXN0RXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMucHVzaChcbiAgICAgICAgICAuLi5yZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8ubWVldGluZ0Fzc2lzdEV2ZW50c1xuICAgICAgICApO1xuICAgICAgfVxuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/Lm1lZXRpbmdFdmVudHNQbHVzKSB7XG4gICAgICAgIG1lZXRpbmdFdmVudFBsdXMucHVzaCguLi5yZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8ubWVldGluZ0V2ZW50c1BsdXMpO1xuICAgICAgfVxuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmludGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgIGludGVybmFsQXR0ZW5kZWVzLnB1c2goXG4gICAgICAgICAgLi4ucmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmludGVybmFsQXR0ZW5kZWVzXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uZXh0ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZXMucHVzaChcbiAgICAgICAgICAuLi5yZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uZXh0ZXJuYWxBdHRlbmRlZXNcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICByZXR1cm4gcHJvY2Vzc0V2ZW50c0ZvclBsYW5uaW5nKFxuICAgICAgaG9zdElkLFxuICAgICAgXy51bmlxV2l0aChpbnRlcm5hbEF0dGVuZGVlcywgXy5pc0VxdWFsKSxcbiAgICAgIG1lZXRpbmdFdmVudFBsdXMsXG4gICAgICBfLnVuaXFXaXRoKGZpbHRlcmVkRXZlbnRzLCBfLmlzRXF1YWwpLFxuICAgICAgZXZlbnRzLFxuICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIF8udW5pcVdpdGgoZXh0ZXJuYWxBdHRlbmRlZXMsIF8uaXNFcXVhbCksXG4gICAgICBtZWV0aW5nQXNzaXN0RXZlbnRzPy5sZW5ndGggPiAwXG4gICAgICAgID8gXy51bmlxV2l0aChtZWV0aW5nQXNzaXN0RXZlbnRzLCBfLmlzRXF1YWwpXG4gICAgICAgIDogbnVsbFxuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIG1lZXRpbmcgYXNzaXN0Jyk7XG4gIH1cbn07XG5cbmNvbnN0IHByb2Nlc3NRdWV1ZU1lc3NhZ2UgPSBhc3luYyAoZXZlbnQ6IEV2ZW50UGx1c1R5cGUpID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIWV2ZW50Py5pZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyB1c2VySWQgcHJvdmlkZWQgaW5zaWRlIGF0b21pYyBtZWV0aW5nIGFzc2lzdCcpO1xuICAgIH1cblxuICAgIHJldHVybiBwcm9jZXNzRXZlbnRBcHBseUZlYXR1cmVzKGV2ZW50KTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3NRdWV1ZU1lc3NhZ2UgaW5zaWRlIGF0b21pYyBtZWV0aW5nIGFzc2lzdCdcbiAgICApO1xuICB9XG59O1xuXG5jb25zdCBzY2hlZHVsZUV2ZW50V29ya2VyID0gYXN5bmMgKGV2ZW50OiB7IFJlY29yZHM6IE1lc3NhZ2VRdWV1ZVR5cGVbXSB9KSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgY29uc3VtZXIgPSBrYWZrYS5jb25zdW1lcih7IGdyb3VwSWQ6IGthZmthU2NoZWR1bGVFdmVudEdyb3VwSWQgfSk7XG4gICAgYXdhaXQgY29uc3VtZXIuY29ubmVjdCgpO1xuXG4gICAgYXdhaXQgY29uc3VtZXIuc3Vic2NyaWJlKHsgdG9waWM6IGthZmthU2NoZWR1bGVFdmVudFRvcGljIH0pO1xuXG4gICAgYXdhaXQgY29uc3VtZXIucnVuKHtcbiAgICAgIGVhY2hNZXNzYWdlOiBhc3luYyAoeyB0b3BpYywgcGFydGl0aW9uLCBtZXNzYWdlIH0pID0+IHtcbiAgICAgICAgY29uc29sZS5sb2coe1xuICAgICAgICAgIGtleTogbWVzc2FnZT8ua2V5Py50b1N0cmluZygpLFxuICAgICAgICAgIHZhbHVlOiBtZXNzYWdlPy52YWx1ZT8udG9TdHJpbmcoKSxcbiAgICAgICAgICBoZWFkZXJzOiBtZXNzYWdlPy5oZWFkZXJzLFxuICAgICAgICB9KTtcblxuICAgICAgICBjb25zdCBib2R5OiBFdmVudFBsdXNUeXBlID0gSlNPTi5wYXJzZShtZXNzYWdlPy52YWx1ZT8udG9TdHJpbmcoKSk7XG4gICAgICAgIGNvbnNvbGUubG9nKGJvZHksICcgYm9keScpO1xuXG4gICAgICAgIGF3YWl0IHByb2Nlc3NRdWV1ZU1lc3NhZ2UoYm9keSk7XG4gICAgICB9LFxuICAgIH0pO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gYXNzaXN0IGZvciBtZWV0aW5nJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBkZWZhdWx0IHNjaGVkdWxlRXZlbnRXb3JrZXI7XG4iXX0=