import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

import _ from 'lodash';
import {
  listEventsForUserGivenDates,
  listMeetingAssistAttendeesGivenMeetingId,
  listMeetingAssistEventsForAttendeeGivenDates,
  listMeetingAssistPreferredTimeRangesGivenMeetingId,
  listPreferredTimeRangesForEvent,
  listEventsForDate,
  convertMeetingAssistEventTypeToEventPlusType,
  processUserEventForCategoryDefaults,
  listCategoriesForEvent,
  processUserEventForCategoryDefaultsWithUserModifiedCategories,
  getEventFromPrimaryKey,
  processUserEventWithFoundPreviousEvent,
  processUserEventWithFoundPreviousEventWithUserModifiedCategories,
  getUserPreferences,
  processEventWithFoundPreviousEventWithoutCategories,
  listFutureMeetingAssists,
  meetingAttendeeCountGivenMeetingId,
  getMeetingAssist,
  generateNewMeetingEventForAttendee,
  createBufferTimeForNewMeetingEvent,
  createRemindersFromMinutesAndEvent,
  getGlobalCalendar,
  searchTrainingDataByVector, // updated
  getEventVectorById, // updated
  deleteTrainingDataById, // updated
  addTrainingData, // added
} from '@features_apply/_libs/api-helper';
import {
  EventPlusType,
  EventType,
  MeetingAssistEventType,
  EventMeetingPlusType,
  MeetingAssistAttendeeType,
  RemindersForEventType,
  BufferTimeObjectType,
  CategoryType,
  MeetingAssistType,
  ReturnValueForEachFutureMeetingAssistType,
  ValuesToReturnForBufferEventsType,
  TrainingEventSchema,
  FeaturesApplyResponse,
  SkillError, // Added for standardized error handling
} from '@features_apply/_libs/types';
// Remove redundant import of ReturnValueForEachMeetingAssistType if it's covered by the main import
// import { ReturnValueForEachMeetingAssistType } from '@features_apply/_libs/types';

import { processEventsForOptaPlanner } from '@features_apply/_libs/optaplanner/api-helper';

