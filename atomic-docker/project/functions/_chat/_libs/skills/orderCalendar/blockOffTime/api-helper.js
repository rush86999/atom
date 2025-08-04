import requiredFields from './requiredFields';
import { convertEventTitleToOpenAIVector, createGoogleEvent, createPreAndPostEventsFromEvent, createRRuleString, extrapolateDateFromJSONData, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, getCalendarIntegrationByName, getGlobalCalendar, insertReminders, putDataInAllEventIndexInOpenSearch, putDataInTrainEventIndexInOpenSearch, upsertEvents, } from '@chat/_libs/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { googleCalendarName } from '@chat/_libs/constants';
import { v4 as uuid } from 'uuid';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
export const finalStepBlockOffTime = async (body, timezone, blockTimeStartDate, response) => {
    try {
        const primaryCalendar = await getGlobalCalendar(body?.userId);
        if (!primaryCalendar?.id) {
            throw new Error('no primary calendar found inside createAgenda');
        }
        const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
        if (!calIntegration?.clientType) {
            throw new Error('no client type inside calendar integration inside create agenda');
        }
        const eventId = uuid();
        const remindersToUpdateEventId = [];
        if (body?.reminders?.length > 0) {
            const newReminders = body?.reminders.map((r) => ({
                id: uuid(),
                userId: body?.userId,
                eventId,
                timezone,
                minutes: r,
                useDefault: false,
                updatedAt: dayjs().format(),
                createdDate: dayjs().format(),
                deleted: false,
            }));
            remindersToUpdateEventId.push(...newReminders);
        }
        const googleReminder = {
            overrides: remindersToUpdateEventId?.map((r) => ({
                method: 'email',
                minutes: r?.minutes,
            })),
            useDefault: false,
        };
        const newPreferredTimeRanges = [];
        for (const timepreference of body?.timePreferences) {
            if (timepreference.dayOfWeek?.length > 0) {
                for (const dayOfWeek of timepreference.dayOfWeek) {
                    const newPreferredTimeRange = {
                        id: uuid(),
                        eventId,
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
                    eventId,
                    startTime: timepreference?.timeRange?.startTime,
                    endTime: timepreference?.timeRange?.endTime,
                    updatedAt: dayjs().format(),
                    createdDate: dayjs().format(),
                    userId: body?.userId,
                };
                newPreferredTimeRanges.push(newPreferredTimeRange);
            }
        }
        const recur = createRRuleString(body?.recur?.frequency, body?.recur?.interval, body?.recur?.byWeekDay, body?.recur?.occurrence, body?.recur?.endDate, body?.recur?.ByMonthDay);
        const eventToUpsertLocal = {
            id: eventId,
            userId: body?.userId,
            title: body?.title,
            startDate: dayjs(blockTimeStartDate).tz(timezone).format(),
            endDate: dayjs(blockTimeStartDate)
                .tz(timezone)
                .add(body?.duration, 'm')
                .format(),
            allDay: false,
            notes: body?.description || body?.title,
            timezone,
            createdDate: dayjs().format(),
            deleted: false,
            priority: body?.priority || 1,
            isFollowUp: false,
            isPreEvent: false,
            isPostEvent: false,
            modifiable: body?.priority > 1 || newPreferredTimeRanges?.length > 0,
            transparency: body?.transparency,
            visibility: body?.visibility,
            originalStartDate: undefined,
            originalAllDay: false,
            summary: body?.title,
            updatedAt: dayjs().format(),
            calendarId: primaryCalendar?.id,
            eventId: undefined,
            sendUpdates: 'all',
            duration: body?.duration,
            timeBlocking: body?.bufferTime,
            anyoneCanAddSelf: false,
            guestsCanInviteOthers: true,
            guestsCanSeeOtherGuests: true,
            userModifiedAvailability: true,
            userModifiedTimeBlocking: body?.bufferTime ? true : false,
            userModifiedTimePreference: body?.timePreferences?.length > 0 ? true : false,
            userModifiedReminders: body?.reminders?.length > 0 ? true : false,
            userModifiedPriorityLevel: body?.timePreferences?.length > 0 ? true : false,
            userModifiedModifiable: true,
            userModifiedDuration: true,
            location: { title: body?.location },
            recurrence: recur,
            recurrenceRule: {
                frequency: body?.recur?.frequency,
                interval: body?.recur?.interval,
                byWeekDay: body?.recur?.byWeekDay,
                occurrence: body?.recur?.occurrence,
                endDate: body?.recur?.endDate,
                byMonthDay: body?.recur?.ByMonthDay,
            },
        };
        const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, eventToUpsertLocal?.id, eventToUpsertLocal?.endDate, eventToUpsertLocal?.startDate, 0, undefined, eventToUpsertLocal?.sendUpdates, eventToUpsertLocal?.anyoneCanAddSelf, undefined, undefined, eventToUpsertLocal?.title, eventToUpsertLocal?.notes, timezone, undefined, undefined, undefined, eventToUpsertLocal?.guestsCanInviteOthers, eventToUpsertLocal?.guestsCanModify, eventToUpsertLocal?.guestsCanSeeOtherGuests, undefined, undefined, recur, remindersToUpdateEventId?.length > 0 ? googleReminder : undefined, undefined, undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, undefined, undefined, undefined, undefined, undefined, eventToUpsertLocal?.attachments, 'default', body?.location, undefined);
        eventToUpsertLocal.id = googleResValue.id;
        eventToUpsertLocal.eventId = googleResValue.googleEventId;
        if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
            const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime);
            if (returnValues?.afterEvent) {
                const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, returnValues?.afterEvent?.id, returnValues?.afterEvent?.endDate, returnValues?.afterEvent?.startDate, 0, undefined, returnValues?.afterEvent?.sendUpdates, returnValues?.afterEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.afterEvent?.title, returnValues?.afterEvent?.notes, timezone, undefined, undefined, undefined, returnValues?.afterEvent?.guestsCanInviteOthers, returnValues?.afterEvent?.guestsCanModify, returnValues?.afterEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.afterEvent?.transparency, returnValues?.afterEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                returnValues.afterEvent.id = googleResValue.id;
                returnValues.afterEvent.eventId = googleResValue.googleEventId;
                returnValues.newEvent.postEventId = returnValues.afterEvent.id;
            }
            if (returnValues?.beforeEvent) {
                const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, returnValues?.beforeEvent?.id, returnValues?.beforeEvent?.endDate, returnValues?.beforeEvent?.startDate, 0, undefined, returnValues?.beforeEvent?.sendUpdates, returnValues?.beforeEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.beforeEvent?.title, returnValues?.beforeEvent?.notes, timezone, undefined, undefined, undefined, returnValues?.beforeEvent?.guestsCanInviteOthers, returnValues?.beforeEvent?.guestsCanModify, returnValues?.beforeEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.beforeEvent?.transparency, returnValues?.beforeEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                returnValues.beforeEvent.id = googleResValue.id;
                returnValues.beforeEvent.eventId = googleResValue.googleEventId;
                returnValues.newEvent.preEventId = returnValues.afterEvent.id;
            }
            await upsertEvents([
                returnValues.newEvent,
                returnValues?.afterEvent,
                returnValues?.beforeEvent,
            ]?.filter((e) => !!e));
        }
        else {
            await upsertEvents([eventToUpsertLocal]);
        }
        remindersToUpdateEventId?.forEach((r) => ({
            ...r,
            eventId: eventToUpsertLocal.id,
        }));
        newPreferredTimeRanges?.forEach((pt) => ({
            ...pt,
            eventId: eventToUpsertLocal.id,
        }));
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
        await putDataInAllEventIndexInOpenSearch(eventId, searchVector, body?.userId, body?.startDate, dayjs(body?.startDate).tz(timezone).add(body?.duration, 'm').format());
        response.query = 'completed';
        response.data = 'processed request successfully';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step block off time');
    }
};
export const processBlockOffTimePending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
    try {
        console.log(jsonBody, ' jsonBody');
        console.log(dateJSONBody, ' dateJSONBody');
        let duration = 0;
        const year = dateJSONBody?.year;
        const month = dateJSONBody?.month;
        const day = dateJSONBody?.day;
        const isoWeekday = dateJSONBody?.isoWeekday;
        const hour = dateJSONBody?.hour;
        const minute = dateJSONBody?.minute;
        const startTime = dateJSONBody?.startTime;
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'blockOffTime',
        };
        const blockTimeStartDate = extrapolateDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow);
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
            timezone,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description || jsonBody?.params?.notes,
            startDate: jsonBody?.params?.startTime || blockTimeStartDate,
            bufferTime: jsonBody?.params?.bufferTime,
            reminders: jsonBody?.params?.alarms || [],
            priority: jsonBody?.params?.priority || 1,
            timePreferences: dateJSONBody?.timePreferences || [],
            location: jsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility,
            isBreak: jsonBody?.params?.isBreak,
        };
        console.log(body, ' body');
        // if (!day && !isoWeekday) {
        //     response.query = 'missing_fields'
        //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0])
        //     response.data = missingFields
        //     response.prevData = body
        //     response.prevJsonBody = jsonBody
        //     response.prevDateJsonBody = dateJSONBody
        // }
        // if ((hour === null) && (minute === null) && !startTime) {
        //     response.query = 'missing_fields'
        //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1])
        //     response.data = missingFields
        //     response.prevData = body
        //     response.prevJsonBody = jsonBody
        //     response.prevDateJsonBody = dateJSONBody
        // }
        if (!body?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
            response.data = missingFields;
            response.prevData = body;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (recurObject?.frequency) {
            body.recur = recurObject;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepBlockOffTime(body, body?.timezone, body?.startDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process blockOffTime');
    }
};
export const processBlockOffTimeMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
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
        const missingFields = {
            required: [],
            dateTime: { required: [] },
        };
        const response = {
            query: '',
            data: {},
            skill: 'blockOffTime',
        };
        const blockTimeStartDate = extrapolateDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeFromNow);
        if (dateJSONBody?.duration ||
            messageHistoryObject?.prevDateJsonBody?.duration) {
            duration =
                dateJSONBody?.duration ||
                    messageHistoryObject?.prevDateJsonBody?.duration;
        }
        else if ((dateJSONBody?.startTime ||
            messageHistoryObject?.prevDateJsonBody?.startTime) &&
            (dateJSONBody?.endTime || messageHistoryObject?.prevDateJsonBody?.endTime)) {
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
                blockTimeStartDate,
            bufferTime: jsonBody?.params?.bufferTime ||
                messageHistoryObject?.prevJsonBody?.params.bufferTime,
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
        };
        console.log(newBody, ' newBody');
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
        // if (!prevBody?.startDate && !day && !isoWeekday) {
        //     response.query = 'missing_fields'
        //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0])
        //     response.data = missingFields
        //     response.prevData = prevBody
        //     response.prevJsonBody = jsonBody
        //     response.prevDateJsonBody = dateJSONBody
        // }
        // if (!prevBody?.startDate && (hour === null) && (minute === null) && !startTime) {
        //     response.query = 'missing_fields'
        //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1])
        //     response.data = missingFields
        //     response.prevData = prevBody
        //     response.prevJsonBody = jsonBody
        //     response.prevDateJsonBody = dateJSONBody
        // }
        if (!prevBody?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!prevBody?.recur &&
            recurObject
                ?.frequency) {
            prevBody.recur = recurObject;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepBlockOffTime(prevBody, prevBody?.timezone, prevBody?.startDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process block off time missing fields returned');
    }
};
export const blockOffTimeControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let blockOffTimeRes = {
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
                blockOffTimeRes = await processBlockOffTimePending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                blockOffTimeRes = await processBlockOffTimeMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (blockOffTimeRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, blockOffTimeRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (blockOffTimeRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, blockOffTimeRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required =
                blockOffTimeRes?.data;
            messageHistoryObject.prevData = blockOffTimeRes?.prevData;
            messageHistoryObject.prevDataExtra = blockOffTimeRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = blockOffTimeRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = blockOffTimeRes?.prevJsonBody;
        }
        else if (blockOffTimeRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to block off time control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBR0EsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLCtCQUErQixFQUMvQixpQkFBaUIsRUFDakIsK0JBQStCLEVBQy9CLGlCQUFpQixFQUNqQiwyQkFBMkIsRUFDM0IsbURBQW1ELEVBQ25ELHFEQUFxRCxFQUNyRCxnQkFBZ0IsRUFDaEIsNkJBQTZCLEVBQzdCLDZCQUE2QixFQUM3QiwwQ0FBMEMsRUFDMUMsNEJBQTRCLEVBQzVCLGlCQUFpQixFQUNqQixlQUFlLEVBQ2Ysa0NBQWtDLEVBQ2xDLG9DQUFvQyxFQUNwQyxZQUFZLEdBQ2IsTUFBTSx3QkFBd0IsQ0FBQztBQUNoQyxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFReEQsT0FBTyxFQUFFLGtCQUFrQixFQUFFLE1BQU0sdUJBQXVCLENBQUM7QUFDM0QsT0FBTyxFQUFFLEVBQUUsSUFBSSxJQUFJLEVBQUUsTUFBTSxNQUFNLENBQUM7QUFJbEMsT0FBTyxFQUFFLGFBQWEsRUFBRSxNQUFNLHVDQUF1QyxDQUFDO0FBRXRFLE9BQU8sRUFBRSxpQ0FBaUMsRUFBRSxNQUFNLHdDQUF3QyxDQUFDO0FBUTNGLE1BQU0sQ0FBQyxNQUFNLHFCQUFxQixHQUFHLEtBQUssRUFDeEMsSUFBc0IsRUFDdEIsUUFBZ0IsRUFDaEIsa0JBQTBCLEVBQzFCLFFBQWEsRUFDYixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxlQUFlLEdBQUcsTUFBTSxpQkFBaUIsQ0FBQyxJQUFJLEVBQUUsTUFBTSxDQUFDLENBQUM7UUFFOUQsSUFBSSxDQUFDLGVBQWUsRUFBRSxFQUFFLEVBQUUsQ0FBQztZQUN6QixNQUFNLElBQUksS0FBSyxDQUFDLCtDQUErQyxDQUFDLENBQUM7UUFDbkUsQ0FBQztRQUVELE1BQU0sY0FBYyxHQUFHLE1B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OUIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxrREFBa0QsQ0FBQyxDQUFDO0lBQ3JFLENBQUM7QUFDSCxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgRGF0ZVRpbWVKU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9EYXRlVGltZUpTT05KU09OVHlwZSc7XG5pbXBvcnQgVXNlcklucHV0VG9KU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Vc2VySW5wdXRUb0pTT05UeXBlJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCByZXF1aXJlZEZpZWxkcyBmcm9tICcuL3JlcXVpcmVkRmllbGRzJztcbmltcG9ydCB7XG4gIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IsXG4gIGNyZWF0ZUdvb2dsZUV2ZW50LFxuICBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50LFxuICBjcmVhdGVSUnVsZVN0cmluZyxcbiAgZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhLFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnksXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzLFxuICBnZW5lcmF0ZURhdGVUaW1lLFxuICBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dCxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzRGF0ZVRpbWUsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dCxcbiAgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZSxcbiAgZ2V0R2xvYmFsQ2FsZW5kYXIsXG4gIGluc2VydFJlbWluZGVycyxcbiAgcHV0RGF0YUluQWxsRXZlbnRJbmRleEluT3BlblNlYXJjaCxcbiAgcHV0RGF0YUluVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoLFxuICB1cHNlcnRFdmVudHMsXG59IGZyb20gJ0BjaGF0L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9kYXRlLXV0aWxzJztcbmltcG9ydCB7XG4gIEV2ZW50VHlwZSxcbiAgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG4gIFJlY3VycmVuY2VSdWxlVHlwZSxcbiAgVmlzaWJpbGl0eVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0V2ZW50VHlwZSc7XG5pbXBvcnQgeyBCbG9ja09mZlRpbWVUeXBlIH0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgeyBnb29nbGVDYWxlbmRhck5hbWUgfSBmcm9tICdAY2hhdC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IHsgUmVtaW5kZXJUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVtaW5kZXJUeXBlJztcbmltcG9ydCB7IEdvb2dsZVJlbWluZGVyVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0dvb2dsZVJlbWluZGVyVHlwZSc7XG5pbXBvcnQgUHJlZmVycmVkVGltZVJhbmdlVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9QcmVmZXJyZWRUaW1lUmFuZ2VUeXBlJztcbmltcG9ydCB7IERheU9mV2Vla0VudW0gfSBmcm9tICcuLi9yZXNvbHZlQ29uZmxpY3RpbmdFdmVudHMvY29uc3RhbnRzJztcbmltcG9ydCB7IEdvb2dsZVJlc1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Hb29nbGVSZXNUeXBlJztcbmltcG9ydCB7IHVwc2VydFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCB9IGZyb20gJy4uL3Jlc29sdmVDb25mbGljdGluZ0V2ZW50cy9hcGktaGVscGVyJztcbmltcG9ydCBSZXNwb25zZUFjdGlvblR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVzcG9uc2VBY3Rpb25UeXBlJztcbmltcG9ydCB7XG4gIEFzc2lzdGFudE1lc3NhZ2VUeXBlLFxuICBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvTWVzc2FnaW5nL01lc3NhZ2luZ1R5cGVzJztcbmltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcblxuZXhwb3J0IGNvbnN0IGZpbmFsU3RlcEJsb2NrT2ZmVGltZSA9IGFzeW5jIChcbiAgYm9keTogQmxvY2tPZmZUaW1lVHlwZSxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgYmxvY2tUaW1lU3RhcnREYXRlOiBzdHJpbmcsXG4gIHJlc3BvbnNlOiBhbnlcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHByaW1hcnlDYWxlbmRhciA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKGJvZHk/LnVzZXJJZCk7XG5cbiAgICBpZiAoIXByaW1hcnlDYWxlbmRhcj8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpbWFyeSBjYWxlbmRhciBmb3VuZCBpbnNpZGUgY3JlYXRlQWdlbmRhJyk7XG4gICAgfVxuXG4gICAgY29uc3QgY2FsSW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJOYW1lXG4gICAgKTtcblxuICAgIGlmICghY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ25vIGNsaWVudCB0eXBlIGluc2lkZSBjYWxlbmRhciBpbnRlZ3JhdGlvbiBpbnNpZGUgY3JlYXRlIGFnZW5kYSdcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKTtcblxuICAgIGNvbnN0IHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZDogUmVtaW5kZXJUeXBlW10gPSBbXTtcblxuICAgIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnN0IG5ld1JlbWluZGVyczogUmVtaW5kZXJUeXBlW10gPSBib2R5Py5yZW1pbmRlcnMubWFwKChyKSA9PiAoe1xuICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIG1pbnV0ZXM6IHIsXG4gICAgICAgIHVzZURlZmF1bHQ6IGZhbHNlLFxuICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgIH0pKTtcblxuICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkLnB1c2goLi4ubmV3UmVtaW5kZXJzKTtcbiAgICB9XG5cbiAgICBjb25zdCBnb29nbGVSZW1pbmRlcjogR29vZ2xlUmVtaW5kZXJUeXBlID0ge1xuICAgICAgb3ZlcnJpZGVzOiByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lm1hcCgocikgPT4gKHtcbiAgICAgICAgbWV0aG9kOiAnZW1haWwnLFxuICAgICAgICBtaW51dGVzOiByPy5taW51dGVzLFxuICAgICAgfSkpLFxuICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgfTtcblxuICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCB0aW1lcHJlZmVyZW5jZSBvZiBib2R5Py50aW1lUHJlZmVyZW5jZXMpIHtcbiAgICAgIGlmICh0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWs/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgZm9yIChjb25zdCBkYXlPZldlZWsgb2YgdGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrKSB7XG4gICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgICBkYXlPZldlZWs6IERheU9mV2Vla0VudW1bZGF5T2ZXZWVrXSxcbiAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgfTtcblxuICAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICBldmVudElkLFxuICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICB9O1xuXG4gICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHJlY3VyID0gY3JlYXRlUlJ1bGVTdHJpbmcoXG4gICAgICBib2R5Py5yZWN1cj8uZnJlcXVlbmN5LFxuICAgICAgYm9keT8ucmVjdXI/LmludGVydmFsLFxuICAgICAgYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAgIGJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlLFxuICAgICAgYm9keT8ucmVjdXI/LmVuZERhdGUsXG4gICAgICBib2R5Py5yZWN1cj8uQnlNb250aERheVxuICAgICk7XG5cbiAgICBjb25zdCBldmVudFRvVXBzZXJ0TG9jYWw6IEV2ZW50VHlwZSA9IHtcbiAgICAgIGlkOiBldmVudElkLFxuICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICB0aXRsZTogYm9keT8udGl0bGUsXG4gICAgICBzdGFydERhdGU6IGRheWpzKGJsb2NrVGltZVN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgpLFxuICAgICAgZW5kRGF0ZTogZGF5anMoYmxvY2tUaW1lU3RhcnREYXRlKVxuICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgIC5hZGQoYm9keT8uZHVyYXRpb24sICdtJylcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgYWxsRGF5OiBmYWxzZSxcbiAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgIHByaW9yaXR5OiBib2R5Py5wcmlvcml0eSB8fCAxLFxuICAgICAgaXNGb2xsb3dVcDogZmFsc2UsXG4gICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgIGlzUG9zdEV2ZW50OiBmYWxzZSxcbiAgICAgIG1vZGlmaWFibGU6IGJvZHk/LnByaW9yaXR5ID4gMSB8fCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwLFxuICAgICAgdHJhbnNwYXJlbmN5OiBib2R5Py50cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5OiBib2R5Py52aXNpYmlsaXR5IGFzIFZpc2liaWxpdHlUeXBlLFxuICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgIG9yaWdpbmFsQWxsRGF5OiBmYWxzZSxcbiAgICAgIHN1bW1hcnk6IGJvZHk/LnRpdGxlLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgY2FsZW5kYXJJZDogcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgIGV2ZW50SWQ6IHVuZGVmaW5lZCxcbiAgICAgIHNlbmRVcGRhdGVzOiAnYWxsJyxcbiAgICAgIGR1cmF0aW9uOiBib2R5Py5kdXJhdGlvbixcbiAgICAgIHRpbWVCbG9ja2luZzogYm9keT8uYnVmZmVyVGltZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiB0cnVlLFxuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IHRydWUsXG4gICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHk6IHRydWUsXG4gICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmc6IGJvZHk/LmJ1ZmZlclRpbWUgPyB0cnVlIDogZmFsc2UsXG4gICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZTpcbiAgICAgICAgYm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzOiBib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDAgPyB0cnVlIDogZmFsc2UsXG4gICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsOlxuICAgICAgICBib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDAgPyB0cnVlIDogZmFsc2UsXG4gICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb246IHRydWUsXG4gICAgICBsb2NhdGlvbjogeyB0aXRsZTogYm9keT8ubG9jYXRpb24gfSxcbiAgICAgIHJlY3VycmVuY2U6IHJlY3VyLFxuICAgICAgcmVjdXJyZW5jZVJ1bGU6IHtcbiAgICAgICAgZnJlcXVlbmN5OiBib2R5Py5yZWN1cj8uZnJlcXVlbmN5LFxuICAgICAgICBpbnRlcnZhbDogYm9keT8ucmVjdXI/LmludGVydmFsLFxuICAgICAgICBieVdlZWtEYXk6IGJvZHk/LnJlY3VyPy5ieVdlZWtEYXksXG4gICAgICAgIG9jY3VycmVuY2U6IGJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlLFxuICAgICAgICBlbmREYXRlOiBib2R5Py5yZWN1cj8uZW5kRGF0ZSxcbiAgICAgICAgYnlNb250aERheTogYm9keT8ucmVjdXI/LkJ5TW9udGhEYXksXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5pZCxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3RhcnREYXRlLFxuICAgICAgMCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc2VuZFVwZGF0ZXMsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRpdGxlLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ub3RlcyxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICByZWN1cixcbiAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCA/IGdvb2dsZVJlbWluZGVyIDogdW5kZWZpbmVkLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50cmFuc3BhcmVuY3ksXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnZpc2liaWxpdHksXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmF0dGFjaG1lbnRzLFxuICAgICAgJ2RlZmF1bHQnLFxuICAgICAgYm9keT8ubG9jYXRpb24sXG4gICAgICB1bmRlZmluZWRcbiAgICApO1xuXG4gICAgZXZlbnRUb1Vwc2VydExvY2FsLmlkID0gZ29vZ2xlUmVzVmFsdWUuaWQ7XG4gICAgZXZlbnRUb1Vwc2VydExvY2FsLmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuXG4gICAgaWYgKGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQgfHwgYm9keT8uYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQpIHtcbiAgICAgIGNvbnN0IHJldHVyblZhbHVlcyA9IGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGcm9tRXZlbnQoXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbCxcbiAgICAgICAgYm9keT8uYnVmZmVyVGltZVxuICAgICAgKTtcblxuICAgICAgaWYgKHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCkge1xuICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uaWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgIDAsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50aXRsZSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lm5vdGVzLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICk7XG5cbiAgICAgICAgcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWQ7XG4gICAgICAgIHJldHVyblZhbHVlcy5uZXdFdmVudC5wb3N0RXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgfVxuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudCkge1xuICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmlkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgIDAsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py50aXRsZSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICk7XG5cbiAgICAgICAgcmV0dXJuVmFsdWVzLmJlZm9yZUV2ZW50LmlkID0gZ29vZ2xlUmVzVmFsdWUuaWQ7XG4gICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcbiAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnByZUV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZDtcbiAgICAgIH1cblxuICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFxuICAgICAgICBbXG4gICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50LFxuICAgICAgICBdPy5maWx0ZXIoKGUpID0+ICEhZSlcbiAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIGF3YWl0IHVwc2VydEV2ZW50cyhbZXZlbnRUb1Vwc2VydExvY2FsXSk7XG4gICAgfVxuXG4gICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5mb3JFYWNoKChyKSA9PiAoe1xuICAgICAgLi4ucixcbiAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbC5pZCxcbiAgICB9KSk7XG5cbiAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5mb3JFYWNoKChwdCkgPT4gKHtcbiAgICAgIC4uLnB0LFxuICAgICAgZXZlbnRJZDogZXZlbnRUb1Vwc2VydExvY2FsLmlkLFxuICAgIH0pKTtcblxuICAgIGlmIChyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGluc2VydFJlbWluZGVycyhyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQpO1xuICAgIH1cblxuICAgIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcyk7XG4gICAgfVxuXG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSk7XG5cbiAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCB8fCBib2R5Py5wcmlvcml0eSA+IDEpIHtcbiAgICAgIGF3YWl0IHB1dERhdGFJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaChcbiAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgc2VhcmNoVmVjdG9yLFxuICAgICAgICBib2R5Py51c2VySWRcbiAgICAgICk7XG4gICAgfVxuXG4gICAgYXdhaXQgcHV0RGF0YUluQWxsRXZlbnRJbmRleEluT3BlblNlYXJjaChcbiAgICAgIGV2ZW50SWQsXG4gICAgICBzZWFyY2hWZWN0b3IsXG4gICAgICBib2R5Py51c2VySWQsXG4gICAgICBib2R5Py5zdGFydERhdGUsXG4gICAgICBkYXlqcyhib2R5Py5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5hZGQoYm9keT8uZHVyYXRpb24sICdtJykuZm9ybWF0KClcbiAgICApO1xuXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICByZXNwb25zZS5kYXRhID0gJ3Byb2Nlc3NlZCByZXF1ZXN0IHN1Y2Nlc3NmdWxseSc7XG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZmluYWwgc3RlcCBibG9jayBvZmYgdGltZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0Jsb2NrT2ZmVGltZVBlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nXG4pOiBQcm9taXNlPFJlc3BvbnNlQWN0aW9uVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKGpzb25Cb2R5LCAnIGpzb25Cb2R5Jyk7XG4gICAgY29uc29sZS5sb2coZGF0ZUpTT05Cb2R5LCAnIGRhdGVKU09OQm9keScpO1xuICAgIGxldCBkdXJhdGlvbiA9IDA7XG5cbiAgICBjb25zdCB5ZWFyID0gZGF0ZUpTT05Cb2R5Py55ZWFyO1xuICAgIGNvbnN0IG1vbnRoID0gZGF0ZUpTT05Cb2R5Py5tb250aDtcbiAgICBjb25zdCBkYXkgPSBkYXRlSlNPTkJvZHk/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5ID0gZGF0ZUpTT05Cb2R5Py5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXIgPSBkYXRlSlNPTkJvZHk/LmhvdXI7XG4gICAgY29uc3QgbWludXRlID0gZGF0ZUpTT05Cb2R5Py5taW51dGU7XG4gICAgY29uc3Qgc3RhcnRUaW1lID0gZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWU7XG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgICBkYXRlVGltZTogeyByZXF1aXJlZDogW10gfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdibG9ja09mZlRpbWUnLFxuICAgIH07XG5cbiAgICBjb25zdCBibG9ja1RpbWVTdGFydERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhcixcbiAgICAgIG1vbnRoLFxuICAgICAgZGF5LFxuICAgICAgaXNvV2Vla2RheSxcbiAgICAgIGhvdXIsXG4gICAgICBtaW51dGUsXG4gICAgICBzdGFydFRpbWUsXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgaWYgKGRhdGVKU09OQm9keT8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKGRhdGVKU09OQm9keT8uc3RhcnRUaW1lICYmIGRhdGVKU09OQm9keT8uZW5kVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUsICdISDptbScpO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKGRhdGVKU09OQm9keS5lbmRUaW1lLCAnSEg6bW0nKTtcblxuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgJiYganNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoanNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKTtcbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICBkdXJhdGlvbiA9IDMwO1xuICAgIH1cblxuICAgIGxldCByZWN1ck9iamVjdDogUmVjdXJyZW5jZVJ1bGVUeXBlIHwge30gPSB7fTtcbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5KSB7XG4gICAgICBjb25zdCByZWN1ckVuZERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhcixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGgsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91cixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubWludXRlLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5zdGFydFRpbWUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICAgICk7XG5cbiAgICAgIHJlY3VyT2JqZWN0ID0ge1xuICAgICAgICBmcmVxdWVuY3k6XG4gICAgICAgICAgKGRhdGVKU09OQm9keT8ucmVjdXI/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSkgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5mcmVxdWVuY3ksXG4gICAgICAgIGludGVydmFsOlxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uaW50ZXJ2YWwsXG4gICAgICB9O1xuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5KSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5V2Vla0RheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieU1vbnRoRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5vY2N1cnJlbmNlID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlO1xuICAgICAgfVxuXG4gICAgICBpZiAocmVjdXJFbmREYXRlIHx8IGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuZW5kRGF0ZSA9XG4gICAgICAgICAgcmVjdXJFbmREYXRlIHx8IGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGU7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgYm9keTogQmxvY2tPZmZUaW1lVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgZHVyYXRpb24sXG4gICAgICBkZXNjcmlwdGlvbjoganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHwganNvbkJvZHk/LnBhcmFtcz8ubm90ZXMsXG4gICAgICBzdGFydERhdGU6IGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fCBibG9ja1RpbWVTdGFydERhdGUsXG4gICAgICBidWZmZXJUaW1lOiBqc29uQm9keT8ucGFyYW1zPy5idWZmZXJUaW1lLFxuICAgICAgcmVtaW5kZXJzOiBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHwgW10sXG4gICAgICBwcmlvcml0eToganNvbkJvZHk/LnBhcmFtcz8ucHJpb3JpdHkgfHwgMSxcbiAgICAgIHRpbWVQcmVmZXJlbmNlczogZGF0ZUpTT05Cb2R5Py50aW1lUHJlZmVyZW5jZXMgfHwgW10sXG4gICAgICBsb2NhdGlvbjoganNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24sXG4gICAgICB0cmFuc3BhcmVuY3k6IGpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6IGpzb25Cb2R5Py5wYXJhbXMudmlzaWJpbGl0eSxcbiAgICAgIGlzQnJlYWs6IGpzb25Cb2R5Py5wYXJhbXM/LmlzQnJlYWssXG4gICAgfTtcblxuICAgIGNvbnNvbGUubG9nKGJvZHksICcgYm9keScpO1xuXG4gICAgLy8gaWYgKCFkYXkgJiYgIWlzb1dlZWtkYXkpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnXG4gICAgLy8gICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzBdKVxuICAgIC8vICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkc1xuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHlcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHlcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keVxuICAgIC8vIH1cblxuICAgIC8vIGlmICgoaG91ciA9PT0gbnVsbCkgJiYgKG1pbnV0ZSA9PT0gbnVsbCkgJiYgIXN0YXJ0VGltZSkge1xuICAgIC8vICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcydcbiAgICAvLyAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkPy5bMV0pXG4gICAgLy8gICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzXG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5XG4gICAgLy8gfVxuXG4gICAgaWYgKCFib2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZVxuICAgICkge1xuICAgICAgYm9keS5yZWN1ciA9IHJlY3VyT2JqZWN0IGFzIGFueTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwQmxvY2tPZmZUaW1lKFxuICAgICAgYm9keSxcbiAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgYm9keT8uc3RhcnREYXRlLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGJsb2NrT2ZmVGltZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0Jsb2NrT2ZmVGltZU1pc3NpbmdGaWVsZHNSZXR1cm5lZCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICBkYXRlSlNPTkJvZHk6IERhdGVUaW1lSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IGR1cmF0aW9uID0gMDtcblxuICAgIGNvbnN0IHllYXIgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py55ZWFyIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py55ZWFyO1xuICAgIGNvbnN0IG1vbnRoID1cbiAgICAgIGRhdGVKU09OQm9keT8ubW9udGggfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/Lm1vbnRoO1xuICAgIGNvbnN0IGRheSA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmRheSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXkgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5pc29XZWVrZGF5IHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyID1cbiAgICAgIGRhdGVKU09OQm9keT8uaG91ciB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uaG91cjtcbiAgICBjb25zdCBtaW51dGUgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5taW51dGUgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWUgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5zdGFydFRpbWU7XG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgICBkYXRlVGltZTogeyByZXF1aXJlZDogW10gfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdibG9ja09mZlRpbWUnLFxuICAgIH07XG5cbiAgICBjb25zdCBibG9ja1RpbWVTdGFydERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhcixcbiAgICAgIG1vbnRoLFxuICAgICAgZGF5LFxuICAgICAgaXNvV2Vla2RheSxcbiAgICAgIGhvdXIsXG4gICAgICBtaW51dGUsXG4gICAgICBzdGFydFRpbWUsXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgaWYgKFxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbiB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1cmF0aW9uXG4gICAgKSB7XG4gICAgICBkdXJhdGlvbiA9XG4gICAgICAgIGRhdGVKU09OQm9keT8uZHVyYXRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoXG4gICAgICAoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnN0YXJ0VGltZSkgJiZcbiAgICAgIChkYXRlSlNPTkJvZHk/LmVuZFRpbWUgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmVuZFRpbWUpXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydFRpbWVPYmplY3QgPSBkYXlqcyhcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uc3RhcnRUaW1lLFxuICAgICAgICAnSEg6bW0nXG4gICAgICApO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBkYXRlSlNPTkJvZHkuZW5kVGltZSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZW5kVGltZSxcbiAgICAgICAgJ0hIOm1tJ1xuICAgICAgKTtcblxuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChcbiAgICAgIChqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUpICYmXG4gICAgICAoanNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUpXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydFRpbWVPYmplY3QgPSBkYXlqcyhcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWVcbiAgICAgICk7XG4gICAgICBjb25zdCBlbmRUaW1lT2JqZWN0ID0gZGF5anMoXG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWVcbiAgICAgICk7XG4gICAgICBjb25zdCBtaW51dGVzID0gZW5kVGltZU9iamVjdC5kaWZmKHN0YXJ0VGltZU9iamVjdCwgJ20nKTtcblxuICAgICAgaWYgKG1pbnV0ZXMgPiAwKSB7XG4gICAgICAgIGR1cmF0aW9uID0gbWludXRlcztcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgZHVyYXRpb24gPSAzMDtcbiAgICB9XG5cbiAgICBsZXQgcmVjdXJPYmplY3Q6IFJlY3VycmVuY2VSdWxlVHlwZSB8IHt9ID0ge307XG4gICAgaWYgKFxuICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmZyZXF1ZW5jeVxuICAgICkge1xuICAgICAgY29uc3QgcmVjdXJFbmREYXRlID0gZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhKFxuICAgICAgICBjdXJyZW50VGltZSxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnllYXIgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/LnllYXIsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1vbnRoIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5tb250aCxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uZGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5kYXksXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/Lmlzb1dlZWtkYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/Lmlzb1dlZWtkYXksXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LmhvdXIgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/LmhvdXIsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1pbnV0ZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubWludXRlLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5zdGFydFRpbWUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZVxuICAgICAgICAgICAgPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5yZWxhdGl2ZVRpbWVGcm9tTm93IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlXG4gICAgICAgICAgICA/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICAgICk7XG5cbiAgICAgIHJlY3VyT2JqZWN0ID0ge1xuICAgICAgICBmcmVxdWVuY3k6XG4gICAgICAgICAgKGRhdGVKU09OQm9keT8ucmVjdXI/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmZyZXF1ZW5jeSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZnJlcXVlbmN5IHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZnJlcXVlbmN5LFxuICAgICAgICBpbnRlcnZhbDpcbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmludGVydmFsIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uaW50ZXJ2YWwsXG4gICAgICB9O1xuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5V2Vla0RheSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5V2Vla0RheVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5V2Vla0RheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieVdlZWtEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5TW9udGhEYXlcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieU1vbnRoRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2UgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlXG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkub2NjdXJyZW5jZSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICByZWN1ckVuZERhdGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGVcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5lbmREYXRlID1cbiAgICAgICAgICByZWN1ckVuZERhdGUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG5ld0JvZHk6IEJsb2NrT2ZmVGltZVR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2sgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5ub3RlcyxcbiAgICAgIHN0YXJ0RGF0ZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIGJsb2NrVGltZVN0YXJ0RGF0ZSxcbiAgICAgIGJ1ZmZlclRpbWU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zLmJ1ZmZlclRpbWUsXG4gICAgICByZW1pbmRlcnM6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fFxuICAgICAgICBbXSxcbiAgICAgIHByaW9yaXR5OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8XG4gICAgICAgIDEsXG4gICAgICB0aW1lUHJlZmVyZW5jZXM6XG4gICAgICAgIGRhdGVKU09OQm9keT8udGltZVByZWZlcmVuY2VzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py50aW1lUHJlZmVyZW5jZXMgfHxcbiAgICAgICAgW10sXG4gICAgICBsb2NhdGlvbjpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5sb2NhdGlvbixcbiAgICAgIHRyYW5zcGFyZW5jeTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcy52aXNpYmlsaXR5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udmlzaWJpbGl0eSxcbiAgICAgIGlzQnJlYWs6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmlzQnJlYWsgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5pc0JyZWFrLFxuICAgIH07XG5cbiAgICBjb25zb2xlLmxvZyhuZXdCb2R5LCAnIG5ld0JvZHknKTtcblxuICAgIGNvbnN0IHByZXZCb2R5OiBCbG9ja09mZlRpbWVUeXBlID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZHVyYXRpb24pIHtcbiAgICAgIHByZXZCb2R5LmR1cmF0aW9uID0gbmV3Qm9keT8uZHVyYXRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZGVzY3JpcHRpb24pIHtcbiAgICAgIHByZXZCb2R5LmRlc2NyaXB0aW9uID0gbmV3Qm9keT8uZGVzY3JpcHRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uc3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS5zdGFydERhdGUgPSBuZXdCb2R5Py5zdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgcHJldkJvZHkuYnVmZmVyVGltZSA9IG5ld0JvZHk/LmJ1ZmZlclRpbWU7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnJlbWluZGVycyA9IG5ld0JvZHk/LnJlbWluZGVycyB8fCBbXTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5wcmlvcml0eSkge1xuICAgICAgcHJldkJvZHkucHJpb3JpdHkgPSBuZXdCb2R5Py5wcmlvcml0eTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkudGltZVByZWZlcmVuY2VzID0gbmV3Qm9keT8udGltZVByZWZlcmVuY2VzO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmxvY2F0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5sb2NhdGlvbiA9IG5ld0JvZHk/LmxvY2F0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgcHJldkJvZHkudHJhbnNwYXJlbmN5ID0gbmV3Qm9keT8udHJhbnNwYXJlbmN5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIHByZXZCb2R5LnZpc2liaWxpdHkgPSBuZXdCb2R5Py52aXNpYmlsaXR5O1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5pc0JyZWFrID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHByZXZCb2R5LmlzQnJlYWsgPSBuZXdCb2R5Py5pc0JyZWFrO1xuICAgIH1cblxuICAgIC8vIGlmICghcHJldkJvZHk/LnN0YXJ0RGF0ZSAmJiAhZGF5ICYmICFpc29XZWVrZGF5KSB7XG4gICAgLy8gICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJ1xuICAgIC8vICAgICBtaXNzaW5nRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQ/LlswXSlcbiAgICAvLyAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHNcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5XG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKCFwcmV2Qm9keT8uc3RhcnREYXRlICYmIChob3VyID09PSBudWxsKSAmJiAobWludXRlID09PSBudWxsKSAmJiAhc3RhcnRUaW1lKSB7XG4gICAgLy8gICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJ1xuICAgIC8vICAgICBtaXNzaW5nRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQ/LlsxXSlcbiAgICAvLyAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHNcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5XG4gICAgLy8gfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzBdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAhcHJldkJvZHk/LnJlY3VyICYmXG4gICAgICAoKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSlcbiAgICAgICAgPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUpXG4gICAgKSB7XG4gICAgICBwcmV2Qm9keS5yZWN1ciA9IHJlY3VyT2JqZWN0IGFzIGFueTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBCbG9ja09mZlRpbWUoXG4gICAgICBwcmV2Qm9keSxcbiAgICAgIHByZXZCb2R5Py50aW1lem9uZSxcbiAgICAgIHByZXZCb2R5Py5zdGFydERhdGUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgYmxvY2sgb2ZmIHRpbWUgbWlzc2luZyBmaWVsZHMgcmV0dXJuZWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGJsb2NrT2ZmVGltZUNvbnRyb2xDZW50ZXIgPSBhc3luYyAoXG4gIG9wZW5haTogT3BlbkFJLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxuICB1c2VyQ3VycmVudFRpbWU6IHN0cmluZyxcbiAgcXVlcnk6ICdtaXNzaW5nX2ZpZWxkcycgfCAnY29tcGxldGVkJyB8ICdldmVudF9ub3RfZm91bmQnIHwgJ3BlbmRpbmcnXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZXNzYWdlTGVuZ3RoID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXM/Lmxlbmd0aDtcbiAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJztcbiAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgIHVzZXJNZXNzYWdlID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCB1c2VySW5wdXQgPSB1c2VyTWVzc2FnZTtcblxuICAgIGxldCBibG9ja09mZlRpbWVSZXM6IFJlc3BvbnNlQWN0aW9uVHlwZSA9IHtcbiAgICAgIHF1ZXJ5OiAnY29tcGxldGVkJyxcbiAgICAgIGRhdGE6ICcnLFxuICAgICAgc2tpbGw6ICcnLFxuICAgICAgcHJldkRhdGE6IHt9LFxuICAgICAgcHJldkRhdGFFeHRyYToge30sXG4gICAgfTtcblxuICAgIHN3aXRjaCAocXVlcnkpIHtcbiAgICAgIGNhc2UgJ3BlbmRpbmcnOlxuICAgICAgICBjb25zdCBqc29uQm9keSA9IGF3YWl0IGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZVRpbWUgPSBhd2FpdCBnZW5lcmF0ZURhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgYmxvY2tPZmZUaW1lUmVzID0gYXdhaXQgcHJvY2Vzc0Jsb2NrT2ZmVGltZVBlbmRpbmcoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25Cb2R5LFxuICAgICAgICAgIGRhdGVUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ21pc3NpbmdfZmllbGRzJzpcbiAgICAgICAgbGV0IHByaW9yVXNlcklucHV0ID0gJyc7XG4gICAgICAgIGxldCBwcmlvckFzc2lzdGFudE91dHB1dCA9ICcnO1xuXG4gICAgICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICdhc3Npc3RhbnQnKSB7XG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICAgICAgaWYgKG1lc3NhZ2UuY29udGVudCAhPT0gdXNlcklucHV0KSB7XG4gICAgICAgICAgICAgIHByaW9yVXNlcklucHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoIXByaW9yVXNlcklucHV0IHx8ICFwcmlvckFzc2lzdGFudE91dHB1dCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yVXNlcklucHV0LCAnIHByaW9yVXNlcklucHV0Jyk7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JBc3Npc3RhbnRPdXRwdXQsICcgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHByaW9yVXNlcmlucHV0IG9yIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgIH1cbiAgICAgICAgY29uc3QganNvbk1pc3NpbmdGaWVsZHNCb2R5ID1cbiAgICAgICAgICBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lID0gYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuXG4gICAgICAgIGJsb2NrT2ZmVGltZVJlcyA9IGF3YWl0IHByb2Nlc3NCbG9ja09mZlRpbWVNaXNzaW5nRmllbGRzUmV0dXJuZWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25NaXNzaW5nRmllbGRzQm9keSxcbiAgICAgICAgICBkYXRlTWlzc2luZ0ZpZWxkc1RpbWUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgIH1cblxuICAgIGlmIChibG9ja09mZlRpbWVSZXM/LnF1ZXJ5ID09PSAnY29tcGxldGVkJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeShcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgYmxvY2tPZmZUaW1lUmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoYmxvY2tPZmZUaW1lUmVzPy5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzKFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBibG9ja09mZlRpbWVSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9XG4gICAgICAgIGJsb2NrT2ZmVGltZVJlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IGJsb2NrT2ZmVGltZVJlcz8ucHJldkRhdGE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YUV4dHJhID0gYmxvY2tPZmZUaW1lUmVzPy5wcmV2RGF0YUV4dHJhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGVKc29uQm9keSA9IGJsb2NrT2ZmVGltZVJlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZKc29uQm9keSA9IGJsb2NrT2ZmVGltZVJlcz8ucHJldkpzb25Cb2R5O1xuICAgIH0gZWxzZSBpZiAoYmxvY2tPZmZUaW1lUmVzPy5xdWVyeSA9PT0gJ2V2ZW50X25vdF9mb3VuZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2U6IEFzc2lzdGFudE1lc3NhZ2VUeXBlID0ge1xuICAgICAgICByb2xlOiAnYXNzaXN0YW50JyxcbiAgICAgICAgY29udGVudDogXCJPb3BzLi4uIEkgY291bGRuJ3QgZmluZCB0aGUgZXZlbnQuIFNvcnJ5IDooXCIsXG4gICAgICB9O1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9XG5cbiAgICByZXR1cm4gbWVzc2FnZUhpc3RvcnlPYmplY3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBibG9jayBvZmYgdGltZSBjb250cm9sIGNlbnRlciBwZW5kaW5nJyk7XG4gIH1cbn07XG4iXX0=