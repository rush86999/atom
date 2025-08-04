import { Kafka, logLevel } from 'kafkajs';
import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import _ from 'lodash';
import { listEventsForUserGivenDates, listMeetingAssistAttendeesGivenMeetingId, listMeetingAssistEventsForAttendeeGivenDates, listMeetingAssistPreferredTimeRangesGivenMeetingId, listPreferredTimeRangesForEvent, processEventsForOptaPlanner, listEventsForDate, convertMeetingAssistEventTypeToEventPlusType, getMeetingAssist, generateNewMeetingEventForAttendee, listFutureMeetingAssists, meetingAttendeeCountGivenMeetingId, createRemindersFromMinutesAndEvent, createBufferTimeForNewMeetingEvent, getGlobalCalendar, } from '@schedule_assist/_libs/api-helper';
import { kafkaScheduleAssistGroupId, kafkaScheduleAssistTopic, } from '../_libs/constants';
import { parseUserRequest } from '../_libs/llm-helper';
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
function getRandomInt(min, max) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min) + min); // The maximum is exclusive and the minimum is inclusive
}
const processEachFutureMeetingAssist = async (windowStartDate, windowEndDate, meetingId, listedEvents) => {
    try {
        const meetingAssist = await getMeetingAssist(meetingId);
        // const hostId = meetingAssist?.userId
        const preferredTimesRanges = await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);
        const attendees = await listMeetingAssistAttendeesGivenMeetingId(meetingId);
        const hostTimezone = meetingAssist?.timezone;
        // fake generate events
        const newMeetingEvents = [];
        for (let i = 0; i < attendees.length; i++) {
            let calendarId = null;
            if (!attendees?.[i]?.externalAttendee) {
                calendarId = (await getGlobalCalendar(attendees?.[i]?.userId))?.id;
            }
            const randonNumber = getRandomInt(0, preferredTimesRanges?.length ?? 1);
            const newMeetingEvent = generateNewMeetingEventForAttendee(attendees?.[i], meetingAssist, windowStartDate, windowEndDate, hostTimezone, calendarId, preferredTimesRanges?.[randonNumber]);
            newMeetingEvents.push({
                ...newMeetingEvent,
                preferredTimeRanges: preferredTimesRanges,
            });
            console.log(newMeetingEvent, ' newMeetingEvent inside processEachFutureMeetingAssist');
        }
        const externalAttendees = attendees.filter((a) => !!a?.externalAttendee);
        const internalAttendees = attendees.filter((a) => !a?.externalAttendee);
        const meetingAssistEvents = [];
        const events = [];
        // get events
        if (externalAttendees?.length > 0) {
            for (let i = 0; i < externalAttendees?.length; i++) {
                const newMeetingAssistEvents = await listMeetingAssistEventsForAttendeeGivenDates(externalAttendees[i].id, windowStartDate, windowEndDate, externalAttendees[i].timezone, hostTimezone);
                if (newMeetingAssistEvents?.length > 0) {
                    meetingAssistEvents.push(...newMeetingAssistEvents);
                }
            }
        }
        // Host is part of internal attendees
        for (let i = 0; i < internalAttendees.length; i++) {
            const newEvents = await listEventsForUserGivenDates(internalAttendees[i].userId, windowStartDate, windowEndDate, internalAttendees[i].timezone, hostTimezone);
            if (newEvents?.length > 0) {
                events.push(...newEvents);
            }
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
                const meetingAssistEventForMeeting = newMeetingAssistEvents?.find((m) => m?.meetingId === meetingId);
                const filteredMeetingAssistEvents = newMeetingAssistEvents?.filter((e) => e?.meetingId !== meetingId);
                if (filteredMeetingAssistEvents?.length > 0) {
                    meetingAssistEvents.push(...filteredMeetingAssistEvents);
                }
                if (meetingAssistEventForMeeting?.id) {
                    meetingEvents.push(convertMeetingAssistEventTypeToEventPlusType(meetingAssistEventForMeeting, externalAttendees[i]?.userId));
                }
            }
        }
        for (let i = 0; i < internalAttendees.length; i++) {
            const newEvents = await listEventsForUserGivenDates(internalAttendees[i].userId, windowStartDate, windowEndDate, internalAttendees[i].timezone, hostTimezone);
            const meetingAssistEventForMeeting = newEvents?.find((e) => e?.meetingId === meetingId);
            const filteredNewEvents = newEvents?.filter((e) => e?.meetingId !== meetingId);
            if (filteredNewEvents?.length > 0) {
                events.push(...filteredNewEvents);
            }
            if (meetingAssistEventForMeeting?.id) {
                meetingEvents.push(meetingAssistEventForMeeting);
            }
        }
        const preferredTimesRanges = await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);
        const newUserModifiedMeetingEvents = meetingEvents?.map((me) => ({
            ...me,
            preferredTimeRanges: preferredTimesRanges,
        }));
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
            meetingEventsPlus: newUserModifiedMeetingEvents,
            internalAttendees,
            externalAttendees,
        };
    }
    catch (e) {
        console.log(e, ' unable to process each meeting assist');
    }
};
const processScheduleAssistWithMeetingAssist = async (body) => {
    try {
        const hostId = body?.userId;
        const windowStartDate = body?.windowStartDate;
        const windowEndDate = body?.windowEndDate;
        const hostTimezone = body?.timezone;
        const events = await listEventsForDate(hostId, windowStartDate, windowEndDate, hostTimezone);
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
        filteredEvents.push(...events);
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
        /**
         * trigger next step:
         * eventsWithMeetingId count processed === length
         * newMeetingAssistsActive count processed === length
         */
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
        if (body.naturalLanguageRequest) {
            const parsedRequest = await parseUserRequest(body.naturalLanguageRequest);
            body = {
                ...body,
                ...parsedRequest,
            };
        }
        const userId = body?.userId;
        const windowStartDate = body?.windowStartDate;
        const windowEndDate = body?.windowEndDate;
        const timezone = body?.timezone;
        if (!userId) {
            throw new Error('no userId provided inside atomic meeting assist');
        }
        if (!windowStartDate) {
            throw new Error('no window start date provided inside atomic meeting assist');
        }
        if (!windowEndDate) {
            throw new Error('no window end date provided inside atomic meeting assist ');
        }
        if (!timezone) {
            throw new Error(' no timezone provided inside atomic meeting assist');
        }
        return processScheduleAssistWithMeetingAssist(body);
    }
    catch (e) {
        console.log(e, ' unable to processQueueMessage inside atomic meeting assist');
    }
};
const scheduleMeetingWorker = async (event) => {
    try {
        const consumer = kafka.consumer({ groupId: kafkaScheduleAssistGroupId });
        await consumer.connect();
        await consumer.subscribe({ topic: kafkaScheduleAssistTopic });
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
export default scheduleMeetingWorker;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsS0FBSyxFQUFFLFFBQVEsRUFBRSxNQUFNLFNBQVMsQ0FBQztBQUMxQyxPQUFPLEtBQUssTUFBTSxPQUFPLENBQUM7QUFDMUIsT0FBTyxPQUFPLE1BQU0sc0JBQXNCLENBQUM7QUFDM0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxTQUFTLE1BQU0sd0JBQXdCLENBQUM7QUFDL0MsT0FBTyxRQUFRLE1BQU0sdUJBQXVCLENBQUM7QUFDN0MsT0FBTyxHQUFHLE1BQU0sa0JBQWtCLENBQUM7QUFNbkMsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBQ3ZCLE9BQU8sRUFDTCwyQkFBMkIsRUFDM0Isd0NBQXdDLEVBQ3hDLDRDQUE0QyxFQUM1QyxrREFBa0QsRUFDbEQsK0JBQStCLEVBQy9CLDJCQUEyQixFQUMzQixpQkFBaUIsRUFDakIsNENBQTRDLEVBQzVDLGdCQUFnQixFQUNoQixrQ0FBa0MsRUFDbEMsd0JBQXdCLEVBQ3hCLGtDQUFrQyxFQUNsQyxrQ0FBa0MsRUFDbEMsa0NBQWtDLEVBQ2xDLGlCQUFpQixHQUNsQixNQUFNLG1DQUFtQyxDQUFDO0FBZTNDLE9BQU8sRUFDTCwwQkFBMEIsRUFDMUIsd0JBQXdCLEdBQ3pCLE1BQU0sb0JBQW9CLENBQUM7QUFDNUIsT0FBTyxFQUFFLGdCQUFnQixFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFFdkQsS0FBSyxDQUFDLE1BQU0sQ0FBQyxPQUFPLENBQUMsQ0FBQztBQUN0QixLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsU0FBUyxDQUFDLENBQUM7QUFDeEIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsQ0FBQztBQUN2QixLQUFLLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FB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K0JBQStCLENBQUMsQ0FBQztJQUNsRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxxQkFBcUIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IEthZmthLCBsb2dMZXZlbCB9IGZyb20gJ2thZmthanMnO1xuaW1wb3J0IGRheWpzIGZyb20gJ2RheWpzJztcbmltcG9ydCBpc29XZWVrIGZyb20gJ2RheWpzL3BsdWdpbi9pc29XZWVrJztcbmltcG9ydCBkdXJhdGlvbiBmcm9tICdkYXlqcy9wbHVnaW4vZHVyYXRpb24nO1xuaW1wb3J0IGlzQmV0d2VlbiBmcm9tICdkYXlqcy9wbHVnaW4vaXNCZXR3ZWVuJztcbmltcG9ydCB0aW1lem9uZSBmcm9tICdkYXlqcy9wbHVnaW4vdGltZXpvbmUnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcblxuaW1wb3J0IHtcbiAgU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGUsXG4gIE1lc3NhZ2VRdWV1ZVR5cGUsXG59IGZyb20gJ0BzY2hlZHVsZV9hc3Npc3QvX2xpYnMvdHlwZXMvc2NoZWR1bGVNZWV0aW5nV29ya2VyL3R5cGVzJztcbmltcG9ydCBfIGZyb20gJ2xvZGFzaCc7XG5pbXBvcnQge1xuICBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMsXG4gIGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzR2l2ZW5NZWV0aW5nSWQsXG4gIGxpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzLFxuICBsaXN0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbk1lZXRpbmdJZCxcbiAgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCxcbiAgcHJvY2Vzc0V2ZW50c0Zvck9wdGFQbGFubmVyLFxuICBsaXN0RXZlbnRzRm9yRGF0ZSxcbiAgY29udmVydE1lZXRpbmdBc3Npc3RFdmVudFR5cGVUb0V2ZW50UGx1c1R5cGUsXG4gIGdldE1lZXRpbmdBc3Npc3QsXG4gIGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUsXG4gIGxpc3RGdXR1cmVNZWV0aW5nQXNzaXN0cyxcbiAgbWVldGluZ0F0dGVuZGVlQ291bnRHaXZlbk1lZXRpbmdJZCxcbiAgY3JlYXRlUmVtaW5kZXJzRnJvbU1pbnV0ZXNBbmRFdmVudCxcbiAgY3JlYXRlQnVmZmVyVGltZUZvck5ld01lZXRpbmdFdmVudCxcbiAgZ2V0R2xvYmFsQ2FsZW5kYXIsXG59IGZyb20gJ0BzY2hlZHVsZV9hc3Npc3QvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQge1xuICBFdmVudFBsdXNUeXBlLFxuICBFdmVudFR5cGUsXG4gIE1lZXRpbmdBc3Npc3RFdmVudFR5cGUsXG4gIEV2ZW50TWVldGluZ1BsdXNUeXBlLFxuICBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlLFxuICBSZXR1cm5WYWx1ZUZvckVhY2hGdXR1cmVNZWV0aW5nQXNzaXN0VHlwZSxcbiAgTWVldGluZ0Fzc2lzdFR5cGUsXG4gIFJlbWluZGVyc0ZvckV2ZW50VHlwZSxcbiAgQnVmZmVyVGltZU9iamVjdFR5cGUsXG4gIFZhbHVlc1RvUmV0dXJuRm9yQnVmZmVyRXZlbnRzVHlwZSxcbn0gZnJvbSAnQHNjaGVkdWxlX2Fzc2lzdC9fbGlicy90eXBlcyc7XG5pbXBvcnQgeyBSZXR1cm5WYWx1ZUZvckVhY2hNZWV0aW5nQXNzaXN0VHlwZSB9IGZyb20gJ0BzY2hlZHVsZV9hc3Npc3QvX2xpYnMvdHlwZXMnO1xuaW1wb3J0IGlwIGZyb20gJ2lwJztcbmltcG9ydCB7XG4gIGthZmthU2NoZWR1bGVBc3Npc3RHcm91cElkLFxuICBrYWZrYVNjaGVkdWxlQXNzaXN0VG9waWMsXG59IGZyb20gJy4uL19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBwYXJzZVVzZXJSZXF1ZXN0IH0gZnJvbSAnLi4vX2xpYnMvbGxtLWhlbHBlcic7XG5cbmRheWpzLmV4dGVuZChpc29XZWVrKTtcbmRheWpzLmV4dGVuZChkdXJhdGlvbik7XG5kYXlqcy5leHRlbmQoaXNCZXR3ZWVuKTtcbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5kYXlqcy5leHRlbmQodXRjKTtcblxuY29uc3Qga2Fma2EgPSBuZXcgS2Fma2Eoe1xuICBsb2dMZXZlbDogbG9nTGV2ZWwuREVCVUcsXG4gIGJyb2tlcnM6IFtga2Fma2ExOjI5MDkyYF0sXG4gIGNsaWVudElkOiAnYXRvbWljJyxcbiAgLy8gc3NsOiB0cnVlLFxuICBzYXNsOiB7XG4gICAgbWVjaGFuaXNtOiAncGxhaW4nLCAvLyBzY3JhbS1zaGEtMjU2IG9yIHNjcmFtLXNoYS01MTJcbiAgICB1c2VybmFtZTogcHJvY2Vzcy5lbnYuS0FGS0FfVVNFUk5BTUUsXG4gICAgcGFzc3dvcmQ6IHByb2Nlc3MuZW52LktBRktBX1BBU1NXT1JELFxuICB9LFxufSk7XG5cbmNvbnN0IHByb2Nlc3NFdmVudHNGb3JQbGFubmluZyA9IGFzeW5jIChcbiAgbWFpbkhvc3RJZDogc3RyaW5nLFxuICBpbnRlcm5hbEF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdLFxuICBtZWV0aW5nRXZlbnRQbHVzOiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdLCAvLyBldmVudHMgd2l0aCBhIG1lZXRpbmdJZFxuICBuZXdNZWV0aW5nRXZlbnRQbHVzOiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdLCAvLyBnZW5lcmF0ZWQgZXZlbnRzXG4gIG5ld01lZXRpbmdBc3Npc3RzOiBNZWV0aW5nQXNzaXN0VHlwZVtdLFxuICB0b3RhbEV2ZW50czogRXZlbnRUeXBlW10sXG4gIG9sZEV2ZW50czogRXZlbnRUeXBlW10sXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBleHRlcm5hbEF0dGVuZGVlcz86IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSxcbiAgbWVldGluZ0Fzc2lzdEV2ZW50cz86IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZXZlbnRzOiBFdmVudFBsdXNUeXBlW10gPSBfLmNsb25lRGVlcCh0b3RhbEV2ZW50cyk7XG4gICAgY29uc3QgdXNlck1vZGlmaWVkRXZlbnRzOiBFdmVudFBsdXNUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgZXZlbnQgb2YgZXZlbnRzKSB7XG4gICAgICAvLyBnZXQgcHJlZmVycmVkVGltZVJhbmdlc1xuICAgICAgY29uc3QgcHJlZmVycmVkVGltZVJhbmdlcyA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQoXG4gICAgICAgIGV2ZW50Py5pZFxuICAgICAgKTtcbiAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXM/Lm1hcCgocHQpID0+XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIHB0LFxuICAgICAgICAgICcgcHJlZmVycmVkVGltZVJhbmdlIGluc2lkZSBwcm9jZXNzVXNlckV2ZW50c0ZvclBsYW5uaW5nJ1xuICAgICAgICApXG4gICAgICApO1xuICAgICAgaWYgKHByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgcHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChwdCkgPT5cbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgIHB0LFxuICAgICAgICAgICAgJyBwcmVmZXJyZWRUaW1lUmFuZ2UgaW5zaWRlIHByb2Nlc3NVc2VyRXZlbnRzRm9yUGxhbm5pbmcnXG4gICAgICAgICAgKVxuICAgICAgICApO1xuICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaCh7XG4gICAgICAgICAgLi4uZXZlbnQsXG4gICAgICAgICAgcHJlZmVycmVkVGltZVJhbmdlczogcHJlZmVycmVkVGltZVJhbmdlcyxcbiAgICAgICAgfSk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB1c2VyTW9kaWZpZWRFdmVudHMucHVzaChldmVudCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgbmV3SG9zdFJlbWluZGVyczogUmVtaW5kZXJzRm9yRXZlbnRUeXBlW10gPSBbXTtcbiAgICBjb25zdCBuZXdIb3N0QnVmZmVyVGltZXM6IEJ1ZmZlclRpbWVPYmplY3RUeXBlW10gPSBbXTtcbiAgICBjb25zdCBuZXdIb3N0TWVldGluZ0V2ZW50c1BsdXM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgbmV3TWVldGluZ0Fzc2lzdCBvZiBuZXdNZWV0aW5nQXNzaXN0cykge1xuICAgICAgbGV0IG5ld0hvc3RNZWV0aW5nRXZlbnRQbHVzID0gbmV3TWVldGluZ0V2ZW50UGx1c1xuICAgICAgICA/LmZpbHRlcigobWUpID0+IG1lPy5tZWV0aW5nSWQgPT09IG5ld01lZXRpbmdBc3Npc3Q/LmlkKVxuICAgICAgICA/LmZpbmQoKG1lKSA9PiBtZT8udXNlcklkID09PSBuZXdNZWV0aW5nQXNzaXN0Py51c2VySWQpO1xuICAgICAgbGV0IG5ld0J1ZmZlclRpbWVGb3JNZWV0aW5nRXZlbnRPckVtcHR5T2JqZWN0OiBCdWZmZXJUaW1lT2JqZWN0VHlwZSA9IHt9O1xuICAgICAgbGV0IG5ld01vZGlmaWVkUmVtaW5kZXJPck51bGw6IFJlbWluZGVyc0ZvckV2ZW50VHlwZSB8IG51bGwgPSBudWxsO1xuXG4gICAgICBpZiAobmV3SG9zdE1lZXRpbmdFdmVudFBsdXM/LmlkKSB7XG4gICAgICAgIG5ld01vZGlmaWVkUmVtaW5kZXJPck51bGwgPSBuZXdNZWV0aW5nQXNzaXN0Py5yZW1pbmRlcnM/LlswXVxuICAgICAgICAgID8gY3JlYXRlUmVtaW5kZXJzRnJvbU1pbnV0ZXNBbmRFdmVudChcbiAgICAgICAgICAgICAgbmV3SG9zdE1lZXRpbmdFdmVudFBsdXMuaWQsXG4gICAgICAgICAgICAgIG5ld01lZXRpbmdBc3Npc3QucmVtaW5kZXJzLFxuICAgICAgICAgICAgICBuZXdNZWV0aW5nQXNzaXN0LnRpbWV6b25lLFxuICAgICAgICAgICAgICBuZXdNZWV0aW5nQXNzaXN0LnVzZURlZmF1bHRBbGFybXMsXG4gICAgICAgICAgICAgIG5ld01lZXRpbmdBc3Npc3QudXNlcklkXG4gICAgICAgICAgICApXG4gICAgICAgICAgOiBudWxsO1xuICAgICAgfVxuXG4gICAgICBpZiAobmV3TW9kaWZpZWRSZW1pbmRlck9yTnVsbD8ucmVtaW5kZXJzPy5bMF0/LnVzZXJJZCkge1xuICAgICAgICBuZXdIb3N0UmVtaW5kZXJzLnB1c2gobmV3TW9kaWZpZWRSZW1pbmRlck9yTnVsbCk7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHZhbHVlc1RvUmV0dXJuOiBWYWx1ZXNUb1JldHVybkZvckJ1ZmZlckV2ZW50c1R5cGUgPVxuICAgICAgICBuZXdNZWV0aW5nQXNzaXN0Py5idWZmZXJUaW1lPy5hZnRlckV2ZW50ID4gMCB8fFxuICAgICAgICBuZXdNZWV0aW5nQXNzaXN0Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCA+IDBcbiAgICAgICAgICA/IGNyZWF0ZUJ1ZmZlclRpbWVGb3JOZXdNZWV0aW5nRXZlbnQoXG4gICAgICAgICAgICAgIG5ld0hvc3RNZWV0aW5nRXZlbnRQbHVzLFxuICAgICAgICAgICAgICBuZXdNZWV0aW5nQXNzaXN0LmJ1ZmZlclRpbWVcbiAgICAgICAgICAgIClcbiAgICAgICAgICA6IG51bGw7XG5cbiAgICAgIGlmICh2YWx1ZXNUb1JldHVybj8uYmVmb3JlRXZlbnQ/LmlkKSB7XG4gICAgICAgIG5ld0J1ZmZlclRpbWVGb3JNZWV0aW5nRXZlbnRPckVtcHR5T2JqZWN0LmJlZm9yZUV2ZW50ID1cbiAgICAgICAgICB2YWx1ZXNUb1JldHVybi5iZWZvcmVFdmVudDtcbiAgICAgICAgbmV3SG9zdE1lZXRpbmdFdmVudFBsdXMgPSB2YWx1ZXNUb1JldHVybi5uZXdFdmVudDtcbiAgICAgIH1cblxuICAgICAgaWYgKHZhbHVlc1RvUmV0dXJuPy5hZnRlckV2ZW50Py5pZCkge1xuICAgICAgICBuZXdCdWZmZXJUaW1lRm9yTWVldGluZ0V2ZW50T3JFbXB0eU9iamVjdC5hZnRlckV2ZW50ID1cbiAgICAgICAgICB2YWx1ZXNUb1JldHVybi5hZnRlckV2ZW50O1xuICAgICAgICBuZXdIb3N0TWVldGluZ0V2ZW50UGx1cyA9IHZhbHVlc1RvUmV0dXJuLm5ld0V2ZW50O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIG5ld0J1ZmZlclRpbWVGb3JNZWV0aW5nRXZlbnRPckVtcHR5T2JqZWN0Py5hZnRlckV2ZW50Py5pZCB8fFxuICAgICAgICBuZXdCdWZmZXJUaW1lRm9yTWVldGluZ0V2ZW50T3JFbXB0eU9iamVjdD8uYmVmb3JlRXZlbnQ/LmlkXG4gICAgICApIHtcbiAgICAgICAgbmV3SG9zdEJ1ZmZlclRpbWVzLnB1c2gobmV3QnVmZmVyVGltZUZvck1lZXRpbmdFdmVudE9yRW1wdHlPYmplY3QpO1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIG5ld0hvc3RNZWV0aW5nRXZlbnRQbHVzPy5wcmVFdmVudElkIHx8XG4gICAgICAgIG5ld0hvc3RNZWV0aW5nRXZlbnRQbHVzPy5wb3N0RXZlbnRJZFxuICAgICAgKSB7XG4gICAgICAgIG5ld0hvc3RNZWV0aW5nRXZlbnRzUGx1cy5wdXNoKG5ld0hvc3RNZWV0aW5nRXZlbnRQbHVzKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBuZXdNZWV0aW5nRXZlbnRQbHVzUmVtb3ZlZEhvc3RFdmVudHMgPSBfLmRpZmZlcmVuY2VCeShcbiAgICAgIG5ld01lZXRpbmdFdmVudFBsdXMsXG4gICAgICBuZXdIb3N0TWVldGluZ0V2ZW50c1BsdXMsXG4gICAgICAnaWQnXG4gICAgKTtcbiAgICBjb25zdCBuZXdNZWV0aW5nRXZlbnRQbHVzTW9kaWZpZWRIb3N0RXZlbnRzID1cbiAgICAgIG5ld01lZXRpbmdFdmVudFBsdXNSZW1vdmVkSG9zdEV2ZW50cy5jb25jYXQobmV3SG9zdE1lZXRpbmdFdmVudHNQbHVzKTtcblxuICAgIHJldHVybiBwcm9jZXNzRXZlbnRzRm9yT3B0YVBsYW5uZXIoXG4gICAgICBtYWluSG9zdElkLFxuICAgICAgaW50ZXJuYWxBdHRlbmRlZXMsXG4gICAgICBtZWV0aW5nRXZlbnRQbHVzLFxuICAgICAgbmV3TWVldGluZ0V2ZW50UGx1c01vZGlmaWVkSG9zdEV2ZW50cyxcbiAgICAgIHVzZXJNb2RpZmllZEV2ZW50cyxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBvbGRFdmVudHMsXG4gICAgICBleHRlcm5hbEF0dGVuZGVlcyxcbiAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMsXG4gICAgICBuZXdIb3N0UmVtaW5kZXJzPy5sZW5ndGggPiAwID8gbmV3SG9zdFJlbWluZGVycyA6IFtdLFxuICAgICAgbmV3SG9zdEJ1ZmZlclRpbWVzPy5sZW5ndGggPiAwID8gbmV3SG9zdEJ1ZmZlclRpbWVzIDogW11cbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBldmVudHMgZm9yIHBsYW5uaW5nJyk7XG4gIH1cbn07XG5cbmZ1bmN0aW9uIGdldFJhbmRvbUludChtaW4sIG1heCkge1xuICBtaW4gPSBNYXRoLmNlaWwobWluKTtcbiAgbWF4ID0gTWF0aC5mbG9vcihtYXgpO1xuICByZXR1cm4gTWF0aC5mbG9vcihNYXRoLnJhbmRvbSgpICogKG1heCAtIG1pbikgKyBtaW4pOyAvLyBUaGUgbWF4aW11bSBpcyBleGNsdXNpdmUgYW5kIHRoZSBtaW5pbXVtIGlzIGluY2x1c2l2ZVxufVxuY29uc3QgcHJvY2Vzc0VhY2hGdXR1cmVNZWV0aW5nQXNzaXN0ID0gYXN5bmMgKFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBtZWV0aW5nSWQ6IHN0cmluZyxcbiAgbGlzdGVkRXZlbnRzOiBFdmVudFR5cGVbXVxuKTogUHJvbWlzZTxSZXR1cm5WYWx1ZUZvckVhY2hGdXR1cmVNZWV0aW5nQXNzaXN0VHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3QgPSBhd2FpdCBnZXRNZWV0aW5nQXNzaXN0KG1lZXRpbmdJZCk7XG4gICAgLy8gY29uc3QgaG9zdElkID0gbWVldGluZ0Fzc2lzdD8udXNlcklkXG4gICAgY29uc3QgcHJlZmVycmVkVGltZXNSYW5nZXMgPVxuICAgICAgYXdhaXQgbGlzdE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5NZWV0aW5nSWQobWVldGluZ0lkKTtcbiAgICBjb25zdCBhdHRlbmRlZXMgPSBhd2FpdCBsaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlc0dpdmVuTWVldGluZ0lkKG1lZXRpbmdJZCk7XG4gICAgY29uc3QgaG9zdFRpbWV6b25lID0gbWVldGluZ0Fzc2lzdD8udGltZXpvbmU7XG5cbiAgICAvLyBmYWtlIGdlbmVyYXRlIGV2ZW50c1xuICAgIGNvbnN0IG5ld01lZXRpbmdFdmVudHM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10gPSBbXTtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGF0dGVuZGVlcy5sZW5ndGg7IGkrKykge1xuICAgICAgbGV0IGNhbGVuZGFySWQ6IHN0cmluZyB8IG51bGwgPSBudWxsO1xuICAgICAgaWYgKCFhdHRlbmRlZXM/LltpXT8uZXh0ZXJuYWxBdHRlbmRlZSkge1xuICAgICAgICBjYWxlbmRhcklkID0gKGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKGF0dGVuZGVlcz8uW2ldPy51c2VySWQpKT8uaWQ7XG4gICAgICB9XG4gICAgICBjb25zdCByYW5kb25OdW1iZXIgPSBnZXRSYW5kb21JbnQoMCwgcHJlZmVycmVkVGltZXNSYW5nZXM/Lmxlbmd0aCA/PyAxKTtcbiAgICAgIGNvbnN0IG5ld01lZXRpbmdFdmVudCA9IGdlbmVyYXRlTmV3TWVldGluZ0V2ZW50Rm9yQXR0ZW5kZWUoXG4gICAgICAgIGF0dGVuZGVlcz8uW2ldLFxuICAgICAgICBtZWV0aW5nQXNzaXN0LFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgcHJlZmVycmVkVGltZXNSYW5nZXM/LltyYW5kb25OdW1iZXJdXG4gICAgICApO1xuICAgICAgbmV3TWVldGluZ0V2ZW50cy5wdXNoKHtcbiAgICAgICAgLi4ubmV3TWVldGluZ0V2ZW50LFxuICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBwcmVmZXJyZWRUaW1lc1JhbmdlcyxcbiAgICAgIH0pO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIG5ld01lZXRpbmdFdmVudCxcbiAgICAgICAgJyBuZXdNZWV0aW5nRXZlbnQgaW5zaWRlIHByb2Nlc3NFYWNoRnV0dXJlTWVldGluZ0Fzc2lzdCdcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgZXh0ZXJuYWxBdHRlbmRlZXMgPSBhdHRlbmRlZXMuZmlsdGVyKChhKSA9PiAhIWE/LmV4dGVybmFsQXR0ZW5kZWUpO1xuXG4gICAgY29uc3QgaW50ZXJuYWxBdHRlbmRlZXMgPSBhdHRlbmRlZXMuZmlsdGVyKChhKSA9PiAhYT8uZXh0ZXJuYWxBdHRlbmRlZSk7XG5cbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0RXZlbnRzOiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW10gPSBbXTtcbiAgICBjb25zdCBldmVudHM6IEV2ZW50VHlwZVtdID0gW107XG5cbiAgICAvLyBnZXQgZXZlbnRzXG4gICAgaWYgKGV4dGVybmFsQXR0ZW5kZWVzPy5sZW5ndGggPiAwKSB7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IGV4dGVybmFsQXR0ZW5kZWVzPy5sZW5ndGg7IGkrKykge1xuICAgICAgICBjb25zdCBuZXdNZWV0aW5nQXNzaXN0RXZlbnRzID1cbiAgICAgICAgICBhd2FpdCBsaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcyhcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzW2ldLmlkLFxuICAgICAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzW2ldLnRpbWV6b25lLFxuICAgICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgICAgKTtcblxuICAgICAgICBpZiAobmV3TWVldGluZ0Fzc2lzdEV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMucHVzaCguLi5uZXdNZWV0aW5nQXNzaXN0RXZlbnRzKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIC8vIEhvc3QgaXMgcGFydCBvZiBpbnRlcm5hbCBhdHRlbmRlZXNcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGludGVybmFsQXR0ZW5kZWVzLmxlbmd0aDsgaSsrKSB7XG4gICAgICBjb25zdCBuZXdFdmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMoXG4gICAgICAgIGludGVybmFsQXR0ZW5kZWVzW2ldLnVzZXJJZCxcbiAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgICBpbnRlcm5hbEF0dGVuZGVlc1tpXS50aW1lem9uZSxcbiAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICApO1xuXG4gICAgICBpZiAobmV3RXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGV2ZW50cy5wdXNoKC4uLm5ld0V2ZW50cyk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSBldmVudHNcbiAgICAgID8ubWFwKChlKSA9PiB7XG4gICAgICAgIGNvbnN0IGZvdW5kSW5kZXggPSBsaXN0ZWRFdmVudHM/LmZpbmRJbmRleCgobCkgPT4gbD8uaWQgPT09IGU/LmlkKTtcbiAgICAgICAgaWYgKGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgIHJldHVybiBudWxsO1xuICAgICAgICB9XG4gICAgICAgIHJldHVybiBlO1xuICAgICAgfSlcbiAgICAgID8uZmlsdGVyKChlKSA9PiBlICE9PSBudWxsKTtcblxuICAgIHJldHVybiB7XG4gICAgICBldmVudHM6IGZpbHRlcmVkRXZlbnRzLFxuICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cyxcbiAgICAgIG5ld01lZXRpbmdFdmVudFBsdXM6IG5ld01lZXRpbmdFdmVudHMsXG4gICAgICBpbnRlcm5hbEF0dGVuZGVlcyxcbiAgICAgIGV4dGVybmFsQXR0ZW5kZWVzLFxuICAgIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGVhY2ggZnV0dXJlIG1lZXRpbmcgYXNzaXN0Jyk7XG4gIH1cbn07XG5cbmNvbnN0IHByb2Nlc3NFYWNoTWVldGluZ0Fzc2lzdCA9IGFzeW5jIChcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIG1lZXRpbmdJZDogc3RyaW5nLFxuICBtZWV0aW5nRXZlbnQ6IEV2ZW50VHlwZSxcbiAgbGlzdGVkRXZlbnRzOiBFdmVudFR5cGVbXVxuKTogUHJvbWlzZTxSZXR1cm5WYWx1ZUZvckVhY2hNZWV0aW5nQXNzaXN0VHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGF0dGVuZGVlcyA9IGF3YWl0IGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzR2l2ZW5NZWV0aW5nSWQobWVldGluZ0lkKTtcblxuICAgIGNvbnN0IGV4dGVybmFsQXR0ZW5kZWVzID0gYXR0ZW5kZWVzLmZpbHRlcigoYSkgPT4gISFhPy5leHRlcm5hbEF0dGVuZGVlKTtcblxuICAgIGNvbnN0IGludGVybmFsQXR0ZW5kZWVzID0gYXR0ZW5kZWVzLmZpbHRlcigoYSkgPT4gIWE/LmV4dGVybmFsQXR0ZW5kZWUpO1xuICAgIC8vIG9yaWdpbmFsIG1lZXRpbmcgYXNzc2l0IGV2ZW50c1xuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSA9IFtdO1xuICAgIC8vIGV2ZW50cyBmb3IgZWFjaCB1c2VyXG4gICAgY29uc3QgZXZlbnRzOiBFdmVudFR5cGVbXSA9IFtdO1xuICAgIC8vIGV2ZW50cyB3aXRoIGEgbWVldGluZ0lkXG4gICAgY29uc3QgbWVldGluZ0V2ZW50czogRXZlbnRUeXBlW10gPSBbXTtcbiAgICBtZWV0aW5nRXZlbnRzLnB1c2gobWVldGluZ0V2ZW50KTtcbiAgICAvLyBnZXQgZXZlbnRzXG4gICAgaWYgKGV4dGVybmFsQXR0ZW5kZWVzPy5sZW5ndGggPiAwKSB7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IGV4dGVybmFsQXR0ZW5kZWVzPy5sZW5ndGg7IGkrKykge1xuICAgICAgICBjb25zdCBuZXdNZWV0aW5nQXNzaXN0RXZlbnRzID1cbiAgICAgICAgICBhd2FpdCBsaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcyhcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzW2ldLmlkLFxuICAgICAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzW2ldLnRpbWV6b25lLFxuICAgICAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBtZWV0aW5nQXNzaXN0RXZlbnRGb3JNZWV0aW5nID0gbmV3TWVldGluZ0Fzc2lzdEV2ZW50cz8uZmluZChcbiAgICAgICAgICAobSkgPT4gbT8ubWVldGluZ0lkID09PSBtZWV0aW5nSWRcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZmlsdGVyZWRNZWV0aW5nQXNzaXN0RXZlbnRzID0gbmV3TWVldGluZ0Fzc2lzdEV2ZW50cz8uZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlPy5tZWV0aW5nSWQgIT09IG1lZXRpbmdJZFxuICAgICAgICApO1xuICAgICAgICBpZiAoZmlsdGVyZWRNZWV0aW5nQXNzaXN0RXZlbnRzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50cy5wdXNoKC4uLmZpbHRlcmVkTWVldGluZ0Fzc2lzdEV2ZW50cyk7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAobWVldGluZ0Fzc2lzdEV2ZW50Rm9yTWVldGluZz8uaWQpIHtcbiAgICAgICAgICBtZWV0aW5nRXZlbnRzLnB1c2goXG4gICAgICAgICAgICBjb252ZXJ0TWVldGluZ0Fzc2lzdEV2ZW50VHlwZVRvRXZlbnRQbHVzVHlwZShcbiAgICAgICAgICAgICAgbWVldGluZ0Fzc2lzdEV2ZW50Rm9yTWVldGluZyxcbiAgICAgICAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZXNbaV0/LnVzZXJJZFxuICAgICAgICAgICAgKVxuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGludGVybmFsQXR0ZW5kZWVzLmxlbmd0aDsgaSsrKSB7XG4gICAgICBjb25zdCBuZXdFdmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMoXG4gICAgICAgIGludGVybmFsQXR0ZW5kZWVzW2ldLnVzZXJJZCxcbiAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgICBpbnRlcm5hbEF0dGVuZGVlc1tpXS50aW1lem9uZSxcbiAgICAgICAgaG9zdFRpbWV6b25lXG4gICAgICApO1xuICAgICAgY29uc3QgbWVldGluZ0Fzc2lzdEV2ZW50Rm9yTWVldGluZyA9IG5ld0V2ZW50cz8uZmluZChcbiAgICAgICAgKGUpID0+IGU/Lm1lZXRpbmdJZCA9PT0gbWVldGluZ0lkXG4gICAgICApO1xuICAgICAgY29uc3QgZmlsdGVyZWROZXdFdmVudHMgPSBuZXdFdmVudHM/LmZpbHRlcihcbiAgICAgICAgKGUpID0+IGU/Lm1lZXRpbmdJZCAhPT0gbWVldGluZ0lkXG4gICAgICApO1xuXG4gICAgICBpZiAoZmlsdGVyZWROZXdFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgZXZlbnRzLnB1c2goLi4uZmlsdGVyZWROZXdFdmVudHMpO1xuICAgICAgfVxuXG4gICAgICBpZiAobWVldGluZ0Fzc2lzdEV2ZW50Rm9yTWVldGluZz8uaWQpIHtcbiAgICAgICAgbWVldGluZ0V2ZW50cy5wdXNoKG1lZXRpbmdBc3Npc3RFdmVudEZvck1lZXRpbmcpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHByZWZlcnJlZFRpbWVzUmFuZ2VzID1cbiAgICAgIGF3YWl0IGxpc3RNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuTWVldGluZ0lkKG1lZXRpbmdJZCk7XG5cbiAgICBjb25zdCBuZXdVc2VyTW9kaWZpZWRNZWV0aW5nRXZlbnRzOiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdID1cbiAgICAgIG1lZXRpbmdFdmVudHM/Lm1hcCgobWUpID0+ICh7XG4gICAgICAgIC4uLm1lLFxuICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzOiBwcmVmZXJyZWRUaW1lc1JhbmdlcyxcbiAgICAgIH0pKTtcblxuICAgIGNvbnN0IGZpbHRlcmVkRXZlbnRzID0gZXZlbnRzXG4gICAgICA/Lm1hcCgoZSkgPT4ge1xuICAgICAgICBjb25zdCBmb3VuZEluZGV4ID0gbGlzdGVkRXZlbnRzPy5maW5kSW5kZXgoKGwpID0+IGw/LmlkID09PSBlPy5pZCk7XG4gICAgICAgIGlmIChmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4gZTtcbiAgICAgIH0pXG4gICAgICA/LmZpbHRlcigoZSkgPT4gZSAhPT0gbnVsbCk7XG5cbiAgICByZXR1cm4ge1xuICAgICAgZXZlbnRzOiBmaWx0ZXJlZEV2ZW50cyxcbiAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMsXG4gICAgICBtZWV0aW5nRXZlbnRzUGx1czogbmV3VXNlck1vZGlmaWVkTWVldGluZ0V2ZW50cyxcbiAgICAgIGludGVybmFsQXR0ZW5kZWVzLFxuICAgICAgZXh0ZXJuYWxBdHRlbmRlZXMsXG4gICAgfTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgZWFjaCBtZWV0aW5nIGFzc2lzdCcpO1xuICB9XG59O1xuXG5jb25zdCBwcm9jZXNzU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ0Fzc2lzdCA9IGFzeW5jIChcbiAgYm9keTogU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGhvc3RJZCA9IGJvZHk/LnVzZXJJZDtcbiAgICBjb25zdCB3aW5kb3dTdGFydERhdGUgPSBib2R5Py53aW5kb3dTdGFydERhdGU7XG4gICAgY29uc3Qgd2luZG93RW5kRGF0ZSA9IGJvZHk/LndpbmRvd0VuZERhdGU7XG4gICAgY29uc3QgaG9zdFRpbWV6b25lID0gYm9keT8udGltZXpvbmU7XG5cbiAgICBjb25zdCBldmVudHMgPSBhd2FpdCBsaXN0RXZlbnRzRm9yRGF0ZShcbiAgICAgIGhvc3RJZCxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICBob3N0VGltZXpvbmVcbiAgICApO1xuXG4gICAgY29uc3QgZXZlbnRzV2l0aE1lZXRpbmdJZCA9IGV2ZW50cy5maWx0ZXIoKGUpID0+ICEhZT8ubWVldGluZ0lkKTtcblxuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RFdmVudHM6IE1lZXRpbmdBc3Npc3RFdmVudFR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IG1lZXRpbmdFdmVudFBsdXM6IEV2ZW50TWVldGluZ1BsdXNUeXBlW10gPSBbXTtcbiAgICBjb25zdCBpbnRlcm5hbEF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdID0gW107XG4gICAgY29uc3QgZXh0ZXJuYWxBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSA9IFtdO1xuICAgIGNvbnN0IGZpbHRlcmVkRXZlbnRzOiBFdmVudFR5cGVbXSA9IFtdO1xuXG4gICAgLyoqXG4gICAgICogcXVldWUgZm9yIGVhY2hcbiAgICAgKiBwYXJlbnRLZXk6IGhvc3RJZC9zaW5nbGV0b25JZFxuICAgICAqIG9sZENoaWxkS2V5OiBob3N0SWQvbWVldGluZ0lkXG4gICAgICovXG5cbiAgICBmaWx0ZXJlZEV2ZW50cy5wdXNoKC4uLmV2ZW50cyk7XG5cbiAgICBmb3IgKGNvbnN0IGV2ZW50V2l0aE1lZXRpbmdJZCBvZiBldmVudHNXaXRoTWVldGluZ0lkKSB7XG4gICAgICBjb25zdCByZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZyA9IGF3YWl0IHByb2Nlc3NFYWNoTWVldGluZ0Fzc2lzdChcbiAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgIGV2ZW50V2l0aE1lZXRpbmdJZD8ubWVldGluZ0lkLFxuICAgICAgICBldmVudFdpdGhNZWV0aW5nSWQsXG4gICAgICAgIGV2ZW50c1xuICAgICAgKTtcblxuICAgICAgaWYgKHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5ldmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3QgbmV3RXZlbnRzID0gcmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmV2ZW50cztcblxuICAgICAgICBmaWx0ZXJlZEV2ZW50cy5wdXNoKC4uLm5ld0V2ZW50cyk7XG4gICAgICAgIGV2ZW50cy5wdXNoKC4uLm5ld0V2ZW50cyk7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXNGb3JFYWNoTWVldGluZz8ubWVldGluZ0Fzc2lzdEV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBtZWV0aW5nQXNzaXN0RXZlbnRzLnB1c2goXG4gICAgICAgICAgLi4ucmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/Lm1lZXRpbmdBc3Npc3RFdmVudHNcbiAgICAgICAgKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5tZWV0aW5nRXZlbnRzUGx1cykge1xuICAgICAgICBtZWV0aW5nRXZlbnRQbHVzLnB1c2goLi4ucmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/Lm1lZXRpbmdFdmVudHNQbHVzKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5pbnRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgICBpbnRlcm5hbEF0dGVuZGVlcy5wdXNoKFxuICAgICAgICAgIC4uLnJldHVyblZhbHVlc0ZvckVhY2hNZWV0aW5nPy5pbnRlcm5hbEF0dGVuZGVlc1xuICAgICAgICApO1xuICAgICAgfVxuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmV4dGVybmFsQXR0ZW5kZWVzKSB7XG4gICAgICAgIGV4dGVybmFsQXR0ZW5kZWVzLnB1c2goXG4gICAgICAgICAgLi4ucmV0dXJuVmFsdWVzRm9yRWFjaE1lZXRpbmc/LmV4dGVybmFsQXR0ZW5kZWVzXG4gICAgICAgICk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gZnV0dXJlIG1lZXRpbmcgYXNzaXN0c1xuICAgIGNvbnN0IG1lZXRpbmdJZHNUb05vdEluY2x1ZGUgPSBldmVudHNXaXRoTWVldGluZ0lkLm1hcCgoZSkgPT4gZT8ubWVldGluZ0lkKTtcblxuICAgIGNvbnNvbGUubG9nKG1lZXRpbmdJZHNUb05vdEluY2x1ZGUsICcgbWVldGluZ0lkc1RvTm90SW5jbHVkZScpO1xuXG4gICAgY29uc3QgbmV3TWVldGluZ0Fzc2lzdHNOb1RocmVzaG9sZCA9IGF3YWl0IGxpc3RGdXR1cmVNZWV0aW5nQXNzaXN0cyhcbiAgICAgIGhvc3RJZCxcbiAgICAgIGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSkuZm9ybWF0KCksXG4gICAgICBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSkudHooaG9zdFRpbWV6b25lKS5hZGQoMSwgJ2QnKS5mb3JtYXQoKSxcbiAgICAgIG1lZXRpbmdJZHNUb05vdEluY2x1ZGVcbiAgICApO1xuXG4gICAgY29uc29sZS5sb2cobmV3TWVldGluZ0Fzc2lzdHNOb1RocmVzaG9sZCwgJyBuZXdNZWV0aW5nQXNzaXN0c05vVGhyZXNob2xkJyk7XG5cbiAgICBjb25zdCBuZXdNZWV0aW5nRXZlbnRQbHVzOiBFdmVudE1lZXRpbmdQbHVzVHlwZVtdID0gW107XG4gICAgY29uc3QgbmV3TWVldGluZ0Fzc2lzdHNBY3RpdmU6IE1lZXRpbmdBc3Npc3RUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgZnV0dXJlTWVldGluZ0Fzc2lzdCBvZiBuZXdNZWV0aW5nQXNzaXN0c05vVGhyZXNob2xkKSB7XG4gICAgICBjb25zdCBjb3VudCA9IGF3YWl0IG1lZXRpbmdBdHRlbmRlZUNvdW50R2l2ZW5NZWV0aW5nSWQoXG4gICAgICAgIGZ1dHVyZU1lZXRpbmdBc3Npc3Q/LmlkXG4gICAgICApO1xuXG4gICAgICBpZiAoY291bnQgPj0gZnV0dXJlTWVldGluZ0Fzc2lzdD8ubWluVGhyZXNob2xkQ291bnQpIHtcbiAgICAgICAgbmV3TWVldGluZ0Fzc2lzdHNBY3RpdmUucHVzaChmdXR1cmVNZWV0aW5nQXNzaXN0KTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvKipcbiAgICAgKiBxdWV1ZSBmb3IgZWFjaFxuICAgICAqIHBhcmVudEtleTogaG9zdElkL3NpbmdsZXRvbklkXG4gICAgICogbmV3Q2hpbGRLZXk6IGhvc3RJZC9tZWV0aW5nSWRcbiAgICAgKi9cbiAgICBmb3IgKGNvbnN0IGZ1dHVyZU1lZXRpbmdBc3Npc3RBY3RpdmUgb2YgbmV3TWVldGluZ0Fzc2lzdHNBY3RpdmUpIHtcbiAgICAgIGNvbnN0IHJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0ID1cbiAgICAgICAgYXdhaXQgcHJvY2Vzc0VhY2hGdXR1cmVNZWV0aW5nQXNzaXN0KFxuICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgICAgIGZ1dHVyZU1lZXRpbmdBc3Npc3RBY3RpdmU/LmlkLFxuICAgICAgICAgIGV2ZW50c1xuICAgICAgICApO1xuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzRnJvbUZ1dHVyZU1lZXRpbmdBc3Npc3Q/LmV2ZW50cz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBjb25zdCBuZXdFdmVudHMgPSByZXR1cm5WYWx1ZXNGcm9tRnV0dXJlTWVldGluZ0Fzc2lzdD8uZXZlbnRzO1xuXG4gICAgICAgIGZpbHRlcmVkRXZlbnRzLnB1c2goLi4ubmV3RXZlbnRzKTtcbiAgICAgICAgZXZlbnRzLnB1c2goLi4ubmV3RXZlbnRzKTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICByZXR1cm5WYWx1ZXNGcm9tRnV0dXJlTWVldGluZ0Fzc2lzdD8ubWVldGluZ0Fzc2lzdEV2ZW50cz8ubGVuZ3RoID4gMFxuICAgICAgKSB7XG4gICAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHMucHVzaChcbiAgICAgICAgICAuLi5yZXR1cm5WYWx1ZXNGcm9tRnV0dXJlTWVldGluZ0Fzc2lzdD8ubWVldGluZ0Fzc2lzdEV2ZW50c1xuICAgICAgICApO1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIHJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5uZXdNZWV0aW5nRXZlbnRQbHVzPy5sZW5ndGggPiAwXG4gICAgICApIHtcbiAgICAgICAgbmV3TWVldGluZ0V2ZW50UGx1cy5wdXNoKFxuICAgICAgICAgIC4uLnJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5uZXdNZWV0aW5nRXZlbnRQbHVzXG4gICAgICAgICk7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXNGcm9tRnV0dXJlTWVldGluZ0Fzc2lzdD8uaW50ZXJuYWxBdHRlbmRlZXMpIHtcbiAgICAgICAgaW50ZXJuYWxBdHRlbmRlZXMucHVzaChcbiAgICAgICAgICAuLi5yZXR1cm5WYWx1ZXNGcm9tRnV0dXJlTWVldGluZ0Fzc2lzdD8uaW50ZXJuYWxBdHRlbmRlZXNcbiAgICAgICAgKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5leHRlcm5hbEF0dGVuZGVlcykge1xuICAgICAgICBleHRlcm5hbEF0dGVuZGVlcy5wdXNoKFxuICAgICAgICAgIC4uLnJldHVyblZhbHVlc0Zyb21GdXR1cmVNZWV0aW5nQXNzaXN0Py5leHRlcm5hbEF0dGVuZGVlc1xuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8qKlxuICAgICAqIHRyaWdnZXIgbmV4dCBzdGVwOlxuICAgICAqIGV2ZW50c1dpdGhNZWV0aW5nSWQgY291bnQgcHJvY2Vzc2VkID09PSBsZW5ndGhcbiAgICAgKiBuZXdNZWV0aW5nQXNzaXN0c0FjdGl2ZSBjb3VudCBwcm9jZXNzZWQgPT09IGxlbmd0aFxuICAgICAqL1xuICAgIHJldHVybiBwcm9jZXNzRXZlbnRzRm9yUGxhbm5pbmcoXG4gICAgICBob3N0SWQsXG4gICAgICBfLnVuaXFXaXRoKGludGVybmFsQXR0ZW5kZWVzLCBfLmlzRXF1YWwpLFxuICAgICAgbWVldGluZ0V2ZW50UGx1cyxcbiAgICAgIG5ld01lZXRpbmdFdmVudFBsdXMsXG4gICAgICBuZXdNZWV0aW5nQXNzaXN0c0FjdGl2ZSxcbiAgICAgIF8udW5pcVdpdGgoZmlsdGVyZWRFdmVudHMsIF8uaXNFcXVhbCksXG4gICAgICBldmVudHMsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgXy51bmlxV2l0aChleHRlcm5hbEF0dGVuZGVlcywgXy5pc0VxdWFsKSxcbiAgICAgIG1lZXRpbmdBc3Npc3RFdmVudHM/Lmxlbmd0aCA+IDBcbiAgICAgICAgPyBfLnVuaXFXaXRoKG1lZXRpbmdBc3Npc3RFdmVudHMsIF8uaXNFcXVhbClcbiAgICAgICAgOiBudWxsXG4gICAgKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgbWVldGluZyBhc3Npc3QnKTtcbiAgfVxufTtcblxuY29uc3QgcHJvY2Vzc1F1ZXVlTWVzc2FnZSA9IGFzeW5jIChcbiAgYm9keTogU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ1F1ZXVlQm9keVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGlmIChib2R5Lm5hdHVyYWxMYW5ndWFnZVJlcXVlc3QpIHtcbiAgICAgIGNvbnN0IHBhcnNlZFJlcXVlc3QgPSBhd2FpdCBwYXJzZVVzZXJSZXF1ZXN0KGJvZHkubmF0dXJhbExhbmd1YWdlUmVxdWVzdCk7XG4gICAgICBib2R5ID0ge1xuICAgICAgICAuLi5ib2R5LFxuICAgICAgICAuLi5wYXJzZWRSZXF1ZXN0LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBjb25zdCB1c2VySWQgPSBib2R5Py51c2VySWQ7XG4gICAgY29uc3Qgd2luZG93U3RhcnREYXRlID0gYm9keT8ud2luZG93U3RhcnREYXRlO1xuICAgIGNvbnN0IHdpbmRvd0VuZERhdGUgPSBib2R5Py53aW5kb3dFbmREYXRlO1xuICAgIGNvbnN0IHRpbWV6b25lID0gYm9keT8udGltZXpvbmU7XG5cbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyB1c2VySWQgcHJvdmlkZWQgaW5zaWRlIGF0b21pYyBtZWV0aW5nIGFzc2lzdCcpO1xuICAgIH1cblxuICAgIGlmICghd2luZG93U3RhcnREYXRlKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICdubyB3aW5kb3cgc3RhcnQgZGF0ZSBwcm92aWRlZCBpbnNpZGUgYXRvbWljIG1lZXRpbmcgYXNzaXN0J1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBpZiAoIXdpbmRvd0VuZERhdGUpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ25vIHdpbmRvdyBlbmQgZGF0ZSBwcm92aWRlZCBpbnNpZGUgYXRvbWljIG1lZXRpbmcgYXNzaXN0ICdcbiAgICAgICk7XG4gICAgfVxuXG4gICAgaWYgKCF0aW1lem9uZSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCcgbm8gdGltZXpvbmUgcHJvdmlkZWQgaW5zaWRlIGF0b21pYyBtZWV0aW5nIGFzc2lzdCcpO1xuICAgIH1cblxuICAgIHJldHVybiBwcm9jZXNzU2NoZWR1bGVBc3Npc3RXaXRoTWVldGluZ0Fzc2lzdChib2R5KTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3NRdWV1ZU1lc3NhZ2UgaW5zaWRlIGF0b21pYyBtZWV0aW5nIGFzc2lzdCdcbiAgICApO1xuICB9XG59O1xuXG5jb25zdCBzY2hlZHVsZU1lZXRpbmdXb3JrZXIgPSBhc3luYyAoZXZlbnQ6IHtcbiAgUmVjb3JkczogTWVzc2FnZVF1ZXVlVHlwZVtdO1xufSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGNvbnN1bWVyID0ga2Fma2EuY29uc3VtZXIoeyBncm91cElkOiBrYWZrYVNjaGVkdWxlQXNzaXN0R3JvdXBJZCB9KTtcbiAgICBhd2FpdCBjb25zdW1lci5jb25uZWN0KCk7XG5cbiAgICBhd2FpdCBjb25zdW1lci5zdWJzY3JpYmUoeyB0b3BpYzoga2Fma2FTY2hlZHVsZUFzc2lzdFRvcGljIH0pO1xuXG4gICAgYXdhaXQgY29uc3VtZXIucnVuKHtcbiAgICAgIGVhY2hNZXNzYWdlOiBhc3luYyAoeyB0b3BpYywgcGFydGl0aW9uLCBtZXNzYWdlIH0pID0+IHtcbiAgICAgICAgY29uc29sZS5sb2coe1xuICAgICAgICAgIGtleTogbWVzc2FnZT8ua2V5Py50b1N0cmluZygpLFxuICAgICAgICAgIHZhbHVlOiBtZXNzYWdlPy52YWx1ZT8udG9TdHJpbmcoKSxcbiAgICAgICAgICBoZWFkZXJzOiBtZXNzYWdlPy5oZWFkZXJzLFxuICAgICAgICB9KTtcblxuICAgICAgICBjb25zdCBib2R5OiBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZSA9IEpTT04ucGFyc2UoXG4gICAgICAgICAgbWVzc2FnZT8udmFsdWU/LnRvU3RyaW5nKClcbiAgICAgICAgKTtcbiAgICAgICAgY29uc29sZS5sb2coYm9keSwgJyBib2R5Jyk7XG5cbiAgICAgICAgYXdhaXQgcHJvY2Vzc1F1ZXVlTWVzc2FnZShib2R5KTtcbiAgICAgIH0sXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBhc3Npc3QgZm9yIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgc2NoZWR1bGVNZWV0aW5nV29ya2VyO1xuIl19