import {
  kafkaFeaturesApplyGroupId,
  kafkaFeaturesApplyTopic,
} from '../_libs/constants';
import { Kafka, logLevel } from 'kafkajs';
import ip from 'ip';
import { ScheduleAssistWithMeetingQueueBodyType } from '@/autopilot/_libs/types';

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
  newMeetingEventPlus: EventMeetingPlusType[], // generated events
  newMeetingAssists: MeetingAssistType[],
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
      const preferredTimeRangesResponse = await listPreferredTimeRangesForEvent(
        event?.id
      );
      if (!preferredTimeRangesResponse.ok) {
        // Decide: throw, or log and continue with empty preferredTimeRanges?
        // For now, logging and continuing as preferredTimeRanges might not be critical for all events.
        console.warn(
          `Failed to get preferred time ranges for event ${event?.id}: ${preferredTimeRangesResponse.error?.message}`
        );
        userModifiedEvents.push(event); // Add event without preferredTimeRanges
      } else {
        const preferredTimeRanges = preferredTimeRangesResponse.data || [];
        userModifiedEvents.push({
          ...event,
          preferredTimeRanges: preferredTimeRanges,
        });
      }
    }

    const newHostReminders: RemindersForEventType[] = [];
    const newHostBufferTimes: BufferTimeObjectType[] = [];
    const newHostMeetingEventsPlus: EventMeetingPlusType[] = [];

    for (const newMeetingAssist of newMeetingAssists) {
      let newHostMeetingEventPlus = newMeetingEventPlus
        ?.filter((me) => me?.meetingId === newMeetingAssist?.id)
        ?.find((me) => me?.userId === newMeetingAssist?.userId);
      let newBufferTimeForMeetingEventOrEmptyObject: BufferTimeObjectType = {};
      let newModifiedReminderOrNull: RemindersForEventType | null = null;

      if (newHostMeetingEventPlus?.id) {
        newModifiedReminderOrNull = newMeetingAssist?.reminders?.[0]
          ? createRemindersFromMinutesAndEvent(
              newHostMeetingEventPlus.id,
              newMeetingAssist.reminders,
              newMeetingAssist.timezone,
              newMeetingAssist.useDefaultAlarms,
              newMeetingAssist.userId
            )
          : null;
      }

      if (newModifiedReminderOrNull?.reminders?.[0]?.userId) {
        newHostReminders.push(newModifiedReminderOrNull);
      }

      const valuesToReturn: ValuesToReturnForBufferEventsType =
        newMeetingAssist?.bufferTime?.afterEvent > 0 ||
        newMeetingAssist?.bufferTime?.beforeEvent > 0
          ? createBufferTimeForNewMeetingEvent(
              newHostMeetingEventPlus,
              newMeetingAssist.bufferTime
            )
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

      if (
        newBufferTimeForMeetingEventOrEmptyObject?.afterEvent?.id ||
        newBufferTimeForMeetingEventOrEmptyObject?.beforeEvent?.id
      ) {
        newHostBufferTimes.push(newBufferTimeForMeetingEventOrEmptyObject);
      }

      if (
        newHostMeetingEventPlus?.preEventId ||
        newHostMeetingEventPlus?.postEventId
      ) {
        newHostMeetingEventsPlus.push(newHostMeetingEventPlus);
      }
    }

    const newMeetingEventPlusRemovedHostEvents = _.differenceBy(
      newMeetingEventPlus,
      newHostMeetingEventsPlus,
      'id'
    );
    const newMeetingEventPlusModifiedHostEvents =
      newMeetingEventPlusRemovedHostEvents.concat(newHostMeetingEventsPlus);

    return processEventsForOptaPlanner(
      mainHostId,
      internalAttendees,
      meetingEventPlus,
      newMeetingEventPlusModifiedHostEvents,
      userModifiedEvents,
      windowStartDate,
      windowEndDate,
      hostTimezone,
      oldEvents,
      externalAttendees,
      meetingAssistEvents,
      newHostReminders?.length > 0 ? newHostReminders : [],
      newHostBufferTimes?.length > 0 ? newHostBufferTimes : []
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
  // This return type might need to become FeaturesApplyResponse as well if we want to propagate errors from it
  try {
    const attendeesResponse =
      await listMeetingAssistAttendeesGivenMeetingId(meetingId);
    if (!attendeesResponse.ok)
      throw new Error(
        `Failed to list attendees for meeting ${meetingId}: ${attendeesResponse.error?.message}`
      );
    const attendees = attendeesResponse.data || [];

    const externalAttendees = attendees.filter((a) => !!a?.externalAttendee);
    const internalAttendees = attendees.filter((a) => !a?.externalAttendee);

    const meetingAssistEvents: MeetingAssistEventType[] = [];
    const events: EventType[] = [];
    const meetingEvents: EventType[] = [meetingEvent]; // Start with the initial meeting event

    if (externalAttendees.length > 0) {
      for (const attendee of externalAttendees) {
        const extEventsResponse =
          await listMeetingAssistEventsForAttendeeGivenDates(
            attendee.id,
            windowStartDate,
            windowEndDate,
            attendee.timezone,
            hostTimezone
          );
        if (!extEventsResponse.ok) {
          console.warn(
            `Failed to list meeting assist events for external attendee ${attendee.id}: ${extEventsResponse.error?.message}`
          );
          continue; // Skip this attendee or handle error more strictly
        }
        const newMeetingAssistEvents = extEventsResponse.data || [];
        const meetingAssistEventForMeeting = newMeetingAssistEvents.find(
          (m) => m?.meetingId === meetingId
        );
        const filteredMeetingAssistEvents = newMeetingAssistEvents.filter(
          (e) => e?.meetingId !== meetingId
        );

        if (filteredMeetingAssistEvents.length > 0)
          meetingAssistEvents.push(...filteredMeetingAssistEvents);
        if (meetingAssistEventForMeeting?.id)
          meetingEvents.push(
            convertMeetingAssistEventTypeToEventPlusType(
              meetingAssistEventForMeeting,
              attendee.userId
            )
          );
      }
    }

    for (const attendee of internalAttendees) {
      const internalEventsResponse = await listEventsForUserGivenDates(
        attendee.userId,
        windowStartDate,
        windowEndDate,
        attendee.timezone,
        hostTimezone
      );
      if (!internalEventsResponse.ok) {
        console.warn(
          `Failed to list events for internal attendee ${attendee.userId}: ${internalEventsResponse.error?.message}`
        );
        continue; // Skip this attendee
      }
      const newEvents = internalEventsResponse.data || [];
      const meetingEventForCurrentAttendee = newEvents.find(
        (e) => e?.meetingId === meetingId
      );
      const filteredNewEvents = newEvents.filter(
        (e) => e?.meetingId !== meetingId
      );

      if (filteredNewEvents.length > 0) events.push(...filteredNewEvents);
      if (meetingEventForCurrentAttendee?.id)
        meetingEvents.push(meetingEventForCurrentAttendee);
    }

    const preferredTimesRangesResponse =
      await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);
    if (!preferredTimesRangesResponse.ok) {
      console.warn(
        `Failed to list preferred time ranges for meeting ${meetingId}: ${preferredTimesRangesResponse.error?.message}`
      );
    }
    const preferredTimesRanges =
      preferredTimesRangesResponse.ok && preferredTimesRangesResponse.data
        ? preferredTimesRangesResponse.data
        : [];

    const newUserModifiedMeetingEvents: EventMeetingPlusType[] =
      meetingEvents.map((me) => ({
        ...me,
        preferredTimeRanges: preferredTimesRanges,
      }));

    const userModifiedEvents: EventPlusType[] = [];
    for (const event of events) {
      const eventPreferredTimeRangesResponse =
        await listPreferredTimeRangesForEvent(event?.id);
      if (!eventPreferredTimeRangesResponse.ok) {
        console.warn(
          `Failed to list preferred time ranges for event ${event.id}: ${eventPreferredTimeRangesResponse.error?.message}`
        );
        userModifiedEvents.push(event); // Add with empty or no preferred time ranges
        continue;
      }
      const eventPreferredTimeRanges =
        eventPreferredTimeRangesResponse.ok &&
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
  } catch (e) {
    console.log(e, ' unable to process each meeting assist');
  }
};

