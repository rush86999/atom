import Session from 'supertokens-web-js/recipe/session';

import { dayjs } from '@lib/date-utils';
import _ from 'lodash';
import { Day } from '@lib/Schedule/constants';
import {
  atomicUpsertEventInDb,
  createNewEvent,
  getCalendarInDb,
  meetingTypeStringType,
} from '@lib/Calendar/UserCreateCalendarHelper';

import { deleteGoogleEvent } from '@lib/calendarLib/googleCalendarHelper';

import { googleResourceName } from '@lib/calendarLib/constants';
import { EventType, Time } from '@lib/dataTypes/EventType';
import {
  eventToQueueAuthUrl,
  calendarToQueueAuthUrl,
  eventToQueueShortAuthUrl,
  methodToSearchIndexAuthUrl,
} from '@lib/constants';
import axios from 'axios';
import { updateEvent } from '@lib/Calendar/UserEditCalendarHelper';

import { LocationType, BufferTimeType } from '@lib/dataTypes/EventType';
import {
  SendUpdatesType,
  TransparencyType,
  VisibilityType,
} from '@lib/calendarLib/types';
import { esResponseBody, Person } from '@lib/Calendar/types';
import { DeadlineType, TaskPlusType } from '@pages/Progress/Todo/UserTask';

import { CalendarType } from '@lib/dataTypes/CalendarType';
import {
  getEventWithId,
  upsertCalendar,
} from '@lib/calendarLib/calendarDbHelper';
import { palette } from '@lib/theme/theme';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';

import getEventById from '@lib/apollo/gql/getEventById';
import deleteEventById from '@lib/apollo/gql/deleteEventById';
import getCalendarById from '@lib/apollo/gql/getCalendarById';

import getCalendarWithResource from '@lib/apollo/gql/getCalendarWithResource';
import listEventsNotLocallySynced from '@lib/apollo/gql/listEventsNotLocallySynced';

import { deleteAttendeesForEvent } from '@lib/Calendar/Attendee/AttendeeHelper';
import { deleteConferencesWithIds } from '@lib/Calendar/Conference/ConferenceHelper';
import { removeRemindersForEvent } from '@lib/Calendar/Reminder/ReminderHelper';
import { deleteZoomMeeting, zoomAvailable } from '@lib/zoom/zoomMeetingHelper';
import { getConferenceInDb } from '@lib/Calendar/UserCreateCalendarHelper';
import { updateTaskByIdInDb } from './UserTaskHelper3';
import { WeeklyTask } from './constants';

type RecurrenceFrequency = 'daily' | 'weekly' | 'monthly' | 'yearly';

type TaskType = 'Daily' | 'Weekly' | 'Master' | 'Grocery' | string;

export const getEventForTask = async (
  eventId: string,
  client: ApolloClient<NormalizedCacheObject>
) => {
  try {
    const event = (
      await client.query<{ Event_by_pk: EventType }>({
        query: getEventById,
        variables: {
          id: eventId,
        },
      })
    ).data?.Event_by_pk;
    return event;
  } catch (e) {
    console.log(e, ' unable to get event for task');
  }
};

export const removeEventForTask = async (
  client: ApolloClient<NormalizedCacheObject>,
  task: TaskPlusType,
  userId: string
) => {
  try {
    await deleteEventInCalendarForTask(task?.eventId, client, userId);

    task.startDate = null;
    task.endDate = null;
    task.nextDay = null;
    task.eventId = null;
    task.softDeadline = null;
    task.hardDeadline = null;

    await updateTaskByIdInDb(client, task);
  } catch (e) {
    console.log(e, ' unable to delete event for task');
  }
};

