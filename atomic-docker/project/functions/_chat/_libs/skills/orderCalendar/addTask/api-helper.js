import { googleCalendarName, googleResourceName, hasuraAdminSecret, hasuraGraphUrl, } from '@chat/_libs/constants';
import insertTaskOne from '@chat/_libs/gql/insertTaskOne';
import got from 'got';
import { MasterTask, TaskStatus } from './constants';
import { v4 as uuid } from 'uuid';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { convertEventTitleToOpenAIVector, createGoogleEvent, createPreAndPostEventsFromEvent, createRRuleString, extrapolateDateFromJSONData, findAnEmptySlot, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, getCalendarIntegrationByName, getGlobalCalendar, getRRuleByWeekDay, insertReminders, putDataInAllEventIndexInOpenSearch, putDataInTrainEventIndexInOpenSearch, upsertEvents, } from '@chat/_libs/api-helper';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
import { createDayScheduleForTasks } from './day-schedule/api-helper';
import * as pkg from 'rrule';
import { interopDefault } from 'mlly';
const { RRule } = interopDefault(pkg);
import { generateWorkTimesForUser, getUserPreferences, } from '@chat/_libs/skills/askCalendar/api-helper';
export const createDeadlineEventForTaskList = async (generatedId, userId, title, duration, taskId, taskListName, priority, timezone, startDate, softDeadline, hardDeadline, allDay, reminders, recurObject, transparency, visibility, location) => {
    try {
        let calendarDoc = null;
        calendarDoc = await getGlobalCalendar(userId);
        const calIntegration = await getCalendarIntegrationByName(userId, googleCalendarName);
        if (calendarDoc?.id && calendarDoc?.resource === googleResourceName) {
            const colorId = calendarDoc?.colorId;
            const backgroundColor = calendarDoc?.backgroundColor;
            const startDateTime = dayjs(startDate).tz(timezone).format();
            const endDateTime = dayjs(startDate)
                .tz(timezone)
                .add(duration, 'minute')
                .format();
            const googleReminder = {
                overrides: reminders?.map((r) => ({ method: 'email', minutes: r })),
                useDefault: false,
            };
            const recur = createRRuleString(recurObject?.frequency, recurObject?.interval, recurObject?.byWeekDay, recurObject?.occurrence, recurObject?.endDate, recurObject?.byMonthDay);
            const googleRes = await createGoogleEvent(userId, calendarDoc?.id, calIntegration?.clientType, generatedId, endDateTime, startDateTime, 0, undefined, 'all', false, undefined, undefined, title, title, timezone, allDay && dayjs(startDate).tz(timezone).format('YYYY-MM-DD'), allDay &&
                dayjs(startDate).tz(timezone).add(duration, 'm').format('YYYY-MM-DD'), undefined, undefined, undefined, undefined, undefined, undefined, recur?.length > 0 ? recur : undefined, reminders?.length > 0 ? googleReminder : undefined, undefined, undefined, transparency, visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', location, undefined);
            console.log(googleRes, ' googleRes inside createDeadlineEventForTaskList');
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
    }
    catch (e) {
        console.log(e, ' unable to create deadline event');
    }
};
export const insertTaskInDb = async (task) => {
    try {
        const operationName = 'InsertTaskOne';
        const query = insertTaskOne;
        const variables = {
            task,
        };
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to get insertTaskInDb');
    }
};
export const createTaskAndEvent = async (userId, taskListName = MasterTask, text, timezone, startDate, important, softDeadline, hardDeadline, status, eventId, duration, priority, allDay, reminders, recurObject, transparency, visibility, location) => {
    try {
        const newTask = {
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
        const event = await createDeadlineEventForTaskList(eventId, userId, text, duration || 30, newTask?.id, taskListName, priority || 1, timezone, startDate || dayjs(deadline).tz(timezone).subtract(30, 'm').format(), softDeadline, hardDeadline, allDay, reminders, recurObject, transparency, visibility, location);
        await upsertEvents([event]);
        return {
            task: newTask,
            event,
        };
    }
    catch (e) {
        console.log(e, ' unable to get insertTaskInDb');
    }
};
export const createTask = async (userId, taskListName = MasterTask, text, important, softDeadline, hardDeadline, status, eventId, duration, priority) => {
    try {
        const newTask = {
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
    }
    catch (e) {
        console.log(e, ' unable to get insertTaskInDb');
    }
};
export const createEventForTask = async (userId, taskListName = MasterTask, taskId, text, timezone, startDate, softDeadline, hardDeadline, eventId, duration, priority, allDay, reminders, recurObject, transparency, visibility, location) => {
    try {
        console.log(startDate, ' startDate inside createEventForTask');
        const event = await createDeadlineEventForTaskList(eventId, userId, text, duration || 30, taskId, taskListName, priority || 1, timezone, startDate, softDeadline, hardDeadline, allDay, reminders, recurObject, transparency, visibility, location);
        await upsertEvents([event]);
        return event;
    }
    catch (e) {
        console.log(e, ' unable to get insertTaskInDb');
    }
};
export const getTaskStatus = (status) => {
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
export const getRruleFreq = (freq) => {
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
export const getDayjsUnitFromFrequency = (frequency) => {
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
export var Day;
(function (Day) {
    Day["MO"] = "MO";
    Day["TU"] = "TU";
    Day["WE"] = "WE";
    Day["TH"] = "TH";
    Day["FR"] = "FR";
    Day["SA"] = "SA";
    Day["SU"] = "SU";
})(Day || (Day = {}));
export const generateDatesUsingRrule = async (startTime, frequency, interval, until, timezone, userId, byWeekDay, byMonthDay) => {
    try {
        const rruleObject = {
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
            console.log(dayWindowStartDatesForRecurrence?.length === 0, ' dayWindowStartDatesForRecurrence?.length === 0');
            dayWindowStartDatesForRecurrence.push(dayjs(startTime).tz(timezone).format());
        }
        const userPreferences = await getUserPreferences(userId);
        const workTimesObject = generateWorkTimesForUser(userPreferences, timezone);
        const timeWindows = [];
        console.log(dayWindowStartDatesForRecurrence, ' dayWindowStartDatesForRecurrence');
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
            console.log(startHour, startMinute, endHour, endMinute, ' shartHour, startMinute, endHour, endMinute ');
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
            console.log(dayjs(dayWindowStartDate)
                .tz(timezone)
                .hour(startHour)
                .minute(startMinute)
                .format(), '  dayWindowStartDate: dayjs(dayWindowStartDate).tz(timezone).hour(startHour).minute(startMinute).format()');
            console.log(dayjs(dayWindowStartDate)
                .tz(timezone)
                .hour(endHour)
                .minute(endMinute)
                .format(), ' dayWindowEndDate: dayjs(dayWindowStartDate).tz(timezone).hour(endHour).minute(endMinute).format()');
        }
        console.log(timeWindows, ' timeWindows');
        if (!(timeWindows?.length > 0)) {
            throw new Error(' timeWindows length is 0');
        }
        return timeWindows;
    }
    catch (e) {
        console.log(e, ' generate dates for meeting assists recurrence');
    }
};
export const finalStepAddTask = async (body, timezone, userCurrentTime, response) => {
    try {
        const eventsToUpsert = [];
        const deadlineType = body?.deadlineType || 'softDeadline';
        const defaultEndDate = dayjs(userCurrentTime, 'dddd, YYYY-MM-DDTHH:mm:ssZ')
            .tz(timezone)
            .hour(23)
            .minute(59)
            .format();
        const diffDays = dayjs(body?.dueDate).diff(dayjs(body?.startDate), 'd');
        if (body?.taskList?.length > 0 && diffDays > 1) {
            // 'h:mm a'
            const timeWindows = await generateDatesUsingRrule(body?.startDate, body?.recur?.frequency || 'daily', body?.recur?.interval || 1, body?.recur?.endDate || body?.dueDate || defaultEndDate, timezone, body?.userId, body?.recur?.byWeekDay, body?.recur?.byMonthDay);
            const tasks = [];
            for (const taskObject of body?.taskList) {
                const task = await createTask(body?.userId, taskObject?.tasklistName || 'Master', taskObject?.task, undefined, undefined, undefined, getTaskStatus(taskObject?.status) || TaskStatus.TODO, undefined, undefined, body?.priority || 1);
                tasks.push(task);
            }
            for (const timeWindow of timeWindows) {
                const taskList = body?.taskList?.map((tl) => `${tl?.task}${tl?.duration > 0 ? `: ${tl?.duration} minutes` : ''}`);
                const daySchedule = await createDayScheduleForTasks(body?.userId, taskList, body?.timezone, timeWindow?.dayWindowStartDate, timeWindow?.dayWindowEndDate, userCurrentTime, body?.bufferTime, body?.startDate);
                for (const taskObject of body?.taskList) {
                    const task = tasks?.find((t) => taskObject?.task?.toLowerCase() === t?.notes?.toLowerCase());
                    const eventId = uuid();
                    const taskFromSchedule = daySchedule?.find((ds) => ds?.task?.toLowerCase() === taskObject?.task?.toLowerCase());
                    const duration = dayjs(taskFromSchedule?.end_time, 'h:mm a')
                        .tz(timezone, true)
                        .diff(dayjs(taskFromSchedule?.start_time, 'h:mm a').tz(timezone, true), 'm');
                    const year = dayjs(timeWindow?.dayWindowStartDate)
                        .tz(timezone)
                        .year();
                    const month = dayjs(timeWindow?.dayWindowStartDate)
                        .tz(timezone)
                        .month();
                    const date = dayjs(timeWindow?.dayWindowStartDate)
                        .tz(timezone)
                        .date();
                    console.log(year, month, date, duration, task, taskFromSchedule, ' year, month, date, duration, task, taskFromSchedule');
                    const event = await createEventForTask(body?.userId, taskObject?.tasklistName || 'Master', task?.id, taskObject?.task, timezone, dayjs(taskFromSchedule?.start_time, 'h:mm a')
                        .tz(body?.timezone, true)
                        .year(year)
                        .month(month)
                        .date(date)
                        .format(), undefined, undefined, eventId, duration, body?.priority, body?.allDay, body?.reminders, undefined, body?.transparency, body?.visibility, body?.location);
                    const remindersToUpdateEventId = [];
                    if (body?.reminders?.length > 0) {
                        const newReminders = body?.reminders.map((r) => ({
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
                    const newPreferredTimeRanges = [];
                    for (const timepreference of body?.timePreferences) {
                        if (timepreference.dayOfWeek?.length > 0) {
                            for (const dayOfWeek of timepreference.dayOfWeek) {
                                const newPreferredTimeRange = {
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
                        }
                        else {
                            const newPreferredTimeRange = {
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
                        const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
                        if (!calIntegration?.clientType) {
                            throw new Error('no client type inside calendar integration inside create agenda');
                        }
                        const returnValues = createPreAndPostEventsFromEvent(event, body?.bufferTime);
                        if (returnValues?.afterEvent) {
                            const googleResValue = await createGoogleEvent(body?.userId, event?.calendarId, calIntegration?.clientType, returnValues?.afterEvent?.id, returnValues?.afterEvent?.endDate, returnValues?.afterEvent?.startDate, 0, undefined, returnValues?.afterEvent?.sendUpdates, returnValues?.afterEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.afterEvent?.title, returnValues?.afterEvent?.notes, timezone, undefined, undefined, undefined, returnValues?.afterEvent?.guestsCanInviteOthers, returnValues?.afterEvent?.guestsCanModify, returnValues?.afterEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.afterEvent?.transparency, returnValues?.afterEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                            returnValues.afterEvent.id = googleResValue.id;
                            returnValues.afterEvent.eventId = googleResValue.googleEventId;
                            returnValues.newEvent.postEventId = returnValues.afterEvent.id;
                        }
                        if (returnValues?.beforeEvent) {
                            const googleResValue = await createGoogleEvent(body?.userId, event?.calendarId, calIntegration?.clientType, returnValues?.beforeEvent?.id, returnValues?.beforeEvent?.endDate, returnValues?.beforeEvent?.startDate, 0, undefined, returnValues?.beforeEvent?.sendUpdates, returnValues?.beforeEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.beforeEvent?.title, returnValues?.beforeEvent?.notes, timezone, undefined, undefined, undefined, returnValues?.beforeEvent?.guestsCanInviteOthers, returnValues?.beforeEvent?.guestsCanModify, returnValues?.beforeEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.beforeEvent?.transparency, returnValues?.beforeEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                            returnValues.beforeEvent.id = googleResValue.id;
                            returnValues.beforeEvent.eventId = googleResValue.googleEventId;
                            returnValues.newEvent.preEventId = returnValues.afterEvent.id;
                        }
                        eventsToUpsert.push(...[
                            returnValues.newEvent,
                            returnValues?.afterEvent,
                            returnValues?.beforeEvent,
                        ]?.filter((e) => !!e));
                    }
                    else {
                        eventsToUpsert.push(event);
                    }
                    if (remindersToUpdateEventId?.length > 0) {
                        await insertReminders(remindersToUpdateEventId);
                    }
                    if (newPreferredTimeRanges?.length > 0) {
                        await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
                    }
                    const searchVector = await convertEventTitleToOpenAIVector(taskObject?.task);
                    if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
                        await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, body?.userId);
                    }
                    await putDataInAllEventIndexInOpenSearch(event?.id, searchVector, body?.userId, event?.startDate, event?.endDate);
                }
            }
        }
        else {
            const eventId = uuid();
            const taskAndEvent = await createTaskAndEvent(body?.userId, MasterTask, body?.title, timezone, body?.startDate, undefined, deadlineType === 'softDeadline' ? body?.dueDate : undefined, (deadlineType === 'hardDeadline' ? body?.dueDate : undefined) ||
                (!deadlineType ? body?.dueDate : undefined), TaskStatus.TODO, eventId, body?.duration, body?.priority, body?.allDay, body?.reminders, body?.recur, body?.transparency, body?.visibility, body?.location);
            const remindersToUpdateEventId = [];
            if (body?.reminders?.length > 0) {
                const newReminders = body?.reminders.map((r) => ({
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
            const newPreferredTimeRanges = [];
            for (const timepreference of body?.timePreferences) {
                if (timepreference.dayOfWeek?.length > 0) {
                    for (const dayOfWeek of timepreference.dayOfWeek) {
                        const newPreferredTimeRange = {
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
                }
                else {
                    const newPreferredTimeRange = {
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
                const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
                if (!calIntegration?.clientType) {
                    throw new Error('no client type inside calendar integration inside create agenda');
                }
                const returnValues = createPreAndPostEventsFromEvent(taskAndEvent.event, body?.bufferTime);
                if (returnValues?.afterEvent) {
                    const googleResValue = await createGoogleEvent(body?.userId, taskAndEvent?.event?.calendarId, calIntegration?.clientType, returnValues?.afterEvent?.id, returnValues?.afterEvent?.endDate, returnValues?.afterEvent?.startDate, 0, undefined, returnValues?.afterEvent?.sendUpdates, returnValues?.afterEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.afterEvent?.title, returnValues?.afterEvent?.notes, timezone, undefined, undefined, undefined, returnValues?.afterEvent?.guestsCanInviteOthers, returnValues?.afterEvent?.guestsCanModify, returnValues?.afterEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.afterEvent?.transparency, returnValues?.afterEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                    returnValues.afterEvent.id = googleResValue.id;
                    returnValues.afterEvent.eventId = googleResValue.googleEventId;
                    returnValues.newEvent.postEventId = returnValues.afterEvent.id;
                }
                if (returnValues?.beforeEvent) {
                    const googleResValue = await createGoogleEvent(body?.userId, taskAndEvent?.event?.calendarId, calIntegration?.clientType, returnValues?.beforeEvent?.id, returnValues?.beforeEvent?.endDate, returnValues?.beforeEvent?.startDate, 0, undefined, returnValues?.beforeEvent?.sendUpdates, returnValues?.beforeEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.beforeEvent?.title, returnValues?.beforeEvent?.notes, timezone, undefined, undefined, undefined, returnValues?.beforeEvent?.guestsCanInviteOthers, returnValues?.beforeEvent?.guestsCanModify, returnValues?.beforeEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.beforeEvent?.transparency, returnValues?.beforeEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                    returnValues.beforeEvent.id = googleResValue.id;
                    returnValues.beforeEvent.eventId = googleResValue.googleEventId;
                    returnValues.newEvent.preEventId = returnValues.afterEvent.id;
                }
                eventsToUpsert.push(...[
                    returnValues.newEvent,
                    returnValues?.afterEvent,
                    returnValues?.beforeEvent,
                ]?.filter((e) => !!e));
            }
            else {
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
                await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, body?.userId);
            }
            await putDataInAllEventIndexInOpenSearch(taskAndEvent?.event?.id, searchVector, body?.userId, taskAndEvent?.event?.startDate, taskAndEvent.event?.endDate);
        }
        console.log(eventsToUpsert?.length, ' eventsToUpsert?.length');
        await upsertEvents(eventsToUpsert);
        response.query = 'completed';
        response.data = 'processed request successfully';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step add task');
    }
};
export const processAddTaskPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
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
        const response = {
            query: '',
            data: {},
            skill: 'addTask',
        };
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const taskStartDate = extrapolateDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow);
        const taskDueDate = extrapolateDateFromJSONData(currentTime, timezone, yearDue, monthDue, dayDue, isoWeekdayDue, hourDue, minuteDue, startTimeDue, dateJSONBody?.dueDate?.relativeTimeChangeFromNow, dateJSONBody?.dueDate?.relativeTimeFromNow);
        console.log(taskStartDate, taskDueDate, ' taskStartDate, taskDueDate');
        if (dateJSONBody?.duration) {
            duration = dateJSONBody?.duration;
        }
        else if (dateJSONBody?.startTime && dateJSONBody?.endTime) {
            const startTimeObject = dayjs(dateJSONBody?.startTime, 'HH:mm');
            const endTimeObject = dayjs(dateJSONBody.endTime, 'HH:mm');
            const minutes = endTimeObject.diff(startTimeObject, 'm');
            if (minutes > 0) {
                duration = minutes;
            }
        }
        else if (dateJSONBody?.dueDate?.duration) {
            duration = dateJSONBody?.dueDate?.duration;
        }
        else if (jsonBody?.params?.startTime && jsonBody?.params?.endTime) {
            const startTimeObject = dayjs(jsonBody?.params?.startTime);
            const endTimeObject = dayjs(jsonBody?.params?.endTime);
            const minutes = endTimeObject.diff(startTimeObject, 'm');
            if (minutes > 0) {
                duration = minutes;
            }
        }
        else {
            duration = 30;
        }
        let recurObject = {};
        if (dateJSONBody?.recur?.frequency) {
            const recurEndDate = extrapolateDateFromJSONData(currentTime, timezone, dateJSONBody?.recur?.endDate?.year, dateJSONBody?.recur?.endDate?.month, dateJSONBody?.recur?.endDate?.day, dateJSONBody?.recur?.endDate?.isoWeekday, dateJSONBody?.recur?.endDate?.hour, dateJSONBody?.recur?.endDate?.minute, dateJSONBody?.recur?.endDate?.startTime, dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow, dateJSONBody?.recur?.endDate?.relativeTimeFromNow);
            recurObject = {
                frequency: dateJSONBody?.recur?.frequency ||
                    jsonBody?.params?.recurrence?.frequency,
                interval: dateJSONBody?.recur?.interval ||
                    jsonBody?.params?.recurrence?.interval ||
                    1,
            };
            if (dateJSONBody?.recur?.byWeekDay) {
                recurObject.byWeekDay =
                    dateJSONBody?.recur?.byWeekDay;
            }
            if (dateJSONBody?.recur?.byMonthDay) {
                recurObject.byMonthDay =
                    dateJSONBody?.recur?.byMonthDay;
            }
            if (dateJSONBody?.recur?.occurrence) {
                recurObject.occurrence =
                    dateJSONBody?.recur?.occurrence;
            }
            if (recurEndDate || jsonBody?.params?.recurrence?.endDate) {
                recurObject.endDate =
                    recurEndDate || jsonBody?.params?.recurrence?.endDate;
            }
        }
        let startDate = taskStartDate;
        const body = {
            userId,
            timezone,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description || jsonBody?.params?.notes,
            startDate: jsonBody?.params?.startTime || startDate,
            dueDate: taskDueDate || recurObject?.endDate,
            bufferTime: jsonBody?.params?.bufferTime,
            reminders: jsonBody?.params?.alarms || [],
            priority: jsonBody?.params?.priority || 1,
            timePreferences: dateJSONBody?.timePreferences || [],
            location: jsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility,
            isBreak: jsonBody?.params?.isBreak,
            allDay: dateJSONBody?.allDay,
            deadlineType: jsonBody?.params?.deadlineType,
            taskList: jsonBody?.params?.taskList?.map((tl) => ({
                ...tl,
                tasklistName: tl?.tasklistName?.toLowerCase(),
            })) || [],
        };
        if (body?.startDate && taskDueDate) {
            const diffDays = dayjs(taskDueDate).diff(body?.startDate, 'd');
            if (diffDays > 1) {
                startDate = body?.startDate;
                if (!recurObject?.frequency) {
                    recurObject.frequency = 'daily';
                }
                if (!recurObject?.interval) {
                    recurObject.interval = 1;
                }
                recurObject.endDate = taskDueDate;
            }
            else if (dayjs(taskDueDate).isAfter(dayjs(body?.startDate))) {
                startDate = taskDueDate;
            }
        }
        if (recurObject?.frequency) {
            body.recur = recurObject;
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
            }
            else if (body?.dueDate) {
                body.startDate = dayjs(body.dueDate)
                    .tz(timezone)
                    .subtract(body.duration, 'm')
                    .format();
            }
            else {
                const windowStartDate = dayjs().tz(timezone).format();
                const windowEndDate = dayjs().tz(timezone).hour(23).minute(59).format();
                const availableSlot = await findAnEmptySlot(userId, timezone, windowStartDate, windowEndDate, body?.duration || 30);
                body.startDate = dayjs(availableSlot.startTime, 'h:mm a')
                    .tz(timezone, true)
                    .format();
            }
        }
        console.log(response, ' response');
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepAddTask(body, body?.timezone, currentTime, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process add task');
    }
};
export const processAddTaskMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
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
        const response = {
            query: '',
            data: {},
            skill: 'addTask',
        };
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const taskStartDate = extrapolateDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeFromNow);
        const taskDueDate = extrapolateDateFromJSONData(currentTime, timezone, yearDue, monthDue, dayDue, isoWeekdayDue, hourDue, minuteDue, startTimeDue, dateJSONBody?.dueDate?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.dueDate
                ?.relativeTimeChangeFromNow, dateJSONBody?.dueDate?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.relativeTimeFromNow);
        if (dateJSONBody?.duration) {
            duration = dateJSONBody?.duration;
        }
        else if (dateJSONBody?.startTime && dateJSONBody?.endTime) {
            const startTimeObject = dayjs(dateJSONBody?.startTime, 'HH:mm');
            const endTimeObject = dayjs(dateJSONBody.endTime, 'HH:mm');
            const minutes = endTimeObject.diff(startTimeObject, 'm');
            if (minutes > 0) {
                duration = minutes;
            }
        }
        else if (dateJSONBody?.dueDate?.duration) {
            duration = dateJSONBody?.dueDate?.duration;
        }
        else if ((jsonBody?.params?.startTime ||
            messageHistoryObject?.prevJsonBody?.params?.startTime) &&
            (jsonBody?.params?.endTime ||
                messageHistoryObject?.prevJsonBody?.params?.endTime)) {
            const startTimeObject = dayjs(jsonBody?.params?.startTime ||
                messageHistoryObject?.prevJsonBody?.params?.startTime);
            const endTimeObject = dayjs(jsonBody?.params?.endTime ||
                messageHistoryObject?.prevJsonBody?.params?.endTime);
            const minutes = endTimeObject.diff(startTimeObject, 'm');
            if (minutes > 0) {
                duration = minutes;
            }
        }
        else {
            duration = 30;
        }
        let recurObject = {};
        if (dateJSONBody?.recur?.frequency ||
            messageHistoryObject?.prevDateJsonBody?.recur?.frequency) {
            const recurEndDate = extrapolateDateFromJSONData(currentTime, timezone, dateJSONBody?.recur?.endDate?.year ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.year, dateJSONBody?.recur?.endDate?.month ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.month, dateJSONBody?.recur?.endDate?.day ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.day, dateJSONBody?.recur?.endDate?.isoWeekday ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.isoWeekday, dateJSONBody?.recur?.endDate?.hour ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.hour, dateJSONBody?.recur?.endDate?.minute ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.minute, dateJSONBody?.recur?.endDate?.startTime ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.startTime, dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate
                    ?.relativeTimeChangeFromNow, dateJSONBody?.recur?.endDate?.relativeTimeFromNow ||
                messageHistoryObject?.prevDateJsonBody?.recur?.endDate
                    ?.relativeTimeFromNow);
            recurObject = {
                frequency: dateJSONBody?.recur?.frequency ||
                    messageHistoryObject?.prevDateJsonBody?.recur?.frequency ||
                    messageHistoryObject?.prevJsonBody?.params?.recurrence?.frequency ||
                    jsonBody?.params?.recurrence?.frequency,
                interval: dateJSONBody?.recur?.interval ||
                    messageHistoryObject?.prevDateJsonBody?.recur?.interval ||
                    messageHistoryObject?.prevJsonBody?.params?.recurrence?.interval ||
                    jsonBody?.params?.recurrence?.interval,
            };
            if (dateJSONBody?.recur?.byWeekDay ||
                messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay) {
                recurObject.byWeekDay =
                    dateJSONBody?.recur?.byWeekDay ||
                        messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay;
            }
            if (dateJSONBody?.recur?.byMonthDay ||
                messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay) {
                recurObject.byMonthDay =
                    dateJSONBody?.recur?.byMonthDay ||
                        messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay;
            }
            if (dateJSONBody?.recur?.occurrence ||
                messageHistoryObject?.prevDateJsonBody?.recur?.occurrence) {
                recurObject.occurrence =
                    dateJSONBody?.recur?.occurrence ||
                        messageHistoryObject?.prevDateJsonBody?.recur?.occurrence;
            }
            if (recurEndDate ||
                messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
                jsonBody?.params?.recurrence?.endDate) {
                recurObject.endDate =
                    recurEndDate ||
                        messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
                        jsonBody?.params?.recurrence?.endDate;
            }
        }
        let startDate = taskStartDate;
        const newBody = {
            userId,
            timezone,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task ||
                messageHistoryObject?.prevJsonBody?.params?.title ||
                messageHistoryObject?.prevJsonBody?.params?.summary ||
                messageHistoryObject?.prevJsonBody?.params?.description ||
                messageHistoryObject?.prevJsonBody?.params?.taskList?.[0]?.task,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description ||
                jsonBody?.params?.notes ||
                messageHistoryObject?.prevJsonBody?.params?.description ||
                messageHistoryObject?.prevJsonBody?.params?.notes,
            startDate: jsonBody?.params?.startTime ||
                messageHistoryObject?.prevJsonBody?.params?.startTime ||
                startDate,
            dueDate: taskDueDate || recurObject?.endDate,
            bufferTime: jsonBody?.params?.bufferTime ||
                messageHistoryObject?.prevJsonBody?.params?.bufferTime,
            reminders: jsonBody?.params?.alarms ||
                messageHistoryObject?.prevJsonBody?.params?.alarms ||
                [],
            priority: jsonBody?.params?.priority ||
                messageHistoryObject?.prevJsonBody?.params?.priority ||
                1,
            timePreferences: dateJSONBody?.timePreferences ||
                messageHistoryObject?.prevDateJsonBody?.timePreferences ||
                [],
            location: jsonBody?.params?.location ||
                messageHistoryObject?.prevJsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency ||
                messageHistoryObject?.prevJsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility ||
                messageHistoryObject?.prevJsonBody?.params?.visibility,
            isBreak: jsonBody?.params?.isBreak ||
                messageHistoryObject?.prevJsonBody?.params?.isBreak,
            allDay: dateJSONBody?.allDay || messageHistoryObject?.prevDateJsonBody?.allDay,
            deadlineType: jsonBody?.params?.deadlineType ||
                messageHistoryObject?.prevJsonBody?.params?.deadlineType,
            taskList: jsonBody?.params?.taskList?.map((tl) => ({
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
                if (!recurObject?.frequency) {
                    recurObject.frequency = 'daily';
                }
                if (!recurObject?.interval) {
                    recurObject.interval = 1;
                }
                recurObject.endDate = taskDueDate;
            }
            else if (dayjs(taskDueDate).isAfter(dayjs(newBody?.startDate))) {
                startDate = taskDueDate;
            }
        }
        const prevBody = {
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
        if (recurObject?.frequency) {
            newBody.recur = recurObject;
        }
        if (!prevBody?.recur) {
            prevBody.recur = newBody?.recur;
        }
        if (!prevBody?.startDate) {
            if (prevBody?.recur?.frequency) {
                prevBody.startDate = dayjs().add(1, 'h').tz(timezone).format();
            }
            else if (prevBody?.dueDate) {
                prevBody.startDate = dayjs(prevBody.dueDate)
                    .tz(timezone)
                    .subtract(prevBody.duration, 'm')
                    .format();
            }
            else {
                const windowStartDate = dayjs().tz(timezone).format();
                const windowEndDate = dayjs().tz(timezone).hour(23).minute(59).format();
                const availableSlot = await findAnEmptySlot(userId, timezone, windowStartDate, windowEndDate, prevBody?.duration || 30);
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
        const response2 = await finalStepAddTask(prevBody, prevBody?.timezone, currentTime, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process add task missing fields returned');
    }
};
export const addTaskControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        const jsonBody = await generateJSONDataFromUserInput(userInput, userCurrentTime);
        const dateTime = await generateDateTime(userInput, userCurrentTime, timezone);
        let addTaskRes = {
            query: 'completed',
            data: '',
            skill: '',
            prevData: {},
            prevDataExtra: {},
        };
        switch (query) {
            case 'pending':
                addTaskRes = await processAddTaskPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
                break;
            case 'missing_fields':
                addTaskRes = await processAddTaskMissingFieldsReturned(userId, timezone, jsonBody, dateTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (addTaskRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, addTaskRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (addTaskRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, addTaskRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = addTaskRes?.data;
            messageHistoryObject.prevData = addTaskRes?.prevData;
            messageHistoryObject.prevDataExtra = addTaskRes?.prevDataExtra;
        }
        else if (addTaskRes?.query === 'event_not_found') {
            const assistantMessage = {
                role: 'assistant',
                content: "Oops... I couldn't find the event. Sorry :(",
            };
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'event_not_found';
            messageHistoryObject.required = null;
        }
        return messageHistoryObject;
    }
    catch (e) {
        console.log(e, ' unable to add task control center');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLGtCQUFrQixFQUNsQixrQkFBa0IsRUFDbEIsaUJBQWlCLEVBQ2pCLGNBQWMsR0FDZixNQUFNLHVCQUF1QixDQUFDO0FBQy9CLE9BQU8sYUFBYSxNQUFNLCtCQUErQixDQUFDO0FBRTFELE9BQU8sR0FBRyxNQUFNLEtBQUssQ0FBQztBQUN0QixPQUFPLEVBQUUsVUFBVSxFQUFFLFVBQVUsRUFBRSxNQUFNLGFBQWEsQ0FBQztBQUNyRCxPQUFPLEVBQUUsRUFBRSxJQUFJLElBQUksRUFBRSxNQUFNLE1BQU0sQ0FBQztBQUNsQyxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFLeEQsT0FBTyxFQUNMLCtCQUErQixFQUMvQixpQkFBaUIsRUFDakIsK0JBQStCLEVBQy9CLGlCQUFpQixFQUNqQiwyQkFBMkIsRUFDM0IsZUFBZSxFQUNmLG1EQUFtRCxFQUNuRCxxREFBcUQsRUFDckQsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3Qiw0QkFBNEIsRUFDNUIsaUJBQWlCLEVBQ2pCLGlCQUFpQixFQUNqQixlQUFlLEVBQ2Ysa0NBQWtDLEVBQ2xDLG9DQUFvQyxFQUNwQyxZQUFZLEdBQ2IsTUFBTSx3QkFBd0IsQ0FBQztBQW9CaEMsT0FBTyxFQUFFLGFBQWEsRUFBRSxNQUFNLHVDQUF1QyxDQUFDO0FBQ3RFLE9BQU8sRUFBRSxpQ0FBaUMsRUFBRSxNQUFNLHdDQUF3QyxDQUFDO0FBTTNGLE9BQU8sRUFBRSx5QkFBeUIsRUFBRSxNQUFNLDJCQUEyQixDQUFDO0FBQ3RFLE9BQU8sS0FBSyxHQUFHLE1BQU0sT0FBTyxDQUFDO0FBRTdCLE9BQU8sRUFBRSxjQUFjLEVBQUUsTUFBTSxNQUFNLENBQUM7QUFDdEMsTUFBTSxFQUFFLEtBQUssRUFBRSxHQUFHLGNBQWMsQ0FBQyxHQUFHLENBQUMs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e1xuICBnb29nbGVDYWxlbmRhck5hbWUsXG4gIGdvb2dsZVJlc291cmNlTmFtZSxcbiAgaGFzdXJhQWRtaW5TZWNyZXQsXG4gIGhhc3VyYUdyYXBoVXJsLFxufSBmcm9tICdAY2hhdC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IGluc2VydFRhc2tPbmUgZnJvbSAnQGNoYXQvX2xpYnMvZ3FsL2luc2VydFRhc2tPbmUnO1xuaW1wb3J0IHsgVGFza1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9UYXNrVHlwZSc7XG5pbXBvcnQgZ290IGZyb20gJ2dvdCc7XG5pbXBvcnQgeyBNYXN0ZXJUYXNrLCBUYXNrU3RhdHVzIH0gZnJvbSAnLi9jb25zdGFudHMnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9kYXRlLXV0aWxzJztcbmltcG9ydCB7XG4gIEV2ZW50VHlwZSxcbiAgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0V2ZW50VHlwZSc7XG5pbXBvcnQge1xuICBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yLFxuICBjcmVhdGVHb29nbGVFdmVudCxcbiAgY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21FdmVudCxcbiAgY3JlYXRlUlJ1bGVTdHJpbmcsXG4gIGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YSxcbiAgZmluZEFuRW1wdHlTbG90LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnksXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzLFxuICBnZW5lcmF0ZURhdGVUaW1lLFxuICBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dCxcbiAgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZSxcbiAgZ2V0R2xvYmFsQ2FsZW5kYXIsXG4gIGdldFJSdWxlQnlXZWVrRGF5LFxuICBpbnNlcnRSZW1pbmRlcnMsXG4gIHB1dERhdGFJbkFsbEV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsXG4gIHB1dERhdGFJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaCxcbiAgdXBzZXJ0RXZlbnRzLFxufSBmcm9tICdAY2hhdC9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCB7IENhbGVuZGFyVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0NhbGVuZGFyVHlwZSc7XG5pbXBvcnQge1xuICBSZWN1cnJlbmNlUnVsZVR5cGUsXG4gIFRyYW5zcGFyZW5jeVR5cGUsXG4gIFZpc2liaWxpdHlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IHsgUmVtaW5kZXJUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvR29vZ2xlVHlwZXMnO1xuaW1wb3J0IHsgR29vZ2xlUmVtaW5kZXJUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvR29vZ2xlUmVtaW5kZXJUeXBlJztcbmltcG9ydCBEYXRlVGltZUpTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL0RhdGVUaW1lSlNPTkpTT05UeXBlJztcbmltcG9ydCBVc2VySW5wdXRUb0pTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1VzZXJJbnB1dFRvSlNPTlR5cGUnO1xuaW1wb3J0IFJlcXVpcmVkRmllbGRzVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXF1aXJlZEZpZWxkc1R5cGUnO1xuaW1wb3J0IHsgQWRkVGFza1R5cGUgfSBmcm9tICcuL3R5cGVzJztcbmltcG9ydCBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlLCB7XG4gIERheU9mV2Vla1ZhbHVlVHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUHJlZmVycmVkVGltZVJhbmdlVHlwZSc7XG5cbmltcG9ydCB7IEdvb2dsZVJlc1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Hb29nbGVSZXNUeXBlJztcblxuaW1wb3J0IFJlc3BvbnNlQWN0aW9uVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXNwb25zZUFjdGlvblR5cGUnO1xuaW1wb3J0IHsgRGF5T2ZXZWVrRW51bSB9IGZyb20gJy4uL3Jlc29sdmVDb25mbGljdGluZ0V2ZW50cy9jb25zdGFudHMnO1xuaW1wb3J0IHsgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50IH0gZnJvbSAnLi4vcmVzb2x2ZUNvbmZsaWN0aW5nRXZlbnRzL2FwaS1oZWxwZXInO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHtcbiAgQXNzaXN0YW50TWVzc2FnZVR5cGUsXG4gIFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9NZXNzYWdpbmcvTWVzc2FnaW5nVHlwZXMnO1xuaW1wb3J0IHsgY3JlYXRlRGF5U2NoZWR1bGVGb3JUYXNrcyB9IGZyb20gJy4vZGF5LXNjaGVkdWxlL2FwaS1oZWxwZXInO1xuaW1wb3J0ICogYXMgcGtnIGZyb20gJ3JydWxlJztcblxuaW1wb3J0IHsgaW50ZXJvcERlZmF1bHQgfSBmcm9tICdtbGx5JztcbmNvbnN0IHsgUlJ1bGUgfSA9IGludGVyb3BEZWZhdWx0KHBrZyk7XG5pbXBvcnQge1xuICBnZW5lcmF0ZVdvcmtUaW1lc0ZvclVzZXIsXG4gIGdldFVzZXJQcmVmZXJlbmNlcyxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvc2tpbGxzL2Fza0NhbGVuZGFyL2FwaS1oZWxwZXInO1xuaW1wb3J0IHJlcXVpcmVkRmllbGRzIGZyb20gJy4vcmVxdWlyZWRGaWVsZHMnO1xuaW1wb3J0IERheU9mV2Vla1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvRGF5T2ZXZWVrVHlwZSc7XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVEZWFkbGluZUV2ZW50Rm9yVGFza0xpc3QgPSBhc3luYyAoXG4gIGdlbmVyYXRlZElkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aXRsZTogc3RyaW5nLFxuICBkdXJhdGlvbjogbnVtYmVyLFxuICB0YXNrSWQ6IHN0cmluZyxcbiAgdGFza0xpc3ROYW1lOiBzdHJpbmcsXG4gIHByaW9yaXR5OiBudW1iZXIsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICBzb2Z0RGVhZGxpbmU/OiBzdHJpbmcsXG4gIGhhcmREZWFkbGluZT86IHN0cmluZyxcbiAgYWxsRGF5PzogYm9vbGVhbixcbiAgcmVtaW5kZXJzPzogbnVtYmVyW10sXG4gIHJlY3VyT2JqZWN0PzogUmVjdXJyZW5jZVJ1bGVUeXBlLFxuICB0cmFuc3BhcmVuY3k/OiBUcmFuc3BhcmVuY3lUeXBlLFxuICB2aXNpYmlsaXR5PzogVmlzaWJpbGl0eVR5cGUsXG4gIGxvY2F0aW9uPzogc3RyaW5nXG4pOiBQcm9taXNlPEV2ZW50VHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGxldCBjYWxlbmRhckRvYzogQ2FsZW5kYXJUeXBlID0gbnVsbDtcbiAgICBjYWxlbmRhckRvYyA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKHVzZXJJZCk7XG5cbiAgICBjb25zdCBjYWxJbnRlZ3JhdGlvbiA9IGF3YWl0IGdldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUoXG4gICAgICB1c2VySWQsXG4gICAgICBnb29nbGVDYWxlbmRhck5hbWVcbiAgICApO1xuXG4gICAgaWYgKGNhbGVuZGFyRG9jPy5pZCAmJiBjYWxlbmRhckRvYz8ucmVzb3VyY2UgPT09IGdvb2dsZVJlc291cmNlTmFtZSkge1xuICAgICAgY29uc3QgY29sb3JJZCA9IGNhbGVuZGFyRG9jPy5jb2xvcklkO1xuICAgICAgY29uc3QgYmFja2dyb3VuZENvbG9yID0gY2FsZW5kYXJEb2M/LmJhY2tncm91bmRDb2xvcjtcblxuICAgICAgY29uc3Qgc3RhcnREYXRlVGltZSA9IGRheWpzKHN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgpO1xuICAgICAgY29uc3QgZW5kRGF0ZVRpbWUgPSBkYXlqcyhzdGFydERhdGUpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmFkZChkdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoKTtcblxuICAgICAgY29uc3QgZ29vZ2xlUmVtaW5kZXI6IEdvb2dsZVJlbWluZGVyVHlwZSA9IHtcbiAgICAgICAgb3ZlcnJpZGVzOiByZW1pbmRlcnM/Lm1hcCgocikgPT4gKHsgbWV0aG9kOiAnZW1haWwnLCBtaW51dGVzOiByIH0pKSxcbiAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgICB9O1xuXG4gICAgICBjb25zdCByZWN1ciA9IGNyZWF0ZVJSdWxlU3RyaW5nKFxuICAgICAgICByZWN1ck9iamVjdD8uZnJlcXVlbmN5LFxuICAgICAgICByZWN1ck9iamVjdD8uaW50ZXJ2YWwsXG4gICAgICAgIHJlY3VyT2JqZWN0Py5ieVdlZWtEYXksXG4gICAgICAgIHJlY3VyT2JqZWN0Py5vY2N1cnJlbmNlLFxuICAgICAgICByZWN1ck9iamVjdD8uZW5kRGF0ZSxcbiAgICAgICAgcmVjdXJPYmplY3Q/LmJ5TW9udGhEYXlcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IGdvb2dsZVJlcyA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNhbGVuZGFyRG9jPy5pZCxcbiAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgIGdlbmVyYXRlZElkLFxuICAgICAgICBlbmREYXRlVGltZSxcbiAgICAgICAgc3RhcnREYXRlVGltZSxcbiAgICAgICAgMCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAnYWxsJyxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB0aXRsZSxcbiAgICAgICAgdGl0bGUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBhbGxEYXkgJiYgZGF5anMoc3RhcnREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIGFsbERheSAmJlxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmFkZChkdXJhdGlvbiwgJ20nKS5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgcmVjdXI/Lmxlbmd0aCA+IDAgPyByZWN1ciA6IHVuZGVmaW5lZCxcbiAgICAgICAgcmVtaW5kZXJzPy5sZW5ndGggPiAwID8gZ29vZ2xlUmVtaW5kZXIgOiB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICAgIHZpc2liaWxpdHksXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgbG9jYXRpb24sXG4gICAgICAgIHVuZGVmaW5lZFxuICAgICAgKTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBnb29nbGVSZXMsXG4gICAgICAgICcgZ29vZ2xlUmVzIGluc2lkZSBjcmVhdGVEZWFkbGluZUV2ZW50Rm9yVGFza0xpc3QnXG4gICAgICApO1xuXG4gICAgICBjb25zdCBkYWlseVRhc2tMaXN0ID0gdGFza0xpc3ROYW1lID09PSAnRGFpbHknO1xuICAgICAgY29uc3Qgd2Vla2x5VGFza0xpc3QgPSB0YXNrTGlzdE5hbWUgPT09ICdXZWVrbHknO1xuXG4gICAgICByZXR1cm4ge1xuICAgICAgICBpZDogYCR7Z29vZ2xlUmVzPy5nb29nbGVFdmVudElkfSMke2NhbGVuZGFyRG9jPy5pZH1gLFxuICAgICAgICBldmVudElkOiBnb29nbGVSZXM/Lmdvb2dsZUV2ZW50SWQsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgZGFpbHlUYXNrTGlzdCxcbiAgICAgICAgd2Vla2x5VGFza0xpc3QsXG4gICAgICAgIGNhbGVuZGFySWQ6IGNhbGVuZGFyRG9jPy5pZCxcbiAgICAgICAgdGl0bGUsXG4gICAgICAgIGR1cmF0aW9uLFxuICAgICAgICB0YXNrSWQsXG4gICAgICAgIHRhc2tUeXBlOiB0YXNrTGlzdE5hbWUsXG4gICAgICAgIHByaW9yaXR5LFxuICAgICAgICBjb2xvcklkLFxuICAgICAgICBiYWNrZ3JvdW5kQ29sb3IsXG4gICAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgICAgZW5kRGF0ZTogZW5kRGF0ZVRpbWUsXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgdGltZXpvbmU6IGRheWpzLnR6Lmd1ZXNzKCksXG4gICAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgICBtb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgICBhbnlvbmVDYW5BZGRTZWxmOiBmYWxzZSxcbiAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBmYWxzZSxcbiAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IGZhbHNlLFxuICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICAgIHN1bW1hcnk6IHRpdGxlLFxuICAgICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICAgIHZpc2liaWxpdHksXG4gICAgICAgIGlzQnJlYWs6IGZhbHNlLFxuICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHk6IGZhbHNlLFxuICAgICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsOiB0cnVlLFxuICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrOiB0cnVlLFxuICAgICAgICBzb2Z0RGVhZGxpbmUsXG4gICAgICAgIGhhcmREZWFkbGluZSxcbiAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb246IHRydWUsXG4gICAgICAgIG1ldGhvZDogJ3VwZGF0ZScsXG4gICAgICAgIG5vdGVzOiB0aXRsZSxcbiAgICAgIH07XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gY3JlYXRlIGRlYWRsaW5lIGV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBpbnNlcnRUYXNrSW5EYiA9IGFzeW5jICh0YXNrOiBUYXNrVHlwZSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0VGFza09uZSc7XG4gICAgY29uc3QgcXVlcnkgPSBpbnNlcnRUYXNrT25lO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHRhc2ssXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IGluc2VydF9UYXNrX29uZTogVGFza1R5cGUgfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGluc2VydFRhc2tJbkRiJyk7XG4gICAgaWYgKHJlcz8uZGF0YT8uaW5zZXJ0X1Rhc2tfb25lKSB7XG4gICAgICByZXR1cm4gcmVzPy5kYXRhPy5pbnNlcnRfVGFza19vbmU7XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGluc2VydFRhc2tJbkRiJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVUYXNrQW5kRXZlbnQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0YXNrTGlzdE5hbWU6IHN0cmluZyA9IE1hc3RlclRhc2ssXG4gIHRleHQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgc3RhcnREYXRlPzogc3RyaW5nLFxuICBpbXBvcnRhbnQ/OiBib29sZWFuLFxuICBzb2Z0RGVhZGxpbmU/OiBzdHJpbmcsXG4gIGhhcmREZWFkbGluZT86IHN0cmluZyxcbiAgc3RhdHVzPzogVGFza1N0YXR1cyxcbiAgZXZlbnRJZD86IHN0cmluZyxcbiAgZHVyYXRpb24/OiBudW1iZXIsXG4gIHByaW9yaXR5PzogbnVtYmVyLFxuICBhbGxEYXk/OiBib29sZWFuLFxuICByZW1pbmRlcnM/OiBudW1iZXJbXSxcbiAgcmVjdXJPYmplY3Q/OiBSZWN1cnJlbmNlUnVsZVR5cGUsXG4gIHRyYW5zcGFyZW5jeT86IFRyYW5zcGFyZW5jeVR5cGUsXG4gIHZpc2liaWxpdHk/OiBWaXNpYmlsaXR5VHlwZSxcbiAgbG9jYXRpb24/OiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG5ld1Rhc2s6IFRhc2tUeXBlID0ge1xuICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGV2ZW50SWQsXG4gICAgICB0eXBlOiB0YXNrTGlzdE5hbWUsXG4gICAgICBub3RlczogdGV4dCxcbiAgICAgIGltcG9ydGFudCxcbiAgICAgIHN0YXR1cyxcbiAgICAgIHByaW9yaXR5OiBwcmlvcml0eSB8fCAxLFxuICAgICAgc29mdERlYWRsaW5lLFxuICAgICAgaGFyZERlYWRsaW5lLFxuICAgICAgZHVyYXRpb24sXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICB9O1xuXG4gICAgY29uc3QgZGVhZGxpbmUgPSBzb2Z0RGVhZGxpbmUgfHwgaGFyZERlYWRsaW5lO1xuXG4gICAgYXdhaXQgaW5zZXJ0VGFza0luRGIobmV3VGFzayk7XG5cbiAgICBjb25zdCBldmVudCA9IGF3YWl0IGNyZWF0ZURlYWRsaW5lRXZlbnRGb3JUYXNrTGlzdChcbiAgICAgIGV2ZW50SWQsXG4gICAgICB1c2VySWQsXG4gICAgICB0ZXh0LFxuICAgICAgZHVyYXRpb24gfHwgMzAsXG4gICAgICBuZXdUYXNrPy5pZCxcbiAgICAgIHRhc2tMaXN0TmFtZSxcbiAgICAgIHByaW9yaXR5IHx8IDEsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHN0YXJ0RGF0ZSB8fCBkYXlqcyhkZWFkbGluZSkudHoodGltZXpvbmUpLnN1YnRyYWN0KDMwLCAnbScpLmZvcm1hdCgpLFxuICAgICAgc29mdERlYWRsaW5lLFxuICAgICAgaGFyZERlYWRsaW5lLFxuICAgICAgYWxsRGF5LFxuICAgICAgcmVtaW5kZXJzLFxuICAgICAgcmVjdXJPYmplY3QsXG4gICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5LFxuICAgICAgbG9jYXRpb25cbiAgICApO1xuICAgIGF3YWl0IHVwc2VydEV2ZW50cyhbZXZlbnRdKTtcblxuICAgIHJldHVybiB7XG4gICAgICB0YXNrOiBuZXdUYXNrLFxuICAgICAgZXZlbnQsXG4gICAgfTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBpbnNlcnRUYXNrSW5EYicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlVGFzayA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRhc2tMaXN0TmFtZTogc3RyaW5nID0gTWFzdGVyVGFzayxcbiAgdGV4dDogc3RyaW5nLFxuICBpbXBvcnRhbnQ/OiBib29sZWFuLFxuICBzb2Z0RGVhZGxpbmU/OiBzdHJpbmcsXG4gIGhhcmREZWFkbGluZT86IHN0cmluZyxcbiAgc3RhdHVzPzogVGFza1N0YXR1cyxcbiAgZXZlbnRJZD86IHN0cmluZyxcbiAgZHVyYXRpb24/OiBudW1iZXIsXG4gIHByaW9yaXR5PzogbnVtYmVyXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBuZXdUYXNrOiBUYXNrVHlwZSA9IHtcbiAgICAgIGlkOiB1dWlkKCksXG4gICAgICB1c2VySWQsXG4gICAgICBldmVudElkLFxuICAgICAgdHlwZTogdGFza0xpc3ROYW1lLFxuICAgICAgbm90ZXM6IHRleHQsXG4gICAgICBpbXBvcnRhbnQsXG4gICAgICBzdGF0dXMsXG4gICAgICBwcmlvcml0eTogcHJpb3JpdHkgfHwgMSxcbiAgICAgIHNvZnREZWFkbGluZSxcbiAgICAgIGhhcmREZWFkbGluZSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgfTtcblxuICAgIGF3YWl0IGluc2VydFRhc2tJbkRiKG5ld1Rhc2spO1xuXG4gICAgcmV0dXJuIG5ld1Rhc2s7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgaW5zZXJ0VGFza0luRGInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZUV2ZW50Rm9yVGFzayA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRhc2tMaXN0TmFtZTogc3RyaW5nID0gTWFzdGVyVGFzayxcbiAgdGFza0lkOiBzdHJpbmcsXG4gIHRleHQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgc3RhcnREYXRlPzogc3RyaW5nLFxuICBzb2Z0RGVhZGxpbmU/OiBzdHJpbmcsXG4gIGhhcmREZWFkbGluZT86IHN0cmluZyxcbiAgZXZlbnRJZD86IHN0cmluZyxcbiAgZHVyYXRpb24/OiBudW1iZXIsXG4gIHByaW9yaXR5PzogbnVtYmVyLFxuICBhbGxEYXk/OiBib29sZWFuLFxuICByZW1pbmRlcnM/OiBudW1iZXJbXSxcbiAgcmVjdXJPYmplY3Q/OiBSZWN1cnJlbmNlUnVsZVR5cGUsXG4gIHRyYW5zcGFyZW5jeT86IFRyYW5zcGFyZW5jeVR5cGUsXG4gIHZpc2liaWxpdHk/OiBWaXNpYmlsaXR5VHlwZSxcbiAgbG9jYXRpb24/OiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKHN0YXJ0RGF0ZSwgJyBzdGFydERhdGUgaW5zaWRlIGNyZWF0ZUV2ZW50Rm9yVGFzaycpO1xuICAgIGNvbnN0IGV2ZW50ID0gYXdhaXQgY3JlYXRlRGVhZGxpbmVFdmVudEZvclRhc2tMaXN0KFxuICAgICAgZXZlbnRJZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRleHQsXG4gICAgICBkdXJhdGlvbiB8fCAzMCxcbiAgICAgIHRhc2tJZCxcbiAgICAgIHRhc2tMaXN0TmFtZSxcbiAgICAgIHByaW9yaXR5IHx8IDEsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIHNvZnREZWFkbGluZSxcbiAgICAgIGhhcmREZWFkbGluZSxcbiAgICAgIGFsbERheSxcbiAgICAgIHJlbWluZGVycyxcbiAgICAgIHJlY3VyT2JqZWN0LFxuICAgICAgdHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eSxcbiAgICAgIGxvY2F0aW9uXG4gICAgKTtcblxuICAgIGF3YWl0IHVwc2VydEV2ZW50cyhbZXZlbnRdKTtcblxuICAgIHJldHVybiBldmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBpbnNlcnRUYXNrSW5EYicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0VGFza1N0YXR1cyA9IChzdGF0dXM6ICd0b2RvJyB8ICdkb2luZycgfCAnZG9uZScpID0+IHtcbiAgaWYgKCFzdGF0dXMpIHtcbiAgICByZXR1cm47XG4gIH1cblxuICBzd2l0Y2ggKHN0YXR1cykge1xuICAgIGNhc2UgJ3RvZG8nOlxuICAgICAgcmV0dXJuIFRhc2tTdGF0dXMuVE9ETztcbiAgICBjYXNlICdkb2luZyc6XG4gICAgICByZXR1cm4gVGFza1N0YXR1cy5ET0lORztcbiAgICBjYXNlICdkb25lJzpcbiAgICAgIHJldHVybiBUYXNrU3RhdHVzLkRPTkU7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRScnVsZUZyZXEgPSAoZnJlcTogUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUpID0+IHtcbiAgc3dpdGNoIChmcmVxKSB7XG4gICAgY2FzZSAnZGFpbHknOlxuICAgICAgcmV0dXJuIFJSdWxlLkRBSUxZO1xuICAgIGNhc2UgJ3dlZWtseSc6XG4gICAgICByZXR1cm4gUlJ1bGUuV0VFS0xZO1xuICAgIGNhc2UgJ21vbnRobHknOlxuICAgICAgcmV0dXJuIFJSdWxlLk1PTlRITFk7XG4gICAgY2FzZSAneWVhcmx5JzpcbiAgICAgIHJldHVybiBSUnVsZS5ZRUFSTFk7XG4gIH1cbn07XG5cbnR5cGUgRGF5VGltZVdpbmRvd1R5cGUgPSB7XG4gIGRheVdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nO1xuICBkYXlXaW5kb3dFbmREYXRlOiBzdHJpbmc7XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0RGF5anNVbml0RnJvbUZyZXF1ZW5jeSA9IChcbiAgZnJlcXVlbmN5OiBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZVxuKSA9PiB7XG4gIHN3aXRjaCAoZnJlcXVlbmN5KSB7XG4gICAgY2FzZSAnZGFpbHknOlxuICAgICAgcmV0dXJuICdkJztcbiAgICBjYXNlICd3ZWVrbHknOlxuICAgICAgcmV0dXJuICd3JztcbiAgICBjYXNlICdtb250aGx5JzpcbiAgICAgIHJldHVybiAnbSc7XG4gICAgY2FzZSAneWVhcmx5JzpcbiAgICAgIHJldHVybiAneSc7XG4gICAgZGVmYXVsdDpcbiAgICAgIHJldHVybiAnZCc7XG4gIH1cbn07XG5cbmV4cG9ydCBlbnVtIERheSB7XG4gIE1PID0gJ01PJyxcbiAgVFUgPSAnVFUnLFxuICBXRSA9ICdXRScsXG4gIFRIID0gJ1RIJyxcbiAgRlIgPSAnRlInLFxuICBTQSA9ICdTQScsXG4gIFNVID0gJ1NVJyxcbn1cblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlRGF0ZXNVc2luZ1JydWxlID0gYXN5bmMgKFxuICBzdGFydFRpbWU6IHN0cmluZyxcbiAgZnJlcXVlbmN5OiBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSxcbiAgaW50ZXJ2YWw6IG51bWJlcixcbiAgdW50aWw6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGJ5V2Vla0RheT86IERheU9mV2Vla1R5cGVbXSxcbiAgYnlNb250aERheT86IG51bWJlcltdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBycnVsZU9iamVjdDogUGFydGlhbDxhbnk+ID0ge1xuICAgICAgZHRzdGFydDogZGF5anMoc3RhcnRUaW1lKS50eih0aW1lem9uZSkudG9EYXRlKCksXG4gICAgICBmcmVxOiBnZXRScnVsZUZyZXEoZnJlcXVlbmN5KSxcbiAgICAgIGludGVydmFsLFxuICAgICAgdW50aWw6IGRheWpzKHVudGlsKS50eih0aW1lem9uZSkudG9EYXRlKCksXG4gICAgfTtcblxuICAgIGlmIChieVdlZWtEYXk/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHJydWxlT2JqZWN0LmJ5d2Vla2RheSA9IGJ5V2Vla0RheT8ubWFwKCh3KSA9PiBnZXRSUnVsZUJ5V2Vla0RheSh3KSk7XG4gICAgfVxuXG4gICAgaWYgKGJ5TW9udGhEYXk/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHJydWxlT2JqZWN0LmJ5bW9udGhkYXkgPSBieU1vbnRoRGF5O1xuICAgIH1cblxuICAgIGNvbnN0IHJ1bGVTdGFydERhdGUgPSBuZXcgUlJ1bGUocnJ1bGVPYmplY3QpO1xuXG4gICAgY29uc3QgZGF5V2luZG93U3RhcnREYXRlc0ZvclJlY3VycmVuY2UgPSBydWxlU3RhcnREYXRlXG4gICAgICAuYWxsKClcbiAgICAgID8ubWFwKChkKSA9PiBkYXlqcy51dGMoZCkuZm9ybWF0KCkpO1xuXG4gICAgaWYgKGRheVdpbmRvd1N0YXJ0RGF0ZXNGb3JSZWN1cnJlbmNlPy5sZW5ndGggPT09IDApIHtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBkYXlXaW5kb3dTdGFydERhdGVzRm9yUmVjdXJyZW5jZT8ubGVuZ3RoID09PSAwLFxuICAgICAgICAnIGRheVdpbmRvd1N0YXJ0RGF0ZXNGb3JSZWN1cnJlbmNlPy5sZW5ndGggPT09IDAnXG4gICAgICApO1xuICAgICAgZGF5V2luZG93U3RhcnREYXRlc0ZvclJlY3VycmVuY2UucHVzaChcbiAgICAgICAgZGF5anMoc3RhcnRUaW1lKS50eih0aW1lem9uZSkuZm9ybWF0KClcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgdXNlclByZWZlcmVuY2VzID0gYXdhaXQgZ2V0VXNlclByZWZlcmVuY2VzKHVzZXJJZCk7XG5cbiAgICBjb25zdCB3b3JrVGltZXNPYmplY3QgPSBnZW5lcmF0ZVdvcmtUaW1lc0ZvclVzZXIodXNlclByZWZlcmVuY2VzLCB0aW1lem9uZSk7XG5cbiAgICBjb25zdCB0aW1lV2luZG93czogRGF5VGltZVdpbmRvd1R5cGVbXSA9IFtdO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBkYXlXaW5kb3dTdGFydERhdGVzRm9yUmVjdXJyZW5jZSxcbiAgICAgICcgZGF5V2luZG93U3RhcnREYXRlc0ZvclJlY3VycmVuY2UnXG4gICAgKTtcblxuICAgIGZvciAoY29uc3QgZGF5V2luZG93U3RhcnREYXRlIG9mIGRheVdpbmRvd1N0YXJ0RGF0ZXNGb3JSZWN1cnJlbmNlKSB7XG4gICAgICBjb25zdCBkYXkgPSBkYXlqcyhkYXlXaW5kb3dTdGFydERhdGUpXG4gICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgnZGRkZCcpXG4gICAgICAgID8udG9VcHBlckNhc2UoKTtcblxuICAgICAgY29uc29sZS5sb2coZGF5LCAnIGRheScpO1xuICAgICAgY29uc3Qgd29ya1RpbWVPYmplY3QgPSB3b3JrVGltZXNPYmplY3Q/LmZpbmQoKHcpID0+IHc/LmRheU9mV2VlayA9PT0gZGF5KTtcblxuICAgICAgY29uc29sZS5sb2cod29ya1RpbWVPYmplY3QsICcgd29ya1RpbWVPYmplY3QnKTtcblxuICAgICAgLyoqXG4gICAgICAgICAgICAgKiBzdGFydFRpbWU6IGRheWpzKHNldElTT0RheShkYXlqcygpLmhvdXIoc3RhcnRIb3VyKS5taW51dGUoc3RhcnRNaW51dGUpLnR6KHRpbWV6b25lLCB0cnVlKS50b0RhdGUoKSwgaSArIDEpKS50eih0aW1lem9uZSkuZm9ybWF0KCdoOm1tIGEnKSBhcyB0aW1lLFxuICAgICAgICAgICAgICAgIGVuZFRpbWU6IGRheWpzKHNldElTT0RheShkYXlqcygpLmhvdXIoZW5kSG91cikubWludXRlKGVuZE1pbnV0ZSkudHoodGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpLCBpICsgMSkpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ2g6bW0gYScpIGFzIHRpbWUsXG4gICAgICAgICAgICAgKi9cblxuICAgICAgY29uc3Qgc3RhcnRIb3VyID0gZGF5anMod29ya1RpbWVPYmplY3Q/LnN0YXJ0VGltZSwgJ2g6bW0gYScpXG4gICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmhvdXIoKTtcbiAgICAgIGNvbnN0IHN0YXJ0TWludXRlID0gZGF5anMod29ya1RpbWVPYmplY3Q/LnN0YXJ0VGltZSwgJ2g6bW0gYScpXG4gICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLm1pbnV0ZSgpO1xuXG4gICAgICBjb25zdCBlbmRIb3VyID0gZGF5anMod29ya1RpbWVPYmplY3Q/LmVuZFRpbWUsICdoOm1tIGEnKVxuICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgIC5ob3VyKCk7XG4gICAgICBjb25zdCBlbmRNaW51dGUgPSBkYXlqcyh3b3JrVGltZU9iamVjdD8uZW5kVGltZSwgJ2g6bW0gYScpXG4gICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLm1pbnV0ZSgpO1xuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgc3RhcnRIb3VyLFxuICAgICAgICBzdGFydE1pbnV0ZSxcbiAgICAgICAgZW5kSG91cixcbiAgICAgICAgZW5kTWludXRlLFxuICAgICAgICAnIHNoYXJ0SG91ciwgc3RhcnRNaW51dGUsIGVuZEhvdXIsIGVuZE1pbnV0ZSAnXG4gICAgICApO1xuXG4gICAgICB0aW1lV2luZG93cy5wdXNoKHtcbiAgICAgICAgZGF5V2luZG93U3RhcnREYXRlOiBkYXlqcyhkYXlXaW5kb3dTdGFydERhdGUpXG4gICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91cilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZGF5V2luZG93RW5kRGF0ZTogZGF5anMoZGF5V2luZG93U3RhcnREYXRlKVxuICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAuaG91cihlbmRIb3VyKVxuICAgICAgICAgIC5taW51dGUoZW5kTWludXRlKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgZGF5anMoZGF5V2luZG93U3RhcnREYXRlKVxuICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXIpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZSlcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICcgIGRheVdpbmRvd1N0YXJ0RGF0ZTogZGF5anMoZGF5V2luZG93U3RhcnREYXRlKS50eih0aW1lem9uZSkuaG91cihzdGFydEhvdXIpLm1pbnV0ZShzdGFydE1pbnV0ZSkuZm9ybWF0KCknXG4gICAgICApO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGRheWpzKGRheVdpbmRvd1N0YXJ0RGF0ZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoZW5kSG91cilcbiAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZSlcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgICcgZGF5V2luZG93RW5kRGF0ZTogZGF5anMoZGF5V2luZG93U3RhcnREYXRlKS50eih0aW1lem9uZSkuaG91cihlbmRIb3VyKS5taW51dGUoZW5kTWludXRlKS5mb3JtYXQoKSdcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2codGltZVdpbmRvd3MsICcgdGltZVdpbmRvd3MnKTtcblxuICAgIGlmICghKHRpbWVXaW5kb3dzPy5sZW5ndGggPiAwKSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCcgdGltZVdpbmRvd3MgbGVuZ3RoIGlzIDAnKTtcbiAgICB9XG5cbiAgICByZXR1cm4gdGltZVdpbmRvd3M7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGdlbmVyYXRlIGRhdGVzIGZvciBtZWV0aW5nIGFzc2lzdHMgcmVjdXJyZW5jZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZmluYWxTdGVwQWRkVGFzayA9IGFzeW5jIChcbiAgYm9keTogQWRkVGFza1R5cGUsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuICByZXNwb25zZTogYW55XG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBldmVudHNUb1Vwc2VydDogRXZlbnRUeXBlW10gPSBbXTtcblxuICAgIGNvbnN0IGRlYWRsaW5lVHlwZSA9IGJvZHk/LmRlYWRsaW5lVHlwZSB8fCAnc29mdERlYWRsaW5lJztcblxuICAgIGNvbnN0IGRlZmF1bHRFbmREYXRlID0gZGF5anModXNlckN1cnJlbnRUaW1lLCAnZGRkZCwgWVlZWS1NTS1ERFRISDptbTpzc1onKVxuICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgLmhvdXIoMjMpXG4gICAgICAubWludXRlKDU5KVxuICAgICAgLmZvcm1hdCgpO1xuXG4gICAgY29uc3QgZGlmZkRheXMgPSBkYXlqcyhib2R5Py5kdWVEYXRlKS5kaWZmKGRheWpzKGJvZHk/LnN0YXJ0RGF0ZSksICdkJyk7XG5cbiAgICBpZiAoYm9keT8udGFza0xpc3Q/Lmxlbmd0aCA+IDAgJiYgZGlmZkRheXMgPiAxKSB7XG4gICAgICAvLyAnaDptbSBhJ1xuXG4gICAgICBjb25zdCB0aW1lV2luZG93cyA9IGF3YWl0IGdlbmVyYXRlRGF0ZXNVc2luZ1JydWxlKFxuICAgICAgICBib2R5Py5zdGFydERhdGUsXG4gICAgICAgIGJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHwgJ2RhaWx5JyxcbiAgICAgICAgYm9keT8ucmVjdXI/LmludGVydmFsIHx8IDEsXG4gICAgICAgIGJvZHk/LnJlY3VyPy5lbmREYXRlIHx8IGJvZHk/LmR1ZURhdGUgfHwgZGVmYXVsdEVuZERhdGUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgIGJvZHk/LnJlY3VyPy5ieVdlZWtEYXksXG4gICAgICAgIGJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5XG4gICAgICApO1xuXG4gICAgICBjb25zdCB0YXNrczogVGFza1R5cGVbXSA9IFtdO1xuXG4gICAgICBmb3IgKGNvbnN0IHRhc2tPYmplY3Qgb2YgYm9keT8udGFza0xpc3QpIHtcbiAgICAgICAgY29uc3QgdGFzayA9IGF3YWl0IGNyZWF0ZVRhc2soXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIHRhc2tPYmplY3Q/LnRhc2tsaXN0TmFtZSB8fCAnTWFzdGVyJyxcbiAgICAgICAgICB0YXNrT2JqZWN0Py50YXNrLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIGdldFRhc2tTdGF0dXModGFza09iamVjdD8uc3RhdHVzKSB8fCBUYXNrU3RhdHVzLlRPRE8sXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICBib2R5Py5wcmlvcml0eSB8fCAxXG4gICAgICAgICk7XG5cbiAgICAgICAgdGFza3MucHVzaCh0YXNrKTtcbiAgICAgIH1cblxuICAgICAgZm9yIChjb25zdCB0aW1lV2luZG93IG9mIHRpbWVXaW5kb3dzKSB7XG4gICAgICAgIGNvbnN0IHRhc2tMaXN0OiBzdHJpbmdbXSA9IGJvZHk/LnRhc2tMaXN0Py5tYXAoXG4gICAgICAgICAgKHRsKSA9PlxuICAgICAgICAgICAgYCR7dGw/LnRhc2t9JHt0bD8uZHVyYXRpb24gPiAwID8gYDogJHt0bD8uZHVyYXRpb259IG1pbnV0ZXNgIDogJyd9YFxuICAgICAgICApO1xuXG4gICAgICAgIGNvbnN0IGRheVNjaGVkdWxlID0gYXdhaXQgY3JlYXRlRGF5U2NoZWR1bGVGb3JUYXNrcyhcbiAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgdGFza0xpc3QsXG4gICAgICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgICAgICAgdGltZVdpbmRvdz8uZGF5V2luZG93U3RhcnREYXRlLFxuICAgICAgICAgIHRpbWVXaW5kb3c/LmRheVdpbmRvd0VuZERhdGUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIGJvZHk/LmJ1ZmZlclRpbWUsXG4gICAgICAgICAgYm9keT8uc3RhcnREYXRlXG4gICAgICAgICk7XG5cbiAgICAgICAgZm9yIChjb25zdCB0YXNrT2JqZWN0IG9mIGJvZHk/LnRhc2tMaXN0KSB7XG4gICAgICAgICAgY29uc3QgdGFzayA9IHRhc2tzPy5maW5kKFxuICAgICAgICAgICAgKHQpID0+IHRhc2tPYmplY3Q/LnRhc2s/LnRvTG93ZXJDYXNlKCkgPT09IHQ/Lm5vdGVzPy50b0xvd2VyQ2FzZSgpXG4gICAgICAgICAgKTtcbiAgICAgICAgICBjb25zdCBldmVudElkID0gdXVpZCgpO1xuICAgICAgICAgIGNvbnN0IHRhc2tGcm9tU2NoZWR1bGUgPSBkYXlTY2hlZHVsZT8uZmluZChcbiAgICAgICAgICAgIChkcykgPT4gZHM/LnRhc2s/LnRvTG93ZXJDYXNlKCkgPT09IHRhc2tPYmplY3Q/LnRhc2s/LnRvTG93ZXJDYXNlKClcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgZHVyYXRpb24gPSBkYXlqcyh0YXNrRnJvbVNjaGVkdWxlPy5lbmRfdGltZSwgJ2g6bW0gYScpXG4gICAgICAgICAgICAudHoodGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuZGlmZihcbiAgICAgICAgICAgICAgZGF5anModGFza0Zyb21TY2hlZHVsZT8uc3RhcnRfdGltZSwgJ2g6bW0gYScpLnR6KHRpbWV6b25lLCB0cnVlKSxcbiAgICAgICAgICAgICAgJ20nXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgeWVhciA9IGRheWpzKHRpbWVXaW5kb3c/LmRheVdpbmRvd1N0YXJ0RGF0ZSlcbiAgICAgICAgICAgIC50eih0aW1lem9uZSlcbiAgICAgICAgICAgIC55ZWFyKCk7XG4gICAgICAgICAgY29uc3QgbW9udGggPSBkYXlqcyh0aW1lV2luZG93Py5kYXlXaW5kb3dTdGFydERhdGUpXG4gICAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgICAubW9udGgoKTtcbiAgICAgICAgICBjb25zdCBkYXRlID0gZGF5anModGltZVdpbmRvdz8uZGF5V2luZG93U3RhcnREYXRlKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmRhdGUoKTtcblxuICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgeWVhcixcbiAgICAgICAgICAgIG1vbnRoLFxuICAgICAgICAgICAgZGF0ZSxcbiAgICAgICAgICAgIGR1cmF0aW9uLFxuICAgICAgICAgICAgdGFzayxcbiAgICAgICAgICAgIHRhc2tGcm9tU2NoZWR1bGUsXG4gICAgICAgICAgICAnIHllYXIsIG1vbnRoLCBkYXRlLCBkdXJhdGlvbiwgdGFzaywgdGFza0Zyb21TY2hlZHVsZSdcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgZXZlbnQgPSBhd2FpdCBjcmVhdGVFdmVudEZvclRhc2soXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICB0YXNrT2JqZWN0Py50YXNrbGlzdE5hbWUgfHwgJ01hc3RlcicsXG4gICAgICAgICAgICB0YXNrPy5pZCxcbiAgICAgICAgICAgIHRhc2tPYmplY3Q/LnRhc2ssXG4gICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgIGRheWpzKHRhc2tGcm9tU2NoZWR1bGU/LnN0YXJ0X3RpbWUsICdoOm1tIGEnKVxuICAgICAgICAgICAgICAudHooYm9keT8udGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC55ZWFyKHllYXIpXG4gICAgICAgICAgICAgIC5tb250aChtb250aClcbiAgICAgICAgICAgICAgLmRhdGUoZGF0ZSlcbiAgICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICAgIGR1cmF0aW9uLFxuICAgICAgICAgICAgYm9keT8ucHJpb3JpdHksXG4gICAgICAgICAgICBib2R5Py5hbGxEYXksXG4gICAgICAgICAgICBib2R5Py5yZW1pbmRlcnMsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICBib2R5Py50cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICBib2R5Py52aXNpYmlsaXR5IGFzIFZpc2liaWxpdHlUeXBlLFxuICAgICAgICAgICAgYm9keT8ubG9jYXRpb25cbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkOiBSZW1pbmRlclR5cGVbXSA9IFtdO1xuXG4gICAgICAgICAgaWYgKGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgY29uc3QgbmV3UmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXSA9IGJvZHk/LnJlbWluZGVycy5tYXAoKHIpID0+ICh7XG4gICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgICBldmVudElkOiBldmVudD8uaWQsXG4gICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICBtaW51dGVzOiByLFxuICAgICAgICAgICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgICB9KSk7XG5cbiAgICAgICAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZC5wdXNoKC4uLm5ld1JlbWluZGVycyk7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlczogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW107XG5cbiAgICAgICAgICBmb3IgKGNvbnN0IHRpbWVwcmVmZXJlbmNlIG9mIGJvZHk/LnRpbWVQcmVmZXJlbmNlcykge1xuICAgICAgICAgICAgaWYgKHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICBmb3IgKGNvbnN0IGRheU9mV2VlayBvZiB0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWspIHtcbiAgICAgICAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgICAgICAgZXZlbnRJZDogZXZlbnQ/LmlkLFxuICAgICAgICAgICAgICAgICAgZGF5T2ZXZWVrOiBEYXlPZldlZWtFbnVtW2RheU9mV2Vla10sXG4gICAgICAgICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgICAgIH07XG5cbiAgICAgICAgICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKTtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgICAgZXZlbnRJZDogZXZlbnQ/LmlkLFxuICAgICAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgICB9O1xuXG4gICAgICAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChib2R5Py5idWZmZXJUaW1lPy5hZnRlckV2ZW50IHx8IGJvZHk/LmJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50KSB7XG4gICAgICAgICAgICBjb25zdCBjYWxJbnRlZ3JhdGlvbiA9IGF3YWl0IGdldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUoXG4gICAgICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgICAgZ29vZ2xlQ2FsZW5kYXJOYW1lXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICBpZiAoIWNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlKSB7XG4gICAgICAgICAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgICAgICAgICAnbm8gY2xpZW50IHR5cGUgaW5zaWRlIGNhbGVuZGFyIGludGVncmF0aW9uIGluc2lkZSBjcmVhdGUgYWdlbmRhJ1xuICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBjb25zdCByZXR1cm5WYWx1ZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50KFxuICAgICAgICAgICAgICBldmVudCxcbiAgICAgICAgICAgICAgYm9keT8uYnVmZmVyVGltZVxuICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCkge1xuICAgICAgICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgICAgICBldmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmlkLFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZW5kRGF0ZSxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICAgICAgICAwLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udGl0bGUsXG4gICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICAnZGVmYXVsdCcsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZFxuICAgICAgICAgICAgICApO1xuXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkID0gZ29vZ2xlUmVzVmFsdWUuaWQ7XG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucG9zdEV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZDtcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgICAgICAgY29uc3QgZ29vZ2xlUmVzVmFsdWU6IEdvb2dsZVJlc1R5cGUgPSBhd2FpdCBjcmVhdGVHb29nbGVFdmVudChcbiAgICAgICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICAgICAgZXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uaWQsXG4gICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZW5kRGF0ZSxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zdGFydERhdGUsXG4gICAgICAgICAgICAgICAgMCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRpdGxlLFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lm5vdGVzLFxuICAgICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgICB1bmRlZmluZWRcbiAgICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzLmJlZm9yZUV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucHJlRXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBldmVudHNUb1Vwc2VydC5wdXNoKFxuICAgICAgICAgICAgICAuLi5bXG4gICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LFxuICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCxcbiAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50LFxuICAgICAgICAgICAgICBdPy5maWx0ZXIoKGUpID0+ICEhZSlcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGV2ZW50c1RvVXBzZXJ0LnB1c2goZXZlbnQpO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIGF3YWl0IGluc2VydFJlbWluZGVycyhyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQpO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcyk7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcihcbiAgICAgICAgICAgIHRhc2tPYmplY3Q/LnRhc2tcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgaWYgKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDAgfHwgYm9keT8ucHJpb3JpdHkgPiAxKSB7XG4gICAgICAgICAgICBhd2FpdCBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2goXG4gICAgICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgICAgICAgICAgYm9keT8udXNlcklkXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGF3YWl0IHB1dERhdGFJbkFsbEV2ZW50SW5kZXhJbk9wZW5TZWFyY2goXG4gICAgICAgICAgICBldmVudD8uaWQsXG4gICAgICAgICAgICBzZWFyY2hWZWN0b3IsXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICBldmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgICAgZXZlbnQ/LmVuZERhdGVcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnN0IGV2ZW50SWQgPSB1dWlkKCk7XG4gICAgICBjb25zdCB0YXNrQW5kRXZlbnQgPSBhd2FpdCBjcmVhdGVUYXNrQW5kRXZlbnQoXG4gICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgTWFzdGVyVGFzayxcbiAgICAgICAgYm9keT8udGl0bGUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBib2R5Py5zdGFydERhdGUsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZGVhZGxpbmVUeXBlID09PSAnc29mdERlYWRsaW5lJyA/IGJvZHk/LmR1ZURhdGUgOiB1bmRlZmluZWQsXG4gICAgICAgIChkZWFkbGluZVR5cGUgPT09ICdoYXJkRGVhZGxpbmUnID8gYm9keT8uZHVlRGF0ZSA6IHVuZGVmaW5lZCkgfHxcbiAgICAgICAgICAoIWRlYWRsaW5lVHlwZSA/IGJvZHk/LmR1ZURhdGUgOiB1bmRlZmluZWQpLFxuICAgICAgICBUYXNrU3RhdHVzLlRPRE8sXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICAgIGJvZHk/LmR1cmF0aW9uLFxuICAgICAgICBib2R5Py5wcmlvcml0eSxcbiAgICAgICAgYm9keT8uYWxsRGF5LFxuICAgICAgICBib2R5Py5yZW1pbmRlcnMsXG4gICAgICAgIGJvZHk/LnJlY3VyIGFzIGFueSxcbiAgICAgICAgYm9keT8udHJhbnNwYXJlbmN5LFxuICAgICAgICBib2R5Py52aXNpYmlsaXR5IGFzIFZpc2liaWxpdHlUeXBlLFxuICAgICAgICBib2R5Py5sb2NhdGlvblxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkOiBSZW1pbmRlclR5cGVbXSA9IFtdO1xuXG4gICAgICBpZiAoYm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGNvbnN0IG5ld1JlbWluZGVyczogUmVtaW5kZXJUeXBlW10gPSBib2R5Py5yZW1pbmRlcnMubWFwKChyKSA9PiAoe1xuICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgZXZlbnRJZDogdGFza0FuZEV2ZW50Py5ldmVudD8uaWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgbWludXRlczogcixcbiAgICAgICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgIH0pKTtcblxuICAgICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQucHVzaCguLi5uZXdSZW1pbmRlcnMpO1xuICAgICAgfVxuXG4gICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXTtcblxuICAgICAgZm9yIChjb25zdCB0aW1lcHJlZmVyZW5jZSBvZiBib2R5Py50aW1lUHJlZmVyZW5jZXMpIHtcbiAgICAgICAgaWYgKHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgIGZvciAoY29uc3QgZGF5T2ZXZWVrIG9mIHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaykge1xuICAgICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgICBldmVudElkOiB0YXNrQW5kRXZlbnQ/LmV2ZW50Py5pZCxcbiAgICAgICAgICAgICAgZGF5T2ZXZWVrOiBEYXlPZldlZWtFbnVtW2RheU9mV2Vla10sXG4gICAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgIH07XG5cbiAgICAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZDogdGFza0FuZEV2ZW50Py5ldmVudD8uaWQsXG4gICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgIH07XG5cbiAgICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKTtcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBpZiAoYm9keT8uYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCB8fCBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCkge1xuICAgICAgICBjb25zdCBjYWxJbnRlZ3JhdGlvbiA9IGF3YWl0IGdldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIGdvb2dsZUNhbGVuZGFyTmFtZVxuICAgICAgICApO1xuXG4gICAgICAgIGlmICghY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpIHtcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICAgICAnbm8gY2xpZW50IHR5cGUgaW5zaWRlIGNhbGVuZGFyIGludGVncmF0aW9uIGluc2lkZSBjcmVhdGUgYWdlbmRhJ1xuICAgICAgICAgICk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXR1cm5WYWx1ZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50KFxuICAgICAgICAgIHRhc2tBbmRFdmVudC5ldmVudCxcbiAgICAgICAgICBib2R5Py5idWZmZXJUaW1lXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCkge1xuICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICB0YXNrQW5kRXZlbnQ/LmV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmlkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zdGFydERhdGUsXG4gICAgICAgICAgICAwLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zZW5kVXBkYXRlcyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udGl0bGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lm5vdGVzLFxuICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkID0gZ29vZ2xlUmVzVmFsdWUuaWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnBvc3RFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQ7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAocmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudCkge1xuICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICB0YXNrQW5kRXZlbnQ/LmV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5pZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zdGFydERhdGUsXG4gICAgICAgICAgICAwLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udGl0bGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucHJlRXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgICB9XG5cbiAgICAgICAgZXZlbnRzVG9VcHNlcnQucHVzaChcbiAgICAgICAgICAuLi5bXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50LFxuICAgICAgICAgIF0/LmZpbHRlcigoZSkgPT4gISFlKVxuICAgICAgICApO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgZXZlbnRzVG9VcHNlcnQucHVzaCh0YXNrQW5kRXZlbnQuZXZlbnQpO1xuICAgICAgfVxuXG4gICAgICBpZiAocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGF3YWl0IGluc2VydFJlbWluZGVycyhyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQpO1xuICAgICAgfVxuXG4gICAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcyk7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuXG4gICAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCB8fCBib2R5Py5wcmlvcml0eSA+IDEpIHtcbiAgICAgICAgYXdhaXQgcHV0RGF0YUluVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoKFxuICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgc2VhcmNoVmVjdG9yLFxuICAgICAgICAgIGJvZHk/LnVzZXJJZFxuICAgICAgICApO1xuICAgICAgfVxuXG4gICAgICBhd2FpdCBwdXREYXRhSW5BbGxFdmVudEluZGV4SW5PcGVuU2VhcmNoKFxuICAgICAgICB0YXNrQW5kRXZlbnQ/LmV2ZW50Py5pZCxcbiAgICAgICAgc2VhcmNoVmVjdG9yLFxuICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgIHRhc2tBbmRFdmVudD8uZXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAgICAgdGFza0FuZEV2ZW50LmV2ZW50Py5lbmREYXRlXG4gICAgICApO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGV2ZW50c1RvVXBzZXJ0Py5sZW5ndGgsICcgZXZlbnRzVG9VcHNlcnQ/Lmxlbmd0aCcpO1xuXG4gICAgYXdhaXQgdXBzZXJ0RXZlbnRzKGV2ZW50c1RvVXBzZXJ0KTtcblxuICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgcmVzcG9uc2UuZGF0YSA9ICdwcm9jZXNzZWQgcmVxdWVzdCBzdWNjZXNzZnVsbHknO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGZpbmFsIHN0ZXAgYWRkIHRhc2snKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NBZGRUYXNrUGVuZGluZyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICBkYXRlSlNPTkJvZHk6IERhdGVUaW1lSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmdcbik6IFByb21pc2U8UmVzcG9uc2VBY3Rpb25UeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IGR1cmF0aW9uID0gMDtcblxuICAgIGNvbnN0IHllYXIgPSBkYXRlSlNPTkJvZHk/LnllYXI7XG4gICAgY29uc3QgbW9udGggPSBkYXRlSlNPTkJvZHk/Lm1vbnRoO1xuICAgIGNvbnN0IGRheSA9IGRhdGVKU09OQm9keT8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXkgPSBkYXRlSlNPTkJvZHk/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ciA9IGRhdGVKU09OQm9keT8uaG91cjtcbiAgICBjb25zdCBtaW51dGUgPSBkYXRlSlNPTkJvZHk/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWUgPSBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IHllYXJEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LnllYXI7XG4gICAgY29uc3QgbW9udGhEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/Lm1vbnRoO1xuICAgIGNvbnN0IGRheUR1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXlEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ckR1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8uaG91cjtcbiAgICBjb25zdCBtaW51dGVEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWVEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAnYWRkVGFzaycsXG4gICAgfTtcblxuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICAgIGRhdGVUaW1lOiB7IHJlcXVpcmVkOiBbXSB9LFxuICAgIH07XG5cbiAgICBjb25zdCB0YXNrU3RhcnREYXRlID0gZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXIsXG4gICAgICBtb250aCxcbiAgICAgIGRheSxcbiAgICAgIGlzb1dlZWtkYXksXG4gICAgICBob3VyLFxuICAgICAgbWludXRlLFxuICAgICAgc3RhcnRUaW1lLFxuICAgICAgZGF0ZUpTT05Cb2R5Py5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgZGF0ZUpTT05Cb2R5Py5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIGNvbnN0IHRhc2tEdWVEYXRlID0gZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXJEdWUsXG4gICAgICBtb250aER1ZSxcbiAgICAgIGRheUR1ZSxcbiAgICAgIGlzb1dlZWtkYXlEdWUsXG4gICAgICBob3VyRHVlLFxuICAgICAgbWludXRlRHVlLFxuICAgICAgc3RhcnRUaW1lRHVlLFxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKHRhc2tTdGFydERhdGUsIHRhc2tEdWVEYXRlLCAnIHRhc2tTdGFydERhdGUsIHRhc2tEdWVEYXRlJyk7XG5cbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgJiYgZGF0ZUpTT05Cb2R5Py5lbmRUaW1lKSB7XG4gICAgICBjb25zdCBzdGFydFRpbWVPYmplY3QgPSBkYXlqcyhkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSwgJ0hIOm1tJyk7XG4gICAgICBjb25zdCBlbmRUaW1lT2JqZWN0ID0gZGF5anMoZGF0ZUpTT05Cb2R5LmVuZFRpbWUsICdISDptbScpO1xuXG4gICAgICBjb25zdCBtaW51dGVzID0gZW5kVGltZU9iamVjdC5kaWZmKHN0YXJ0VGltZU9iamVjdCwgJ20nKTtcblxuICAgICAgaWYgKG1pbnV0ZXMgPiAwKSB7XG4gICAgICAgIGR1cmF0aW9uID0gbWludXRlcztcbiAgICAgIH1cbiAgICB9IGVsc2UgaWYgKGRhdGVKU09OQm9keT8uZHVlRGF0ZT8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSAmJiBqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKSB7XG4gICAgICBjb25zdCBzdGFydFRpbWVPYmplY3QgPSBkYXlqcyhqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUpO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUpO1xuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGR1cmF0aW9uID0gMzA7XG4gICAgfVxuXG4gICAgbGV0IHJlY3VyT2JqZWN0OiBSZWN1cnJlbmNlUnVsZVR5cGUgfCB7fSA9IHt9O1xuICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kpIHtcbiAgICAgIGNvbnN0IHJlY3VyRW5kRGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgICAgY3VycmVudFRpbWUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5tb250aCxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICAgKTtcblxuICAgICAgcmVjdXJPYmplY3QgPSB7XG4gICAgICAgIGZyZXF1ZW5jeTpcbiAgICAgICAgICAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlKSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWw6XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIDEsXG4gICAgICB9O1xuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5KSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5V2Vla0RheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieU1vbnRoRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5vY2N1cnJlbmNlID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlO1xuICAgICAgfVxuXG4gICAgICBpZiAocmVjdXJFbmREYXRlIHx8IGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuZW5kRGF0ZSA9XG4gICAgICAgICAgcmVjdXJFbmREYXRlIHx8IGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGU7XG4gICAgICB9XG4gICAgfVxuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHRhc2tTdGFydERhdGU7XG5cbiAgICBjb25zdCBib2R5OiBBZGRUYXNrVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgZHVyYXRpb24sXG4gICAgICBkZXNjcmlwdGlvbjoganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHwganNvbkJvZHk/LnBhcmFtcz8ubm90ZXMsXG4gICAgICBzdGFydERhdGU6IGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fCBzdGFydERhdGUsXG4gICAgICBkdWVEYXRlOiB0YXNrRHVlRGF0ZSB8fCAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uZW5kRGF0ZSxcbiAgICAgIGJ1ZmZlclRpbWU6IGpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUsXG4gICAgICByZW1pbmRlcnM6IGpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fCBbXSxcbiAgICAgIHByaW9yaXR5OiBqc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fCAxLFxuICAgICAgdGltZVByZWZlcmVuY2VzOiBkYXRlSlNPTkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fCBbXSxcbiAgICAgIGxvY2F0aW9uOiBqc29uQm9keT8ucGFyYW1zPy5sb2NhdGlvbixcbiAgICAgIHRyYW5zcGFyZW5jeToganNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eToganNvbkJvZHk/LnBhcmFtcy52aXNpYmlsaXR5IGFzIFZpc2liaWxpdHlUeXBlLFxuICAgICAgaXNCcmVhazoganNvbkJvZHk/LnBhcmFtcz8uaXNCcmVhayxcbiAgICAgIGFsbERheTogZGF0ZUpTT05Cb2R5Py5hbGxEYXksXG4gICAgICBkZWFkbGluZVR5cGU6IGpzb25Cb2R5Py5wYXJhbXM/LmRlYWRsaW5lVHlwZSxcbiAgICAgIHRhc2tMaXN0OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8ubWFwKCh0bCkgPT4gKHtcbiAgICAgICAgICAuLi50bCxcbiAgICAgICAgICB0YXNrbGlzdE5hbWU6IHRsPy50YXNrbGlzdE5hbWU/LnRvTG93ZXJDYXNlKCksXG4gICAgICAgIH0pKSB8fCBbXSxcbiAgICB9O1xuXG4gICAgaWYgKGJvZHk/LnN0YXJ0RGF0ZSAmJiB0YXNrRHVlRGF0ZSkge1xuICAgICAgY29uc3QgZGlmZkRheXMgPSBkYXlqcyh0YXNrRHVlRGF0ZSkuZGlmZihib2R5Py5zdGFydERhdGUsICdkJyk7XG5cbiAgICAgIGlmIChkaWZmRGF5cyA+IDEpIHtcbiAgICAgICAgc3RhcnREYXRlID0gYm9keT8uc3RhcnREYXRlO1xuXG4gICAgICAgIGlmICghKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSkge1xuICAgICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmZyZXF1ZW5jeSA9ICdkYWlseSc7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoIShyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5pbnRlcnZhbCkge1xuICAgICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmludGVydmFsID0gMTtcbiAgICAgICAgfVxuXG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmVuZERhdGUgPSB0YXNrRHVlRGF0ZTtcbiAgICAgIH0gZWxzZSBpZiAoZGF5anModGFza0R1ZURhdGUpLmlzQWZ0ZXIoZGF5anMoYm9keT8uc3RhcnREYXRlKSkpIHtcbiAgICAgICAgc3RhcnREYXRlID0gdGFza0R1ZURhdGU7XG4gICAgICB9XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZVxuICAgICkge1xuICAgICAgYm9keS5yZWN1ciA9IHJlY3VyT2JqZWN0IGFzIGFueTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhib2R5LCAnIGJvZHknKTtcblxuICAgIGNvbnNvbGUubG9nKGRheSwgaXNvV2Vla2RheSwgJyBkYXksIGlzb1dlZWtkYXksJyk7XG5cbiAgICAvLyBpZiAoIWRheSAmJiAhaXNvV2Vla2RheSkge1xuICAgIC8vICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcydcbiAgICAvLyAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkPy5bMF0pXG4gICAgLy8gICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzXG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keVxuXG4gICAgLy8gfVxuXG4gICAgY29uc29sZS5sb2coaG91ciwgbWludXRlLCBzdGFydFRpbWUsICcgaG91ciwgbWludXRlLCBzdGFydFRpbWUsJyk7XG5cbiAgICAvLyBpZiAoKGhvdXIgPT09IG51bGwpICYmIChtaW51dGUgPT09IG51bGwpICYmICFzdGFydFRpbWUpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnXG4gICAgLy8gICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzFdKVxuICAgIC8vICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkc1xuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHlcbiAgICAvLyB9XG5cbiAgICBpZiAoIWJvZHk/LnN0YXJ0RGF0ZSkge1xuICAgICAgaWYgKGJvZHk/LnJlY3VyPy5mcmVxdWVuY3kpIHtcbiAgICAgICAgYm9keS5zdGFydERhdGUgPSBkYXlqcygpLmFkZCgxLCAnaCcpLnR6KHRpbWV6b25lKS5mb3JtYXQoKTtcbiAgICAgIH0gZWxzZSBpZiAoYm9keT8uZHVlRGF0ZSkge1xuICAgICAgICBib2R5LnN0YXJ0RGF0ZSA9IGRheWpzKGJvZHkuZHVlRGF0ZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLnN1YnRyYWN0KGJvZHkuZHVyYXRpb24sICdtJylcbiAgICAgICAgICAuZm9ybWF0KCk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zdCB3aW5kb3dTdGFydERhdGUgPSBkYXlqcygpLnR6KHRpbWV6b25lKS5mb3JtYXQoKTtcbiAgICAgICAgY29uc3Qgd2luZG93RW5kRGF0ZSA9IGRheWpzKCkudHoodGltZXpvbmUpLmhvdXIoMjMpLm1pbnV0ZSg1OSkuZm9ybWF0KCk7XG4gICAgICAgIGNvbnN0IGF2YWlsYWJsZVNsb3QgPSBhd2FpdCBmaW5kQW5FbXB0eVNsb3QoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgICAgIGJvZHk/LmR1cmF0aW9uIHx8IDMwXG4gICAgICAgICk7XG4gICAgICAgIGJvZHkuc3RhcnREYXRlID0gZGF5anMoYXZhaWxhYmxlU2xvdC5zdGFydFRpbWUsICdoOm1tIGEnKVxuICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgcmVzcG9uc2UnKTtcblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcEFkZFRhc2soXG4gICAgICBib2R5LFxuICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBhZGQgdGFzaycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0FkZFRhc2tNaXNzaW5nRmllbGRzUmV0dXJuZWQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGVcbik6IFByb21pc2U8UmVzcG9uc2VBY3Rpb25UeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IGR1cmF0aW9uID0gMDtcblxuICAgIGNvbnN0IHllYXIgPSBkYXRlSlNPTkJvZHk/LnllYXI7XG4gICAgY29uc3QgbW9udGggPSBkYXRlSlNPTkJvZHk/Lm1vbnRoO1xuICAgIGNvbnN0IGRheSA9IGRhdGVKU09OQm9keT8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXkgPSBkYXRlSlNPTkJvZHk/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ciA9IGRhdGVKU09OQm9keT8uaG91cjtcbiAgICBjb25zdCBtaW51dGUgPSBkYXRlSlNPTkJvZHk/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWUgPSBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IHllYXJEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LnllYXI7XG4gICAgY29uc3QgbW9udGhEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/Lm1vbnRoO1xuICAgIGNvbnN0IGRheUR1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXlEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ckR1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8uaG91cjtcbiAgICBjb25zdCBtaW51dGVEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWVEdWUgPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAnYWRkVGFzaycsXG4gICAgfTtcblxuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICAgIGRhdGVUaW1lOiB7IHJlcXVpcmVkOiBbXSB9LFxuICAgIH07XG5cbiAgICBjb25zdCB0YXNrU3RhcnREYXRlID0gZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXIsXG4gICAgICBtb250aCxcbiAgICAgIGRheSxcbiAgICAgIGlzb1dlZWtkYXksXG4gICAgICBob3VyLFxuICAgICAgbWludXRlLFxuICAgICAgc3RhcnRUaW1lLFxuICAgICAgZGF0ZUpTT05Cb2R5Py5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgZGF0ZUpTT05Cb2R5Py5yZWxhdGl2ZVRpbWVGcm9tTm93IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIGNvbnN0IHRhc2tEdWVEYXRlID0gZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXJEdWUsXG4gICAgICBtb250aER1ZSxcbiAgICAgIGRheUR1ZSxcbiAgICAgIGlzb1dlZWtkYXlEdWUsXG4gICAgICBob3VyRHVlLFxuICAgICAgbWludXRlRHVlLFxuICAgICAgc3RhcnRUaW1lRHVlLFxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kdWVEYXRlXG4gICAgICAgICAgPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5yZWxhdGl2ZVRpbWVGcm9tTm93IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kdWVEYXRlPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIGlmIChkYXRlSlNPTkJvZHk/LmR1cmF0aW9uKSB7XG4gICAgICBkdXJhdGlvbiA9IGRhdGVKU09OQm9keT8uZHVyYXRpb247XG4gICAgfSBlbHNlIGlmIChkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSAmJiBkYXRlSlNPTkJvZHk/LmVuZFRpbWUpIHtcbiAgICAgIGNvbnN0IHN0YXJ0VGltZU9iamVjdCA9IGRheWpzKGRhdGVKU09OQm9keT8uc3RhcnRUaW1lLCAnSEg6bW0nKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhkYXRlSlNPTkJvZHkuZW5kVGltZSwgJ0hIOm1tJyk7XG5cbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH0gZWxzZSBpZiAoZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoXG4gICAgICAoanNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lKSAmJlxuICAgICAgKGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKVxuICAgICkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoXG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lXG4gICAgICApO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lXG4gICAgICApO1xuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGR1cmF0aW9uID0gMzA7XG4gICAgfVxuXG4gICAgbGV0IHJlY3VyT2JqZWN0OiBSZWN1cnJlbmNlUnVsZVR5cGUgfCB7fSA9IHt9O1xuICAgIGlmIChcbiAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmZyZXF1ZW5jeSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5mcmVxdWVuY3lcbiAgICApIHtcbiAgICAgIGNvbnN0IHJlY3VyRW5kRGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgICAgY3VycmVudFRpbWUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5tb250aCB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGgsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1pbnV0ZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uc3RhcnRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5zdGFydFRpbWUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGVcbiAgICAgICAgICAgID8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vdyB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZVxuICAgICAgICAgICAgPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgICApO1xuXG4gICAgICByZWN1ck9iamVjdCA9IHtcbiAgICAgICAgZnJlcXVlbmN5OlxuICAgICAgICAgIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUpIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWw6XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmludGVydmFsLFxuICAgICAgfTtcblxuICAgICAgaWYgKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieVdlZWtEYXlcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieVdlZWtEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5V2Vla0RheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5XG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlNb250aERheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlNb250aERheTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLm9jY3VycmVuY2UgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2UgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/Lm9jY3VycmVuY2U7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgcmVjdXJFbmREYXRlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlXG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuZW5kRGF0ZSA9XG4gICAgICAgICAgcmVjdXJFbmREYXRlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBsZXQgc3RhcnREYXRlID0gdGFza1N0YXJ0RGF0ZTtcblxuICAgIGNvbnN0IG5ld0JvZHk6IEFkZFRhc2tUeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgbWV0aG9kOiBkYXRlSlNPTkJvZHk/Lm1ldGhvZCBhcyBhbnksXG4gICAgICBkdXJhdGlvbixcbiAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5ub3RlcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ubm90ZXMsXG4gICAgICBzdGFydERhdGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICBzdGFydERhdGUsXG4gICAgICBkdWVEYXRlOiB0YXNrRHVlRGF0ZSB8fCAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uZW5kRGF0ZSxcbiAgICAgIGJ1ZmZlclRpbWU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5idWZmZXJUaW1lLFxuICAgICAgcmVtaW5kZXJzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHxcbiAgICAgICAgW10sXG4gICAgICBwcmlvcml0eTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucHJpb3JpdHkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fFxuICAgICAgICAxLFxuICAgICAgdGltZVByZWZlcmVuY2VzOlxuICAgICAgICBkYXRlSlNPTkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8udGltZVByZWZlcmVuY2VzIHx8XG4gICAgICAgIFtdLFxuICAgICAgbG9jYXRpb246XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmxvY2F0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24sXG4gICAgICB0cmFuc3BhcmVuY3k6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6XG4gICAgICAgIChqc29uQm9keT8ucGFyYW1zLnZpc2liaWxpdHkgYXMgVmlzaWJpbGl0eVR5cGUpIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udmlzaWJpbGl0eSxcbiAgICAgIGlzQnJlYWs6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmlzQnJlYWsgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5pc0JyZWFrLFxuICAgICAgYWxsRGF5OlxuICAgICAgICBkYXRlSlNPTkJvZHk/LmFsbERheSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uYWxsRGF5LFxuICAgICAgZGVhZGxpbmVUeXBlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZWFkbGluZVR5cGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZWFkbGluZVR5cGUsXG4gICAgICB0YXNrTGlzdDpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/Lm1hcCgodGwpID0+ICh7XG4gICAgICAgICAgLi4udGwsXG4gICAgICAgICAgdGFza2xpc3ROYW1lOiB0bD8udGFza2xpc3ROYW1lPy50b0xvd2VyQ2FzZSgpLFxuICAgICAgICB9KSkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8ubWFwKCh0bCkgPT4gKHtcbiAgICAgICAgICAuLi50bCxcbiAgICAgICAgICB0YXNrbGlzdE5hbWU6IHRsPy50YXNrbGlzdE5hbWU/LnRvTG93ZXJDYXNlKCksXG4gICAgICAgIH0pKSB8fFxuICAgICAgICBbXSxcbiAgICB9O1xuXG4gICAgaWYgKG5ld0JvZHk/LnN0YXJ0RGF0ZSAmJiB0YXNrRHVlRGF0ZSkge1xuICAgICAgY29uc3QgZGlmZkhvdXJzID0gZGF5anModGFza0R1ZURhdGUpLmRpZmYobmV3Qm9keT8uc3RhcnREYXRlLCAnaCcpO1xuICAgICAgY29uc3QgZGlmZkRheXMgPSBkYXlqcyhuZXdCb2R5Py5zdGFydERhdGUpLmRpZmYobmV3Qm9keT8uc3RhcnREYXRlLCAnZCcpO1xuXG4gICAgICBpZiAoZGlmZkRheXMgPiAxKSB7XG4gICAgICAgIHN0YXJ0RGF0ZSA9IG5ld0JvZHk/LnN0YXJ0RGF0ZTtcblxuICAgICAgICBpZiAoIShyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5mcmVxdWVuY3kpIHtcbiAgICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5mcmVxdWVuY3kgPSAnZGFpbHknO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCEocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uaW50ZXJ2YWwpIHtcbiAgICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5pbnRlcnZhbCA9IDE7XG4gICAgICAgIH1cblxuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5lbmREYXRlID0gdGFza0R1ZURhdGU7XG4gICAgICB9IGVsc2UgaWYgKGRheWpzKHRhc2tEdWVEYXRlKS5pc0FmdGVyKGRheWpzKG5ld0JvZHk/LnN0YXJ0RGF0ZSkpKSB7XG4gICAgICAgIHN0YXJ0RGF0ZSA9IHRhc2tEdWVEYXRlO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHByZXZCb2R5OiBBZGRUYXNrVHlwZSA9IHtcbiAgICAgIC4uLm1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YSxcbiAgICB9O1xuXG4gICAgaWYgKCFwcmV2Qm9keT8udXNlcklkKSB7XG4gICAgICBwcmV2Qm9keS51c2VySWQgPSB1c2VySWQgfHwgbmV3Qm9keT8udXNlcklkO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpbWV6b25lKSB7XG4gICAgICBwcmV2Qm9keS50aW1lem9uZSA9IHRpbWV6b25lIHx8IG5ld0JvZHk/LnRpbWV6b25lO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICBwcmV2Qm9keS50aXRsZSA9IG5ld0JvZHk/LnRpdGxlO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmR1cmF0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5kdXJhdGlvbiA9IG5ld0JvZHk/LmR1cmF0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmRlc2NyaXB0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5kZXNjcmlwdGlvbiA9IG5ld0JvZHk/LmRlc2NyaXB0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnN0YXJ0RGF0ZSkge1xuICAgICAgcHJldkJvZHkuc3RhcnREYXRlID0gbmV3Qm9keT8uc3RhcnREYXRlO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmR1ZURhdGUpIHtcbiAgICAgIHByZXZCb2R5LmR1ZURhdGUgPSBuZXdCb2R5LmR1ZURhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgcHJldkJvZHkuYnVmZmVyVGltZSA9IG5ld0JvZHk/LmJ1ZmZlclRpbWU7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnJlbWluZGVycyA9IG5ld0JvZHk/LnJlbWluZGVycyB8fCBbXTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5wcmlvcml0eSkge1xuICAgICAgcHJldkJvZHkucHJpb3JpdHkgPSBuZXdCb2R5Py5wcmlvcml0eTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkudGltZVByZWZlcmVuY2VzID0gbmV3Qm9keT8udGltZVByZWZlcmVuY2VzO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmxvY2F0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5sb2NhdGlvbiA9IG5ld0JvZHk/LmxvY2F0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgcHJldkJvZHkudHJhbnNwYXJlbmN5ID0gbmV3Qm9keT8udHJhbnNwYXJlbmN5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIHByZXZCb2R5LnZpc2liaWxpdHkgPSBuZXdCb2R5Py52aXNpYmlsaXR5O1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5pc0JyZWFrID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHByZXZCb2R5LmlzQnJlYWsgPSBuZXdCb2R5Py5pc0JyZWFrO1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5hbGxEYXkgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuYWxsRGF5ID0gbmV3Qm9keT8uYWxsRGF5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmRlYWRsaW5lVHlwZSkge1xuICAgICAgcHJldkJvZHkuZGVhZGxpbmVUeXBlID0gbmV3Qm9keT8uZGVhZGxpbmVUeXBlO1xuICAgIH1cblxuICAgIGlmICghKHByZXZCb2R5Py50YXNrTGlzdD8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnRhc2tMaXN0ID0gbmV3Qm9keT8udGFza0xpc3Q7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZVxuICAgICkge1xuICAgICAgbmV3Qm9keS5yZWN1ciA9IHJlY3VyT2JqZWN0IGFzIGFueTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5yZWN1cikge1xuICAgICAgcHJldkJvZHkucmVjdXIgPSBuZXdCb2R5Py5yZWN1cjtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5zdGFydERhdGUpIHtcbiAgICAgIGlmIChwcmV2Qm9keT8ucmVjdXI/LmZyZXF1ZW5jeSkge1xuICAgICAgICBwcmV2Qm9keS5zdGFydERhdGUgPSBkYXlqcygpLmFkZCgxLCAnaCcpLnR6KHRpbWV6b25lKS5mb3JtYXQoKTtcbiAgICAgIH0gZWxzZSBpZiAocHJldkJvZHk/LmR1ZURhdGUpIHtcbiAgICAgICAgcHJldkJvZHkuc3RhcnREYXRlID0gZGF5anMocHJldkJvZHkuZHVlRGF0ZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLnN1YnRyYWN0KHByZXZCb2R5LmR1cmF0aW9uLCAnbScpXG4gICAgICAgICAgLmZvcm1hdCgpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc3Qgd2luZG93U3RhcnREYXRlID0gZGF5anMoKS50eih0aW1lem9uZSkuZm9ybWF0KCk7XG4gICAgICAgIGNvbnN0IHdpbmRvd0VuZERhdGUgPSBkYXlqcygpLnR6KHRpbWV6b25lKS5ob3VyKDIzKS5taW51dGUoNTkpLmZvcm1hdCgpO1xuICAgICAgICBjb25zdCBhdmFpbGFibGVTbG90ID0gYXdhaXQgZmluZEFuRW1wdHlTbG90KFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAgICAgICBwcmV2Qm9keT8uZHVyYXRpb24gfHwgMzBcbiAgICAgICAgKTtcbiAgICAgICAgcHJldkJvZHkuc3RhcnREYXRlID0gZGF5anMoYXZhaWxhYmxlU2xvdC5zdGFydFRpbWUsICdoOm1tIGEnKVxuICAgICAgICAgIC50eih0aW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAuZm9ybWF0KCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uc3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS5zdGFydERhdGUgPSBuZXdCb2R5Py5zdGFydERhdGU7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coZGF5LCBpc29XZWVrZGF5LCAnIGRheSwgaXNvV2Vla2RheScpO1xuXG4gICAgLy8gaWYgKCFwcmV2Qm9keT8uc3RhcnREYXRlICYmICFkYXkgJiYgIWlzb1dlZWtkYXkpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnXG4gICAgLy8gICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzBdKVxuICAgIC8vICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkc1xuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5XG5cbiAgICAvLyB9XG5cbiAgICBjb25zb2xlLmxvZyhob3VyLCBtaW51dGUsIHN0YXJ0VGltZSwgJyBob3VyLCBtaW51dGUsIHN0YXJ0VGltZSwnKTtcblxuICAgIC8vIGlmICgoZGF5anMocHJldkJvZHk/LnN0YXJ0RGF0ZSkuaG91cigpID09PSAwKVxuICAgIC8vICAgICAmJiAoZGF5anMocHJldkJvZHk/LnN0YXJ0RGF0ZSkubWludXRlKCkgPT09IDApXG4gICAgLy8gICAgICYmIChob3VyID09PSBudWxsKSAmJiAobWludXRlID09PSBudWxsKSAmJiAhc3RhcnRUaW1lKSB7XG4gICAgLy8gICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJ1xuICAgIC8vICAgICBtaXNzaW5nRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQ/LlsxXSlcbiAgICAvLyAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHNcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keVxuICAgIC8vIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcEFkZFRhc2soXG4gICAgICBwcmV2Qm9keSxcbiAgICAgIHByZXZCb2R5Py50aW1lem9uZSxcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGFkZCB0YXNrIG1pc3NpbmcgZmllbGRzIHJldHVybmVkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBhZGRUYXNrQ29udHJvbENlbnRlciA9IGFzeW5jIChcbiAgb3BlbmFpOiBPcGVuQUksXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG4gIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuICBxdWVyeTogJ21pc3NpbmdfZmllbGRzJyB8ICdjb21wbGV0ZWQnIHwgJ2V2ZW50X25vdF9mb3VuZCcgfCAncGVuZGluZydcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG1lc3NhZ2VMZW5ndGggPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcz8ubGVuZ3RoO1xuICAgIGxldCB1c2VyTWVzc2FnZSA9ICcnO1xuICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgdXNlck1lc3NhZ2UgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHVzZXJJbnB1dCA9IHVzZXJNZXNzYWdlO1xuXG4gICAgY29uc3QganNvbkJvZHkgPSBhd2FpdCBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgIHVzZXJJbnB1dCxcbiAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICk7XG4gICAgY29uc3QgZGF0ZVRpbWUgPSBhd2FpdCBnZW5lcmF0ZURhdGVUaW1lKFxuICAgICAgdXNlcklucHV0LFxuICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmVcbiAgICApO1xuICAgIGxldCBhZGRUYXNrUmVzOiBSZXNwb25zZUFjdGlvblR5cGUgPSB7XG4gICAgICBxdWVyeTogJ2NvbXBsZXRlZCcsXG4gICAgICBkYXRhOiAnJyxcbiAgICAgIHNraWxsOiAnJyxcbiAgICAgIHByZXZEYXRhOiB7fSxcbiAgICAgIHByZXZEYXRhRXh0cmE6IHt9LFxuICAgIH07XG5cbiAgICBzd2l0Y2ggKHF1ZXJ5KSB7XG4gICAgICBjYXNlICdwZW5kaW5nJzpcbiAgICAgICAgYWRkVGFza1JlcyA9IGF3YWl0IHByb2Nlc3NBZGRUYXNrUGVuZGluZyhcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbkJvZHksXG4gICAgICAgICAgZGF0ZVRpbWUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnbWlzc2luZ19maWVsZHMnOlxuICAgICAgICBhZGRUYXNrUmVzID0gYXdhaXQgcHJvY2Vzc0FkZFRhc2tNaXNzaW5nRmllbGRzUmV0dXJuZWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25Cb2R5LFxuICAgICAgICAgIGRhdGVUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICB9XG5cbiAgICBpZiAoYWRkVGFza1Jlcz8ucXVlcnkgPT09ICdjb21wbGV0ZWQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5KFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBhZGRUYXNrUmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoYWRkVGFza1Jlcz8ucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyhcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgYWRkVGFza1Jlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gYWRkVGFza1Jlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IGFkZFRhc2tSZXM/LnByZXZEYXRhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGFFeHRyYSA9IGFkZFRhc2tSZXM/LnByZXZEYXRhRXh0cmE7XG4gICAgfSBlbHNlIGlmIChhZGRUYXNrUmVzPy5xdWVyeSA9PT0gJ2V2ZW50X25vdF9mb3VuZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2U6IEFzc2lzdGFudE1lc3NhZ2VUeXBlID0ge1xuICAgICAgICByb2xlOiAnYXNzaXN0YW50JyxcbiAgICAgICAgY29udGVudDogXCJPb3BzLi4uIEkgY291bGRuJ3QgZmluZCB0aGUgZXZlbnQuIFNvcnJ5IDooXCIsXG4gICAgICB9O1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9XG5cbiAgICByZXR1cm4gbWVzc2FnZUhpc3RvcnlPYmplY3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBhZGQgdGFzayBjb250cm9sIGNlbnRlcicpO1xuICB9XG59O1xuIl19