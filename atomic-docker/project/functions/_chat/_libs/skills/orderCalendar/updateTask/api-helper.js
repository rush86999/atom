import { googleCalendarName, googleResourceName, hasuraAdminSecret, hasuraGraphUrl, } from '@chat/_libs/constants';
import got from 'got';
import { TaskStatus } from './constants';
import { v4 as uuid } from 'uuid';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, createGoogleEvent, createPreAndPostEventsFromEvent, createRRuleString, deleteEventGivenId, deleteGoogleEvent, deleteRemindersWithIds, eventSearchBoundary, extrapolateDateFromJSONData, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, getCalendarIntegrationByName, getEventFromPrimaryKey, getGlobalCalendar, getTaskGivenId, insertReminders, patchGoogleEvent, putDataInTrainEventIndexInOpenSearch, upsertEvents, } from '@chat/_libs/api-helper';
import requiredFields from './requiredFields';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
import { deletePreferredTimeRangesGivenEventId } from '../removeAllPreferedTimes/api-helper';
// updateGoogleEvent
export const patchGoogleEventForTaskList = async (eventId, userId, clientType, calendarId, calendarResourceName, title, duration, timezone, startDate, oldStartDate, allDay, reminders, recurObject, transparency, visibility, location) => {
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
            const endDateTime = startDateTime && duration
                ? dayjs(startDateTime).tz(timezone).add(duration, 'minute').format()
                : oldStartDate && duration
                    ? dayjs(oldStartDate).tz(timezone).add(duration, 'minute').format()
                    : undefined;
            const googleReminder = {
                overrides: reminders?.map((r) => ({ method: 'email', minutes: r })),
                useDefault: false,
            };
            // take care of recurrence
            const recur = createRRuleString(recurObject?.frequency, recurObject?.interval, recurObject?.byWeekDay, recurObject?.occurrence, recurObject?.endDate, recurObject?.byMonthDay);
            await patchGoogleEvent(userId, calendarId, eventId, clientType, endDateTime, startDateTime, 0, undefined, 'all', false, undefined, undefined, title, title, timezone, allDay && dayjs(startDate).tz(timezone).format('YYYY-MM-DD'), allDay &&
                dayjs(startDate).tz(timezone).add(duration, 'm').format('YYYY-MM-DD'), undefined, undefined, undefined, undefined, undefined, undefined, recur, reminders?.length > 0 ? googleReminder : undefined, undefined, undefined, transparency, visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', location, undefined);
            console.log(' googlePatch inside updateDeadlineEventForTaskList');
        }
    }
    catch (e) {
        console.log(e, ' unable to patch event for task');
    }
};
export const updateTaskInDb = async (task) => {
    try {
        let variables = { id: task?.id };
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
        console.log(res, ' res inside updateTaskInDb');
        if (res?.data?.update_Task_by_pk) {
            return res?.data?.update_Task_by_pk;
        }
    }
    catch (e) {
        console.log(e, ' unable to get insertTaskInDb');
    }
};
export const updateTaskInDbAndEventInGoogle = async (userId, taskId, clientType, calendarId, calendarResourceName, taskListName, text, timezone, startDate, oldStartDate, important, softDeadline, hardDeadline, status, eventId, duration, priority, allDay, reminders, recurObject, transparency, visibility, location) => {
    try {
        const toUpdateTask = {
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
        await patchGoogleEventForTaskList(eventId, userId, clientType, calendarId, calendarResourceName, text, duration || 30, timezone, startDate, oldStartDate, allDay, reminders, recurObject, transparency, visibility, location);
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
export const finalStepUpdateTask = async (body, startDate, endDate, response) => {
    try {
        // convert to vector for search
        const searchTitle = body?.oldTitle || body?.title;
        const searchVector = await convertEventTitleToOpenAIVector(searchTitle);
        const res = await allEventWithDatesOpenSearch(body?.userId, searchVector, startDate, endDate);
        const id = res?.hits?.hits?.[0]?._id;
        // validate found event
        if (!id) {
            response.query = 'event_not_found';
            return response;
        }
        const eventId = id;
        // get client type
        const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
        // getGlobalCalendar
        let calendarDoc = null;
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
        const recur = createRRuleString(body?.recur?.frequency, body?.recur?.interval, body?.recur?.byWeekDay, body?.recur?.occurrence, body?.recur?.endDate, body?.recur?.byMonthDay);
        // if existing buffer times
        // delete old and create new ones later on
        if ((oldEvent?.preEventId && body?.bufferTime?.beforeEvent) ||
            (oldEvent?.postEventId && body?.bufferTime?.afterEvent)) {
            // delete buffere times if any
            if (oldEvent?.preEventId) {
                const preEvent = await getEventFromPrimaryKey(oldEvent?.preEventId);
                await deleteGoogleEvent(body?.userId, preEvent?.calendarId, preEvent?.eventId, calIntegration?.clientType);
                await deleteEventGivenId(oldEvent?.preEventId);
            }
            if (oldEvent?.postEventId) {
                const postEvent = await getEventFromPrimaryKey(oldEvent?.postEventId);
                await deleteGoogleEvent(body?.userId, postEvent?.calendarId, postEvent?.eventId, calIntegration?.clientType);
                await deleteEventGivenId(oldEvent?.postEventId);
            }
        }
        // patchGoogleEvent
        const startDateTime = startDate
            ? dayjs(startDate).tz(body?.timezone).format()
            : oldEvent?.startDate;
        const endDateTime = startDateTime && body?.duration
            ? dayjs(startDateTime)
                .tz(body?.timezone)
                .add(body?.duration, 'minute')
                .format()
            : oldEvent?.endDate;
        // need to be updated
        const eventToUpsertLocal = {
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
            eventToUpsertLocal.visibility = body.visibility;
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
        const eventsToUpsert = [];
        const deadlineType = body?.deadlineType ||
            (oldTask?.softDeadline ? 'softDeadline' : 'hardDeadline');
        if (body?.taskList?.length > 0) {
            for (const taskList of body?.taskList) {
                const remindersToUpdateEventId = [];
                if (body?.reminders?.length > 0) {
                    const newReminders = body?.reminders.map((r) => ({
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
                const newPreferredTimeRanges = [];
                for (const timepreference of body?.timePreferences) {
                    if (timepreference.dayOfWeek?.length > 0) {
                        for (const dayOfWeek of timepreference.dayOfWeek) {
                            const newPreferredTimeRange = {
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
                    }
                    else {
                        const newPreferredTimeRange = {
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
                await updateTaskInDbAndEventInGoogle(body?.userId, eventToUpsertLocal?.taskId, calIntegration?.clientType, oldEvent?.calendarId, calendarDoc?.resource, taskList?.tasklistName, taskList?.task, eventToUpsertLocal?.timezone, eventToUpsertLocal?.startDate, oldEvent?.startDate, undefined, deadlineType === 'softDeadline' && body?.dueDate, deadlineType === 'hardDeadline' && body?.dueDate, getTaskStatus(taskList?.status) || oldTask?.status, oldEvent?.id, eventToUpsertLocal?.duration, eventToUpsertLocal?.priority, eventToUpsertLocal?.allDay, body?.reminders, body?.recur?.frequency
                    ? body?.recur
                    : undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, eventToUpsertLocal?.location?.title);
                // add buffer time if any
                if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
                    const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime);
                    if (returnValues?.afterEvent) {
                        const googleResValue = await createGoogleEvent(body?.userId, eventToUpsertLocal?.calendarId, calIntegration?.clientType, returnValues?.afterEvent?.id, returnValues?.afterEvent?.endDate, returnValues?.afterEvent?.startDate, 0, undefined, returnValues?.afterEvent?.sendUpdates, returnValues?.afterEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.afterEvent?.title, returnValues?.afterEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.afterEvent?.guestsCanInviteOthers, returnValues?.afterEvent?.guestsCanModify, returnValues?.afterEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.afterEvent?.transparency, returnValues?.afterEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                        returnValues.afterEvent.id = googleResValue.id;
                        returnValues.afterEvent.eventId = googleResValue.googleEventId;
                        returnValues.newEvent.postEventId = returnValues.afterEvent.id;
                    }
                    if (returnValues?.beforeEvent) {
                        const googleResValue = await createGoogleEvent(body?.userId, eventToUpsertLocal?.calendarId, calIntegration?.clientType, returnValues?.beforeEvent?.id, returnValues?.beforeEvent?.endDate, returnValues?.beforeEvent?.startDate, 0, undefined, returnValues?.beforeEvent?.sendUpdates, returnValues?.beforeEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.beforeEvent?.title, returnValues?.beforeEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.beforeEvent?.guestsCanInviteOthers, returnValues?.beforeEvent?.guestsCanModify, returnValues?.beforeEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.beforeEvent?.transparency, returnValues?.beforeEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
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
                    const searchVector = await convertEventTitleToOpenAIVector(taskList?.task);
                    // train event
                    await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, body?.userId);
                }
            }
        }
        else {
            const remindersToUpdateEventId = [];
            if (body?.reminders?.length > 0) {
                const newReminders = body?.reminders.map((r) => ({
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
            const newPreferredTimeRanges = [];
            for (const timepreference of body?.timePreferences) {
                if (timepreference.dayOfWeek?.length > 0) {
                    for (const dayOfWeek of timepreference.dayOfWeek) {
                        const newPreferredTimeRange = {
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
                }
                else {
                    const newPreferredTimeRange = {
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
            await updateTaskInDbAndEventInGoogle(body?.userId, eventToUpsertLocal?.taskId, calIntegration?.clientType, oldEvent?.calendarId, calendarDoc?.resource, undefined, eventToUpsertLocal?.title, eventToUpsertLocal?.timezone, eventToUpsertLocal?.startDate, oldEvent?.startDate, undefined, body?.deadlineType === 'softDeadline' && body?.dueDate, body?.deadlineType === 'hardDeadline' && body?.dueDate, oldTask?.status, oldEvent?.id, eventToUpsertLocal?.duration, eventToUpsertLocal?.priority, eventToUpsertLocal?.allDay, body?.reminders, body?.recur?.frequency
                ? body?.recur
                : undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, eventToUpsertLocal?.location?.title);
            // add buffer time if any
            if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
                // validate
                if (!calIntegration?.clientType) {
                    throw new Error('no client type inside calendar integration inside create agenda');
                }
                const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime);
                if (returnValues?.afterEvent) {
                    const googleResValue = await createGoogleEvent(body?.userId, eventToUpsertLocal?.calendarId, calIntegration?.clientType, returnValues?.afterEvent?.id, returnValues?.afterEvent?.endDate, returnValues?.afterEvent?.startDate, 0, undefined, returnValues?.afterEvent?.sendUpdates, returnValues?.afterEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.afterEvent?.title, returnValues?.afterEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.afterEvent?.guestsCanInviteOthers, returnValues?.afterEvent?.guestsCanModify, returnValues?.afterEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.afterEvent?.transparency, returnValues?.afterEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                    returnValues.afterEvent.id = googleResValue.id;
                    returnValues.afterEvent.eventId = googleResValue.googleEventId;
                    returnValues.newEvent.postEventId = returnValues.afterEvent.id;
                }
                if (returnValues?.beforeEvent) {
                    const googleResValue = await createGoogleEvent(body?.userId, eventToUpsertLocal?.calendarId, calIntegration?.clientType, returnValues?.beforeEvent?.id, returnValues?.beforeEvent?.endDate, returnValues?.beforeEvent?.startDate, 0, undefined, returnValues?.beforeEvent?.sendUpdates, returnValues?.beforeEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.beforeEvent?.title, returnValues?.beforeEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.beforeEvent?.guestsCanInviteOthers, returnValues?.beforeEvent?.guestsCanModify, returnValues?.beforeEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.beforeEvent?.transparency, returnValues?.beforeEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
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
                await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, body?.userId);
            }
        }
        console.log(eventsToUpsert?.length, ' eventsToUpsert?.length');
        await upsertEvents(eventsToUpsert);
        // success response
        response.query = 'completed';
        response.data = 'successfully  updated task';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step update task');
    }
};
export const processUpdateTaskPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
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
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'updateTask',
        };
        const taskStartDate = extrapolateDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow);
        const taskDueDate = extrapolateDateFromJSONData(currentTime, timezone, yearDue, monthDue, dayDue, isoWeekdayDue, hourDue, minuteDue, startTimeDue, dateJSONBody?.dueDate?.relativeTimeChangeFromNow, dateJSONBody?.dueDate?.relativeTimeFromNow);
        if (dateJSONBody?.duration) {
            duration = dateJSONBody?.duration;
        }
        else if (dateJSONBody?.startTime && dateJSONBody?.endTime) {
            // likely start time also present
            const startTimeObject = dayjs(dateJSONBody?.startTime, 'HH:mm');
            const endTimeObject = dayjs(dateJSONBody.endTime, 'HH:mm');
            const minutes = endTimeObject.diff(startTimeObject, 'm');
            if (minutes > 0) {
                duration = minutes;
            }
        }
        else if (jsonBody?.params?.startTime && jsonBody?.params?.endTime) {
            const startTimeObject = dayjs(jsonBody?.params?.startTime);
            const endTimeObject = dayjs(jsonBody?.params?.endTime);
            const minutes = endTimeObject.diff(startTimeObject, 'm');
            if (minutes > 0) {
                duration = minutes;
            }
        }
        // take care of any recurring dates
        let recurObject = {};
        if (dateJSONBody?.recur?.frequency) {
            const recurEndDate = extrapolateDateFromJSONData(currentTime, timezone, dateJSONBody?.recur?.endDate?.year, dateJSONBody?.recur?.endDate?.month, dateJSONBody?.recur?.endDate?.day, dateJSONBody?.recur?.endDate?.isoWeekday, dateJSONBody?.recur?.endDate?.hour, dateJSONBody?.recur?.endDate?.minute, dateJSONBody?.recur?.endDate?.startTime, dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow, dateJSONBody?.recur?.endDate?.relativeTimeFromNow);
            recurObject = {
                frequency: dateJSONBody?.recur?.frequency ||
                    jsonBody?.params?.recurrence?.frequency,
                interval: dateJSONBody?.recur?.interval ||
                    jsonBody?.params?.recurrence?.interval,
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
        const body = {
            userId,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task,
            oldTitle: jsonBody?.params?.oldTitle,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description || jsonBody?.params?.notes,
            startDate: jsonBody?.params?.startTime || taskStartDate,
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
            isFollowUp: jsonBody?.params?.isFollowUp,
            timezone,
        };
        if (recurObject?.frequency) {
            body.recur = recurObject;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
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
        const response2 = await finalStepUpdateTask(body, startDate, endDate, response);
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
    }
    catch (e) {
        console.log(e, ' unable to process add task');
    }
};
export const processUpdateTaskMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
    try {
        let duration = 0;
        const year = dateJSONBody?.year || messageHistoryObject?.prevDateJsonBody?.year;
        const month = dateJSONBody?.month || messageHistoryObject?.prevDateJsonBody?.month;
        const day = dateJSONBody?.day || messageHistoryObject?.prevDateJsonBody?.day;
        const isoWeekday = dateJSONBody?.isoWeekday ||
            messageHistoryObject?.prevDateJsonBody?.isoWeekday;
        const hour = dateJSONBody?.hour || messageHistoryObject?.prevDateJsonBody?.hour;
        const minute = dateJSONBody?.minute || messageHistoryObject?.prevDateJsonBody?.minute;
        const startTime = dateJSONBody?.startTime ||
            messageHistoryObject?.prevDateJsonBody?.startTime;
        const yearDue = dateJSONBody?.dueDate?.year ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.year;
        const monthDue = dateJSONBody?.dueDate?.month ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.month;
        const dayDue = dateJSONBody?.dueDate?.day ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.day;
        const isoWeekdayDue = dateJSONBody?.dueDate?.isoWeekday ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.isoWeekday;
        const hourDue = dateJSONBody?.dueDate?.hour ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.hour;
        const minuteDue = dateJSONBody?.dueDate?.minute ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.minute;
        const startTimeDue = dateJSONBody?.dueDate?.startTime ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.startTime;
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'updateTask',
        };
        const taskStartDate = extrapolateDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeFromNow);
        const taskDueDate = extrapolateDateFromJSONData(currentTime, timezone, yearDue, monthDue, dayDue, isoWeekdayDue, hourDue, minuteDue, startTimeDue, dateJSONBody?.dueDate?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.dueDate
                ?.relativeTimeChangeFromNow, dateJSONBody?.dueDate?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.dueDate?.relativeTimeFromNow);
        if (dateJSONBody?.duration ||
            messageHistoryObject?.prevDateJsonBody?.duration) {
            duration =
                dateJSONBody?.duration ||
                    messageHistoryObject?.prevDateJsonBody?.duration;
        }
        else if ((dateJSONBody?.startTime ||
            messageHistoryObject?.prevDateJsonBody?.startTime) &&
            (dateJSONBody?.endTime || messageHistoryObject?.prevDateJsonBody?.endTime)) {
            // likely start time also present
            const startTimeObject = dayjs(dateJSONBody?.startTime ||
                messageHistoryObject?.prevDateJsonBody?.startTime, 'HH:mm');
            const endTimeObject = dayjs(dateJSONBody.endTime || messageHistoryObject?.prevDateJsonBody?.endTime, 'HH:mm');
            const minutes = endTimeObject.diff(startTimeObject, 'm');
            if (minutes > 0) {
                duration = minutes;
            }
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
        // take care of any recurring dates
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
            oldTitle: jsonBody?.params?.oldTitle ||
                messageHistoryObject?.prevJsonBody?.params?.oldTitle,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description ||
                jsonBody?.params?.notes ||
                messageHistoryObject?.prevJsonBody?.params?.description ||
                messageHistoryObject?.prevJsonBody?.params?.notes,
            startDate: jsonBody?.params?.startTime ||
                messageHistoryObject?.prevJsonBody?.params?.startTime ||
                taskStartDate,
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
            isFollowUp: jsonBody?.params?.isFollowUp ||
                messageHistoryObject?.prevJsonBody?.params?.isFollowUp,
        };
        if (recurObject?.frequency) {
            newBody.recur = recurObject;
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
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
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
        const prevSearchBoundary = messageHistoryObject?.prevDataExtra?.searchBoundary;
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
        const response2 = await finalStepUpdateTask(prevBody, prevStartDate, prevEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process update task missing fields returned');
    }
};
export const updateTaskControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let updateTaskRes = {
            query: 'completed',
            data: '',
            skill: '',
            prevData: {},
            prevDataExtra: {},
        };
        switch (query) {
            case 'pending':
                const jsonBody = await generateJSONDataFromUserInput(userInput, userCurrentTime);
                const dateTime = await generateDateTime(userInput, userCurrentTime, timezone);
                updateTaskRes = await processUpdateTaskPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                const jsonMissingFieldsBody = await generateMissingFieldsJSONDataFromUserInput(userInput, priorUserInput, priorAssistantOutput, userCurrentTime);
                const dateMissingFieldsTime = await generateMissingFieldsDateTime(userInput, priorUserInput, priorAssistantOutput, userCurrentTime, timezone);
                updateTaskRes = await processUpdateTaskMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (updateTaskRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, updateTaskRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (updateTaskRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, updateTaskRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = updateTaskRes?.data;
            messageHistoryObject.prevData = updateTaskRes?.prevData;
            messageHistoryObject.prevDataExtra = updateTaskRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = updateTaskRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = updateTaskRes?.prevJsonBody;
        }
        else if (updateTaskRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to update task control center pending ');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLGtCQUFrQixFQUNsQixrQkFBa0IsRUFDbEIsaUJBQWlCLEVBQ2pCLGNBQWMsR0FDZixNQUFNLHVCQUF1QixDQUFDO0FBRS9CLE9BQU8sR0FBRyxNQUFNLEtBQUssQ0FBQztBQUN0QixPQUFPLEVBQUUsVUFBVSxFQUFFLE1BQU0sYUFBYSxDQUFDO0FBQ3pDLE9BQU8sRUFBRSxFQUFFLElBQUksSUFBSSxFQUFFLE1BQU0sTUFBTSxDQUFDO0FBQ2xDLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQUt4RCxPQUFPLEVBQ0wsMkJBQTJCLEVBQzNCLCtCQUErQixFQUMvQixpQkFBaUIsRUFDakIsK0JBQStCLEVBQy9CLGlCQUFpQixFQUNqQixrQkFBa0IsRUFDbEIsaUJBQWlCLEVBQ2pCLHNCQUFzQixFQUN0QixtQkFBbUIsRUFDbkIsMkJBQTJCLEVBRTNCLG1EQUFtRCxFQUNuRCxxREFBcUQsRUFDckQsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3Qiw2QkFBNkIsRUFDN0IsMENBQTBDLEVBQzFDLDRCQUE0QixFQUM1QixzQkFBc0IsRUFDdEIsaUJBQWlCLEVBQ2pCLGNBQWMsRUFDZCxlQUFlLEVBQ2YsZ0JBQWdCLEVBQ2hCLG9DQUFvQyxFQUNwQyxZQUFZLEdBQ2IsTUFBTSx3QkFBd0IsQ0FBQztBQWFoQyxPQUFPLGNBQWMsTUFBTSxrQkFBa0IsQ0FBQztBQUU5QyxPQUFPLEVBQUUsYUFBYSxFQUFFLE1BQU0sdUNBQXVDLENBQUM7QUFFdEUsT0FBTyxFQUFFLGlDQUFpQyxFQUFFLE1BQU0sd0NBQXdDLENBQUM7QUFDM0YsT0FBTyxFQUFFLHFDQUFxQyxFQUFFLE1BQU0sc0NBQXNDLENBQUM7QUFXN0Ysb0JBQW9CO0FBQ3BCLE1BQU0sQ0FBQyxNQUFNLDJCQUEyQixHQUFHLEtB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QyxDQUFDLEVBQUUsSUFBSSxJQUFJLEVBQUUsT0FBTyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsbUJBQW1CLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSSxJQUFJLEVBQUUsWUFBWSxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsMkJBQTJCLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSSxJQUFJLEVBQUUsU0FBUyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsc0JBQXNCLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSSxJQUFJLEVBQUUsS0FBSyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsaUJBQWlCLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSSxJQUFJLEVBQUUsS0FBSyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsY0FBYyxDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUksSUFBSSxFQUFFLFFBQVEsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGtCQUFrQixDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUksSUFBSSxFQUFFLFFBQVEsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUksSUFBSSxFQUFFLFlBQVksS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLDJCQUEyQixDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUksSUFBSSxFQUFFLE1BQU0sS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGtCQUFrQixDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUksSUFBSSxFQUFFLFFBQVEsS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLG1CQUFtQixDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUksSUFBSSxFQUFFLElBQUksS0FBSyxTQUFTLENBQUMsQ0FBQyxDQUFDLGVBQWUsQ0FBQyxDQUFDLENBQUMsRUFBRTtrRUFDenZCLElBQUksRUFBRSxhQUFhLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxnQ0FBZ0MsQ0FBQyxDQUFDLENBQUMsRUFBRSxJQUFJLElBQUksRUFBRSxRQUFRLEtBQUss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LENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBnb29nbGVDYWxlbmRhck5hbWUsXG4gIGdvb2dsZVJlc291cmNlTmFtZSxcbiAgaGFzdXJhQWRtaW5TZWNyZXQsXG4gIGhhc3VyYUdyYXBoVXJsLFxufSBmcm9tICdAY2hhdC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgVGFza1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9UYXNrVHlwZSc7XG5pbXBvcnQgZ290IGZyb20gJ2dvdCc7XG5pbXBvcnQgeyBUYXNrU3RhdHVzIH0gZnJvbSAnLi9jb25zdGFudHMnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9kYXRlLXV0aWxzJztcbmltcG9ydCB7XG4gIEV2ZW50VHlwZSxcbiAgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0V2ZW50VHlwZSc7XG5pbXBvcnQge1xuICBhbGxFdmVudFdpdGhEYXRlc09wZW5TZWFyY2gsXG4gIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IsXG4gIGNyZWF0ZUdvb2dsZUV2ZW50LFxuICBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50LFxuICBjcmVhdGVSUnVsZVN0cmluZyxcbiAgZGVsZXRlRXZlbnRHaXZlbklkLFxuICBkZWxldGVHb29nbGVFdmVudCxcbiAgZGVsZXRlUmVtaW5kZXJzV2l0aElkcyxcbiAgZXZlbnRTZWFyY2hCb3VuZGFyeSxcbiAgZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhLFxuICBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyxcbiAgZ2VuZXJhdGVEYXRlVGltZSxcbiAgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lLFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUsXG4gIGdldEV2ZW50RnJvbVByaW1hcnlLZXksXG4gIGdldEdsb2JhbENhbGVuZGFyLFxuICBnZXRUYXNrR2l2ZW5JZCxcbiAgaW5zZXJ0UmVtaW5kZXJzLFxuICBwYXRjaEdvb2dsZUV2ZW50LFxuICBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsXG4gIHVwc2VydEV2ZW50cyxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBDYWxlbmRhclR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9DYWxlbmRhclR5cGUnO1xuaW1wb3J0IHtcbiAgUmVjdXJyZW5jZVJ1bGVUeXBlLFxuICBUcmFuc3BhcmVuY3lUeXBlLFxuICBWaXNpYmlsaXR5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvRXZlbnRUeXBlJztcbmltcG9ydCB7IFJlbWluZGVyVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0dvb2dsZVR5cGVzJztcbmltcG9ydCB7IEdvb2dsZVJlbWluZGVyVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0dvb2dsZVJlbWluZGVyVHlwZSc7XG5pbXBvcnQgRGF0ZVRpbWVKU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9EYXRlVGltZUpTT05KU09OVHlwZSc7XG5pbXBvcnQgVXNlcklucHV0VG9KU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Vc2VySW5wdXRUb0pTT05UeXBlJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCB7IFVwZGF0ZVRhc2tUeXBlIH0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgcmVxdWlyZWRGaWVsZHMgZnJvbSAnLi9yZXF1aXJlZEZpZWxkcyc7XG5pbXBvcnQgUHJlZmVycmVkVGltZVJhbmdlVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9QcmVmZXJyZWRUaW1lUmFuZ2VUeXBlJztcbmltcG9ydCB7IERheU9mV2Vla0VudW0gfSBmcm9tICcuLi9yZXNvbHZlQ29uZmxpY3RpbmdFdmVudHMvY29uc3RhbnRzJztcbmltcG9ydCB7IEdvb2dsZVJlc1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Hb29nbGVSZXNUeXBlJztcbmltcG9ydCB7IHVwc2VydFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCB9IGZyb20gJy4uL3Jlc29sdmVDb25mbGljdGluZ0V2ZW50cy9hcGktaGVscGVyJztcbmltcG9ydCB7IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQgfSBmcm9tICcuLi9yZW1vdmVBbGxQcmVmZXJlZFRpbWVzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgQ2FsZW5kYXJDbGllbnRUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGUnO1xuaW1wb3J0IHtcbiAgQXNzaXN0YW50TWVzc2FnZVR5cGUsXG4gIFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9NZXNzYWdpbmcvTWVzc2FnaW5nVHlwZXMnO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHsgU2VhcmNoQm91bmRhcnlUeXBlIH0gZnJvbSAnLi4vZGVsZXRlVGFzay90eXBlcyc7XG5pbXBvcnQgUmVzcG9uc2VBY3Rpb25UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1Jlc3BvbnNlQWN0aW9uVHlwZSc7XG5pbXBvcnQgaXNvV2VlayBmcm9tICdkYXlqcy9wbHVnaW4vaXNvV2Vlayc7XG5cbi8vIHVwZGF0ZUdvb2dsZUV2ZW50XG5leHBvcnQgY29uc3QgcGF0Y2hHb29nbGVFdmVudEZvclRhc2tMaXN0ID0gYXN5bmMgKFxuICBldmVudElkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjbGllbnRUeXBlOiBDYWxlbmRhckNsaWVudFR5cGUsXG4gIGNhbGVuZGFySWQ6IHN0cmluZyxcbiAgY2FsZW5kYXJSZXNvdXJjZU5hbWU6IHN0cmluZyxcbiAgdGl0bGU/OiBzdHJpbmcsXG4gIGR1cmF0aW9uPzogbnVtYmVyLFxuICB0aW1lem9uZT86IHN0cmluZyxcbiAgc3RhcnREYXRlPzogc3RyaW5nLFxuICBvbGRTdGFydERhdGU/OiBzdHJpbmcsXG4gIGFsbERheT86IGJvb2xlYW4sXG4gIHJlbWluZGVycz86IG51bWJlcltdLFxuICByZWN1ck9iamVjdD86IFJlY3VycmVuY2VSdWxlVHlwZSxcbiAgdHJhbnNwYXJlbmN5PzogVHJhbnNwYXJlbmN5VHlwZSxcbiAgdmlzaWJpbGl0eT86IFZpc2liaWxpdHlUeXBlLFxuICBsb2NhdGlvbj86IHN0cmluZ1xuKTogUHJvbWlzZTx2b2lkPiA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0R2xvYmFsQ2FsZW5kYXJcbiAgICAvLyBsZXQgY2FsZW5kYXJEb2M6IENhbGVuZGFyVHlwZSA9IG51bGxcbiAgICAvLyBjYWxlbmRhckRvYyA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKHVzZXJJZClcblxuICAgIC8vIGdldCBjbGllbnQgdHlwZVxuICAgIC8vIGNvbnN0IGNhbEludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZShcbiAgICAvLyAgICAgdXNlcklkLFxuICAgIC8vICAgICBnb29nbGVDYWxlbmRhck5hbWUsXG4gICAgLy8gKVxuXG4gICAgaWYgKGNhbGVuZGFySWQgJiYgY2FsZW5kYXJSZXNvdXJjZU5hbWUgPT09IGdvb2dsZVJlc291cmNlTmFtZSkge1xuICAgICAgY29uc3Qgc3RhcnREYXRlVGltZSA9IHN0YXJ0RGF0ZVxuICAgICAgICA/IGRheWpzKHN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgpXG4gICAgICAgIDogdW5kZWZpbmVkO1xuICAgICAgY29uc3QgZW5kRGF0ZVRpbWUgPVxuICAgICAgICBzdGFydERhdGVUaW1lICYmIGR1cmF0aW9uXG4gICAgICAgICAgPyBkYXlqcyhzdGFydERhdGVUaW1lKS50eih0aW1lem9uZSkuYWRkKGR1cmF0aW9uLCAnbWludXRlJykuZm9ybWF0KClcbiAgICAgICAgICA6IG9sZFN0YXJ0RGF0ZSAmJiBkdXJhdGlvblxuICAgICAgICAgICAgPyBkYXlqcyhvbGRTdGFydERhdGUpLnR6KHRpbWV6b25lKS5hZGQoZHVyYXRpb24sICdtaW51dGUnKS5mb3JtYXQoKVxuICAgICAgICAgICAgOiB1bmRlZmluZWQ7XG5cbiAgICAgIGNvbnN0IGdvb2dsZVJlbWluZGVyOiBHb29nbGVSZW1pbmRlclR5cGUgPSB7XG4gICAgICAgIG92ZXJyaWRlczogcmVtaW5kZXJzPy5tYXAoKHIpID0+ICh7IG1ldGhvZDogJ2VtYWlsJywgbWludXRlczogciB9KSksXG4gICAgICAgIHVzZURlZmF1bHQ6IGZhbHNlLFxuICAgICAgfTtcblxuICAgICAgLy8gdGFrZSBjYXJlIG9mIHJlY3VycmVuY2VcbiAgICAgIGNvbnN0IHJlY3VyID0gY3JlYXRlUlJ1bGVTdHJpbmcoXG4gICAgICAgIHJlY3VyT2JqZWN0Py5mcmVxdWVuY3ksXG4gICAgICAgIHJlY3VyT2JqZWN0Py5pbnRlcnZhbCxcbiAgICAgICAgcmVjdXJPYmplY3Q/LmJ5V2Vla0RheSxcbiAgICAgICAgcmVjdXJPYmplY3Q/Lm9jY3VycmVuY2UsXG4gICAgICAgIHJlY3VyT2JqZWN0Py5lbmREYXRlLFxuICAgICAgICByZWN1ck9iamVjdD8uYnlNb250aERheVxuICAgICAgKTtcblxuICAgICAgYXdhaXQgcGF0Y2hHb29nbGVFdmVudChcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBjYWxlbmRhcklkLFxuICAgICAgICBldmVudElkLFxuICAgICAgICBjbGllbnRUeXBlLFxuICAgICAgICBlbmREYXRlVGltZSxcbiAgICAgICAgc3RhcnREYXRlVGltZSxcbiAgICAgICAgMCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAnYWxsJyxcbiAgICAgICAgZmFsc2UsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB0aXRsZSxcbiAgICAgICAgdGl0bGUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBhbGxEYXkgJiYgZGF5anMoc3RhcnREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICAgIGFsbERheSAmJlxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmFkZChkdXJhdGlvbiwgJ20nKS5mb3JtYXQoJ1lZWVktTU0tREQnKSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgcmVjdXIsXG4gICAgICAgIHJlbWluZGVycz8ubGVuZ3RoID4gMCA/IGdvb2dsZVJlbWluZGVyIDogdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdHJhbnNwYXJlbmN5LFxuICAgICAgICB2aXNpYmlsaXR5LFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAnZGVmYXVsdCcsXG4gICAgICAgIGxvY2F0aW9uLFxuICAgICAgICB1bmRlZmluZWRcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZygnIGdvb2dsZVBhdGNoIGluc2lkZSB1cGRhdGVEZWFkbGluZUV2ZW50Rm9yVGFza0xpc3QnKTtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwYXRjaCBldmVudCBmb3IgdGFzaycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlVGFza0luRGIgPSBhc3luYyAodGFzazogVGFza1R5cGUpID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgdmFyaWFibGVzOiBhbnkgPSB7IGlkOiB0YXNrPy5pZCB9O1xuXG4gICAgaWYgKHRhc2s/LmNvbXBsZXRlZERhdGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmNvbXBsZXRlZERhdGUgPSB0YXNrPy5jb21wbGV0ZWREYXRlO1xuICAgIH1cblxuICAgIGlmICh0YXNrPy5kdXJhdGlvbiAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuZHVyYXRpb24gPSB0YXNrPy5kdXJhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAodGFzaz8uZXZlbnRJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuZXZlbnRJZCA9IHRhc2s/LmV2ZW50SWQ7XG4gICAgfVxuXG4gICAgaWYgKHRhc2s/LmhhcmREZWFkbGluZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuaGFyZERlYWRsaW5lID0gdGFzaz8uaGFyZERlYWRsaW5lO1xuICAgIH1cblxuICAgIGlmICh0YXNrPy5pbXBvcnRhbnQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmltcG9ydGFudCA9IHRhc2s/LmltcG9ydGFudDtcbiAgICB9XG5cbiAgICBpZiAodGFzaz8ubm90ZXMgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLm5vdGVzID0gdGFzaz8ubm90ZXM7XG4gICAgfVxuXG4gICAgaWYgKHRhc2s/Lm9yZGVyICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5vcmRlciA9IHRhc2s/Lm9yZGVyO1xuICAgIH1cblxuICAgIGlmICh0YXNrPy5wYXJlbnRJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMucGFyZW50SWQgPSB0YXNrPy5wYXJlbnRJZDtcbiAgICB9XG5cbiAgICBpZiAodGFzaz8ucHJpb3JpdHkgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnByaW9yaXR5ID0gdGFzaz8ucHJpb3JpdHk7XG4gICAgfVxuXG4gICAgaWYgKHRhc2s/LnNvZnREZWFkbGluZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuc29mdERlYWRsaW5lID0gdGFzaz8uc29mdERlYWRsaW5lO1xuICAgIH1cblxuICAgIGlmICh0YXNrPy5zdGF0dXMgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnN0YXR1cyA9IHRhc2s/LnN0YXR1cztcbiAgICB9XG5cbiAgICBpZiAodGFzaz8uc3luY0RhdGEgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnN5bmNEYXRhID0gdGFzaz8uc3luY0RhdGE7XG4gICAgfVxuXG4gICAgaWYgKHRhc2s/LnR5cGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnR5cGUgPSB0YXNrPy50eXBlO1xuICAgIH1cblxuICAgIGNvbnN0IHVwZGF0ZVRhc2tCeUlkID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gVXBkYXRlVGFza0J5SWQoJGlkOiB1dWlkISwgJHt0YXNrPy5jb21wbGV0ZWREYXRlICE9PSB1bmRlZmluZWQgPyAnJGNvbXBsZXRlZERhdGU6IHRpbWVzdGFtcHR6LCcgOiAnJ30gJHt0YXNrPy5kdXJhdGlvbiAhPT0gdW5kZWZpbmVkID8gJyRkdXJhdGlvbjogSW50LCcgOiAnJ30gJHt0YXNrPy5ldmVudElkICE9PSB1bmRlZmluZWQgPyAnJGV2ZW50SWQ6IFN0cmluZywnIDogJyd9ICR7dGFzaz8uaGFyZERlYWRsaW5lICE9PSB1bmRlZmluZWQgPyAnJGhhcmREZWFkbGluZTogdGltZXN0YW1wLCcgOiAnJ30gJHt0YXNrPy5pbXBvcnRhbnQgIT09IHVuZGVmaW5lZCA/ICckaW1wb3J0YW50OiBCb29sZWFuLCcgOiAnJ30gJHt0YXNrPy5ub3RlcyAhPT0gdW5kZWZpbmVkID8gJyRub3RlczogU3RyaW5nLCcgOiAnJ30gJHt0YXNrPy5vcmRlciAhPT0gdW5kZWZpbmVkID8gJyRvcmRlcjogSW50LCcgOiAnJ30gJHt0YXNrPy5wYXJlbnRJZCAhPT0gdW5kZWZpbmVkID8gJyRwYXJlbnRJZDogdXVpZCwnIDogJyd9ICR7dGFzaz8ucHJpb3JpdHkgIT09IHVuZGVmaW5lZCA/ICckcHJpb3JpdHk6IEludCwnIDogJyd9ICR7dGFzaz8uc29mdERlYWRsaW5lICE9PSB1bmRlZmluZWQgPyAnJHNvZnREZWFkbGluZTogdGltZXN0YW1wLCcgOiAnJ30gJHt0YXNrPy5zdGF0dXMgIT09IHVuZGVmaW5lZCA/ICckc3RhdHVzOiBTdHJpbmcsJyA6ICcnfSAke3Rhc2s/LnN5bmNEYXRhICE9PSB1bmRlZmluZWQgPyAnJHN5bmNEYXRhOiBqc29uYiwnIDogJyd9ICR7dGFzaz8udHlwZSAhPT0gdW5kZWZpbmVkID8gJyR0eXBlOiBTdHJpbmcnIDogJyd9KXtcbiAgICAgICAgICAgICAgICB1cGRhdGVfVGFza19ieV9wayhwa19jb2x1bW5zOiB7aWQ6ICRpZH0sIF9zZXQ6IHske3Rhc2s/LmNvbXBsZXRlZERhdGUgIT09IHVuZGVmaW5lZCA/ICdjb21wbGV0ZWREYXRlOiAkY29tcGxldGVkRGF0ZSwnIDogJyd9ICR7dGFzaz8uZHVyYXRpb24gIT09IHVuZGVmaW5lZCA/ICdkdXJhdGlvbjogJGR1cmF0aW9uLCcgOiAnJ30gJHt0YXNrPy5ldmVudElkICE9PSB1bmRlZmluZWQgPyAnZXZlbnRJZDogJGV2ZW50SWQsJyA6ICcnfSAke3Rhc2s/LmhhcmREZWFkbGluZSAhPT0gdW5kZWZpbmVkID8gJ2hhcmREZWFkbGluZTogJGhhcmREZWFkbGluZSwnIDogJyd9ICR7dGFzaz8uaW1wb3J0YW50ICE9PSB1bmRlZmluZWQgPyAnaW1wb3J0YW50OiAkaW1wb3J0YW50LCcgOiAnJ30gJHt0YXNrPy5ub3RlcyAhPT0gdW5kZWZpbmVkID8gJ25vdGVzOiAkbm90ZXMsJyA6ICcnfSAke3Rhc2s/Lm9yZGVyICE9PSB1bmRlZmluZWQgPyAnb3JkZXI6ICRvcmRlciwnIDogJyd9ICR7dGFzaz8ucGFyZW50SWQgIT09IHVuZGVmaW5lZCA/ICdwYXJlbnRJZDogJHBhcmVudElkLCcgOiAnJ30gJHt0YXNrPy5wcmlvcml0eSAhPT0gdW5kZWZpbmVkID8gJ3ByaW9yaXR5OiAkcHJpb3JpdHksJyA6ICcnfSAke3Rhc2s/LnNvZnREZWFkbGluZSAhPT0gdW5kZWZpbmVkID8gJ3NvZnREZWFkbGluZTogJHNvZnREZWFkbGluZSwnIDogJyd9ICR7dGFzaz8uc3RhdHVzICE9PSB1bmRlZmluZWQgPyAnc3RhdHVzOiAkc3RhdHVzLCcgOiAnJ30gJHt0YXNrPy5zeW5jRGF0YSAhPT0gdW5kZWZpbmVkID8gJ3N5bmNEYXRhOiAkc3luY0RhdGEsJyA6ICcnfSAke3Rhc2s/LnR5cGUgIT09IHVuZGVmaW5lZCA/ICd0eXBlOiAkdHlwZScgOiAnJ319KSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbXBsZXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaW1wb3J0YW50XG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yZGVyXG4gICAgICAgICAgICAgICAgICAgIHBhcmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHNvZnREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgc3luY0RhdGFcbiAgICAgICAgICAgICAgICAgICAgdHlwZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdVcGRhdGVUYXNrQnlJZCc7XG4gICAgY29uc3QgcXVlcnkgPSB1cGRhdGVUYXNrQnlJZDtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IHVwZGF0ZV9UYXNrX2J5X3BrOiBUYXNrVHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBpbnNpZGUgdXBkYXRlVGFza0luRGInKTtcbiAgICBpZiAocmVzPy5kYXRhPy51cGRhdGVfVGFza19ieV9waykge1xuICAgICAgcmV0dXJuIHJlcz8uZGF0YT8udXBkYXRlX1Rhc2tfYnlfcGs7XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGluc2VydFRhc2tJbkRiJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVUYXNrSW5EYkFuZEV2ZW50SW5Hb29nbGUgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0YXNrSWQ6IHN0cmluZyxcbiAgY2xpZW50VHlwZTogQ2FsZW5kYXJDbGllbnRUeXBlLFxuICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFyUmVzb3VyY2VOYW1lOiBzdHJpbmcsXG4gIHRhc2tMaXN0TmFtZT86IHN0cmluZyxcbiAgdGV4dD86IHN0cmluZyxcbiAgdGltZXpvbmU/OiBzdHJpbmcsXG4gIHN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgb2xkU3RhcnREYXRlPzogc3RyaW5nLFxuICBpbXBvcnRhbnQ/OiBib29sZWFuLFxuICBzb2Z0RGVhZGxpbmU/OiBzdHJpbmcsXG4gIGhhcmREZWFkbGluZT86IHN0cmluZyxcbiAgc3RhdHVzPzogVGFza1N0YXR1cyxcbiAgZXZlbnRJZD86IHN0cmluZyxcbiAgZHVyYXRpb24/OiBudW1iZXIsXG4gIHByaW9yaXR5PzogbnVtYmVyLFxuICBhbGxEYXk/OiBib29sZWFuLFxuICByZW1pbmRlcnM/OiBudW1iZXJbXSxcbiAgcmVjdXJPYmplY3Q/OiBSZWN1cnJlbmNlUnVsZVR5cGUsXG4gIHRyYW5zcGFyZW5jeT86IFRyYW5zcGFyZW5jeVR5cGUsXG4gIHZpc2liaWxpdHk/OiBWaXNpYmlsaXR5VHlwZSxcbiAgbG9jYXRpb24/OiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRvVXBkYXRlVGFzazogVGFza1R5cGUgPSB7XG4gICAgICBpZDogdGFza0lkLFxuICAgICAgdXNlcklkLFxuICAgICAgZXZlbnRJZCxcbiAgICAgIHR5cGU6IHRhc2tMaXN0TmFtZSxcbiAgICAgIG5vdGVzOiB0ZXh0LFxuICAgICAgaW1wb3J0YW50LFxuICAgICAgc3RhdHVzLFxuICAgICAgcHJpb3JpdHksXG4gICAgICBzb2Z0RGVhZGxpbmUsXG4gICAgICBoYXJkRGVhZGxpbmUsXG4gICAgICBkdXJhdGlvbixcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIH07XG5cbiAgICAvLyBjb25zdCBkZWFkbGluZSA9IHNvZnREZWFkbGluZSB8fCBoYXJkRGVhZGxpbmVcblxuICAgIGF3YWl0IHVwZGF0ZVRhc2tJbkRiKHRvVXBkYXRlVGFzayk7XG5cbiAgICBhd2FpdCBwYXRjaEdvb2dsZUV2ZW50Rm9yVGFza0xpc3QoXG4gICAgICBldmVudElkLFxuICAgICAgdXNlcklkLFxuICAgICAgY2xpZW50VHlwZSxcbiAgICAgIGNhbGVuZGFySWQsXG4gICAgICBjYWxlbmRhclJlc291cmNlTmFtZSxcbiAgICAgIHRleHQsXG4gICAgICBkdXJhdGlvbiB8fCAzMCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgc3RhcnREYXRlLFxuICAgICAgb2xkU3RhcnREYXRlLFxuICAgICAgYWxsRGF5LFxuICAgICAgcmVtaW5kZXJzLFxuICAgICAgcmVjdXJPYmplY3QsXG4gICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5LFxuICAgICAgbG9jYXRpb25cbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGluc2VydFRhc2tJbkRiJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRUYXNrU3RhdHVzID0gKHN0YXR1czogJ3RvZG8nIHwgJ2RvaW5nJyB8ICdkb25lJykgPT4ge1xuICBpZiAoIXN0YXR1cykge1xuICAgIHJldHVybjtcbiAgfVxuXG4gIHN3aXRjaCAoc3RhdHVzKSB7XG4gICAgY2FzZSAndG9kbyc6XG4gICAgICByZXR1cm4gVGFza1N0YXR1cy5UT0RPO1xuICAgIGNhc2UgJ2RvaW5nJzpcbiAgICAgIHJldHVybiBUYXNrU3RhdHVzLkRPSU5HO1xuICAgIGNhc2UgJ2RvbmUnOlxuICAgICAgcmV0dXJuIFRhc2tTdGF0dXMuRE9ORTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGZpbmFsU3RlcFVwZGF0ZVRhc2sgPSBhc3luYyAoXG4gIGJvZHk6IFVwZGF0ZVRhc2tUeXBlLFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nLFxuICByZXNwb25zZTogYW55XG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBjb252ZXJ0IHRvIHZlY3RvciBmb3Igc2VhcmNoXG4gICAgY29uc3Qgc2VhcmNoVGl0bGUgPSBib2R5Py5vbGRUaXRsZSB8fCBib2R5Py50aXRsZTtcbiAgICBjb25zdCBzZWFyY2hWZWN0b3IgPSBhd2FpdCBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yKHNlYXJjaFRpdGxlKTtcblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaChcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGVcbiAgICApO1xuXG4gICAgY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkO1xuXG4gICAgLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICBpZiAoIWlkKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50SWQgPSBpZDtcblxuICAgIC8vIGdldCBjbGllbnQgdHlwZVxuICAgIGNvbnN0IGNhbEludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZShcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIGdvb2dsZUNhbGVuZGFyTmFtZVxuICAgICk7XG5cbiAgICAvLyBnZXRHbG9iYWxDYWxlbmRhclxuICAgIGxldCBjYWxlbmRhckRvYzogQ2FsZW5kYXJUeXBlID0gbnVsbDtcbiAgICBjYWxlbmRhckRvYyA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKGJvZHk/LnVzZXJJZCk7XG5cbiAgICAvLyBkZWxldGUgb2xkIHJlbWluZGVyc1xuICAgIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGRlbGV0ZVJlbWluZGVyc1dpdGhJZHMoW2V2ZW50SWRdLCBib2R5Py51c2VySWQpO1xuICAgIH1cblxuICAgIC8vIGRlbGV0ZSBvbGQgdGltZSBwcmVmZXJlbmNlc1xuICAgIGlmIChib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQoZXZlbnRJZCk7XG4gICAgfVxuXG4gICAgLy8gZ2V0IG9sZCBldmVudFxuICAgIGNvbnN0IG9sZEV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShldmVudElkKTtcblxuICAgIC8vIGdldCBvbGQgVGFza1xuICAgIGNvbnN0IG9sZFRhc2sgPSBhd2FpdCBnZXRUYXNrR2l2ZW5JZChvbGRFdmVudD8udGFza0lkKTtcblxuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFvbGRFdmVudD8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gb2xkIGV2ZW50IGZvdW5kPyEnKTtcbiAgICB9XG5cbiAgICAvLyB0YWtlIGNhcmUgb2YgcmVjdXJyZW5jZVxuICAgIGNvbnN0IHJlY3VyID0gY3JlYXRlUlJ1bGVTdHJpbmcoXG4gICAgICBib2R5Py5yZWN1cj8uZnJlcXVlbmN5LFxuICAgICAgYm9keT8ucmVjdXI/LmludGVydmFsLFxuICAgICAgYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAgIGJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlLFxuICAgICAgYm9keT8ucmVjdXI/LmVuZERhdGUsXG4gICAgICBib2R5Py5yZWN1cj8uYnlNb250aERheVxuICAgICk7XG5cbiAgICAvLyBpZiBleGlzdGluZyBidWZmZXIgdGltZXNcbiAgICAvLyBkZWxldGUgb2xkIGFuZCBjcmVhdGUgbmV3IG9uZXMgbGF0ZXIgb25cbiAgICBpZiAoXG4gICAgICAob2xkRXZlbnQ/LnByZUV2ZW50SWQgJiYgYm9keT8uYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQpIHx8XG4gICAgICAob2xkRXZlbnQ/LnBvc3RFdmVudElkICYmIGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQpXG4gICAgKSB7XG4gICAgICAvLyBkZWxldGUgYnVmZmVyZSB0aW1lcyBpZiBhbnlcblxuICAgICAgaWYgKG9sZEV2ZW50Py5wcmVFdmVudElkKSB7XG4gICAgICAgIGNvbnN0IHByZUV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShvbGRFdmVudD8ucHJlRXZlbnRJZCk7XG4gICAgICAgIGF3YWl0IGRlbGV0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICBwcmVFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICBwcmVFdmVudD8uZXZlbnRJZCxcbiAgICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZVxuICAgICAgICApO1xuICAgICAgICBhd2FpdCBkZWxldGVFdmVudEdpdmVuSWQob2xkRXZlbnQ/LnByZUV2ZW50SWQpO1xuICAgICAgfVxuXG4gICAgICBpZiAob2xkRXZlbnQ/LnBvc3RFdmVudElkKSB7XG4gICAgICAgIGNvbnN0IHBvc3RFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkob2xkRXZlbnQ/LnBvc3RFdmVudElkKTtcbiAgICAgICAgYXdhaXQgZGVsZXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIHBvc3RFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICBwb3N0RXZlbnQ/LmV2ZW50SWQsXG4gICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGVcbiAgICAgICAgKTtcbiAgICAgICAgYXdhaXQgZGVsZXRlRXZlbnRHaXZlbklkKG9sZEV2ZW50Py5wb3N0RXZlbnRJZCk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gcGF0Y2hHb29nbGVFdmVudFxuICAgIGNvbnN0IHN0YXJ0RGF0ZVRpbWUgPSBzdGFydERhdGVcbiAgICAgID8gZGF5anMoc3RhcnREYXRlKS50eihib2R5Py50aW1lem9uZSkuZm9ybWF0KClcbiAgICAgIDogb2xkRXZlbnQ/LnN0YXJ0RGF0ZTtcbiAgICBjb25zdCBlbmREYXRlVGltZSA9XG4gICAgICBzdGFydERhdGVUaW1lICYmIGJvZHk/LmR1cmF0aW9uXG4gICAgICAgID8gZGF5anMoc3RhcnREYXRlVGltZSlcbiAgICAgICAgICAgIC50eihib2R5Py50aW1lem9uZSlcbiAgICAgICAgICAgIC5hZGQoYm9keT8uZHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgpXG4gICAgICAgIDogb2xkRXZlbnQ/LmVuZERhdGU7XG4gICAgLy8gbmVlZCB0byBiZSB1cGRhdGVkXG4gICAgY29uc3QgZXZlbnRUb1Vwc2VydExvY2FsOiBFdmVudFR5cGUgPSB7XG4gICAgICAuLi5vbGRFdmVudCxcbiAgICAgIGlkOiBldmVudElkLFxuICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgIH07XG5cbiAgICBpZiAoYm9keT8udGl0bGUpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC50aXRsZSA9IGJvZHk/LnRpdGxlO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnN1bW1hcnkgPSBib2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoc3RhcnREYXRlKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuc3RhcnREYXRlID0gZGF5anMoc3RhcnREYXRlKVxuICAgICAgICAudHooYm9keT8udGltZXpvbmUpXG4gICAgICAgIC5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoZW5kRGF0ZVRpbWUgJiYgZW5kRGF0ZVRpbWUgIT09IG9sZEV2ZW50Py5lbmREYXRlKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuZW5kRGF0ZSA9IGRheWpzKHN0YXJ0RGF0ZVRpbWUpXG4gICAgICAgIC50eihib2R5Py50aW1lem9uZSlcbiAgICAgICAgLmFkZChib2R5Py5kdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgIC5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8uZHVyYXRpb24gJiYgYm9keT8uZHVyYXRpb24gIT09IG9sZEV2ZW50Py5kdXJhdGlvbikge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmR1cmF0aW9uID0gYm9keT8uZHVyYXRpb247XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LmlzRm9sbG93VXApIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5pc0ZvbGxvd1VwID0gYm9keS5pc0ZvbGxvd1VwO1xuICAgIH1cblxuICAgIGlmIChib2R5Py5hbGxEYXkpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5hbGxEYXkgPSBib2R5Py5hbGxEYXk7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwubm90ZXMgPSBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8udGltZXpvbmUpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC50aW1lem9uZSA9IGJvZHk/LnRpbWV6b25lO1xuICAgIH1cblxuICAgIGlmIChib2R5Py5wcmlvcml0eSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnByaW9yaXR5ID0gYm9keS5wcmlvcml0eTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8udHJhbnNwYXJlbmN5KSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwudHJhbnNwYXJlbmN5ID0gYm9keS50cmFuc3BhcmVuY3k7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5ID0gdHJ1ZTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8udmlzaWJpbGl0eSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnZpc2liaWxpdHkgPSBib2R5LnZpc2liaWxpdHkgYXMgVmlzaWJpbGl0eVR5cGU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LmR1cmF0aW9uKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuZHVyYXRpb24gPSBib2R5Py5kdXJhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRpbWVCbG9ja2luZyA9IGJvZHkuYnVmZmVyVGltZTtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcgPSB0cnVlO1xuICAgIH1cblxuICAgIGlmIChib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZSA9IHRydWU7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwubW9kaWZpYWJsZSA9IHRydWU7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkTW9kaWZpYWJsZSA9IHRydWU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFJlbWluZGVycyA9IHRydWU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnByaW9yaXR5ID4gMSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWwgPSB0cnVlO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLm1vZGlmaWFibGUgPSB0cnVlO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZE1vZGlmaWFibGUgPSB0cnVlO1xuICAgIH1cblxuICAgIGlmIChib2R5Py5kdXJhdGlvbikge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZER1cmF0aW9uID0gdHJ1ZTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8ubG9jYXRpb24pIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5sb2NhdGlvbiA9IHsgdGl0bGU6IGJvZHk/LmxvY2F0aW9uIH07XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnJlY3VyKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwucmVjdXJyZW5jZSA9IHJlY3VyO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnJlY3VycmVuY2VSdWxlID0ge1xuICAgICAgICBmcmVxdWVuY3k6IGJvZHk/LnJlY3VyPy5mcmVxdWVuY3ksXG4gICAgICAgIGludGVydmFsOiBib2R5Py5yZWN1cj8uaW50ZXJ2YWwsXG4gICAgICAgIGJ5V2Vla0RheTogYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAgICAgb2NjdXJyZW5jZTogYm9keT8ucmVjdXI/Lm9jY3VycmVuY2UsXG4gICAgICAgIGVuZERhdGU6IGJvZHk/LnJlY3VyPy5lbmREYXRlLFxuICAgICAgICBieU1vbnRoRGF5OiBib2R5Py5yZWN1cj8uYnlNb250aERheSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgZXZlbnRzVG9VcHNlcnQ6IEV2ZW50VHlwZVtdID0gW107XG5cbiAgICBjb25zdCBkZWFkbGluZVR5cGUgPVxuICAgICAgYm9keT8uZGVhZGxpbmVUeXBlIHx8XG4gICAgICAob2xkVGFzaz8uc29mdERlYWRsaW5lID8gJ3NvZnREZWFkbGluZScgOiAnaGFyZERlYWRsaW5lJyk7XG5cbiAgICBpZiAoYm9keT8udGFza0xpc3Q/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGZvciAoY29uc3QgdGFza0xpc3Qgb2YgYm9keT8udGFza0xpc3QpIHtcbiAgICAgICAgY29uc3QgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkOiBSZW1pbmRlclR5cGVbXSA9IFtdO1xuXG4gICAgICAgIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICBjb25zdCBuZXdSZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdID0gYm9keT8ucmVtaW5kZXJzLm1hcCgocikgPT4gKHtcbiAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgICAgICB0aW1lem9uZTogYm9keT8udGltZXpvbmUsXG4gICAgICAgICAgICBtaW51dGVzOiByLFxuICAgICAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgIH0pKTtcblxuICAgICAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZC5wdXNoKC4uLm5ld1JlbWluZGVycyk7XG4gICAgICAgIH1cblxuICAgICAgICAvLyB0aW1lIHByZWZlcmVuY2VzIGFuZCBwcmlvcml0eVxuICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXTtcblxuICAgICAgICBmb3IgKGNvbnN0IHRpbWVwcmVmZXJlbmNlIG9mIGJvZHk/LnRpbWVQcmVmZXJlbmNlcykge1xuICAgICAgICAgIGlmICh0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWs/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIGZvciAoY29uc3QgZGF5T2ZXZWVrIG9mIHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaykge1xuICAgICAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgICAgICBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWw/LmlkLFxuICAgICAgICAgICAgICAgIGRheU9mV2VlazogRGF5T2ZXZWVrRW51bVtkYXlPZldlZWtdLFxuICAgICAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgICB9O1xuXG4gICAgICAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgIH07XG5cbiAgICAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGF3YWl0IHVwZGF0ZVRhc2tJbkRiQW5kRXZlbnRJbkdvb2dsZShcbiAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50YXNrSWQsXG4gICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICAgICAgY2FsZW5kYXJEb2M/LnJlc291cmNlLFxuICAgICAgICAgIHRhc2tMaXN0Py50YXNrbGlzdE5hbWUsXG4gICAgICAgICAgdGFza0xpc3Q/LnRhc2ssXG4gICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50aW1lem9uZSxcbiAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICBvbGRFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICBkZWFkbGluZVR5cGUgPT09ICdzb2Z0RGVhZGxpbmUnICYmIGJvZHk/LmR1ZURhdGUsXG4gICAgICAgICAgZGVhZGxpbmVUeXBlID09PSAnaGFyZERlYWRsaW5lJyAmJiBib2R5Py5kdWVEYXRlLFxuICAgICAgICAgIGdldFRhc2tTdGF0dXModGFza0xpc3Q/LnN0YXR1cykgfHwgb2xkVGFzaz8uc3RhdHVzLFxuICAgICAgICAgIG9sZEV2ZW50Py5pZCxcbiAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmR1cmF0aW9uLFxuICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8ucHJpb3JpdHksXG4gICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5hbGxEYXksXG4gICAgICAgICAgYm9keT8ucmVtaW5kZXJzLFxuICAgICAgICAgIChib2R5Py5yZWN1ciBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5mcmVxdWVuY3lcbiAgICAgICAgICAgID8gKGJvZHk/LnJlY3VyIGFzIFJlY3VycmVuY2VSdWxlVHlwZSlcbiAgICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udmlzaWJpbGl0eSxcbiAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmxvY2F0aW9uPy50aXRsZVxuICAgICAgICApO1xuXG4gICAgICAgIC8vIGFkZCBidWZmZXIgdGltZSBpZiBhbnlcbiAgICAgICAgaWYgKGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQgfHwgYm9keT8uYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgICBjb25zdCByZXR1cm5WYWx1ZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50KFxuICAgICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLFxuICAgICAgICAgICAgYm9keT8uYnVmZmVyVGltZVxuICAgICAgICAgICk7XG5cbiAgICAgICAgICBpZiAocmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50KSB7XG4gICAgICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uaWQsXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZW5kRGF0ZSxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zdGFydERhdGUsXG4gICAgICAgICAgICAgIDAsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zZW5kVXBkYXRlcyxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50aXRsZSxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZFxuICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuICAgICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnBvc3RFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQ7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5jYWxlbmRhcklkLFxuICAgICAgICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uaWQsXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICAgICAgMCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zZW5kVXBkYXRlcyxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRpdGxlLFxuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgICAnZGVmYXVsdCcsXG4gICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcbiAgICAgICAgICAgIHJldHVyblZhbHVlcy5uZXdFdmVudC5wcmVFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQ7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgZXZlbnRzVG9VcHNlcnQucHVzaChcbiAgICAgICAgICAgIC4uLltcbiAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LFxuICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQsXG4gICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQsXG4gICAgICAgICAgICBdPy5maWx0ZXIoKGUpID0+ICEhZSlcbiAgICAgICAgICApO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIGV2ZW50c1RvVXBzZXJ0LnB1c2goZXZlbnRUb1Vwc2VydExvY2FsKTtcbiAgICAgICAgfVxuXG4gICAgICAgIC8vIGluc2VydCByZW1pbmRlcnNcbiAgICAgICAgaWYgKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgIGF3YWl0IGluc2VydFJlbWluZGVycyhyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQpO1xuICAgICAgICB9XG5cbiAgICAgICAgLy8gaW5zZXJ0IHRpbWUgcHJlZmVyZW5jZXNcbiAgICAgICAgaWYgKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcyk7XG4gICAgICAgIH1cblxuICAgICAgICAvLyBjb252ZXJ0IHRvIHZlY3RvciBmb3Igc2VhcmNoXG4gICAgICAgIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwIHx8IGJvZHk/LnByaW9yaXR5ID4gMSkge1xuICAgICAgICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoXG4gICAgICAgICAgICB0YXNrTGlzdD8udGFza1xuICAgICAgICAgICk7XG5cbiAgICAgICAgICAvLyB0cmFpbiBldmVudFxuICAgICAgICAgIGF3YWl0IHB1dERhdGFJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaChcbiAgICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgICBzZWFyY2hWZWN0b3IsXG4gICAgICAgICAgICBib2R5Py51c2VySWRcbiAgICAgICAgICApO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnN0IHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZDogUmVtaW5kZXJUeXBlW10gPSBbXTtcblxuICAgICAgaWYgKGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBjb25zdCBuZXdSZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdID0gYm9keT8ucmVtaW5kZXJzLm1hcCgocikgPT4gKHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgICAgdGltZXpvbmU6IGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgIG1pbnV0ZXM6IHIsXG4gICAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICB9KSk7XG5cbiAgICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkLnB1c2goLi4ubmV3UmVtaW5kZXJzKTtcbiAgICAgIH1cblxuICAgICAgLy8gdGltZSBwcmVmZXJlbmNlcyBhbmQgcHJpb3JpdHlcbiAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSA9IFtdO1xuXG4gICAgICBmb3IgKGNvbnN0IHRpbWVwcmVmZXJlbmNlIG9mIGJvZHk/LnRpbWVQcmVmZXJlbmNlcykge1xuICAgICAgICBpZiAodGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgZm9yIChjb25zdCBkYXlPZldlZWsgb2YgdGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrKSB7XG4gICAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgICAgICAgIGRheU9mV2VlazogRGF5T2ZXZWVrRW51bVtkYXlPZldlZWtdLFxuICAgICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAgICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgICB9O1xuXG4gICAgICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgIH07XG5cbiAgICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKTtcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBhd2FpdCB1cGRhdGVUYXNrSW5EYkFuZEV2ZW50SW5Hb29nbGUoXG4gICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50YXNrSWQsXG4gICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgY2FsZW5kYXJEb2M/LnJlc291cmNlLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udGl0bGUsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udGltZXpvbmUsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3RhcnREYXRlLFxuICAgICAgICBvbGRFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGJvZHk/LmRlYWRsaW5lVHlwZSA9PT0gJ3NvZnREZWFkbGluZScgJiYgYm9keT8uZHVlRGF0ZSxcbiAgICAgICAgYm9keT8uZGVhZGxpbmVUeXBlID09PSAnaGFyZERlYWRsaW5lJyAmJiBib2R5Py5kdWVEYXRlLFxuICAgICAgICBvbGRUYXNrPy5zdGF0dXMsXG4gICAgICAgIG9sZEV2ZW50Py5pZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5kdXJhdGlvbixcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5wcmlvcml0eSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5hbGxEYXksXG4gICAgICAgIGJvZHk/LnJlbWluZGVycyxcbiAgICAgICAgKGJvZHk/LnJlY3VyIGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeVxuICAgICAgICAgID8gKGJvZHk/LnJlY3VyIGFzIFJlY3VycmVuY2VSdWxlVHlwZSlcbiAgICAgICAgICA6IHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50cmFuc3BhcmVuY3ksXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udmlzaWJpbGl0eSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5sb2NhdGlvbj8udGl0bGVcbiAgICAgICk7XG5cbiAgICAgIC8vIGFkZCBidWZmZXIgdGltZSBpZiBhbnlcbiAgICAgIGlmIChib2R5Py5idWZmZXJUaW1lPy5hZnRlckV2ZW50IHx8IGJvZHk/LmJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50KSB7XG4gICAgICAgIC8vIHZhbGlkYXRlXG4gICAgICAgIGlmICghY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpIHtcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICAgICAgICAnbm8gY2xpZW50IHR5cGUgaW5zaWRlIGNhbGVuZGFyIGludGVncmF0aW9uIGluc2lkZSBjcmVhdGUgYWdlbmRhJ1xuICAgICAgICAgICk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXR1cm5WYWx1ZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50KFxuICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbCxcbiAgICAgICAgICBib2R5Py5idWZmZXJUaW1lXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCkge1xuICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmNhbGVuZGFySWQsXG4gICAgICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uaWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICAgIDAsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50aXRsZSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8ubm90ZXMsXG4gICAgICAgICAgICBib2R5Py50aW1lem9uZSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICAnZGVmYXVsdCcsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWRcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucG9zdEV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZDtcbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChyZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50KSB7XG4gICAgICAgICAgY29uc3QgZ29vZ2xlUmVzVmFsdWU6IEdvb2dsZVJlc1R5cGUgPSBhd2FpdCBjcmVhdGVHb29nbGVFdmVudChcbiAgICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uaWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgICAgMCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRpdGxlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8ubm90ZXMsXG4gICAgICAgICAgICBib2R5Py50aW1lem9uZSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZFxuICAgICAgICAgICk7XG5cbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnByZUV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZDtcbiAgICAgICAgfVxuXG4gICAgICAgIGV2ZW50c1RvVXBzZXJ0LnB1c2goXG4gICAgICAgICAgLi4uW1xuICAgICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudCxcbiAgICAgICAgICBdPy5maWx0ZXIoKGUpID0+ICEhZSlcbiAgICAgICAgKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGV2ZW50c1RvVXBzZXJ0LnB1c2goZXZlbnRUb1Vwc2VydExvY2FsKTtcbiAgICAgIH1cblxuICAgICAgLy8gaW5zZXJ0IHJlbWluZGVyc1xuICAgICAgaWYgKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCkge1xuICAgICAgICBhd2FpdCBpbnNlcnRSZW1pbmRlcnMocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkKTtcbiAgICAgIH1cblxuICAgICAgLy8gaW5zZXJ0IHRpbWUgcHJlZmVyZW5jZXNcbiAgICAgIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGF3YWl0IHVwc2VydFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzKTtcbiAgICAgIH1cblxuICAgICAgLy8gY29udmVydCB0byB2ZWN0b3IgZm9yIHNlYXJjaFxuICAgICAgaWYgKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDAgfHwgYm9keT8ucHJpb3JpdHkgPiAxKSB7XG4gICAgICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuXG4gICAgICAgIC8vIHRyYWluIGV2ZW50XG4gICAgICAgIGF3YWl0IHB1dERhdGFJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaChcbiAgICAgICAgICBldmVudElkLFxuICAgICAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgICAgICBib2R5Py51c2VySWRcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhldmVudHNUb1Vwc2VydD8ubGVuZ3RoLCAnIGV2ZW50c1RvVXBzZXJ0Py5sZW5ndGgnKTtcblxuICAgIGF3YWl0IHVwc2VydEV2ZW50cyhldmVudHNUb1Vwc2VydCk7XG5cbiAgICAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICByZXNwb25zZS5kYXRhID0gJ3N1Y2Nlc3NmdWxseSAgdXBkYXRlZCB0YXNrJztcbiAgICByZXR1cm4gcmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBmaW5hbCBzdGVwIHVwZGF0ZSB0YXNrJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzVXBkYXRlVGFza1BlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgZHVyYXRpb24gPSAwO1xuXG4gICAgY29uc3QgeWVhciA9IGRhdGVKU09OQm9keT8ueWVhcjtcbiAgICBjb25zdCBtb250aCA9IGRhdGVKU09OQm9keT8ubW9udGg7XG4gICAgY29uc3QgZGF5ID0gZGF0ZUpTT05Cb2R5Py5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheSA9IGRhdGVKU09OQm9keT8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyID0gZGF0ZUpTT05Cb2R5Py5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZSA9IGRhdGVKU09OQm9keT8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZSA9IGRhdGVKU09OQm9keT8uc3RhcnRUaW1lO1xuXG4gICAgY29uc3QgeWVhckR1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8ueWVhcjtcbiAgICBjb25zdCBtb250aER1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8ubW9udGg7XG4gICAgY29uc3QgZGF5RHVlID0gZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheUR1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyRHVlID0gZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZUR1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZUR1ZSA9IGRhdGVKU09OQm9keT8uZHVlRGF0ZT8uc3RhcnRUaW1lO1xuXG4gICAgY29uc3QgbWlzc2luZ0ZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICAgICAgcmVxdWlyZWQ6IFtdLFxuICAgICAgZGF0ZVRpbWU6IHsgcmVxdWlyZWQ6IFtdIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAndXBkYXRlVGFzaycsXG4gICAgfTtcblxuICAgIGNvbnN0IHRhc2tTdGFydERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhcixcbiAgICAgIG1vbnRoLFxuICAgICAgZGF5LFxuICAgICAgaXNvV2Vla2RheSxcbiAgICAgIGhvdXIsXG4gICAgICBtaW51dGUsXG4gICAgICBzdGFydFRpbWUsXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgY29uc3QgdGFza0R1ZURhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhckR1ZSxcbiAgICAgIG1vbnRoRHVlLFxuICAgICAgZGF5RHVlLFxuICAgICAgaXNvV2Vla2RheUR1ZSxcbiAgICAgIGhvdXJEdWUsXG4gICAgICBtaW51dGVEdWUsXG4gICAgICBzdGFydFRpbWVEdWUsXG4gICAgICBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgaWYgKGRhdGVKU09OQm9keT8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKGRhdGVKU09OQm9keT8uc3RhcnRUaW1lICYmIGRhdGVKU09OQm9keT8uZW5kVGltZSkge1xuICAgICAgLy8gbGlrZWx5IHN0YXJ0IHRpbWUgYWxzbyBwcmVzZW50XG5cbiAgICAgIGNvbnN0IHN0YXJ0VGltZU9iamVjdCA9IGRheWpzKGRhdGVKU09OQm9keT8uc3RhcnRUaW1lLCAnSEg6bW0nKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhkYXRlSlNPTkJvZHkuZW5kVGltZSwgJ0hIOm1tJyk7XG5cbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH0gZWxzZSBpZiAoanNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lICYmIGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUpIHtcbiAgICAgIGNvbnN0IHN0YXJ0VGltZU9iamVjdCA9IGRheWpzKGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSk7XG4gICAgICBjb25zdCBlbmRUaW1lT2JqZWN0ID0gZGF5anMoanNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSk7XG4gICAgICBjb25zdCBtaW51dGVzID0gZW5kVGltZU9iamVjdC5kaWZmKHN0YXJ0VGltZU9iamVjdCwgJ20nKTtcblxuICAgICAgaWYgKG1pbnV0ZXMgPiAwKSB7XG4gICAgICAgIGR1cmF0aW9uID0gbWludXRlcztcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyB0YWtlIGNhcmUgb2YgYW55IHJlY3VycmluZyBkYXRlc1xuICAgIGxldCByZWN1ck9iamVjdDogUmVjdXJyZW5jZVJ1bGVUeXBlIHwge30gPSB7fTtcbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5KSB7XG4gICAgICBjb25zdCByZWN1ckVuZERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhcixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGgsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91cixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubWludXRlLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5zdGFydFRpbWUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICAgICk7XG5cbiAgICAgIHJlY3VyT2JqZWN0ID0ge1xuICAgICAgICBmcmVxdWVuY3k6XG4gICAgICAgICAgKGRhdGVKU09OQm9keT8ucmVjdXI/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSkgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5mcmVxdWVuY3ksXG4gICAgICAgIGludGVydmFsOlxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uaW50ZXJ2YWwsXG4gICAgICB9O1xuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5KSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5V2Vla0RheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieU1vbnRoRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5vY2N1cnJlbmNlID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlO1xuICAgICAgfVxuXG4gICAgICBpZiAocmVjdXJFbmREYXRlIHx8IGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuZW5kRGF0ZSA9XG4gICAgICAgICAgcmVjdXJFbmREYXRlIHx8IGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGU7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgYm9keTogVXBkYXRlVGFza1R5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgb2xkVGl0bGU6IGpzb25Cb2R5Py5wYXJhbXM/Lm9sZFRpdGxlLFxuICAgICAgbWV0aG9kOiBkYXRlSlNPTkJvZHk/Lm1ldGhvZCBhcyBhbnksXG4gICAgICBkdXJhdGlvbixcbiAgICAgIGRlc2NyaXB0aW9uOiBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fCBqc29uQm9keT8ucGFyYW1zPy5ub3RlcyxcbiAgICAgIHN0YXJ0RGF0ZToganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8IHRhc2tTdGFydERhdGUsXG4gICAgICBkdWVEYXRlOiB0YXNrRHVlRGF0ZSB8fCAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uZW5kRGF0ZSxcbiAgICAgIGJ1ZmZlclRpbWU6IGpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUsXG4gICAgICByZW1pbmRlcnM6IGpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fCBbXSxcbiAgICAgIHByaW9yaXR5OiBqc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fCAxLFxuICAgICAgdGltZVByZWZlcmVuY2VzOiBkYXRlSlNPTkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fCBbXSxcbiAgICAgIGxvY2F0aW9uOiBqc29uQm9keT8ucGFyYW1zPy5sb2NhdGlvbixcbiAgICAgIHRyYW5zcGFyZW5jeToganNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eToganNvbkJvZHk/LnBhcmFtcy52aXNpYmlsaXR5IGFzIFZpc2liaWxpdHlUeXBlLFxuICAgICAgaXNCcmVhazoganNvbkJvZHk/LnBhcmFtcz8uaXNCcmVhayxcbiAgICAgIGFsbERheTogZGF0ZUpTT05Cb2R5Py5hbGxEYXksXG4gICAgICBkZWFkbGluZVR5cGU6IGpzb25Cb2R5Py5wYXJhbXM/LmRlYWRsaW5lVHlwZSxcbiAgICAgIHRhc2tMaXN0OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8ubWFwKCh0bCkgPT4gKHtcbiAgICAgICAgICAuLi50bCxcbiAgICAgICAgICB0YXNrbGlzdE5hbWU6IHRsPy50YXNrbGlzdE5hbWU/LnRvTG93ZXJDYXNlKCksXG4gICAgICAgIH0pKSB8fCBbXSxcbiAgICAgIGlzRm9sbG93VXA6IGpzb25Cb2R5Py5wYXJhbXM/LmlzRm9sbG93VXAsXG4gICAgICB0aW1lem9uZSxcbiAgICB9O1xuXG4gICAgaWYgKFxuICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZVxuICAgICkge1xuICAgICAgYm9keS5yZWN1ciA9IHJlY3VyT2JqZWN0IGFzIGFueTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCBzZWFyY2hCb3VuZGFyeSA9IGV2ZW50U2VhcmNoQm91bmRhcnkoXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGRhdGVKU09OQm9keSxcbiAgICAgIGN1cnJlbnRUaW1lXG4gICAgKTtcblxuICAgIGxldCBzdGFydERhdGUgPSBzZWFyY2hCb3VuZGFyeS5zdGFydERhdGU7XG4gICAgbGV0IGVuZERhdGUgPSBzZWFyY2hCb3VuZGFyeS5lbmREYXRlO1xuXG4gICAgLy8gIGFsbEV2ZW50V2l0aEV2ZW50T3BlblNlYXJjaFxuICAgIC8vIGFsbEV2ZW50T3BlblNlYXJjaFxuICAgIGlmICghc3RhcnREYXRlKSB7XG4gICAgICBzdGFydERhdGUgPSBkYXlqcygpLnN1YnRyYWN0KDIsICd3JykuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgaWYgKCFlbmREYXRlKSB7XG4gICAgICBlbmREYXRlID0gZGF5anMoKS5hZGQoNCwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICAvLyB2YWxpZGF0ZSByZW1haW5pbmcgcmVxdWlyZWQgZmllbGRzXG4gICAgaWYgKCFib2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwVXBkYXRlVGFzayhcbiAgICAgIGJvZHksXG4gICAgICBzdGFydERhdGUsXG4gICAgICBlbmREYXRlLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcblxuICAgIC8vIGNvbnZlcnQgdG8gdmVjdG9yIGZvciBzZWFyY2hcbiAgICAvLyBjb25zdCBzZWFyY2hUaXRsZSA9IGJvZHk/Lm9sZFRpdGxlIHx8IGJvZHk/LnRpdGxlXG4gICAgLy8gY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcihzZWFyY2hUaXRsZSlcblxuICAgIC8vIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaCh1c2VySWQsIHNlYXJjaFZlY3Rvciwgc3RhcnREYXRlLCBlbmREYXRlKVxuXG4gICAgLy8gY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkXG5cbiAgICAvLyAvLyB2YWxpZGF0ZSBmb3VuZCBldmVudFxuICAgIC8vIGlmICghaWQpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJ1xuICAgIC8vICAgICByZXR1cm4gcmVzcG9uc2VcbiAgICAvLyB9XG5cbiAgICAvLyBjb25zdCBldmVudElkID0gaWRcblxuICAgIC8vIC8vIGdldCBjbGllbnQgdHlwZVxuICAgIC8vIGNvbnN0IGNhbEludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZShcbiAgICAvLyAgICAgdXNlcklkLFxuICAgIC8vICAgICBnb29nbGVDYWxlbmRhck5hbWUsXG4gICAgLy8gKVxuXG4gICAgLy8gLy8gZ2V0R2xvYmFsQ2FsZW5kYXJcbiAgICAvLyBsZXQgY2FsZW5kYXJEb2M6IENhbGVuZGFyVHlwZSA9IG51bGxcbiAgICAvLyBjYWxlbmRhckRvYyA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKHVzZXJJZClcblxuICAgIC8vIC8vIGRlbGV0ZSBvbGQgcmVtaW5kZXJzXG4gICAgLy8gaWYgKGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuXG4gICAgLy8gICAgIGF3YWl0IGRlbGV0ZVJlbWluZGVyc1dpdGhJZHMoW2V2ZW50SWRdLCB1c2VySWQpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gZGVsZXRlIG9sZCB0aW1lIHByZWZlcmVuY2VzXG4gICAgLy8gaWYgKGJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICBhd2FpdCBkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkKGV2ZW50SWQpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gZ2V0IG9sZCBldmVudFxuICAgIC8vIGNvbnN0IG9sZEV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShldmVudElkKVxuXG4gICAgLy8gLy8gZ2V0IG9sZCBUYXNrXG4gICAgLy8gY29uc3Qgb2xkVGFzayA9IGF3YWl0IGdldFRhc2tHaXZlbklkKG9sZEV2ZW50Py50YXNrSWQpXG5cbiAgICAvLyAvLyB2YWxpZGF0ZVxuICAgIC8vIGlmICghb2xkRXZlbnQ/LmlkKSB7XG4gICAgLy8gICAgIHRocm93IG5ldyBFcnJvcignbm8gb2xkIGV2ZW50IGZvdW5kPyEnKVxuICAgIC8vIH1cblxuICAgIC8vIC8vIHRha2UgY2FyZSBvZiByZWN1cnJlbmNlXG4gICAgLy8gY29uc3QgcmVjdXIgPSBjcmVhdGVSUnVsZVN0cmluZyhib2R5Py5yZWN1cj8uZnJlcXVlbmN5LCBib2R5Py5yZWN1cj8uaW50ZXJ2YWwsIGJvZHk/LnJlY3VyPy5ieVdlZWtEYXksIGJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlLCBib2R5Py5yZWN1cj8uZW5kRGF0ZSwgYm9keT8ucmVjdXI/LmJ5TW9udGhEYXkpXG5cbiAgICAvLyAvLyBpZiBleGlzdGluZyBidWZmZXIgdGltZXNcbiAgICAvLyAvLyBkZWxldGUgb2xkIGFuZCBjcmVhdGUgbmV3IG9uZXMgbGF0ZXIgb25cbiAgICAvLyBpZiAoKG9sZEV2ZW50Py5wcmVFdmVudElkICYmIGJvZHk/LmJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50KSB8fCAob2xkRXZlbnQ/LnBvc3RFdmVudElkICYmIGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQpKSB7XG4gICAgLy8gICAgIC8vIGRlbGV0ZSBidWZmZXJlIHRpbWVzIGlmIGFueVxuXG4gICAgLy8gICAgIGlmIChvbGRFdmVudD8ucHJlRXZlbnRJZCkge1xuICAgIC8vICAgICAgICAgY29uc3QgcHJlRXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KG9sZEV2ZW50Py5wcmVFdmVudElkKVxuICAgIC8vICAgICAgICAgYXdhaXQgZGVsZXRlR29vZ2xlRXZlbnQodXNlcklkLCBwcmVFdmVudD8uY2FsZW5kYXJJZCwgcHJlRXZlbnQ/LmV2ZW50SWQsIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlKVxuICAgIC8vICAgICAgICAgYXdhaXQgZGVsZXRlRXZlbnRHaXZlbklkKG9sZEV2ZW50Py5wcmVFdmVudElkKVxuXG4gICAgLy8gICAgIH1cblxuICAgIC8vICAgICBpZiAob2xkRXZlbnQ/LnBvc3RFdmVudElkKSB7XG5cbiAgICAvLyAgICAgICAgIGNvbnN0IHBvc3RFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkob2xkRXZlbnQ/LnBvc3RFdmVudElkKVxuICAgIC8vICAgICAgICAgYXdhaXQgZGVsZXRlR29vZ2xlRXZlbnQodXNlcklkLCBwb3N0RXZlbnQ/LmNhbGVuZGFySWQsIHBvc3RFdmVudD8uZXZlbnRJZCwgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpXG4gICAgLy8gICAgICAgICBhd2FpdCBkZWxldGVFdmVudEdpdmVuSWQob2xkRXZlbnQ/LnBvc3RFdmVudElkKVxuICAgIC8vICAgICB9XG4gICAgLy8gfVxuXG4gICAgLy8gLy8gcGF0Y2hHb29nbGVFdmVudFxuICAgIC8vIGNvbnN0IHN0YXJ0RGF0ZVRpbWUgPSBzdGFydERhdGUgPyBkYXlqcyhzdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoKSA6IG9sZEV2ZW50Py5zdGFydERhdGVcbiAgICAvLyBjb25zdCBlbmREYXRlVGltZSA9IChzdGFydERhdGVUaW1lICYmIGR1cmF0aW9uKSA/IGRheWpzKHN0YXJ0RGF0ZVRpbWUpLnR6KHRpbWV6b25lKS5hZGQoZHVyYXRpb24sICdtaW51dGUnKS5mb3JtYXQoKVxuICAgIC8vICAgICA6IG9sZEV2ZW50Py5lbmREYXRlXG4gICAgLy8gLy8gbmVlZCB0byBiZSB1cGRhdGVkXG4gICAgLy8gY29uc3QgZXZlbnRUb1Vwc2VydExvY2FsOiBFdmVudFR5cGUgPSB7XG4gICAgLy8gICAgIC4uLm9sZEV2ZW50LFxuICAgIC8vICAgICBpZDogZXZlbnRJZCxcbiAgICAvLyAgICAgdXNlcklkLFxuICAgIC8vICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGU6IHRydWUsXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnRpdGxlKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC50aXRsZSA9IGJvZHk/LnRpdGxlXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5zdW1tYXJ5ID0gYm9keT8udGl0bGVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoc3RhcnREYXRlKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5zdGFydERhdGUgPSBkYXlqcyhzdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoKVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChlbmREYXRlVGltZSAmJiAoZW5kRGF0ZVRpbWUgIT09IG9sZEV2ZW50Py5lbmREYXRlKSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwuZW5kRGF0ZSA9IGRheWpzKHN0YXJ0RGF0ZVRpbWUpLnR6KHRpbWV6b25lKS5hZGQoZHVyYXRpb24sICdtaW51dGUnKS5mb3JtYXQoKVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChkdXJhdGlvbiAmJiAoZHVyYXRpb24gIT09IG9sZEV2ZW50Py5kdXJhdGlvbikpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmR1cmF0aW9uID0gZHVyYXRpb25cbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8uaXNGb2xsb3dVcCkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwuaXNGb2xsb3dVcCA9IGJvZHkuaXNGb2xsb3dVcFxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5hbGxEYXkpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmFsbERheSA9IGJvZHk/LmFsbERheVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwubm90ZXMgPSBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py50aW1lem9uZSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudGltZXpvbmUgPSBib2R5Py50aW1lem9uZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5wcmlvcml0eSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwucHJpb3JpdHkgPSBib2R5LnByaW9yaXR5XG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudHJhbnNwYXJlbmN5ID0gYm9keS50cmFuc3BhcmVuY3lcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eSA9IHRydWVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8udmlzaWJpbGl0eSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudmlzaWJpbGl0eSA9IGJvZHkudmlzaWJpbGl0eSBhcyBWaXNpYmlsaXR5VHlwZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5kdXJhdGlvbikge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwuZHVyYXRpb24gPSBkdXJhdGlvblxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5idWZmZXJUaW1lKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC50aW1lQmxvY2tpbmcgPSBib2R5LmJ1ZmZlclRpbWVcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFRpbWVCbG9ja2luZyA9IHRydWVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZSA9IHRydWVcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLm1vZGlmaWFibGUgPSB0cnVlXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRNb2RpZmlhYmxlID0gdHJ1ZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFJlbWluZGVycyA9IHRydWVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8ucHJpb3JpdHkgPiAxKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsID0gdHJ1ZVxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwubW9kaWZpYWJsZSA9IHRydWVcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZE1vZGlmaWFibGUgPSB0cnVlXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LmR1cmF0aW9uKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWREdXJhdGlvbiA9IHRydWVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8ubG9jYXRpb24pIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmxvY2F0aW9uID0geyB0aXRsZTogYm9keT8ubG9jYXRpb24gfVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5yZWN1cikge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwucmVjdXJyZW5jZSA9IHJlY3VyXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5yZWN1cnJlbmNlUnVsZSA9IHtcbiAgICAvLyAgICAgICAgIGZyZXF1ZW5jeTogYm9keT8ucmVjdXI/LmZyZXF1ZW5jeSxcbiAgICAvLyAgICAgICAgIGludGVydmFsOiBib2R5Py5yZWN1cj8uaW50ZXJ2YWwsXG4gICAgLy8gICAgICAgICBieVdlZWtEYXk6IGJvZHk/LnJlY3VyPy5ieVdlZWtEYXksXG4gICAgLy8gICAgICAgICBvY2N1cnJlbmNlOiBib2R5Py5yZWN1cj8ub2NjdXJyZW5jZSxcbiAgICAvLyAgICAgICAgIGVuZERhdGU6IGJvZHk/LnJlY3VyPy5lbmREYXRlLFxuICAgIC8vICAgICAgICAgYnlNb250aERheTogYm9keT8ucmVjdXI/LmJ5TW9udGhEYXksXG4gICAgLy8gICAgIH1cbiAgICAvLyB9XG5cbiAgICAvLyBjb25zdCBldmVudHNUb1Vwc2VydDogRXZlbnRUeXBlW10gPSBbXVxuXG4gICAgLy8gY29uc3QgZGVhZGxpbmVUeXBlID0gYm9keT8uZGVhZGxpbmVUeXBlIHx8IChvbGRUYXNrPy5zb2Z0RGVhZGxpbmUgPyAnc29mdERlYWRsaW5lJyA6ICdoYXJkRGVhZGxpbmUnKVxuXG4gICAgLy8gaWYgKGJvZHk/LnRhc2tMaXN0Py5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgIGZvciAoY29uc3QgdGFza0xpc3Qgb2YgYm9keT8udGFza0xpc3QpIHtcblxuICAgIC8vICAgICAgICAgY29uc3QgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkOiBSZW1pbmRlclR5cGVbXSA9IFtdXG5cbiAgICAvLyAgICAgICAgIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgICAgICAgICBjb25zdCBuZXdSZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdID0gYm9keT8ucmVtaW5kZXJzLm1hcChyID0+ICh7XG4gICAgLy8gICAgICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgLy8gICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgZXZlbnRJZDogZXZlbnRUb1Vwc2VydExvY2FsPy5pZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgLy8gICAgICAgICAgICAgICAgIG1pbnV0ZXM6IHIsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVzZURlZmF1bHQ6IGZhbHNlLFxuICAgIC8vICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAvLyAgICAgICAgICAgICB9KSlcblxuICAgIC8vICAgICAgICAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZC5wdXNoKC4uLm5ld1JlbWluZGVycylcbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgLy8gdGltZSBwcmVmZXJlbmNlcyBhbmQgcHJpb3JpdHlcbiAgICAvLyAgICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSA9IFtdXG5cbiAgICAvLyAgICAgICAgIGZvciAoY29uc3QgdGltZXByZWZlcmVuY2Ugb2YgYm9keT8udGltZVByZWZlcmVuY2VzKSB7XG5cbiAgICAvLyAgICAgICAgICAgICBpZiAodGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGZvciAoY29uc3QgZGF5T2ZXZWVrIG9mIHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWw/LmlkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIGRheU9mV2VlazogRGF5T2ZXZWVrRW51bVtkYXlPZldlZWtdLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSlcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpXG4gICAgLy8gICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIGF3YWl0IHVwZGF0ZVRhc2tJbkRiQW5kRXZlbnRJbkdvb2dsZShcbiAgICAvLyAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50YXNrSWQsXG4gICAgLy8gICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgLy8gICAgICAgICAgICAgb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICAgICAgY2FsZW5kYXJEb2M/LnJlc291cmNlLFxuICAgIC8vICAgICAgICAgICAgIHRhc2tMaXN0Py50YXNrbGlzdE5hbWUsXG4gICAgLy8gICAgICAgICAgICAgdGFza0xpc3Q/LnRhc2ssXG4gICAgLy8gICAgICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50aW1lem9uZSxcbiAgICAvLyAgICAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICBvbGRFdmVudD8uc3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAoZGVhZGxpbmVUeXBlID09PSAnc29mdERlYWRsaW5lJykgJiYgYm9keT8uZHVlRGF0ZSxcbiAgICAvLyAgICAgICAgICAgICAoZGVhZGxpbmVUeXBlID09PSAnaGFyZERlYWRsaW5lJykgJiYgYm9keT8uZHVlRGF0ZSxcbiAgICAvLyAgICAgICAgICAgICBnZXRUYXNrU3RhdHVzKHRhc2tMaXN0Py5zdGF0dXMpIHx8IG9sZFRhc2s/LnN0YXR1cyxcbiAgICAvLyAgICAgICAgICAgICBvbGRFdmVudD8uaWQsXG4gICAgLy8gICAgICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5kdXJhdGlvbixcbiAgICAvLyAgICAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnByaW9yaXR5LFxuICAgIC8vICAgICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uYWxsRGF5LFxuICAgIC8vICAgICAgICAgICAgIGJvZHk/LnJlbWluZGVycyxcbiAgICAvLyAgICAgICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uZnJlcXVlbmN5ID8gcmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlIDogdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udHJhbnNwYXJlbmN5LFxuICAgIC8vICAgICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udmlzaWJpbGl0eSxcbiAgICAvLyAgICAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmxvY2F0aW9uPy50aXRsZSxcbiAgICAvLyAgICAgICAgIClcblxuICAgIC8vICAgICAgICAgLy8gYWRkIGJ1ZmZlciB0aW1lIGlmIGFueVxuICAgIC8vICAgICAgICAgaWYgKGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQgfHwgYm9keT8uYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQpIHtcblxuICAgIC8vICAgICAgICAgICAgIGNvbnN0IHJldHVyblZhbHVlcyA9IGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGcm9tRXZlbnQoZXZlbnRUb1Vwc2VydExvY2FsLCBib2R5Py5idWZmZXJUaW1lKVxuXG4gICAgLy8gICAgICAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCkge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uaWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmVuZERhdGUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIDAsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50aXRsZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8ubm90ZXMsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py52aXNpYmlsaXR5LFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICApXG5cbiAgICAvLyAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucG9zdEV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZFxuXG4gICAgLy8gICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdXNlcklkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5jYWxlbmRhcklkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5pZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAwLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udGl0bGUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAnZGVmYXVsdCcsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIClcblxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWRcbiAgICAvLyAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnByZUV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZFxuXG4gICAgLy8gICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICAgICAgZXZlbnRzVG9VcHNlcnQucHVzaCguLi4oW3JldHVyblZhbHVlcy5uZXdFdmVudCwgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50LCByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50XT8uZmlsdGVyKGUgPT4gISFlKSkpXG4gICAgLy8gICAgICAgICB9IGVsc2Uge1xuICAgIC8vICAgICAgICAgICAgIGV2ZW50c1RvVXBzZXJ0LnB1c2goZXZlbnRUb1Vwc2VydExvY2FsKVxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICAvLyBpbnNlcnQgcmVtaW5kZXJzXG4gICAgLy8gICAgICAgICBpZiAocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgICAgICAgICAgYXdhaXQgaW5zZXJ0UmVtaW5kZXJzKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZClcbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgLy8gaW5zZXJ0IHRpbWUgcHJlZmVyZW5jZXNcbiAgICAvLyAgICAgICAgIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgICAgICAgICAgYXdhaXQgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMpXG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIC8vIGNvbnZlcnQgdG8gdmVjdG9yIGZvciBzZWFyY2hcbiAgICAvLyAgICAgICAgIGlmICgobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkgfHwgYm9keT8ucHJpb3JpdHkgPiAxKSB7XG5cbiAgICAvLyAgICAgICAgICAgICBjb25zdCBzZWFyY2hWZWN0b3IgPSBhd2FpdCBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yKHRhc2tMaXN0Py50YXNrKVxuXG4gICAgLy8gICAgICAgICAgICAgLy8gdHJhaW4gZXZlbnRcbiAgICAvLyAgICAgICAgICAgICBhd2FpdCBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2goZXZlbnRJZCwgc2VhcmNoVmVjdG9yLCB1c2VySWQpXG4gICAgLy8gICAgICAgICB9XG4gICAgLy8gICAgIH1cbiAgICAvLyB9IGVsc2Uge1xuXG4gICAgLy8gICAgIGNvbnN0IHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZDogUmVtaW5kZXJUeXBlW10gPSBbXVxuXG4gICAgLy8gICAgIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgICAgIGNvbnN0IG5ld1JlbWluZGVyczogUmVtaW5kZXJUeXBlW10gPSBib2R5Py5yZW1pbmRlcnMubWFwKHIgPT4gKHtcbiAgICAvLyAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgIC8vICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWw/LmlkLFxuICAgIC8vICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgIC8vICAgICAgICAgICAgIG1pbnV0ZXM6IHIsXG4gICAgLy8gICAgICAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgLy8gICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIC8vICAgICAgICAgfSkpXG5cbiAgICAvLyAgICAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZC5wdXNoKC4uLm5ld1JlbWluZGVycylcbiAgICAvLyAgICAgfVxuXG4gICAgLy8gICAgIC8vIHRpbWUgcHJlZmVyZW5jZXMgYW5kIHByaW9yaXR5XG4gICAgLy8gICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSA9IFtdXG5cbiAgICAvLyAgICAgZm9yIChjb25zdCB0aW1lcHJlZmVyZW5jZSBvZiBib2R5Py50aW1lUHJlZmVyZW5jZXMpIHtcblxuICAgIC8vICAgICAgICAgaWYgKHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICAgICAgICAgIGZvciAoY29uc3QgZGF5T2ZXZWVrIG9mIHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWw/LmlkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgZGF5T2ZXZWVrOiBEYXlPZldlZWtFbnVtW2RheU9mV2Vla10sXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpXG4gICAgLy8gICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgfSBlbHNlIHtcblxuICAgIC8vICAgICAgICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAvLyAgICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZXZlbnRJZDogZXZlbnRUb1Vwc2VydExvY2FsPy5pZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKVxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgIH1cblxuICAgIC8vICAgICBhd2FpdCB1cGRhdGVUYXNrSW5EYkFuZEV2ZW50SW5Hb29nbGUoXG4gICAgLy8gICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRhc2tJZCxcbiAgICAvLyAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgIC8vICAgICAgICAgb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICBjYWxlbmRhckRvYz8ucmVzb3VyY2UsXG4gICAgLy8gICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRpdGxlLFxuICAgIC8vICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50aW1lem9uZSxcbiAgICAvLyAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgb2xkRXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgIChib2R5Py5kZWFkbGluZVR5cGUgPT09ICdzb2Z0RGVhZGxpbmUnKSAmJiBib2R5Py5kdWVEYXRlLFxuICAgIC8vICAgICAgICAgKGJvZHk/LmRlYWRsaW5lVHlwZSA9PT0gJ2hhcmREZWFkbGluZScpICYmIGJvZHk/LmR1ZURhdGUsXG4gICAgLy8gICAgICAgICBvbGRUYXNrPy5zdGF0dXMsXG4gICAgLy8gICAgICAgICBvbGRFdmVudD8uaWQsXG4gICAgLy8gICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmR1cmF0aW9uLFxuICAgIC8vICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5wcmlvcml0eSxcbiAgICAvLyAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uYWxsRGF5LFxuICAgIC8vICAgICAgICAgYm9keT8ucmVtaW5kZXJzLFxuICAgIC8vICAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSA/IHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSA6IHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udHJhbnNwYXJlbmN5LFxuICAgIC8vICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy52aXNpYmlsaXR5LFxuICAgIC8vICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5sb2NhdGlvbj8udGl0bGUsXG4gICAgLy8gICAgIClcblxuICAgIC8vICAgICAvLyBhZGQgYnVmZmVyIHRpbWUgaWYgYW55XG4gICAgLy8gICAgIGlmIChib2R5Py5idWZmZXJUaW1lPy5hZnRlckV2ZW50IHx8IGJvZHk/LmJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50KSB7XG5cbiAgICAvLyAgICAgICAgIC8vIHZhbGlkYXRlXG4gICAgLy8gICAgICAgICBpZiAoIWNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlKSB7XG4gICAgLy8gICAgICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBjbGllbnQgdHlwZSBpbnNpZGUgY2FsZW5kYXIgaW50ZWdyYXRpb24gaW5zaWRlIGNyZWF0ZSBhZ2VuZGEnKVxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICBjb25zdCByZXR1cm5WYWx1ZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50KGV2ZW50VG9VcHNlcnRMb2NhbCwgYm9keT8uYnVmZmVyVGltZSlcblxuICAgIC8vICAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCkge1xuXG4gICAgLy8gICAgICAgICAgICAgY29uc3QgZ29vZ2xlUmVzVmFsdWU6IEdvb2dsZVJlc1R5cGUgPSBhd2FpdCBjcmVhdGVHb29nbGVFdmVudChcbiAgICAvLyAgICAgICAgICAgICAgICAgdXNlcklkLFxuICAgIC8vICAgICAgICAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmlkLFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmVuZERhdGUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgICAgICAgICAwLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udGl0bGUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8ubm90ZXMsXG4gICAgLy8gICAgICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAvLyAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8ub3JpZ2luYWxTdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAvLyAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py52aXNpYmlsaXR5LFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICAnZGVmYXVsdCcsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIClcblxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkID0gZ29vZ2xlUmVzVmFsdWUuaWRcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcy5uZXdFdmVudC5wb3N0RXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkXG5cbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQpIHtcblxuICAgIC8vICAgICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgLy8gICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5jYWxlbmRhcklkLFxuICAgIC8vICAgICAgICAgICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uaWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgMCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zZW5kVXBkYXRlcyxcbiAgICAvLyAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRpdGxlLFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAvLyAgICAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAvLyAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAvLyAgICAgICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8ub3JpZ2luYWxTdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgLy8gICAgICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAvLyAgICAgICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgKVxuXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzLmJlZm9yZUV2ZW50LmlkID0gZ29vZ2xlUmVzVmFsdWUuaWRcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWRcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucHJlRXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkXG5cbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgZXZlbnRzVG9VcHNlcnQucHVzaCguLi4oW3JldHVyblZhbHVlcy5uZXdFdmVudCwgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50LCByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50XT8uZmlsdGVyKGUgPT4gISFlKSkpXG4gICAgLy8gICAgIH0gZWxzZSB7XG4gICAgLy8gICAgICAgICBldmVudHNUb1Vwc2VydC5wdXNoKGV2ZW50VG9VcHNlcnRMb2NhbClcbiAgICAvLyAgICAgfVxuXG4gICAgLy8gICAgIC8vIGluc2VydCByZW1pbmRlcnNcbiAgICAvLyAgICAgaWYgKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICAgICAgYXdhaXQgaW5zZXJ0UmVtaW5kZXJzKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZClcbiAgICAvLyAgICAgfVxuXG4gICAgLy8gICAgIC8vIGluc2VydCB0aW1lIHByZWZlcmVuY2VzXG4gICAgLy8gICAgIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcylcbiAgICAvLyAgICAgfVxuXG4gICAgLy8gICAgIC8vIGNvbnZlcnQgdG8gdmVjdG9yIGZvciBzZWFyY2hcbiAgICAvLyAgICAgaWYgKChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB8fCBib2R5Py5wcmlvcml0eSA+IDEpIHtcblxuICAgIC8vICAgICAgICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSlcblxuICAgIC8vICAgICAgICAgLy8gdHJhaW4gZXZlbnRcbiAgICAvLyAgICAgICAgIGF3YWl0IHB1dERhdGFJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaChldmVudElkLCBzZWFyY2hWZWN0b3IsIHVzZXJJZClcbiAgICAvLyAgICAgfVxuICAgIC8vIH1cblxuICAgIC8vIGNvbnNvbGUubG9nKGV2ZW50c1RvVXBzZXJ0Py5sZW5ndGgsICcgZXZlbnRzVG9VcHNlcnQ/Lmxlbmd0aCcpXG5cbiAgICAvLyBhd2FpdCB1cHNlcnRFdmVudHMoZXZlbnRzVG9VcHNlcnQpXG5cbiAgICAvLyAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgLy8gcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJ1xuXG4gICAgLy8gcmV0dXJuIHJlc3BvbnNlXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGFkZCB0YXNrJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzVXBkYXRlVGFza01pc3NpbmdGaWVsZHNSZXR1cm5lZCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICBkYXRlSlNPTkJvZHk6IERhdGVUaW1lSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IGR1cmF0aW9uID0gMDtcblxuICAgIGNvbnN0IHllYXIgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py55ZWFyIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py55ZWFyO1xuICAgIGNvbnN0IG1vbnRoID1cbiAgICAgIGRhdGVKU09OQm9keT8ubW9udGggfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/Lm1vbnRoO1xuICAgIGNvbnN0IGRheSA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmRheSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXkgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5pc29XZWVrZGF5IHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyID1cbiAgICAgIGRhdGVKU09OQm9keT8uaG91ciB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uaG91cjtcbiAgICBjb25zdCBtaW51dGUgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5taW51dGUgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWUgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5zdGFydFRpbWU7XG5cbiAgICBjb25zdCB5ZWFyRHVlID1cbiAgICAgIGRhdGVKU09OQm9keT8uZHVlRGF0ZT8ueWVhciB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1ZURhdGU/LnllYXI7XG4gICAgY29uc3QgbW9udGhEdWUgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5tb250aCB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1ZURhdGU/Lm1vbnRoO1xuICAgIGNvbnN0IGRheUR1ZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LmRheSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1ZURhdGU/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5RHVlID1cbiAgICAgIGRhdGVKU09OQm9keT8uZHVlRGF0ZT8uaXNvV2Vla2RheSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1ZURhdGU/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ckR1ZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/LmhvdXIgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kdWVEYXRlPy5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZUR1ZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmR1ZURhdGU/Lm1pbnV0ZSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1ZURhdGU/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWVEdWUgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdWVEYXRlPy5zdGFydFRpbWUgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kdWVEYXRlPy5zdGFydFRpbWU7XG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgICBkYXRlVGltZTogeyByZXF1aXJlZDogW10gfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICd1cGRhdGVUYXNrJyxcbiAgICB9O1xuXG4gICAgY29uc3QgdGFza1N0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB5ZWFyLFxuICAgICAgbW9udGgsXG4gICAgICBkYXksXG4gICAgICBpc29XZWVrZGF5LFxuICAgICAgaG91cixcbiAgICAgIG1pbnV0ZSxcbiAgICAgIHN0YXJ0VGltZSxcbiAgICAgIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBjb25zdCB0YXNrRHVlRGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB5ZWFyRHVlLFxuICAgICAgbW9udGhEdWUsXG4gICAgICBkYXlEdWUsXG4gICAgICBpc29XZWVrZGF5RHVlLFxuICAgICAgaG91ckR1ZSxcbiAgICAgIG1pbnV0ZUR1ZSxcbiAgICAgIHN0YXJ0VGltZUR1ZSxcbiAgICAgIGRhdGVKU09OQm9keT8uZHVlRGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZHVlRGF0ZVxuICAgICAgICAgID8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8uZHVlRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZHVlRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBpZiAoXG4gICAgICBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZHVyYXRpb25cbiAgICApIHtcbiAgICAgIGR1cmF0aW9uID1cbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZHVyYXRpb247XG4gICAgfSBlbHNlIGlmIChcbiAgICAgIChkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uc3RhcnRUaW1lKSAmJlxuICAgICAgKGRhdGVKU09OQm9keT8uZW5kVGltZSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZW5kVGltZSlcbiAgICApIHtcbiAgICAgIC8vIGxpa2VseSBzdGFydCB0aW1lIGFsc28gcHJlc2VudFxuXG4gICAgICBjb25zdCBzdGFydFRpbWVPYmplY3QgPSBkYXlqcyhcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uc3RhcnRUaW1lLFxuICAgICAgICAnSEg6bW0nXG4gICAgICApO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBkYXRlSlNPTkJvZHkuZW5kVGltZSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZW5kVGltZSxcbiAgICAgICAgJ0hIOm1tJ1xuICAgICAgKTtcblxuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChcbiAgICAgIChqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUpICYmXG4gICAgICAoanNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUpXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydFRpbWVPYmplY3QgPSBkYXlqcyhcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWVcbiAgICAgICk7XG4gICAgICBjb25zdCBlbmRUaW1lT2JqZWN0ID0gZGF5anMoXG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWVcbiAgICAgICk7XG4gICAgICBjb25zdCBtaW51dGVzID0gZW5kVGltZU9iamVjdC5kaWZmKHN0YXJ0VGltZU9iamVjdCwgJ20nKTtcblxuICAgICAgaWYgKG1pbnV0ZXMgPiAwKSB7XG4gICAgICAgIGR1cmF0aW9uID0gbWludXRlcztcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyB0YWtlIGNhcmUgb2YgYW55IHJlY3VycmluZyBkYXRlc1xuICAgIGxldCByZWN1ck9iamVjdDogUmVjdXJyZW5jZVJ1bGVUeXBlIHwge30gPSB7fTtcbiAgICBpZiAoXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5XG4gICAgKSB7XG4gICAgICBjb25zdCByZWN1ckVuZERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhciB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhcixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGggfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1vbnRoLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5kYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91ciB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91cixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubWludXRlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uc3RhcnRUaW1lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlXG4gICAgICAgICAgICA/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGVcbiAgICAgICAgICAgID8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICAgKTtcblxuICAgICAgcmVjdXJPYmplY3QgPSB7XG4gICAgICAgIGZyZXF1ZW5jeTpcbiAgICAgICAgICAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlKSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5mcmVxdWVuY3kgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5mcmVxdWVuY3ksXG4gICAgICAgIGludGVydmFsOlxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCxcbiAgICAgIH07XG5cbiAgICAgIGlmIChcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5XG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlXZWVrRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5V2Vla0RheTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlNb250aERheVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5TW9udGhEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5TW9udGhEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/Lm9jY3VycmVuY2VcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5vY2N1cnJlbmNlID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlO1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIHJlY3VyRW5kRGF0ZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmVuZERhdGUgPVxuICAgICAgICAgIHJlY3VyRW5kRGF0ZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGU7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgbmV3Qm9keTogVXBkYXRlVGFza1R5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2sgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBvbGRUaXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ub2xkVGl0bGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5vbGRUaXRsZSxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgZHVyYXRpb24sXG4gICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ubm90ZXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzLFxuICAgICAgc3RhcnREYXRlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgdGFza1N0YXJ0RGF0ZSxcbiAgICAgIGR1ZURhdGU6IHRhc2tEdWVEYXRlIHx8IChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5lbmREYXRlLFxuICAgICAgYnVmZmVyVGltZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYnVmZmVyVGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUsXG4gICAgICByZW1pbmRlcnM6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fFxuICAgICAgICBbXSxcbiAgICAgIHByaW9yaXR5OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8XG4gICAgICAgIDEsXG4gICAgICB0aW1lUHJlZmVyZW5jZXM6XG4gICAgICAgIGRhdGVKU09OQm9keT8udGltZVByZWZlcmVuY2VzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py50aW1lUHJlZmVyZW5jZXMgfHxcbiAgICAgICAgW10sXG4gICAgICBsb2NhdGlvbjpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5sb2NhdGlvbixcbiAgICAgIHRyYW5zcGFyZW5jeTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eTpcbiAgICAgICAgKGpzb25Cb2R5Py5wYXJhbXMudmlzaWJpbGl0eSBhcyBWaXNpYmlsaXR5VHlwZSkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy52aXNpYmlsaXR5LFxuICAgICAgaXNCcmVhazpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uaXNCcmVhayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmlzQnJlYWssXG4gICAgICBhbGxEYXk6XG4gICAgICAgIGRhdGVKU09OQm9keT8uYWxsRGF5IHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5hbGxEYXksXG4gICAgICBkZWFkbGluZVR5cGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlYWRsaW5lVHlwZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlYWRsaW5lVHlwZSxcbiAgICAgIHRhc2tMaXN0OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8ubWFwKCh0bCkgPT4gKHtcbiAgICAgICAgICAuLi50bCxcbiAgICAgICAgICB0YXNrbGlzdE5hbWU6IHRsPy50YXNrbGlzdE5hbWU/LnRvTG93ZXJDYXNlKCksXG4gICAgICAgIH0pKSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5tYXAoKHRsKSA9PiAoe1xuICAgICAgICAgIC4uLnRsLFxuICAgICAgICAgIHRhc2tsaXN0TmFtZTogdGw/LnRhc2tsaXN0TmFtZT8udG9Mb3dlckNhc2UoKSxcbiAgICAgICAgfSkpIHx8XG4gICAgICAgIFtdLFxuICAgICAgaXNGb2xsb3dVcDpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uaXNGb2xsb3dVcCB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmlzRm9sbG93VXAsXG4gICAgfTtcblxuICAgIGlmIChcbiAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbiAgICApIHtcbiAgICAgIG5ld0JvZHkucmVjdXIgPSByZWN1ck9iamVjdCBhcyBhbnk7XG4gICAgfVxuXG4gICAgY29uc3QgcHJldkJvZHk6IFVwZGF0ZVRhc2tUeXBlID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ub2xkVGl0bGUpIHtcbiAgICAgIHByZXZCb2R5Lm9sZFRpdGxlID0gbmV3Qm9keT8ub2xkVGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZHVyYXRpb24pIHtcbiAgICAgIHByZXZCb2R5LmR1cmF0aW9uID0gbmV3Qm9keT8uZHVyYXRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZGVzY3JpcHRpb24pIHtcbiAgICAgIHByZXZCb2R5LmRlc2NyaXB0aW9uID0gbmV3Qm9keT8uZGVzY3JpcHRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uc3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS5zdGFydERhdGUgPSBuZXdCb2R5Py5zdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZHVlRGF0ZSkge1xuICAgICAgcHJldkJvZHkuZHVlRGF0ZSA9IG5ld0JvZHk/LmR1ZURhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgcHJldkJvZHkuYnVmZmVyVGltZSA9IG5ld0JvZHk/LmJ1ZmZlclRpbWU7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnJlbWluZGVycyA9IG5ld0JvZHk/LnJlbWluZGVycyB8fCBbXTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5wcmlvcml0eSkge1xuICAgICAgcHJldkJvZHkucHJpb3JpdHkgPSBuZXdCb2R5Py5wcmlvcml0eTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkudGltZVByZWZlcmVuY2VzID0gbmV3Qm9keT8udGltZVByZWZlcmVuY2VzO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmxvY2F0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5sb2NhdGlvbiA9IG5ld0JvZHk/LmxvY2F0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgcHJldkJvZHkudHJhbnNwYXJlbmN5ID0gbmV3Qm9keT8udHJhbnNwYXJlbmN5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIHByZXZCb2R5LnZpc2liaWxpdHkgPSBuZXdCb2R5Py52aXNpYmlsaXR5O1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5pc0JyZWFrID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHByZXZCb2R5LmlzQnJlYWsgPSBuZXdCb2R5Py5pc0JyZWFrO1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5hbGxEYXkgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuYWxsRGF5ID0gbmV3Qm9keT8uYWxsRGF5O1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5kZWFkbGluZVR5cGUgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuZGVhZGxpbmVUeXBlID0gbmV3Qm9keT8uZGVhZGxpbmVUeXBlO1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS50YXNrTGlzdCA9PT0gdW5kZWZpbmVkKSB7XG4gICAgICBwcmV2Qm9keS50YXNrTGlzdCA9IG5ld0JvZHk/LnRhc2tMaXN0O1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5pc0ZvbGxvd1VwID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHByZXZCb2R5LmlzRm9sbG93VXAgPSBuZXdCb2R5Py5pc0ZvbGxvd1VwO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnJlY3VyKSB7XG4gICAgICBwcmV2Qm9keS5yZWN1ciA9IG5ld0JvZHk/LnJlY3VyO1xuICAgIH1cblxuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICAvLyAgYWxsRXZlbnRXaXRoRXZlbnRPcGVuU2VhcmNoXG4gICAgLy8gYWxsRXZlbnRPcGVuU2VhcmNoXG4gICAgaWYgKCFzdGFydERhdGUpIHtcbiAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIWVuZERhdGUpIHtcbiAgICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IHByZXZTZWFyY2hCb3VuZGFyeTogU2VhcmNoQm91bmRhcnlUeXBlID1cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy5zZWFyY2hCb3VuZGFyeTtcblxuICAgIGxldCBwcmV2U3RhcnREYXRlID0gcHJldlNlYXJjaEJvdW5kYXJ5Py5zdGFydERhdGU7XG5cbiAgICBsZXQgcHJldkVuZERhdGUgPSBwcmV2U2VhcmNoQm91bmRhcnk/LmVuZERhdGU7XG5cbiAgICBpZiAoIXByZXZTdGFydERhdGUpIHtcbiAgICAgIHByZXZTdGFydERhdGUgPSBzdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2RW5kRGF0ZSkge1xuICAgICAgcHJldkVuZERhdGUgPSBlbmREYXRlO1xuICAgIH1cblxuICAgIC8vIGlmICghcHJldkJvZHk/LnN0YXJ0RGF0ZSAmJiAhZGF5ICYmICFpc29XZWVrZGF5KSB7XG4gICAgLy8gICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJ1xuICAgIC8vICAgICBtaXNzaW5nRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQ/LlswXSlcbiAgICAvLyAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHNcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgIC8vICAgICAgICAgc2VhcmNoQm91bmRhcnk6IHtcbiAgICAvLyAgICAgICAgICAgICBzdGFydERhdGU6IHByZXZTdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgZW5kRGF0ZTogcHJldkVuZERhdGUsXG4gICAgLy8gICAgICAgICB9LFxuICAgIC8vICAgICB9XG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5XG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHlcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoIXByZXZCb2R5Py5zdGFydERhdGUgJiYgKGhvdXIgPT09IG51bGwpICYmIChtaW51dGUgPT09IG51bGwpICYmICFzdGFydFRpbWUpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnXG4gICAgLy8gICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzFdKVxuICAgIC8vICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkc1xuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5XG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgLy8gICAgICAgICBzZWFyY2hCb3VuZGFyeToge1xuICAgIC8vICAgICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAvLyAgICAgICAgIH0sXG4gICAgLy8gICAgIH1cbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHlcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keVxuICAgIC8vIH1cblxuICAgIC8vIHZhbGlkYXRlIHJlbWFpbmluZyByZXF1aXJlZCBmaWVsZHNcbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgc2VhcmNoQm91bmRhcnk6IHtcbiAgICAgICAgICBzdGFydERhdGU6IHByZXZTdGFydERhdGUsXG4gICAgICAgICAgZW5kRGF0ZTogcHJldkVuZERhdGUsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcFVwZGF0ZVRhc2soXG4gICAgICBwcmV2Qm9keSxcbiAgICAgIHByZXZTdGFydERhdGUsXG4gICAgICBwcmV2RW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIHVwZGF0ZSB0YXNrIG1pc3NpbmcgZmllbGRzIHJldHVybmVkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVUYXNrQ29udHJvbENlbnRlciA9IGFzeW5jIChcbiAgb3BlbmFpOiBPcGVuQUksXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG4gIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuICBxdWVyeTogJ21pc3NpbmdfZmllbGRzJyB8ICdjb21wbGV0ZWQnIHwgJ2V2ZW50X25vdF9mb3VuZCcgfCAncGVuZGluZydcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG1lc3NhZ2VMZW5ndGggPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcz8ubGVuZ3RoO1xuICAgIGxldCB1c2VyTWVzc2FnZSA9ICcnO1xuICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgdXNlck1lc3NhZ2UgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHVzZXJJbnB1dCA9IHVzZXJNZXNzYWdlO1xuXG4gICAgbGV0IHVwZGF0ZVRhc2tSZXM6IFJlc3BvbnNlQWN0aW9uVHlwZSA9IHtcbiAgICAgIHF1ZXJ5OiAnY29tcGxldGVkJyxcbiAgICAgIGRhdGE6ICcnLFxuICAgICAgc2tpbGw6ICcnLFxuICAgICAgcHJldkRhdGE6IHt9LFxuICAgICAgcHJldkRhdGFFeHRyYToge30sXG4gICAgfTtcblxuICAgIHN3aXRjaCAocXVlcnkpIHtcbiAgICAgIGNhc2UgJ3BlbmRpbmcnOlxuICAgICAgICBjb25zdCBqc29uQm9keSA9IGF3YWl0IGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZVRpbWUgPSBhd2FpdCBnZW5lcmF0ZURhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgdXBkYXRlVGFza1JlcyA9IGF3YWl0IHByb2Nlc3NVcGRhdGVUYXNrUGVuZGluZyhcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbkJvZHksXG4gICAgICAgICAgZGF0ZVRpbWUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnbWlzc2luZ19maWVsZHMnOlxuICAgICAgICBsZXQgcHJpb3JVc2VySW5wdXQgPSAnJztcbiAgICAgICAgbGV0IHByaW9yQXNzaXN0YW50T3V0cHV0ID0gJyc7XG5cbiAgICAgICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ2Fzc2lzdGFudCcpIHtcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgICAgICBpZiAobWVzc2FnZS5jb250ZW50ICE9PSB1c2VySW5wdXQpIHtcbiAgICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghcHJpb3JVc2VySW5wdXQgfHwgIXByaW9yQXNzaXN0YW50T3V0cHV0KSB7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JVc2VySW5wdXQsICcgcHJpb3JVc2VySW5wdXQnKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvckFzc2lzdGFudE91dHB1dCwgJyBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpb3JVc2VyaW5wdXQgb3IgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBqc29uTWlzc2luZ0ZpZWxkc0JvZHkgPVxuICAgICAgICAgIGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgICApO1xuICAgICAgICBjb25zdCBkYXRlTWlzc2luZ0ZpZWxkc1RpbWUgPSBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZShcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICk7XG5cbiAgICAgICAgdXBkYXRlVGFza1JlcyA9IGF3YWl0IHByb2Nlc3NVcGRhdGVUYXNrTWlzc2luZ0ZpZWxkc1JldHVybmVkKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uTWlzc2luZ0ZpZWxkc0JvZHksXG4gICAgICAgICAgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICB9XG5cbiAgICBpZiAodXBkYXRlVGFza1Jlcz8ucXVlcnkgPT09ICdjb21wbGV0ZWQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5KFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICB1cGRhdGVUYXNrUmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAodXBkYXRlVGFza1Jlcz8ucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyhcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgdXBkYXRlVGFza1Jlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gdXBkYXRlVGFza1Jlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IHVwZGF0ZVRhc2tSZXM/LnByZXZEYXRhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGFFeHRyYSA9IHVwZGF0ZVRhc2tSZXM/LnByZXZEYXRhRXh0cmE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0ZUpzb25Cb2R5ID0gdXBkYXRlVGFza1Jlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZKc29uQm9keSA9IHVwZGF0ZVRhc2tSZXM/LnByZXZKc29uQm9keTtcbiAgICB9IGVsc2UgaWYgKHVwZGF0ZVRhc2tSZXM/LnF1ZXJ5ID09PSAnZXZlbnRfbm90X2ZvdW5kJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZTogQXNzaXN0YW50TWVzc2FnZVR5cGUgPSB7XG4gICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgICBjb250ZW50OiBcIk9vcHMuLi4gSSBjb3VsZG4ndCBmaW5kIHRoZSBldmVudC4gU29ycnkgOihcIixcbiAgICAgIH07XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH1cblxuICAgIHJldHVybiBtZXNzYWdlSGlzdG9yeU9iamVjdDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSB0YXNrIGNvbnRyb2wgY2VudGVyIHBlbmRpbmcgJyk7XG4gIH1cbn07XG4iXX0=