function getRandomInt(min, max) {
  min = Math.ceil(min);
  max = Math.floor(max);
  return Math.floor(Math.random() * (max - min) + min); // The maximum is exclusive and the minimum is inclusive
}

const processEachFutureMeetingAssist = async (
  windowStartDate: string,
  windowEndDate: string,
  meetingId: string,
  listedEvents: EventType[]
): Promise<ReturnValueForEachFutureMeetingAssistType> => {
  try {
    const meetingAssistResponse = await getMeetingAssist(meetingId);
    if (!meetingAssistResponse.ok || !meetingAssistResponse.data)
      throw new Error(
        `Failed to get meeting assist ${meetingId}: ${meetingAssistResponse.error?.message}`
      );
    const meetingAssist = meetingAssistResponse.data;

    const preferredTimesRangesResponse =
      await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);
    if (!preferredTimesRangesResponse.ok)
      throw new Error(
        `Failed to list preferred time ranges for meeting ${meetingId}: ${preferredTimesRangesResponse.error?.message}`
      );
    const preferredTimesRanges = preferredTimesRangesResponse.data || [];

    const attendeesResponse =
      await listMeetingAssistAttendeesGivenMeetingId(meetingId);
    if (!attendeesResponse.ok)
      throw new Error(
        `Failed to list attendees for meeting ${meetingId}: ${attendeesResponse.error?.message}`
      );
    const attendees = attendeesResponse.data || [];

    const hostTimezone = meetingAssist?.timezone;
    if (!hostTimezone)
      throw new Error('Host timezone is missing from meeting assist data.');

    const newMeetingEvents: EventMeetingPlusType[] = [];
    for (const attendee of attendees) {
      let calendarId: string | null = null;
      if (!attendee?.externalAttendee) {
        const globalCalendarResponse = await getGlobalCalendar(
          attendee?.userId
        );
        if (!globalCalendarResponse.ok) {
          console.warn(
            `Failed to get global calendar for attendee ${attendee.userId}: ${globalCalendarResponse.error?.message}`
          );
        }
        calendarId =
          globalCalendarResponse.ok && globalCalendarResponse.data
            ? globalCalendarResponse.data.id
            : null;
      }
      const newMeetingEvent = generateNewMeetingEventForAttendee(
        attendee,
        meetingAssist,
        windowStartDate,
        windowEndDate,
        hostTimezone,
        calendarId,
        preferredTimesRanges?.[getRandomInt(0, preferredTimesRanges.length)]
      );
      newMeetingEvents.push({ ...newMeetingEvent, preferredTimeRanges });
    }

    const externalAttendees = attendees.filter((a) => !!a?.externalAttendee);
    const internalAttendees = attendees.filter((a) => !a?.externalAttendee);
    const meetingAssistEvents: MeetingAssistEventType[] = [];
    const events: EventType[] = [];

    if (externalAttendees.length > 0) {
      for (const attendee of externalAttendees) {
        const extEventsResponse =
          await listMeetingAssistEventsForAttendeeGivenDates(
            attendee.id,
            windowStartDate,
            windowEndDate,
            attendee.timezone,
            hostTimezone
          );
        if (!extEventsResponse.ok) {
          console.warn(
            `Failed to list meeting assist events for external attendee ${attendee.id}: ${extEventsResponse.error?.message}`
          );
          continue;
        }
        const newExtMeetingAssistEvents = extEventsResponse.data || [];
        if (newExtMeetingAssistEvents.length > 0)
          meetingAssistEvents.push(...newExtMeetingAssistEvents);
      }
    }

    for (const attendee of internalAttendees) {
      const internalEventsResponse = await listEventsForUserGivenDates(
        attendee.userId,
        windowStartDate,
        windowEndDate,
        attendee.timezone,
        hostTimezone
      );
      if (!internalEventsResponse.ok) {
        console.warn(
          `Failed to list events for internal attendee ${attendee.userId}: ${internalEventsResponse.error?.message}`
        );
        continue;
      }
      const newInternalEvents = internalEventsResponse.data || [];
      if (newInternalEvents.length > 0) events.push(...newInternalEvents);
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
  } catch (e) {
    console.log(e, ' unable to process each future meeting assist');
  }
};

