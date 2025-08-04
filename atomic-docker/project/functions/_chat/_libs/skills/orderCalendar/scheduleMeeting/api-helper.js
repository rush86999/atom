import { createGoogleEvent, createPreAndPostEventsFromEvent, createZoomMeeting, extrapolateStartDateFromJSONData, findContactByEmailGivenUserId, getGlobalCalendar, getZoomAPIToken, upsertAttendeesforEvent, upsertConference, insertReminders, upsertEvents, getCalendarIntegrationByName, createRRuleString, convertEventTitleToOpenAIVector, putDataInTrainEventIndexInOpenSearch, listUserContactInfosGivenUserId, getUserContactInfosGivenIds, getContactByNameWithUserId, getUserGivenId, putDataInAllEventIndexInOpenSearch, generateDateTime, generateJSONDataFromUserInput, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, extrapolateDateFromJSONData, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, } from '@chat/_libs/api-helper';
import requiredFields from './requiredFields';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import getChatMeetingPreferenceByUserId from '@chat/_libs/gql/getChatMeetingPreferenceByUserId';
import { googleCalendarName, hasuraAdminSecret, hasuraGraphUrl, } from '@chat/_libs/constants';
import got from 'got';
import { v4 as uuid } from 'uuid';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
export const getChatMeetingPreferenceGivenUserId = async (userId) => {
    try {
        const operationName = 'GetChatMeetingPreferenceByUserId';
        const query = getChatMeetingPreferenceByUserId;
        const variables = {
            userId,
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
        console.log(res?.data?.Chat_Meeting_Preference, ' res inside getChatMeetingPreferenceGivenUserId');
        return res?.data?.Chat_Meeting_Preference?.[0];
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const finalStepScheduleMeeting = async (body, defaultMeetingPreferences, response) => {
    try {
        const aWithEmails = body?.attendees?.filter((a) => !!a?.email);
        const aWithContactInfos = await getUserContactInfosGivenIds(aWithEmails?.map((a) => a?.email));
        const primaryCalendar = await getGlobalCalendar(body?.userId);
        if (!primaryCalendar?.id) {
            throw new Error('no primary calendar found inside createAgenda');
        }
        const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
        if (!calIntegration?.clientType) {
            throw new Error('no client type inside calendar integration inside create agenda');
        }
        const eventId = uuid();
        const attendeesFromExtractedJSON = body?.attendees;
        const attendees = [];
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
        const remindersToUpdateEventId = [];
        if (body?.reminders?.length > 0) {
            const newReminders = body?.reminders.map((r) => ({
                id: uuid(),
                userId: body?.userId,
                eventId,
                timezone: body?.timezone,
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
                const zoomObject = await createZoomMeeting(zoomToken, body?.startDate, body?.timezone, body?.title, body?.duration, defaultMeetingPreferences?.name, defaultMeetingPreferences?.primaryEmail, body?.attendees?.map((a) => a?.email), body?.recur);
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
                startDate: dayjs(body?.startDate).tz(body?.timezone).format(),
                endDate: dayjs(body?.startDate)
                    .tz(body?.timezone)
                    .add(body?.duration, 'm')
                    .format(),
                allDay: false,
                notes: body?.description || body?.title,
                timezone: body?.timezone,
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
                : undefined, eventToUpsertLocal?.summary, eventToUpsertLocal?.notes, body?.timezone, undefined, undefined, undefined, eventToUpsertLocal?.guestsCanInviteOthers, eventToUpsertLocal?.guestsCanModify, eventToUpsertLocal?.guestsCanSeeOtherGuests, eventToUpsertLocal?.originalStartDate, undefined, recur, remindersToUpdateEventId?.length > 0 ? googleReminder : undefined, undefined, undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, undefined, undefined, undefined, undefined, undefined, eventToUpsertLocal?.attachments, 'default', body?.location, undefined);
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
                    const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, returnValues?.afterEvent?.id, returnValues?.afterEvent?.endDate, returnValues?.afterEvent?.startDate, 0, undefined, returnValues?.afterEvent?.sendUpdates, returnValues?.afterEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.afterEvent?.title, returnValues?.afterEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.afterEvent?.guestsCanInviteOthers, returnValues?.afterEvent?.guestsCanModify, returnValues?.afterEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.afterEvent?.transparency, returnValues?.afterEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                    returnValues.afterEvent.id = googleResValue.id;
                    returnValues.afterEvent.eventId = googleResValue.googleEventId;
                    returnValues.newEvent.postEventId = returnValues.afterEvent.id;
                }
                if (returnValues?.beforeEvent) {
                    const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, returnValues?.beforeEvent?.id, returnValues?.beforeEvent?.endDate, returnValues?.beforeEvent?.startDate, 0, undefined, returnValues?.beforeEvent?.sendUpdates, returnValues?.beforeEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.beforeEvent?.title, returnValues?.beforeEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.beforeEvent?.guestsCanInviteOthers, returnValues?.beforeEvent?.guestsCanModify, returnValues?.beforeEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.beforeEvent?.transparency, returnValues?.beforeEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
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
                startDate: dayjs(body?.startDate).tz(body?.timezone).format(),
                endDate: dayjs(body?.startDate)
                    .tz(body?.timezone)
                    .add(body?.duration, 'm')
                    .format(),
                allDay: false,
                notes: body?.description || body?.title,
                timezone: body?.timezone,
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
            const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, eventToUpsertLocal?.id, eventToUpsertLocal?.endDate, eventToUpsertLocal?.startDate, 0, undefined, eventToUpsertLocal?.sendUpdates, eventToUpsertLocal?.anyoneCanAddSelf, body?.attendees?.map((a) => ({ email: a?.email })), undefined, eventToUpsertLocal?.title, eventToUpsertLocal?.notes, body?.timezone, undefined, undefined, undefined, eventToUpsertLocal?.guestsCanInviteOthers, eventToUpsertLocal?.guestsCanModify, eventToUpsertLocal?.guestsCanSeeOtherGuests, eventToUpsertLocal?.originalStartDate, undefined, recur, remindersToUpdateEventId?.length > 0 ? googleReminder : undefined, undefined, undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, undefined, undefined, undefined, undefined, undefined, eventToUpsertLocal?.attachments, 'default', body?.location, undefined);
            eventToUpsertLocal.id = googleResValue.id;
            eventToUpsertLocal.eventId = googleResValue.googleEventId;
            if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
                const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime);
                if (returnValues?.afterEvent) {
                    const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, returnValues?.afterEvent?.id, returnValues?.afterEvent?.endDate, returnValues?.afterEvent?.startDate, 0, undefined, returnValues?.afterEvent?.sendUpdates, returnValues?.afterEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.afterEvent?.title, returnValues?.afterEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.afterEvent?.guestsCanInviteOthers, returnValues?.afterEvent?.guestsCanModify, returnValues?.afterEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.afterEvent?.transparency, returnValues?.afterEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                    returnValues.afterEvent.id = googleResValue.id;
                    returnValues.afterEvent.eventId = googleResValue.googleEventId;
                    returnValues.newEvent.postEventId = returnValues.afterEvent.id;
                }
                if (returnValues?.beforeEvent) {
                    const googleResValue = await createGoogleEvent(body?.userId, primaryCalendar?.id, calIntegration?.clientType, returnValues?.beforeEvent?.id, returnValues?.beforeEvent?.endDate, returnValues?.beforeEvent?.startDate, 0, undefined, returnValues?.beforeEvent?.sendUpdates, returnValues?.beforeEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.beforeEvent?.title, returnValues?.beforeEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.beforeEvent?.guestsCanInviteOthers, returnValues?.beforeEvent?.guestsCanModify, returnValues?.beforeEvent?.guestsCanSeeOtherGuests, undefined, undefined, undefined, undefined, undefined, undefined, returnValues?.beforeEvent?.transparency, returnValues?.beforeEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
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
        await putDataInAllEventIndexInOpenSearch(eventId, searchVector, body?.userId, body?.startDate, dayjs(body?.startDate)
            .tz(body?.timezone)
            .add(body?.duration, 'm')
            .format());
        response.query = 'completed';
        response.data = 'successfully scheduled meeting';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step schedule meeting');
    }
};
export const processScheduleMeetingPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
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
            skill: 'scheduleMeeting',
        };
        const meetingStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow);
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
        else if (jsonBody?.params?.startTime && jsonBody?.params?.endTime) {
            const startTimeObject = dayjs(jsonBody?.params?.startTime);
            const endTimeObject = dayjs(jsonBody?.params?.endTime);
            const minutes = endTimeObject.diff(startTimeObject, 'm');
            if (minutes > 0) {
                duration = minutes;
            }
        }
        else if (defaultMeetingPreferences?.duration) {
            duration = defaultMeetingPreferences?.duration;
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
            startDate: jsonBody?.params?.startTime || meetingStartDate,
            bufferTime: jsonBody?.params?.bufferTime || defaultMeetingPreferences?.bufferTime,
            reminders: jsonBody?.params?.alarms || defaultMeetingPreferences?.reminders || [],
            priority: jsonBody?.params?.priority || 1,
            timePreferences: dateJSONBody?.timePreferences || [],
            location: jsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params.visibility,
        };
        if (recurObject?.frequency) {
            body.recur = recurObject;
        }
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
                    missingFields.required.push(requiredFields.required?.[1]?.['and']?.[2]);
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
        if (!(body?.attendees?.length > 0)) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]);
            response.data = missingFields;
            response.prevData = body;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        const userContactInfos = await listUserContactInfosGivenUserId(userId);
        const providedHostInfo = body?.attendees?.find((a) => a?.isHost === true);
        const primaryInfoItem = userContactInfos?.find((u) => u.primary && u.type === 'email');
        const user = await getUserGivenId(userId);
        const primaryHostAttendeeInfo = {
            name: primaryInfoItem?.name || user?.name,
            email: primaryInfoItem?.id || user?.email,
            isHost: true,
        };
        if (!providedHostInfo && primaryHostAttendeeInfo?.email) {
            body?.attendees.push(primaryHostAttendeeInfo);
        }
        const hostInfo = providedHostInfo || primaryHostAttendeeInfo;
        if (!hostInfo?.email) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]['and'][1]);
            response.data = missingFields;
            response.prevData = body;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepScheduleMeeting(body, defaultMeetingPreferences, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process schedule meeting');
    }
};
export const processScheduleMeetingMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
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
            skill: 'scheduleMeeting',
        };
        const meetingStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow ||
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
                meetingStartDate,
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
        };
        if (recurObject?.frequency) {
            newBody.recur = recurObject;
        }
        const prevBody = {
            ...messageHistoryObject?.prevData,
        };
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
                    missingFields.required.push(requiredFields.required?.[1]?.['and']?.[2]);
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
        if (!prevBody?.userId) {
            prevBody.userId = userId || newBody?.userId;
        }
        if (!prevBody?.timezone) {
            prevBody.timezone = timezone || newBody?.timezone;
        }
        if (!prevBody?.title) {
            prevBody.title = newBody?.title;
        }
        if (!(prevBody?.attendees?.length > 0)) {
            prevBody.attendees = newBody?.attendees;
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
        // if (!prevBody?.startDate) {
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
        if (!(prevBody?.attendees?.length > 0)) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        const userContactInfos = await listUserContactInfosGivenUserId(userId);
        const newProvidedHostInfo = newBody?.attendees?.find((a) => a?.isHost === true);
        const prevProvidedHostInfo = prevBody?.attendees?.find((a) => a?.isHost === true);
        const primaryInfoItem = userContactInfos?.find((u) => u.primary && u.type === 'email');
        const user = await getUserGivenId(userId);
        const primaryHostAttendeeInfo = {
            name: primaryInfoItem?.name || user?.name,
            email: primaryInfoItem?.id || user?.email,
            isHost: true,
        };
        if (!newProvidedHostInfo && primaryHostAttendeeInfo?.email) {
            newBody?.attendees.push(primaryHostAttendeeInfo);
        }
        if (!prevProvidedHostInfo && primaryHostAttendeeInfo?.email) {
            prevBody?.attendees.push(primaryHostAttendeeInfo);
        }
        const prevHostInfo = prevProvidedHostInfo || newProvidedHostInfo || primaryHostAttendeeInfo;
        if (!prevHostInfo?.email) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[1]['and'][1]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!prevBody?.recur) {
            prevBody.recur = newBody?.recur;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepScheduleMeeting(prevBody, defaultMeetingPreferences, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process schedule meeting missing fields returned');
    }
};
export const scheduleMeetingControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let scheduleMeetingRes = {
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
                scheduleMeetingRes = await processScheduleMeetingPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                scheduleMeetingRes = await processScheduleMeetingMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (scheduleMeetingRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, scheduleMeetingRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (scheduleMeetingRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, scheduleMeetingRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required =
                scheduleMeetingRes?.data;
            messageHistoryObject.prevData = scheduleMeetingRes?.prevData;
            messageHistoryObject.prevDataExtra = scheduleMeetingRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody =
                scheduleMeetingRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = scheduleMeetingRes?.prevJsonBody;
        }
        else if (scheduleMeetingRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to schedule meeting control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLGlCQUFpQixFQUNqQiwrQkFBK0IsRUFDL0IsaUJBQWlCLEVBQ2pCLGdDQUFnQyxFQUNoQyw2QkFBNkIsRUFDN0IsaUJBQWlCLEVBQ2pCLGVBQWUsRUFDZix1QkFBdUIsRUFDdkIsZ0JBQWdCLEVBQ2hCLGVBQWUsRUFDZixZQUFZLEVBQ1osNEJBQTRCLEVBQzVCLGlCQUFpQixFQUNqQiwrQkFBK0IsRUFDL0Isb0NBQW9DLEVBQ3BDLCtCQUErQixFQUMvQiwyQkFBMkIsRUFDM0IsMEJBQTBCLEVBQzFCLGNBQWMsRUFDZCxrQ0FBa0MsRUFDbEMsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3QixtREFBbUQsRUFDbkQscURBQXFELEVBQ3JELDJCQUEyQixFQUMzQiw2QkFBNkIsRUFDN0IsMENBQTBDLEdBQzNDLE1BQU0sd0JBQXdCLENBQUM7QUFNaEMsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUFFLEtBQUssRUFBRSxNQUFNLGlDQUFpQyxDQUFDO0FBUXhELE9BQU8sZ0NBQWdDLE1BQU0sa0RBQWtELENBQUM7QUFFaEcsT0FBTyxFQUNMLGtCQUFrQixFQUNsQixpQkFBaUIsRUFDakIsY0FBYyxHQUNmLE1BQU0sdUJBQXVCLENBQUM7QUFDL0IsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBRXRCLE9BQU8sRUFBRSxFQUFFLElBQUksSUFBSSxFQUFFLE1BQU0sTUFBTSxDQUFDO0FBT2xDLE9BQU8sRUFBRSxhQUFhLEVBQUUsTUFBTSx1Q0FBdUMsQ0FBQztBQUN0RSxPQUFPLEVBQUUsaUNBQWlDLEVBQUUsTUFBTSx3Q0FBd0MsQ0FBQztBQVMzRixNQUFNLENBQUMsTUFBTSxtQ0FBbUMsR0FBRyxLQUFLLEVBQUUsTUFBYyxFQUFFLEVBQUU7SUFDMUUsSUFBSSxDQUFDO1FB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QkFBb0IsQ0FDckIsQ0FBQztZQUVKLG9CQUFvQixDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztZQUNyRCxvQkFBb0IsQ0FBQyxLQUFLLEdBQUcsZ0JBQWdCLENBQUM7WUFDOUMsb0JBQW9CLENBQUMsUUFBUTtnQkFDM0Isa0JBQWtCLEVBQUUsSUFBMEIsQ0FBQztZQUNqRCxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsa0JBQWtCLEVBQUUsUUFBUSxDQUFDO1lBQzdELG9CQUFvQixDQUFDLGFBQWEsR0FBRyxrQkFBa0IsRUFBRSxhQUFhLENBQUM7WUFDdkUsb0JBQW9CLENBQUMsZ0JBQWdCO2dCQUNuQyxrQkFBa0IsRUFBRSxnQkFBZ0IsQ0FBQztZQUN2QyxvQkFBb0IsQ0FBQyxZQUFZLEdBQUcsa0JBQWtCLEVBQUUsWUFBWSxDQUFDO1FBQ3ZFLENBQUM7YUFBTSxJQUFJLGtCQUFrQixFQUFFLEtBQUssS0FBSyxpQkFBaUIsRUFBRSxDQUFDO1lBQzNELE1BQU0sZ0JBQWdCLEdBQXlCO2dCQUM3QyxJQUFJLEVBQUUsV0FBVztnQkFDakIsT0FBTyxFQUFFLDZDQUE2QzthQUN2RCxDQUFDO1lBRUYsb0JBQW9CLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQ3JELG9CQUFvQixDQUFDLEtBQUssR0FBRyxpQkFBaUIsQ0FBQztZQUMvQyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO1FBQ3ZDLENBQUM7UUFFRCxPQUFPLG9CQUFvQixDQUFDO0lBQzlCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsb0RBQW9ELENBQUMsQ0FBQztJQUN2RSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgY3JlYXRlR29vZ2xlRXZlbnQsXG4gIGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGcm9tRXZlbnQsXG4gIGNyZWF0ZVpvb21NZWV0aW5nLFxuICBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YSxcbiAgZmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWQsXG4gIGdldEdsb2JhbENhbGVuZGFyLFxuICBnZXRab29tQVBJVG9rZW4sXG4gIHVwc2VydEF0dGVuZGVlc2ZvckV2ZW50LFxuICB1cHNlcnRDb25mZXJlbmNlLFxuICBpbnNlcnRSZW1pbmRlcnMsXG4gIHVwc2VydEV2ZW50cyxcbiAgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZSxcbiAgY3JlYXRlUlJ1bGVTdHJpbmcsXG4gIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IsXG4gIHB1dERhdGFJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaCxcbiAgbGlzdFVzZXJDb250YWN0SW5mb3NHaXZlblVzZXJJZCxcbiAgZ2V0VXNlckNvbnRhY3RJbmZvc0dpdmVuSWRzLFxuICBnZXRDb250YWN0QnlOYW1lV2l0aFVzZXJJZCxcbiAgZ2V0VXNlckdpdmVuSWQsXG4gIHB1dERhdGFJbkFsbEV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsXG4gIGdlbmVyYXRlRGF0ZVRpbWUsXG4gIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnksXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzLFxuICBleHRyYXBvbGF0ZURhdGVGcm9tSlNPTkRhdGEsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lLFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQsXG59IGZyb20gJ0BjaGF0L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IERhdGVUaW1lSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvRGF0ZVRpbWVKU09OSlNPTlR5cGUnO1xuaW1wb3J0IFVzZXJJbnB1dFRvSlNPTlR5cGUsIHtcbiAgTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVXNlcklucHV0VG9KU09OVHlwZSc7XG5pbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5pbXBvcnQgcmVxdWlyZWRGaWVsZHMgZnJvbSAnLi9yZXF1aXJlZEZpZWxkcyc7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuXG5pbXBvcnQge1xuICBFdmVudFR5cGUsXG4gIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlLFxuICBSZWN1cnJlbmNlUnVsZVR5cGUsXG4gIFZpc2liaWxpdHlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUJ5VXNlcklkIGZyb20gJ0BjaGF0L19saWJzL2dxbC9nZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VCeVVzZXJJZCc7XG5pbXBvcnQgeyBDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0NoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlJztcbmltcG9ydCB7XG4gIGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgaGFzdXJhQWRtaW5TZWNyZXQsXG4gIGhhc3VyYUdyYXBoVXJsLFxufSBmcm9tICdAY2hhdC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IHsgU2NoZWR1bGVNZWV0aW5nVHlwZSB9IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IHsgUmVtaW5kZXJUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVtaW5kZXJUeXBlJztcbmltcG9ydCB7IEdvb2dsZVJlbWluZGVyVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0dvb2dsZVJlbWluZGVyVHlwZSc7XG5pbXBvcnQgeyBDb25mZXJlbmNlVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0NvbmZlcmVuY2VUeXBlJztcbmltcG9ydCB7IEdvb2dsZVJlc1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Hb29nbGVSZXNUeXBlJztcbmltcG9ydCBSZXNwb25zZUFjdGlvblR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVzcG9uc2VBY3Rpb25UeXBlJztcbmltcG9ydCBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1ByZWZlcnJlZFRpbWVSYW5nZVR5cGUnO1xuaW1wb3J0IHsgRGF5T2ZXZWVrRW51bSB9IGZyb20gJy4uL3Jlc29sdmVDb25mbGljdGluZ0V2ZW50cy9jb25zdGFudHMnO1xuaW1wb3J0IHsgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50IH0gZnJvbSAnLi4vcmVzb2x2ZUNvbmZsaWN0aW5nRXZlbnRzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgQXR0ZW5kZWVUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQXR0ZW5kZWVUeXBlJztcbmltcG9ydCB7XG4gIEFzc2lzdGFudE1lc3NhZ2VUeXBlLFxuICBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvTWVzc2FnaW5nL01lc3NhZ2luZ1R5cGVzJztcbmltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCByZWxhdGl2ZVRpbWUgZnJvbSAnZGF5anMvcGx1Z2luL3JlbGF0aXZlVGltZSc7XG5cbmV4cG9ydCBjb25zdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VHaXZlblVzZXJJZCA9IGFzeW5jICh1c2VySWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlQnlVc2VySWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlQnlVc2VySWQ7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHsgQ2hhdF9NZWV0aW5nX1ByZWZlcmVuY2U6IENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlW10gfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzPy5kYXRhPy5DaGF0X01lZXRpbmdfUHJlZmVyZW5jZSxcbiAgICAgICcgcmVzIGluc2lkZSBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VHaXZlblVzZXJJZCdcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uQ2hhdF9NZWV0aW5nX1ByZWZlcmVuY2U/LlswXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBFbWFpbF9Lbm93bGVkZ2ViYXNlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBmaW5hbFN0ZXBTY2hlZHVsZU1lZXRpbmcgPSBhc3luYyAoXG4gIGJvZHk6IFNjaGVkdWxlTWVldGluZ1R5cGUsXG4gIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM6IENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlLFxuICByZXNwb25zZTogYW55XG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBhV2l0aEVtYWlscyA9IGJvZHk/LmF0dGVuZGVlcz8uZmlsdGVyKChhKSA9PiAhIWE/LmVtYWlsKTtcblxuICAgIGNvbnN0IGFXaXRoQ29udGFjdEluZm9zID0gYXdhaXQgZ2V0VXNlckNvbnRhY3RJbmZvc0dpdmVuSWRzKFxuICAgICAgYVdpdGhFbWFpbHM/Lm1hcCgoYSkgPT4gYT8uZW1haWwpXG4gICAgKTtcblxuICAgIGNvbnN0IHByaW1hcnlDYWxlbmRhciA9IGF3YWl0IGdldEdsb2JhbENhbGVuZGFyKGJvZHk/LnVzZXJJZCk7XG5cbiAgICBpZiAoIXByaW1hcnlDYWxlbmRhcj8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpbWFyeSBjYWxlbmRhciBmb3VuZCBpbnNpZGUgY3JlYXRlQWdlbmRhJyk7XG4gICAgfVxuXG4gICAgY29uc3QgY2FsSW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgZ29vZ2xlQ2FsZW5kYXJOYW1lXG4gICAgKTtcblxuICAgIGlmICghY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ25vIGNsaWVudCB0eXBlIGluc2lkZSBjYWxlbmRhciBpbnRlZ3JhdGlvbiBpbnNpZGUgY3JlYXRlIGFnZW5kYSdcbiAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgZXZlbnRJZCA9IHV1aWQoKTtcblxuICAgIGNvbnN0IGF0dGVuZGVlc0Zyb21FeHRyYWN0ZWRKU09OID0gYm9keT8uYXR0ZW5kZWVzO1xuICAgIGNvbnN0IGF0dGVuZGVlczogQXR0ZW5kZWVUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgYSBvZiBhdHRlbmRlZXNGcm9tRXh0cmFjdGVkSlNPTikge1xuICAgICAgY29uc3QgY29udGFjdCA9IGF3YWl0IGZpbmRDb250YWN0QnlFbWFpbEdpdmVuVXNlcklkKFxuICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgIGEuZW1haWxcbiAgICAgICk7XG4gICAgICBjb25zdCB1c2VySWRGb3VuZCA9IGFXaXRoQ29udGFjdEluZm9zPy5maW5kKChiKSA9PiBiPy5pZCA9PT0gYT8uZW1haWwpO1xuXG4gICAgICBjb25zdCBhdHRlbmRlZTogQXR0ZW5kZWVUeXBlID0ge1xuICAgICAgICBpZDogdXNlcklkRm91bmQ/LnVzZXJJZCB8fCB1dWlkKCksXG4gICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICBuYW1lOlxuICAgICAgICAgIGE/Lm5hbWUgfHxcbiAgICAgICAgICBjb250YWN0Py5uYW1lIHx8XG4gICAgICAgICAgYCR7Y29udGFjdD8uZmlyc3ROYW1lfSAke2NvbnRhY3Q/Lmxhc3ROYW1lfWAsXG4gICAgICAgIGNvbnRhY3RJZDogY29udGFjdD8uaWQsXG4gICAgICAgIGVtYWlsczogW3sgcHJpbWFyeTogdHJ1ZSwgdmFsdWU6IGE/LmVtYWlsIH1dLFxuICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgZXZlbnRJZCxcbiAgICAgIH07XG5cbiAgICAgIGF0dGVuZGVlcy5wdXNoKGF0dGVuZGVlKTtcbiAgICB9XG5cbiAgICBjb25zdCByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ6IFJlbWluZGVyVHlwZVtdID0gW107XG5cbiAgICBpZiAoYm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBuZXdSZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdID0gYm9keT8ucmVtaW5kZXJzLm1hcCgocikgPT4gKHtcbiAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICAgIHRpbWV6b25lOiBib2R5Py50aW1lem9uZSxcbiAgICAgICAgbWludXRlczogcixcbiAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgfSkpO1xuXG4gICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQucHVzaCguLi5uZXdSZW1pbmRlcnMpO1xuICAgIH1cblxuICAgIGNvbnN0IGdvb2dsZVJlbWluZGVyOiBHb29nbGVSZW1pbmRlclR5cGUgPSB7XG4gICAgICBvdmVycmlkZXM6IHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubWFwKChyKSA9PiAoe1xuICAgICAgICBtZXRob2Q6ICdlbWFpbCcsXG4gICAgICAgIG1pbnV0ZXM6IHI/Lm1pbnV0ZXMsXG4gICAgICB9KSksXG4gICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICB9O1xuXG4gICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlczogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IHRpbWVwcmVmZXJlbmNlIG9mIGJvZHk/LnRpbWVQcmVmZXJlbmNlcykge1xuICAgICAgaWYgKHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBmb3IgKGNvbnN0IGRheU9mV2VlayBvZiB0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWspIHtcbiAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICAgIGRheU9mV2VlazogRGF5T2ZXZWVrRW51bVtkYXlPZldlZWtdLFxuICAgICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICB9O1xuXG4gICAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgIH07XG5cbiAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgcmVjdXIgPSBjcmVhdGVSUnVsZVN0cmluZyhcbiAgICAgIGJvZHk/LnJlY3VyPy5mcmVxdWVuY3ksXG4gICAgICBib2R5Py5yZWN1cj8uaW50ZXJ2YWwsXG4gICAgICBib2R5Py5yZWN1cj8uYnlXZWVrRGF5LFxuICAgICAgYm9keT8ucmVjdXI/Lm9jY3VycmVuY2UsXG4gICAgICBib2R5Py5yZWN1cj8uZW5kRGF0ZSxcbiAgICAgIGJvZHk/LnJlY3VyPy5CeU1vbnRoRGF5XG4gICAgKTtcblxuICAgIGxldCBjb25mZXJlbmNlOiBDb25mZXJlbmNlVHlwZSB8IHt9ID0ge307XG5cbiAgICBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCkge1xuICAgICAgY29uc3Qgem9vbVRva2VuID0gYXdhaXQgZ2V0Wm9vbUFQSVRva2VuKGJvZHk/LnVzZXJJZCk7XG4gICAgICBjb25mZXJlbmNlID1cbiAgICAgICAgem9vbVRva2VuICYmIGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJ1xuICAgICAgICAgID8ge31cbiAgICAgICAgICA6IHtcbiAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgICAgIGNhbGVuZGFySWQ6IHByaW1hcnlDYWxlbmRhcj8uaWQsXG4gICAgICAgICAgICAgIGFwcDogJ2dvb2dsZScsXG4gICAgICAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgICAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAgICAgICAgICAgcmVxdWVzdElkOiB1dWlkKCksXG4gICAgICAgICAgICB9O1xuXG4gICAgICBpZiAoem9vbVRva2VuICYmIGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJykge1xuICAgICAgICBjb25zb2xlLmxvZyh6b29tVG9rZW4sICcgem9vbVRva2VuIGluc2lkZSBpZiAoem9vbVRva2VuKScpO1xuXG4gICAgICAgIGNvbnN0IHpvb21PYmplY3QgPSBhd2FpdCBjcmVhdGVab29tTWVldGluZyhcbiAgICAgICAgICB6b29tVG9rZW4sXG4gICAgICAgICAgYm9keT8uc3RhcnREYXRlLFxuICAgICAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgIGJvZHk/LnRpdGxlLFxuICAgICAgICAgIGJvZHk/LmR1cmF0aW9uLFxuICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucHJpbWFyeUVtYWlsLFxuICAgICAgICAgIGJvZHk/LmF0dGVuZGVlcz8ubWFwKChhKSA9PiBhPy5lbWFpbCksXG4gICAgICAgICAgYm9keT8ucmVjdXIgYXMgYW55XG4gICAgICAgICk7XG5cbiAgICAgICAgY29uc29sZS5sb2coem9vbU9iamVjdCwgJyB6b29tT2JqZWN0IGFmdGVyIGNyZWF0ZVpvb21NZWV0aW5nJyk7XG5cbiAgICAgICAgaWYgKHpvb21PYmplY3QpIHtcbiAgICAgICAgICBjb25mZXJlbmNlID0ge1xuICAgICAgICAgICAgaWQ6IGAke3pvb21PYmplY3Q/LmlkfWAsXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgIGNhbGVuZGFySWQ6IHByaW1hcnlDYWxlbmRhcj8uaWQsXG4gICAgICAgICAgICBhcHA6ICd6b29tJyxcbiAgICAgICAgICAgIG5hbWU6IHpvb21PYmplY3Q/LmFnZW5kYSxcbiAgICAgICAgICAgIG5vdGVzOiB6b29tT2JqZWN0Py5hZ2VuZGEsXG4gICAgICAgICAgICBqb2luVXJsOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAgICAgICAgIHN0YXJ0VXJsOiB6b29tT2JqZWN0Py5zdGFydF91cmwsXG4gICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgZW50cnlQb2ludHM6IFtcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGVudHJ5UG9pbnRUeXBlOiAndmlkZW8nLFxuICAgICAgICAgICAgICAgIGxhYmVsOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAgICAgICAgICAgICBwYXNzd29yZDogem9vbU9iamVjdD8ucGFzc3dvcmQsXG4gICAgICAgICAgICAgICAgdXJpOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgfSBhcyBDb25mZXJlbmNlVHlwZTtcbiAgICAgICAgfVxuICAgICAgfVxuXG4gICAgICBjb25zdCBldmVudFRvVXBzZXJ0TG9jYWw6IEV2ZW50VHlwZSA9IHtcbiAgICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICB0aXRsZTogYm9keT8udGl0bGUsXG4gICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoYm9keT8uc3RhcnREYXRlKS50eihib2R5Py50aW1lem9uZSkuZm9ybWF0KCksXG4gICAgICAgIGVuZERhdGU6IGRheWpzKGJvZHk/LnN0YXJ0RGF0ZSlcbiAgICAgICAgICAudHooYm9keT8udGltZXpvbmUpXG4gICAgICAgICAgLmFkZChib2R5Py5kdXJhdGlvbiwgJ20nKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgYWxsRGF5OiBmYWxzZSxcbiAgICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlLFxuICAgICAgICB0aW1lem9uZTogYm9keT8udGltZXpvbmUsXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgcHJpb3JpdHk6IGJvZHk/LnByaW9yaXR5IHx8IDEsXG4gICAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgICBtb2RpZmlhYmxlOiBib2R5Py5wcmlvcml0eSA+IDEgfHwgbmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCxcbiAgICAgICAgYW55b25lQ2FuQWRkU2VsZjogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOlxuICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICB0cmFuc3BhcmVuY3k6XG4gICAgICAgICAgYm9keT8udHJhbnNwYXJlbmN5IHx8IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgdmlzaWJpbGl0eTpcbiAgICAgICAgICAoYm9keT8udmlzaWJpbGl0eSBhcyBWaXNpYmlsaXR5VHlwZSkgfHxcbiAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy52aXNpYmlsaXR5LFxuICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICAgIHN1bW1hcnk6IGJvZHk/LnRpdGxlLFxuICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgIGNhbGVuZGFySWQ6IHByaW1hcnlDYWxlbmRhcj8uaWQsXG4gICAgICAgIGV2ZW50SWQ6IHVuZGVmaW5lZCxcbiAgICAgICAgY29uZmVyZW5jZUlkOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkLFxuICAgICAgICBzZW5kVXBkYXRlczogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uc2VuZFVwZGF0ZXMsXG4gICAgICAgIGR1cmF0aW9uOiBib2R5Py5kdXJhdGlvbixcbiAgICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5OiB0cnVlLFxuICAgICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmc6IGJvZHk/LmJ1ZmZlclRpbWUgPyB0cnVlIDogZmFsc2UsXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlOlxuICAgICAgICAgIGJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCA/IHRydWUgOiBmYWxzZSxcbiAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzOiBib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDAgPyB0cnVlIDogZmFsc2UsXG4gICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWw6XG4gICAgICAgICAgYm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvbjogdHJ1ZSxcbiAgICAgICAgbG9jYXRpb246IHsgdGl0bGU6IGJvZHk/LmxvY2F0aW9uIH0sXG4gICAgICAgIHJlY3VycmVuY2U6IHJlY3VyLFxuICAgICAgICByZWN1cnJlbmNlUnVsZToge1xuICAgICAgICAgIGZyZXF1ZW5jeTogYm9keT8ucmVjdXI/LmZyZXF1ZW5jeSxcbiAgICAgICAgICBpbnRlcnZhbDogYm9keT8ucmVjdXI/LmludGVydmFsLFxuICAgICAgICAgIGJ5V2Vla0RheTogYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAgICAgICBvY2N1cnJlbmNlOiBib2R5Py5yZWN1cj8ub2NjdXJyZW5jZSxcbiAgICAgICAgICBlbmREYXRlOiBib2R5Py5yZWN1cj8uZW5kRGF0ZSxcbiAgICAgICAgICBieU1vbnRoRGF5OiBib2R5Py5yZWN1cj8uQnlNb250aERheSxcbiAgICAgICAgfSxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zdGFydERhdGUsXG4gICAgICAgIChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uaWQgPyAxIDogMCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnNlbmRVcGRhdGVzLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgIGJvZHk/LmF0dGVuZGVlcz8ubWFwKChhKSA9PiAoeyBlbWFpbDogYT8uZW1haWwgfSkpLFxuICAgICAgICAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkXG4gICAgICAgICAgPyB7XG4gICAgICAgICAgICAgIHR5cGU6XG4gICAgICAgICAgICAgICAgKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5hcHAgPT09ICd6b29tJ1xuICAgICAgICAgICAgICAgICAgPyAnYWRkT24nXG4gICAgICAgICAgICAgICAgICA6ICdoYW5nb3V0c01lZXQnLFxuICAgICAgICAgICAgICBuYW1lOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/Lm5hbWUsXG4gICAgICAgICAgICAgIGNvbmZlcmVuY2VJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZCxcbiAgICAgICAgICAgICAgZW50cnlQb2ludHM6IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uZW50cnlQb2ludHMsXG4gICAgICAgICAgICAgIGNyZWF0ZVJlcXVlc3Q6XG4gICAgICAgICAgICAgICAgKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5hcHAgPT09ICdnb29nbGUnXG4gICAgICAgICAgICAgICAgICA/IHtcbiAgICAgICAgICAgICAgICAgICAgICByZXF1ZXN0SWQ6IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8ucmVxdWVzdElkLFxuICAgICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbktleToge1xuICAgICAgICAgICAgICAgICAgICAgICAgdHlwZTogJ2hhbmdvdXRzTWVldCcsXG4gICAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgICAgICAgICB9XG4gICAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3VtbWFyeSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ub3RlcyxcbiAgICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICByZWN1cixcbiAgICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwID8gZ29vZ2xlUmVtaW5kZXIgOiB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy52aXNpYmlsaXR5LFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5hdHRhY2htZW50cyxcbiAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICBib2R5Py5sb2NhdGlvbixcbiAgICAgICAgdW5kZWZpbmVkXG4gICAgICApO1xuXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcblxuICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5mb3JFYWNoKChyKSA9PiAoe1xuICAgICAgICAuLi5yLFxuICAgICAgICBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWwuaWQsXG4gICAgICB9KSk7XG5cbiAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/LmZvckVhY2goKHApID0+ICh7XG4gICAgICAgIC4uLnAsXG4gICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbC5pZCxcbiAgICAgIH0pKTtcblxuICAgICAgYXR0ZW5kZWVzPy5mb3JFYWNoKChhKSA9PiAoeyAuLi5hLCBldmVudElkOiBldmVudFRvVXBzZXJ0TG9jYWw/LmlkIH0pKTtcblxuICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKTtcblxuICAgICAgaWYgKGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQgfHwgYm9keT8uYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgY29uc3QgcmV0dXJuVmFsdWVzID0gY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21FdmVudChcbiAgICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWwsXG4gICAgICAgICAgYm9keT8uYnVmZmVyVGltZVxuICAgICAgICApO1xuXG4gICAgICAgIGlmIChyZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQpIHtcbiAgICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgICAgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5pZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZW5kRGF0ZSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgICAgMCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRpdGxlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZFxuICAgICAgICAgICk7XG5cbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuICAgICAgICAgIHJldHVyblZhbHVlcy5uZXdFdmVudC5wb3N0RXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQpIHtcbiAgICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgICAgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uaWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgICAgMCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRpdGxlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8ubm90ZXMsXG4gICAgICAgICAgICBib2R5Py50aW1lem9uZSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udmlzaWJpbGl0eSxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZFxuICAgICAgICAgICk7XG5cbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnByZUV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZDtcbiAgICAgICAgfVxuXG4gICAgICAgIGF3YWl0IHVwc2VydEV2ZW50cyhcbiAgICAgICAgICBbXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50LFxuICAgICAgICAgIF0/LmZpbHRlcigoZSkgPT4gISFlKVxuICAgICAgICApO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFtldmVudFRvVXBzZXJ0TG9jYWxdKTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCkge1xuICAgICAgICBhd2FpdCBpbnNlcnRSZW1pbmRlcnMocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkKTtcbiAgICAgIH1cblxuICAgICAgaWYgKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgYXdhaXQgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMpO1xuICAgICAgfVxuXG4gICAgICBhd2FpdCB1cHNlcnRBdHRlbmRlZXNmb3JFdmVudChhdHRlbmRlZXMpO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBldmVudFRvVXBzZXJ0TG9jYWw6IEV2ZW50VHlwZSA9IHtcbiAgICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICB0aXRsZTogYm9keT8udGl0bGUsXG4gICAgICAgIHN0YXJ0RGF0ZTogZGF5anMoYm9keT8uc3RhcnREYXRlKS50eihib2R5Py50aW1lem9uZSkuZm9ybWF0KCksXG4gICAgICAgIGVuZERhdGU6IGRheWpzKGJvZHk/LnN0YXJ0RGF0ZSlcbiAgICAgICAgICAudHooYm9keT8udGltZXpvbmUpXG4gICAgICAgICAgLmFkZChib2R5Py5kdXJhdGlvbiwgJ20nKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgYWxsRGF5OiBmYWxzZSxcbiAgICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlLFxuICAgICAgICB0aW1lem9uZTogYm9keT8udGltZXpvbmUsXG4gICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgcHJpb3JpdHk6IGJvZHk/LnByaW9yaXR5IHx8IDEsXG4gICAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgICBtb2RpZmlhYmxlOiBib2R5Py5wcmlvcml0eSA+IDEgfHwgbmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCxcbiAgICAgICAgYW55b25lQ2FuQWRkU2VsZjogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOlxuICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICB0cmFuc3BhcmVuY3k6XG4gICAgICAgICAgYm9keT8udHJhbnNwYXJlbmN5IHx8IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgdmlzaWJpbGl0eTpcbiAgICAgICAgICAoYm9keT8udmlzaWJpbGl0eSBhcyBWaXNpYmlsaXR5VHlwZSkgfHxcbiAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy52aXNpYmlsaXR5LFxuICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZTogdW5kZWZpbmVkLFxuICAgICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICAgIHN1bW1hcnk6IGJvZHk/LnRpdGxlLFxuICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgIGNhbGVuZGFySWQ6IHByaW1hcnlDYWxlbmRhcj8uaWQsXG4gICAgICAgIGV2ZW50SWQ6IHVuZGVmaW5lZCxcbiAgICAgICAgc2VuZFVwZGF0ZXM6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnNlbmRVcGRhdGVzLFxuICAgICAgICBkdXJhdGlvbjogYm9keT8uZHVyYXRpb24sXG4gICAgICAgIHRpbWVCbG9ja2luZzogYm9keT8uYnVmZmVyVGltZSxcbiAgICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5OiB0cnVlLFxuICAgICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmc6IGJvZHk/LmJ1ZmZlclRpbWUgPyB0cnVlIDogZmFsc2UsXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlOlxuICAgICAgICAgIGJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCA/IHRydWUgOiBmYWxzZSxcbiAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzOiBib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDAgPyB0cnVlIDogZmFsc2UsXG4gICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWw6XG4gICAgICAgICAgYm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwID8gdHJ1ZSA6IGZhbHNlLFxuICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB0cnVlLFxuICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvbjogdHJ1ZSxcbiAgICAgICAgbG9jYXRpb246IHsgdGl0bGU6IGJvZHk/LmxvY2F0aW9uIH0sXG4gICAgICAgIHJlY3VycmVuY2U6IHJlY3VyLFxuICAgICAgICByZWN1cnJlbmNlUnVsZToge1xuICAgICAgICAgIGZyZXF1ZW5jeTogYm9keT8ucmVjdXI/LmZyZXF1ZW5jeSxcbiAgICAgICAgICBpbnRlcnZhbDogYm9keT8ucmVjdXI/LmludGVydmFsLFxuICAgICAgICAgIGJ5V2Vla0RheTogYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAgICAgICBvY2N1cnJlbmNlOiBib2R5Py5yZWN1cj8ub2NjdXJyZW5jZSxcbiAgICAgICAgICBlbmREYXRlOiBib2R5Py5yZWN1cj8uZW5kRGF0ZSxcbiAgICAgICAgICBieU1vbnRoRGF5OiBib2R5Py5yZWN1cj8uQnlNb250aERheSxcbiAgICAgICAgfSxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgcHJpbWFyeUNhbGVuZGFyPy5pZCxcbiAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zdGFydERhdGUsXG4gICAgICAgIDAsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zZW5kVXBkYXRlcyxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICBib2R5Py5hdHRlbmRlZXM/Lm1hcCgoYSkgPT4gKHsgZW1haWw6IGE/LmVtYWlsIH0pKSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRpdGxlLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lm5vdGVzLFxuICAgICAgICBib2R5Py50aW1lem9uZSxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lm9yaWdpbmFsU3RhcnREYXRlLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHJlY3VyLFxuICAgICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lmxlbmd0aCA+IDAgPyBnb29nbGVSZW1pbmRlciA6IHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udHJhbnNwYXJlbmN5LFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnZpc2liaWxpdHksXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmF0dGFjaG1lbnRzLFxuICAgICAgICAnZGVmYXVsdCcsXG4gICAgICAgIGJvZHk/LmxvY2F0aW9uLFxuICAgICAgICB1bmRlZmluZWRcbiAgICAgICk7XG5cbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuXG4gICAgICBpZiAoYm9keT8uYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCB8fCBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCkge1xuICAgICAgICBjb25zdCByZXR1cm5WYWx1ZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50KFxuICAgICAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbCxcbiAgICAgICAgICBib2R5Py5idWZmZXJUaW1lXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCkge1xuICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmlkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zdGFydERhdGUsXG4gICAgICAgICAgICAwLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zZW5kVXBkYXRlcyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udGl0bGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lm5vdGVzLFxuICAgICAgICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkID0gZ29vZ2xlUmVzVmFsdWUuaWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWQ7XG4gICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnBvc3RFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQ7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAocmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudCkge1xuICAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgICBwcmltYXJ5Q2FsZW5kYXI/LmlkLFxuICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5pZCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zdGFydERhdGUsXG4gICAgICAgICAgICAwLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udGl0bGUsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py52aXNpYmlsaXR5LFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucHJlRXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgICB9XG5cbiAgICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFxuICAgICAgICAgIFtcbiAgICAgICAgICAgIHJldHVyblZhbHVlcy5uZXdFdmVudCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCxcbiAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQsXG4gICAgICAgICAgXT8uZmlsdGVyKChlKSA9PiAhIWUpXG4gICAgICAgICk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBhd2FpdCB1cHNlcnRFdmVudHMoW2V2ZW50VG9VcHNlcnRMb2NhbF0pO1xuICAgICAgfVxuXG4gICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/LmZvckVhY2goKHIpID0+ICh7XG4gICAgICAgIC4uLnIsXG4gICAgICAgIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbC5pZCxcbiAgICAgIH0pKTtcblxuICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcz8uZm9yRWFjaCgocCkgPT4gKHtcbiAgICAgICAgLi4ucCxcbiAgICAgICAgZXZlbnRJZDogZXZlbnRUb1Vwc2VydExvY2FsLmlkLFxuICAgICAgfSkpO1xuXG4gICAgICBhdHRlbmRlZXM/LmZvckVhY2goKGEpID0+ICh7IC4uLmEsIGV2ZW50SWQ6IGV2ZW50VG9VcHNlcnRMb2NhbD8uaWQgfSkpO1xuXG4gICAgICBpZiAocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGF3YWl0IGluc2VydFJlbWluZGVycyhyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQpO1xuICAgICAgfVxuXG4gICAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcyk7XG4gICAgICB9XG5cbiAgICAgIGF3YWl0IHVwc2VydEF0dGVuZGVlc2ZvckV2ZW50KGF0dGVuZGVlcyk7XG4gICAgfVxuXG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSk7XG4gICAgaWYgKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDAgfHwgYm9keT8ucHJpb3JpdHkgPiAxKSB7XG4gICAgICBhd2FpdCBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2goXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgICAgYm9keT8udXNlcklkXG4gICAgICApO1xuICAgIH1cblxuICAgIGF3YWl0IHB1dERhdGFJbkFsbEV2ZW50SW5kZXhJbk9wZW5TZWFyY2goXG4gICAgICBldmVudElkLFxuICAgICAgc2VhcmNoVmVjdG9yLFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgYm9keT8uc3RhcnREYXRlLFxuICAgICAgZGF5anMoYm9keT8uc3RhcnREYXRlKVxuICAgICAgICAudHooYm9keT8udGltZXpvbmUpXG4gICAgICAgIC5hZGQoYm9keT8uZHVyYXRpb24sICdtJylcbiAgICAgICAgLmZvcm1hdCgpXG4gICAgKTtcblxuICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgcmVzcG9uc2UuZGF0YSA9ICdzdWNjZXNzZnVsbHkgc2NoZWR1bGVkIG1lZXRpbmcnO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGZpbmFsIHN0ZXAgc2NoZWR1bGUgbWVldGluZycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc1NjaGVkdWxlTWVldGluZ1BlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nXG4pOiBQcm9taXNlPFJlc3BvbnNlQWN0aW9uVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGxldCBkdXJhdGlvbiA9IDA7XG5cbiAgICBjb25zdCB5ZWFyID0gZGF0ZUpTT05Cb2R5Py55ZWFyO1xuICAgIGNvbnN0IG1vbnRoID0gZGF0ZUpTT05Cb2R5Py5tb250aDtcbiAgICBjb25zdCBkYXkgPSBkYXRlSlNPTkJvZHk/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5ID0gZGF0ZUpTT05Cb2R5Py5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXIgPSBkYXRlSlNPTkJvZHk/LmhvdXI7XG4gICAgY29uc3QgbWludXRlID0gZGF0ZUpTT05Cb2R5Py5taW51dGU7XG4gICAgY29uc3Qgc3RhcnRUaW1lID0gZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWU7XG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgICBkYXRlVGltZTogeyByZXF1aXJlZDogW10gfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdzY2hlZHVsZU1lZXRpbmcnLFxuICAgIH07XG5cbiAgICBjb25zdCBtZWV0aW5nU3RhcnREYXRlID0gZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhcixcbiAgICAgIG1vbnRoLFxuICAgICAgZGF5LFxuICAgICAgaXNvV2Vla2RheSxcbiAgICAgIGhvdXIsXG4gICAgICBtaW51dGUsXG4gICAgICBzdGFydFRpbWUsXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgY29uc3QgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyA9XG4gICAgICBhd2FpdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VHaXZlblVzZXJJZCh1c2VySWQpO1xuXG4gICAgaWYgKGRhdGVKU09OQm9keT8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKGRhdGVKU09OQm9keT8uc3RhcnRUaW1lICYmIGRhdGVKU09OQm9keT8uZW5kVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUsICdISDptbScpO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKGRhdGVKU09OQm9keS5lbmRUaW1lLCAnSEg6bW0nKTtcblxuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgJiYganNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoanNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKTtcbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH0gZWxzZSBpZiAoZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZHVyYXRpb24pIHtcbiAgICAgIGR1cmF0aW9uID0gZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8uZHVyYXRpb247XG4gICAgfSBlbHNlIHtcbiAgICAgIGR1cmF0aW9uID0gMzA7XG4gICAgfVxuXG4gICAgbGV0IHJlY3VyT2JqZWN0OiBSZWN1cnJlbmNlUnVsZVR5cGUgfCB7fSA9IHt9O1xuICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kpIHtcbiAgICAgIGNvbnN0IHJlY3VyRW5kRGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgICAgY3VycmVudFRpbWUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5tb250aCxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICAgKTtcblxuICAgICAgcmVjdXJPYmplY3QgPSB7XG4gICAgICAgIGZyZXF1ZW5jeTpcbiAgICAgICAgICAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlKSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWw6XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCxcbiAgICAgIH07XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXkpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlXZWVrRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5KSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5TW9udGhEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLm9jY3VycmVuY2UgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2U7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZWN1ckVuZERhdGUgfHwganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5lbmREYXRlID1cbiAgICAgICAgICByZWN1ckVuZERhdGUgfHwganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBib2R5OiBTY2hlZHVsZU1lZXRpbmdUeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgYXR0ZW5kZWVzOiBqc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMsXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgZGVzY3JpcHRpb246IGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8IGpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzLFxuICAgICAgY29uZmVyZW5jZUFwcDpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uY29uZmVyZW5jZT8uYXBwIHx8XG4gICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmNvbmZlcmVuY2VBcHAsXG4gICAgICBzdGFydERhdGU6IGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fCBtZWV0aW5nU3RhcnREYXRlLFxuICAgICAgYnVmZmVyVGltZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYnVmZmVyVGltZSB8fCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5idWZmZXJUaW1lLFxuICAgICAgcmVtaW5kZXJzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHwgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucmVtaW5kZXJzIHx8IFtdLFxuICAgICAgcHJpb3JpdHk6IGpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8IDEsXG4gICAgICB0aW1lUHJlZmVyZW5jZXM6IGRhdGVKU09OQm9keT8udGltZVByZWZlcmVuY2VzIHx8IFtdLFxuICAgICAgbG9jYXRpb246IGpzb25Cb2R5Py5wYXJhbXM/LmxvY2F0aW9uLFxuICAgICAgdHJhbnNwYXJlbmN5OiBqc29uQm9keT8ucGFyYW1zPy50cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5OiBqc29uQm9keT8ucGFyYW1zLnZpc2liaWxpdHksXG4gICAgfTtcblxuICAgIGlmIChcbiAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbiAgICApIHtcbiAgICAgIGJvZHkucmVjdXIgPSByZWN1ck9iamVjdCBhcyBhbnk7XG4gICAgfVxuXG4gICAgLy8gaWYgKCFkYXkgJiYgIWlzb1dlZWtkYXkpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnXG4gICAgLy8gICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzBdKVxuICAgIC8vICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkc1xuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHlcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHlcbiAgICAvLyAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keVxuICAgIC8vIH1cblxuICAgIC8vIGlmICgoaG91ciA9PT0gbnVsbCkgJiYgKG1pbnV0ZSA9PT0gbnVsbCkgJiYgIXN0YXJ0VGltZSkge1xuICAgIC8vICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcydcbiAgICAvLyAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkPy5bMV0pXG4gICAgLy8gICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzXG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5XG4gICAgLy8gfVxuXG4gICAgY29uc3QgbmV3QXR0ZW5kZWVzOiBNdXRhdGVkQ2FsZW5kYXJFeHRyYWN0ZWRKU09OQXR0ZW5kZWVUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgYSBvZiBib2R5Py5hdHRlbmRlZXMpIHtcbiAgICAgIGlmICghYT8uZW1haWwpIHtcbiAgICAgICAgY29uc3QgY29udGFjdCA9IGF3YWl0IGdldENvbnRhY3RCeU5hbWVXaXRoVXNlcklkKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICBgJSR7YT8ubmFtZX0lYFxuICAgICAgICApO1xuICAgICAgICBpZiAoY29udGFjdD8uZW1haWxzPy5bMF0/LnZhbHVlKSB7XG4gICAgICAgICAgY29uc3QgcHJpbWFyeUVtYWlsID0gY29udGFjdD8uZW1haWxzPy5maW5kKChlKSA9PiAhIWUucHJpbWFyeSk/LnZhbHVlO1xuICAgICAgICAgIGNvbnN0IGFueUVtYWlsID0gY29udGFjdD8uZW1haWxzPy5bMF0/LnZhbHVlO1xuICAgICAgICAgIG5ld0F0dGVuZGVlcy5wdXNoKHsgLi4uYSwgZW1haWw6IHByaW1hcnlFbWFpbCB8fCBhbnlFbWFpbCB9KTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKFxuICAgICAgICAgICAgcmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXT8uWydhbmQnXT8uWzJdXG4gICAgICAgICAgKTtcbiAgICAgICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goYSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgYm9keS5hdHRlbmRlZXMgPSBuZXdBdHRlbmRlZXM7XG5cbiAgICBpZiAoIWJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlswXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAoIShib2R5Py5hdHRlbmRlZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBjb25zdCB1c2VyQ29udGFjdEluZm9zID0gYXdhaXQgbGlzdFVzZXJDb250YWN0SW5mb3NHaXZlblVzZXJJZCh1c2VySWQpO1xuXG4gICAgY29uc3QgcHJvdmlkZWRIb3N0SW5mbyA9IGJvZHk/LmF0dGVuZGVlcz8uZmluZCgoYSkgPT4gYT8uaXNIb3N0ID09PSB0cnVlKTtcblxuICAgIGNvbnN0IHByaW1hcnlJbmZvSXRlbSA9IHVzZXJDb250YWN0SW5mb3M/LmZpbmQoXG4gICAgICAodSkgPT4gdS5wcmltYXJ5ICYmIHUudHlwZSA9PT0gJ2VtYWlsJ1xuICAgICk7XG5cbiAgICBjb25zdCB1c2VyID0gYXdhaXQgZ2V0VXNlckdpdmVuSWQodXNlcklkKTtcblxuICAgIGNvbnN0IHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvOiBNdXRhdGVkQ2FsZW5kYXJFeHRyYWN0ZWRKU09OQXR0ZW5kZWVUeXBlID0ge1xuICAgICAgbmFtZTogcHJpbWFyeUluZm9JdGVtPy5uYW1lIHx8IHVzZXI/Lm5hbWUsXG4gICAgICBlbWFpbDogcHJpbWFyeUluZm9JdGVtPy5pZCB8fCB1c2VyPy5lbWFpbCxcbiAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICB9O1xuXG4gICAgaWYgKCFwcm92aWRlZEhvc3RJbmZvICYmIHByaW1hcnlIb3N0QXR0ZW5kZWVJbmZvPy5lbWFpbCkge1xuICAgICAgYm9keT8uYXR0ZW5kZWVzLnB1c2gocHJpbWFyeUhvc3RBdHRlbmRlZUluZm8pO1xuICAgIH1cblxuICAgIGNvbnN0IGhvc3RJbmZvID0gcHJvdmlkZWRIb3N0SW5mbyB8fCBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbztcblxuICAgIGlmICghaG9zdEluZm8/LmVtYWlsKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXVsnYW5kJ11bMV0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwU2NoZWR1bGVNZWV0aW5nKFxuICAgICAgYm9keSxcbiAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXMsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBzY2hlZHVsZSBtZWV0aW5nJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzU2NoZWR1bGVNZWV0aW5nTWlzc2luZ0ZpZWxkc1JldHVybmVkID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgZHVyYXRpb24gPSAwO1xuXG4gICAgY29uc3QgeWVhciA9XG4gICAgICBkYXRlSlNPTkJvZHk/LnllYXIgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnllYXI7XG4gICAgY29uc3QgbW9udGggPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5tb250aCB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ubW9udGg7XG4gICAgY29uc3QgZGF5ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZGF5IHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheSA9XG4gICAgICBkYXRlSlNPTkJvZHk/Lmlzb1dlZWtkYXkgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXIgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5ob3VyIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/Lm1pbnV0ZSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICAgIGRhdGVUaW1lOiB7IHJlcXVpcmVkOiBbXSB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ3NjaGVkdWxlTWVldGluZycsXG4gICAgfTtcblxuICAgIGNvbnN0IG1lZXRpbmdTdGFydERhdGUgPSBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB5ZWFyLFxuICAgICAgbW9udGgsXG4gICAgICBkYXksXG4gICAgICBpc29XZWVrZGF5LFxuICAgICAgaG91cixcbiAgICAgIG1pbnV0ZSxcbiAgICAgIHN0YXJ0VGltZSxcbiAgICAgIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lRnJvbU5vdyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBjb25zdCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzID1cbiAgICAgIGF3YWl0IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUdpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBpZiAoXG4gICAgICBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZHVyYXRpb25cbiAgICApIHtcbiAgICAgIGR1cmF0aW9uID1cbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZHVyYXRpb247XG4gICAgfSBlbHNlIGlmIChcbiAgICAgIChkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uc3RhcnRUaW1lKSAmJlxuICAgICAgKGRhdGVKU09OQm9keT8uZW5kVGltZSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uZW5kVGltZSlcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0VGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5zdGFydFRpbWUsXG4gICAgICAgICdISDptbSdcbiAgICAgICk7XG4gICAgICBjb25zdCBlbmRUaW1lT2JqZWN0ID0gZGF5anMoXG4gICAgICAgIGRhdGVKU09OQm9keS5lbmRUaW1lIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5lbmRUaW1lLFxuICAgICAgICAnSEg6bW0nXG4gICAgICApO1xuXG4gICAgICBjb25zdCBtaW51dGVzID0gZW5kVGltZU9iamVjdC5kaWZmKHN0YXJ0VGltZU9iamVjdCwgJ20nKTtcblxuICAgICAgaWYgKG1pbnV0ZXMgPiAwKSB7XG4gICAgICAgIGR1cmF0aW9uID0gbWludXRlcztcbiAgICAgIH1cbiAgICB9IGVsc2UgaWYgKGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmR1cmF0aW9uKSB7XG4gICAgICBkdXJhdGlvbiA9IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoXG4gICAgICAoanNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lKSAmJlxuICAgICAgKGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKVxuICAgICkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoXG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lXG4gICAgICApO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lXG4gICAgICApO1xuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGR1cmF0aW9uID0gMzA7XG4gICAgfVxuXG4gICAgbGV0IHJlY3VyT2JqZWN0OiBSZWN1cnJlbmNlUnVsZVR5cGUgfCB7fSA9IHt9O1xuICAgIGlmIChcbiAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmZyZXF1ZW5jeSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5mcmVxdWVuY3lcbiAgICApIHtcbiAgICAgIGNvbnN0IHJlY3VyRW5kRGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgICAgY3VycmVudFRpbWUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5tb250aCB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGgsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1pbnV0ZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uc3RhcnRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5zdGFydFRpbWUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGVcbiAgICAgICAgICAgID8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vdyB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZVxuICAgICAgICAgICAgPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgICApO1xuXG4gICAgICByZWN1ck9iamVjdCA9IHtcbiAgICAgICAgZnJlcXVlbmN5OlxuICAgICAgICAgIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUpIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWw6XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmludGVydmFsLFxuICAgICAgfTtcblxuICAgICAgaWYgKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieVdlZWtEYXlcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieVdlZWtEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5V2Vla0RheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5XG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlNb250aERheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlNb250aERheTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLm9jY3VycmVuY2UgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2UgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/Lm9jY3VycmVuY2U7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgcmVjdXJFbmREYXRlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlXG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuZW5kRGF0ZSA9XG4gICAgICAgICAgcmVjdXJFbmREYXRlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBuZXdCb2R5OiBTY2hlZHVsZU1lZXRpbmdUeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgYXR0ZW5kZWVzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMsXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5ub3RlcyxcbiAgICAgIGNvbmZlcmVuY2VBcHA6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCB8fFxuICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5jb25mZXJlbmNlQXBwLFxuICAgICAgc3RhcnREYXRlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVldGluZ1N0YXJ0RGF0ZSxcbiAgICAgIGJ1ZmZlclRpbWU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5idWZmZXJUaW1lIHx8XG4gICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LmJ1ZmZlclRpbWUsXG4gICAgICByZW1pbmRlcnM6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyB8fFxuICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5yZW1pbmRlcnMgfHxcbiAgICAgICAgW10sXG4gICAgICBwcmlvcml0eTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucHJpb3JpdHkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fFxuICAgICAgICAxLFxuICAgICAgdGltZVByZWZlcmVuY2VzOlxuICAgICAgICBkYXRlSlNPTkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8udGltZVByZWZlcmVuY2VzIHx8XG4gICAgICAgIFtdLFxuICAgICAgbG9jYXRpb246XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmxvY2F0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24sXG4gICAgICB0cmFuc3BhcmVuY3k6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXMudmlzaWJpbGl0eSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnZpc2liaWxpdHksXG4gICAgfTtcblxuICAgIGlmIChcbiAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbiAgICApIHtcbiAgICAgIG5ld0JvZHkucmVjdXIgPSByZWN1ck9iamVjdCBhcyBhbnk7XG4gICAgfVxuXG4gICAgY29uc3QgcHJldkJvZHk6IFNjaGVkdWxlTWVldGluZ1R5cGUgPSB7XG4gICAgICAuLi5tZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGEsXG4gICAgfTtcblxuICAgIGNvbnN0IG5ld0F0dGVuZGVlczogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGEgb2YgbmV3Qm9keT8uYXR0ZW5kZWVzKSB7XG4gICAgICBpZiAoIWE/LmVtYWlsKSB7XG4gICAgICAgIGNvbnN0IGNvbnRhY3QgPSBhd2FpdCBnZXRDb250YWN0QnlOYW1lV2l0aFVzZXJJZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgYCUke2E/Lm5hbWV9JWBcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZSkge1xuICAgICAgICAgIGNvbnN0IHByaW1hcnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uZmluZCgoZSkgPT4gISFlLnByaW1hcnkpPy52YWx1ZTtcbiAgICAgICAgICBjb25zdCBhbnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZTtcbiAgICAgICAgICBuZXdBdHRlbmRlZXMucHVzaCh7IC4uLmEsIGVtYWlsOiBwcmltYXJ5RW1haWwgfHwgYW55RW1haWwgfSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChcbiAgICAgICAgICAgIHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMV0/LlsnYW5kJ10/LlsyXVxuICAgICAgICAgICk7XG4gICAgICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBuZXdBdHRlbmRlZXMucHVzaChhKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBuZXdCb2R5LmF0dGVuZGVlcyA9IG5ld0F0dGVuZGVlcztcblxuICAgIGlmICghcHJldkJvZHk/LnVzZXJJZCkge1xuICAgICAgcHJldkJvZHkudXNlcklkID0gdXNlcklkIHx8IG5ld0JvZHk/LnVzZXJJZDtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aW1lem9uZSkge1xuICAgICAgcHJldkJvZHkudGltZXpvbmUgPSB0aW1lem9uZSB8fCBuZXdCb2R5Py50aW1lem9uZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcHJldkJvZHkudGl0bGUgPSBuZXdCb2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8uYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkuYXR0ZW5kZWVzID0gbmV3Qm9keT8uYXR0ZW5kZWVzO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmR1cmF0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5kdXJhdGlvbiA9IG5ld0JvZHk/LmR1cmF0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmRlc2NyaXB0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5kZXNjcmlwdGlvbiA9IG5ld0JvZHk/LmRlc2NyaXB0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmNvbmZlcmVuY2VBcHApIHtcbiAgICAgIHByZXZCb2R5LmNvbmZlcmVuY2VBcHAgPSBuZXdCb2R5Py5jb25mZXJlbmNlQXBwO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnN0YXJ0RGF0ZSkge1xuICAgICAgcHJldkJvZHkuc3RhcnREYXRlID0gbmV3Qm9keT8uc3RhcnREYXRlO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmJ1ZmZlclRpbWUpIHtcbiAgICAgIHByZXZCb2R5LmJ1ZmZlclRpbWUgPSBuZXdCb2R5Py5idWZmZXJUaW1lO1xuICAgIH1cblxuICAgIGlmICghKHByZXZCb2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBwcmV2Qm9keS5yZW1pbmRlcnMgPSBuZXdCb2R5Py5yZW1pbmRlcnMgfHwgW107XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ucHJpb3JpdHkpIHtcbiAgICAgIHByZXZCb2R5LnByaW9yaXR5ID0gbmV3Qm9keT8ucHJpb3JpdHk7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnRpbWVQcmVmZXJlbmNlcyA9IG5ld0JvZHk/LnRpbWVQcmVmZXJlbmNlcztcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5sb2NhdGlvbikge1xuICAgICAgcHJldkJvZHkubG9jYXRpb24gPSBuZXdCb2R5Py5sb2NhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50cmFuc3BhcmVuY3kpIHtcbiAgICAgIHByZXZCb2R5LnRyYW5zcGFyZW5jeSA9IG5ld0JvZHk/LnRyYW5zcGFyZW5jeTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py52aXNpYmlsaXR5KSB7XG4gICAgICBwcmV2Qm9keS52aXNpYmlsaXR5ID0gbmV3Qm9keT8udmlzaWJpbGl0eTtcbiAgICB9XG5cbiAgICAvLyBpZiAoIXByZXZCb2R5Py5zdGFydERhdGUpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnXG4gICAgLy8gICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzBdKVxuICAgIC8vICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkc1xuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5XG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5XG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHlcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoIXByZXZCb2R5Py5zdGFydERhdGUgJiYgKGhvdXIgPT09IG51bGwpICYmIChtaW51dGUgPT09IG51bGwpICYmICFzdGFydFRpbWUpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnXG4gICAgLy8gICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzFdKVxuICAgIC8vICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkc1xuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5XG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5XG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHlcbiAgICAvLyB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmICghKHByZXZCb2R5Py5hdHRlbmRlZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgY29uc3QgdXNlckNvbnRhY3RJbmZvcyA9IGF3YWl0IGxpc3RVc2VyQ29udGFjdEluZm9zR2l2ZW5Vc2VySWQodXNlcklkKTtcblxuICAgIGNvbnN0IG5ld1Byb3ZpZGVkSG9zdEluZm8gPSBuZXdCb2R5Py5hdHRlbmRlZXM/LmZpbmQoXG4gICAgICAoYSkgPT4gYT8uaXNIb3N0ID09PSB0cnVlXG4gICAgKTtcblxuICAgIGNvbnN0IHByZXZQcm92aWRlZEhvc3RJbmZvID0gcHJldkJvZHk/LmF0dGVuZGVlcz8uZmluZChcbiAgICAgIChhKSA9PiBhPy5pc0hvc3QgPT09IHRydWVcbiAgICApO1xuXG4gICAgY29uc3QgcHJpbWFyeUluZm9JdGVtID0gdXNlckNvbnRhY3RJbmZvcz8uZmluZChcbiAgICAgICh1KSA9PiB1LnByaW1hcnkgJiYgdS50eXBlID09PSAnZW1haWwnXG4gICAgKTtcblxuICAgIGNvbnN0IHVzZXIgPSBhd2FpdCBnZXRVc2VyR2l2ZW5JZCh1c2VySWQpO1xuXG4gICAgY29uc3QgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm86IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGUgPSB7XG4gICAgICBuYW1lOiBwcmltYXJ5SW5mb0l0ZW0/Lm5hbWUgfHwgdXNlcj8ubmFtZSxcbiAgICAgIGVtYWlsOiBwcmltYXJ5SW5mb0l0ZW0/LmlkIHx8IHVzZXI/LmVtYWlsLFxuICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIH07XG5cbiAgICBpZiAoIW5ld1Byb3ZpZGVkSG9zdEluZm8gJiYgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm8/LmVtYWlsKSB7XG4gICAgICBuZXdCb2R5Py5hdHRlbmRlZXMucHVzaChwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbyk7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2UHJvdmlkZWRIb3N0SW5mbyAmJiBwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbz8uZW1haWwpIHtcbiAgICAgIHByZXZCb2R5Py5hdHRlbmRlZXMucHVzaChwcmltYXJ5SG9zdEF0dGVuZGVlSW5mbyk7XG4gICAgfVxuXG4gICAgY29uc3QgcHJldkhvc3RJbmZvID1cbiAgICAgIHByZXZQcm92aWRlZEhvc3RJbmZvIHx8IG5ld1Byb3ZpZGVkSG9zdEluZm8gfHwgcHJpbWFyeUhvc3RBdHRlbmRlZUluZm87XG5cbiAgICBpZiAoIXByZXZIb3N0SW5mbz8uZW1haWwpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzFdWydhbmQnXVsxXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ucmVjdXIpIHtcbiAgICAgIHByZXZCb2R5LnJlY3VyID0gbmV3Qm9keT8ucmVjdXI7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwU2NoZWR1bGVNZWV0aW5nKFxuICAgICAgcHJldkJvZHksXG4gICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3Mgc2NoZWR1bGUgbWVldGluZyBtaXNzaW5nIGZpZWxkcyByZXR1cm5lZCdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3Qgc2NoZWR1bGVNZWV0aW5nQ29udHJvbENlbnRlciA9IGFzeW5jIChcbiAgb3BlbmFpOiBPcGVuQUksXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG4gIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuICBxdWVyeTogJ21pc3NpbmdfZmllbGRzJyB8ICdjb21wbGV0ZWQnIHwgJ2V2ZW50X25vdF9mb3VuZCcgfCAncGVuZGluZydcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG1lc3NhZ2VMZW5ndGggPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcz8ubGVuZ3RoO1xuICAgIGxldCB1c2VyTWVzc2FnZSA9ICcnO1xuICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgdXNlck1lc3NhZ2UgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHVzZXJJbnB1dCA9IHVzZXJNZXNzYWdlO1xuXG4gICAgbGV0IHNjaGVkdWxlTWVldGluZ1JlczogUmVzcG9uc2VBY3Rpb25UeXBlID0ge1xuICAgICAgcXVlcnk6ICdjb21wbGV0ZWQnLFxuICAgICAgZGF0YTogJycsXG4gICAgICBza2lsbDogJycsXG4gICAgICBwcmV2RGF0YToge30sXG4gICAgICBwcmV2RGF0YUV4dHJhOiB7fSxcbiAgICB9O1xuXG4gICAgc3dpdGNoIChxdWVyeSkge1xuICAgICAgY2FzZSAncGVuZGluZyc6XG4gICAgICAgIGNvbnN0IGpzb25Cb2R5ID0gYXdhaXQgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBjb25zdCBkYXRlVGltZSA9IGF3YWl0IGdlbmVyYXRlRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuICAgICAgICBzY2hlZHVsZU1lZXRpbmdSZXMgPSBhd2FpdCBwcm9jZXNzU2NoZWR1bGVNZWV0aW5nUGVuZGluZyhcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbkJvZHksXG4gICAgICAgICAgZGF0ZVRpbWUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnbWlzc2luZ19maWVsZHMnOlxuICAgICAgICBsZXQgcHJpb3JVc2VySW5wdXQgPSAnJztcbiAgICAgICAgbGV0IHByaW9yQXNzaXN0YW50T3V0cHV0ID0gJyc7XG5cbiAgICAgICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ2Fzc2lzdGFudCcpIHtcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgICAgICBpZiAobWVzc2FnZS5jb250ZW50ICE9PSB1c2VySW5wdXQpIHtcbiAgICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghcHJpb3JVc2VySW5wdXQgfHwgIXByaW9yQXNzaXN0YW50T3V0cHV0KSB7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JVc2VySW5wdXQsICcgcHJpb3JVc2VySW5wdXQnKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvckFzc2lzdGFudE91dHB1dCwgJyBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpb3JVc2VyaW5wdXQgb3IgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBqc29uTWlzc2luZ0ZpZWxkc0JvZHkgPVxuICAgICAgICAgIGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgICApO1xuICAgICAgICBjb25zdCBkYXRlTWlzc2luZ0ZpZWxkc1RpbWUgPSBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZShcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICk7XG5cbiAgICAgICAgc2NoZWR1bGVNZWV0aW5nUmVzID0gYXdhaXQgcHJvY2Vzc1NjaGVkdWxlTWVldGluZ01pc3NpbmdGaWVsZHNSZXR1cm5lZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbk1pc3NpbmdGaWVsZHNCb2R5LFxuICAgICAgICAgIGRhdGVNaXNzaW5nRmllbGRzVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgfVxuXG4gICAgaWYgKHNjaGVkdWxlTWVldGluZ1Jlcz8ucXVlcnkgPT09ICdjb21wbGV0ZWQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5KFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBzY2hlZHVsZU1lZXRpbmdSZXMuZGF0YSBhcyBzdHJpbmcsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfSBlbHNlIGlmIChzY2hlZHVsZU1lZXRpbmdSZXM/LnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIHNjaGVkdWxlTWVldGluZ1Jlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID1cbiAgICAgICAgc2NoZWR1bGVNZWV0aW5nUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhID0gc2NoZWR1bGVNZWV0aW5nUmVzPy5wcmV2RGF0YTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhRXh0cmEgPSBzY2hlZHVsZU1lZXRpbmdSZXM/LnByZXZEYXRhRXh0cmE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0ZUpzb25Cb2R5ID1cbiAgICAgICAgc2NoZWR1bGVNZWV0aW5nUmVzPy5wcmV2RGF0ZUpzb25Cb2R5O1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkpzb25Cb2R5ID0gc2NoZWR1bGVNZWV0aW5nUmVzPy5wcmV2SnNvbkJvZHk7XG4gICAgfSBlbHNlIGlmIChzY2hlZHVsZU1lZXRpbmdSZXM/LnF1ZXJ5ID09PSAnZXZlbnRfbm90X2ZvdW5kJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZTogQXNzaXN0YW50TWVzc2FnZVR5cGUgPSB7XG4gICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgICBjb250ZW50OiBcIk9vcHMuLi4gSSBjb3VsZG4ndCBmaW5kIHRoZSBldmVudC4gU29ycnkgOihcIixcbiAgICAgIH07XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH1cblxuICAgIHJldHVybiBtZXNzYWdlSGlzdG9yeU9iamVjdDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHNjaGVkdWxlIG1lZXRpbmcgY29udHJvbCBjZW50ZXIgcGVuZGluZycpO1xuICB9XG59O1xuIl19