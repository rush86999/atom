import {
  googleCalendarName,
  googleResourceName,
  hasuraAdminSecret,
  hasuraGraphUrl,
} from '@chat/_libs/constants';
import { TaskType } from '@chat/_libs/types/TaskType';
import got from 'got';
import { TaskStatus } from './constants';
import { v4 as uuid } from 'uuid';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import {
  EventType,
  RecurrenceFrequencyType,
} from '@chat/_libs/types/EventType';
import {
  allEventWithDatesOpenSearch,
  convertEventTitleToOpenAIVector,
  createGoogleEvent,
  createPreAndPostEventsFromEvent,
  createRRuleString,
  deleteEventGivenId,
  deleteGoogleEvent,
  deleteRemindersWithIds,
  eventSearchBoundary,
  extrapolateDateFromJSONData,
  extrapolateStartDateFromJSONData,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
  getCalendarIntegrationByName,
  getEventFromPrimaryKey,
  getGlobalCalendar,
  getTaskGivenId,
  insertReminders,
  patchGoogleEvent,
  putDataInTrainEventIndexInOpenSearch,
  upsertEvents,
} from '@chat/_libs/api-helper';
import { CalendarType } from '@chat/_libs/types/CalendarType';
import {
  RecurrenceRuleType,
  TransparencyType,
  VisibilityType,
} from '@chat/_libs/types/EventType';
import { ReminderType } from '@chat/_libs/types/GoogleTypes';
import { GoogleReminderType } from '@chat/_libs/types/GoogleReminderType';
import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import { UpdateTaskType } from './types';
import requiredFields from './requiredFields';
import PreferredTimeRangeType from '@chat/_libs/types/PreferredTimeRangeType';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { GoogleResType } from '@chat/_libs/types/GoogleResType';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
import { deletePreferredTimeRangesGivenEventId } from '../removeAllPreferedTimes/api-helper';
import { CalendarClientType } from '@chat/_libs/types/CalendarIntegrationType';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import { SearchBoundaryType } from '../deleteTask/types';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import isoWeek from 'dayjs/plugin/isoWeek';

// updateGoogleEvent
export const patchGoogleEventForTaskList = async (
  eventId: string,
  userId: string,
  clientType: CalendarClientType,
  calendarId: string,
  calendarResourceName: string,
  title?: string,
  duration?: number,
  timezone?: string,
  startDate?: string,
  oldStartDate?: string,
  allDay?: boolean,
  reminders?: number[],
  recurObject?: RecurrenceRuleType,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  location?: string
): Promise<void> => {
  try {
    // getGlobalCalendar
    // let calendarDoc: CalendarType = null
    // calendarDoc = await getGlobalCalendar(userId)

    // get client type
    // const calIntegration = await getCalendarIntegrationByName(
    //     userId,
    //     googleCalendarName,
    // )

    if (calendarId && calendarResourceName === googleResourceName) {
      const startDateTime = startDate
        ? dayjs(startDate).tz(timezone).format()
        : undefined;
      const endDateTime =
        startDateTime && duration
          ? dayjs(startDateTime).tz(timezone).add(duration, 'minute').format()
          : oldStartDate && duration
            ? dayjs(oldStartDate).tz(timezone).add(duration, 'minute').format()
            : undefined;

      const googleReminder: GoogleReminderType = {
        overrides: reminders?.map((r) => ({ method: 'email', minutes: r })),
        useDefault: false,
      };

      // take care of recurrence
      const recur = createRRuleString(
        recurObject?.frequency,
        recurObject?.interval,
        recurObject?.byWeekDay,
        recurObject?.occurrence,
        recurObject?.endDate,
        recurObject?.byMonthDay
      );

      await patchGoogleEvent(
        userId,
        calendarId,
        eventId,
        clientType,
        endDateTime,
        startDateTime,
        0,
        undefined,
        'all',
        false,
        undefined,
        undefined,
        title,
        title,
        timezone,
        allDay && dayjs(startDate).tz(timezone).format('YYYY-MM-DD'),
        allDay &&
          dayjs(startDate).tz(timezone).add(duration, 'm').format('YYYY-MM-DD'),
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        recur,
        reminders?.length > 0 ? googleReminder : undefined,
        undefined,
        undefined,
        transparency,
        visibility,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        'default',
        location,
        undefined
      );
      console.log(' googlePatch inside updateDeadlineEventForTaskList');
    }
  } catch (e) {
    console.log(e, ' unable to patch event for task');
  }
};

export const updateTaskInDb = async (task: TaskType) => {
  try {
    let variables: any = { id: task?.id };

    if (task?.completedDate !== undefined) {
      variables.completedDate = task?.completedDate;
    }

    if (task?.duration !== undefined) {
      variables.duration = task?.duration;
    }

    if (task?.eventId !== undefined) {
      variables.eventId = task?.eventId;
    }

    if (task?.hardDeadline !== undefined) {
      variables.hardDeadline = task?.hardDeadline;
    }

    if (task?.important !== undefined) {
      variables.important = task?.important;
    }

    if (task?.notes !== undefined) {
      variables.notes = task?.notes;
    }

    if (task?.order !== undefined) {
      variables.order = task?.order;
    }

    if (task?.parentId !== undefined) {
      variables.parentId = task?.parentId;
    }

    if (task?.priority !== undefined) {
      variables.priority = task?.priority;
    }

    if (task?.softDeadline !== undefined) {
      variables.softDeadline = task?.softDeadline;
    }

    if (task?.status !== undefined) {
      variables.status = task?.status;
    }

    if (task?.syncData !== undefined) {
      variables.syncData = task?.syncData;
    }

    if (task?.type !== undefined) {
      variables.type = task?.type;
    }

    const updateTaskById = `
            mutation UpdateTaskById($id: uuid!, ${task?.completedDate !== undefined ? '$completedDate: timestamptz,' : ''} ${task?.duration !== undefined ? '$duration: Int,' : ''} ${task?.eventId !== undefined ? '$eventId: String,' : ''} ${task?.hardDeadline !== undefined ? '$hardDeadline: timestamp,' : ''} ${task?.important !== undefined ? '$important: Boolean,' : ''} ${task?.notes !== undefined ? '$notes: String,' : ''} ${task?.order !== undefined ? '$order: Int,' : ''} ${task?.parentId !== undefined ? '$parentId: uuid,' : ''} ${task?.priority !== undefined ? '$priority: Int,' : ''} ${task?.softDeadline !== undefined ? '$softDeadline: timestamp,' : ''} ${task?.status !== undefined ? '$status: String,' : ''} ${task?.syncData !== undefined ? '$syncData: jsonb,' : ''} ${task?.type !== undefined ? '$type: String' : ''}){
                update_Task_by_pk(pk_columns: {id: $id}, _set: {${task?.completedDate !== undefined ? 'completedDate: $completedDate,' : ''} ${task?.duration !== undefined ? 'duration: $duration,' : ''} ${task?.eventId !== undefined ? 'eventId: $eventId,' : ''} ${task?.hardDeadline !== undefined ? 'hardDeadline: $hardDeadline,' : ''} ${task?.important !== undefined ? 'important: $important,' : ''} ${task?.notes !== undefined ? 'notes: $notes,' : ''} ${task?.order !== undefined ? 'order: $order,' : ''} ${task?.parentId !== undefined ? 'parentId: $parentId,' : ''} ${task?.priority !== undefined ? 'priority: $priority,' : ''} ${task?.softDeadline !== undefined ? 'softDeadline: $softDeadline,' : ''} ${task?.status !== undefined ? 'status: $status,' : ''} ${task?.syncData !== undefined ? 'syncData: $syncData,' : ''} ${task?.type !== undefined ? 'type: $type' : ''}}) {
                    completedDate
                    createdDate
                    duration
                    eventId
                    hardDeadline
                    id
                    important
                    notes
                    order
                    parentId
                    priority
                    softDeadline
                    status
                    syncData
                    type
                    updatedAt
                    userId
                }
            }
        `;

    const operationName = 'UpdateTaskById';
    const query = updateTaskById;

    const res: { data: { update_Task_by_pk: TaskType } } = await got
      .post(hasuraGraphUrl, {
        json: {
          operationName,
          query,
          variables,
        },
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
      })
      .json();

    console.log(res, ' res inside updateTaskInDb');
    if (res?.data?.update_Task_by_pk) {
      return res?.data?.update_Task_by_pk;
    }
  } catch (e) {
    console.log(e, ' unable to get insertTaskInDb');
  }
};

export const updateTaskInDbAndEventInGoogle = async (
  userId: string,
  taskId: string,
  clientType: CalendarClientType,
  calendarId: string,
  calendarResourceName: string,
  taskListName?: string,
  text?: string,
  timezone?: string,
  startDate?: string,
  oldStartDate?: string,
  important?: boolean,
  softDeadline?: string,
  hardDeadline?: string,
  status?: TaskStatus,
  eventId?: string,
  duration?: number,
  priority?: number,
  allDay?: boolean,
  reminders?: number[],
  recurObject?: RecurrenceRuleType,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  location?: string
) => {
  try {
    const toUpdateTask: TaskType = {
      id: taskId,
      userId,
      eventId,
      type: taskListName,
      notes: text,
      important,
      status,
      priority,
      softDeadline,
      hardDeadline,
      duration,
      updatedAt: dayjs().format(),
      createdDate: dayjs().format(),
    };

    // const deadline = softDeadline || hardDeadline

    await updateTaskInDb(toUpdateTask);

    await patchGoogleEventForTaskList(
      eventId,
      userId,
      clientType,
      calendarId,
      calendarResourceName,
      text,
      duration || 30,
      timezone,
      startDate,
      oldStartDate,
      allDay,
      reminders,
      recurObject,
      transparency,
      visibility,
      location
    );
  } catch (e) {
    console.log(e, ' unable to get insertTaskInDb');
  }
};