export const createEventFromUTCForTask = async (
  startDate: string,
  endDate: string,
  userId: string,
  client: ApolloClient<NormalizedCacheObject>,
  taskId: string,
  taskType: TaskType,
  recurringEndDate?: string,
  frequency?: RecurrenceFrequency,
  interval?: number,
  title?: string,
  deadlineAlarms?: string[],
  notes?: string,
  byWeekDay?: Day[],
  hardDeadline?: string,
  softDeadline?: string,
  selectedCalendarId?: string
) => {
  try {
    return createNewEvent(
      dayjs.utc(startDate).toISOString(),
      dayjs.utc(endDate).toISOString(),
      userId,
      client,
      selectedCalendarId,
      undefined,
      title,
      false,
      recurringEndDate,
      frequency,
      interval,
      deadlineAlarms,
      notes,
      undefined,
      false,
      false,
      false,
      true,
      false,
      false,
      false,
      false,
      dayjs.tz.guess(),
      taskId,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      false,
      false,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      title,
      'opaque',
      'private',
      undefined,
      undefined,
      undefined,
      undefined,
      dayjs.tz.guess(),
      undefined,
      undefined,
      deadlineAlarms?.length > 0,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      taskType === 'Daily',
      taskType === 'Weekly',
      false,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      true,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      true,
      true,
      hardDeadline,
      softDeadline,
      undefined,
      undefined,
      undefined,
      undefined,
      dayjs(endDate).diff(dayjs(startDate), 'minute'),
      undefined,
      true,
      undefined,
      undefined,
      byWeekDay
    );
  } catch (e) {
    console.log(e, ' unable to create event from utc');
  }
};

export const createEventForTask = async (
  startDate: string,
  endDate: string,
  userId: string,
  client: ApolloClient<NormalizedCacheObject>,
  taskId: string,
  taskType: TaskType,
  priority: number,
  recurringEndDate?: string,
  frequency?: RecurrenceFrequency,
  interval?: number,
  title?: string,
  deadlineAlarms?: string[],
  notes?: string,
  byWeekDay?: Day[],
  hardDeadline?: string,
  softDeadline?: string,
  selectedCalendarId?: string
) => {
  try {
    return createNewEvent(
      startDate,
      endDate,
      userId,
      client,
      selectedCalendarId,
      undefined,
      title,
      false,
      recurringEndDate,
      frequency,
      interval,
      deadlineAlarms,
      notes,
      undefined,
      false,
      false,
      false,
      true,
      false,
      false,
      false,
      false,
      dayjs.tz.guess(),
      taskId,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      false,
      false,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      title,
      'opaque',
      'private',
      undefined,
      undefined,
      undefined,
      undefined,
      dayjs.tz.guess(),
      undefined,
      undefined,
      deadlineAlarms?.length > 0,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      taskType === 'Daily',
      taskType === 'Weekly',
      false,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      true,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      true,
      true,
      hardDeadline,
      softDeadline,
      undefined,
      undefined,
      undefined,
      undefined,
      dayjs(endDate).diff(dayjs(startDate), 'minute'),
      undefined,
      true,
      undefined,
      undefined,
      byWeekDay,
      priority
    );
  } catch (e) {
    console.log(e, ' unable to create event from utc');
  }
};

export const deleteEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  eventId: string
) => {
  try {
    console.log(eventId, userId, ' eventId, userId inside deleteEvent');
    await deleteAttendeesForEvent(client, eventId);
    const originalEvent = await getEventWithId(client, eventId);
    console.log(originalEvent, ' originalEvent inside deleteEvent');
    if (originalEvent?.conferenceId) {
      const isZoomAvailable = await zoomAvailable(client, userId);
      const conference = await getConferenceInDb(
        client,
        originalEvent?.conferenceId
      );

      if (isZoomAvailable && conference?.app === 'zoom') {
        await deleteZoomMeeting(
          userId,
          parseInt(originalEvent?.conferenceId, 10)
        );
      }

      await deleteConferencesWithIds(client, [originalEvent?.conferenceId]);
    }

    await removeRemindersForEvent(client, eventId);

    const url = methodToSearchIndexAuthUrl;
    const token = await Session.getAccessToken();
    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    const searchData = {
      search: `${originalEvent?.summary}${originalEvent?.notes ? `: ${originalEvent?.notes}` : ''}`,
      method: 'search',
    };
    const results = await axios.post<{
      message: string;
      event: esResponseBody;
    }>(url, searchData, config);

    console.log(results, ' results inside deleteEvent');
    console.log(results?.data, ' results?.data inside deleteEvent');
    console.log(
      results?.data?.event?.hits?.hits?.[0]?._id,
      ' results?.data?.event?.hits?.hits?.[0]?._id inside deleteEvent'
    );

    if (results?.data?.event?.hits?.hits?.[0]?._id === eventId) {
      console.log('event exists, delete it');
      const deleteData = {
        eventId: results?.data?.event?.hits?.hits?.[0]?._id,
        method: 'delete',
      };

      const deleteResults = await axios.post<{
        message: string;
        event: object;
      }>(url, deleteData, config);
      console.log(deleteResults, ' deleteResults in search');
    }

    await deleteEventInCalendarForTask(eventId, client, userId);
  } catch (e) {
    console.log(e, 'error for deleteEvent');
  }
};

