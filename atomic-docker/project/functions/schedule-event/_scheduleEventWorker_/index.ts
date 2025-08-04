import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

import { MessageQueueType } from '@schedule_event/_libs/types/scheduleEventWorker/types';
import _ from 'lodash';
import {
  listEventsForUserGivenDates,
  listMeetingAssistAttendeesGivenMeetingId,
  listMeetingAssistEventsForAttendeeGivenDates,
  listMeetingAssistPreferredTimeRangesGivenMeetingId,
  listPreferredTimeRangesForEvent,
  processEventsForOptaPlanner,
  listEventsForDate,
  convertMeetingAssistEventTypeToEventPlusType,
  processUserEventForCategoryDefaults,
  listCategoriesForEvent,
  processUserEventForCategoryDefaultsWithUserModifiedCategories,
  getEventFromPrimaryKey,
  // deleteDocInSearch3, // Replaced
  processUserEventWithFoundPreviousEvent,
  processUserEventWithFoundPreviousEventWithUserModifiedCategories,
  getUserPreferences,
  processEventWithFoundPreviousEventWithoutCategories,
  // searchTrainEventIndexInOpenSearch, // Replaced
  // getVectorInAllEventIndexInOpenSearch, // Replaced
  searchTrainingDataByVector, // Added
  getEventVectorById, // Added
  deleteTrainingDataById, // Added
  addTrainingData, // Added
} from '@schedule_event/_libs/api-helper';
import {
  EventPlusType,
  EventType,
  MeetingAssistEventType,
  EventMeetingPlusType,
  MeetingAssistAttendeeType,
  RemindersForEventType,
  BufferTimeObjectType,
  CategoryType,
  TrainingEventSchema,
} from '@schedule_event/_libs/types'; // Added TrainingEventSchema
import { ReturnValueForEachMeetingAssistType } from '@schedule_event/_libs/types';
import {
  kafkaScheduleEventGroupId,
  kafkaScheduleEventTopic,
} from '../_libs/constants';
import { Kafka, logLevel } from 'kafkajs';
import ip from 'ip';

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

const processEventsForPlanning = async (
  mainHostId: string,
  internalAttendees: MeetingAssistAttendeeType[],
  meetingEventPlus: EventMeetingPlusType[], // events with a meetingId
  totalEvents: EventType[],
  oldEvents: EventType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  externalAttendees?: MeetingAssistAttendeeType[],
  meetingAssistEvents?: MeetingAssistEventType[]
) => {
  try {
    const events: EventPlusType[] = _.cloneDeep(totalEvents);
    const userModifiedEvents: EventPlusType[] = [];

    for (const event of events) {
      // get preferredTimeRanges
      const preferredTimeRanges = await listPreferredTimeRangesForEvent(
        event?.id
      );
      preferredTimeRanges?.map((pt) =>
        console.log(
          pt,
          ' preferredTimeRange inside processUserEventsForPlanning'
        )
      );
      if (preferredTimeRanges?.length > 0) {
        preferredTimeRanges?.map((pt) =>
          console.log(
            pt,
            ' preferredTimeRange inside processUserEventsForPlanning'
          )
        );
        userModifiedEvents.push({
          ...event,
          preferredTimeRanges: preferredTimeRanges,
        });
      } else {
        userModifiedEvents.push(event);
      }
    }

    return processEventsForOptaPlanner(
      mainHostId,
      internalAttendees,
      meetingEventPlus,
      [],
      userModifiedEvents,
      windowStartDate,
      windowEndDate,
      hostTimezone,
      oldEvents,
      externalAttendees,
      meetingAssistEvents,
      [],
      []
    );
  } catch (e) {
    console.log(e, ' unable to process events for planning');
  }
};