export const getTaskStatus = (status: 'todo' | 'doing' | 'done') => {
  if (!status) {
    return;
  }

  switch (status) {
    case 'todo':
      return TaskStatus.TODO;
    case 'doing':
      return TaskStatus.DOING;
    case 'done':
      return TaskStatus.DONE;
  }
};

export const finalStepUpdateTask = async (
  body: UpdateTaskType,
  startDate: string,
  endDate: string,
  response: any
) => {
  try {
    // convert to vector for search
    const searchTitle = body?.oldTitle || body?.title;
    const searchVector = await convertEventTitleToOpenAIVector(searchTitle);

    const res = await allEventWithDatesOpenSearch(
      body?.userId,
      searchVector,
      startDate,
      endDate
    );

    const id = res?.hits?.hits?.[0]?._id;

    // validate found event
    if (!id) {
      response.query = 'event_not_found';
      return response;
    }

    const eventId = id;

    // get client type
    const calIntegration = await getCalendarIntegrationByName(
      body?.userId,
      googleCalendarName
    );

    // getGlobalCalendar
    let calendarDoc: CalendarType = null;
    calendarDoc = await getGlobalCalendar(body?.userId);

    // delete old reminders
    if (body?.reminders?.length > 0) {
      await deleteRemindersWithIds([eventId], body?.userId);
    }

    // delete old time preferences
    if (body?.timePreferences?.length > 0) {
      await deletePreferredTimeRangesGivenEventId(eventId);
    }

    // get old event
    const oldEvent = await getEventFromPrimaryKey(eventId);

    // get old Task
    const oldTask = await getTaskGivenId(oldEvent?.taskId);

    // validate
    if (!oldEvent?.id) {
      throw new Error('no old event found?!');
    }

    // take care of recurrence
    const recur = createRRuleString(
      body?.recur?.frequency,
      body?.recur?.interval,
      body?.recur?.byWeekDay,
      body?.recur?.occurrence,
      body?.recur?.endDate,
      body?.recur?.byMonthDay
    );

    // if existing buffer times
    // delete old and create new ones later on
    if (
      (oldEvent?.preEventId && body?.bufferTime?.beforeEvent) ||
      (oldEvent?.postEventId && body?.bufferTime?.afterEvent)
    ) {
      // delete buffere times if any

      if (oldEvent?.preEventId) {
        const preEvent = await getEventFromPrimaryKey(oldEvent?.preEventId);
        await deleteGoogleEvent(
          body?.userId,
          preEvent?.calendarId,
          preEvent?.eventId,
          calIntegration?.clientType
        );
        await deleteEventGivenId(oldEvent?.preEventId);
      }

      if (oldEvent?.postEventId) {
        const postEvent = await getEventFromPrimaryKey(oldEvent?.postEventId);
        await deleteGoogleEvent(
          body?.userId,
          postEvent?.calendarId,
          postEvent?.eventId,
          calIntegration?.clientType
        );
        await deleteEventGivenId(oldEvent?.postEventId);
      }
    }

    // patchGoogleEvent
    const startDateTime = startDate
      ? dayjs(startDate).tz(body?.timezone).format()
      : oldEvent?.startDate;
    const endDateTime =
      startDateTime && body?.duration
        ? dayjs(startDateTime)
            .tz(body?.timezone)
            .add(body?.duration, 'minute')
            .format()
        : oldEvent?.endDate;
    // need to be updated
    const eventToUpsertLocal: EventType = {
      ...oldEvent,
      id: eventId,
      userId: body?.userId,
      updatedAt: dayjs().format(),
      userModifiedModifiable: true,
    };

    if (body?.title) {
      eventToUpsertLocal.title = body?.title;
      eventToUpsertLocal.summary = body?.title;
    }

    if (startDate) {
      eventToUpsertLocal.startDate = dayjs(startDate)
        .tz(body?.timezone)
        .format();
    }

    if (endDateTime && endDateTime !== oldEvent?.endDate) {
      eventToUpsertLocal.endDate = dayjs(startDateTime)
        .tz(body?.timezone)
        .add(body?.duration, 'minute')
        .format();
    }

    if (body?.duration && body?.duration !== oldEvent?.duration) {
      eventToUpsertLocal.duration = body?.duration;
    }

    if (body?.isFollowUp) {
      eventToUpsertLocal.isFollowUp = body.isFollowUp;
    }

    if (body?.allDay) {
      eventToUpsertLocal.allDay = body?.allDay;
    }

    if (body?.description || body?.title) {
      eventToUpsertLocal.notes = body?.description || body?.title;
    }

    if (body?.timezone) {
      eventToUpsertLocal.timezone = body?.timezone;
    }

    if (body?.priority) {
      eventToUpsertLocal.priority = body.priority;
    }

    if (body?.transparency) {
      eventToUpsertLocal.transparency = body.transparency;
      eventToUpsertLocal.userModifiedAvailability = true;
    }

    if (body?.visibility) {
      eventToUpsertLocal.visibility = body.visibility as VisibilityType;
    }

    if (body?.duration) {
      eventToUpsertLocal.duration = body?.duration;
    }

    if (body?.bufferTime) {
      eventToUpsertLocal.timeBlocking = body.bufferTime;
      eventToUpsertLocal.userModifiedTimeBlocking = true;
    }

    if (body?.timePreferences?.length > 0) {
      eventToUpsertLocal.userModifiedTimePreference = true;
      eventToUpsertLocal.modifiable = true;
      eventToUpsertLocal.userModifiedModifiable = true;
    }

    if (body?.reminders?.length > 0) {
      eventToUpsertLocal.userModifiedReminders = true;
    }

    if (body?.priority > 1) {
      eventToUpsertLocal.userModifiedPriorityLevel = true;
      eventToUpsertLocal.modifiable = true;
      eventToUpsertLocal.userModifiedModifiable = true;
    }

    if (body?.duration) {
      eventToUpsertLocal.userModifiedDuration = true;
    }

    if (body?.location) {
      eventToUpsertLocal.location = { title: body?.location };
    }

    if (body?.recur) {
      eventToUpsertLocal.recurrence = recur;
      eventToUpsertLocal.recurrenceRule = {
        frequency: body?.recur?.frequency,
        interval: body?.recur?.interval,
        byWeekDay: body?.recur?.byWeekDay,
        occurrence: body?.recur?.occurrence,
        endDate: body?.recur?.endDate,
        byMonthDay: body?.recur?.byMonthDay,
      };
    }

    const eventsToUpsert: EventType[] = [];

    const deadlineType =
      body?.deadlineType ||
      (oldTask?.softDeadline ? 'softDeadline' : 'hardDeadline');

    if (body?.taskList?.length > 0) {
      for (const taskList of body?.taskList) {
        const remindersToUpdateEventId: ReminderType[] = [];

        if (body?.reminders?.length > 0) {
          const newReminders: ReminderType[] = body?.reminders.map((r) => ({
            id: uuid(),
            userId: body?.userId,
            eventId: eventToUpsertLocal?.id,
            timezone: body?.timezone,
            minutes: r,
            useDefault: false,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            deleted: false,
          }));

          remindersToUpdateEventId.push(...newReminders);
        }

        // time preferences and priority
        const newPreferredTimeRanges: PreferredTimeRangeType[] = [];

        for (const timepreference of body?.timePreferences) {
          if (timepreference.dayOfWeek?.length > 0) {
            for (const dayOfWeek of timepreference.dayOfWeek) {
              const newPreferredTimeRange: PreferredTimeRangeType = {
                id: uuid(),
                eventId: eventToUpsertLocal?.id,
                dayOfWeek: DayOfWeekEnum[dayOfWeek],
                startTime: timepreference?.timeRange?.startTime,
                endTime: timepreference?.timeRange?.endTime,
                updatedAt: dayjs().format(),
                createdDate: dayjs().format(),
                userId: body?.userId,
              };

              newPreferredTimeRanges.push(newPreferredTimeRange);
            }
          } else {
            const newPreferredTimeRange: PreferredTimeRangeType = {
              id: uuid(),
              eventId: eventToUpsertLocal?.id,
              startTime: timepreference?.timeRange?.startTime,
              endTime: timepreference?.timeRange?.endTime,
              updatedAt: dayjs().format(),
              createdDate: dayjs().format(),
              userId: body?.userId,
            };

            newPreferredTimeRanges.push(newPreferredTimeRange);
          }
        }

        await updateTaskInDbAndEventInGoogle(
          body?.userId,
          eventToUpsertLocal?.taskId,
          calIntegration?.clientType,
          oldEvent?.calendarId,
          calendarDoc?.resource,
          taskList?.tasklistName,
          taskList?.task,
          eventToUpsertLocal?.timezone,
          eventToUpsertLocal?.startDate,
          oldEvent?.startDate,
          undefined,
          deadlineType === 'softDeadline' && body?.dueDate,
          deadlineType === 'hardDeadline' && body?.dueDate,
          getTaskStatus(taskList?.status) || oldTask?.status,
          oldEvent?.id,
          eventToUpsertLocal?.duration,
          eventToUpsertLocal?.priority,
          eventToUpsertLocal?.allDay,
          body?.reminders,
          (body?.recur as RecurrenceRuleType)?.frequency
            ? (body?.recur as RecurrenceRuleType)
            : undefined,
          eventToUpsertLocal?.transparency,
          eventToUpsertLocal?.visibility,
          eventToUpsertLocal?.location?.title
        );

        // add buffer time if any
        if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
          const returnValues = createPreAndPostEventsFromEvent(
            eventToUpsertLocal,
            body?.bufferTime
          );

          if (returnValues?.afterEvent) {
            const googleResValue: GoogleResType = await createGoogleEvent(
              body?.userId,
              eventToUpsertLocal?.calendarId,
              calIntegration?.clientType,
              returnValues?.afterEvent?.id,
              returnValues?.afterEvent?.endDate,
              returnValues?.afterEvent?.startDate,
              0,
              undefined,
              returnValues?.afterEvent?.sendUpdates,
              returnValues?.afterEvent?.anyoneCanAddSelf,
              undefined,
              undefined,
              returnValues?.afterEvent?.title,
              returnValues?.afterEvent?.notes,
              body?.timezone,
              undefined,
              undefined,
              undefined,
              returnValues?.afterEvent?.guestsCanInviteOthers,
              returnValues?.afterEvent?.guestsCanModify,
              returnValues?.afterEvent?.guestsCanSeeOtherGuests,
              undefined,
              undefined,
              undefined,
              undefined,
              undefined,
              undefined,
              returnValues?.afterEvent?.transparency,
              returnValues?.afterEvent?.visibility,
              undefined,
              undefined,
              undefined,
              undefined,
              undefined,
              undefined,
              'default',
              undefined,
              undefined
            );

            returnValues.afterEvent.id = googleResValue.id;
            returnValues.afterEvent.eventId = googleResValue.googleEventId;
            returnValues.newEvent.postEventId = returnValues.afterEvent.id;
          }

          if (returnValues?.beforeEvent) {
            const googleResValue: GoogleResType = await createGoogleEvent(
              body?.userId,
              eventToUpsertLocal?.calendarId,
              calIntegration?.clientType,
              returnValues?.beforeEvent?.id,
              returnValues?.beforeEvent?.endDate,
              returnValues?.beforeEvent?.startDate,
              0,
              undefined,
              returnValues?.beforeEvent?.sendUpdates,
              returnValues?.beforeEvent?.anyoneCanAddSelf,
              undefined,
              undefined,
              returnValues?.beforeEvent?.title,
              returnValues?.beforeEvent?.notes,
              body?.timezone,
              undefined,
              undefined,
              undefined,
              returnValues?.beforeEvent?.guestsCanInviteOthers,
              returnValues?.beforeEvent?.guestsCanModify,
              returnValues?.beforeEvent?.guestsCanSeeOtherGuests,
              undefined,
              undefined,
              undefined,
              undefined,
              undefined,
              undefined,
              returnValues?.beforeEvent?.transparency,
              returnValues?.beforeEvent?.visibility,
              undefined,
              undefined,
              undefined,
              undefined,
              undefined,
              undefined,
              'default',
              undefined,
              undefined
            );

            returnValues.beforeEvent.id = googleResValue.id;
            returnValues.beforeEvent.eventId = googleResValue.googleEventId;
            returnValues.newEvent.preEventId = returnValues.afterEvent.id;
          }

          eventsToUpsert.push(
            ...[
              returnValues.newEvent,
              returnValues?.afterEvent,
              returnValues?.beforeEvent,
            ]?.filter((e) => !!e)
          );
        } else {
          eventsToUpsert.push(eventToUpsertLocal);
        }

        // insert reminders
        if (remindersToUpdateEventId?.length > 0) {
          await insertReminders(remindersToUpdateEventId);
        }

        // insert time preferences
        if (newPreferredTimeRanges?.length > 0) {
          await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
        }

        // convert to vector for search
        if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
          const searchVector = await convertEventTitleToOpenAIVector(
            taskList?.task
          );

          // train event
          await putDataInTrainEventIndexInOpenSearch(
            eventId,
            searchVector,
            body?.userId
          );
        }
      }
    } else {
      const remindersToUpdateEventId: ReminderType[] = [];

      if (body?.reminders?.length > 0) {
        const newReminders: ReminderType[] = body?.reminders.map((r) => ({
          id: uuid(),
          userId: body?.userId,
          eventId: eventToUpsertLocal?.id,
          timezone: body?.timezone,
          minutes: r,
          useDefault: false,
          updatedAt: dayjs().format(),
          createdDate: dayjs().format(),
          deleted: false,
        }));

        remindersToUpdateEventId.push(...newReminders);
      }

      // time preferences and priority
      const newPreferredTimeRanges: PreferredTimeRangeType[] = [];

      for (const timepreference of body?.timePreferences) {
        if (timepreference.dayOfWeek?.length > 0) {
          for (const dayOfWeek of timepreference.dayOfWeek) {
            const newPreferredTimeRange: PreferredTimeRangeType = {
              id: uuid(),
              eventId: eventToUpsertLocal?.id,
              dayOfWeek: DayOfWeekEnum[dayOfWeek],
              startTime: timepreference?.timeRange?.startTime,
              endTime: timepreference?.timeRange?.endTime,
              updatedAt: dayjs().format(),
              createdDate: dayjs().format(),
              userId: body?.userId,
            };

            newPreferredTimeRanges.push(newPreferredTimeRange);
          }
        } else {
          const newPreferredTimeRange: PreferredTimeRangeType = {
            id: uuid(),
            eventId: eventToUpsertLocal?.id,
            startTime: timepreference?.timeRange?.startTime,
            endTime: timepreference?.timeRange?.endTime,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            userId: body?.userId,
          };

          newPreferredTimeRanges.push(newPreferredTimeRange);
        }
      }

      await updateTaskInDbAndEventInGoogle(
        body?.userId,
        eventToUpsertLocal?.taskId,
        calIntegration?.clientType,
        oldEvent?.calendarId,
        calendarDoc?.resource,
        undefined,
        eventToUpsertLocal?.title,
        eventToUpsertLocal?.timezone,
        eventToUpsertLocal?.startDate,
        oldEvent?.startDate,
        undefined,
        body?.deadlineType === 'softDeadline' && body?.dueDate,
        body?.deadlineType === 'hardDeadline' && body?.dueDate,
        oldTask?.status,
        oldEvent?.id,
        eventToUpsertLocal?.duration,
        eventToUpsertLocal?.priority,
        eventToUpsertLocal?.allDay,
        body?.reminders,
        (body?.recur as RecurrenceRuleType)?.frequency
          ? (body?.recur as RecurrenceRuleType)
          : undefined,
        eventToUpsertLocal?.transparency,
        eventToUpsertLocal?.visibility,
        eventToUpsertLocal?.location?.title
      );

      // add buffer time if any
      if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
        // validate
        if (!calIntegration?.clientType) {
          throw new Error(
            'no client type inside calendar integration inside create agenda'
          );
        }

        const returnValues = createPreAndPostEventsFromEvent(
          eventToUpsertLocal,
          body?.bufferTime
        );

        if (returnValues?.afterEvent) {
          const googleResValue: GoogleResType = await createGoogleEvent(
            body?.userId,
            eventToUpsertLocal?.calendarId,
            calIntegration?.clientType,
            returnValues?.afterEvent?.id,
            returnValues?.afterEvent?.endDate,
            returnValues?.afterEvent?.startDate,
            0,
            undefined,
            returnValues?.afterEvent?.sendUpdates,
            returnValues?.afterEvent?.anyoneCanAddSelf,
            undefined,
            undefined,
            returnValues?.afterEvent?.title,
            returnValues?.afterEvent?.notes,
            body?.timezone,
            undefined,
            undefined,
            undefined,
            returnValues?.afterEvent?.guestsCanInviteOthers,
            returnValues?.afterEvent?.guestsCanModify,
            returnValues?.afterEvent?.guestsCanSeeOtherGuests,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            returnValues?.afterEvent?.transparency,
            returnValues?.afterEvent?.visibility,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            'default',
            undefined,
            undefined
          );

          returnValues.afterEvent.id = googleResValue.id;
          returnValues.afterEvent.eventId = googleResValue.googleEventId;
          returnValues.newEvent.postEventId = returnValues.afterEvent.id;
        }

        if (returnValues?.beforeEvent) {
          const googleResValue: GoogleResType = await createGoogleEvent(
            body?.userId,
            eventToUpsertLocal?.calendarId,
            calIntegration?.clientType,
            returnValues?.beforeEvent?.id,
            returnValues?.beforeEvent?.endDate,
            returnValues?.beforeEvent?.startDate,
            0,
            undefined,
            returnValues?.beforeEvent?.sendUpdates,
            returnValues?.beforeEvent?.anyoneCanAddSelf,
            undefined,
            undefined,
            returnValues?.beforeEvent?.title,
            returnValues?.beforeEvent?.notes,
            body?.timezone,
            undefined,
            undefined,
            undefined,
            returnValues?.beforeEvent?.guestsCanInviteOthers,
            returnValues?.beforeEvent?.guestsCanModify,
            returnValues?.beforeEvent?.guestsCanSeeOtherGuests,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            returnValues?.beforeEvent?.transparency,
            returnValues?.beforeEvent?.visibility,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            'default',
            undefined,
            undefined
          );

          returnValues.beforeEvent.id = googleResValue.id;
          returnValues.beforeEvent.eventId = googleResValue.googleEventId;
          returnValues.newEvent.preEventId = returnValues.afterEvent.id;
        }

        eventsToUpsert.push(
          ...[
            returnValues.newEvent,
            returnValues?.afterEvent,
            returnValues?.beforeEvent,
          ]?.filter((e) => !!e)
        );
      } else {
        eventsToUpsert.push(eventToUpsertLocal);
      }

      // insert reminders
      if (remindersToUpdateEventId?.length > 0) {
        await insertReminders(remindersToUpdateEventId);
      }

      // insert time preferences
      if (newPreferredTimeRanges?.length > 0) {
        await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
      }

      // convert to vector for search
      if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
        const searchVector = await convertEventTitleToOpenAIVector(body?.title);

        // train event
        await putDataInTrainEventIndexInOpenSearch(
          eventId,
          searchVector,
          body?.userId
        );
      }
    }

    console.log(eventsToUpsert?.length, ' eventsToUpsert?.length');

    await upsertEvents(eventsToUpsert);

    // success response
    response.query = 'completed';
    response.data = 'successfully  updated task';
    return response;
  } catch (e) {
    console.log(e, ' unable to final step update task');
  }
};

