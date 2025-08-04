import {
  googleCalendarName,
  googleResourceName,
  hasuraAdminSecret,
  hasuraGraphUrl,
} from '@chat/_libs/constants';
import insertTaskOne from '@chat/_libs/gql/insertTaskOne';
import { TaskType } from '@chat/_libs/types/TaskType';
import got from 'got';
import { MasterTask, TaskStatus } from './constants';
import { v4 as uuid } from 'uuid';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import {
  EventType,
  RecurrenceFrequencyType,
} from '@chat/_libs/types/EventType';
import {
  convertEventTitleToOpenAIVector,
  createGoogleEvent,
  createPreAndPostEventsFromEvent,
  createRRuleString,
  extrapolateDateFromJSONData,
  findAnEmptySlot,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateDateTime,
  generateJSONDataFromUserInput,
  getCalendarIntegrationByName,
  getGlobalCalendar,
  getRRuleByWeekDay,
  insertReminders,
  putDataInAllEventIndexInOpenSearch,
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
import { AddTaskType } from './types';
import PreferredTimeRangeType, {
  DayOfWeekValueType,
} from '@chat/_libs/types/PreferredTimeRangeType';

import { GoogleResType } from '@chat/_libs/types/GoogleResType';

import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
import OpenAI from 'openai';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import { createDayScheduleForTasks } from './day-schedule/api-helper';
import * as pkg from 'rrule';

import { interopDefault } from 'mlly';
const { RRule } = interopDefault(pkg);
import {
  generateWorkTimesForUser,
  getUserPreferences,
} from '@chat/_libs/skills/askCalendar/api-helper';
import requiredFields from './requiredFields';
import DayOfWeekType from '@chat/_libs/types/DayOfWeekType';

export const createDeadlineEventForTaskList = async (
  generatedId: string,
  userId: string,
  title: string,
  duration: number,
  taskId: string,
  taskListName: string,
  priority: number,
  timezone: string,
  startDate: string,
  softDeadline?: string,
  hardDeadline?: string,
  allDay?: boolean,
  reminders?: number[],
  recurObject?: RecurrenceRuleType,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  location?: string
): Promise<EventType> => {
  try {
    let calendarDoc: CalendarType = null;
    calendarDoc = await getGlobalCalendar(userId);

    const calIntegration = await getCalendarIntegrationByName(
      userId,
      googleCalendarName
    );

    if (calendarDoc?.id && calendarDoc?.resource === googleResourceName) {
      const colorId = calendarDoc?.colorId;
      const backgroundColor = calendarDoc?.backgroundColor;

      const startDateTime = dayjs(startDate).tz(timezone).format();
      const endDateTime = dayjs(startDate)
        .tz(timezone)
        .add(duration, 'minute')
        .format();

      const googleReminder: GoogleReminderType = {
        overrides: reminders?.map((r) => ({ method: 'email', minutes: r })),
        useDefault: false,
      };

      const recur = createRRuleString(
        recurObject?.frequency,
        recurObject?.interval,
        recurObject?.byWeekDay,
        recurObject?.occurrence,
        recurObject?.endDate,
        recurObject?.byMonthDay
      );

      const googleRes = await createGoogleEvent(
        userId,
        calendarDoc?.id,
        calIntegration?.clientType,
        generatedId,
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
        recur?.length > 0 ? recur : undefined,
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
      console.log(
        googleRes,
        ' googleRes inside createDeadlineEventForTaskList'
      );

      const dailyTaskList = taskListName === 'Daily';
      const weeklyTaskList = taskListName === 'Weekly';

      return {
        id: `${googleRes?.googleEventId}#${calendarDoc?.id}`,
        eventId: googleRes?.googleEventId,
        userId,
        dailyTaskList,
        weeklyTaskList,
        calendarId: calendarDoc?.id,
        title,
        duration,
        taskId,
        taskType: taskListName,
        priority,
        colorId,
        backgroundColor,
        startDate,
        endDate: endDateTime,
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
        originalStartDate: undefined,
        originalAllDay: false,
        summary: title,
        transparency,
        visibility,
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
    console.log(e, ' unable to create deadline event');
  }
};

export const insertTaskInDb = async (task: TaskType) => {
  try {
    const operationName = 'InsertTaskOne';
    const query = insertTaskOne;
    const variables = {
      task,
    };

    const res: { data: { insert_Task_one: TaskType } } = await got
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

    console.log(res, ' res inside insertTaskInDb');
    if (res?.data?.insert_Task_one) {
      return res?.data?.insert_Task_one;
    }
  } catch (e) {
    console.log(e, ' unable to get insertTaskInDb');
  }
};

export const createTaskAndEvent = async (
  userId: string,
  taskListName: string = MasterTask,
  text: string,
  timezone: string,
  startDate?: string,
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
    const newTask: TaskType = {
      id: uuid(),
      userId,
      eventId,
      type: taskListName,
      notes: text,
      important,
      status,
      priority: priority || 1,
      softDeadline,
      hardDeadline,
      duration,
      updatedAt: dayjs().format(),
      createdDate: dayjs().format(),
    };

    const deadline = softDeadline || hardDeadline;

    await insertTaskInDb(newTask);

    const event = await createDeadlineEventForTaskList(
      eventId,
      userId,
      text,
      duration || 30,
      newTask?.id,
      taskListName,
      priority || 1,
      timezone,
      startDate || dayjs(deadline).tz(timezone).subtract(30, 'm').format(),
      softDeadline,
      hardDeadline,
      allDay,
      reminders,
      recurObject,
      transparency,
      visibility,
      location
    );
    await upsertEvents([event]);

    return {
      task: newTask,
      event,
    };
  } catch (e) {
    console.log(e, ' unable to get insertTaskInDb');
  }
};

export const createTask = async (
  userId: string,
  taskListName: string = MasterTask,
  text: string,
  important?: boolean,
  softDeadline?: string,
  hardDeadline?: string,
  status?: TaskStatus,
  eventId?: string,
  duration?: number,
  priority?: number
) => {
  try {
    const newTask: TaskType = {
      id: uuid(),
      userId,
      eventId,
      type: taskListName,
      notes: text,
      important,
      status,
      priority: priority || 1,
      softDeadline,
      hardDeadline,
      duration,
      updatedAt: dayjs().format(),
      createdDate: dayjs().format(),
    };

    await insertTaskInDb(newTask);

    return newTask;
  } catch (e) {
    console.log(e, ' unable to get insertTaskInDb');
  }
};

export const createEventForTask = async (
  userId: string,
  taskListName: string = MasterTask,
  taskId: string,
  text: string,
  timezone: string,
  startDate?: string,
  softDeadline?: string,
  hardDeadline?: string,
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
    console.log(startDate, ' startDate inside createEventForTask');
    const event = await createDeadlineEventForTaskList(
      eventId,
      userId,
      text,
      duration || 30,
      taskId,
      taskListName,
      priority || 1,
      timezone,
      startDate,
      softDeadline,
      hardDeadline,
      allDay,
      reminders,
      recurObject,
      transparency,
      visibility,
      location
    );

    await upsertEvents([event]);

    return event;
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

export const getRruleFreq = (freq: RecurrenceFrequencyType) => {
  switch (freq) {
    case 'daily':
      return RRule.DAILY;
    case 'weekly':
      return RRule.WEEKLY;
    case 'monthly':
      return RRule.MONTHLY;
    case 'yearly':
      return RRule.YEARLY;
  }
};

type DayTimeWindowType = {
  dayWindowStartDate: string;
  dayWindowEndDate: string;
};

export const getDayjsUnitFromFrequency = (
  frequency: RecurrenceFrequencyType
) => {
  switch (frequency) {
    case 'daily':
      return 'd';
    case 'weekly':
      return 'w';
    case 'monthly':
      return 'm';
    case 'yearly':
      return 'y';
    default:
      return 'd';
  }
};

export enum Day {
  MO = 'MO',
  TU = 'TU',
  WE = 'WE',
  TH = 'TH',
  FR = 'FR',
  SA = 'SA',
  SU = 'SU',
}

export const generateDatesUsingRrule = async (
  startTime: string,
  frequency: RecurrenceFrequencyType,
  interval: number,
  until: string,
  timezone: string,
  userId: string,
  byWeekDay?: DayOfWeekType[],
  byMonthDay?: number[]
) => {
  try {
    const rruleObject: Partial<any> = {
      dtstart: dayjs(startTime).tz(timezone).toDate(),
      freq: getRruleFreq(frequency),
      interval,
      until: dayjs(until).tz(timezone).toDate(),
    };

    if (byWeekDay?.length > 0) {
      rruleObject.byweekday = byWeekDay?.map((w) => getRRuleByWeekDay(w));
    }

    if (byMonthDay?.length > 0) {
      rruleObject.bymonthday = byMonthDay;
    }

    const ruleStartDate = new RRule(rruleObject);

    const dayWindowStartDatesForRecurrence = ruleStartDate
      .all()
      ?.map((d) => dayjs.utc(d).format());

    if (dayWindowStartDatesForRecurrence?.length === 0) {
      console.log(
        dayWindowStartDatesForRecurrence?.length === 0,
        ' dayWindowStartDatesForRecurrence?.length === 0'
      );
      dayWindowStartDatesForRecurrence.push(
        dayjs(startTime).tz(timezone).format()
      );
    }

    const userPreferences = await getUserPreferences(userId);

    const workTimesObject = generateWorkTimesForUser(userPreferences, timezone);

    const timeWindows: DayTimeWindowType[] = [];

    console.log(
      dayWindowStartDatesForRecurrence,
      ' dayWindowStartDatesForRecurrence'
    );

    for (const dayWindowStartDate of dayWindowStartDatesForRecurrence) {
      const day = dayjs(dayWindowStartDate)
        .tz(timezone)
        .format('dddd')
        ?.toUpperCase();

      console.log(day, ' day');
      const workTimeObject = workTimesObject?.find((w) => w?.dayOfWeek === day);

      console.log(workTimeObject, ' workTimeObject');

      /**
             * startTime: dayjs(setISODay(dayjs().hour(startHour).minute(startMinute).tz(timezone, true).toDate(), i + 1)).tz(timezone).format('h:mm a') as time,
                endTime: dayjs(setISODay(dayjs().hour(endHour).minute(endMinute).tz(timezone, true).toDate(), i + 1)).tz(timezone).format('h:mm a') as time,
             */

      const startHour = dayjs(workTimeObject?.startTime, 'h:mm a')
        .tz(timezone, true)
        .hour();
      const startMinute = dayjs(workTimeObject?.startTime, 'h:mm a')
        .tz(timezone, true)
        .minute();

      const endHour = dayjs(workTimeObject?.endTime, 'h:mm a')
        .tz(timezone, true)
        .hour();
      const endMinute = dayjs(workTimeObject?.endTime, 'h:mm a')
        .tz(timezone, true)
        .minute();

      console.log(
        startHour,
        startMinute,
        endHour,
        endMinute,
        ' shartHour, startMinute, endHour, endMinute '
      );

      timeWindows.push({
        dayWindowStartDate: dayjs(dayWindowStartDate)
          .tz(timezone)
          .hour(startHour)
          .minute(startMinute)
          .format(),
        dayWindowEndDate: dayjs(dayWindowStartDate)
          .tz(timezone)
          .hour(endHour)
          .minute(endMinute)
          .format(),
      });

      console.log(
        dayjs(dayWindowStartDate)
          .tz(timezone)
          .hour(startHour)
          .minute(startMinute)
          .format(),
        '  dayWindowStartDate: dayjs(dayWindowStartDate).tz(timezone).hour(startHour).minute(startMinute).format()'
      );
      console.log(
        dayjs(dayWindowStartDate)
          .tz(timezone)
          .hour(endHour)
          .minute(endMinute)
          .format(),
        ' dayWindowEndDate: dayjs(dayWindowStartDate).tz(timezone).hour(endHour).minute(endMinute).format()'
      );
    }

    console.log(timeWindows, ' timeWindows');

    if (!(timeWindows?.length > 0)) {
      throw new Error(' timeWindows length is 0');
    }

    return timeWindows;
  } catch (e) {
    console.log(e, ' generate dates for meeting assists recurrence');
  }
};

export const finalStepAddTask = async (
  body: AddTaskType,
  timezone: string,
  userCurrentTime: string,
  response: any
) => {
  try {
    const eventsToUpsert: EventType[] = [];

    const deadlineType = body?.deadlineType || 'softDeadline';

    const defaultEndDate = dayjs(userCurrentTime, 'dddd, YYYY-MM-DDTHH:mm:ssZ')
      .tz(timezone)
      .hour(23)
      .minute(59)
      .format();

    const diffDays = dayjs(body?.dueDate).diff(dayjs(body?.startDate), 'd');

    if (body?.taskList?.length > 0 && diffDays > 1) {
      // 'h:mm a'

      const timeWindows = await generateDatesUsingRrule(
        body?.startDate,
        body?.recur?.frequency || 'daily',
        body?.recur?.interval || 1,
        body?.recur?.endDate || body?.dueDate || defaultEndDate,
        timezone,
        body?.userId,
        body?.recur?.byWeekDay,
        body?.recur?.byMonthDay
      );

      const tasks: TaskType[] = [];

      for (const taskObject of body?.taskList) {
        const task = await createTask(
          body?.userId,
          taskObject?.tasklistName || 'Master',
          taskObject?.task,
          undefined,
          undefined,
          undefined,
          getTaskStatus(taskObject?.status) || TaskStatus.TODO,
          undefined,
          undefined,
          body?.priority || 1
        );

        tasks.push(task);
      }

      for (const timeWindow of timeWindows) {
        const taskList: string[] = body?.taskList?.map(
          (tl) =>
            `${tl?.task}${tl?.duration > 0 ? `: ${tl?.duration} minutes` : ''}`
        );

        const daySchedule = await createDayScheduleForTasks(
          body?.userId,
          taskList,
          body?.timezone,
          timeWindow?.dayWindowStartDate,
          timeWindow?.dayWindowEndDate,
          userCurrentTime,
          body?.bufferTime,
          body?.startDate
        );

        for (const taskObject of body?.taskList) {
          const task = tasks?.find(
            (t) => taskObject?.task?.toLowerCase() === t?.notes?.toLowerCase()
          );
          const eventId = uuid();
          const taskFromSchedule = daySchedule?.find(
            (ds) => ds?.task?.toLowerCase() === taskObject?.task?.toLowerCase()
          );

          const duration = dayjs(taskFromSchedule?.end_time, 'h:mm a')
            .tz(timezone, true)
            .diff(
              dayjs(taskFromSchedule?.start_time, 'h:mm a').tz(timezone, true),
              'm'
            );

          const year = dayjs(timeWindow?.dayWindowStartDate)
            .tz(timezone)
            .year();
          const month = dayjs(timeWindow?.dayWindowStartDate)
            .tz(timezone)
            .month();
          const date = dayjs(timeWindow?.dayWindowStartDate)
            .tz(timezone)
            .date();

          console.log(
            year,
            month,
            date,
            duration,
            task,
            taskFromSchedule,
            ' year, month, date, duration, task, taskFromSchedule'
          );

          const event = await createEventForTask(
            body?.userId,
            taskObject?.tasklistName || 'Master',
            task?.id,
            taskObject?.task,
            timezone,
            dayjs(taskFromSchedule?.start_time, 'h:mm a')
              .tz(body?.timezone, true)
              .year(year)
              .month(month)
              .date(date)
              .format(),
            undefined,
            undefined,
            eventId,
            duration,
            body?.priority,
            body?.allDay,
            body?.reminders,
            undefined,
            body?.transparency,
            body?.visibility as VisibilityType,
            body?.location
          );

          const remindersToUpdateEventId: ReminderType[] = [];

          if (body?.reminders?.length > 0) {
            const newReminders: ReminderType[] = body?.reminders.map((r) => ({
              id: uuid(),
              userId: body?.userId,
              eventId: event?.id,
              timezone,
              minutes: r,
              useDefault: false,
              updatedAt: dayjs().format(),
              createdDate: dayjs().format(),
              deleted: false,
            }));

            remindersToUpdateEventId.push(...newReminders);
          }

          const newPreferredTimeRanges: PreferredTimeRangeType[] = [];

          for (const timepreference of body?.timePreferences) {
            if (timepreference.dayOfWeek?.length > 0) {
              for (const dayOfWeek of timepreference.dayOfWeek) {
                const newPreferredTimeRange: PreferredTimeRangeType = {
                  id: uuid(),
                  eventId: event?.id,
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
                eventId: event?.id,
                startTime: timepreference?.timeRange?.startTime,
                endTime: timepreference?.timeRange?.endTime,
                updatedAt: dayjs().format(),
                createdDate: dayjs().format(),
                userId: body?.userId,
              };

              newPreferredTimeRanges.push(newPreferredTimeRange);
            }
          }

          if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
            const calIntegration = await getCalendarIntegrationByName(
              body?.userId,
              googleCalendarName
            );

            if (!calIntegration?.clientType) {
              throw new Error(
                'no client type inside calendar integration inside create agenda'
              );
            }

            const returnValues = createPreAndPostEventsFromEvent(
              event,
              body?.bufferTime
            );

            if (returnValues?.afterEvent) {
              const googleResValue: GoogleResType = await createGoogleEvent(
                body?.userId,
                event?.calendarId,
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
                timezone,
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
                event?.calendarId,
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
                timezone,
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
            eventsToUpsert.push(event);
          }

          if (remindersToUpdateEventId?.length > 0) {
            await insertReminders(remindersToUpdateEventId);
          }

          if (newPreferredTimeRanges?.length > 0) {
            await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
          }

          const searchVector = await convertEventTitleToOpenAIVector(
            taskObject?.task
          );

          if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
            await putDataInTrainEventIndexInOpenSearch(
              eventId,
              searchVector,
              body?.userId
            );
          }

          await putDataInAllEventIndexInOpenSearch(
            event?.id,
            searchVector,
            body?.userId,
            event?.startDate,
            event?.endDate
          );
        }
      }
    } else {
      const eventId = uuid();
      const taskAndEvent = await createTaskAndEvent(
        body?.userId,
        MasterTask,
        body?.title,
        timezone,
        body?.startDate,
        undefined,
        deadlineType === 'softDeadline' ? body?.dueDate : undefined,
        (deadlineType === 'hardDeadline' ? body?.dueDate : undefined) ||
          (!deadlineType ? body?.dueDate : undefined),
        TaskStatus.TODO,
        eventId,
        body?.duration,
        body?.priority,
        body?.allDay,
        body?.reminders,
        body?.recur as any,
        body?.transparency,
        body?.visibility as VisibilityType,
        body?.location
      );

      const remindersToUpdateEventId: ReminderType[] = [];

      if (body?.reminders?.length > 0) {
        const newReminders: ReminderType[] = body?.reminders.map((r) => ({
          id: uuid(),
          userId: body?.userId,
          eventId: taskAndEvent?.event?.id,
          timezone,
          minutes: r,
          useDefault: false,
          updatedAt: dayjs().format(),
          createdDate: dayjs().format(),
          deleted: false,
        }));

        remindersToUpdateEventId.push(...newReminders);
      }

      const newPreferredTimeRanges: PreferredTimeRangeType[] = [];

      for (const timepreference of body?.timePreferences) {
        if (timepreference.dayOfWeek?.length > 0) {
          for (const dayOfWeek of timepreference.dayOfWeek) {
            const newPreferredTimeRange: PreferredTimeRangeType = {
              id: uuid(),
              eventId: taskAndEvent?.event?.id,
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
            eventId: taskAndEvent?.event?.id,
            startTime: timepreference?.timeRange?.startTime,
            endTime: timepreference?.timeRange?.endTime,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            userId: body?.userId,
          };

          newPreferredTimeRanges.push(newPreferredTimeRange);
        }
      }

      if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
        const calIntegration = await getCalendarIntegrationByName(
          body?.userId,
          googleCalendarName
        );

        if (!calIntegration?.clientType) {
          throw new Error(
            'no client type inside calendar integration inside create agenda'
          );
        }

        const returnValues = createPreAndPostEventsFromEvent(
          taskAndEvent.event,
          body?.bufferTime
        );

        if (returnValues?.afterEvent) {
          const googleResValue: GoogleResType = await createGoogleEvent(
            body?.userId,
            taskAndEvent?.event?.calendarId,
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
            timezone,
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
            taskAndEvent?.event?.calendarId,
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
            timezone,
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
        eventsToUpsert.push(taskAndEvent.event);
      }

      if (remindersToUpdateEventId?.length > 0) {
        await insertReminders(remindersToUpdateEventId);
      }

      if (newPreferredTimeRanges?.length > 0) {
        await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
      }

      const searchVector = await convertEventTitleToOpenAIVector(body?.title);

      if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
        await putDataInTrainEventIndexInOpenSearch(
          eventId,
          searchVector,
          body?.userId
        );
      }

      await putDataInAllEventIndexInOpenSearch(
        taskAndEvent?.event?.id,
        searchVector,
        body?.userId,
        taskAndEvent?.event?.startDate,
        taskAndEvent.event?.endDate
      );
    }

    console.log(eventsToUpsert?.length, ' eventsToUpsert?.length');

    await upsertEvents(eventsToUpsert);

    response.query = 'completed';
    response.data = 'processed request successfully';
    return response;
  } catch (e) {
    console.log(e, ' unable to final step add task');
  }
};

export const processAddTaskPending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string
): Promise<ResponseActionType> => {
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

    const response: any = {
      query: '',
      data: {},
      skill: 'addTask',
    };

    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
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

    console.log(taskStartDate, taskDueDate, ' taskStartDate, taskDueDate');

    if (dateJSONBody?.duration) {
      duration = dateJSONBody?.duration;
    } else if (dateJSONBody?.startTime && dateJSONBody?.endTime) {
      const startTimeObject = dayjs(dateJSONBody?.startTime, 'HH:mm');
      const endTimeObject = dayjs(dateJSONBody.endTime, 'HH:mm');

      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else if (dateJSONBody?.dueDate?.duration) {
      duration = dateJSONBody?.dueDate?.duration;
    } else if (jsonBody?.params?.startTime && jsonBody?.params?.endTime) {
      const startTimeObject = dayjs(jsonBody?.params?.startTime);
      const endTimeObject = dayjs(jsonBody?.params?.endTime);
      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else {
      duration = 30;
    }

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
          jsonBody?.params?.recurrence?.interval ||
          1,
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

    let startDate = taskStartDate;

    const body: AddTaskType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      method: dateJSONBody?.method as any,
      duration,
      description: jsonBody?.params?.description || jsonBody?.params?.notes,
      startDate: jsonBody?.params?.startTime || startDate,
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
    };

    if (body?.startDate && taskDueDate) {
      const diffDays = dayjs(taskDueDate).diff(body?.startDate, 'd');

      if (diffDays > 1) {
        startDate = body?.startDate;

        if (!(recurObject as RecurrenceRuleType)?.frequency) {
          (recurObject as RecurrenceRuleType).frequency = 'daily';
        }

        if (!(recurObject as RecurrenceRuleType)?.interval) {
          (recurObject as RecurrenceRuleType).interval = 1;
        }

        (recurObject as RecurrenceRuleType).endDate = taskDueDate;
      } else if (dayjs(taskDueDate).isAfter(dayjs(body?.startDate))) {
        startDate = taskDueDate;
      }
    }

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      body.recur = recurObject as any;
    }

    console.log(body, ' body');

    console.log(day, isoWeekday, ' day, isoWeekday,');

    // if (!day && !isoWeekday) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0])
    //     response.data = missingFields
    //     response.prevData = body

    // }

    console.log(hour, minute, startTime, ' hour, minute, startTime,');

    // if ((hour === null) && (minute === null) && !startTime) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1])
    //     response.data = missingFields
    //     response.prevData = body
    // }

    if (!body?.startDate) {
      if (body?.recur?.frequency) {
        body.startDate = dayjs().add(1, 'h').tz(timezone).format();
      } else if (body?.dueDate) {
        body.startDate = dayjs(body.dueDate)
          .tz(timezone)
          .subtract(body.duration, 'm')
          .format();
      } else {
        const windowStartDate = dayjs().tz(timezone).format();
        const windowEndDate = dayjs().tz(timezone).hour(23).minute(59).format();
        const availableSlot = await findAnEmptySlot(
          userId,
          timezone,
          windowStartDate,
          windowEndDate,
          body?.duration || 30
        );
        body.startDate = dayjs(availableSlot.startTime, 'h:mm a')
          .tz(timezone, true)
          .format();
      }
    }

    console.log(response, ' response');

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepAddTask(
      body,
      body?.timezone,
      currentTime,
      response
    );
    return response2;
  } catch (e) {
    console.log(e, ' unable to process add task');
  }
};

export const processAddTaskMissingFieldsReturned = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string,
  messageHistoryObject: SkillMessageHistoryType
): Promise<ResponseActionType> => {
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

    const response: any = {
      query: '',
      data: {},
      skill: 'addTask',
    };

    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
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

    if (dateJSONBody?.duration) {
      duration = dateJSONBody?.duration;
    } else if (dateJSONBody?.startTime && dateJSONBody?.endTime) {
      const startTimeObject = dayjs(dateJSONBody?.startTime, 'HH:mm');
      const endTimeObject = dayjs(dateJSONBody.endTime, 'HH:mm');

      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else if (dateJSONBody?.dueDate?.duration) {
      duration = dateJSONBody?.dueDate?.duration;
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
    } else {
      duration = 30;
    }

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

    let startDate = taskStartDate;

    const newBody: AddTaskType = {
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
        startDate,
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
    };

    if (newBody?.startDate && taskDueDate) {
      const diffHours = dayjs(taskDueDate).diff(newBody?.startDate, 'h');
      const diffDays = dayjs(newBody?.startDate).diff(newBody?.startDate, 'd');

      if (diffDays > 1) {
        startDate = newBody?.startDate;

        if (!(recurObject as RecurrenceRuleType)?.frequency) {
          (recurObject as RecurrenceRuleType).frequency = 'daily';
        }

        if (!(recurObject as RecurrenceRuleType)?.interval) {
          (recurObject as RecurrenceRuleType).interval = 1;
        }

        (recurObject as RecurrenceRuleType).endDate = taskDueDate;
      } else if (dayjs(taskDueDate).isAfter(dayjs(newBody?.startDate))) {
        startDate = taskDueDate;
      }
    }

    const prevBody: AddTaskType = {
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
      prevBody.dueDate = newBody.dueDate;
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

    if (!prevBody?.deadlineType) {
      prevBody.deadlineType = newBody?.deadlineType;
    }

    if (!(prevBody?.taskList?.length > 0)) {
      prevBody.taskList = newBody?.taskList;
    }

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      newBody.recur = recurObject as any;
    }

    if (!prevBody?.recur) {
      prevBody.recur = newBody?.recur;
    }

    if (!prevBody?.startDate) {
      if (prevBody?.recur?.frequency) {
        prevBody.startDate = dayjs().add(1, 'h').tz(timezone).format();
      } else if (prevBody?.dueDate) {
        prevBody.startDate = dayjs(prevBody.dueDate)
          .tz(timezone)
          .subtract(prevBody.duration, 'm')
          .format();
      } else {
        const windowStartDate = dayjs().tz(timezone).format();
        const windowEndDate = dayjs().tz(timezone).hour(23).minute(59).format();
        const availableSlot = await findAnEmptySlot(
          userId,
          timezone,
          windowStartDate,
          windowEndDate,
          prevBody?.duration || 30
        );
        prevBody.startDate = dayjs(availableSlot.startTime, 'h:mm a')
          .tz(timezone, true)
          .format();
      }
    }

    if (!prevBody?.startDate) {
      prevBody.startDate = newBody?.startDate;
    }

    console.log(day, isoWeekday, ' day, isoWeekday');

    // if (!prevBody?.startDate && !day && !isoWeekday) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0])
    //     response.data = missingFields
    //     response.prevData = prevBody

    // }

    console.log(hour, minute, startTime, ' hour, minute, startTime,');

    // if ((dayjs(prevBody?.startDate).hour() === 0)
    //     && (dayjs(prevBody?.startDate).minute() === 0)
    //     && (hour === null) && (minute === null) && !startTime) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1])
    //     response.data = missingFields
    //     response.prevData = prevBody
    // }

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepAddTask(
      prevBody,
      prevBody?.timezone,
      currentTime,
      response
    );
    return response2;
  } catch (e) {
    console.log(e, ' unable to process add task missing fields returned');
  }
};

export const addTaskControlCenter = async (
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

    const jsonBody = await generateJSONDataFromUserInput(
      userInput,
      userCurrentTime
    );
    const dateTime = await generateDateTime(
      userInput,
      userCurrentTime,
      timezone
    );
    let addTaskRes: ResponseActionType = {
      query: 'completed',
      data: '',
      skill: '',
      prevData: {},
      prevDataExtra: {},
    };

    switch (query) {
      case 'pending':
        addTaskRes = await processAddTaskPending(
          userId,
          timezone,
          jsonBody,
          dateTime,
          userCurrentTime
        );
        break;
      case 'missing_fields':
        addTaskRes = await processAddTaskMissingFieldsReturned(
          userId,
          timezone,
          jsonBody,
          dateTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (addTaskRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          addTaskRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (addTaskRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          addTaskRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = addTaskRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = addTaskRes?.prevData;
      messageHistoryObject.prevDataExtra = addTaskRes?.prevDataExtra;
    } else if (addTaskRes?.query === 'event_not_found') {
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
    console.log(e, ' unable to add task control center');
  }
};