export const deleteEventInCalendarForTask = async (
  eventId: string,
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    console.log(eventId, userId, ' eventId, userId delEventInAppForTask');
    const eventDoc = (
      await client.query<{ Event_by_pk: EventType }>({
        query: getEventById,
        variables: {
          id: eventId,
        },
      })
    )?.data?.Event_by_pk;
    console.log(eventDoc, ' eventDoc inside delEventInAppForTask');
    if (eventDoc?.id) {
      const calendarId = eventDoc?.calendarId;
      const calendarDoc = (
        await client.query<{ Calendar_by_pk: CalendarType }>({
          query: getCalendarById,
          variables: {
            id: calendarId,
          },
        })
      ).data?.Calendar_by_pk;
      console.log(calendarDoc, ' calendarDoc inside delEventInAppForTask');
      if (calendarDoc?.id) {
        const resource = calendarDoc?.resource;
        console.log(
          calendarDoc?.resource,
          ' calendarDoc?.resource inside delEventInAppForTask'
        );
        if (resource === googleResourceName) {
          console.log(
            userId,
            calendarId,
            eventId,
            ' userId, calendarId, eventId inside delEventinAppForTask'
          );
          await deleteGoogleEvent(
            client,
            userId,
            calendarId,
            eventId.split('#')[0]
          );
          await client.mutate<{ delete_Event_by_pk: EventType }>({
            mutation: deleteEventById,
            variables: {
              id: eventId,
            },
            update(cache, { data }) {
              const deletedEvent = data?.delete_Event_by_pk;
              const normalizedId = cache.identify({
                id: deletedEvent.id,
                __typename: deletedEvent.__typename,
              });
              cache.evict({ id: normalizedId });
              cache.gc();
            },
          });
        }
      }
    }
  } catch (e) {
    console.log(e, ' unable to delete event in app');
  }
};