export const processUpdateTaskPending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string
) => {
  try {
    let duration = 0;

    const year = dateJSONBody?.year;
    const month = dateJSONBody?.month;
    const day = dateJSONBody?.day;
    const isoWeekday = dateJSONBody?.isoWeekday;
    const hour = dateJSONBody?.hour;
    const minute = dateJSONBody?.minute;
    const startTime = dateJSONBody?.startTime;

    const yearDue = dateJSONBody?.dueDate?.year;
    const monthDue = dateJSONBody?.dueDate?.month;
    const dayDue = dateJSONBody?.dueDate?.day;
    const isoWeekdayDue = dateJSONBody?.dueDate?.isoWeekday;
    const hourDue = dateJSONBody?.dueDate?.hour;
    const minuteDue = dateJSONBody?.dueDate?.minute;
    const startTimeDue = dateJSONBody?.dueDate?.startTime;

    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'updateTask',
    };

    const taskStartDate = extrapolateDateFromJSONData(
      currentTime,
      timezone,
      year,
      month,
      day,
      isoWeekday,
      hour,
      minute,
      startTime,
      dateJSONBody?.relativeTimeChangeFromNow,
      dateJSONBody?.relativeTimeFromNow
    );

    const taskDueDate = extrapolateDateFromJSONData(
      currentTime,
      timezone,
      yearDue,
      monthDue,
      dayDue,
      isoWeekdayDue,
      hourDue,
      minuteDue,
      startTimeDue,
      dateJSONBody?.dueDate?.relativeTimeChangeFromNow,
      dateJSONBody?.dueDate?.relativeTimeFromNow
    );

    if (dateJSONBody?.duration) {
      duration = dateJSONBody?.duration;
    } else if (dateJSONBody?.startTime && dateJSONBody?.endTime) {
      // likely start time also present

      const startTimeObject = dayjs(dateJSONBody?.startTime, 'HH:mm');
      const endTimeObject = dayjs(dateJSONBody.endTime, 'HH:mm');

      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else if (jsonBody?.params?.startTime && jsonBody?.params?.endTime) {
      const startTimeObject = dayjs(jsonBody?.params?.startTime);
      const endTimeObject = dayjs(jsonBody?.params?.endTime);
      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    }

    // take care of any recurring dates
    let recurObject: RecurrenceRuleType | {} = {};
    if (dateJSONBody?.recur?.frequency) {
      const recurEndDate = extrapolateDateFromJSONData(
        currentTime,
        timezone,
        dateJSONBody?.recur?.endDate?.year,
        dateJSONBody?.recur?.endDate?.month,
        dateJSONBody?.recur?.endDate?.day,
        dateJSONBody?.recur?.endDate?.isoWeekday,
        dateJSONBody?.recur?.endDate?.hour,
        dateJSONBody?.recur?.endDate?.minute,
        dateJSONBody?.recur?.endDate?.startTime,
        dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow,
        dateJSONBody?.recur?.endDate?.relativeTimeFromNow
      );

      recurObject = {
        frequency:
          (dateJSONBody?.recur?.frequency as RecurrenceFrequencyType) ||
          jsonBody?.params?.recurrence?.frequency,
        interval:
          dateJSONBody?.recur?.interval ||
          jsonBody?.params?.recurrence?.interval,
      };

      if (dateJSONBody?.recur?.byWeekDay) {
        (recurObject as RecurrenceRuleType).byWeekDay =
          dateJSONBody?.recur?.byWeekDay;
      }

      if (dateJSONBody?.recur?.byMonthDay) {
        (recurObject as RecurrenceRuleType).byMonthDay =
          dateJSONBody?.recur?.byMonthDay;
      }

      if (dateJSONBody?.recur?.occurrence) {
        (recurObject as RecurrenceRuleType).occurrence =
          dateJSONBody?.recur?.occurrence;
      }

      if (recurEndDate || jsonBody?.params?.recurrence?.endDate) {
        (recurObject as RecurrenceRuleType).endDate =
          recurEndDate || jsonBody?.params?.recurrence?.endDate;
      }
    }

    const body: UpdateTaskType = {
      userId,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      oldTitle: jsonBody?.params?.oldTitle,
      method: dateJSONBody?.method as any,
      duration,
      description: jsonBody?.params?.description || jsonBody?.params?.notes,
      startDate: jsonBody?.params?.startTime || taskStartDate,
      dueDate: taskDueDate || (recurObject as RecurrenceRuleType)?.endDate,
      bufferTime: jsonBody?.params?.bufferTime,
      reminders: jsonBody?.params?.alarms || [],
      priority: jsonBody?.params?.priority || 1,
      timePreferences: dateJSONBody?.timePreferences || [],
      location: jsonBody?.params?.location,
      transparency: jsonBody?.params?.transparency,
      visibility: jsonBody?.params.visibility as VisibilityType,
      isBreak: jsonBody?.params?.isBreak,
      allDay: dateJSONBody?.allDay,
      deadlineType: jsonBody?.params?.deadlineType,
      taskList:
        jsonBody?.params?.taskList?.map((tl) => ({
          ...tl,
          tasklistName: tl?.tasklistName?.toLowerCase(),
        })) || [],
      isFollowUp: jsonBody?.params?.isFollowUp,
      timezone,
    };

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      body.recur = recurObject as any;
    }

    if (response.query === 'missing_fields') {
      return response;
    }

    const searchBoundary = eventSearchBoundary(
      timezone,
      dateJSONBody,
      currentTime
    );

    let startDate = searchBoundary.startDate;
    let endDate = searchBoundary.endDate;

    //  allEventWithEventOpenSearch
    // allEventOpenSearch
    if (!startDate) {
      startDate = dayjs().subtract(2, 'w').format();
    }

    if (!endDate) {
      endDate = dayjs().add(4, 'w').format();
    }

    // validate remaining required fields
    if (!body?.title) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[0]);
      response.data = missingFields;
      response.prevData = body;
      response.prevDataExtra = {
        searchBoundary,
      };
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    const response2 = await finalStepUpdateTask(
      body,
      startDate,
      endDate,
      response
    );

    return response2;

    // convert to vector for search
    // const searchTitle = body?.oldTitle || body?.title
    // const searchVector = await convertEventTitleToOpenAIVector(searchTitle)

    // const res = await allEventWithDatesOpenSearch(userId, searchVector, startDate, endDate)

    // const id = res?.hits?.hits?.[0]?._id

    // // validate found event
    // if (!id) {
    //     response.query = 'event_not_found'
    //     return response
    // }

    // const eventId = id

    // // get client type
    // const calIntegration = await getCalendarIntegrationByName(
    //     userId,
    //     googleCalendarName,
    // )

    // // getGlobalCalendar
    // let calendarDoc: CalendarType = null
    // calendarDoc = await getGlobalCalendar(userId)

    // // delete old reminders
    // if (body?.reminders?.length > 0) {

    //     await deleteRemindersWithIds([eventId], userId)
    // }

    // // delete old time preferences
    // if (body?.timePreferences?.length > 0) {
    //     await deletePreferredTimeRangesGivenEventId(eventId)
    // }

    // // get old event
    // const oldEvent = await getEventFromPrimaryKey(eventId)

    // // get old Task
    // const oldTask = await getTaskGivenId(oldEvent?.taskId)

    // // validate
    // if (!oldEvent?.id) {
    //     throw new Error('no old event found?!')
    // }

    // // take care of recurrence
    // const recur = createRRuleString(body?.recur?.frequency, body?.recur?.interval, body?.recur?.byWeekDay, body?.recur?.occurrence, body?.recur?.endDate, body?.recur?.byMonthDay)

    // // if existing buffer times
    // // delete old and create new ones later on
    // if ((oldEvent?.preEventId && body?.bufferTime?.beforeEvent) || (oldEvent?.postEventId && body?.bufferTime?.afterEvent)) {
    //     // delete buffere times if any

    //     if (oldEvent?.preEventId) {
    //         const preEvent = await getEventFromPrimaryKey(oldEvent?.preEventId)
    //         await deleteGoogleEvent(userId, preEvent?.calendarId, preEvent?.eventId, calIntegration?.clientType)
    //         await deleteEventGivenId(oldEvent?.preEventId)

    //     }

    //     if (oldEvent?.postEventId) {

    //         const postEvent = await getEventFromPrimaryKey(oldEvent?.postEventId)
    //         await deleteGoogleEvent(userId, postEvent?.calendarId, postEvent?.eventId, calIntegration?.clientType)
    //         await deleteEventGivenId(oldEvent?.postEventId)
    //     }
    // }

    // // patchGoogleEvent
    // const startDateTime = startDate ? dayjs(startDate).tz(timezone).format() : oldEvent?.startDate
    // const endDateTime = (startDateTime && duration) ? dayjs(startDateTime).tz(timezone).add(duration, 'minute').format()
    //     : oldEvent?.endDate
    // // need to be updated
    // const eventToUpsertLocal: EventType = {
    //     ...oldEvent,
    //     id: eventId,
    //     userId,
    //     updatedAt: dayjs().format(),
    //     userModifiedModifiable: true,
    // }

    // if (body?.title) {
    //     eventToUpsertLocal.title = body?.title
    //     eventToUpsertLocal.summary = body?.title
    // }

    // if (startDate) {
    //     eventToUpsertLocal.startDate = dayjs(startDate).tz(timezone).format()
    // }

    // if (endDateTime && (endDateTime !== oldEvent?.endDate)) {
    //     eventToUpsertLocal.endDate = dayjs(startDateTime).tz(timezone).add(duration, 'minute').format()
    // }

    // if (duration && (duration !== oldEvent?.duration)) {
    //     eventToUpsertLocal.duration = duration
    // }

    // if (body?.isFollowUp) {
    //     eventToUpsertLocal.isFollowUp = body.isFollowUp
    // }

    // if (body?.allDay) {
    //     eventToUpsertLocal.allDay = body?.allDay
    // }

    // if (body?.description || body?.title) {
    //     eventToUpsertLocal.notes = body?.description || body?.title
    // }

    // if (body?.timezone) {
    //     eventToUpsertLocal.timezone = body?.timezone
    // }

    // if (body?.priority) {
    //     eventToUpsertLocal.priority = body.priority
    // }

    // if (body?.transparency) {
    //     eventToUpsertLocal.transparency = body.transparency
    //     eventToUpsertLocal.userModifiedAvailability = true
    // }

    // if (body?.visibility) {
    //     eventToUpsertLocal.visibility = body.visibility as VisibilityType
    // }

    // if (body?.duration) {
    //     eventToUpsertLocal.duration = duration
    // }

    // if (body?.bufferTime) {
    //     eventToUpsertLocal.timeBlocking = body.bufferTime
    //     eventToUpsertLocal.userModifiedTimeBlocking = true
    // }

    // if (body?.timePreferences?.length > 0) {
    //     eventToUpsertLocal.userModifiedTimePreference = true
    //     eventToUpsertLocal.modifiable = true
    //     eventToUpsertLocal.userModifiedModifiable = true
    // }

    // if (body?.reminders?.length > 0) {
    //     eventToUpsertLocal.userModifiedReminders = true
    // }

    // if (body?.priority > 1) {
    //     eventToUpsertLocal.userModifiedPriorityLevel = true
    //     eventToUpsertLocal.modifiable = true
    //     eventToUpsertLocal.userModifiedModifiable = true
    // }

    // if (body?.duration) {
    //     eventToUpsertLocal.userModifiedDuration = true
    // }

    // if (body?.location) {
    //     eventToUpsertLocal.location = { title: body?.location }
    // }

    // if (body?.recur) {
    //     eventToUpsertLocal.recurrence = recur
    //     eventToUpsertLocal.recurrenceRule = {
    //         frequency: body?.recur?.frequency,
    //         interval: body?.recur?.interval,
    //         byWeekDay: body?.recur?.byWeekDay,
    //         occurrence: body?.recur?.occurrence,
    //         endDate: body?.recur?.endDate,
    //         byMonthDay: body?.recur?.byMonthDay,
    //     }
    // }

    // const eventsToUpsert: EventType[] = []

    // const deadlineType = body?.deadlineType || (oldTask?.softDeadline ? 'softDeadline' : 'hardDeadline')

    // if (body?.taskList?.length > 0) {
    //     for (const taskList of body?.taskList) {

    //         const remindersToUpdateEventId: ReminderType[] = []

    //         if (body?.reminders?.length > 0) {
    //             const newReminders: ReminderType[] = body?.reminders.map(r => ({
    //                 id: uuid(),
    //                 userId,
    //                 eventId: eventToUpsertLocal?.id,
    //                 timezone,
    //                 minutes: r,
    //                 useDefault: false,
    //                 updatedAt: dayjs().format(),
    //                 createdDate: dayjs().format(),
    //                 deleted: false,
    //             }))

    //             remindersToUpdateEventId.push(...newReminders)
    //         }

    //         // time preferences and priority
    //         const newPreferredTimeRanges: PreferredTimeRangeType[] = []

    //         for (const timepreference of body?.timePreferences) {

    //             if (timepreference.dayOfWeek?.length > 0) {
    //                 for (const dayOfWeek of timepreference.dayOfWeek) {

    //                     const newPreferredTimeRange: PreferredTimeRangeType = {
    //                         id: uuid(),
    //                         eventId: eventToUpsertLocal?.id,
    //                         dayOfWeek: DayOfWeekEnum[dayOfWeek],
    //                         startTime: timepreference?.timeRange?.startTime,
    //                         endTime: timepreference?.timeRange?.endTime,
    //                         updatedAt: dayjs().format(),
    //                         createdDate: dayjs().format(),
    //                         userId,
    //                     }

    //                     newPreferredTimeRanges.push(newPreferredTimeRange)
    //                 }
    //             } else {

    //                 const newPreferredTimeRange: PreferredTimeRangeType = {
    //                     id: uuid(),
    //                     eventId: eventToUpsertLocal?.id,
    //                     startTime: timepreference?.timeRange?.startTime,
    //                     endTime: timepreference?.timeRange?.endTime,
    //                     updatedAt: dayjs().format(),
    //                     createdDate: dayjs().format(),
    //                     userId,
    //                 }

    //                 newPreferredTimeRanges.push(newPreferredTimeRange)
    //             }

    //         }

    //         await updateTaskInDbAndEventInGoogle(
    //             userId,
    //             eventToUpsertLocal?.taskId,
    //             calIntegration?.clientType,
    //             oldEvent?.calendarId,
    //             calendarDoc?.resource,
    //             taskList?.tasklistName,
    //             taskList?.task,
    //             eventToUpsertLocal?.timezone,
    //             eventToUpsertLocal?.startDate,
    //             oldEvent?.startDate,
    //             undefined,
    //             (deadlineType === 'softDeadline') && body?.dueDate,
    //             (deadlineType === 'hardDeadline') && body?.dueDate,
    //             getTaskStatus(taskList?.status) || oldTask?.status,
    //             oldEvent?.id,
    //             eventToUpsertLocal?.duration,
    //             eventToUpsertLocal?.priority,
    //             eventToUpsertLocal?.allDay,
    //             body?.reminders,
    //             (recurObject as RecurrenceRuleType)?.frequency ? recurObject as RecurrenceRuleType : undefined,
    //             eventToUpsertLocal?.transparency,
    //             eventToUpsertLocal?.visibility,
    //             eventToUpsertLocal?.location?.title,
    //         )

    //         // add buffer time if any
    //         if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {

    //             const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime)

    //             if (returnValues?.afterEvent) {

    //                 const googleResValue: GoogleResType = await createGoogleEvent(
    //                     userId,
    //                     eventToUpsertLocal?.calendarId,
    //                     calIntegration?.clientType,
    //                     returnValues?.afterEvent?.id,
    //                     returnValues?.afterEvent?.endDate,
    //                     returnValues?.afterEvent?.startDate,
    //                     0,
    //                     undefined,
    //                     returnValues?.afterEvent?.sendUpdates,
    //                     returnValues?.afterEvent?.anyoneCanAddSelf,
    //                     undefined,
    //                     undefined,
    //                     returnValues?.afterEvent?.title,
    //                     returnValues?.afterEvent?.notes,
    //                     timezone,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     returnValues?.afterEvent?.guestsCanInviteOthers,
    //                     returnValues?.afterEvent?.guestsCanModify,
    //                     returnValues?.afterEvent?.guestsCanSeeOtherGuests,
    //                     returnValues?.afterEvent?.originalStartDate,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     returnValues?.afterEvent?.transparency,
    //                     returnValues?.afterEvent?.visibility,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     'default',
    //                     undefined,
    //                     undefined,
    //                 )

    //                 returnValues.afterEvent.id = googleResValue.id
    //                 returnValues.afterEvent.eventId = googleResValue.googleEventId
    //                 returnValues.newEvent.postEventId = returnValues.afterEvent.id

    //             }

    //             if (returnValues?.beforeEvent) {

    //                 const googleResValue: GoogleResType = await createGoogleEvent(
    //                     userId,
    //                     eventToUpsertLocal?.calendarId,
    //                     calIntegration?.clientType,
    //                     returnValues?.beforeEvent?.id,
    //                     returnValues?.beforeEvent?.endDate,
    //                     returnValues?.beforeEvent?.startDate,
    //                     0,
    //                     undefined,
    //                     returnValues?.beforeEvent?.sendUpdates,
    //                     returnValues?.beforeEvent?.anyoneCanAddSelf,
    //                     undefined,
    //                     undefined,
    //                     returnValues?.beforeEvent?.title,
    //                     returnValues?.beforeEvent?.notes,
    //                     timezone,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     returnValues?.beforeEvent?.guestsCanInviteOthers,
    //                     returnValues?.beforeEvent?.guestsCanModify,
    //                     returnValues?.beforeEvent?.guestsCanSeeOtherGuests,
    //                     returnValues?.beforeEvent?.originalStartDate,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     returnValues?.beforeEvent?.transparency,
    //                     returnValues?.beforeEvent?.visibility,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     undefined,
    //                     'default',
    //                     undefined,
    //                     undefined,
    //                 )

    //                 returnValues.beforeEvent.id = googleResValue.id
    //                 returnValues.beforeEvent.eventId = googleResValue.googleEventId
    //                 returnValues.newEvent.preEventId = returnValues.afterEvent.id

    //             }

    //             eventsToUpsert.push(...([returnValues.newEvent, returnValues?.afterEvent, returnValues?.beforeEvent]?.filter(e => !!e)))
    //         } else {
    //             eventsToUpsert.push(eventToUpsertLocal)
    //         }

    //         // insert reminders
    //         if (remindersToUpdateEventId?.length > 0) {
    //             await insertReminders(remindersToUpdateEventId)
    //         }

    //         // insert time preferences
    //         if (newPreferredTimeRanges?.length > 0) {
    //             await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges)
    //         }

    //         // convert to vector for search
    //         if ((newPreferredTimeRanges?.length > 0) || body?.priority > 1) {

    //             const searchVector = await convertEventTitleToOpenAIVector(taskList?.task)

    //             // train event
    //             await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, userId)
    //         }
    //     }
    // } else {

    //     const remindersToUpdateEventId: ReminderType[] = []

    //     if (body?.reminders?.length > 0) {
    //         const newReminders: ReminderType[] = body?.reminders.map(r => ({
    //             id: uuid(),
    //             userId,
    //             eventId: eventToUpsertLocal?.id,
    //             timezone,
    //             minutes: r,
    //             useDefault: false,
    //             updatedAt: dayjs().format(),
    //             createdDate: dayjs().format(),
    //             deleted: false,
    //         }))

    //         remindersToUpdateEventId.push(...newReminders)
    //     }

    //     // time preferences and priority
    //     const newPreferredTimeRanges: PreferredTimeRangeType[] = []

    //     for (const timepreference of body?.timePreferences) {

    //         if (timepreference.dayOfWeek?.length > 0) {
    //             for (const dayOfWeek of timepreference.dayOfWeek) {

    //                 const newPreferredTimeRange: PreferredTimeRangeType = {
    //                     id: uuid(),
    //                     eventId: eventToUpsertLocal?.id,
    //                     dayOfWeek: DayOfWeekEnum[dayOfWeek],
    //                     startTime: timepreference?.timeRange?.startTime,
    //                     endTime: timepreference?.timeRange?.endTime,
    //                     updatedAt: dayjs().format(),
    //                     createdDate: dayjs().format(),
    //                     userId,
    //                 }

    //                 newPreferredTimeRanges.push(newPreferredTimeRange)
    //             }
    //         } else {

    //             const newPreferredTimeRange: PreferredTimeRangeType = {
    //                 id: uuid(),
    //                 eventId: eventToUpsertLocal?.id,
    //                 startTime: timepreference?.timeRange?.startTime,
    //                 endTime: timepreference?.timeRange?.endTime,
    //                 updatedAt: dayjs().format(),
    //                 createdDate: dayjs().format(),
    //                 userId,
    //             }

    //             newPreferredTimeRanges.push(newPreferredTimeRange)
    //         }

    //     }

    //     await updateTaskInDbAndEventInGoogle(
    //         userId,
    //         eventToUpsertLocal?.taskId,
    //         calIntegration?.clientType,
    //         oldEvent?.calendarId,
    //         calendarDoc?.resource,
    //         undefined,
    //         eventToUpsertLocal?.title,
    //         eventToUpsertLocal?.timezone,
    //         eventToUpsertLocal?.startDate,
    //         oldEvent?.startDate,
    //         undefined,
    //         (body?.deadlineType === 'softDeadline') && body?.dueDate,
    //         (body?.deadlineType === 'hardDeadline') && body?.dueDate,
    //         oldTask?.status,
    //         oldEvent?.id,
    //         eventToUpsertLocal?.duration,
    //         eventToUpsertLocal?.priority,
    //         eventToUpsertLocal?.allDay,
    //         body?.reminders,
    //         (recurObject as RecurrenceRuleType)?.frequency ? recurObject as RecurrenceRuleType : undefined,
    //         eventToUpsertLocal?.transparency,
    //         eventToUpsertLocal?.visibility,
    //         eventToUpsertLocal?.location?.title,
    //     )

    //     // add buffer time if any
    //     if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {

    //         // validate
    //         if (!calIntegration?.clientType) {
    //             throw new Error('no client type inside calendar integration inside create agenda')
    //         }

    //         const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime)

    //         if (returnValues?.afterEvent) {

    //             const googleResValue: GoogleResType = await createGoogleEvent(
    //                 userId,
    //                 eventToUpsertLocal?.calendarId,
    //                 calIntegration?.clientType,
    //                 returnValues?.afterEvent?.id,
    //                 returnValues?.afterEvent?.endDate,
    //                 returnValues?.afterEvent?.startDate,
    //                 0,
    //                 undefined,
    //                 returnValues?.afterEvent?.sendUpdates,
    //                 returnValues?.afterEvent?.anyoneCanAddSelf,
    //                 undefined,
    //                 undefined,
    //                 returnValues?.afterEvent?.title,
    //                 returnValues?.afterEvent?.notes,
    //                 timezone,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 returnValues?.afterEvent?.guestsCanInviteOthers,
    //                 returnValues?.afterEvent?.guestsCanModify,
    //                 returnValues?.afterEvent?.guestsCanSeeOtherGuests,
    //                 returnValues?.afterEvent?.originalStartDate,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 returnValues?.afterEvent?.transparency,
    //                 returnValues?.afterEvent?.visibility,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 'default',
    //                 undefined,
    //                 undefined,
    //             )

    //             returnValues.afterEvent.id = googleResValue.id
    //             returnValues.afterEvent.eventId = googleResValue.googleEventId
    //             returnValues.newEvent.postEventId = returnValues.afterEvent.id

    //         }

    //         if (returnValues?.beforeEvent) {

    //             const googleResValue: GoogleResType = await createGoogleEvent(
    //                 userId,
    //                 eventToUpsertLocal?.calendarId,
    //                 calIntegration?.clientType,
    //                 returnValues?.beforeEvent?.id,
    //                 returnValues?.beforeEvent?.endDate,
    //                 returnValues?.beforeEvent?.startDate,
    //                 0,
    //                 undefined,
    //                 returnValues?.beforeEvent?.sendUpdates,
    //                 returnValues?.beforeEvent?.anyoneCanAddSelf,
    //                 undefined,
    //                 undefined,
    //                 returnValues?.beforeEvent?.title,
    //                 returnValues?.beforeEvent?.notes,
    //                 timezone,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 returnValues?.beforeEvent?.guestsCanInviteOthers,
    //                 returnValues?.beforeEvent?.guestsCanModify,
    //                 returnValues?.beforeEvent?.guestsCanSeeOtherGuests,
    //                 returnValues?.beforeEvent?.originalStartDate,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 returnValues?.beforeEvent?.transparency,
    //                 returnValues?.beforeEvent?.visibility,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 undefined,
    //                 'default',
    //                 undefined,
    //                 undefined,
    //             )

    //             returnValues.beforeEvent.id = googleResValue.id
    //             returnValues.beforeEvent.eventId = googleResValue.googleEventId
    //             returnValues.newEvent.preEventId = returnValues.afterEvent.id

    //         }

    //         eventsToUpsert.push(...([returnValues.newEvent, returnValues?.afterEvent, returnValues?.beforeEvent]?.filter(e => !!e)))
    //     } else {
    //         eventsToUpsert.push(eventToUpsertLocal)
    //     }

    //     // insert reminders
    //     if (remindersToUpdateEventId?.length > 0) {
    //         await insertReminders(remindersToUpdateEventId)
    //     }

    //     // insert time preferences
    //     if (newPreferredTimeRanges?.length > 0) {
    //         await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges)
    //     }

    //     // convert to vector for search
    //     if ((newPreferredTimeRanges?.length > 0) || body?.priority > 1) {

    //         const searchVector = await convertEventTitleToOpenAIVector(body?.title)

    //         // train event
    //         await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, userId)
    //     }
    // }

    // console.log(eventsToUpsert?.length, ' eventsToUpsert?.length')

    // await upsertEvents(eventsToUpsert)

    // // success response
    // response.query = 'completed'

    // return response
  } catch (e) {
    console.log(e, ' unable to process add task');
  }
};

