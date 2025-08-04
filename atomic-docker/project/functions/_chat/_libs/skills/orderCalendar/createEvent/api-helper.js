import requiredFields from './requiredFields';
import { convertEventTitleToOpenAIVector, createGoogleEvent, createPreAndPostEventsFromEvent, createRRuleString, createZoomMeeting, extrapolateDateFromJSONData, findContactByEmailGivenUserId, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, getCalendarIntegrationByName, getContactByNameWithUserId, getGlobalCalendar, getUserContactInfosGivenIds, getUserGivenId, getZoomAPIToken, insertReminders, listUserContactInfosGivenUserId, putDataInTrainEventIndexInOpenSearch, upsertAttendeesforEvent, upsertConference, upsertEvents, } from '@chat/_libs/api-helper';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import dayjs from 'dayjs';
import { googleCalendarName } from '@chat/_libs/constants';
import { v4 as uuid } from 'uuid';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
export const finalStepCreatEvent = async (body, timezone, defaultMeetingPreferences, response) => {
    try {
        const eventId = uuid();
        const attendees = [];
        if (body?.attendees?.length > 0) {
            const aWithEmails = body?.attendees?.filter((a) => !!a?.email);
            const aWithContactInfos = await getUserContactInfosGivenIds(aWithEmails?.map((a) => a?.email));
            const userContactInfos = await listUserContactInfosGivenUserId(body?.userId);
            const providedHostInfo = body?.attendees?.find((a) => a?.isHost === true);
            const primaryInfoItem = userContactInfos?.find((u) => u.primary && u.type === 'email');
            const user = await getUserGivenId(body?.userId);
            const primaryHostAttendeeInfo = {
                name: primaryInfoItem?.name || user?.name,
                email: primaryInfoItem?.id || user?.email,
                isHost: true,
            };
            if (!providedHostInfo && primaryHostAttendeeInfo?.email) {
                body?.attendees.push(primaryHostAttendeeInfo);
            }
            const attendeesFromExtractedJSON = body?.attendees;
            for (const a of attendeesFromExtractedJSON) {
                const contact = await findContactByEmailGivenUserId(body?.userId, a.email);
                const userIdFound = aWithContactInfos?.find((b) => b?.id === a?.email);
                const attendee = {
                    id: userIdFound?.userId || uuid(),
                    userId: body?.userId,
                    name: a?.name ||
                        contact?.name ||
                        `${contact?.firstName} ${contact?.lastName}`,
                    contactId: contact?.id,
                    emails: [{ primary: true, value: a?.email }],
                    updatedAt: dayjs().format(),
                    createdDate: dayjs().format(),
                    deleted: false,
                    eventId,
                };
                attendees.push(attendee);
            }
        }
        const primaryCalendar = await getGlobalCalendar(body?.userId);
        if (!primaryCalendar?.id) {
            throw new Error('no primary calendar found inside createAgenda');
        }
        const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
        if (!calIntegration?.clientType) {
            throw new Error('no client type inside calendar integration inside create agenda');
        }
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
        console.log(recur, ' recur');
        let conference = {};
        if (body?.conferenceApp) {
            const zoomToken = await getZoomAPIToken(body?.userId);
            conference =
                zoomToken && body?.conferenceApp === 'zoom'
                    ? {}
                    : {
                        id: uuid(),
                        userId: body?.userId,
                        calendarId: primaryCalendar?.id,
                        app: 'google',
                        name: defaultMeetingPreferences?.name,
                        notes: body?.description || body?.title,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        deleted: false,
                        isHost: true,
                        requestId: uuid(),
                    };
            if (zoomToken && body?.conferenceApp === 'zoom') {
                console.log(zoomToken, ' zoomToken inside if (zoomToken)');
                const zoomObject = await createZoomMeeting(zoomToken, body?.startDate, timezone, body?.title, body?.duration, defaultMeetingPreferences?.name, defaultMeetingPreferences?.primaryEmail, body?.attendees?.map((a) => a?.email), body?.recur);
                console.log(zoomObject, ' zoomObject after createZoomMeeting');
                if (zoomObject) {
                    conference = {
                        id: `${zoomObject?.id}`,
                        userId: body?.userId,
                        calendarId: primaryCalendar?.id,
                        app: 'zoom',
                        name: zoomObject?.agenda,
                        notes: zoomObject?.agenda,
                        joinUrl: zoomObject?.join_url,
                        startUrl: zoomObject?.start_url,
                        isHost: true,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        deleted: false,
                        entryPoints: [
                            {
                                entryPointType: 'video',
                                label: zoomObject?.join_url,
                                password: zoomObject?.password,
                                uri: zoomObject?.join_url,
                            },
                        ],
                    };
                }
            }
            const eventToUpsertLocal = {
                id: eventId,
                userId: body?.userId,
                title: body?.title,
                startDate: dayjs(body?.startDate).tz(timezone).format(),
                endDate: dayjs(body?.startDate)
                    .tz(timezone)
                    .add(body?.duration, 'm')
                    .format(),
                allDay: body?.allDay,
                isBreak: body?.isBreak,
                notes: body?.description || body?.title,
                timezone,
                createdDate: dayjs().format(),
                deleted: false,
                priority: body?.priority || 1,
                isFollowUp: false,
                isPreEvent: false,
                isPostEvent: false,
                modifiable: body?.priority > 1 || newPreferredTimeRanges?.length > 0,
                anyoneCanAddSelf: defaultMeetingPreferences?.anyoneCanAddSelf,
                guestsCanInviteOthers: defaultMeetingPreferences?.guestsCanInviteOthers,
                guestsCanSeeOtherGuests: defaultMeetingPreferences?.guestsCanSeeOtherGuests,
                transparency: body?.transparency || defaultMeetingPreferences?.transparency,
                visibility: body?.visibility ||
                    defaultMeetingPreferences?.visibility,
                originalStartDate: undefined,
                originalAllDay: false,
                summary: body?.title,
                updatedAt: dayjs().format(),
                calendarId: primaryCalendar?.id,
                eventId: undefined,
                conferenceId: conference?.id,
                sendUpdates: defaultMeetingPreferences?.sendUpdates,
                duration: body?.duration,
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
            const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, eventToUpsertLocal?.id, eventToUpsertLocal?.endDate, eventToUpsertLocal?.startDate, conference?.id ? 1 : 0, undefined, eventToUpsertLocal?.sendUpdates, eventToUpsertLocal?.anyoneCanAddSelf, body?.attendees?.map((a) => ({ email: a?.email })), conference?.id
                ? {
                    type: conference?.app === 'zoom'
                        ? 'addOn'
                        : 'hangoutsMeet',
                    name: conference?.name,
                    conferenceId: conference?.id,
                    entryPoints: conference?.entryPoints,
                    createRequest: conference?.app === 'google'
                        ? {
                            requestId: conference?.requestId,
                            conferenceSolutionKey: {
                                type: 'hangoutsMeet',
                            },
                        }
                        : undefined,
                }
                : undefined, eventToUpsertLocal?.summary, eventToUpsertLocal?.notes, timezone, eventToUpsertLocal?.allDay &&
                dayjs(eventToUpsertLocal?.startDate)
                    .tz(timezone)
                    .format('YYYY-MM-DD'), eventToUpsertLocal?.allDay &&
                dayjs(eventToUpsertLocal?.endDate).tz(timezone).format('YYYY-MM-DD'), undefined, eventToUpsertLocal?.guestsCanInviteOthers, eventToUpsertLocal?.guestsCanModify, eventToUpsertLocal?.guestsCanSeeOtherGuests, eventToUpsertLocal?.originalStartDate, undefined, recur, remindersToUpdateEventId?.length > 0 ? googleReminder : undefined, undefined, undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, undefined, undefined, undefined, undefined, undefined, eventToUpsertLocal?.attachments, 'default', body?.location, undefined);
            eventToUpsertLocal.id = googleResValue.id;
            eventToUpsertLocal.eventId = googleResValue.googleEventId;
            remindersToUpdateEventId?.forEach((r) => ({
                ...r,
                eventId: eventToUpsertLocal.id,
            }));
            newPreferredTimeRanges?.forEach((p) => ({
                ...p,
                eventId: eventToUpsertLocal.id,
            }));
            attendees?.forEach((a) => ({ ...a, eventId: eventToUpsertLocal?.id }));
            await upsertConference(conference);
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
            if (remindersToUpdateEventId?.length > 0) {
                await insertReminders(remindersToUpdateEventId);
            }
            if (newPreferredTimeRanges?.length > 0) {
                await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
            }
            await upsertAttendeesforEvent(attendees);
        }
        else {
            const eventToUpsertLocal = {
                id: eventId,
                userId: body?.userId,
                title: body?.title,
                startDate: dayjs(body?.startDate).tz(timezone).format(),
                endDate: dayjs(body?.startDate)
                    .tz(timezone)
                    .add(body?.duration, 'm')
                    .format(),
                allDay: body?.allDay,
                isBreak: body?.isBreak,
                notes: body?.description || body?.title,
                timezone,
                createdDate: dayjs().format(),
                deleted: false,
                priority: body?.priority || 1,
                isFollowUp: false,
                isPreEvent: false,
                isPostEvent: false,
                modifiable: body?.priority > 1 || newPreferredTimeRanges?.length > 0,
                anyoneCanAddSelf: defaultMeetingPreferences?.anyoneCanAddSelf,
                guestsCanInviteOthers: defaultMeetingPreferences?.guestsCanInviteOthers,
                guestsCanSeeOtherGuests: defaultMeetingPreferences?.guestsCanSeeOtherGuests,
                transparency: body?.transparency || defaultMeetingPreferences?.transparency,
                visibility: body?.visibility ||
                    defaultMeetingPreferences?.visibility,
                originalStartDate: undefined,
                originalAllDay: false,
                summary: body?.title,
                updatedAt: dayjs().format(),
                calendarId: primaryCalendar?.id,
                eventId: undefined,
                sendUpdates: defaultMeetingPreferences?.sendUpdates,
                duration: body?.duration,
                timeBlocking: body?.bufferTime,
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
            const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, eventToUpsertLocal?.id, eventToUpsertLocal?.endDate, eventToUpsertLocal?.startDate, 0, undefined, eventToUpsertLocal?.sendUpdates, eventToUpsertLocal?.anyoneCanAddSelf, body?.attendees?.map((a) => ({ email: a?.email })), undefined, eventToUpsertLocal?.title, eventToUpsertLocal?.notes, timezone, undefined, undefined, undefined, eventToUpsertLocal?.guestsCanInviteOthers, eventToUpsertLocal?.guestsCanModify, eventToUpsertLocal?.guestsCanSeeOtherGuests, eventToUpsertLocal?.originalStartDate, undefined, recur, remindersToUpdateEventId?.length > 0 ? googleReminder : undefined, undefined, undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, undefined, undefined, undefined, undefined, undefined, eventToUpsertLocal?.attachments, 'default', body?.location, undefined);
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
            newPreferredTimeRanges?.forEach((p) => ({
                ...p,
                eventId: eventToUpsertLocal.id,
            }));
            attendees?.forEach((a) => ({ ...a, eventId: eventToUpsertLocal?.id }));
            if (remindersToUpdateEventId?.length > 0) {
                await insertReminders(remindersToUpdateEventId);
            }
            if (newPreferredTimeRanges?.length > 0) {
                await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
            }
            await upsertAttendeesforEvent(attendees);
        }
        const searchVector = await convertEventTitleToOpenAIVector(body?.title);
        if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
            await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, body?.userId);
        }
        response.query = 'completed';
        response.data = 'event successfully created';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step add task');
    }
};
export const processCreateEventPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
    try {
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
            skill: 'createEvent',
        };
        const eventStartDate = extrapolateDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow);
        const defaultMeetingPreferences = await getChatMeetingPreferenceGivenUserId(userId);
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
        else if (defaultMeetingPreferences?.duration) {
            duration = defaultMeetingPreferences?.duration;
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
            attendees: jsonBody?.params?.attendees,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description || jsonBody?.params?.notes,
            conferenceApp: jsonBody?.params?.conference?.app ||
                defaultMeetingPreferences?.conferenceApp,
            startDate: jsonBody?.params?.startTime || eventStartDate,
            bufferTime: jsonBody?.params?.bufferTime || defaultMeetingPreferences?.bufferTime,
            reminders: jsonBody?.params?.alarms || defaultMeetingPreferences?.reminders || [],
            priority: jsonBody?.params?.priority || 1,
            timePreferences: dateJSONBody?.timePreferences || [],
            location: jsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility,
            isBreak: jsonBody?.params?.isBreak,
            allDay: dateJSONBody?.allDay,
            isFollowUp: jsonBody?.params?.isFollowUp,
        };
        if (recurObject?.frequency) {
            body.recur = recurObject;
        }
        console.log(body, ' body');
        const newAttendees = [];
        for (const a of body?.attendees) {
            if (!a?.email) {
                const contact = await getContactByNameWithUserId(userId, `%${a?.name}%`);
                if (contact?.emails?.[0]?.value) {
                    const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
                    const anyEmail = contact?.emails?.[0]?.value;
                    newAttendees.push({ ...a, email: primaryEmail || anyEmail });
                }
                else {
                    response.query = 'missing_fields';
                    missingFields.required.push(requiredFields.optional?.[7]?.['and']?.[2]);
                    response.data = missingFields;
                    response.prevData = body;
                    response.prevJsonBody = jsonBody;
                    response.prevDateJsonBody = dateJSONBody;
                }
            }
            else {
                newAttendees.push(a);
            }
        }
        body.attendees = newAttendees;
        if (!body?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
            response.data = missingFields;
            response.prevData = body;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepCreatEvent(body, timezone, defaultMeetingPreferences, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process create event');
    }
};
export const processCreateEventMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
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
            skill: 'createEvent',
        };
        const eventStartDate = extrapolateDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeFromNow);
        const defaultMeetingPreferences = await getChatMeetingPreferenceGivenUserId(userId);
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
        else if (defaultMeetingPreferences?.duration) {
            duration = defaultMeetingPreferences?.duration;
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
            attendees: jsonBody?.params?.attendees ||
                messageHistoryObject?.prevJsonBody?.params?.attendees,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description ||
                jsonBody?.params?.notes ||
                messageHistoryObject?.prevJsonBody?.params?.description ||
                messageHistoryObject?.prevJsonBody?.params?.notes,
            conferenceApp: jsonBody?.params?.conference?.app ||
                messageHistoryObject?.prevJsonBody?.params?.conference?.app ||
                defaultMeetingPreferences?.conferenceApp,
            startDate: jsonBody?.params?.startTime ||
                messageHistoryObject?.prevJsonBody?.params?.startTime ||
                eventStartDate,
            bufferTime: jsonBody?.params?.bufferTime ||
                messageHistoryObject?.prevJsonBody?.params?.bufferTime ||
                defaultMeetingPreferences?.bufferTime,
            reminders: jsonBody?.params?.alarms ||
                messageHistoryObject?.prevJsonBody?.params?.alarms ||
                defaultMeetingPreferences?.reminders ||
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
        if (!prevBody?.duration) {
            prevBody.duration = newBody?.duration;
        }
        if (!prevBody?.description) {
            prevBody.description = newBody?.description;
        }
        if (!prevBody?.conferenceApp) {
            prevBody.conferenceApp = newBody?.conferenceApp;
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
        if (prevBody.allDay === undefined) {
            prevBody.allDay = newBody?.allDay;
        }
        if (prevBody.isFollowUp === undefined) {
            prevBody.isFollowUp = newBody?.isFollowUp;
        }
        const newAttendees = [];
        for (const a of newBody?.attendees) {
            if (!a?.email) {
                const contact = await getContactByNameWithUserId(userId, `%${a?.name}%`);
                if (contact?.emails?.[0]?.value) {
                    const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
                    const anyEmail = contact?.emails?.[0]?.value;
                    newAttendees.push({ ...a, email: primaryEmail || anyEmail });
                }
                else {
                    response.query = 'missing_fields';
                    missingFields.required.push(requiredFields.optional?.[7]?.['and']?.[2]);
                    response.data = missingFields;
                    response.prevData = prevBody;
                    response.prevJsonBody = jsonBody;
                    response.prevDateJsonBody = dateJSONBody;
                }
            }
            else {
                newAttendees.push(a);
            }
        }
        newBody.attendees = newAttendees;
        if (!(prevBody?.attendees?.length > 0)) {
            prevBody.attendees = newBody?.attendees;
        }
        if (!prevBody?.recur) {
            prevBody.recur = newBody?.recur;
        }
        if (!prevBody?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepCreatEvent(prevBody, timezone, defaultMeetingPreferences, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process create event missing fields returned');
    }
};
export const createEventControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let createEventRes = {
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
                createEventRes = await processCreateEventPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                createEventRes = await processCreateEventMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (createEventRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, createEventRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (createEventRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, createEventRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required =
                createEventRes?.data;
            messageHistoryObject.prevData = createEventRes?.prevData;
            messageHistoryObject.prevDataExtra = createEventRes?.prevDataExtra;
            messageHistoryObject.prevJsonBody = createEventRes?.prevJsonBody;
            messageHistoryObject.prevDateJsonBody = createEventRes?.prevDateJsonBody;
        }
        else if (createEventRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to create event');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBS0EsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLCtCQUErQixFQUMvQixpQkFBaUIsRUFDakIsK0JBQStCLEVBQy9CLGlCQUFpQixFQUNqQixpQkFBaUIsRUFDakIsMkJBQTJCLEVBQzNCLDZCQUE2QixFQUM3QixtREFBbUQsRUFDbkQscURBQXFELEVBQ3JELGdCQUFnQixFQUNoQiw2QkFBNkIsRUFDN0IsNkJBQTZCLEVBQzdCLDBDQUEwQyxFQUMxQyw0QkFBNEIsRUFDNUIsMEJBQTBCLEVBQzFCLGlCQUFpQixFQUNqQiwyQkFBMkIsRUFDM0IsY0FBYyxFQUNkLGVBQWUsRUFDZixlQUFlLEVBQ2YsK0JBQStCLEVBQy9CLG9DQUFvQyxFQUNwQyx1QkFBdUIsRUFDdkIsZ0JBQWdCLEVBQ2hCLFlBQVksR0FDYixNQUFNLHdCQUF3QixDQUFDO0FBQ2hDLE9BQU8sRUFBRSxtQ0FBbUMsRUFBRSxNQUFNLCtCQUErQixDQUFDO0FBQ3BGLE9BQU8sS0FBSyxNQUFNLE9BQU8sQ0FBQztBQVExQixPQUFPLEVBQUUsa0JBQWtCLEVBQUUsTUFBTSx1QkFBdUIsQ0FBQztBQUMzRCxPQUFPLEVBQUUsRUFBRSxJQUFJLElBQUksRUFBRSxNQUFNLE1BQU0sQ0FBQztBQUtsQyxPQUFPLEVBQUUsYUFBYSxFQUFFLE1BQU0sdUNBQXVDLENBQUM7QUFHdEUsT0FBTyxFQUFFLGlDQUFpQyxFQUFFLE1BQU0sd0NBQXdDLENBQUM7QUFVM0YsTUFBTSxDQUFDLE1BQU0sbUJBQW1CLEdBQUcsS0FBSyxFQUN0QyxJQUFxQixFQUNyQixRQUFnQixFQUNoQix5QkFBcUQsRUFDckQsUUFBYSxFQUNnQixFQUFFO0lBQy9CLElBQUksQ0FBQztRQUNILE1BQU0sT0FBTyxHQUFHLElBQUksRUFBRSxDQUFDO1FBRXZCLE1BQU0s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QyxRQUFRLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7WUFDckQsb0JBQW9CLENBQUMsS0FBSyxHQUFHLGdCQUFnQixDQUFDO1lBQzlDLG9CQUFvQixDQUFDLFFBQVE7Z0JBQzNCLGNBQWMsRUFBRSxJQUEwQixDQUFDO1lBQzdDLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxjQUFjLEVBQUUsUUFBUSxDQUFDO1lBQ3pELG9CQUFvQixDQUFDLGFBQWEsR0FBRyxjQUFjLEVBQUUsYUFBYSxDQUFDO1lBQ25FLG9CQUFvQixDQUFDLFlBQVksR0FBRyxjQUFjLEVBQUUsWUFBWSxDQUFDO1lBQ2pFLG9CQUFvQixDQUFDLGdCQUFnQixHQUFHLGNBQWMsRUFBRSxnQkFBZ0IsQ0FBQztRQUMzRSxDQUFDO2FBQU0sSUFBSSxjQUFjLEVBQUUsS0FBSyxLQUFLLGlCQUFpQixFQUFFLENBQUM7WUFDdkQsTUFBTSxnQkFBZ0IsR0FBeUI7Z0JBQzdDLElBQUksRUFBRSxXQUFXO2dCQUNqQixPQUFPLEVBQUUsNkNBQTZDO2FBQ3ZELENBQUM7WUFFRixvQkFBb0IsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7WUFDckQsb0JBQW9CLENBQUMsS0FBSyxHQUFHLGlCQUFpQixDQUFDO1lBQy9DLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxJQUFJLENBQUM7UUFDdkMsQ0FBQztRQUVELE9BQU8sb0JBQW9CLENBQUM7SUFDOUIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSx5QkFBeUIsQ0FBQyxDQUFDO0lBQzVDLENBQUM7QUFDSCxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgRGF0ZVRpbWVKU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9EYXRlVGltZUpTT05KU09OVHlwZSc7XG5pbXBvcnQgVXNlcklucHV0VG9KU09OVHlwZSwge1xuICBNdXRhdGVkQ2FsZW5kYXJFeHRyYWN0ZWRKU09OQXR0ZW5kZWVUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Vc2VySW5wdXRUb0pTT05UeXBlJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCByZXF1aXJlZEZpZWxkcyBmcm9tICcuL3JlcXVpcmVkRmllbGRzJztcbmltcG9ydCB7XG4gIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IsXG4gIGNyZWF0ZUdvb2dsZUV2ZW50LFxuICBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50LFxuICBjcmVhdGVSUnVsZVN0cmluZyxcbiAgY3JlYXRlWm9vbU1lZXRpbmcsXG4gIGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YSxcbiAgZmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWQsXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMsXG4gIGdlbmVyYXRlRGF0ZVRpbWUsXG4gIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZSxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lLFxuICBnZXRDb250YWN0QnlOYW1lV2l0aFVzZXJJZCxcbiAgZ2V0R2xvYmFsQ2FsZW5kYXIsXG4gIGdldFVzZXJDb250YWN0SW5mb3NHaXZlbklkcyxcbiAgZ2V0VXNlckdpdmVuSWQsXG4gIGdldFpvb21BUElUb2tlbixcbiAgaW5zZXJ0UmVtaW5kZXJzLFxuICBsaXN0VXNlckNvbnRhY3RJbmZvc0dpdmVuVXNlcklkLFxuICBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsXG4gIHVwc2VydEF0dGVuZGVlc2ZvckV2ZW50LFxuICB1cHNlcnRDb25mZXJlbmNlLFxuICB1cHNlcnRFdmVudHMsXG59IGZyb20gJ0BjaGF0L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlR2l2ZW5Vc2VySWQgfSBmcm9tICcuLi9zY2hlZHVsZU1lZXRpbmcvYXBpLWhlbHBlcic7XG5pbXBvcnQgZGF5anMgZnJvbSAnZGF5anMnO1xuaW1wb3J0IHtcbiAgRXZlbnRUeXBlLFxuICBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSxcbiAgUmVjdXJyZW5jZVJ1bGVUeXBlLFxuICBWaXNpYmlsaXR5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvRXZlbnRUeXBlJztcbmltcG9ydCB7IENyZWF0ZUV2ZW50VHlwZSB9IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IHsgZ29vZ2xlQ2FsZW5kYXJOYW1lIH0gZnJvbSAnQGNoYXQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCB7IEF0dGVuZGVlVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0F0dGVuZGVlVHlwZSc7XG5pbXBvcnQgeyBSZW1pbmRlclR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Hb29nbGVUeXBlcyc7XG5pbXBvcnQgeyBHb29nbGVSZW1pbmRlclR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Hb29nbGVSZW1pbmRlclR5cGUnO1xuaW1wb3J0IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUHJlZmVycmVkVGltZVJhbmdlVHlwZSc7XG5pbXBvcnQgeyBEYXlPZldlZWtFbnVtIH0gZnJvbSAnLi4vcmVzb2x2ZUNvbmZsaWN0aW5nRXZlbnRzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBDb25mZXJlbmNlVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0NvbmZlcmVuY2VUeXBlJztcbmltcG9ydCB7IEdvb2dsZVJlc1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Hb29nbGVSZXNUeXBlJztcbmltcG9ydCB7IHVwc2VydFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCB9IGZyb20gJy4uL3Jlc29sdmVDb25mbGljdGluZ0V2ZW50cy9hcGktaGVscGVyJztcbmltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCB7XG4gIEFzc2lzdGFudE1lc3NhZ2VUeXBlLFxuICBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvTWVzc2FnaW5nL01lc3NhZ2luZ1R5cGVzJztcbmltcG9ydCB7IENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUnO1xuaW1wb3J0IFJlc3BvbnNlQWN0aW9uVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXNwb25zZUFjdGlvblR5cGUnO1xuaW1wb3J0IHJlbGF0aXZlVGltZSBmcm9tICdkYXlqcy9wbHVnaW4vcmVsYXRpdmVUaW1lJztcblxuZXhwb3J0IGNvbnN0IGZpbmFsU3RlcENyZWF0RXZlbnQgPSBhc3luYyAoXG4gIGJvZHk6IENyZWF0ZUV2ZW50VHlwZSxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlczogQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUsXG4gIHJlc3BvbnNlOiBhbnlcbik6IFByb21pc2U8UmVzcG9uc2VBY3Rpb25UeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKTtcblxuICAgIGNvbnN0IGF0dGVuZGVlczogQXR0ZW5kZWVUeXBlW10gPSBbXTtcblxuICAgIGlmIChib2R5Py5hdHRlbmRlZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnN0IGFXaXRoRW1haWxzID0gYm9keT8uYXR0ZW5kZWVzPy5maWx0ZXIoKGEpID0+ICEhYT8uZW1haWwpO1xuXG4gICAgICBjb25zdCBhV2l0aENvbnRhY3RJbmZvcyA9IGF3YWl0IGdldFVzZXJDb250YWN0SW5mb3NHaXZlbklkcyhcbiAgICAgICAgYVdpdGhFbWFpbHM/Lm1hcCgoYSkgPT4gYT8uZW1haWwpXG4gICAgICApO1xuXG4gICAgICBjb25zdCB1c2VyQ29udGFjdEluZm9zID0gYXdhaXQgbGlzdFVzZXJDb250YWN0SW5mb3NHaXZlblVzZXJJZChcbiAgICAgICAgYm9keT8udXNlcklkXG4gICAgICApO1xuXG4gICAgICBjb25zdCBwcm92aWRlZEhvc3RJbmZvID0gYm9keT8uYXR0ZW5kZWVzPy5maW5kKChhKSA9PiBhPy5pc0hvc3QgPT09IHRydWUpO1xuXG4gICAgICBjb25zdCBwcmltYXJ5SW5mb0l0ZW0gPSB1c2VyQ29udGFjdEluZm9zPy5maW5kKFxuICAgICAgICAodSkgPT4gdS5wcmltYXJ5ICYmIHUudHlwZSA9PT0gJ2VtYWlsJ1xuICAgICAgKTtcblxuICAgICAgY29uc3QgdXNlciA9IGF3YWl0IGdldFVzZXJHaXZlbklkKGJvZHk/LnVzZXJJZCk7XG5cbiAgICAgIGNvbnN0IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvOiBNdXRhdGVkQ2FsZW5kYXJFeHRyYWN0ZWRKU09OQXR0ZW5kZWVUeXBlID1cbiAgICAgICAge1xuICAgICAgICAgIG5hbWU6IHByaW1hcnlJbmZvSXRlbT8ubmFtZSB8fCB1c2VyPy5uYW1lLFxuICAgICAgICAgIGVtYWlsOiBwcmltYXJ5SW5mb0l0ZW0/LmlkIHx8IHVzZXI/LmVtYWlsLFxuICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAgICAgfTtcblxuICAgICAgaWYgKCFwcm92aWRlZEhvc3RJbmZvICYmIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5lbWFpbCkge1xuICAgICAgICBib2R5Py5hdHRlbmRlZXMucHVzaChwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbyk7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGF0dGVuZGVlc0Zyb21FeHRyYWN0ZWRKU09OID0gYm9keT8uYXR0ZW5kZWVzO1xuXG4gICAgICBmb3IgKGNvbnN0IGEgb2YgYXR0ZW5kZWVzRnJvbUV4dHJhY3RlZEpTT04pIHtcbiAgICAgICAgY29uc3QgY29udGFjdCA9IGF3YWl0IGZpbmRDb250YWN0QnlFbWFpbEdpdmVuVXNlcklkKFxuICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICBhLmVtYWlsXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IHVzZXJJZEZvdW5kID0gYVdpdGhDb250YWN0SW5mb3M/LmZpbmQoKGIpID0+IGI/LmlkID09PSBhPy5lbWFpbCk7XG5cbiAgICAgICAgY29uc3QgYXR0ZW5kZWU6IEF0dGVuZGVlVHlwZSA9IHtcbiAgICAgICAgICBpZDogdXNlcklkRm91bmQ/LnVzZXJJZCB8fCB1dWlkKCksXG4gICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgbmFtZTpcbiAgICAgICAgICAgIGE/Lm5hbWUgfHxcbiAgICAgICAgICAgIGNvbnRhY3Q/Lm5hbWUgfHxcbiAgICAgICAgICAgIGAke2NvbnRhY3Q/LmZpcnN0TmFtZX0gJHtjb250YWN0Py5sYXN0TmFtZX1gLFxuICAgICAgICAgIGNvbnRhY3RJZDogY29udGFjdD8uaWQsXG4gICAgICAgICAgZW1haWxzOiBbeyBwcmltYXJ5OiB0cnVlLCB2YWx1ZTogYT8uZW1haWwgfV0sXG4gICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgIH07XG5cbiAgICAgICAgYXR0ZW5kZWVzLnB1c2goYXR0ZW5kZWUpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHByaW1hcnlDYWxlbmRhciA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKGJvZHk/LnVzZXJJZCk7XG5cbiAgICBpZiAoIXByaW1hcnlDYWxlbmRhcj8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpbWFyeSBjYWxlbmRhciBmb3VuZCBpbnNpZGUgY3JlYXRlQWdlbmRhJyk7XG4gICAgfVxuXG4gICAgY29uc3QgY2FsSW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJOYW1lXG4gICAgKTtcblxuICAgIGlmICghY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ25vIGNsaWVudCB0eXBlIGluc2lkZSBjYWxlbmRhciBpbnRlZ3JhdGlvbiBpbnNpZGUgY3JlYXRlIGFnZW5kYSdcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkOiBSZW1pbmRlclR5cGVbXSA9IFtdO1xuXG4gICAgaWYgKGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3QgbmV3UmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXSA9IGJvZHk/LnJlbWluZGVycy5tYXAoKHIpID0+ICh7XG4gICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICBldmVudElkLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgbWludXRlczogcixcbiAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgfSkpO1xuXG4gICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQucHVzaCguLi5uZXdSZW1pbmRlcnMpO1xuICAgIH1cblxuICAgIGNvbnN0IGdvb2dsZVJlbWluZGVyOiBHb29nbGVSZW1pbmRlclR5cGUgPSB7XG4gICAgICBvdmVycmlkZXM6IHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubWFwKChyKSA9PiAoe1xuICAgICAgICBtZXRob2Q6ICdlbWFpbCcsXG4gICAgICAgIG1pbnV0ZXM6IHI/Lm1pbnV0ZXMsXG4gICAgICB9KSksXG4gICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICB9O1xuXG4gICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlczogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IHRpbWVwcmVmZXJlbmNlIG9mIGJvZHk/LnRpbWVQcmVmZXJlbmNlcykge1xuICAgICAgaWYgKHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBmb3IgKGNvbnN0IGRheU9mV2VlayBvZiB0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWspIHtcbiAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICAgIGRheU9mV2VlazogRGF5T2ZXZWVrRW51bVtkYXlPZldlZWtdLFxuICAgICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICB9O1xuXG4gICAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgIH07XG5cbiAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgcmVjdXIgPSBjcmVhdGVSUnVsZVN0cmluZyhcbiAgICAgIGJvZHk/LnJlY3VyPy5mcmVxdWVuY3ksXG4gICAgICBib2R5Py5yZWN1cj8uaW50ZXJ2YWwsXG4gICAgICBib2R5Py5yZWN1cj8uYnlXZWVrRGF5LFxuICAgICAgYm9keT8ucmVjdXI/Lm9jY3VycmVuY2UsXG4gICAgICBib2R5Py5yZWN1cj8uZW5kRGF0ZSxcbiAgICAgIGJvZHk/LnJlY3VyPy5CeU1vbnRoRGF5XG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKHJlY3VyLCAnIHJlY3VyJyk7XG5cbiAgICBsZXQgY29uZmVyZW5jZTogQ29uZmVyZW5jZVR5cGUgfCB7fSA9IHt9O1xuXG4gICAgaWYgKGJvZHk/LmNvbmZlcmVuY2VBcHApIHtcbiAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbihib2R5Py51c2VySWQpO1xuICAgICAgY29uZmVyZW5jZSA9XG4gICAgICAgIHpvb21Ub2tlbiAmJiBib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbSdcbiAgICAgICAgICA/IHt9XG4gICAgICAgICAgOiB7XG4gICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgICBjYWxlbmRhcklkOiBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICAgICAgICBhcHA6ICdnb29nbGUnLFxuICAgICAgICAgICAgICBuYW1lOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgICAgICAgICAgICBub3RlczogYm9keT8uZGVzY3JpcHRpb24gfHwgYm9keT8udGl0bGUsXG4gICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgICAgICAgICAgIHJlcXVlc3RJZDogdXVpZCgpLFxuICAgICAgICAgICAgfTtcblxuICAgICAgaWYgKHpvb21Ub2tlbiAmJiBib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbScpIHtcbiAgICAgICAgY29uc29sZS5sb2coem9vbVRva2VuLCAnIHpvb21Ub2tlbiBpbnNpZGUgaWYgKHpvb21Ub2tlbiknKTtcblxuICAgICAgICBjb25zdCB6b29tT2JqZWN0ID0gYXdhaXQgY3JlYXRlWm9vbU1lZXRpbmcoXG4gICAgICAgICAgem9vbVRva2VuLFxuICAgICAgICAgIGJvZHk/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBib2R5Py50aXRsZSxcbiAgICAgICAgICBib2R5Py5kdXJhdGlvbixcbiAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnByaW1hcnlFbWFpbCxcbiAgICAgICAgICBib2R5Py5hdHRlbmRlZXM/Lm1hcCgoYSkgPT4gYT8uZW1haWwpLFxuICAgICAgICAgIGJvZHk/LnJlY3VyIGFzIGFueVxuICAgICAgICApO1xuXG4gICAgICAgIGNvbnNvbGUubG9nKHpvb21PYmplY3QsICcgem9vbU9iamVjdCBhZnRlciBjcmVhdGVab29tTWVldGluZycpO1xuXG4gICAgICAgIGlmICh6b29tT2JqZWN0KSB7XG4gICAgICAgICAgY29uZmVyZW5jZSA9IHtcbiAgICAgICAgICAgIGlkOiBgJHt6b29tT2JqZWN0Py5pZH1gLFxuICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgICBjYWxlbmRhcklkOiBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICAgICAgYXBwOiAnem9vbScsXG4gICAgICAgICAgICBuYW1lOiB6b29tT2JqZWN0Py5hZ2VuZGEsXG4gICAgICAgICAgICBub3Rlczogem9vbU9iamVjdD8uYWdlbmRhLFxuICAgICAgICAgICAgam9pblVybDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICBzdGFydFVybDogem9vbU9iamVjdD8uc3RhcnRfdXJsLFxuICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgICAgIGVudHJ5UG9pbnRzOiBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBlbnRyeVBvaW50VHlwZTogJ3ZpZGVvJyxcbiAgICAgICAgICAgICAgICBsYWJlbDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICAgICAgcGFzc3dvcmQ6IHpvb21PYmplY3Q/LnBhc3N3b3JkLFxuICAgICAgICAgICAgICAgIHVyaTogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0gYXMgQ29uZmVyZW5jZVR5cGU7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgY29uc3QgZXZlbnRUb1Vwc2VydExvY2FsOiBFdmVudFR5cGUgPSB7XG4gICAgICAgIGlkOiBldmVudElkLFxuICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgdGl0bGU6IGJvZHk/LnRpdGxlLFxuICAgICAgICBzdGFydERhdGU6IGRheWpzKGJvZHk/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgpLFxuICAgICAgICBlbmREYXRlOiBkYXlqcyhib2R5Py5zdGFydERhdGUpXG4gICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgIC5hZGQoYm9keT8uZHVyYXRpb24sICdtJylcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgIGFsbERheTogYm9keT8uYWxsRGF5LFxuICAgICAgICBpc0JyZWFrOiBib2R5Py5pc0JyZWFrLFxuICAgICAgICBub3RlczogYm9keT8uZGVzY3JpcHRpb24gfHwgYm9keT8udGl0bGUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgIHByaW9yaXR5OiBib2R5Py5wcmlvcml0eSB8fCAxLFxuICAgICAgICBpc0ZvbGxvd1VwOiBmYWxzZSxcbiAgICAgICAgaXNQcmVFdmVudDogZmFsc2UsXG4gICAgICAgIGlzUG9zdEV2ZW50OiBmYWxzZSxcbiAgICAgICAgbW9kaWZpYWJsZTogYm9keT8ucHJpb3JpdHkgPiAxIHx8IG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDAsXG4gICAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czpcbiAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgdHJhbnNwYXJlbmN5OlxuICAgICAgICAgIGJvZHk/LnRyYW5zcGFyZW5jeSB8fCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy50cmFuc3BhcmVuY3ksXG4gICAgICAgIHZpc2liaWxpdHk6XG4gICAgICAgICAgKGJvZHk/LnZpc2liaWxpdHkgYXMgVmlzaWJpbGl0eVR5cGUpIHx8XG4gICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8udmlzaWJpbGl0eSxcbiAgICAgICAgb3JpZ2luYWxTdGFydERhdGU6IHVuZGVmaW5lZCxcbiAgICAgICAgb3JpZ2luYWxBbGxEYXk6IGZhbHNlLFxuICAgICAgICBzdW1tYXJ5OiBib2R5Py50aXRsZSxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBjYWxlbmRhcklkOiBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICBldmVudElkOiB1bmRlZmluZWQsXG4gICAgICAgIGNvbmZlcmVuY2VJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZCxcbiAgICAgICAgc2VuZFVwZGF0ZXM6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnNlbmRVcGRhdGVzLFxuICAgICAgICBkdXJhdGlvbjogYm9keT8uZHVyYXRpb24sXG4gICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eTogdHJ1ZSxcbiAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nOiBib2R5Py5idWZmZXJUaW1lID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZTpcbiAgICAgICAgICBib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDAgPyB0cnVlIDogZmFsc2UsXG4gICAgICAgIHVzZXJNb2RpZmllZFJlbWluZGVyczogYm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsOlxuICAgICAgICAgIGJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCA/IHRydWUgOiBmYWxzZSxcbiAgICAgICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb246IHRydWUsXG4gICAgICAgIGxvY2F0aW9uOiB7IHRpdGxlOiBib2R5Py5sb2NhdGlvbiB9LFxuICAgICAgICByZWN1cnJlbmNlOiByZWN1cixcbiAgICAgICAgcmVjdXJyZW5jZVJ1bGU6IHtcbiAgICAgICAgICBmcmVxdWVuY3k6IGJvZHk/LnJlY3VyPy5mcmVxdWVuY3ksXG4gICAgICAgICAgaW50ZXJ2YWw6IGJvZHk/LnJlY3VyPy5pbnRlcnZhbCxcbiAgICAgICAgICBieVdlZWtEYXk6IGJvZHk/LnJlY3VyPy5ieVdlZWtEYXksXG4gICAgICAgICAgb2NjdXJyZW5jZTogYm9keT8ucmVjdXI/Lm9jY3VycmVuY2UsXG4gICAgICAgICAgZW5kRGF0ZTogYm9keT8ucmVjdXI/LmVuZERhdGUsXG4gICAgICAgICAgYnlNb250aERheTogYm9keT8ucmVjdXI/LkJ5TW9udGhEYXksXG4gICAgICAgIH0sXG4gICAgICB9O1xuXG4gICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgIHByaW1hcnlDYWxlbmRhcj8uaWQsXG4gICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmlkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmVuZERhdGUsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3RhcnREYXRlLFxuICAgICAgICAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkID8gMSA6IDAsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zZW5kVXBkYXRlcyxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICBib2R5Py5hdHRlbmRlZXM/Lm1hcCgoYSkgPT4gKHsgZW1haWw6IGE/LmVtYWlsIH0pKSxcbiAgICAgICAgKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZFxuICAgICAgICAgID8ge1xuICAgICAgICAgICAgICB0eXBlOlxuICAgICAgICAgICAgICAgIChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uYXBwID09PSAnem9vbSdcbiAgICAgICAgICAgICAgICAgID8gJ2FkZE9uJ1xuICAgICAgICAgICAgICAgICAgOiAnaGFuZ291dHNNZWV0JyxcbiAgICAgICAgICAgICAgbmFtZTogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5uYW1lLFxuICAgICAgICAgICAgICBjb25mZXJlbmNlSWQ6IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uaWQsXG4gICAgICAgICAgICAgIGVudHJ5UG9pbnRzOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmVudHJ5UG9pbnRzLFxuICAgICAgICAgICAgICBjcmVhdGVSZXF1ZXN0OlxuICAgICAgICAgICAgICAgIChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uYXBwID09PSAnZ29vZ2xlJ1xuICAgICAgICAgICAgICAgICAgPyB7XG4gICAgICAgICAgICAgICAgICAgICAgcmVxdWVzdElkOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LnJlcXVlc3RJZCxcbiAgICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlU29sdXRpb25LZXk6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgIHR5cGU6ICdoYW5nb3V0c01lZXQnLFxuICAgICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICAgICAgfVxuICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnN1bW1hcnksXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8ubm90ZXMsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmFsbERheSAmJlxuICAgICAgICAgIGRheWpzKGV2ZW50VG9VcHNlcnRMb2NhbD8uc3RhcnREYXRlKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmFsbERheSAmJlxuICAgICAgICAgIGRheWpzKGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICByZWN1cixcbiAgICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwID8gZ29vZ2xlUmVtaW5kZXIgOiB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy52aXNpYmlsaXR5LFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5hdHRhY2htZW50cyxcbiAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICBib2R5Py5sb2NhdGlvbixcbiAgICAgICAgdW5kZWZpbmVkXG4gICAgICApO1xuXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcblxuICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5mb3JFYWNoKChyKSA9PiAoe1xuICAgICAgICAuLi5yLFxuICAgICAgICBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWwuaWQsXG4gICAgICB9KSk7XG5cbiAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/LmZvckVhY2goKHApID0+ICh7XG4gICAgICAgIC4uLnAsXG4gICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbC5pZCxcbiAgICAgIH0pKTtcblxuICAgICAgYXR0ZW5kZWVzPy5mb3JFYWNoKChhKSA9PiAoeyAuLi5hLCBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWw/LmlkIH0pKTtcblxuICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKTtcblxuICAgICAgaWYgKGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQgfHwgYm9keT8uYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgY29uc3QgcmV0dXJuVmFsdWVzID0gY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21FdmVudChcbiAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWwsXG4gICAgICAgICAgYm9keT8uYnVmZmVyVGltZVxuICAgICAgICApO1xuXG4gICAgICAgIGlmIChyZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQpIHtcbiAgICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgICAgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5pZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZW5kRGF0ZSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgICAgMCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRpdGxlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZFxuICAgICAgICAgICk7XG5cbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuICAgICAgICAgIHJldHVyblZhbHVlcy5uZXdFdmVudC5wb3N0RXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgICAgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uaWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgICAgMCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRpdGxlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8ubm90ZXMsXG4gICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZFxuICAgICAgICAgICk7XG5cbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnByZUV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZDtcbiAgICAgICAgfVxuXG4gICAgICAgIGF3YWl0IHVwc2VydEV2ZW50cyhcbiAgICAgICAgICBbXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50LFxuICAgICAgICAgIF0/LmZpbHRlcigoZSkgPT4gISFlKVxuICAgICAgICApO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFtldmVudFRvVXBzZXJ0TG9jYWxdKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCkge1xuICAgICAgICBhd2FpdCBpbnNlcnRSZW1pbmRlcnMocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkKTtcbiAgICAgIH1cblxuICAgICAgaWYgKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgYXdhaXQgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMpO1xuICAgICAgfVxuXG4gICAgICBhd2FpdCB1cHNlcnRBdHRlbmRlZXNmb3JFdmVudChhdHRlbmRlZXMpO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBldmVudFRvVXBzZXJ0TG9jYWw6IEV2ZW50VHlwZSA9IHtcbiAgICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICB0aXRsZTogYm9keT8udGl0bGUsXG4gICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoYm9keT8uc3RhcnREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCksXG4gICAgICAgIGVuZERhdGU6IGRheWpzKGJvZHk/LnN0YXJ0RGF0ZSlcbiAgICAgICAgICAudHoodGltZXpvbmUpXG4gICAgICAgICAgLmFkZChib2R5Py5kdXJhdGlvbiwgJ20nKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgYWxsRGF5OiBib2R5Py5hbGxEYXksXG4gICAgICAgIGlzQnJlYWs6IGJvZHk/LmlzQnJlYWssXG4gICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgcHJpb3JpdHk6IGJvZHk/LnByaW9yaXR5IHx8IDEsXG4gICAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgICBtb2RpZmlhYmxlOiBib2R5Py5wcmlvcml0eSA+IDEgfHwgbmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCxcbiAgICAgICAgYW55b25lQ2FuQWRkU2VsZjogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOlxuICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICB0cmFuc3BhcmVuY3k6XG4gICAgICAgICAgYm9keT8udHJhbnNwYXJlbmN5IHx8IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgdmlzaWJpbGl0eTpcbiAgICAgICAgICAoYm9keT8udmlzaWJpbGl0eSBhcyBWaXNpYmlsaXR5VHlwZSkgfHxcbiAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy52aXNpYmlsaXR5LFxuICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICAgIHN1bW1hcnk6IGJvZHk/LnRpdGxlLFxuICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgIGNhbGVuZGFySWQ6IHByaW1hcnlDYWxlbmRhcj8uaWQsXG4gICAgICAgIGV2ZW50SWQ6IHVuZGVmaW5lZCxcbiAgICAgICAgc2VuZFVwZGF0ZXM6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnNlbmRVcGRhdGVzLFxuICAgICAgICBkdXJhdGlvbjogYm9keT8uZHVyYXRpb24sXG4gICAgICAgIHRpbWVCbG9ja2luZzogYm9keT8uYnVmZmVyVGltZSxcbiAgICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5OiB0cnVlLFxuICAgICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmc6IGJvZHk/LmJ1ZmZlclRpbWUgPyB0cnVlIDogZmFsc2UsXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlOlxuICAgICAgICAgIGJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCA/IHRydWUgOiBmYWxzZSxcbiAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzOiBib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDAgPyB0cnVlIDogZmFsc2UsXG4gICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWw6XG4gICAgICAgICAgYm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvbjogdHJ1ZSxcbiAgICAgICAgbG9jYXRpb246IHsgdGl0bGU6IGJvZHk/LmxvY2F0aW9uIH0sXG4gICAgICAgIHJlY3VycmVuY2U6IHJlY3VyLFxuICAgICAgICByZWN1cnJlbmNlUnVsZToge1xuICAgICAgICAgIGZyZXF1ZW5jeTogYm9keT8ucmVjdXI/LmZyZXF1ZW5jeSxcbiAgICAgICAgICBpbnRlcnZhbDogYm9keT8ucmVjdXI/LmludGVydmFsLFxuICAgICAgICAgIGJ5V2Vla0RheTogYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAgICAgICBvY2N1cnJlbmNlOiBib2R5Py5yZWN1cj8ub2NjdXJyZW5jZSxcbiAgICAgICAgICBlbmREYXRlOiBib2R5Py5yZWN1cj8uZW5kRGF0ZSxcbiAgICAgICAgICBieU1vbnRoRGF5OiBib2R5Py5yZWN1cj8uQnlNb250aERheSxcbiAgICAgICAgfSxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zdGFydERhdGUsXG4gICAgICAgIDAsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zZW5kVXBkYXRlcyxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICBib2R5Py5hdHRlbmRlZXM/Lm1hcCgoYSkgPT4gKHsgZW1haWw6IGE/LmVtYWlsIH0pKSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRpdGxlLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lm5vdGVzLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lm9yaWdpbmFsU3RhcnREYXRlLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHJlY3VyLFxuICAgICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lmxlbmd0aCA+IDAgPyBnb29nbGVSZW1pbmRlciA6IHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udHJhbnNwYXJlbmN5LFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnZpc2liaWxpdHksXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmF0dGFjaG1lbnRzLFxuICAgICAgICAnZGVmYXVsdCcsXG4gICAgICAgIGJvZHk/LmxvY2F0aW9uLFxuICAgICAgICB1bmRlZmluZWRcbiAgICAgICk7XG5cbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuXG4gICAgICBpZiAoYm9keT8uYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCB8fCBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCkge1xuICAgICAgICBjb25zdCByZXR1cm5WYWx1ZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50KFxuICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbCxcbiAgICAgICAgICBib2R5Py5idWZmZXJUaW1lXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCkge1xuICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmlkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zdGFydERhdGUsXG4gICAgICAgICAgICAwLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zZW5kVXBkYXRlcyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udGl0bGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lm5vdGVzLFxuICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkID0gZ29vZ2xlUmVzVmFsdWUuaWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnBvc3RFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQ7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAocmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudCkge1xuICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5pZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zdGFydERhdGUsXG4gICAgICAgICAgICAwLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udGl0bGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucHJlRXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgICB9XG5cbiAgICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFxuICAgICAgICAgIFtcbiAgICAgICAgICAgIHJldHVyblZhbHVlcy5uZXdFdmVudCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQsXG4gICAgICAgICAgXT8uZmlsdGVyKChlKSA9PiAhIWUpXG4gICAgICAgICk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBhd2FpdCB1cHNlcnRFdmVudHMoW2V2ZW50VG9VcHNlcnRMb2NhbF0pO1xuICAgICAgfVxuXG4gICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/LmZvckVhY2goKHIpID0+ICh7XG4gICAgICAgIC4uLnIsXG4gICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbC5pZCxcbiAgICAgIH0pKTtcblxuICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcz8uZm9yRWFjaCgocCkgPT4gKHtcbiAgICAgICAgLi4ucCxcbiAgICAgICAgZXZlbnRJZDogZXZlbnRUb1Vwc2VydExvY2FsLmlkLFxuICAgICAgfSkpO1xuXG4gICAgICBhdHRlbmRlZXM/LmZvckVhY2goKGEpID0+ICh7IC4uLmEsIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQgfSkpO1xuXG4gICAgICBpZiAocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGF3YWl0IGluc2VydFJlbWluZGVycyhyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQpO1xuICAgICAgfVxuXG4gICAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcyk7XG4gICAgICB9XG5cbiAgICAgIGF3YWl0IHVwc2VydEF0dGVuZGVlc2ZvckV2ZW50KGF0dGVuZGVlcyk7XG4gICAgfVxuXG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSk7XG4gICAgaWYgKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDAgfHwgYm9keT8ucHJpb3JpdHkgPiAxKSB7XG4gICAgICBhd2FpdCBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2goXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgICAgYm9keT8udXNlcklkXG4gICAgICApO1xuICAgIH1cblxuICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgcmVzcG9uc2UuZGF0YSA9ICdldmVudCBzdWNjZXNzZnVsbHkgY3JlYXRlZCc7XG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZmluYWwgc3RlcCBhZGQgdGFzaycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0NyZWF0ZUV2ZW50UGVuZGluZyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICBkYXRlSlNPTkJvZHk6IERhdGVUaW1lSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmdcbik6IFByb21pc2U8UmVzcG9uc2VBY3Rpb25UeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IGR1cmF0aW9uID0gMDtcblxuICAgIGNvbnN0IHllYXIgPSBkYXRlSlNPTkJvZHk/LnllYXI7XG4gICAgY29uc3QgbW9udGggPSBkYXRlSlNPTkJvZHk/Lm1vbnRoO1xuICAgIGNvbnN0IGRheSA9IGRhdGVKU09OQm9keT8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXkgPSBkYXRlSlNPTkJvZHk/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ciA9IGRhdGVKU09OQm9keT8uaG91cjtcbiAgICBjb25zdCBtaW51dGUgPSBkYXRlSlNPTkJvZHk/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWUgPSBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICAgIGRhdGVUaW1lOiB7IHJlcXVpcmVkOiBbXSB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ2NyZWF0ZUV2ZW50JyxcbiAgICB9O1xuXG4gICAgY29uc3QgZXZlbnRTdGFydERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhcixcbiAgICAgIG1vbnRoLFxuICAgICAgZGF5LFxuICAgICAgaXNvV2Vla2RheSxcbiAgICAgIGhvdXIsXG4gICAgICBtaW51dGUsXG4gICAgICBzdGFydFRpbWUsXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgY29uc3QgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyA9XG4gICAgICBhd2FpdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VHaXZlblVzZXJJZCh1c2VySWQpO1xuXG4gICAgaWYgKGRhdGVKU09OQm9keT8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKGRhdGVKU09OQm9keT8uc3RhcnRUaW1lICYmIGRhdGVKU09OQm9keT8uZW5kVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUsICdISDptbScpO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKGRhdGVKU09OQm9keS5lbmRUaW1lLCAnSEg6bW0nKTtcblxuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSAmJiBqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKSB7XG4gICAgICBjb25zdCBzdGFydFRpbWVPYmplY3QgPSBkYXlqcyhqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUpO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUpO1xuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGR1cmF0aW9uID0gMzA7XG4gICAgfVxuXG4gICAgbGV0IHJlY3VyT2JqZWN0OiBSZWN1cnJlbmNlUnVsZVR5cGUgfCB7fSA9IHt9O1xuICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kpIHtcbiAgICAgIGNvbnN0IHJlY3VyRW5kRGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgICAgY3VycmVudFRpbWUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5tb250aCxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICAgKTtcblxuICAgICAgcmVjdXJPYmplY3QgPSB7XG4gICAgICAgIGZyZXF1ZW5jeTpcbiAgICAgICAgICAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlKSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWw6XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCxcbiAgICAgIH07XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXkpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlXZWVrRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5KSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5TW9udGhEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLm9jY3VycmVuY2UgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2U7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZWN1ckVuZERhdGUgfHwganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5lbmREYXRlID1cbiAgICAgICAgICByZWN1ckVuZERhdGUgfHwganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBib2R5OiBDcmVhdGVFdmVudFR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBhdHRlbmRlZXM6IGpzb25Cb2R5Py5wYXJhbXM/LmF0dGVuZGVlcyxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgZHVyYXRpb24sXG4gICAgICBkZXNjcmlwdGlvbjoganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHwganNvbkJvZHk/LnBhcmFtcz8ubm90ZXMsXG4gICAgICBjb25mZXJlbmNlQXBwOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5jb25mZXJlbmNlPy5hcHAgfHxcbiAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uY29uZmVyZW5jZUFwcCxcbiAgICAgIHN0YXJ0RGF0ZToganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8IGV2ZW50U3RhcnREYXRlLFxuICAgICAgYnVmZmVyVGltZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYnVmZmVyVGltZSB8fCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5idWZmZXJUaW1lLFxuICAgICAgcmVtaW5kZXJzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHwgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucmVtaW5kZXJzIHx8IFtdLFxuICAgICAgcHJpb3JpdHk6IGpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8IDEsXG4gICAgICB0aW1lUHJlZmVyZW5jZXM6IGRhdGVKU09OQm9keT8udGltZVByZWZlcmVuY2VzIHx8IFtdLFxuICAgICAgbG9jYXRpb246IGpzb25Cb2R5Py5wYXJhbXM/LmxvY2F0aW9uLFxuICAgICAgdHJhbnNwYXJlbmN5OiBqc29uQm9keT8ucGFyYW1zPy50cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5OiBqc29uQm9keT8ucGFyYW1zLnZpc2liaWxpdHksXG4gICAgICBpc0JyZWFrOiBqc29uQm9keT8ucGFyYW1zPy5pc0JyZWFrLFxuICAgICAgYWxsRGF5OiBkYXRlSlNPTkJvZHk/LmFsbERheSxcbiAgICAgIGlzRm9sbG93VXA6IGpzb25Cb2R5Py5wYXJhbXM/LmlzRm9sbG93VXAsXG4gICAgfTtcblxuICAgIGlmIChcbiAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbiAgICApIHtcbiAgICAgIGJvZHkucmVjdXIgPSByZWN1ck9iamVjdCBhcyBhbnk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coYm9keSwgJyBib2R5Jyk7XG5cbiAgICBjb25zdCBuZXdBdHRlbmRlZXM6IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhIG9mIGJvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGAlJHthPy5uYW1lfSVgXG4gICAgICAgICk7XG4gICAgICAgIGlmIChjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWUpIHtcbiAgICAgICAgICBjb25zdCBwcmltYXJ5RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LmZpbmQoKGUpID0+ICEhZS5wcmltYXJ5KT8udmFsdWU7XG4gICAgICAgICAgY29uc3QgYW55RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWU7XG4gICAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goeyAuLi5hLCBlbWFpbDogcHJpbWFyeUVtYWlsIHx8IGFueUVtYWlsIH0pO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2goXG4gICAgICAgICAgICByZXF1aXJlZEZpZWxkcy5vcHRpb25hbD8uWzddPy5bJ2FuZCddPy5bMl1cbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBuZXdBdHRlbmRlZXMucHVzaChhKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBib2R5LmF0dGVuZGVlcyA9IG5ld0F0dGVuZGVlcztcblxuICAgIGlmICghYm9keT8udGl0bGUpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzBdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBib2R5O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcENyZWF0RXZlbnQoXG4gICAgICBib2R5LFxuICAgICAgdGltZXpvbmUsXG4gICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIGNyZWF0ZSBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0NyZWF0ZUV2ZW50TWlzc2luZ0ZpZWxkc1JldHVybmVkID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgZHVyYXRpb24gPSAwO1xuXG4gICAgY29uc3QgeWVhciA9XG4gICAgICBkYXRlSlNPTkJvZHk/LnllYXIgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnllYXI7XG4gICAgY29uc3QgbW9udGggPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5tb250aCB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ubW9udGg7XG4gICAgY29uc3QgZGF5ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZGF5IHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheSA9XG4gICAgICBkYXRlSlNPTkJvZHk/Lmlzb1dlZWtkYXkgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXIgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5ob3VyIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/Lm1pbnV0ZSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICAgIGRhdGVUaW1lOiB7IHJlcXVpcmVkOiBbXSB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ2NyZWF0ZUV2ZW50JyxcbiAgICB9O1xuXG4gICAgY29uc3QgZXZlbnRTdGFydERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhcixcbiAgICAgIG1vbnRoLFxuICAgICAgZGF5LFxuICAgICAgaXNvV2Vla2RheSxcbiAgICAgIGhvdXIsXG4gICAgICBtaW51dGUsXG4gICAgICBzdGFydFRpbWUsXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgY29uc3QgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyA9XG4gICAgICBhd2FpdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VHaXZlblVzZXJJZCh1c2VySWQpO1xuXG4gICAgaWYgKFxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbiB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1cmF0aW9uXG4gICAgKSB7XG4gICAgICBkdXJhdGlvbiA9XG4gICAgICAgIGRhdGVKU09OQm9keT8uZHVyYXRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoXG4gICAgICAoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnN0YXJ0VGltZSkgJiZcbiAgICAgIChkYXRlSlNPTkJvZHk/LmVuZFRpbWUgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmVuZFRpbWUpXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydFRpbWVPYmplY3QgPSBkYXlqcyhcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uc3RhcnRUaW1lLFxuICAgICAgICAnSEg6bW0nXG4gICAgICApO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBkYXRlSlNPTkJvZHkuZW5kVGltZSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZW5kVGltZSxcbiAgICAgICAgJ0hIOm1tJ1xuICAgICAgKTtcblxuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKFxuICAgICAgKGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSkgJiZcbiAgICAgIChqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSlcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0VGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZVxuICAgICAgKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZVxuICAgICAgKTtcbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICBkdXJhdGlvbiA9IDMwO1xuICAgIH1cblxuICAgIGxldCByZWN1ck9iamVjdDogUmVjdXJyZW5jZVJ1bGVUeXBlIHwge30gPSB7fTtcbiAgICBpZiAoXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5XG4gICAgKSB7XG4gICAgICBjb25zdCByZWN1ckVuZERhdGUgPSBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEoXG4gICAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhciB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhcixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGggfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1vbnRoLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5kYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91ciB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91cixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubWludXRlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uc3RhcnRUaW1lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlXG4gICAgICAgICAgICA/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGVcbiAgICAgICAgICAgID8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICAgKTtcblxuICAgICAgcmVjdXJPYmplY3QgPSB7XG4gICAgICAgIGZyZXF1ZW5jeTpcbiAgICAgICAgICAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlKSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5mcmVxdWVuY3kgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5mcmVxdWVuY3ksXG4gICAgICAgIGludGVydmFsOlxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCxcbiAgICAgIH07XG5cbiAgICAgIGlmIChcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5XG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlXZWVrRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5V2Vla0RheTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlNb250aERheVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5TW9udGhEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5TW9udGhEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/Lm9jY3VycmVuY2VcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5vY2N1cnJlbmNlID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlO1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIHJlY3VyRW5kRGF0ZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmVuZERhdGUgPVxuICAgICAgICAgIHJlY3VyRW5kRGF0ZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGU7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgbmV3Qm9keTogQ3JlYXRlRXZlbnRUeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgYXR0ZW5kZWVzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMsXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5ub3RlcyxcbiAgICAgIGNvbmZlcmVuY2VBcHA6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCB8fFxuICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5jb25mZXJlbmNlQXBwLFxuICAgICAgc3RhcnREYXRlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgZXZlbnRTdGFydERhdGUsXG4gICAgICBidWZmZXJUaW1lOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5idWZmZXJUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uYnVmZmVyVGltZSB8fFxuICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5idWZmZXJUaW1lLFxuICAgICAgcmVtaW5kZXJzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHxcbiAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucmVtaW5kZXJzIHx8XG4gICAgICAgIFtdLFxuICAgICAgcHJpb3JpdHk6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucHJpb3JpdHkgfHxcbiAgICAgICAgMSxcbiAgICAgIHRpbWVQcmVmZXJlbmNlczpcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py50aW1lUHJlZmVyZW5jZXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fFxuICAgICAgICBbXSxcbiAgICAgIGxvY2F0aW9uOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5sb2NhdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmxvY2F0aW9uLFxuICAgICAgdHJhbnNwYXJlbmN5OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50cmFuc3BhcmVuY3kgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zLnZpc2liaWxpdHkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy52aXNpYmlsaXR5LFxuICAgICAgaXNCcmVhazpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uaXNCcmVhayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmlzQnJlYWssXG4gICAgICBhbGxEYXk6XG4gICAgICAgIGRhdGVKU09OQm9keT8uYWxsRGF5IHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5hbGxEYXksXG4gICAgICBpc0ZvbGxvd1VwOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5pc0ZvbGxvd1VwIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uaXNGb2xsb3dVcCxcbiAgICB9O1xuXG4gICAgaWYgKFxuICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZVxuICAgICkge1xuICAgICAgbmV3Qm9keS5yZWN1ciA9IHJlY3VyT2JqZWN0IGFzIGFueTtcbiAgICB9XG5cbiAgICBjb25zdCBwcmV2Qm9keTogQ3JlYXRlRXZlbnRUeXBlID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZHVyYXRpb24pIHtcbiAgICAgIHByZXZCb2R5LmR1cmF0aW9uID0gbmV3Qm9keT8uZHVyYXRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZGVzY3JpcHRpb24pIHtcbiAgICAgIHByZXZCb2R5LmRlc2NyaXB0aW9uID0gbmV3Qm9keT8uZGVzY3JpcHRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uY29uZmVyZW5jZUFwcCkge1xuICAgICAgcHJldkJvZHkuY29uZmVyZW5jZUFwcCA9IG5ld0JvZHk/LmNvbmZlcmVuY2VBcHA7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uc3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS5zdGFydERhdGUgPSBuZXdCb2R5Py5zdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgcHJldkJvZHkuYnVmZmVyVGltZSA9IG5ld0JvZHk/LmJ1ZmZlclRpbWU7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnJlbWluZGVycyA9IG5ld0JvZHk/LnJlbWluZGVycyB8fCBbXTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5wcmlvcml0eSkge1xuICAgICAgcHJldkJvZHkucHJpb3JpdHkgPSBuZXdCb2R5Py5wcmlvcml0eTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkudGltZVByZWZlcmVuY2VzID0gbmV3Qm9keT8udGltZVByZWZlcmVuY2VzO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmxvY2F0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5sb2NhdGlvbiA9IG5ld0JvZHk/LmxvY2F0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgcHJldkJvZHkudHJhbnNwYXJlbmN5ID0gbmV3Qm9keT8udHJhbnNwYXJlbmN5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIHByZXZCb2R5LnZpc2liaWxpdHkgPSBuZXdCb2R5Py52aXNpYmlsaXR5O1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5pc0JyZWFrID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHByZXZCb2R5LmlzQnJlYWsgPSBuZXdCb2R5Py5pc0JyZWFrO1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5hbGxEYXkgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuYWxsRGF5ID0gbmV3Qm9keT8uYWxsRGF5O1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5pc0ZvbGxvd1VwID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHByZXZCb2R5LmlzRm9sbG93VXAgPSBuZXdCb2R5Py5pc0ZvbGxvd1VwO1xuICAgIH1cblxuICAgIGNvbnN0IG5ld0F0dGVuZGVlczogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGEgb2YgbmV3Qm9keT8uYXR0ZW5kZWVzKSB7XG4gICAgICBpZiAoIWE/LmVtYWlsKSB7XG4gICAgICAgIGNvbnN0IGNvbnRhY3QgPSBhd2FpdCBnZXRDb250YWN0QnlOYW1lV2l0aFVzZXJJZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgYCUke2E/Lm5hbWV9JWBcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZSkge1xuICAgICAgICAgIGNvbnN0IHByaW1hcnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uZmluZCgoZSkgPT4gISFlLnByaW1hcnkpPy52YWx1ZTtcbiAgICAgICAgICBjb25zdCBhbnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZTtcbiAgICAgICAgICBuZXdBdHRlbmRlZXMucHVzaCh7IC4uLmEsIGVtYWlsOiBwcmltYXJ5RW1haWwgfHwgYW55RW1haWwgfSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChcbiAgICAgICAgICAgIHJlcXVpcmVkRmllbGRzLm9wdGlvbmFsPy5bN10/LlsnYW5kJ10/LlsyXVxuICAgICAgICAgICk7XG4gICAgICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBuZXdBdHRlbmRlZXMucHVzaChhKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBuZXdCb2R5LmF0dGVuZGVlcyA9IG5ld0F0dGVuZGVlcztcblxuICAgIGlmICghKHByZXZCb2R5Py5hdHRlbmRlZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBwcmV2Qm9keS5hdHRlbmRlZXMgPSBuZXdCb2R5Py5hdHRlbmRlZXM7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ucmVjdXIpIHtcbiAgICAgIHByZXZCb2R5LnJlY3VyID0gbmV3Qm9keT8ucmVjdXI7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzBdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBDcmVhdEV2ZW50KFxuICAgICAgcHJldkJvZHksXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXMsXG4gICAgICByZXNwb25zZVxuICAgICk7XG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgY3JlYXRlIGV2ZW50IG1pc3NpbmcgZmllbGRzIHJldHVybmVkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVFdmVudENvbnRyb2xDZW50ZXIgPSBhc3luYyAoXG4gIG9wZW5haTogT3BlbkFJLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxuICB1c2VyQ3VycmVudFRpbWU6IHN0cmluZyxcbiAgcXVlcnk6ICdtaXNzaW5nX2ZpZWxkcycgfCAnY29tcGxldGVkJyB8ICdldmVudF9ub3RfZm91bmQnIHwgJ3BlbmRpbmcnXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZXNzYWdlTGVuZ3RoID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXM/Lmxlbmd0aDtcbiAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJztcbiAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgIHVzZXJNZXNzYWdlID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCB1c2VySW5wdXQgPSB1c2VyTWVzc2FnZTtcblxuICAgIGxldCBjcmVhdGVFdmVudFJlczogUmVzcG9uc2VBY3Rpb25UeXBlID0ge1xuICAgICAgcXVlcnk6ICdjb21wbGV0ZWQnLFxuICAgICAgZGF0YTogJycsXG4gICAgICBza2lsbDogJycsXG4gICAgICBwcmV2RGF0YToge30sXG4gICAgICBwcmV2RGF0YUV4dHJhOiB7fSxcbiAgICB9O1xuXG4gICAgc3dpdGNoIChxdWVyeSkge1xuICAgICAgY2FzZSAncGVuZGluZyc6XG4gICAgICAgIGNvbnN0IGpzb25Cb2R5ID0gYXdhaXQgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBjb25zdCBkYXRlVGltZSA9IGF3YWl0IGdlbmVyYXRlRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuICAgICAgICBjcmVhdGVFdmVudFJlcyA9IGF3YWl0IHByb2Nlc3NDcmVhdGVFdmVudFBlbmRpbmcoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25Cb2R5LFxuICAgICAgICAgIGRhdGVUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ21pc3NpbmdfZmllbGRzJzpcbiAgICAgICAgbGV0IHByaW9yVXNlcklucHV0ID0gJyc7XG4gICAgICAgIGxldCBwcmlvckFzc2lzdGFudE91dHB1dCA9ICcnO1xuXG4gICAgICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICdhc3Npc3RhbnQnKSB7XG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICAgICAgaWYgKG1lc3NhZ2UuY29udGVudCAhPT0gdXNlcklucHV0KSB7XG4gICAgICAgICAgICAgIHByaW9yVXNlcklucHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoIXByaW9yVXNlcklucHV0IHx8ICFwcmlvckFzc2lzdGFudE91dHB1dCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yVXNlcklucHV0LCAnIHByaW9yVXNlcklucHV0Jyk7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JBc3Npc3RhbnRPdXRwdXQsICcgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHByaW9yVXNlcmlucHV0IG9yIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgIH1cbiAgICAgICAgY29uc3QganNvbk1pc3NpbmdGaWVsZHNCb2R5ID1cbiAgICAgICAgICBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lID0gYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuXG4gICAgICAgIGNyZWF0ZUV2ZW50UmVzID0gYXdhaXQgcHJvY2Vzc0NyZWF0ZUV2ZW50TWlzc2luZ0ZpZWxkc1JldHVybmVkKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uTWlzc2luZ0ZpZWxkc0JvZHksXG4gICAgICAgICAgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICB9XG5cbiAgICBpZiAoY3JlYXRlRXZlbnRSZXM/LnF1ZXJ5ID09PSAnY29tcGxldGVkJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeShcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgY3JlYXRlRXZlbnRSZXMuZGF0YSBhcyBzdHJpbmcsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfSBlbHNlIGlmIChjcmVhdGVFdmVudFJlcz8ucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyhcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgY3JlYXRlRXZlbnRSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9XG4gICAgICAgIGNyZWF0ZUV2ZW50UmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhID0gY3JlYXRlRXZlbnRSZXM/LnByZXZEYXRhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGFFeHRyYSA9IGNyZWF0ZUV2ZW50UmVzPy5wcmV2RGF0YUV4dHJhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkpzb25Cb2R5ID0gY3JlYXRlRXZlbnRSZXM/LnByZXZKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPSBjcmVhdGVFdmVudFJlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICB9IGVsc2UgaWYgKGNyZWF0ZUV2ZW50UmVzPy5xdWVyeSA9PT0gJ2V2ZW50X25vdF9mb3VuZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2U6IEFzc2lzdGFudE1lc3NhZ2VUeXBlID0ge1xuICAgICAgICByb2xlOiAnYXNzaXN0YW50JyxcbiAgICAgICAgY29udGVudDogXCJPb3BzLi4uIEkgY291bGRuJ3QgZmluZCB0aGUgZXZlbnQuIFNvcnJ5IDooXCIsXG4gICAgICB9O1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9XG5cbiAgICByZXR1cm4gbWVzc2FnZUhpc3RvcnlPYmplY3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjcmVhdGUgZXZlbnQnKTtcbiAgfVxufTtcbiJdfQ==