const processApplyFeatures = async (
  body: ScheduleAssistWithMeetingQueueBodyType
) => {
  try {
    const hostId = body?.userId;
    const windowStartDate = body?.windowStartDate;
    const windowEndDate = body?.windowEndDate;
    const hostTimezone = body?.timezone;

    const events: EventPlusType[] = await listEventsForDate(
      hostId,
      windowStartDate,
      windowEndDate,
      hostTimezone
    );
    const eventsWithoutMeetingAssist: EventPlusType[] = events?.filter(
      (e) => !e?.meetingId
    );

    const userModifiedEvents: EventPlusType[] = [];
    const newModifiedReminders: RemindersForEventType[] = [];
    const newModifiedBufferTimes: BufferTimeObjectType[] = [];

    for (const event of eventsWithoutMeetingAssist) {
      const preferredTimeRangesForEvent = await listPreferredTimeRangesForEvent(
        event?.id
      );

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
        const { newEvent, newReminders, newBufferTimes } =
          await processUserEventForCategoryDefaults(event, vector);
        console.log(
          newEvent,
          ' newEvent for processUserEventForCategoryDefaults'
        );
        console.log(
          newReminders,
          ' newReminders for processUserEventForCategoryDefaults'
        );
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
          'no trainingResult found but event has user modified categories'
        );
        // no previous event found use user modified categories and category defaults
        const categories: CategoryType[] = await listCategoriesForEvent(
          event?.id
        );
        console.log(categories, ' categories');
        if (categories?.[0]?.id) {
          const { newEvent, newReminders, newBufferTimes } =
            await processUserEventForCategoryDefaultsWithUserModifiedCategories(
              event,
              vector
            );
          console.log(
            newEvent,
            ' newEvent for processUserEventForCategoryDefaultsWithUserModifiedCategories'
          );
          console.log(
            newReminders,
            ' newReminders for processUserEventForCategoryDefaultsWithUserModifiedCategories'
          );
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
        } else {
          // Add current event to training data as no similar past event was found and no categories to guide defaults
          const newTrainingEntry: TrainingEventSchema = {
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
      } else if (trainingResult?.id && !event?.userModifiedCategories) {
        // previous event found (via trainingResult) use previous event to copy over values
        const previousEventIdFromTraining = trainingResult.id; // This ID is from the training data, assumed to be the googleEventId of a previous similar event.
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
            'trainingResult.id inside !previousEvent && !event?.userModifiedCategories. This means the linked event was deleted.'
          );
          await deleteTrainingDataById(trainingResult.id); // Delete stale training entry
          // Fallback to category defaults as the "similar" event is gone
          const { newEvent, newReminders, newBufferTimes } =
            await processUserEventForCategoryDefaults(event, vector);
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
          const newTrainingEntry: TrainingEventSchema = {
            id: event.id,
            userId: event.userId,
            vector: vector,
            source_event_text: `${event.title || event.summary}:${event.notes || ''}`,
            created_at: dayjs().toISOString(),
          };
          await addTrainingData(newTrainingEntry);
        } else {
          const { newEvent, newReminders, newBufferTimes } =
            await processUserEventWithFoundPreviousEvent(
              event,
              previousEventIdFromTraining
            );
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
            'trainingResult.id inside !previousEvent && event?.userModifiedCategories. This means the linked event was deleted.'
          );
          await deleteTrainingDataById(trainingResult.id); // Delete stale training entry
          // Fallback to user modified categories as the "similar" event is gone
          const categories: CategoryType[] = await listCategoriesForEvent(
            event?.id
          );
          if (categories?.[0]?.id) {
            const { newEvent, newReminders, newBufferTimes } =
              await processUserEventForCategoryDefaultsWithUserModifiedCategories(
                event,
                vector
              );
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
          } else {
            // Add current event to training data as the previously similar one was stale and no categories to guide
            const newTrainingEntry: TrainingEventSchema = {
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
        } else {
          const categories: CategoryType[] = await listCategoriesForEvent(
            event?.id
          );
          if (categories?.[0]?.id) {
            const { newEvent, newReminders, newBufferTimes } =
              await processUserEventWithFoundPreviousEventWithUserModifiedCategories(
                event,
                previousEventIdFromTraining
              );
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
          } else {
            // No categories, but a previous event was found.
            const userPreferences = await getUserPreferences(userId);
            const {
              newModifiedEvent: newModifiedEvent1,
              newReminders: newReminders1,
              newBufferTimes: newTimeBlocking1,
            } = await processEventWithFoundPreviousEventWithoutCategories(
              previousEvent,
              event,
              userPreferences,
              userId
            );
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

    // future meeting assists
    const meetingIdsToNotInclude = eventsWithMeetingId.map((e) => e?.meetingId);

    console.log(meetingIdsToNotInclude, ' meetingIdsToNotInclude');

    const newMeetingAssistsNoThreshold = await listFutureMeetingAssists(
      hostId,
      dayjs(windowStartDate.slice(0, 19)).tz(hostTimezone).format(),
      dayjs(windowEndDate.slice(0, 19)).tz(hostTimezone).add(1, 'd').format(),
      meetingIdsToNotInclude
    );

    console.log(newMeetingAssistsNoThreshold, ' newMeetingAssistsNoThreshold');

    const newMeetingEventPlus: EventMeetingPlusType[] = [];
    const newMeetingAssistsActive: MeetingAssistType[] = [];

    for (const futureMeetingAssist of newMeetingAssistsNoThreshold) {
      const count = await meetingAttendeeCountGivenMeetingId(
        futureMeetingAssist?.id
      );

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
      const returnValuesFromFutureMeetingAssist =
        await processEachFutureMeetingAssist(
          windowStartDate,
          windowEndDate,
          futureMeetingAssistActive?.id,
          events
        );

      if (returnValuesFromFutureMeetingAssist?.events?.length > 0) {
        const newEvents = returnValuesFromFutureMeetingAssist?.events;

        filteredEvents.push(...newEvents);
        events.push(...newEvents);
      }

      if (
        returnValuesFromFutureMeetingAssist?.meetingAssistEvents?.length > 0
      ) {
        meetingAssistEvents.push(
          ...returnValuesFromFutureMeetingAssist?.meetingAssistEvents
        );
      }

      if (
        returnValuesFromFutureMeetingAssist?.newMeetingEventPlus?.length > 0
      ) {
        newMeetingEventPlus.push(
          ...returnValuesFromFutureMeetingAssist?.newMeetingEventPlus
        );
      }

      if (returnValuesFromFutureMeetingAssist?.internalAttendees) {
        internalAttendees.push(
          ...returnValuesFromFutureMeetingAssist?.internalAttendees
        );
      }

      if (returnValuesFromFutureMeetingAssist?.externalAttendees) {
        externalAttendees.push(
          ...returnValuesFromFutureMeetingAssist?.externalAttendees
        );
      }
    }

    return processEventsForPlanning(
      hostId,
      _.uniqWith(internalAttendees, _.isEqual),
      meetingEventPlus,
      newMeetingEventPlus,
      newMeetingAssistsActive,
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

const processQueueMessage = async (
  body: ScheduleAssistWithMeetingQueueBodyType
) => {
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
      const error = new Error(
        `Invalid message payload: Missing ${missingParams}`
      );
      // @ts-ignore // Add custom property for structured logging/handling if needed
      error.code = 'MESSAGE_VALIDATION_ERROR';
      throw error;
    }

    return await processApplyFeatures(body); // Propagate result or error
  } catch (e: any) {
    // Catch errors from processApplyFeatures or validation
    console.error(
      `Error in processQueueMessage for userId ${body?.userId}: ${e.message}`,
      e
    );
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

        let messagePayload: ScheduleAssistWithMeetingQueueBodyType | null =
          null;
        try {
          if (!message?.value) {
            // This error is about Kafka message integrity, not business logic validation
            throw new Error('Kafka message value is null or undefined.');
          }
          messagePayload = JSON.parse(message.value.toString());
          console.log(messagePayload, ' messagePayload');
          await processQueueMessage(messagePayload!);
        } catch (e: any) {
          console.error(
            `Failed to process Kafka message from topic ${topic}, partition ${partition}: ${e.message}`,
            {
              messageKey: message?.key?.toString(),
              errorMessage: e.message,
              errorCode: e.code,
              errorStack: e.stack,
              originalPayload: message?.value?.toString(),
            }
          );
          // Re-throw the error to utilize Kafka's retry/DLQ mechanisms if configured.
          throw e;
        }
      },
    });
  } catch (e: any) {
    console.error('Kafka consumer error in scheduleMeetingWorker:', e);
    // This error is likely a connection or subscription issue with Kafka itself.
    throw e; // Re-throw to make the worker crash and restart if managed by PM2/Kubernetes
  }
};

export default scheduleMeetingWorker;