export const processUpdateTaskMissingFieldsReturned = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string,
  messageHistoryObject: SkillMessageHistoryType
) => {
  try {
    let duration = 0;

    const year =
      dateJSONBody?.year || messageHistoryObject?.prevDateJsonBody?.year;
    const month =
      dateJSONBody?.month || messageHistoryObject?.prevDateJsonBody?.month;
    const day =
      dateJSONBody?.day || messageHistoryObject?.prevDateJsonBody?.day;
    const isoWeekday =
      dateJSONBody?.isoWeekday ||
      messageHistoryObject?.prevDateJsonBody?.isoWeekday;
    const hour =
      dateJSONBody?.hour || messageHistoryObject?.prevDateJsonBody?.hour;
    const minute =
      dateJSONBody?.minute || messageHistoryObject?.prevDateJsonBody?.minute;
    const startTime =
      dateJSONBody?.startTime ||
      messageHistoryObject?.prevDateJsonBody?.startTime;

    const yearDue =
      dateJSONBody?.dueDate?.year ||
      messageHistoryObject?.prevDateJsonBody?.dueDate?.year;
    const monthDue =
      dateJSONBody?.dueDate?.month ||
      messageHistoryObject?.prevDateJsonBody?.dueDate?.month;
    const dayDue =
      dateJSONBody?.dueDate?.day ||
      messageHistoryObject?.prevDateJsonBody?.dueDate?.day;
    const isoWeekdayDue =
      dateJSONBody?.dueDate?.isoWeekday ||
      messageHistoryObject?.prevDateJsonBody?.dueDate?.isoWeekday;
    const hourDue =
      dateJSONBody?.dueDate?.hour ||
      messageHistoryObject?.prevDateJsonBody?.dueDate?.hour;
    const minuteDue =
      dateJSONBody?.dueDate?.minute ||
      messageHistoryObject?.prevDateJsonBody?.dueDate?.minute;
    const startTimeDue =
      dateJSONBody?.dueDate?.startTime ||
      messageHistoryObject?.prevDateJsonBody?.dueDate?.startTime;

    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'updateTask',
    };

    const taskStartDate = extrapolateDateFromJSONData(
      currentTime,
      timezone,
      year,
      month,
      day,
      isoWeekday,
      hour,
      minute,
      startTime,
      dateJSONBody?.relativeTimeChangeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.relativeTimeChangeFromNow,
      dateJSONBody?.relativeTimeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.relativeTimeFromNow
    );

    const taskDueDate = extrapolateDateFromJSONData(
      currentTime,
      timezone,
      yearDue,
      monthDue,
      dayDue,
      isoWeekdayDue,
      hourDue,
      minuteDue,
      startTimeDue,
      dateJSONBody?.dueDate?.relativeTimeChangeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.dueDate
          ?.relativeTimeChangeFromNow,
      dateJSONBody?.dueDate?.relativeTimeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.dueDate?.relativeTimeFromNow
    );

    if (
      dateJSONBody?.duration ||
      messageHistoryObject?.prevDateJsonBody?.duration
    ) {
      duration =
        dateJSONBody?.duration ||
        messageHistoryObject?.prevDateJsonBody?.duration;
    } else if (
      (dateJSONBody?.startTime ||
        messageHistoryObject?.prevDateJsonBody?.startTime) &&
      (dateJSONBody?.endTime || messageHistoryObject?.prevDateJsonBody?.endTime)
    ) {
      // likely start time also present

      const startTimeObject = dayjs(
        dateJSONBody?.startTime ||
          messageHistoryObject?.prevDateJsonBody?.startTime,
        'HH:mm'
      );
      const endTimeObject = dayjs(
        dateJSONBody.endTime || messageHistoryObject?.prevDateJsonBody?.endTime,
        'HH:mm'
      );

      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else if (
      (jsonBody?.params?.startTime ||
        messageHistoryObject?.prevJsonBody?.params?.startTime) &&
      (jsonBody?.params?.endTime ||
        messageHistoryObject?.prevJsonBody?.params?.endTime)
    ) {
      const startTimeObject = dayjs(
        jsonBody?.params?.startTime ||
          messageHistoryObject?.prevJsonBody?.params?.startTime
      );
      const endTimeObject = dayjs(
        jsonBody?.params?.endTime ||
          messageHistoryObject?.prevJsonBody?.params?.endTime
      );
      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    }

    // take care of any recurring dates
    let recurObject: RecurrenceRuleType | {} = {};
    if (
      dateJSONBody?.recur?.frequency ||
      messageHistoryObject?.prevDateJsonBody?.recur?.frequency
    ) {
      const recurEndDate = extrapolateDateFromJSONData(
        currentTime,
        timezone,
        dateJSONBody?.recur?.endDate?.year ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.year,
        dateJSONBody?.recur?.endDate?.month ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.month,
        dateJSONBody?.recur?.endDate?.day ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.day,
        dateJSONBody?.recur?.endDate?.isoWeekday ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.isoWeekday,
        dateJSONBody?.recur?.endDate?.hour ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.hour,
        dateJSONBody?.recur?.endDate?.minute ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.minute,
        dateJSONBody?.recur?.endDate?.startTime ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.startTime,
        dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate
            ?.relativeTimeChangeFromNow,
        dateJSONBody?.recur?.endDate?.relativeTimeFromNow ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate
            ?.relativeTimeFromNow
      );

      recurObject = {
        frequency:
          (dateJSONBody?.recur?.frequency as RecurrenceFrequencyType) ||
          messageHistoryObject?.prevDateJsonBody?.recur?.frequency ||
          messageHistoryObject?.prevJsonBody?.params?.recurrence?.frequency ||
          jsonBody?.params?.recurrence?.frequency,
        interval:
          dateJSONBody?.recur?.interval ||
          messageHistoryObject?.prevDateJsonBody?.recur?.interval ||
          messageHistoryObject?.prevJsonBody?.params?.recurrence?.interval ||
          jsonBody?.params?.recurrence?.interval,
      };

      if (
        dateJSONBody?.recur?.byWeekDay ||
        messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay
      ) {
        (recurObject as RecurrenceRuleType).byWeekDay =
          dateJSONBody?.recur?.byWeekDay ||
          messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay;
      }

      if (
        dateJSONBody?.recur?.byMonthDay ||
        messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay
      ) {
        (recurObject as RecurrenceRuleType).byMonthDay =
          dateJSONBody?.recur?.byMonthDay ||
          messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay;
      }

      if (
        dateJSONBody?.recur?.occurrence ||
        messageHistoryObject?.prevDateJsonBody?.recur?.occurrence
      ) {
        (recurObject as RecurrenceRuleType).occurrence =
          dateJSONBody?.recur?.occurrence ||
          messageHistoryObject?.prevDateJsonBody?.recur?.occurrence;
      }

      if (
        recurEndDate ||
        messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
        jsonBody?.params?.recurrence?.endDate
      ) {
        (recurObject as RecurrenceRuleType).endDate =
          recurEndDate ||
          messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
          jsonBody?.params?.recurrence?.endDate;
      }
    }

    const newBody: UpdateTaskType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task ||
        messageHistoryObject?.prevJsonBody?.params?.title ||
        messageHistoryObject?.prevJsonBody?.params?.summary ||
        messageHistoryObject?.prevJsonBody?.params?.description ||
        messageHistoryObject?.prevJsonBody?.params?.taskList?.[0]?.task,
      oldTitle:
        jsonBody?.params?.oldTitle ||
        messageHistoryObject?.prevJsonBody?.params?.oldTitle,
      method: dateJSONBody?.method as any,
      duration,
      description:
        jsonBody?.params?.description ||
        jsonBody?.params?.notes ||
        messageHistoryObject?.prevJsonBody?.params?.description ||
        messageHistoryObject?.prevJsonBody?.params?.notes,
      startDate:
        jsonBody?.params?.startTime ||
        messageHistoryObject?.prevJsonBody?.params?.startTime ||
        taskStartDate,
      dueDate: taskDueDate || (recurObject as RecurrenceRuleType)?.endDate,
      bufferTime:
        jsonBody?.params?.bufferTime ||
        messageHistoryObject?.prevJsonBody?.params?.bufferTime,
      reminders:
        jsonBody?.params?.alarms ||
        messageHistoryObject?.prevJsonBody?.params?.alarms ||
        [],
      priority:
        jsonBody?.params?.priority ||
        messageHistoryObject?.prevJsonBody?.params?.priority ||
        1,
      timePreferences:
        dateJSONBody?.timePreferences ||
        messageHistoryObject?.prevDateJsonBody?.timePreferences ||
        [],
      location:
        jsonBody?.params?.location ||
        messageHistoryObject?.prevJsonBody?.params?.location,
      transparency:
        jsonBody?.params?.transparency ||
        messageHistoryObject?.prevJsonBody?.params?.transparency,
      visibility:
        (jsonBody?.params.visibility as VisibilityType) ||
        messageHistoryObject?.prevJsonBody?.params?.visibility,
      isBreak:
        jsonBody?.params?.isBreak ||
        messageHistoryObject?.prevJsonBody?.params?.isBreak,
      allDay:
        dateJSONBody?.allDay || messageHistoryObject?.prevDateJsonBody?.allDay,
      deadlineType:
        jsonBody?.params?.deadlineType ||
        messageHistoryObject?.prevJsonBody?.params?.deadlineType,
      taskList:
        jsonBody?.params?.taskList?.map((tl) => ({
          ...tl,
          tasklistName: tl?.tasklistName?.toLowerCase(),
        })) ||
        messageHistoryObject?.prevJsonBody?.params?.taskList?.map((tl) => ({
          ...tl,
          tasklistName: tl?.tasklistName?.toLowerCase(),
        })) ||
        [],
      isFollowUp:
        jsonBody?.params?.isFollowUp ||
        messageHistoryObject?.prevJsonBody?.params?.isFollowUp,
    };

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      newBody.recur = recurObject as any;
    }

    const prevBody: UpdateTaskType = {
      ...messageHistoryObject?.prevData,
    };

    if (!prevBody?.userId) {
      prevBody.userId = userId || newBody?.userId;
    }

    if (!prevBody?.timezone) {
      prevBody.timezone = timezone || newBody?.timezone;
    }

    if (!prevBody?.title) {
      prevBody.title = newBody?.title;
    }

    if (!prevBody?.oldTitle) {
      prevBody.oldTitle = newBody?.oldTitle;
    }

    if (!prevBody?.duration) {
      prevBody.duration = newBody?.duration;
    }

    if (!prevBody?.description) {
      prevBody.description = newBody?.description;
    }

    if (!prevBody?.startDate) {
      prevBody.startDate = newBody?.startDate;
    }

    if (!prevBody?.dueDate) {
      prevBody.dueDate = newBody?.dueDate;
    }

    if (!prevBody?.bufferTime) {
      prevBody.bufferTime = newBody?.bufferTime;
    }

    if (!(prevBody?.reminders?.length > 0)) {
      prevBody.reminders = newBody?.reminders || [];
    }

    if (!prevBody?.priority) {
      prevBody.priority = newBody?.priority;
    }

    if (!(prevBody?.timePreferences?.length > 0)) {
      prevBody.timePreferences = newBody?.timePreferences;
    }

    if (!prevBody?.location) {
      prevBody.location = newBody?.location;
    }

    if (!prevBody?.transparency) {
      prevBody.transparency = newBody?.transparency;
    }

    if (!prevBody?.visibility) {
      prevBody.visibility = newBody?.visibility;
    }

    if (prevBody.isBreak === undefined) {
      prevBody.isBreak = newBody?.isBreak;
    }

    if (prevBody.allDay === undefined) {
      prevBody.allDay = newBody?.allDay;
    }

    if (prevBody.deadlineType === undefined) {
      prevBody.deadlineType = newBody?.deadlineType;
    }

    if (prevBody.taskList === undefined) {
      prevBody.taskList = newBody?.taskList;
    }

    if (prevBody.isFollowUp === undefined) {
      prevBody.isFollowUp = newBody?.isFollowUp;
    }

    if (!prevBody?.recur) {
      prevBody.recur = newBody?.recur;
    }

    const searchBoundary = eventSearchBoundary(
      timezone,
      dateJSONBody,
      currentTime
    );

    let startDate = searchBoundary.startDate;
    let endDate = searchBoundary.endDate;

    //  allEventWithEventOpenSearch
    // allEventOpenSearch
    if (!startDate) {
      startDate = dayjs().subtract(2, 'w').format();
    }

    if (!endDate) {
      endDate = dayjs().add(4, 'w').format();
    }

    const prevSearchBoundary: SearchBoundaryType =
      messageHistoryObject?.prevDataExtra?.searchBoundary;

    let prevStartDate = prevSearchBoundary?.startDate;

    let prevEndDate = prevSearchBoundary?.endDate;

    if (!prevStartDate) {
      prevStartDate = startDate;
    }

    if (!prevEndDate) {
      prevEndDate = endDate;
    }

    // if (!prevBody?.startDate && !day && !isoWeekday) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0])
    //     response.data = missingFields
    //     response.prevData = prevBody
    //     response.prevDataExtra = {
    //         searchBoundary: {
    //             startDate: prevStartDate,
    //             endDate: prevEndDate,
    //         },
    //     }
    //     response.prevJsonBody = jsonBody
    //     response.prevDateJsonBody = dateJSONBody
    // }

    // if (!prevBody?.startDate && (hour === null) && (minute === null) && !startTime) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1])
    //     response.data = missingFields
    //     response.prevData = prevBody
    //     response.prevDataExtra = {
    //         searchBoundary: {
    //             startDate: prevStartDate,
    //             endDate: prevEndDate,
    //         },
    //     }
    //     response.prevJsonBody = jsonBody
    //     response.prevDateJsonBody = dateJSONBody
    // }

    // validate remaining required fields
    if (!prevBody?.title) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[0]);
      response.data = missingFields;
      response.prevData = prevBody;
      response.prevDataExtra = {
        searchBoundary: {
          startDate: prevStartDate,
          endDate: prevEndDate,
        },
      };
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepUpdateTask(
      prevBody,
      prevStartDate,
      prevEndDate,
      response
    );

    return response2;
  } catch (e) {
    console.log(e, ' unable to process update task missing fields returned');
  }
};