export const editEventForTask = async (
  id: string,
  startDate: string,
  endDate: string,
  userId: string,
  client: ApolloClient<NormalizedCacheObject>,
  selectedCalendarId: string,
  categoryIds?: string[],
  title?: string,
  allDay?: boolean,
  recurringEndDate?: string,
  frequency?: RecurrenceFrequency,
  interval?: number,
  alarms?: string[] | number[],
  notes?: string,
  location?: LocationType,
  isFollowUp?: boolean,
  isPreEvent?: boolean,
  isPostEvent?: boolean,
  modifiable?: boolean,
  anyoneCanAddSelf?: boolean,
  guestsCanInviteOthers?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalAllDay?: boolean,
  timezone?: string,
  taskId?: string,
  taskType?: string,
  followUpEventId?: string,
  preEventId?: string,
  postEventId?: string,
  forEventId?: string,
  zoomMeet?: boolean,
  googleMeet?: boolean,
  meetingTypeString?: meetingTypeStringType,
  zoomPassword?: string,
  zoomPrivateMeeting?: boolean,
  attendees?: Person[],
  conferenceId?: string,
  maxAttendees?: number,
  sendUpdates?: SendUpdatesType,
  status?: string,
  summary?: string,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  recurringEventId?: string,
  iCalUID?: string,
  htmlLink?: string,
  colorId?: string,
  originalTimezone?: string,
  backgroundColor?: string,
  foregroundColor?: string,
  useDefaultAlarms?: boolean,
  positiveImpactScore?: number,
  negativeImpactScore?: number,
  positiveImpactDayOfWeek?: number,
  positiveImpactTime?: Time,
  negativeImpactDayOfWeek?: number,
  negativeImpactTime?: Time,
  preferredDayOfWeek?: number,
  preferredTime?: Time,
  isExternalMeeting?: boolean,
  isExternalMeetingModifiable?: boolean,
  isMeetingModifiable?: boolean,
  isMeeting?: boolean,
  dailyTaskList?: boolean,
  weeklyTaskList?: boolean,
  isBreak?: boolean,
  preferredStartTimeRange?: Time,
  preferredEndTimeRange?: Time,
  copyAvailability?: boolean,
  copyTimeBlocking?: boolean,
  copyTimePreference?: boolean,
  copyReminders?: boolean,
  copyPriorityLevel?: boolean,
  copyModifiable?: boolean,
  copyCategories?: boolean,
  copyIsBreak?: boolean,
  timeBlocking?: BufferTimeType,
  userModifiedAvailability?: boolean,
  userModifiedTimeBlocking?: boolean,
  userModifiedTimePreference?: boolean,
  userModifiedReminders?: boolean,
  userModifiedPriorityLevel?: boolean,
  userModifiedCategories?: boolean,
  userModifiedModifiable?: boolean,
  userModifiedIsBreak?: boolean,
  hardDeadline?: string,
  softDeadline?: string,
  copyIsMeeting?: boolean,
  copyIsExternalMeeting?: boolean,
  userModifiedIsMeeting?: boolean,
  userModifiedIsExternalMeeting?: boolean,
  duration?: number,
  copyDuration?: boolean,
  userModifiedDuration?: boolean,
  method?: 'create' | 'update',
  unlink?: boolean,
  byWeekDay?: Day[],
  priority?: number
) => {
  try {
    console.log(
      hardDeadline,
      softDeadline,
      ' hardDeadline, softDeadline inside editEventForTask'
    );
    console.log(categoryIds, ' categoryIds inside editEventForTask');
    return updateEvent(
      id,
      startDate,
      endDate,
      userId,
      client,
      selectedCalendarId,
      categoryIds,
      title,
      allDay,
      recurringEndDate,
      frequency,
      interval,
      alarms,
      notes,
      location,
      isFollowUp,
      isPreEvent,
      isPostEvent,
      modifiable,
      anyoneCanAddSelf,
      guestsCanInviteOthers,
      guestsCanSeeOtherGuests,
      originalAllDay,
      timezone,
      taskId,
      taskType,
      followUpEventId,
      preEventId,
      postEventId,
      forEventId,
      zoomMeet,
      googleMeet,
      meetingTypeString,
      zoomPassword,
      zoomPrivateMeeting,
      attendees,
      conferenceId,
      maxAttendees,
      sendUpdates,
      status,
      summary,
      transparency,
      visibility,
      recurringEventId,
      iCalUID,
      htmlLink,
      colorId,
      originalTimezone,
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
      byWeekDay,
      priority
    );
  } catch (e) {
    console.log(e, ' unable to edit event in app');
  }
};

export const createDeadlineForTask = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  title: string,
  duration: number,
  taskId: string,
  taskType: TaskType,
  priority: number,
  softDeadline?: string,
  hardDeadline?: string,
  reminders?: number[],
  categoryIds?: string[],
  colorId?: string,
  backgroundColor?: string,
  notes?: string
) => {
  try {
    const calendarDoc = await getCalendarInDb(client, userId, undefined, true);
    const calendarId = calendarDoc?.id;
    if (calendarId) {
      const eventId = await createNewEvent(
        dayjs().add(1, 'h').format(),
        dayjs().add(1, 'h').add(duration, 'minute').format(),
        userId,
        client,
        calendarId,
        categoryIds,
        title,
        false,
        undefined,
        undefined,
        undefined,
        reminders,
        notes || title,
        undefined,
        false,
        false,
        false,
        true,
        false,
        false,
        false,
        false,
        dayjs.tz.guess(),
        taskId,
        taskType,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        title,
        'opaque',
        'private',
        undefined,
        undefined,
        undefined,
        colorId,
        undefined,
        backgroundColor,
        undefined,
        reminders?.length === 0,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        taskType === 'Daily',
        taskType === 'Weekly',
        false,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        true,
        true,
        categoryIds?.length > 0,
        true,
        true,
        true,
        true,
        hardDeadline,
        softDeadline,
        undefined,
        undefined,
        undefined,
        undefined,
        duration,
        undefined,
        true,
        undefined,
        undefined,
        undefined,
        priority
      );
      return eventId;
    }
  } catch (e) {
    console.log(e, ' unable to create deadline in app');
  }
};

