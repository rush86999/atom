import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import { listEventsForUserGivenDates, listMeetingAssistAttendeesGivenMeetingId, listMeetingAssistEventsForAttendeeGivenDates, listMeetingAssistPreferredTimeRangesGivenMeetingId, listPreferredTimeRangesForEvent, processEventsForOptaPlanner, listEventsForDate, convertMeetingAssistEventTypeToEventPlusType, processUserEventForCategoryDefaults, listCategoriesForEvent, processUserEventForCategoryDefaultsWithUserModifiedCategories, getEventFromPrimaryKey, 
// deleteDocInSearch3, // Replaced
processUserEventWithFoundPreviousEvent, processUserEventWithFoundPreviousEventWithUserModifiedCategories, getUserPreferences, processEventWithFoundPreviousEventWithoutCategories, } from '@schedule_event/_libs/api-helper';
import { kafkaScheduleEventGroupId, kafkaScheduleShortEventTopic, } from '../_libs/constants';
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
const processEventShortApplyFeatures = async (event) => {
    try {
        const hostId = event?.userId;
        const windowStartDate = dayjs(event?.startDate?.slice(0, 19))
            .tz(event?.timezone, true)
            .add(1, 'h')
            .minute(0)
            .format();
        const windowEndDate = dayjs(event?.startDate?.slice(0, 19))
            .tz(event?.timezone, true)
            .hour(23)
            .minute(59)
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
        // const text = `${event?.title || event?.summary}:${event?.notes}`
        const vector = await getVectorInAllEventIndexInOpenSearch(event?.id);
        console.log(vector, ' vector');
        // 2. find closest event
        const res = await searchTrainEventIndexInOpenSearch(userId, vector);
        console.log(res, ' res from searchData');
        const results = res?.hits?.hits?.[0];
        console.log(results, ' results from searchData');
        // validate results
        if (!results?._id && !event?.userModifiedCategories) {
            console.log('no results found');
            // no previous event found use CategoryDefaults
            const { newEvent, newReminders, newTimeBlocking: newBufferTimes, } = await processUserEventForCategoryDefaults(event, vector);
            console.log(newEvent, ' newEvent for processUserEventForCategoryDefaults');
            console.log(newReminders, ' newReminders for processUserEventForCategoryDefaults');
            userModifiedEvents.push(newEvent);
            newModifiedReminders.push({
                eventId: newEvent?.id,
                reminders: newReminders,
            });
            newModifiedTimeBlockings.push(newBufferTimes);
        }
        if (!results?._id && event?.userModifiedCategories) {
            console.log('no results found');
            // no previous event found use user modified categories and category defaults
            const categories = await listCategoriesForEvent(event?.id);
            console.log(categories, ' categories');
            if (categories?.[0]?.id) {
                const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaultsWithUserModifiedCategories(event, vector);
                console.log(newEvent, ' newEvent for processUserEventForCategoryDefaultsWithUserModifiedCategories');
                console.log(newReminders, ' newReminders for processUserEventForCategoryDefaultsWithUserModifiedCategories');
                userModifiedEvents.push(newEvent);
                newModifiedReminders.push({
                    eventId: newEvent?.id,
                    reminders: newReminders,
                });
                newModifiedTimeBlockings.push(newTimeBlocking);
            }
            else {
                //  create new event datatype in elastic search
                // await putDataInSearch(event?.id, vector, userId)
                event.vector = vector;
                userModifiedEvents.push(event);
            }
        }
        // previous event found use previous event to copy over values
        if (results?._id && !event?.userModifiedCategories) {
            // valdate as might be old deleted event
            const previousEvent = await getEventFromPrimaryKey(results?._id);
            if (previousEvent?.id) {
                const preferredTimeRanges = await listPreferredTimeRangesForEvent(results?._id);
                previousEvent.preferredTimeRanges = preferredTimeRanges;
            }
            // there is no event found so change direction
            if (!previousEvent) {
                console.log(results?._id, 'results?._id inside !previousEvent results?._id && !event?.userModifiedCategories');
                await deleteDocInSearch3(results?._id);
                if (!event?.userModifiedCategories) {
                    console.log('no results found');
                    // no previous event found use CategoryDefaults
                    const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaults(event, vector);
                    console.log(newEvent, ' newEvent for processUserEventForCategoryDefaults');
                    console.log(newReminders, ' newReminders for processUserEventForCategoryDefaults');
                    userModifiedEvents.push(newEvent);
                    newModifiedReminders.push({
                        eventId: newEvent?.id,
                        reminders: newReminders,
                    });
                    newModifiedTimeBlockings.push(newTimeBlocking);
                }
            }
            else {
                const { newEvent, newReminders, newTimeBlocking } = await processUserEventWithFoundPreviousEvent(event, results?._id);
                console.log(newEvent, ' newEvent for processUserEventWithFoundPreviousEvent');
                console.log(newReminders, ' newReminders for processUserEventWithFoundPreviousEvent');
                userModifiedEvents.push(newEvent);
                newModifiedReminders.push({
                    eventId: newEvent?.id,
                    reminders: newReminders,
                });
                newModifiedTimeBlockings.push(newTimeBlocking);
            }
        }
        if (results?._id && event?.userModifiedCategories) {
            // valdate as might be old deleted event
            const previousEvent = await getEventFromPrimaryKey(results?._id);
            if (previousEvent?.id) {
                const preferredTimeRanges = await listPreferredTimeRangesForEvent(results?._id);
                previousEvent.preferredTimeRanges = preferredTimeRanges;
            }
            if (!previousEvent) {
                console.log(previousEvent, 'previousEvent - old deleted event in doc search');
                await deleteDocInSearch3(results?._id);
                if (event?.userModifiedCategories) {
                    console.log(results?._id, ' results?._id inside !previousEvent results?._id && event?.userModifiedCategories');
                    console.log('no results found');
                    // no previous event found use user modified categories and category defaults
                    const categories = await listCategoriesForEvent(event?.id);
                    console.log(categories, ' categories');
                    if (categories?.[0]?.id) {
                        const { newEvent, newReminders, newTimeBlocking } = await processUserEventForCategoryDefaultsWithUserModifiedCategories(event, vector);
                        console.log(newEvent, ' newEvent for processUserEventForCategoryDefaultsWithUserModifiedCategories');
                        console.log(newReminders, ' newReminders for processUserEventForCategoryDefaultsWithUserModifiedCategories');
                        userModifiedEvents.push(newEvent);
                        newModifiedReminders.push({
                            eventId: newEvent?.id,
                            reminders: newReminders,
                        });
                        newModifiedTimeBlockings.push(newTimeBlocking);
                    }
                    else {
                        //  create new event datatype in elastic search
                        // await putDataInSearch(event?.id, vector, userId)
                        event.vector = vector;
                        userModifiedEvents.push(event);
                    }
                }
            }
            else {
                // const categories: CategoryType[] = await listCategoriesForEvent(event?.id)
                const categories = await listCategoriesForEvent(event?.id);
                console.log(categories, ' categories');
                if (categories?.[0]?.id) {
                    const { newEvent, newReminders, newTimeBlocking } = await processUserEventWithFoundPreviousEventWithUserModifiedCategories(event, results?._id);
                    console.log(newEvent, ' newEvent for processUserEventWithFoundPreviousEventWithUserModifiedCategories');
                    console.log(newReminders, ' newReminders for processUserEventWithFoundPreviousEventWithUserModifiedCategories');
                    userModifiedEvents.push(newEvent);
                    newModifiedReminders.push({
                        eventId: newEvent?.id,
                        reminders: newReminders,
                    });
                    newModifiedTimeBlockings.push(newTimeBlocking);
                }
                else {
                    console.log('no categories found');
                    // get previous event
                    const previousEvent = await getEventFromPrimaryKey(results?._id);
                    const preferredTimeRanges = await listPreferredTimeRangesForEvent(results?._id);
                    previousEvent.preferredTimeRanges = preferredTimeRanges;
                    if (!previousEvent?.id) {
                        throw new Error('previousEvent is missing');
                    }
                    const userPreferences = await getUserPreferences(userId);
                    const { newModifiedEvent: newModifiedEvent1, newReminders: newReminders1, newTimeBlocking: newTimeBlocking1, } = await processEventWithFoundPreviousEventWithoutCategories(previousEvent, event, userPreferences, userId);
                    userModifiedEvents.push(newModifiedEvent1);
                    newModifiedReminders.push({
                        eventId: newModifiedEvent1?.id,
                        reminders: newReminders1,
                    });
                    newModifiedTimeBlockings.push(newTimeBlocking1);
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
        return processEventShortApplyFeatures(event);
    }
    catch (e) {
        console.log(e, ' unable to processQueueMessage inside atomic meeting assist');
    }
};
const scheduleEventWorker = async (event) => {
    try {
        const consumer = kafka.consumer({ groupId: kafkaScheduleEventGroupId });
        await consumer.connect();
        await consumer.subscribe({ topic: kafkaScheduleShortEventTopic });
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEtBQUssTUFBTSxPQUFPLENBQUM7QUFDMUIsT0FBTyxPQUFPLE1BQU0sc0JBQXNCLENBQUM7QUFDM0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxTQUFTLE1BQU0sd0JBQXdCLENBQUM7QUFDL0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxHQUFHLE1BQU0sa0JBQWtCLENBQUM7QUFHbkMsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBQ3ZCLE9BQU8sRUFDTCwyQkFBMkIsRUFDM0Isd0NBQXdDLEVBQ3hDLDRDQUE0QyxFQUM1QyxrREFBa0QsRUFDbEQsK0JBQStCLEVBQy9CLDJCQUEyQixFQUMzQixpQkFBaUIsRUFDakIsNENBQTRDLEVBQzVDLG1DQUFtQyxFQUNuQyxzQkFBc0IsRUFDdEIsNkRBQTZELEVBQzdELHNCQUFzQjtBQUN0QixrQ0FBa0M7QUFDbEMsc0NBQXNDLEVBQ3RDLGdFQUFnRSxFQUNoRSxrQkFBa0IsRUFDbEIsbURBQW1ELEdBT3BELE1BQU0sa0NBQWtDLENBQUM7QUFhMUMsT0FBTyxFQUNMLHlCQUF5QixFQUN6Qiw0QkFBNEIsR0FDN0IsTUFBTSxvQkFBb0IsQ0FBQztBQUM1QixPQUFPLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxNQUFNLFNBQVMsQ0FBQztBQUcxQyxLQUFLLENBQUMsTUFBTSxDQUFDLE9BQU8sQ0FBQyxDQUFDO0FBQ3RCLEtBQUssQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLENBQUM7QUFDdkIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxTQUFTLENBQUMsQ0FBQztBQUN4QixLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUM7QUFFbEIsTUFBTSxLQUFLLEdBQUcsSUFBSSxLQUFLLENBQUM7SUFDdEIsUUFBUSxFQUFFLFFBQVEsQ0FBQyxLQUFLO0lBQ3hCLE9BQU8sRUFBRSxDQUFDLGNBQWMsQ0FBQztJQUN6QixRQUFRLEVBQUUsUUFBUTtJQUNsQixhQUFhO0lBQ2IsSUFBSSxFQUFFO1FBQ0osU0FBUyxFQUFFLE9BQU8sRUFBRSxpQ0FBaUM7UUFDckQsUUFBUSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYztRQUNwQyxRQUFRLEVBQUUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxjQUFjO0tBQ3JDO0NBQ0YsQ0FBQyxDQUFDO0FBRUgsTUFBTSx3QkFBd0IsR0FBRyxLQUFLLEVBQ3BDLFVBQWtCLEVBQ2xCLGlCQUE4QyxFQUM5QyxnQkFBd0MsRUFBRSwwQkFBMEI7QUFDcEUsV0FBd0IsRUFDeEIsU0FBc0IsRUFDdEIsZUFBdUIsRUFDdkIsYUFBcUIsRUFDckIsWUFBb0IsRUFDcEIsaUJBQStDLEVBQy9DLG1CQUE4QyxFQUM5QyxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxNQUFNLEdBQW9CLENBQUMsQ0FBQyxTQUFTLENBQUMsV0FBVyxDQUFDLENBQUM7UUFDekQsTUFBTSxrQkFBa0IsR0FBb0IsRUFBRSxDQUFDO1FBRS9DLEtBQUssTUFBTSxLQUFLLElBQUksTUFBTSxFQUFFLENBQUM7WUFDM0IsMEJBQTBCO1lBQzFCLE1BQU0sbUJBQW1CLEdBQUcsTUFBTSwrQkFBK0IsQ0FDL0QsS0FBSyxFQUFFLEVBQUUsQ0FDVixDQUFDO1lBQ0YsbUJBQW1CLEVBQUUsR0FBRyxDQUFDLENBQUMsRUFBRSxFQUFFLEVBQUUsQ0FDOUIsT0FBTyxDQUFDLEdBQUcsQ0FDVCxFQUFFLEVBQ0YseURBQXlELENBQzFELENBQ0YsQ0FBQztZQUNGLElBQUksbUJBQW1CLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO2dCQUNwQyxtQkFBbUIsRUFBRSxHQUFHLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRSxDQUM5QixPQUFPLENBQUMsR0FBRyxDQUNULEVBQUUsRUFDRix5REFBeUQsQ0FDMUQsQ0FDRixDQUFDO2dCQUNGLGtCQUFrQixDQUFDLElBQUksQ0FBQztvQkFDdEIsR0FBRyxLQUFLO29CQUNSLG1CQUFtQixFQUFFLG1CQUFtQjtpQkFDekMsQ0FBQyxDQUFDO1lBQ0wsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLGtCQUFrQixDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUNqQyxDQUFDO1FBQ0gsQ0FBQztRQUVELE9BQU8sMkJBQTJCLENBQ2hDLFVBQVUsRUFDVixpQkFBaUIsRUFDakIsZ0JBQWdCLEVBQ2hCLEVBQUUsRUFDRixrQkFBa0IsRUFDbEIsZUFBZSxFQUNmLGFBQWEsRUFDYixZQUFZLEVBQ1osU0FBUyxFQUNULGlCQUFpQixFQUNqQixtQkFBbUIsRUFDbkIsRUFBRSxFQUNGLEVBQUUsQ0FDSCxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSx3Q0FBd0MsQ0FBQyxDQUFDO0lBQzNELENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixNQUFNLHdCQUF3QixHQUFHLEtBQUssRUFDcEMsZUFBdUIsRUFDdkIsYUFBcUIsRUFDckIsWUFBb0IsRUFDcEIsU0FBaUIsRUFDakIsWUFBdUIsRUFDdkIsWUFBNkIsRUFDaUIsRUFBRTtJQUNoRCxJQUFJLENBQUM7UUFDSCxNQUFNLFNBQVMsR0FBRyxNQUFNLHdDQUF3QyxDQUFDLFNBQVMsQ0FBQyxDQUFDO1FBRTVFLE1BQU0saUJBQWlCLEdBQUcsU0FBUyxDQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUMsRUFBRSxnQkFBZ0IsQ0FBQyxDQUFDO1FBRXpFLE1BQU0saUJBQWlCLEdBQUcsU0FBUyxDQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsZ0JBQWdCLENBQUMsQ0FBQztRQUN4RSxpQ0FBaUM7UUFDakMsTUFBTSxtQkFBbUIsR0FBNkIsRUFBRSxDQUFDO1FBQ3pELHVCQUF1QjtRQUN2QixNQUFNLE1BQU0sR0FBZ0IsRUFBRSxDQUFDO1FBQy9CLDBCQUEwQjtRQUMxQixNQUFNLGFBQWEsR0FBZ0IsRUFBRSxDQUFDO1FBQ3RDLGFBQWEsQ0FBQyxJQUFJLENBQUMsWUFBWSxDQUFDLENBQUM7UUFDakMsYUFBYTtRQUNiLElBQUksaUJBQWlCLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ2xDLEtBQUssSUFBSSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsR0FBRyxpQkFBaUIsRUFBRSxNQUFNLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztnQkFDbkQsTUFBTSxzQkFBc0IsR0FDMUIsTUFBTSw0Q0FBNEMsQ0FDaEQsaUJBQWlCLENBQUMsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUN2QixlQUFlLEVBQ2YsYUFBYSxFQUNiLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxDQUFDLFFBQVEsRUFDN0IsWUFBWSxDQUNiLENBQUM7Z0JBRUosTUFBTSw0QkFBNEIsR0FBRyxzQkFBc0IsQ0FBQyxJQUFJLENBQzlELENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsU0FBUyxLQUFLLFNBQVMsQ0FDakMsQ0FBQztnQkFDRixNQUFNLDJCQUEyQixHQUFHLHNCQUFzQixDQUFDLE1BQU0sQ0FDL0QsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxTQUFTLEtBQUssU0FBUyxDQUNsQyxDQUFDO2dCQUNGLG1CQUFtQixDQUFDLElBQUksQ0FBQyxHQUFHLDJCQUEyQixDQUFDLENBQUM7Z0JBQ3pELElBQUksNEJBQTRCLEVBQUUsRUFBRSxFQUFFLENBQUM7b0JBQ3JDLGFBQWEsQ0FBQyxJQUFJLENBQ2hCLDRDQUE0QyxDQUMxQyw0QkFBNEIsRUFDNUIsaUJBQWlCLENBQUMsQ0FBQyxDQUFDLEVBQUUsTUFBTSxDQUM3QixDQUNGLENBQUM7Z0JBQ0osQ0FBQztZQUNILENBQUM7UUFDSCxDQUFDO1FBRUQsS0FBSyxJQUFJLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxHQUFHLGlCQUFpQixDQUFDLE1BQU0sRUFBRSxDQUFDLEVBQUUsRUFBRSxDQUFDO1lBQ2xELE1BQU0sU0FBUyxHQUFHLE1BQU0sMkJBQTJCLENBQ2pELGlCQUFpQixDQUFDLENBQUMsQ0FBQyxDQUFDLE1BQU0sRUFDM0IsZUFBZSxFQUNmLGFBQWEsRUFDYixpQkFBaUIsQ0FBQyxDQUFDLENBQUMsQ0FBQyxRQUFRLEVBQzdCLFlBQVksQ0FDYixDQUFDO1lBQ0YsTUFBTSw0QkFBNEIsR0FBRyxTQUFTLENBQUMsSUFBSSxDQUNqRCxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLFNBQVMsS0FBSyxTQUFTLENBQ2xDLENBQUM7WUFDRixNQUFNLGlCQUFpQixHQUFHLFNBQVMsQ0FBQyxNQUFNLENBQ3hDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsU0FBUyxLQUFLLFNBQVMsQ0FDbEMsQ0FBQztZQUNGLE1BQU0sQ0FBQyxJQUFJLENBQUMsR0FBRyxpQkFBaUIsQ0FBQyxDQUFDO1lBQ2xDLElBQUksNEJBQTRCLEVBQUUsRUFBRSxFQUFFLENBQUM7Z0JBQ3JDLGFBQWEsQ0FBQyxJQUFJLENBQUMsNEJBQTRCLENBQUMsQ0FBQztZQUNuRCxDQUFDO1FBQ0gsQ0FBQztRQUVELE1BQU0sb0JBQW9CLEdBQ3hCLE1BQU0sa0RBQWtELENBQUMsU0FBUyxDQUFDLENBQUM7UUFFdEUsTUFBTSw0QkFBNEIsR0FDaEMsYUFBYSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsRUFBRSxFQUFFLENBQUMsQ0FBQztZQUN6QixHQUFHLEVBQUU7WUFDTCxtQkFBbUIsRUFBRSxvQkFBb0I7U0FDMUMsQ0FBQyxDQUFDLENBQUM7UUFFTixNQUFNLGtCQUFrQixHQUFvQixFQUFFLENBQUM7UUFFL0MsS0FBSyxNQUFNLEtBQUssSUFBSSxNQUFNLEVBQUUsQ0FBQztZQUMzQiwwQkFBMEI7WUFDMUIsTUFBTSxtQkFBbUIsR0FBRyxNQUFNLCtCQUErQixDQUMvRCxLQUFLLEVBQUUsRUFBRSxDQUNWLENBQUM7WUFDRixJQUFJLG1CQUFtQixFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztnQkFDcEMsbUJBQW1CLEVBQUUsR0FBRyxDQUFDLENBQUMsRUFBRSxFQUFFLEVBQUUsQ0FDOUIsT0FBTyxDQUFDLEdBQUcsQ0FDVCxFQUFFLEVBQ0YseURBQXlELENBQzFELENBQ0YsQ0FBQztnQkFDRixrQkFBa0IsQ0FBQyxJQUFJLENBQUM7b0JBQ3RCLEdBQUcsS0FBSztvQkFDUixtQkFBbUIsRUFBRSxtQkFBbUI7aUJBQ3pDLENBQUMsQ0FBQztZQUNMLENBQUM7aUJBQU0sQ0FBQztnQkFDTixrQkFBa0IsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDakMsQ0FBQztRQUNILENBQUM7UUFFRCxNQUFNLGNBQWMsR0FBRyxrQkFBa0I7WUFDdkMsRUFBRSxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRTtZQUNWLE1BQU0sVUFBVSxHQUFHLFlBQVksQ0FBQyxTQUFTLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxFQUFFLEtBQUssQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1lBQ2xFLElBQUksVUFBVSxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7Z0JBQ3BCLE9BQU8sSUFBSSxDQUFDO1lBQ2QsQ0FBQztZQUNELE9BQU8sQ0FBQyxDQUFDO1FBQ1gsQ0FBQyxDQUFDO1lBQ0YsRUFBRSxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxJQUFJLENBQUMsQ0FBQztRQUU5QixPQUFPO1lBQ0wsTUFBTSxFQUFFLGNBQWM7WUFDdEIsbUJBQW1CO1lBQ25CLGlCQUFpQixFQUFFLDRCQUE0QjtZQUMvQyxpQkFBaUI7WUFDakIsaUJBQWlCO1NBQ2xCLENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHdDQUF3QyxDQUFDLENBQUM7SUFDM0QsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLE1BQU0sOEJBQThCLEdBQUcsS0FBSyxFQUFFLEtBQW9CLEVBQUUsRUFBRTtJQUNwRSxJQUFJLENBQUM7UUFDSCxNQUFNLE1BQU0sR0FBRyxLQUFLLEVBQUUsTUFBTSxDQUFDO1FBQzdCLE1BQU0sZUFBZSxHQUFHLEtBQUssQ0FBQyxLQUFLLEVBQUUsU0FBUyxFQUFFLEtBQUssQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7YUFDMUQsRUFBRSxDQUFDLEtBQUssRUFBRSxRQUFRLEVBQUUsSUFBSSxDQUFDO2FBQ3pCLEdBQUcsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDO2FBQ1gsTUFBTSxDQUFDLENBQUMsQ0FBQzthQUNULE1BQU0sRUFBRSxDQUFDO1FBQ1osTUFBTSxhQUFhLEdBQUcsS0FBSyxDQUFDLEtBQUssRUFBRSxTQUFTLEVBQUUsS0FBSyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQzthQUN4RCxFQUFFLENBQUMsS0FBSyxFQUFFLFFBQVEsRUFBRSxJQUFJLENBQUM7YUFDekIsSUFBSSxDQUFDLEVBQUUsQ0FBQzthQUNSLE1BQU0sQ0FBQyxFQUFFLENBQUM7YUFDVixNQUFNLEVBQUUsQ0FBQztRQUNaLE1BQU0sWUFBWSxHQUFHLEtBQUssRUFBRSxRQUFRLENBQUM7UUFFckMsTUFBTSwyQkFBMkIsR0FBRyxNQUFNLCtCQUErQixDQUN2RSxLQUFLLEVBQUUsRUFBRSxDQUNWLENBQUM7UUFDRixLQUFLLENBQUMsbUJBQW1CLEdBQUcsMkJBQTJCLENBQUM7UUFFeEQsTUFBTSxNQUFNLEdBQW9CLE1BQU0saUJBQWlCLENBQ3JELE1BQU0sRUFDTixlQUFlLEVBQ2YsYUFBYSxFQUNiLFlBQVksQ0FDYixDQUFDO1FBRUYsTUFBTSxrQkFBa0IsR0FBb0IsRUFBRSxDQUFDO1FBQy9DLE1BQU0sb0JBQW9CLEdBQTRCLEVBQUUsQ0FBQztRQUN6RCxNQUFNLHdCQUF3QixHQUEyQixFQUFFLENBQUM7UUFFNUQsa0JBQWtCLENBQUMsSUFBSSxDQUFDLEdBQUcsTUFBTSxDQUFDLENBQUM7UUFFbkMsNkJBQTZCO1FBQzdCLE1BQU0sRUFBRSxNQUFNLEVBQUUsR0FBRyxLQUFLLENBQUM7UUFDekIsbUVBQW1FO1FBRW5FLE1BQU0sTUFBTSxHQUFHLE1BQU0sb0NBQW9DLENBQUMsS0FBSyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1FBQ3JFLE9BQU8sQ0FBQyxHQUFHLENBQUMsTUFBTSxFQUFFLFNBQVMsQ0FBQyxDQUFDO1FBRS9CLHdCQUF3QjtRQUN4QixNQUFNLEdBQUcsR0FBRyxNQUFNLGlDQUFpQyxDQUFDLE1BQU0sRUFBRSxNQUFNLENBQUMsQ0FBQztRQUNwRSxPQUFPLENBQUMsR0FBRyxDQUFDLEdBQUcsRUFBRSxzQkFBc0IsQ0FBQyxDQUFDO1FBQ3pDLE1BQU0sT0FBTyxHQUFHLEdBQUcsRUFBRSxJQUFJLEVBQUUsSUFBSSxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFDckMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxPQUFPLEVBQUUsMEJBQTBCLENBQUMsQ0FBQztRQUVqRCxtQkFBbUI7UUFDbkIsSUFBSSxDQUFDLE9BQU8sRUFBRSxHQUFHLElBQUksQ0FBQyxLQUFLLEVBQUUsc0JBQXNCLEVBQUUsQ0FBQztZQUNwRCxPQUFPLENBQUMsR0FBRyxDQUFDLGtCQUFrQixDQUFDLENBQUM7WUFDaEMsK0NBQStDO1lBQy9DLE1BQU0sRUFDSixRQUFRLEVBQ1IsWUFBWSxFQUNaLGVBQWUsRUFBRSxjQUFjLEdBQ2hDLEdBQUcsTUFBTSxtQ0FBbUMsQ0FBQyxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUM7WUFDN0QsT0FBTyxDQUFDLEdBQUcsQ0FDVCxRQUFRLEVBQ1IsbURBQW1ELENBQ3BELENBQUM7WUFDRixPQUFPLENBQUMsR0FBRyxDQUNULFlBQVksRUFDWix1REFBdUQsQ0FDeEQsQ0FBQztZQUNGLGtCQUFrQixDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztZQUNsQyxvQkFBb0IsQ0FBQyxJQUFJLENBQUM7Z0JBQ3hCLE9BQU8sRUFBRSxRQUFRLEVBQUUsRUFBRTtnQkFDckIsU0FBUyxFQUFFLFlBQVk7YUFDeEIsQ0FBQyxDQUFDO1lBQ0gsd0JBQXdCLENBQUMsSUFBSSxDQUFDLGNBQWMsQ0FBQyxDQUFDO1FBQ2hELENBQUM7UUFFRCxJQUFJLENBQUMsT0FBTyxFQUFFLEdBQUcsSUFBSSxLQUFLLEVBQUUsc0JBQXNCLEVBQUUsQ0FBQztZQUNuRCxPQUFPLENBQUMsR0FBRyxDQUFDLGtCQUFrQixDQUFDLENBQUM7WUFDaEMsNkVBQTZFO1lBQzdFLE1BQU0sVUFBVSxHQUFtQixNQUFNLHNCQUFzQixDQUM3RCxLQUFLLEVBQUUsRUFBRSxDQUNWLENBQUM7WUFDRixPQUFPLENBQUMsR0FBRyxDQUFDLFVBQVUsRUFBRSxhQUFhLENBQUMsQ0FBQztZQUN2QyxJQUFJLFVBQVUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsRUFBRSxDQUFDO2dCQUN4QixNQUFNLEVBQUUsUUFBUSxFQUFFLFlBQVksRUFBRSxlQUFlLEVBQUUsR0FDL0MsTUFBTSw2REFBNkQsQ0FDakUsS0FBSyxFQUNMLE1BQU0sQ0FDUCxDQUFDO2dCQUNKLE9BQU8sQ0FBQyxHQUFHLENBQ1QsUUFBUSxFQUNSLDZFQUE2RSxDQUM5RSxDQUFDO2dCQUNGLE9BQU8sQ0FBQyxHQUFHLENBQ1QsWUFBWSxFQUNaLGlGQUFpRixDQUNsRixDQUFDO2dCQUNGLGtCQUFrQixDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztnQkFDbEMsb0JBQW9CLENBQUMsSUFBSSxDQUFDO29CQUN4QixPQUFPLEVBQUUsUUFBUSxFQUFFLEVBQUU7b0JBQ3JCLFNBQVMsRUFBRSxZQUFZO2lCQUN4QixDQUFDLENBQUM7Z0JBQ0gsd0JBQXdCLENBQUMsSUFBSSxDQUFDLGVBQWUsQ0FBQyxDQUFDO1lBQ2pELENBQUM7aUJBQU0sQ0FBQztnQkFDTiwrQ0FBK0M7Z0JBQy9DLG1EQUFtRDtnQkFDbkQsS0FBSyxDQUFDLE1BQU0sR0FBRyxNQUFNLENBQUM7Z0JBQ3RCLGtCQUFrQixDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztZQUNqQyxDQUFDO1FBQ0gsQ0FBQztRQUVELDhEQUE4RDtRQUM5RCxJQUFJLE9BQU8sRUFBRSxHQUFHLElBQUksQ0FBQyxLQUFLLEVBQUUsc0JBQXNCLEVBQUUsQ0FBQztZQUNuRCx3Q0FBd0M7WUFDeEMsTUFBTSxhQUFhLEdBQUcsTUFBTSxzQkFBc0IsQ0FBQyxPQUFPLEVBQUUsR0FBRyxDQUFDLENBQUM7WUFDakUsSUFBSSxhQUFhLEVBQUUsRUFBRSxFQUFFLENBQUM7Z0JBQ3RCLE1BQU0sbUJBQW1CLEdBQUcsTUFBTSwrQkFBK0IsQ0FDL0QsT0FBTyxFQUFFLEdBQUcsQ0FDYixDQUFDO2dCQUNGLGFBQWEsQ0FBQyxtQkFBbUIsR0FBRyxtQkFBbUIsQ0FBQztZQUMxRCxDQUFDO1lBRUQsOENBQThDO1lBQzlDLElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQztnQkFDbkIsT0FBTyxDQUFDLEdBQUcsQ0FDVCxPQUFPLEVBQUUsR0FBRyxFQUNaLG1GQUFtRixDQUNwRixDQUFDO2dCQUNGLE1BQU0sa0JBQWtCLENBQUMsT0FBTyxFQUFFLEdBQUcsQ0FBQyxDQUFDO2dCQUN2QyxJQUFJLENBQUMsS0FBSyxFQUFFLHNCQUFzQixFQUFFLENBQUM7b0JBQ25DLE9BQU8sQ0FBQyxHQUFHLENBQUMsa0JBQWtCLENBQUMsQ0FBQztvQkFDaEMsK0NBQStDO29CQUMvQyxNQUFNLEVBQUUsUUFBUSxFQUFFLFlBQVksRUFBRSxlQUFlLEVBQUUsR0FDL0MsTUFBTSxtQ0FBbUMsQ0FBQyxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUM7b0JBQzNELE9BQU8sQ0FBQyxHQUFHLENBQ1QsUUFBUSxFQUNSLG1EQUFtRCxDQUNwRCxDQUFDO29CQUNGLE9BQU8sQ0FBQyxHQUFHLENBQ1QsWUFBWSxFQUNaLHVEQUF1RCxDQUN4RCxDQUFDO29CQUNGLGtCQUFrQixDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztvQkFDbEMsb0JBQW9CLENBQUMsSUFBSSxDQUFDO3dCQUN4QixPQUFPLEVBQUUsUUFBUSxFQUFFLEVBQUU7d0JBQ3JCLFNBQVMsRUFBRSxZQUFZO3FCQUN4QixDQUFDLENBQUM7b0JBQ0gsd0JBQXdCLENBQUMsSUFBSSxDQUFDLGVBQWUsQ0FBQyxDQUFDO2dCQUNqRCxDQUFDO1lBQ0gsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLE1BQU0sRUFBRSxRQUFRLEVBQUUsWUFBWSxFQUFFLGVBQWUsRUFBRSxHQUMvQyxNQUFNLHNDQUFzQyxDQUFDLEtBQUssRUFBRSxPQUFPLEVBQUUsR0FBRyxDQUFDLENBQUM7Z0JBQ3BFLE9BQU8sQ0FBQyxHQUFHLENBQ1QsUUFBUSxFQUNSLHNEQUFzRCxDQUN2RCxDQUFDO2dCQUNGLE9BQU8sQ0FBQyxHQUFHLENBQ1QsWUFBWSxFQUNaLDBEQUEwRCxDQUMzRCxDQUFDO2dCQUNGLGtCQUFrQixDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsQ0FBQztnQkFDbEMsb0JBQW9CLENBQUMsSUFBSSxDQUFDO29CQUN4QixPQUFPLEVBQUUsUUFBUSxFQUFFLEVBQUU7b0JBQ3JCLFNBQVMsRUFBRSxZQUFZO2lCQUN4QixDQUFDLENBQUM7Z0JBQ0gsd0JBQXdCLENBQUMsSUFBSSxDQUFDLGVBQWUsQ0FBQyxDQUFDO1lBQ2pELENBQUM7UUFDSCxDQUFDO1FBRUQsSUFBSSxPQUFPLEVBQUUsR0FBRyxJQUFJLEtBQUssRUFBRSxzQkFBc0IsRUFBRSxDQUFDO1lBQ2xELHdDQUF3QztZQUN4QyxNQUFNLGFBQWEsR0FBRyxNQUFNLHNCQUFzQixDQUFDLE9BQU8sRUFBRSxHQUFHLENBQUMsQ0FBQztZQUNqRSxJQUFJLGFBQWEsRUFBRSxFQUFFLEVBQUUsQ0FBQztnQkFDdEIsTUFBTSxtQkFBbUIsR0FBRyxNQUFNLCtCQUErQixDQUMvRCxPQUFPLEVBQUUsR0FBRyxDQUNiLENBQUM7Z0JBQ0YsYUFBYSxDQUFDLG1CQUFtQixHQUFHLG1CQUFtQixDQUFDO1lBQzFELENBQUM7WUFFRCxJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7Z0JBQ25CLE9BQU8sQ0FBQyxHQUFHLENBQ1QsYUFBYSxFQUNiLGlEQUFpRCxDQUNsRCxDQUFDO2dCQUNGLE1BQU0sa0JBQWtCLENBQUMsT0FBTyxFQUFFLEdBQUcsQ0FBQyxDQUFDO2dCQUV2QyxJQUFJLEtBQUssRUFBRSxzQkFBc0IsRUFBRSxDQUFDO29CQUNsQyxPQUFPLENBQUMsR0FBRyxDQUNULE9BQU8sRUFBRSxHQUFHLEVBQ1osbUZBQW1GLENBQ3BGLENBQUM7b0JBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDO29CQUNoQyw2RUFBNkU7b0JBQzdFLE1BQU0sVUFBVSxHQUFtQixNQUFNLHNCQUFzQixDQUM3RCxLQUFLLEVBQUUsRUFBRSxDQUNWLENBQUM7b0JBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxVQUFVLEVBQUUsYUFBYSxDQUFDLENBQUM7b0JBQ3ZDLElBQUksVUFBVSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxFQUFFLENBQUM7d0JBQ3hCLE1BQU0sRUFBRSxRQUFRLEVBQUUsWUFBWSxFQUFFLGVBQWUsRUFBRSxHQUMvQyxNQUFNLDZEQUE2RCxDQUNqRSxLQUFLLEVBQ0wsTUFBTSxDQUNQLENBQUM7d0JBQ0osT0FBTyxDQUFDLEdBQUcsQ0FDVCxRQUFRLEVBQ1IsNkVBQTZFLENBQzlFLENBQUM7d0JBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FDVCxZQUFZLEVBQ1osaUZBQWlGLENBQ2xGLENBQUM7d0JBQ0Ysa0JBQWtCLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxDQUFDO3dCQUNsQyxvQkFBb0IsQ0FBQyxJQUFJLENBQUM7NEJBQ3hCLE9BQU8sRUFBRSxRQUFRLEVBQUUsRUFBRTs0QkFDckIsU0FBUyxFQUFFLFlBQVk7eUJBQ3hCLENBQUMsQ0FBQzt3QkFDSCx3QkFBd0IsQ0FBQyxJQUFJLENBQUMsZUFBZSxDQUFDLENBQUM7b0JBQ2pELENBQUM7eUJBQU0sQ0FBQzt3QkFDTiwrQ0FBK0M7d0JBQy9DLG1EQUFtRDt3QkFDbkQsS0FBSyxDQUFDLE1BQU0sR0FBRyxNQUFNLENBQUM7d0JBQ3RCLGtCQUFrQixDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztvQkFDakMsQ0FBQztnQkFDSCxDQUFDO1lBQ0gsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLDZFQUE2RTtnQkFDN0UsTUFBTSxVQUFVLEdBQW1CLE1BQU0sc0JBQXNCLENBQzdELEtBQUssRUFBRSxFQUFFLENBQ1YsQ0FBQztnQkFDRixPQUFPLENBQUMsR0FBRyxDQUFDLFVBQVUsRUFBRSxhQUFhLENBQUMsQ0FBQztnQkFDdkMsSUFBSSxVQUFVLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLEVBQUUsQ0FBQztvQkFDeEIsTUFBTSxFQUFFLFFBQVEsRUFBRSxZQUFZLEVBQUUsZUFBZSxFQUFFLEdBQy9DLE1BQU0sZ0VBQWdFLENBQ3BFLEtBQUssRUFDTCxPQUFPLEVBQUUsR0FBRyxDQUNiLENBQUM7b0JBQ0osT0FBTyxDQUFDLEdBQUcsQ0FDVCxRQUFRLEVBQ1IsZ0ZBQWdGLENBQ2pGLENBQUM7b0JBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FDVCxZQUFZLEVBQ1osb0ZBQW9GLENBQ3JGLENBQUM7b0JBQ0Ysa0JBQWtCLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxDQUFDO29CQUNsQyxvQkFBb0IsQ0FBQyxJQUFJLENBQUM7d0JBQ3hCLE9BQU8sRUFBRSxRQUFRLEVBQUUsRUFBRTt3QkFDckIsU0FBUyxFQUFFLFlBQVk7cUJBQ3hCLENBQUMsQ0FBQztvQkFDSCx3QkFBd0IsQ0FBQyxJQUFJLENBQUMsZUFBZSxDQUFDLENBQUM7Z0JBQ2pELENBQUM7cUJBQU0sQ0FBQztvQkFDTixPQUFPLENBQUMsR0FBRyxDQUFDLHFCQUFxQixDQUFDLENBQUM7b0JBQ25DLHFCQUFxQjtvQkFDckIsTUFBTSxhQUFhLEdBQUcsTUFBTSxzQkFBc0IsQ0FBQyxPQUFPLEVBQUUsR0FBRyxDQUFDLENBQUM7b0JBQ2pFLE1BQU0sbUJBQW1CLEdBQUcsTUFBTSwrQkFBK0IsQ0FDL0QsT0FBTyxFQUFFLEdBQUcsQ0FDYixDQUFDO29CQUNGLGFBQWEsQ0FBQyxtQkFBbUIsR0FBRyxtQkFBbUIsQ0FBQztvQkFFeEQsSUFBSSxDQUFDLGFBQWEsRUFBRSxFQUFFLEVBQUUsQ0FBQzt3QkFDdkIsTUFBTSxJQUFJLEtBQUssQ0FBQywwQkFBMEIsQ0FBQyxDQUFDO29CQUM5QyxDQUFDO29CQUNELE1BQU0sZUFBZSxHQUFHLE1BQU0sa0JBQWtCLENBQUMsTUFBTSxDQUFDLENBQUM7b0JBRXpELE1BQU0sRUFDSixnQkFBZ0IsRUFBRSxpQkFBaUIsRUFDbkMsWUFBWSxFQUFFLGFBQWEsRUFDM0IsZUFBZSxFQUFFLGdCQUFnQixHQUNsQyxHQUFHLE1BQU0sbURBQW1ELENBQzNELGFBQWEsRUFDYixLQUFLLEVBQ0wsZUFBZSxFQUNmLE1BQU0sQ0FDUCxDQUFDO29CQUVGLGtCQUFrQixDQUFDLElBQUksQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDO29CQUMzQyxvQkFBb0IsQ0FBQyxJQUFJLENBQUM7d0JBQ3hCLE9BQU8sRUFBRSxpQkFBaUIsRUFBRSxFQUFFO3dCQUM5QixTQUFTLEVBQUUsYUFBYTtxQkFDekIsQ0FBQyxDQUFDO29CQUNILHdCQUF3QixDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO2dCQUNsRCxDQUFDO1lBQ0gsQ0FBQztRQUNILENBQUM7UUFFRCxrQkFBa0IsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUMvQixPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxzREFBc0QsQ0FBQyxDQUN2RSxDQUFDO1FBQ0Ysb0JBQW9CLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FDakMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUseURBQXlELENBQUMsQ0FDMUUsQ0FBQztRQUVGLE1BQU0sbUJBQW1CLEdBQUcsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUMsRUFBRSxTQUFTLENBQUMsQ0FBQztRQUVqRSxNQUFNLG1CQUFtQixHQUE2QixFQUFFLENBQUM7UUFDekQsTUFBTSxnQkFBZ0IsR0FBMkIsRUFBRSxDQUFDO1FBQ3BELE1BQU0saUJBQWlCLEdBQWdDLEVBQUUsQ0FBQztRQUMxRCxNQUFNLGlCQUFpQixHQUFnQyxFQUFFLENBQUM7UUFDMUQsTUFBTSxjQUFjLEdBQWdCLEVBQUUsQ0FBQztRQUV2Qzs7OztXQUlHO1FBRUgsY0FBYyxDQUFDLElBQUksQ0FBQyxHQUFHLGtCQUFrQixDQUFDLENBQUM7UUFDM0MsY0FBYyxDQUFDLElBQUksQ0FBQyxHQUFHLG1CQUFtQixDQUFDLENBQUM7UUFFNUMsS0FBSyxNQUFNLGtCQUFrQixJQUFJLG1CQUFtQixFQUFFLENBQUM7WUFDckQsTUFBTSwwQkFBMEIsR0FBRyxNQUFNLHdCQUF3QixDQUMvRCxlQUFlLEVBQ2YsYUFBYSxFQUNiLFlBQVksRUFDWixrQkFBa0IsRUFBRSxTQUFTLEVBQzdCLGtCQUFrQixFQUNsQixNQUFNLENBQ1AsQ0FBQztZQUVGLElBQUksMEJBQTBCLEVBQUUsTUFBTSxFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztnQkFDbkQsTUFBTSxTQUFTLEdBQUcsMEJBQTBCLEVBQUUsTUFBTSxDQUFDO2dCQUVyRCxjQUFjLENBQUMsSUFBSSxDQUFDLEdBQUcsU0FBUyxDQUFDLENBQUM7Z0JBQ2xDLE1BQU0sQ0FBQyxJQUFJLENBQUMsR0FBRyxTQUFTLENBQUMsQ0FBQztZQUM1QixDQUFDO1lBRUQsSUFBSSwwQkFBMEIsRUFBRSxtQkFBbUIsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7Z0JBQ2hFLG1CQUFtQixDQUFDLElBQUksQ0FDdEIsR0FBRywwQkFBMEIsRUFBRSxtQkFBbUIsQ0FDbkQsQ0FBQztZQUNKLENBQUM7WUFFRCxJQUFJLDBCQUEwQixFQUFFLGlCQUFpQixFQUFFLENBQUM7Z0JBQ2xELGdCQUFnQixDQUFDLElBQUksQ0FBQyxHQUFHLDBCQUEwQixFQUFFLGlCQUFpQixDQUFDLENBQUM7WUFDMUUsQ0FBQztZQUVELElBQUksMEJBQTBCLEVBQUUsaUJBQWlCLEVBQUUsQ0FBQztnQkFDbEQsaUJBQWlCLENBQUMsSUFBSSxDQUNwQixHQUFHLDBCQUEwQixFQUFFLGlCQUFpQixDQUNqRCxDQUFDO1lBQ0osQ0FBQztZQUVELElBQUksMEJBQTBCLEVBQUUsaUJBQWlCLEVBQUUsQ0FBQztnQkFDbEQsaUJBQWlCLENBQUMsSUFBSSxDQUNwQixHQUFHLDBCQUEwQixFQUFFLGlCQUFpQixDQUNqRCxDQUFDO1lBQ0osQ0FBQztRQUNILENBQUM7UUFFRCxPQUFPLHdCQUF3QixDQUM3QixNQUFNLEVBQ04sQ0FBQyxDQUFDLFFBQVEsQ0FBQyxpQkFBaUIsRUFBRSxDQUFDLENBQUMsT0FBTyxDQUFDLEVBQ3hDLGdCQUFnQixFQUNoQixDQUFDLENBQUMsUUFBUSxDQUFDLGNBQWMsRUFBRSxDQUFDLENBQUMsT0FBTyxDQUFDLEVBQ3JDLE1BQU0sRUFDTixlQUFlLEVBQ2YsYUFBYSxFQUNiLFlBQVksRUFDWixDQUFDLENBQUMsUUFBUSxDQUFDLGlCQUFpQixFQUFFLENBQUMsQ0FBQyxPQUFPLENBQUMsRUFDeEMsbUJBQW1CLEVBQUUsTUFBTSxHQUFHLENBQUM7WUFDN0IsQ0FBQyxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsbUJBQW1CLEVBQUUsQ0FBQyxDQUFDLE9BQU8sQ0FBQztZQUM1QyxDQUFDLENBQUMsSUFBSSxDQUNULENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLG1DQUFtQyxDQUFDLENBQUM7SUFDdEQsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLE1BQU0sbUJBQW1CLEdBQUcsS0FBSyxFQUFFLEtBQW9CLEVBQUUsRUFBRTtJQUN6RCxJQUFJLENBQUM7UUFDSCxJQUFJLENBQUMsS0FBSyxFQUFFLEVBQUUsRUFBRSxDQUFDO1lBQ2YsTUFBTSxJQUFJLEtBQUssQ0FBQyxpREFBaUQsQ0FBQyxDQUFDO1FBQ3JFLENBQUM7UUFFRCxPQUFPLDhCQUE4QixDQUFDLEtBQUssQ0FBQyxDQUFDO0lBQy9DLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FDVCxDQUFDLEVBQ0QsNkRBQTZELENBQzlELENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsTUFBTSxtQkFBbUIsR0FBRyxLQUFLLEVBQUUsS0FBc0MsRUFBRSxFQUFFO0lBQzNFLElBQUksQ0FBQztRQUNILE1BQU0sUUFBUSxHQUFHLEtBQUssQ0FBQyxRQUFRLENBQUMsRUFBRSxPQUFPLEVBQUUseUJBQXlCLEVBQUUsQ0FBQyxDQUFDO1FBQ3hFLE1BQU0sUUFBUSxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBRXpCLE1BQU0sUUFBUSxDQUFDLFNBQVMsQ0FBQyxFQUFFLEtBQUssRUFBRSw0QkFBNEIsRUFBRSxDQUFDLENBQUM7UUFFbEUsTUFBTSxRQUFRLENBQUMsR0FBRyxDQUFDO1lBQ2pCLFdBQVcsRUFBRSxLQUFLLEVBQUUsRUFBRSxLQUFLLEVBQUUsU0FBUyxFQUFFLE9BQU8sRUFBRSxFQUFFLEVBQUU7Z0JBQ25ELE9BQU8sQ0FBQyxHQUFHLENBQUM7b0JBQ1YsR0FBRyxFQUFFLE9BQU8sRUFBRSxHQUFHLEVBQUUsUUFBUSxFQUFFO29CQUM3QixLQUFLLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxRQUFRLEVBQUU7b0JBQ2pDLE9BQU8sRUFBRSxPQUFPLEVBQUUsT0FBTztpQkFDMUIsQ0FBQyxDQUFDO2dCQUVILE1BQU0sSUFBSSxHQUFrQixJQUFJLENBQUMsS0FBSyxDQUFDLE9BQU8sRUFBRSxLQUFLLEVBQUUsUUFBUSxFQUFFLENBQUMsQ0FBQztnQkFDbkUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxJQUFJLEVBQUUsT0FBTyxDQUFDLENBQUM7Z0JBRTNCLE1BQU0sbUJBQW1CLENBQUMsSUFBSSxDQUFDLENBQUM7WUFDbEMsQ0FBQztTQUNGLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsK0JBQStCLENBQUMsQ0FBQztJQUNsRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxtQkFBbUIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG5pbXBvcnQgaXNvV2VlayBmcm9tICdkYXlqcy9wbHVnaW4vaXNvV2Vlayc7XG5pbXBvcnQgZHVyYXRpb24gZnJvbSAnZGF5anMvcGx1Z2luL2R1cmF0aW9uJztcbmltcG9ydCBpc0JldHdlZW4gZnJvbSAnZGF5anMvcGx1Z2luL2lzQmV0d2Vlbic7XG5pbXBvcnQgdGltZXpvbmUgZnJvbSAnZGF5anMvcGx1Z2luL3RpbWV6b25lJztcbmltcG9ydCB1dGMgZnJvbSAnZGF5anMvcGx1Z2luL3V0Yyc7XG5cbmltcG9ydCB7IE1lc3NhZ2VRdWV1ZVR5cGUgfSBmcm9tICdAc2NoZWR1bGVfZXZlbnQvX2xpYnMvdHlwZXMvc2NoZWR1bGVFdmVudFNob3J0V29ya2VyL3R5cGVzJztcbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG5pbXBvcnQge1xuICBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMsXG4gIGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzR2l2ZW5NZWV0aW5nSWQsXG4gIGxpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzLFxuICBsaXN0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbk1lZXRpbmdJZCxcbiAgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCxcbiAgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyLFxuICBsaXN0RXZlbnRzRm9yRGF0ZSxcbiAgY29udmVydE1lZXRpbmdBc3Npc3RFdmVudFR5cGVUb0V2ZW50UGx1c1R5cGUsXG4gIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzLFxuICBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50LFxuICBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzLFxuICBnZXRFdmVudEZyb21QcmltYXJ5S2V5LFxuICAvLyBkZWxldGVEb2NJblNlYXJjaDMsIC8vIFJlcGxhY2VkXG4gIHByb2Nlc3NVc2VyRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50LFxuICBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudFdpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzLFxuICBnZXRVc2VyUHJlZmVyZW5jZXMsXG4gIHByb2Nlc3NFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnRXaXRob3V0Q2F0ZWdvcmllcyxcbiAgLy8gc2VhcmNoVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoLCAvLyBSZXBsYWNlZFxuICAvLyBnZXRWZWN0b3JJbkFsbEV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsIC8vIFJlcGxhY2VkXG4gIHNlYXJjaFRyYWluaW5nRGF0YUJ5VmVjdG9yLCAvLyBBZGRlZFxuICBnZXRFdmVudFZlY3RvckJ5SWQsIC8vIEFkZGVkXG4gIGRlbGV0ZVRyYWluaW5nRGF0YUJ5SWQsIC8vIEFkZGVkXG4gIGFkZFRyYWluaW5nRGF0YSwgLy8gQWRkZWRcbn0gZnJvbSAnQHNjaGVkdWxlX2V2ZW50L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHtcbiAgRXZlbnRQbHVzVHlwZSxcbiAgRXZlbnRUeXBlLFxuICBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlLFxuICBFdmVudE1lZXRpbmdQbHVzVHlwZSxcbiAgTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSxcbiAgUmVtaW5kZXJzRm9yRXZlbnRUeXBlLFxuICBCdWZmZXJUaW1lT2JqZWN0VHlwZSxcbiAgQ2F0ZWdvcnlUeXBlLFxuICBUcmFpbmluZ0V2ZW50U2NoZW1hLFxufSBmcm9tICdAc2NoZWR1bGVfZXZlbnQvX2xpYnMvdHlwZXMnOyAvLyBBZGRlZCBUcmFpbmluZ0V2ZW50U2NoZW1hXG5pbXBvcnQgeyBSZXR1cm5WYWx1ZUZvckVhY2hNZWV0aW5nQXNzaXN0VHlwZSB9IGZyb20gJ0BzY2hlZHVsZV9ldmVudC9fbGlicy90eXBlcyc7XG5pbXBvcnQge1xuICBrYWZrYVNjaGVkdWxlRXZlbnRHcm91cElkLFxuICBrYWZrYVNjaGVkdWxlU2hvcnRFdmVudFRvcGljLFxufSBmcm9tICcuLi9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgS2Fma2EsIGxvZ0xldmVsIH0gZnJvbSAna2Fma2Fqcyc7XG5pbXBvcnQgaXAgZnJvbSAnaXAnO1xuXG5kYXlqcy5leHRlbmQoaXNvV2Vlayk7XG5kYXlqcy5leHRlbmQoZHVyYXRpb24pO1xuZGF5anMuZXh0ZW5kKGlzQmV0d2Vlbik7XG5kYXlqcy5leHRlbmQodGltZXpvbmUpO1xuZGF5anMuZXh0ZW5kKHV0Yyk7XG5cbmNvbnN0IGthZmthID0gbmV3IEthZmthKHtcbiAgbG9nTGV2ZWw6IGxvZ0xldmVsLkRFQlVHLFxuICBicm9rZXJzOiBbYGthZmthMToyOTA5MmBdLFxuICBjbGllbnRJZDogJ2F0b21pYycsXG4gIC8vIHNzbDogdHJ1ZSxcbiAgc2FzbDoge1xuICAgIG1lY2hhbmlzbTogJ3BsYWluJywgLy8gc2NyYW0tc2hhLTI1NiBvciBzY3JhbS1zaGEtNTEyXG4gICAgdXNlcm5hbWU6IHByb2Nlc3MuZW52LktBRktBX1VTRVJOQU1FLFxuICAgIHBhc3N3b3JkOiBwcm9jZXNzLmVudi5LQUZLQV9QQVNTV09SRCxcbiAgfSxcbn0pO1xuXG5jb25zdCBwcm9jZXNzRXZlbnRzRm9yUGxhbm5pbmcgPSBhc3luYyAoXG4gIG1haW5Ib3N0SWQ6IHN0cmluZyxcbiAgaW50ZXJuYWxBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSxcbiAgbWVldGluZ0V2ZW50UGx1czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSwgLy8gZXZlbnRzIHdpdGggYSBtZWV0aW5nSWRcbiAgdG90YWxFdmVudHM6IEV2ZW50VHlwZVtdLFxuICBvbGRFdmVudHM6IEV2ZW50VHlwZVtdLFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgZXh0ZXJuYWxBdHRlbmRlZXM/OiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIG1lZXRpbmdBc3Npc3RFdmVudHM/OiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW11cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGV2ZW50czogRXZlbnRQbHVzVHlwZVtdID0gXy5jbG9uZURlZXAodG90YWxFdmVudHMpO1xuICAgIGNvbnN0IHVzZXJNb2RpZmllZEV2ZW50czogRXZlbnRQbHVzVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGV2ZW50IG9mIGV2ZW50cykge1xuICAgICAgLy8gZ2V0IHByZWZlcnJlZFRpbWVSYW5nZXNcbiAgICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXMgPSBhd2FpdCBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KFxuICAgICAgICBldmVudD8uaWRcbiAgICAgICk7XG4gICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzPy5tYXAoKHB0KSA9PlxuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBwdCxcbiAgICAgICAgICAnIHByZWZlcnJlZFRpbWVSYW5nZSBpbnNpZGUgcHJvY2Vzc1VzZXJFdmVudHNGb3JQbGFubmluZydcbiAgICAgICAgKVxuICAgICAgKTtcbiAgICAgIGlmIChwcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXM/Lm1hcCgocHQpID0+XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBwdCxcbiAgICAgICAgICAgICcgcHJlZmVycmVkVGltZVJhbmdlIGluc2lkZSBwcm9jZXNzVXNlckV2ZW50c0ZvclBsYW5uaW5nJ1xuICAgICAgICAgIClcbiAgICAgICAgKTtcbiAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goe1xuICAgICAgICAgIC4uLmV2ZW50LFxuICAgICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXM6IHByZWZlcnJlZFRpbWVSYW5nZXMsXG4gICAgICAgIH0pO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goZXZlbnQpO1xuICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXIoXG4gICAgICBtYWluSG9zdElkLFxuICAgICAgaW50ZXJuYWxBdHRlbmRlZXMsXG4gICAgICBtZWV0aW5nRXZlbnRQbHVzLFxuICAgICAgW10sXG4gICAgICB1c2VyTW9kaWZpZWRFdmVudHMsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgb2xkRXZlbnRzLFxuICAgICAgZXh0ZXJuYWxBdHRlbmRlZXMsXG4gICAgICBtZWV0aW5nQXNzaXN0RXZlbnRzLFxuICAgICAgW10sXG4gICAgICBbXVxuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGV2ZW50cyBmb3IgcGxhbm5pbmcnKTtcbiAgfVxufTtcblxuY29uc3QgcHJvY2Vzc0VhY2hNZWV0aW5nQXNzaXN0ID0gYXN5bmMgKFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgbWVldGluZ0lkOiBzdHJpbmcsXG4gIG1lZXRpbmdFdmVudDogRXZlbnRUeXBlLFxuICBsaXN0ZWRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXVxuKTogUHJvbWlzZTxSZXR1cm5WYWx1ZUZvckVhY2hNZWV0aW5nQXNzaXN0VHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGF0dGVuZGVlcyA9IGF3YWl0IGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzR2l2ZW5NZWV0aW5nSWQobWVldGluZ0lkKTtcblxuICAgIGNvbnN0IGV4dGVybmFsQXR0ZW5kZWVzID0gYXR0ZW5kZWVzLmZpbHRlcigoYSkgPT4gISFhPy5leHRlcm5hbEF0dGVuZGVlKTtcblxuICAgIGNvbnN0IGludGVybmFsQXR0ZW5kZWVzID0gYXR0ZW5kZWVzLmZpbHRlcigoYSkgPT4gIWE/LmV4dGVybmFsQXR0ZW5kZWUpO1xuICAgIC8vIG9yaWdpbmFsIG1lZXRpbmcgYXNzc2l0IGV2ZW50c1xuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSA9IFtdO1xuICAgIC8vIGV2ZW50cyBmb3IgZWFjaCB1c2VyXG4gICAgY29uc3QgZXZlbnRzOiBFdmVudFR5cGVbXSA9IFtdO1xuICAgIC8vIGV2ZW50cyB3aXRoIGEgbWVldGluZ0lkXG4gICAgY29uc3QgbWVldGluZ0V2ZW50czogRXZlbnRUeXBlW10gPSBbXTtcbiAgICBtZWV0aW5nRXZlbnRzLnB1c2gobWVldGluZ0V2ZW50KTtcbiAgICAvLyBnZXQgZXZlbnRzXG4gICAgaWYgKGV4dGVybmFsQXR0ZW5kZWVzPy5sZW5ndGggPiAwKSB7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IGV4dGVybmFsQXR0ZW5kZWVzPy5sZW5ndGg7IGkrKykge1xuICAgICAgICBjb25zdCBuZXdNZWV0aW5nQXNzaXN0RXZlbnRzID1cbiAgICAgICAgICBhd2FpdCBsaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcyhcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzW2ldLmlkLFxuICAgICAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzW2ldLnRpbWV6b25lLFxuICAgICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBtZWV0aW5nQXNzaXN0RXZlbnRGb3JNZWV0aW5nID0gbmV3TWVldGluZ0Fzc2lzdEV2ZW50cy5maW5kKFxuICAgICAgICAgIChtKSA9PiBtLm1lZXRpbmdJZCA9PT0gbWVldGluZ0lkXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IGZpbHRlcmVkTWVldGluZ0Fzc2lzdEV2ZW50cyA9IG5ld01lZXRpbmdBc3Npc3RFdmVudHMuZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlPy5tZWV0aW5nSWQgIT09IG1lZXRpbmdJZFxuICAgICAgICApO1xuICAgICAgICBtZWV0aW5nQXNzaXN0RXZlbnRzLnB1c2goLi4uZmlsdGVyZWRNZWV0aW5nQXNzaXN0RXZlbnRzKTtcbiAgICAgICAgaWYgKG1lZXRpbmdBc3Npc3RFdmVudEZvck1lZXRpbmc/LmlkKSB7XG4gICAgICAgICAgbWVldGluZ0V2ZW50cy5wdXNoKFxuICAgICAgICAgICAgY29udmVydE1lZXRpbmdBc3Npc3RFdmVudFR5cGVUb0V2ZW50UGx1c1R5cGUoXG4gICAgICAgICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudEZvck1lZXRpbmcsXG4gICAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzW2ldPy51c2VySWRcbiAgICAgICAgICAgIClcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuXG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCBpbnRlcm5hbEF0dGVuZGVlcy5sZW5ndGg7IGkrKykge1xuICAgICAgY29uc3QgbmV3RXZlbnRzID0gYXdhaXQgbGlzdEV2ZW50c0ZvclVzZXJHaXZlbkRhdGVzKFxuICAgICAgICBpbnRlcm5hbEF0dGVuZGVlc1tpXS51c2VySWQsXG4gICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgaW50ZXJuYWxBdHRlbmRlZXNbaV0udGltZXpvbmUsXG4gICAgICAgIGhvc3RUaW1lem9uZVxuICAgICAgKTtcbiAgICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RFdmVudEZvck1lZXRpbmcgPSBuZXdFdmVudHMuZmluZChcbiAgICAgICAgKGUpID0+IGU/Lm1lZXRpbmdJZCA9PT0gbWVldGluZ0lkXG4gICAgICApO1xuICAgICAgY29uc3QgZmlsdGVyZWROZXdFdmVudHMgPSBuZXdFdmVudHMuZmlsdGVyKFxuICAgICAgICAoZSkgPT4gZT8ubWVldGluZ0lkICE9PSBtZWV0aW5nSWRcbiAgICAgICk7XG4gICAgICBldmVudHMucHVzaCguLi5maWx0ZXJlZE5ld0V2ZW50cyk7XG4gICAgICBpZiAobWVldGluZ0Fzc2lzdEV2ZW50Rm9yTWVldGluZz8uaWQpIHtcbiAgICAgICAgbWVldGluZ0V2ZW50cy5wdXNoKG1lZXRpbmdBc3Npc3RFdmVudEZvck1lZXRpbmcpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHByZWZlcnJlZFRpbWVzUmFuZ2VzID1cbiAgICAgIGF3YWl0IGxpc3RNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuTWVldGluZ0lkKG1lZXRpbmdJZCk7XG5cbiAgICBjb25zdCBuZXdVc2VyTW9kaWZpZWRNZWV0aW5nRXZlbnRzOiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdID1cbiAgICAgIG1lZXRpbmdFdmVudHMubWFwKChtZSkgPT4gKHtcbiAgICAgICAgLi4ubWUsXG4gICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXM6IHByZWZlcnJlZFRpbWVzUmFuZ2VzLFxuICAgICAgfSkpO1xuXG4gICAgY29uc3QgdXNlck1vZGlmaWVkRXZlbnRzOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgZXZlbnQgb2YgZXZlbnRzKSB7XG4gICAgICAvLyBnZXQgcHJlZmVycmVkVGltZVJhbmdlc1xuICAgICAgY29uc3QgcHJlZmVycmVkVGltZVJhbmdlcyA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoXG4gICAgICAgIGV2ZW50Py5pZFxuICAgICAgKTtcbiAgICAgIGlmIChwcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXM/Lm1hcCgocHQpID0+XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBwdCxcbiAgICAgICAgICAgICcgcHJlZmVycmVkVGltZVJhbmdlIGluc2lkZSBwcm9jZXNzVXNlckV2ZW50c0ZvclBsYW5uaW5nJ1xuICAgICAgICAgIClcbiAgICAgICAgKTtcbiAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goe1xuICAgICAgICAgIC4uLmV2ZW50LFxuICAgICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXM6IHByZWZlcnJlZFRpbWVSYW5nZXMsXG4gICAgICAgIH0pO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goZXZlbnQpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IGZpbHRlcmVkRXZlbnRzID0gdXNlck1vZGlmaWVkRXZlbnRzXG4gICAgICA/Lm1hcCgoZSkgPT4ge1xuICAgICAgICBjb25zdCBmb3VuZEluZGV4ID0gbGlzdGVkRXZlbnRzLmZpbmRJbmRleCgobCkgPT4gbD8uaWQgPT09IGU/LmlkKTtcbiAgICAgICAgaWYgKGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgIHJldHVybiBudWxsO1xuICAgICAgICB9XG4gICAgICAgIHJldHVybiBlO1xuICAgICAgfSlcbiAgICAgID8uZmlsdGVyKChlKSA9PiBlICE9PSBudWxsKTtcblxuICAgIHJldHVybiB7XG4gICAgICBldmVudHM6IGZpbHRlcmVkRXZlbnRzLFxuICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cyxcbiAgICAgIG1lZXRpbmdFdmVudHNQbHVzOiBuZXdVc2VyTW9kaWZpZWRNZWV0aW5nRXZlbnRzLFxuICAgICAgaW50ZXJuYWxBdHRlbmRlZXMsXG4gICAgICBleHRlcm5hbEF0dGVuZGVlcyxcbiAgICB9O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBlYWNoIG1lZXRpbmcgYXNzaXN0Jyk7XG4gIH1cbn07XG5cbmNvbnN0IHByb2Nlc3NFdmVudFNob3J0QXBwbHlGZWF0dXJlcyA9IGFzeW5jIChldmVudDogRXZlbnRQbHVzVHlwZSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGhvc3RJZCA9IGV2ZW50Py51c2VySWQ7XG4gICAgY29uc3Qgd2luZG93U3RhcnREYXRlID0gZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGV2ZW50Py50aW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5hZGQoMSwgJ2gnKVxuICAgICAgLm1pbnV0ZSgwKVxuICAgICAgLmZvcm1hdCgpO1xuICAgIGNvbnN0IHdpbmRvd0VuZERhdGUgPSBkYXlqcyhldmVudD8uc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAudHooZXZlbnQ/LnRpbWV6b25lLCB0cnVlKVxuICAgICAgLmhvdXIoMjMpXG4gICAgICAubWludXRlKDU5KVxuICAgICAgLmZvcm1hdCgpO1xuICAgIGNvbnN0IGhvc3RUaW1lem9uZSA9IGV2ZW50Py50aW1lem9uZTtcblxuICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoXG4gICAgICBldmVudD8uaWRcbiAgICApO1xuICAgIGV2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMgPSBwcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQ7XG5cbiAgICBjb25zdCBldmVudHM6IEV2ZW50UGx1c1R5cGVbXSA9IGF3YWl0IGxpc3RFdmVudHNGb3JEYXRlKFxuICAgICAgaG9zdElkLFxuICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgIGhvc3RUaW1lem9uZVxuICAgICk7XG5cbiAgICBjb25zdCB1c2VyTW9kaWZpZWRFdmVudHM6IEV2ZW50UGx1c1R5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG5ld01vZGlmaWVkUmVtaW5kZXJzOiBSZW1pbmRlcnNGb3JFdmVudFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG5ld01vZGlmaWVkVGltZUJsb2NraW5nczogQnVmZmVyVGltZU9iamVjdFR5cGVbXSA9IFtdO1xuXG4gICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goLi4uZXZlbnRzKTtcblxuICAgIC8vIDEuIGNvbnZlcnQgdG8gdmVjdG9yIHNwYWNlXG4gICAgY29uc3QgeyB1c2VySWQgfSA9IGV2ZW50O1xuICAgIC8vIGNvbnN0IHRleHQgPSBgJHtldmVudD8udGl0bGUgfHwgZXZlbnQ/LnN1bW1hcnl9OiR7ZXZlbnQ/Lm5vdGVzfWBcblxuICAgIGNvbnN0IHZlY3RvciA9IGF3YWl0IGdldFZlY3RvckluQWxsRXZlbnRJbmRleEluT3BlblNlYXJjaChldmVudD8uaWQpO1xuICAgIGNvbnNvbGUubG9nKHZlY3RvciwgJyB2ZWN0b3InKTtcblxuICAgIC8vIDIuIGZpbmQgY2xvc2VzdCBldmVudFxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IHNlYXJjaFRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaCh1c2VySWQsIHZlY3Rvcik7XG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIHNlYXJjaERhdGEnKTtcbiAgICBjb25zdCByZXN1bHRzID0gcmVzPy5oaXRzPy5oaXRzPy5bMF07XG4gICAgY29uc29sZS5sb2cocmVzdWx0cywgJyByZXN1bHRzIGZyb20gc2VhcmNoRGF0YScpO1xuXG4gICAgLy8gdmFsaWRhdGUgcmVzdWx0c1xuICAgIGlmICghcmVzdWx0cz8uX2lkICYmICFldmVudD8udXNlck1vZGlmaWVkQ2F0ZWdvcmllcykge1xuICAgICAgY29uc29sZS5sb2coJ25vIHJlc3VsdHMgZm91bmQnKTtcbiAgICAgIC8vIG5vIHByZXZpb3VzIGV2ZW50IGZvdW5kIHVzZSBDYXRlZ29yeURlZmF1bHRzXG4gICAgICBjb25zdCB7XG4gICAgICAgIG5ld0V2ZW50LFxuICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgIG5ld1RpbWVCbG9ja2luZzogbmV3QnVmZmVyVGltZXMsXG4gICAgICB9ID0gYXdhaXQgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMoZXZlbnQsIHZlY3Rvcik7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICcgbmV3RXZlbnQgZm9yIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzJ1xuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICcgbmV3UmVtaW5kZXJzIGZvciBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0cydcbiAgICAgICk7XG4gICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChuZXdFdmVudCk7XG4gICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgIH0pO1xuICAgICAgbmV3TW9kaWZpZWRUaW1lQmxvY2tpbmdzLnB1c2gobmV3QnVmZmVyVGltZXMpO1xuICAgIH1cblxuICAgIGlmICghcmVzdWx0cz8uX2lkICYmIGV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gcmVzdWx0cyBmb3VuZCcpO1xuICAgICAgLy8gbm8gcHJldmlvdXMgZXZlbnQgZm91bmQgdXNlIHVzZXIgbW9kaWZpZWQgY2F0ZWdvcmllcyBhbmQgY2F0ZWdvcnkgZGVmYXVsdHNcbiAgICAgIGNvbnN0IGNhdGVnb3JpZXM6IENhdGVnb3J5VHlwZVtdID0gYXdhaXQgbGlzdENhdGVnb3JpZXNGb3JFdmVudChcbiAgICAgICAgZXZlbnQ/LmlkXG4gICAgICApO1xuICAgICAgY29uc29sZS5sb2coY2F0ZWdvcmllcywgJyBjYXRlZ29yaWVzJyk7XG4gICAgICBpZiAoY2F0ZWdvcmllcz8uWzBdPy5pZCkge1xuICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld1RpbWVCbG9ja2luZyB9ID1cbiAgICAgICAgICBhd2FpdCBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzKFxuICAgICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgICB2ZWN0b3JcbiAgICAgICAgICApO1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgICAnIG5ld0V2ZW50IGZvciBwcm9jZXNzVXNlckV2ZW50Rm9yQ2F0ZWdvcnlEZWZhdWx0c1dpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzJ1xuICAgICAgICApO1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgJyBuZXdSZW1pbmRlcnMgZm9yIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzV2l0aFVzZXJNb2RpZmllZENhdGVnb3JpZXMnXG4gICAgICAgICk7XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKG5ld0V2ZW50KTtcbiAgICAgICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMucHVzaCh7XG4gICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgIHJlbWluZGVyczogbmV3UmVtaW5kZXJzLFxuICAgICAgICB9KTtcbiAgICAgICAgbmV3TW9kaWZpZWRUaW1lQmxvY2tpbmdzLnB1c2gobmV3VGltZUJsb2NraW5nKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIC8vICBjcmVhdGUgbmV3IGV2ZW50IGRhdGF0eXBlIGluIGVsYXN0aWMgc2VhcmNoXG4gICAgICAgIC8vIGF3YWl0IHB1dERhdGFJblNlYXJjaChldmVudD8uaWQsIHZlY3RvciwgdXNlcklkKVxuICAgICAgICBldmVudC52ZWN0b3IgPSB2ZWN0b3I7XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKGV2ZW50KTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBwcmV2aW91cyBldmVudCBmb3VuZCB1c2UgcHJldmlvdXMgZXZlbnQgdG8gY29weSBvdmVyIHZhbHVlc1xuICAgIGlmIChyZXN1bHRzPy5faWQgJiYgIWV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzKSB7XG4gICAgICAvLyB2YWxkYXRlIGFzIG1pZ2h0IGJlIG9sZCBkZWxldGVkIGV2ZW50XG4gICAgICBjb25zdCBwcmV2aW91c0V2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShyZXN1bHRzPy5faWQpO1xuICAgICAgaWYgKHByZXZpb3VzRXZlbnQ/LmlkKSB7XG4gICAgICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXMgPSBhd2FpdCBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KFxuICAgICAgICAgIHJlc3VsdHM/Ll9pZFxuICAgICAgICApO1xuICAgICAgICBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMgPSBwcmVmZXJyZWRUaW1lUmFuZ2VzO1xuICAgICAgfVxuXG4gICAgICAvLyB0aGVyZSBpcyBubyBldmVudCBmb3VuZCBzbyBjaGFuZ2UgZGlyZWN0aW9uXG4gICAgICBpZiAoIXByZXZpb3VzRXZlbnQpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgcmVzdWx0cz8uX2lkLFxuICAgICAgICAgICdyZXN1bHRzPy5faWQgaW5zaWRlICFwcmV2aW91c0V2ZW50IHJlc3VsdHM/Ll9pZCAmJiAhZXZlbnQ/LnVzZXJNb2RpZmllZENhdGVnb3JpZXMnXG4gICAgICAgICk7XG4gICAgICAgIGF3YWl0IGRlbGV0ZURvY0luU2VhcmNoMyhyZXN1bHRzPy5faWQpO1xuICAgICAgICBpZiAoIWV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coJ25vIHJlc3VsdHMgZm91bmQnKTtcbiAgICAgICAgICAvLyBubyBwcmV2aW91cyBldmVudCBmb3VuZCB1c2UgQ2F0ZWdvcnlEZWZhdWx0c1xuICAgICAgICAgIGNvbnN0IHsgbmV3RXZlbnQsIG5ld1JlbWluZGVycywgbmV3VGltZUJsb2NraW5nIH0gPVxuICAgICAgICAgICAgYXdhaXQgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMoZXZlbnQsIHZlY3Rvcik7XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgICAgICcgbmV3RXZlbnQgZm9yIHByb2Nlc3NVc2VyRXZlbnRGb3JDYXRlZ29yeURlZmF1bHRzJ1xuICAgICAgICAgICk7XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgICAnIG5ld1JlbWluZGVycyBmb3IgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHMnXG4gICAgICAgICAgKTtcbiAgICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChuZXdFdmVudCk7XG4gICAgICAgICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMucHVzaCh7XG4gICAgICAgICAgICBldmVudElkOiBuZXdFdmVudD8uaWQsXG4gICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgICAgICB9KTtcbiAgICAgICAgICBuZXdNb2RpZmllZFRpbWVCbG9ja2luZ3MucHVzaChuZXdUaW1lQmxvY2tpbmcpO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld1RpbWVCbG9ja2luZyB9ID1cbiAgICAgICAgICBhd2FpdCBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudChldmVudCwgcmVzdWx0cz8uX2lkKTtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgbmV3RXZlbnQsXG4gICAgICAgICAgJyBuZXdFdmVudCBmb3IgcHJvY2Vzc1VzZXJFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnQnXG4gICAgICAgICk7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgICAnIG5ld1JlbWluZGVycyBmb3IgcHJvY2Vzc1VzZXJFdmVudFdpdGhGb3VuZFByZXZpb3VzRXZlbnQnXG4gICAgICAgICk7XG4gICAgICAgIHVzZXJNb2RpZmllZEV2ZW50cy5wdXNoKG5ld0V2ZW50KTtcbiAgICAgICAgbmV3TW9kaWZpZWRSZW1pbmRlcnMucHVzaCh7XG4gICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgIHJlbWluZGVyczogbmV3UmVtaW5kZXJzLFxuICAgICAgICB9KTtcbiAgICAgICAgbmV3TW9kaWZpZWRUaW1lQmxvY2tpbmdzLnB1c2gobmV3VGltZUJsb2NraW5nKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAocmVzdWx0cz8uX2lkICYmIGV2ZW50Py51c2VyTW9kaWZpZWRDYXRlZ29yaWVzKSB7XG4gICAgICAvLyB2YWxkYXRlIGFzIG1pZ2h0IGJlIG9sZCBkZWxldGVkIGV2ZW50XG4gICAgICBjb25zdCBwcmV2aW91c0V2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShyZXN1bHRzPy5faWQpO1xuICAgICAgaWYgKHByZXZpb3VzRXZlbnQ/LmlkKSB7XG4gICAgICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXMgPSBhd2FpdCBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KFxuICAgICAgICAgIHJlc3VsdHM/Ll9pZFxuICAgICAgICApO1xuICAgICAgICBwcmV2aW91c0V2ZW50LnByZWZlcnJlZFRpbWVSYW5nZXMgPSBwcmVmZXJyZWRUaW1lUmFuZ2VzO1xuICAgICAgfVxuXG4gICAgICBpZiAoIXByZXZpb3VzRXZlbnQpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgcHJldmlvdXNFdmVudCxcbiAgICAgICAgICAncHJldmlvdXNFdmVudCAtIG9sZCBkZWxldGVkIGV2ZW50IGluIGRvYyBzZWFyY2gnXG4gICAgICAgICk7XG4gICAgICAgIGF3YWl0IGRlbGV0ZURvY0luU2VhcmNoMyhyZXN1bHRzPy5faWQpO1xuXG4gICAgICAgIGlmIChldmVudD8udXNlck1vZGlmaWVkQ2F0ZWdvcmllcykge1xuICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgcmVzdWx0cz8uX2lkLFxuICAgICAgICAgICAgJyByZXN1bHRzPy5faWQgaW5zaWRlICFwcmV2aW91c0V2ZW50IHJlc3VsdHM/Ll9pZCAmJiBldmVudD8udXNlck1vZGlmaWVkQ2F0ZWdvcmllcydcbiAgICAgICAgICApO1xuICAgICAgICAgIGNvbnNvbGUubG9nKCdubyByZXN1bHRzIGZvdW5kJyk7XG4gICAgICAgICAgLy8gbm8gcHJldmlvdXMgZXZlbnQgZm91bmQgdXNlIHVzZXIgbW9kaWZpZWQgY2F0ZWdvcmllcyBhbmQgY2F0ZWdvcnkgZGVmYXVsdHNcbiAgICAgICAgICBjb25zdCBjYXRlZ29yaWVzOiBDYXRlZ29yeVR5cGVbXSA9IGF3YWl0IGxpc3RDYXRlZ29yaWVzRm9yRXZlbnQoXG4gICAgICAgICAgICBldmVudD8uaWRcbiAgICAgICAgICApO1xuICAgICAgICAgIGNvbnNvbGUubG9nKGNhdGVnb3JpZXMsICcgY2F0ZWdvcmllcycpO1xuICAgICAgICAgIGlmIChjYXRlZ29yaWVzPy5bMF0/LmlkKSB7XG4gICAgICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld1RpbWVCbG9ja2luZyB9ID1cbiAgICAgICAgICAgICAgYXdhaXQgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHNXaXRoVXNlck1vZGlmaWVkQ2F0ZWdvcmllcyhcbiAgICAgICAgICAgICAgICBldmVudCxcbiAgICAgICAgICAgICAgICB2ZWN0b3JcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgICAgICAgJyBuZXdFdmVudCBmb3IgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHNXaXRoVXNlck1vZGlmaWVkQ2F0ZWdvcmllcydcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgICAgbmV3UmVtaW5kZXJzLFxuICAgICAgICAgICAgICAnIG5ld1JlbWluZGVycyBmb3IgcHJvY2Vzc1VzZXJFdmVudEZvckNhdGVnb3J5RGVmYXVsdHNXaXRoVXNlck1vZGlmaWVkQ2F0ZWdvcmllcydcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChuZXdFdmVudCk7XG4gICAgICAgICAgICBuZXdNb2RpZmllZFJlbWluZGVycy5wdXNoKHtcbiAgICAgICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgICAgICByZW1pbmRlcnM6IG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgbmV3TW9kaWZpZWRUaW1lQmxvY2tpbmdzLnB1c2gobmV3VGltZUJsb2NraW5nKTtcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgLy8gIGNyZWF0ZSBuZXcgZXZlbnQgZGF0YXR5cGUgaW4gZWxhc3RpYyBzZWFyY2hcbiAgICAgICAgICAgIC8vIGF3YWl0IHB1dERhdGFJblNlYXJjaChldmVudD8uaWQsIHZlY3RvciwgdXNlcklkKVxuICAgICAgICAgICAgZXZlbnQudmVjdG9yID0gdmVjdG9yO1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2goZXZlbnQpO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgLy8gY29uc3QgY2F0ZWdvcmllczogQ2F0ZWdvcnlUeXBlW10gPSBhd2FpdCBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50KGV2ZW50Py5pZClcbiAgICAgICAgY29uc3QgY2F0ZWdvcmllczogQ2F0ZWdvcnlUeXBlW10gPSBhd2FpdCBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50KFxuICAgICAgICAgIGV2ZW50Py5pZFxuICAgICAgICApO1xuICAgICAgICBjb25zb2xlLmxvZyhjYXRlZ29yaWVzLCAnIGNhdGVnb3JpZXMnKTtcbiAgICAgICAgaWYgKGNhdGVnb3JpZXM/LlswXT8uaWQpIHtcbiAgICAgICAgICBjb25zdCB7IG5ld0V2ZW50LCBuZXdSZW1pbmRlcnMsIG5ld1RpbWVCbG9ja2luZyB9ID1cbiAgICAgICAgICAgIGF3YWl0IHByb2Nlc3NVc2VyRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50V2l0aFVzZXJNb2RpZmllZENhdGVnb3JpZXMoXG4gICAgICAgICAgICAgIGV2ZW50LFxuICAgICAgICAgICAgICByZXN1bHRzPy5faWRcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICBuZXdFdmVudCxcbiAgICAgICAgICAgICcgbmV3RXZlbnQgZm9yIHByb2Nlc3NVc2VyRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50V2l0aFVzZXJNb2RpZmllZENhdGVnb3JpZXMnXG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgIG5ld1JlbWluZGVycyxcbiAgICAgICAgICAgICcgbmV3UmVtaW5kZXJzIGZvciBwcm9jZXNzVXNlckV2ZW50V2l0aEZvdW5kUHJldmlvdXNFdmVudFdpdGhVc2VyTW9kaWZpZWRDYXRlZ29yaWVzJ1xuICAgICAgICAgICk7XG4gICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3RXZlbnQpO1xuICAgICAgICAgIG5ld01vZGlmaWVkUmVtaW5kZXJzLnB1c2goe1xuICAgICAgICAgICAgZXZlbnRJZDogbmV3RXZlbnQ/LmlkLFxuICAgICAgICAgICAgcmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMsXG4gICAgICAgICAgfSk7XG4gICAgICAgICAgbmV3TW9kaWZpZWRUaW1lQmxvY2tpbmdzLnB1c2gobmV3VGltZUJsb2NraW5nKTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnbm8gY2F0ZWdvcmllcyBmb3VuZCcpO1xuICAgICAgICAgIC8vIGdldCBwcmV2aW91cyBldmVudFxuICAgICAgICAgIGNvbnN0IHByZXZpb3VzRXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KHJlc3VsdHM/Ll9pZCk7XG4gICAgICAgICAgY29uc3QgcHJlZmVycmVkVGltZVJhbmdlcyA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoXG4gICAgICAgICAgICByZXN1bHRzPy5faWRcbiAgICAgICAgICApO1xuICAgICAgICAgIHByZXZpb3VzRXZlbnQucHJlZmVycmVkVGltZVJhbmdlcyA9IHByZWZlcnJlZFRpbWVSYW5nZXM7XG5cbiAgICAgICAgICBpZiAoIXByZXZpb3VzRXZlbnQ/LmlkKSB7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ3ByZXZpb3VzRXZlbnQgaXMgbWlzc2luZycpO1xuICAgICAgICAgIH1cbiAgICAgICAgICBjb25zdCB1c2VyUHJlZmVyZW5jZXMgPSBhd2FpdCBnZXRVc2VyUHJlZmVyZW5jZXModXNlcklkKTtcblxuICAgICAgICAgIGNvbnN0IHtcbiAgICAgICAgICAgIG5ld01vZGlmaWVkRXZlbnQ6IG5ld01vZGlmaWVkRXZlbnQxLFxuICAgICAgICAgICAgbmV3UmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMxLFxuICAgICAgICAgICAgbmV3VGltZUJsb2NraW5nOiBuZXdUaW1lQmxvY2tpbmcxLFxuICAgICAgICAgIH0gPSBhd2FpdCBwcm9jZXNzRXZlbnRXaXRoRm91bmRQcmV2aW91c0V2ZW50V2l0aG91dENhdGVnb3JpZXMoXG4gICAgICAgICAgICBwcmV2aW91c0V2ZW50LFxuICAgICAgICAgICAgZXZlbnQsXG4gICAgICAgICAgICB1c2VyUHJlZmVyZW5jZXMsXG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgdXNlck1vZGlmaWVkRXZlbnRzLnB1c2gobmV3TW9kaWZpZWRFdmVudDEpO1xuICAgICAgICAgIG5ld01vZGlmaWVkUmVtaW5kZXJzLnB1c2goe1xuICAgICAgICAgICAgZXZlbnRJZDogbmV3TW9kaWZpZWRFdmVudDE/LmlkLFxuICAgICAgICAgICAgcmVtaW5kZXJzOiBuZXdSZW1pbmRlcnMxLFxuICAgICAgICAgIH0pO1xuICAgICAgICAgIG5ld01vZGlmaWVkVGltZUJsb2NraW5ncy5wdXNoKG5ld1RpbWVCbG9ja2luZzEpO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuXG4gICAgdXNlck1vZGlmaWVkRXZlbnRzLmZvckVhY2goKGUpID0+XG4gICAgICBjb25zb2xlLmxvZyhlLCAnIHVzZXJNb2RpZmllZEV2ZW50IGJlZm9yZSBwcm9jZXNzaW5nIGZvciBPcHRhcGxhbm5lcicpXG4gICAgKTtcbiAgICBuZXdNb2RpZmllZFJlbWluZGVycy5mb3JFYWNoKChlKSA9PlxuICAgICAgY29uc29sZS5sb2coZSwgJyBuZXdNb2RpZmllZFJlbWluZGVycyBiZWZvcmUgcHJvY2Vzc2luZyBmb3IgT3B0YXBsYW5uZXInKVxuICAgICk7XG5cbiAgICBjb25zdCBldmVudHNXaXRoTWVldGluZ0lkID0gZXZlbnRzLmZpbHRlcigoZSkgPT4gISFlPy5tZWV0aW5nSWQpO1xuXG4gICAgY29uc3QgbWVldGluZ0Fzc2lzdEV2ZW50czogTWVldGluZ0Fzc2lzdEV2ZW50VHlwZVtdID0gW107XG4gICAgY29uc3QgbWVldGluZ0V2ZW50UGx1czogRXZlbnRNZWV0aW5nUGx1c1R5cGVbXSA9IFtdO1xuICAgIGNvbnN0IGludGVybmFsQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10gPSBbXTtcbiAgICBjb25zdCBleHRlcm5hbEF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdID0gW107XG4gICAgY29uc3QgZmlsdGVyZWRFdmVudHM6IEV2ZW50VHlwZVtdID0gW107XG5cbiAgICAvKipcbiAgICAgKiBxdWV1ZSBmb3IgZWFjaFxuICAgICAqIHBhcmVudEtleTogaG9zdElkL3NpbmdsZXRvbklkXG4gICAgICogb2xkQ2hpbGRLZXk6IGhvc3RJZC9tZWV0aW5nSWRcbiAgICAgKi9cblxuICAgIGZpbHRlcmVkRXZlbnRzLnB1c2goLi4udXNlck1vZGlmaWVkRXZlbnRzKTtcbiAgICBmaWx0ZXJlZEV2ZW50cy5wdXNoKC4uLmV2ZW50c1dpdGhNZWV0aW5nSWQpO1xuXG4gICAgZm9yIChjb25zdCBldmVudFdpdGhNZWV0aW5nSWQgb2YgZXZlbnRzV2l0aE1lZXRpbmdJZCkge1xuICAgICAgY29uc3QgcmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmcgPSBhd2FpdCBwcm9jZXNzRWFjaE1lZXRpbmdBc3Npc3QoXG4gICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICBldmVudFdpdGhNZWV0aW5nSWQ/Lm1lZXRpbmdJZCxcbiAgICAgICAgZXZlbnRXaXRoTWVldGluZ0lkLFxuICAgICAgICBldmVudHNcbiAgICAgICk7XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uZXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGNvbnN0IG5ld0V2ZW50cyA9IHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5ldmVudHM7XG5cbiAgICAgICAgZmlsdGVyZWRFdmVudHMucHVzaCguLi5uZXdFdmVudHMpO1xuICAgICAgICBldmVudHMucHVzaCguLi5uZXdFdmVudHMpO1xuICAgICAgfVxuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/Lm1lZXRpbmdBc3Npc3RFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cy5wdXNoKFxuICAgICAgICAgIC4uLnJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5tZWV0aW5nQXNzaXN0RXZlbnRzXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8ubWVldGluZ0V2ZW50c1BsdXMpIHtcbiAgICAgICAgbWVldGluZ0V2ZW50UGx1cy5wdXNoKC4uLnJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5tZWV0aW5nRXZlbnRzUGx1cyk7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uaW50ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgaW50ZXJuYWxBdHRlbmRlZXMucHVzaChcbiAgICAgICAgICAuLi5yZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8uaW50ZXJuYWxBdHRlbmRlZXNcbiAgICAgICAgKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5leHRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgICBleHRlcm5hbEF0dGVuZGVlcy5wdXNoKFxuICAgICAgICAgIC4uLnJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5leHRlcm5hbEF0dGVuZGVlc1xuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiBwcm9jZXNzRXZlbnRzRm9yUGxhbm5pbmcoXG4gICAgICBob3N0SWQsXG4gICAgICBfLnVuaXFXaXRoKGludGVybmFsQXR0ZW5kZWVzLCBfLmlzRXF1YWwpLFxuICAgICAgbWVldGluZ0V2ZW50UGx1cyxcbiAgICAgIF8udW5pcVdpdGgoZmlsdGVyZWRFdmVudHMsIF8uaXNFcXVhbCksXG4gICAgICBldmVudHMsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgXy51bmlxV2l0aChleHRlcm5hbEF0dGVuZGVlcywgXy5pc0VxdWFsKSxcbiAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHM/Lmxlbmd0aCA+IDBcbiAgICAgICAgPyBfLnVuaXFXaXRoKG1lZXRpbmdBc3Npc3RFdmVudHMsIF8uaXNFcXVhbClcbiAgICAgICAgOiBudWxsXG4gICAgKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgbWVldGluZyBhc3Npc3QnKTtcbiAgfVxufTtcblxuY29uc3QgcHJvY2Vzc1F1ZXVlTWVzc2FnZSA9IGFzeW5jIChldmVudDogRXZlbnRQbHVzVHlwZSkgPT4ge1xuICB0cnkge1xuICAgIGlmICghZXZlbnQ/LmlkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHVzZXJJZCBwcm92aWRlZCBpbnNpZGUgYXRvbWljIG1lZXRpbmcgYXNzaXN0Jyk7XG4gICAgfVxuXG4gICAgcmV0dXJuIHByb2Nlc3NFdmVudFNob3J0QXBwbHlGZWF0dXJlcyhldmVudCk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBwcm9jZXNzUXVldWVNZXNzYWdlIGluc2lkZSBhdG9taWMgbWVldGluZyBhc3Npc3QnXG4gICAgKTtcbiAgfVxufTtcblxuY29uc3Qgc2NoZWR1bGVFdmVudFdvcmtlciA9IGFzeW5jIChldmVudDogeyBSZWNvcmRzOiBNZXNzYWdlUXVldWVUeXBlW10gfSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGNvbnN1bWVyID0ga2Fma2EuY29uc3VtZXIoeyBncm91cElkOiBrYWZrYVNjaGVkdWxlRXZlbnRHcm91cElkIH0pO1xuICAgIGF3YWl0IGNvbnN1bWVyLmNvbm5lY3QoKTtcblxuICAgIGF3YWl0IGNvbnN1bWVyLnN1YnNjcmliZSh7IHRvcGljOiBrYWZrYVNjaGVkdWxlU2hvcnRFdmVudFRvcGljIH0pO1xuXG4gICAgYXdhaXQgY29uc3VtZXIucnVuKHtcbiAgICAgIGVhY2hNZXNzYWdlOiBhc3luYyAoeyB0b3BpYywgcGFydGl0aW9uLCBtZXNzYWdlIH0pID0+IHtcbiAgICAgICAgY29uc29sZS5sb2coe1xuICAgICAgICAgIGtleTogbWVzc2FnZT8ua2V5Py50b1N0cmluZygpLFxuICAgICAgICAgIHZhbHVlOiBtZXNzYWdlPy52YWx1ZT8udG9TdHJpbmcoKSxcbiAgICAgICAgICBoZWFkZXJzOiBtZXNzYWdlPy5oZWFkZXJzLFxuICAgICAgICB9KTtcblxuICAgICAgICBjb25zdCBib2R5OiBFdmVudFBsdXNUeXBlID0gSlNPTi5wYXJzZShtZXNzYWdlPy52YWx1ZT8udG9TdHJpbmcoKSk7XG4gICAgICAgIGNvbnNvbGUubG9nKGJvZHksICcgYm9keScpO1xuXG4gICAgICAgIGF3YWl0IHByb2Nlc3NRdWV1ZU1lc3NhZ2UoYm9keSk7XG4gICAgICB9LFxuICAgIH0pO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gYXNzaXN0IGZvciBtZWV0aW5nJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBkZWZhdWx0IHNjaGVkdWxlRXZlbnRXb3JrZXI7XG4iXX0=