export const updateTaskControlCenter = async (
  openai: OpenAI,
  userId: string,
  timezone: string,
  messageHistoryObject: SkillMessageHistoryType,
  userCurrentTime: string,
  query: 'missing_fields' | 'completed' | 'event_not_found' | 'pending'
) => {
  try {
    const messageLength = messageHistoryObject.messages?.length;
    let userMessage = '';
    for (let i = messageLength; i > 0; i--) {
      const message = messageHistoryObject.messages[i - 1];

      if (message.role === 'user') {
        userMessage = message.content;
        break;
      }
    }

    const userInput = userMessage;

    let updateTaskRes: ResponseActionType = {
      query: 'completed',
      data: '',
      skill: '',
      prevData: {},
      prevDataExtra: {},
    };

    switch (query) {
      case 'pending':
        const jsonBody = await generateJSONDataFromUserInput(
          userInput,
          userCurrentTime
        );
        const dateTime = await generateDateTime(
          userInput,
          userCurrentTime,
          timezone
        );
        updateTaskRes = await processUpdateTaskPending(
          userId,
          timezone,
          jsonBody,
          dateTime,
          userCurrentTime
        );
        break;
      case 'missing_fields':
        let priorUserInput = '';
        let priorAssistantOutput = '';

        for (let i = messageLength; i > 0; i--) {
          const message = messageHistoryObject.messages[i - 1];

          if (message.role === 'assistant') {
            priorAssistantOutput = message.content;
            continue;
          }

          if (message.role === 'user') {
            if (message.content !== userInput) {
              priorUserInput = message.content;
              break;
            }
          }
        }

        if (!priorUserInput || !priorAssistantOutput) {
          console.log(priorUserInput, ' priorUserInput');
          console.log(priorAssistantOutput, ' priorAssistantOutput');
          throw new Error('no priorUserinput or priorAssistantOutput');
        }
        const jsonMissingFieldsBody =
          await generateMissingFieldsJSONDataFromUserInput(
            userInput,
            priorUserInput,
            priorAssistantOutput,
            userCurrentTime
          );
        const dateMissingFieldsTime = await generateMissingFieldsDateTime(
          userInput,
          priorUserInput,
          priorAssistantOutput,
          userCurrentTime,
          timezone
        );

        updateTaskRes = await processUpdateTaskMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (updateTaskRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          updateTaskRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (updateTaskRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          updateTaskRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = updateTaskRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = updateTaskRes?.prevData;
      messageHistoryObject.prevDataExtra = updateTaskRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = updateTaskRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = updateTaskRes?.prevJsonBody;
    } else if (updateTaskRes?.query === 'event_not_found') {
      const assistantMessage: AssistantMessageType = {
        role: 'assistant',
        content: "Oops... I couldn't find the event. Sorry :(",
      };

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'event_not_found';
      messageHistoryObject.required = null;
    }

    return messageHistoryObject;
  } catch (e) {
    console.log(e, ' unable to update task control center pending ');
  }
};