export const createDeadlineEventForTaskList = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  title: string,
  duration: number,
  taskId: string,
  taskType: TaskType,
  priority: number,
  softDeadline?: string,
  hardDeadline?: string
): Promise<EventType> => {
  try {
    let calendarDoc: CalendarType = null;
    calendarDoc = await getCalendarInDb(client, userId, undefined, true);

    console.log(
      calendarDoc,
      ' calendarDoc inside createDeadlineEventForTaskList'
    );
    console.log(
      calendarDoc?.resource,
      ' global calendarDoc resource inside createDeadlineEventForTaskList'
    );
    console.log(
      hardDeadline,
      softDeadline,
      ' hardDeadline, softDeadline inside createDeadlineEventForTaskList'
    );
    if (!calendarDoc || calendarDoc?.resource !== googleResourceName) {
      calendarDoc = await getCalendarInDb(
        client,
        userId,
        undefined,
        undefined,
        googleResourceName
      );
    }

    console.log(
      calendarDoc,
      ' calendarDoc inside createDeadlineEventForTaskList'
    );

    const calendarId = calendarDoc?.id;

    console.log(
      calendarId,
      ' calendarId inside createDeadlineEventForTaskList'
    );
    console.log(
      calendarDoc?.resource,
      ' resource inside createDeadlineEventForTaskList'
    );
    if (calendarId && calendarDoc?.resource === googleResourceName) {
      const colorId = calendarDoc?.colorId;
      const backgroundColor = calendarDoc?.backgroundColor;

      const startDate = dayjs().add(1, 'h').format();
      const endDate = dayjs().add(1, 'h').add(duration, 'minute').format();
      const dailyTaskList = taskType === 'Daily';
      const weeklyTaskList = taskType === 'Weekly';
      const eventId = await createNewEvent(
        startDate,
        endDate,
        userId,
        client,
        calendarId,
        undefined,
        title,
        false,
        undefined,
        undefined,
        undefined,
        undefined,
        title,
        undefined,
        false,
        false,
        false,
        true,
        false,
        false,
        false,
        false,
        dayjs.tz.guess(),
        taskId,
        taskType,
        undefined,
        undefined,
        undefined,
        undefined,
        false,
        false,
        undefined,
        undefined,
        false,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        title,
        'opaque',
        'private',
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        backgroundColor,
        undefined,
        true,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        false,
        true,
        true,
        false,
        dailyTaskList,
        weeklyTaskList,
        false,
        undefined,
        undefined,
        false,
        false,
        false,
        false,
        false,
        false,
        false,
        false,
        undefined,
        false,
        false,
        false,
        false,
        true,
        false,
        true,
        true,
        hardDeadline,
        softDeadline,
        false,
        false,
        true,
        true,
        duration,
        false,
        true,
        'update',
        false,
        undefined,
        priority
      );
      console.log(eventId, ' eventId inside createDeadlineEventForTaskList');
      return {
        id: `${eventId}#${calendarId}`,
        eventId,
        userId,
        dailyTaskList,
        weeklyTaskList,
        calendarId,
        title,
        duration,
        taskId,
        taskType,
        priority,
        colorId,
        backgroundColor,
        startDate,
        endDate,
        createdDate: dayjs().toISOString(),
        updatedAt: dayjs().toISOString(),
        deleted: false,
        timezone: dayjs.tz.guess(),
        isFollowUp: false,
        isPreEvent: false,
        isPostEvent: false,
        modifiable: true,
        anyoneCanAddSelf: false,
        guestsCanInviteOthers: false,
        guestsCanSeeOtherGuests: false,
        originalStartDate: dayjs().format(),
        originalAllDay: false,
        summary: title,
        transparency: 'opaque',
        visibility: 'private',
        isBreak: false,
        userModifiedAvailability: false,
        userModifiedPriorityLevel: true,
        userModifiedModifiable: true,
        userModifiedIsBreak: true,
        softDeadline,
        hardDeadline,
        userModifiedDuration: true,
        method: 'update',
        notes: title,
      };
    }
  } catch (e) {
    console.log(e, ' unable to create event in app');
  }
};