const processEachMeetingAssist = async (
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  meetingId: string,
  meetingEvent: EventType,
  listedEvents: EventPlusType[]
): Promise<ReturnValueForEachMeetingAssistType> => {
  try {
    const attendees = await listMeetingAssistAttendeesGivenMeetingId(meetingId);

    const externalAttendees = attendees.filter((a) => !!a?.externalAttendee);

    const internalAttendees = attendees.filter((a) => !a?.externalAttendee);
    // original meeting asssit events
    const meetingAssistEvents: MeetingAssistEventType[] = [];
    // events for each user
    const events: EventType[] = [];
    // events with a meetingId
    const meetingEvents: EventType[] = [];
    meetingEvents.push(meetingEvent);
    // get events
    if (externalAttendees?.length > 0) {
      for (let i = 0; i < externalAttendees?.length; i++) {
        const newMeetingAssistEvents =
          await listMeetingAssistEventsForAttendeeGivenDates(
            externalAttendees[i].id,
            windowStartDate,
            windowEndDate,
            externalAttendees[i].timezone,
            hostTimezone
          );

        const meetingAssistEventForMeeting = newMeetingAssistEvents.find(
          (m) => m.meetingId === meetingId
        );
        const filteredMeetingAssistEvents = newMeetingAssistEvents.filter(
          (e) => e?.meetingId !== meetingId
        );
        meetingAssistEvents.push(...filteredMeetingAssistEvents);
        if (meetingAssistEventForMeeting?.id) {
          meetingEvents.push(
            convertMeetingAssistEventTypeToEventPlusType(
              meetingAssistEventForMeeting,
              externalAttendees[i]?.userId
            )
          );
        }
      }
    }

    for (let i = 0; i < internalAttendees.length; i++) {
      const newEvents = await listEventsForUserGivenDates(
        internalAttendees[i].userId,
        windowStartDate,
        windowEndDate,
        internalAttendees[i].timezone,
        hostTimezone
      );
      const meetingAssistEventForMeeting = newEvents.find(
        (e) => e?.meetingId === meetingId
      );
      const filteredNewEvents = newEvents.filter(
        (e) => e?.meetingId !== meetingId
      );
      events.push(...filteredNewEvents);
      if (meetingAssistEventForMeeting?.id) {
        meetingEvents.push(meetingAssistEventForMeeting);
      }
    }

    const preferredTimesRanges =
      await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);

    const newUserModifiedMeetingEvents: EventMeetingPlusType[] =
      meetingEvents.map((me) => ({
        ...me,
        preferredTimeRanges: preferredTimesRanges,
      }));

    const userModifiedEvents: EventPlusType[] = [];

    for (const event of events) {
      // get preferredTimeRanges
      const preferredTimeRanges = await listPreferredTimeRangesForEvent(
        event?.id
      );
      if (preferredTimeRanges?.length > 0) {
        preferredTimeRanges?.map((pt) =>
          console.log(
            pt,
            ' preferredTimeRange inside processUserEventsForPlanning'
          )
        );
        userModifiedEvents.push({
          ...event,
          preferredTimeRanges: preferredTimeRanges,
        });
      } else {
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
  } catch (e) {
    console.log(e, ' unable to process each meeting assist');
  }
};

const processEventApplyFeatures = async (event: EventPlusType) => {
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

    const preferredTimeRangesForEvent = await listPreferredTimeRangesForEvent(
      event?.id
    );
    event.preferredTimeRanges = preferredTimeRangesForEvent;

    const events: EventPlusType[] = await listEventsForDate(
      hostId,
      windowStartDate,
      windowEndDate,
      hostTimezone
    );

    const userModifiedEvents: EventPlusType[] = [];
    const newModifiedReminders: RemindersForEventType[] = [];
    const newModifiedTimeBlockings: BufferTimeObjectType[] = [];

    userModifiedEvents.push(...events);

    // 1. convert to vector space
    const { userId } = event;
    const vector = await getEventVectorById(event?.id);
    console.log(vector, ' vector');

    if (!vector) {
      // If no vector, cannot find similar events or add to training.
      // Proceed with default category processing or just push the event.
      console.log(
        `No vector found for event ${event.id}. Applying default category processing.`
      );
      if (!event?.userModifiedCategories) {
        const { newEvent, newReminders, newTimeBlocking } =
          await processUserEventForCategoryDefaults(event, null); // Pass null for vector
        userModifiedEvents.push(newEvent);
        if (newReminders)
          newModifiedReminders.push({
            eventId: newEvent?.id,
            reminders: newReminders,
          });
        if (newTimeBlocking) newModifiedTimeBlockings.push(newTimeBlocking);
      } else {
        const categories: CategoryType[] = await listCategoriesForEvent(
          event?.id
        );
        if (categories?.[0]?.id) {
          const { newEvent, newReminders, newTimeBlocking } =
            await processUserEventForCategoryDefaultsWithUserModifiedCategories(
              event,
              null
            ); // Pass null for vector
          userModifiedEvents.push(newEvent);
          if (newReminders)
            newModifiedReminders.push({
              eventId: newEvent?.id,
              reminders: newReminders,
            });
          if (newTimeBlocking) newModifiedTimeBlockings.push(newTimeBlocking);
        } else {
          userModifiedEvents.push(event); // No categories, no vector, push as is
        }
      }
    } else {
      // Vector exists, proceed with search/training logic
      const trainingResult = await searchTrainingDataByVector(userId, vector);
      console.log(trainingResult, ' trainingResult from LanceDB');

      if (!trainingResult?.id && !event?.userModifiedCategories) {
        console.log('no training result found and no user modified categories');
        const { newEvent, newReminders, newTimeBlocking } =
          await processUserEventForCategoryDefaults(event, vector);
        userModifiedEvents.push(newEvent);
        if (newReminders)
          newModifiedReminders.push({
            eventId: newEvent?.id,
            reminders: newReminders,
          });
        if (newTimeBlocking) newModifiedTimeBlockings.push(newTimeBlocking);

        const newTrainingEntry: TrainingEventSchema = {
          id: event.id,
          userId: event.userId,
          vector: vector,
          source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
          created_at: dayjs().toISOString(),
        };
        await addTrainingData(newTrainingEntry);
      } else if (!trainingResult?.id && event?.userModifiedCategories) {
        console.log(
          'no training result found but event has user modified categories'
        );
        const categories: CategoryType[] = await listCategoriesForEvent(
          event?.id
        );
        if (categories?.[0]?.id) {
          const { newEvent, newReminders, newTimeBlocking } =
            await processUserEventForCategoryDefaultsWithUserModifiedCategories(
              event,
              vector
            );
          userModifiedEvents.push(newEvent);
          if (newReminders)
            newModifiedReminders.push({
              eventId: newEvent?.id,
              reminders: newReminders,
            });
          if (newTimeBlocking) newModifiedTimeBlockings.push(newTimeBlocking);
        } else {
          const newTrainingEntry: TrainingEventSchema = {
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
      } else if (trainingResult?.id && !event?.userModifiedCategories) {
        const previousEventIdFromTraining = trainingResult.id;
        const previousEvent = await getEventFromPrimaryKey(
          previousEventIdFromTraining
        );
        if (previousEvent?.id) {
          const preferredTimeRanges = await listPreferredTimeRangesForEvent(
            previousEventIdFromTraining
          );
          previousEvent.preferredTimeRanges = preferredTimeRanges;
        }

        if (!previousEvent) {
          console.log(
            previousEventIdFromTraining,
            'trainingResult.id points to a deleted event.'
          );
          await deleteTrainingDataById(trainingResult.id);
          const { newEvent, newReminders, newTimeBlocking } =
            await processUserEventForCategoryDefaults(event, vector);
          userModifiedEvents.push(newEvent);
          if (newReminders)
            newModifiedReminders.push({
              eventId: newEvent?.id,
              reminders: newReminders,
            });
          if (newTimeBlocking) newModifiedTimeBlockings.push(newTimeBlocking);

          const newTrainingEntry: TrainingEventSchema = {
            id: event.id,
            userId: event.userId,
            vector: vector,
            source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
            created_at: dayjs().toISOString(),
          };
          await addTrainingData(newTrainingEntry);
        } else {
          const { newEvent, newReminders, newTimeBlocking } =
            await processUserEventWithFoundPreviousEvent(
              event,
              previousEventIdFromTraining
            );
          userModifiedEvents.push(newEvent);
          if (newReminders)
            newModifiedReminders.push({
              eventId: newEvent?.id,
              reminders: newReminders,
            });
          if (newTimeBlocking) newModifiedTimeBlockings.push(newTimeBlocking);
        }
      } else if (trainingResult?.id && event?.userModifiedCategories) {
        const previousEventIdFromTraining = trainingResult.id;
        const previousEvent = await getEventFromPrimaryKey(
          previousEventIdFromTraining
        );
        if (previousEvent?.id) {
          const preferredTimeRanges = await listPreferredTimeRangesForEvent(
            previousEventIdFromTraining
          );
          previousEvent.preferredTimeRanges = preferredTimeRanges;
        }

        if (!previousEvent) {
          console.log(
            previousEventIdFromTraining,
            'trainingResult.id points to a deleted event and event has user modified categories.'
          );
          await deleteTrainingDataById(trainingResult.id);
          const categories: CategoryType[] = await listCategoriesForEvent(
            event?.id
          );
          if (categories?.[0]?.id) {
            const { newEvent, newReminders, newTimeBlocking } =
              await processUserEventForCategoryDefaultsWithUserModifiedCategories(
                event,
                vector
              );
            userModifiedEvents.push(newEvent);
            if (newReminders)
              newModifiedReminders.push({
                eventId: newEvent?.id,
                reminders: newReminders,
              });
            if (newTimeBlocking) newModifiedTimeBlockings.push(newTimeBlocking);
          } else {
            const newTrainingEntry: TrainingEventSchema = {
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
        } else {
          const categories: CategoryType[] = await listCategoriesForEvent(
            event?.id
          );
          if (categories?.[0]?.id) {
            const { newEvent, newReminders, newTimeBlocking } =
              await processUserEventWithFoundPreviousEventWithUserModifiedCategories(
                event,
                previousEventIdFromTraining
              );
            userModifiedEvents.push(newEvent);
            if (newReminders)
              newModifiedReminders.push({
                eventId: newEvent?.id,
                reminders: newReminders,
              });
            if (newTimeBlocking) newModifiedTimeBlockings.push(newTimeBlocking);
          } else {
            console.log('no categories found, but previous event found');
            const userPreferences = await getUserPreferences(userId);
            const {
              newModifiedEvent: newModifiedEvent1,
              newReminders: newReminders1,
              newTimeBlocking: newTimeBlocking1,
            } = await processEventWithFoundPreviousEventWithoutCategories(
              previousEvent,
              event,
              userPreferences,
              userId
            );
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

    userModifiedEvents.forEach((e) =>
      console.log(e, ' userModifiedEvent before processing for Optaplanner')
    );
    newModifiedReminders.forEach((e) =>
      console.log(e, ' newModifiedReminders before processing for Optaplanner')
    );

    const eventsWithMeetingId = events.filter((e) => !!e?.meetingId);

    const meetingAssistEvents: MeetingAssistEventType[] = [];
    const meetingEventPlus: EventMeetingPlusType[] = [];
    const internalAttendees: MeetingAssistAttendeeType[] = [];
    const externalAttendees: MeetingAssistAttendeeType[] = [];
    const filteredEvents: EventType[] = [];

    /**
     * queue for each
     * parentKey: hostId/singletonId
     * oldChildKey: hostId/meetingId
     */

    filteredEvents.push(...userModifiedEvents);
    filteredEvents.push(...eventsWithMeetingId);

    for (const eventWithMeetingId of eventsWithMeetingId) {
      const returnValuesForEachMeeting = await processEachMeetingAssist(
        windowStartDate,
        windowEndDate,
        hostTimezone,
        eventWithMeetingId?.meetingId,
        eventWithMeetingId,
        events
      );

      if (returnValuesForEachMeeting?.events?.length > 0) {
        const newEvents = returnValuesForEachMeeting?.events;

        filteredEvents.push(...newEvents);
        events.push(...newEvents);
      }

      if (returnValuesForEachMeeting?.meetingAssistEvents?.length > 0) {
        meetingAssistEvents.push(
          ...returnValuesForEachMeeting?.meetingAssistEvents
        );
      }

      if (returnValuesForEachMeeting?.meetingEventsPlus) {
        meetingEventPlus.push(...returnValuesForEachMeeting?.meetingEventsPlus);
      }

      if (returnValuesForEachMeeting?.internalAttendees) {
        internalAttendees.push(
          ...returnValuesForEachMeeting?.internalAttendees
        );
      }

      if (returnValuesForEachMeeting?.externalAttendees) {
        externalAttendees.push(
          ...returnValuesForEachMeeting?.externalAttendees
        );
      }
    }

    return processEventsForPlanning(
      hostId,
      _.uniqWith(internalAttendees, _.isEqual),
      meetingEventPlus,
      _.uniqWith(filteredEvents, _.isEqual),
      events,
      windowStartDate,
      windowEndDate,
      hostTimezone,
      _.uniqWith(externalAttendees, _.isEqual),
      meetingAssistEvents?.length > 0
        ? _.uniqWith(meetingAssistEvents, _.isEqual)
        : null
    );
  } catch (e) {
    console.log(e, ' unable to process meeting assist');
  }
};

const processQueueMessage = async (event: EventPlusType) => {
  try {
    if (!event?.id) {
      throw new Error('no userId provided inside atomic meeting assist');
    }

    return processEventApplyFeatures(event);
  } catch (e) {
    console.log(
      e,
      ' unable to processQueueMessage inside atomic meeting assist'
    );
  }
};

const scheduleEventWorker = async (event: { Records: MessageQueueType[] }) => {
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

        const body: EventPlusType = JSON.parse(message?.value?.toString());
        console.log(body, ' body');

        await processQueueMessage(body);
      },
    });
  } catch (e) {
    console.log(e, ' unable to assist for meeting');
  }
};

export default scheduleEventWorker;