export const submitCalendarForQueue = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  startDate: string,
  endDate: string,
  toast?: any
) => {
  try {
    const calendar = await getCalendarInDb(
      client,
      userId,
      undefined,
      undefined,
      googleResourceName
    );
    if (!calendar) {
      console.log('no google calendar inside submitCalendarForQueue');
      return;
    }

    const token = await Session.getAccessToken();
    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };
    const body = {
      userId,
      startDate,
      endDate: endDate,
      timezone: dayjs.tz.guess(),
    };

    const url = calendarToQueueAuthUrl;
    const results = await axios.post(url, body, config);
    if (results.data.message) {
      if (toast) {
        toast({
          status: 'success',
          title: 'Running Schedule Assist',
          description: 'Check back in a few minutes',
          duration: 9000,
          isClosable: true,
        });
      }
    }
  } catch (e) {
    console.log(e, ' unable to create event in app');
  }
};

export const submitEventForQueue = async (
  event: EventType,
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  isDaily?: boolean,
  toast?: any
) => {
  try {
    const calendar = await getCalendarInDb(
      client,
      userId,
      undefined,
      undefined,
      googleResourceName
    );
    if (!calendar) {
      console.log('no google calendar inside submitEventForQueue');
      return;
    }

    const token = await Session.getAccessToken();
    const url =
      isDaily === true ? eventToQueueShortAuthUrl : eventToQueueAuthUrl;
    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };
    const filteredEvent = _.omit(event, ['__typename']);
    const results = await axios.post(url, filteredEvent, config);
    if (results.data.message) {
      if (toast) {
        toast({
          status: 'success',
          title: 'Event added to queue',
          description: 'Event added to queue for schedule assist',
          duration: 9000,
          isClosable: true,
        });
      }
    }
  } catch (e) {
    console.log(e, 'error for changeLink');
  }
};

export const createDailyDeadline = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  taskId: string,
  newDailyTaskText: string,
  newDailyPriority: number,
  newDailyDeadline: string,
  newDailyDeadlineType: DeadlineType,
  newDailyDuration: number,
  toast?: any
) => {
  try {
    const notes = newDailyTaskText;

    if (!notes) {
      if (toast) {
        toast({
          status: 'error',
          title: 'Empty',
          description: 'Your task is empty.',
          duration: 9000,
          isClosable: true,
        });
      }

      return;
    }

    console.log(
      newDailyDeadline,
      newDailyDeadlineType,
      ' newDailyDeadline, newDailyDeadlineType inside createDailyDeadline'
    );
    const event = await createDeadlineEventForTaskList(
      client,
      userId,
      notes,
      newDailyDuration,
      taskId,
      'Daily',
      newDailyPriority,
      newDailyDeadlineType === 'soft' ? newDailyDeadline : null,
      newDailyDeadlineType === 'hard' ? newDailyDeadline : null
    );
    console.log(event, 'event inside createDailyDeadline');
    if (event) {
      return event;
    }
    return null;
  } catch (e) {
    console.log(e, ' unable to create event in app');
  }
};

export const createWeeklyDeadline = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  taskId: string,
  newWeeklyTaskText: string,
  newWeeklyPriority: number,
  newWeeklyDeadline: string,
  newWeeklyDeadlineType: DeadlineType,
  newWeeklyDuration: number,
  toast?: any
) => {
  try {
    const notes = newWeeklyTaskText;

    if (!notes) {
      if (toast) {
        toast({
          status: 'error',
          title: 'Empty',
          description: 'Your task is empty',
          duration: 9000,
          isClosable: true,
        });
      }
      return;
    }

    console.log(
      newWeeklyDeadline,
      newWeeklyDeadlineType,
      ' newWeeklyDeadline, newWeeklyDeadlineType inside createWeeklyDeadline'
    );
    const event = await createDeadlineEventForTaskList(
      client,
      userId,
      notes,
      newWeeklyDuration,
      taskId,
      WeeklyTask,
      newWeeklyPriority,
      newWeeklyDeadlineType === 'soft' ? newWeeklyDeadline : null,
      newWeeklyDeadlineType === 'hard' ? newWeeklyDeadlineType : null
    );
    if (event) {
      return event;
    }
  } catch (e) {
    console.log(e, ' unable to create event in app');
  }
};
