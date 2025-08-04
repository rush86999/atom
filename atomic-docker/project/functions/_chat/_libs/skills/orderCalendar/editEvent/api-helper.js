import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, createGoogleEvent, createPreAndPostEventsFromEvent, createRRuleString, createZoomMeeting, deleteConferenceGivenId, deleteEventGivenId, deleteGoogleEvent, deleteRemindersWithIds, deleteZoomMeeting, eventSearchBoundary, extrapolateStartDateFromJSONData, findContactByEmailGivenUserId, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, getCalendarIntegrationByName, getConferenceGivenId, getContactByNameWithUserId, getEventFromPrimaryKey, getUserContactInfosGivenIds, getZoomAPIToken, insertReminders, patchGoogleEvent, putDataInTrainEventIndexInOpenSearch, updateZoomMeeting, upsertAttendeesforEvent, upsertConference, upsertEvents, } from '@chat/_libs/api-helper';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import requiredFields from './requiredFields';
import { v4 as uuid } from 'uuid';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { googleCalendarName } from '@chat/_libs/constants';
import { deletePreferredTimeRangesGivenEventId } from '../removeAllPreferedTimes/api-helper';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
export const finalStepEditEvent = async (body, defaultMeetingPreferences, startDate, endDate, response) => {
    try {
        // convert to vector for search
        const searchTitle = body?.oldTitle || body?.title;
        const searchVector = await convertEventTitleToOpenAIVector(searchTitle);
        //  allEventWithEventOpenSearch
        // allEventOpenSearch
        if (!startDate) {
            startDate = dayjs().subtract(2, 'w').format();
        }
        if (!endDate) {
            endDate = dayjs().add(4, 'w').format();
        }
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
        // validate
        if (!oldEvent?.id) {
            throw new Error('no old event found?!');
        }
        // if no priority use old
        if (!body?.priority) {
            body.priority = oldEvent.priority || 1;
        }
        // findContactByEmailGivenUserId
        // get attendees with provided emails
        const aWithEmails = body?.attendees?.filter((a) => !!a?.email);
        const aWithContactInfos = await getUserContactInfosGivenIds(aWithEmails?.map((a) => a?.email));
        const attendeesFromExtractedJSON = body?.attendees || [];
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
        // take care of recurrence
        const recur = createRRuleString(body?.recur?.frequency, body?.recur?.interval, body?.recur?.byWeekDay, body?.recur?.occurrence, body?.recur?.endDate, body?.recur?.byMonthDay);
        let conference = {};
        // conference: create / update and store in db
        if (body?.conferenceApp && !oldEvent.conferenceId) {
            // create conference object
            const zoomToken = await getZoomAPIToken(body?.userId);
            conference =
                zoomToken && body?.conferenceApp === 'zoom'
                    ? {}
                    : {
                        id: uuid(),
                        userId: body?.userId,
                        calendarId: oldEvent?.calendarId,
                        app: 'google',
                        name: defaultMeetingPreferences?.name,
                        notes: body?.description || body?.title,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        deleted: false,
                        isHost: true,
                    };
            if (body?.conferenceApp === 'zoom') {
                console.log(zoomToken, ' zoomToken inside if (zoomToken)');
                const zoomObject = await createZoomMeeting(zoomToken, body?.startDate, body?.timezone, body?.title, body?.duration, defaultMeetingPreferences?.name, defaultMeetingPreferences?.primaryEmail, body?.attendees?.map((a) => a?.email), body?.recur);
                console.log(zoomObject, ' zoomObject after createZoomMeeting');
                if (zoomObject) {
                    conference = {
                        id: `${zoomObject?.id}`,
                        userId: body?.userId,
                        calendarId: oldEvent?.id,
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
            // insert new conference
            await upsertConference(conference);
        }
        else if (body?.conferenceApp && oldEvent.conferenceId) {
            // get old conference object
            const oldConference = await getConferenceGivenId(oldEvent?.conferenceId);
            // create conference object
            const zoomToken = await getZoomAPIToken(body?.userId);
            // updateZoomMeeting
            conference =
                zoomToken && body?.conferenceApp === 'zoom'
                    ? {}
                    : {
                        ...oldConference,
                        id: oldEvent?.conferenceId,
                        userId: body?.userId,
                        calendarId: oldEvent?.calendarId,
                        app: 'google',
                        name: defaultMeetingPreferences?.name,
                        notes: body?.description || body?.title,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        deleted: false,
                        isHost: true,
                    };
            if (body?.conferenceApp === oldConference.app) {
                console.log(zoomToken, ' zoomToken inside if (zoomToken)');
                if (zoomToken && body?.conferenceApp === 'zoom') {
                    await updateZoomMeeting(zoomToken, parseInt(oldEvent?.conferenceId, 10), body?.startDate, body?.timezone, body?.title || body?.description, body?.duration || oldEvent?.duration, defaultMeetingPreferences?.name, defaultMeetingPreferences?.primaryEmail, attendees?.length > 0
                        ? attendees?.map((a) => a?.emails?.[0]?.value)
                        : undefined, undefined, body?.recur);
                    conference = {
                        ...oldConference,
                        id: oldConference?.id,
                        userId: body?.userId,
                        calendarId: oldEvent?.calendarId,
                        app: 'zoom',
                        name: defaultMeetingPreferences?.name,
                        notes: body?.description || oldEvent?.notes,
                        isHost: true,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        deleted: false,
                    };
                }
                else {
                    conference = {
                        ...oldConference,
                        userId: body?.userId,
                        calendarId: oldEvent?.calendarId,
                        app: 'google',
                        name: defaultMeetingPreferences?.name,
                        notes: body?.description || body?.title,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        deleted: false,
                        isHost: true,
                    };
                }
                // insert new conference
                await upsertConference(conference);
            }
            else if (body?.conferenceApp !== oldConference.app) {
                // create conference object
                const zoomToken = await getZoomAPIToken(body?.userId);
                conference =
                    zoomToken && body?.conferenceApp === 'zoom'
                        ? {}
                        : {
                            id: uuid(),
                            userId: body?.userId,
                            calendarId: oldEvent?.calendarId,
                            app: 'google',
                            name: defaultMeetingPreferences?.name,
                            notes: body?.description || body?.title,
                            updatedAt: dayjs().format(),
                            createdDate: dayjs().format(),
                            deleted: false,
                            isHost: true,
                        };
                if (zoomToken && body?.conferenceApp === 'zoom') {
                    console.log(zoomToken, ' zoomToken inside if (zoomToken)');
                    const zoomObject = await createZoomMeeting(zoomToken, body?.startDate, body?.timezone, body?.title || body?.description, body?.duration, defaultMeetingPreferences?.name, defaultMeetingPreferences?.primaryEmail, body?.attendees?.map((a) => a?.email), body?.recur);
                    console.log(zoomObject, ' zoomObject after createZoomMeeting');
                    if (zoomObject) {
                        conference = {
                            id: `${zoomObject?.id}`,
                            userId: body?.userId,
                            calendarId: oldEvent?.id,
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
                // delete old conference
                await deleteConferenceGivenId(oldConference?.id);
                if (oldConference.app === 'zoom') {
                    await deleteZoomMeeting(zoomToken, parseInt(oldConference.id, 10));
                }
                // insert new conference
                await upsertConference(conference);
            }
        }
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
        // create new time preferences and priority
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
        // create new reminders for updated event
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
        const eventToUpsertLocal = {
            ...oldEvent,
            id: eventId,
            userId: body?.userId,
            timezone: body?.timezone,
            isPreEvent: false,
            isPostEvent: false,
            updatedAt: dayjs().format(),
        };
        if (body?.allDay) {
            eventToUpsertLocal.allDay = body?.allDay;
        }
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
        if (body?.description || body?.title) {
            eventToUpsertLocal.notes = body?.description || body?.title;
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
        if (conference?.id) {
            eventToUpsertLocal.conferenceId = conference?.id;
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
        const googleReminder = {
            overrides: remindersToUpdateEventId?.map((r) => ({
                method: 'email',
                minutes: r?.minutes,
            })),
            useDefault: false,
        };
        await patchGoogleEvent(body?.userId, oldEvent?.calendarId, eventToUpsertLocal?.eventId, calIntegration?.clientType, eventToUpsertLocal?.endDate, eventToUpsertLocal?.startDate, eventToUpsertLocal?.conferenceId ? 1 : 0, undefined, eventToUpsertLocal?.sendUpdates, eventToUpsertLocal?.anyoneCanAddSelf, body?.attendees?.map((a) => ({ email: a?.email })), conference?.id
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
            : undefined, eventToUpsertLocal?.summary, eventToUpsertLocal?.notes, eventToUpsertLocal?.timezone, undefined, undefined, undefined, eventToUpsertLocal?.guestsCanInviteOthers, eventToUpsertLocal?.guestsCanModify, eventToUpsertLocal?.guestsCanSeeOtherGuests, eventToUpsertLocal?.originalStartDate, undefined, recur, remindersToUpdateEventId?.length > 0 ? googleReminder : undefined, undefined, undefined, eventToUpsertLocal?.transparency, eventToUpsertLocal?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', body?.location, undefined);
        // add buffer time
        // add buffer time if any
        if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
            const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime);
            if (returnValues?.afterEvent) {
                const googleResValue = await createGoogleEvent(body?.userId, oldEvent?.calendarId, calIntegration?.clientType, returnValues?.afterEvent?.id, returnValues?.afterEvent?.endDate, returnValues?.afterEvent?.startDate, 0, undefined, returnValues?.afterEvent?.sendUpdates, returnValues?.afterEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.afterEvent?.title, returnValues?.afterEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.afterEvent?.guestsCanInviteOthers, returnValues?.afterEvent?.guestsCanModify, returnValues?.afterEvent?.guestsCanSeeOtherGuests, undefined, undefined, recur, undefined, undefined, undefined, returnValues?.afterEvent?.transparency, returnValues?.afterEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                returnValues.afterEvent.id = googleResValue.id;
                returnValues.afterEvent.eventId = googleResValue.googleEventId;
                returnValues.newEvent.postEventId = returnValues.afterEvent.id;
            }
            if (returnValues?.beforeEvent) {
                const googleResValue = await createGoogleEvent(body?.userId, oldEvent?.calendarId, calIntegration?.clientType, returnValues?.beforeEvent?.id, returnValues?.beforeEvent?.endDate, returnValues?.beforeEvent?.startDate, 0, undefined, returnValues?.beforeEvent?.sendUpdates, returnValues?.beforeEvent?.anyoneCanAddSelf, undefined, undefined, returnValues?.beforeEvent?.title, returnValues?.beforeEvent?.notes, body?.timezone, undefined, undefined, undefined, returnValues?.beforeEvent?.guestsCanInviteOthers, returnValues?.beforeEvent?.guestsCanModify, returnValues?.beforeEvent?.guestsCanSeeOtherGuests, undefined, undefined, recur, undefined, undefined, undefined, returnValues?.beforeEvent?.transparency, returnValues?.beforeEvent?.visibility, undefined, undefined, undefined, undefined, undefined, undefined, 'default', undefined, undefined);
                returnValues.beforeEvent.id = googleResValue.id;
                returnValues.beforeEvent.eventId = googleResValue.googleEventId;
                returnValues.newEvent.preEventId = returnValues.afterEvent.id;
            }
            // insert events
            await upsertEvents([
                returnValues.newEvent,
                returnValues?.afterEvent,
                returnValues?.beforeEvent,
            ]?.filter((e) => !!e));
        }
        else {
            // insert events
            await upsertEvents([eventToUpsertLocal]);
        }
        // update reminders
        remindersToUpdateEventId?.forEach((r) => ({ ...r, eventId: oldEvent?.id }));
        // update timePreferences
        newPreferredTimeRanges?.forEach((pt) => ({ ...pt, eventId: oldEvent?.id }));
        // insert reminders
        if (remindersToUpdateEventId?.length > 0) {
            await insertReminders(remindersToUpdateEventId);
        }
        // insert time preferences
        if (newPreferredTimeRanges?.length > 0) {
            await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
        }
        // add training for time preferences and priority
        // convert to vector for search
        if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
            const searchVector = await convertEventTitleToOpenAIVector(body?.title);
            // train event
            await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, body?.userId);
        }
        // update attendees for event Id
        await upsertAttendeesforEvent(attendees);
        // success response
        response.query = 'completed';
        response.data = 'event successfully edited';
        return response;
    }
    catch (e) {
        console.log(e, ' unable final step edit event');
    }
};
export const processEditEventPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
    try {
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
        let startDate = searchBoundary.startDate;
        let endDate = searchBoundary.endDate;
        let duration = 0;
        const year = dateJSONBody?.year;
        const month = dateJSONBody?.month;
        const day = dateJSONBody?.day;
        const isoWeekday = dateJSONBody?.isoWeekday;
        const hour = dateJSONBody?.hour;
        const minute = dateJSONBody?.minute;
        const startTime = dateJSONBody?.startTime;
        const eventStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow);
        // get default values
        const defaultMeetingPreferences = await getChatMeetingPreferenceGivenUserId(userId);
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
            const recurEndDate = extrapolateStartDateFromJSONData(currentTime, timezone, dateJSONBody?.recur?.endDate?.year, dateJSONBody?.recur?.endDate?.month, dateJSONBody?.recur?.endDate?.day, dateJSONBody?.recur?.endDate?.isoWeekday, dateJSONBody?.recur?.endDate?.hour, dateJSONBody?.recur?.endDate?.minute, dateJSONBody?.recur?.endDate?.startTime, dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow, dateJSONBody?.recur?.endDate?.relativeTimeFromNow);
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
            oldTitle: jsonBody?.params?.oldTitle,
            attendees: jsonBody?.params?.attendees,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description || jsonBody?.params?.notes,
            conferenceApp: jsonBody?.params?.conference?.app,
            startDate: jsonBody?.params?.startTime || eventStartDate,
            bufferTime: jsonBody?.params?.bufferTime,
            reminders: jsonBody?.params?.alarms,
            priority: jsonBody?.params?.priority,
            timePreferences: dateJSONBody?.timePreferences,
            location: jsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params?.visibility,
            isFollowUp: jsonBody?.params?.isFollowUp,
            isBreak: jsonBody?.params?.isBreak,
            allDay: dateJSONBody?.allDay,
        };
        if (recurObject?.frequency) {
            body.recur = recurObject;
        }
        // validate for missing fields
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'editEvent',
        };
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
        // get info of contacts without emails provided and assign values
        const newAttendees = [];
        for (const a of body?.attendees) {
            if (!a?.email) {
                const contact = await getContactByNameWithUserId(userId, a?.name);
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
                    response.prevDataExtra = {
                        searchBoundary,
                    };
                    response.prevJsonBody = jsonBody;
                    response.prevDateJsonBody = dateJSONBody;
                }
            }
            else {
                newAttendees.push(a);
            }
        }
        body.attendees = newAttendees;
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepEditEvent(body, defaultMeetingPreferences, startDate, endDate, response);
        return response2;
        // convert to vector for search
        // const searchTitle = body?.oldTitle || body?.title
        // const searchVector = await convertEventTitleToOpenAIVector(searchTitle)
        // //  allEventWithEventOpenSearch
        // // allEventOpenSearch
        // if (!startDate) {
        //     startDate = dayjs().subtract(2, 'w').format()
        // }
        // if (!endDate) {
        //     endDate = dayjs().add(4, 'w').format()
        // }
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
        // // validate
        // if (!oldEvent?.id) {
        //     throw new Error('no old event found?!')
        // }
        // // if no priority use old
        // if (!body?.priority) {
        //     body.priority = oldEvent.priority || 1
        // }
        // // findContactByEmailGivenUserId
        // // get attendees with provided emails
        // const aWithEmails = body?.attendees?.filter(a => !!a?.email)
        // const aWithContactInfos = await getUserContactInfosGivenIds(aWithEmails?.map(a => (a?.email)))
        // const attendeesFromExtractedJSON = body?.attendees || []
        // const attendees: AttendeeType[] = []
        // for (const a of attendeesFromExtractedJSON) {
        //     const contact = await findContactByEmailGivenUserId(userId, a.email)
        //     const userIdFound = aWithContactInfos?.find(b => (b?.id === a?.email))
        //     const attendee: AttendeeType = {
        //         id: userIdFound?.userId || uuid(),
        //         userId,
        //         name: a?.name || contact?.name || `${contact?.firstName} ${contact?.lastName}`,
        //         contactId: contact?.id,
        //         emails: [{ primary: true, value: a?.email }],
        //         updatedAt: dayjs().format(),
        //         createdDate: dayjs().format(),
        //         deleted: false,
        //         eventId,
        //     }
        //     attendees.push(attendee)
        // }
        // // take care of recurrence
        // const recur = createRRuleString(body?.recur?.frequency, body?.recur?.interval, body?.recur?.byWeekDay, body?.recur?.occurrence, body?.recur?.endDate, (body?.recur as RecurrenceRuleType)?.byMonthDay)
        // let conference: ConferenceType | {} = {}
        // // conference: create / update and store in db
        // if (body?.conferenceApp && !oldEvent.conferenceId) {
        //     // create conference object
        //     const zoomToken = await getZoomAPIToken(userId)
        //     conference = (zoomToken && (body?.conferenceApp === 'zoom')) ? {} : {
        //         id: uuid(),
        //         userId,
        //         calendarId: oldEvent?.calendarId,
        //         app: 'google',
        //         name: defaultMeetingPreferences?.name,
        //         notes: body?.description || body?.title,
        //         updatedAt: dayjs().format(),
        //         createdDate: dayjs().format(),
        //         deleted: false,
        //         isHost: true,
        //     }
        //     if (body?.conferenceApp === 'zoom') {
        //         console.log(zoomToken, ' zoomToken inside if (zoomToken)')
        //         const zoomObject = await createZoomMeeting(
        //             zoomToken,
        //             body?.startDate,
        //             timezone,
        //             body?.title,
        //             duration,
        //             defaultMeetingPreferences?.name,
        //             defaultMeetingPreferences?.primaryEmail,
        //             body?.attendees?.map(a => a?.email),
        //             body?.recur as any,
        //         )
        //         console.log(zoomObject, ' zoomObject after createZoomMeeting')
        //         if (zoomObject) {
        //             conference = {
        //                 id: `${zoomObject?.id}`,
        //                 userId: userId,
        //                 calendarId: oldEvent?.id,
        //                 app: 'zoom',
        //                 name: zoomObject?.agenda,
        //                 notes: zoomObject?.agenda,
        //                 joinUrl: zoomObject?.join_url,
        //                 startUrl: zoomObject?.start_url,
        //                 isHost: true,
        //                 updatedAt: dayjs().format(),
        //                 createdDate: dayjs().format(),
        //                 deleted: false,
        //                 entryPoints: [{
        //                     entryPointType: 'video',
        //                     label: zoomObject?.join_url,
        //                     password: zoomObject?.password,
        //                     uri: zoomObject?.join_url,
        //                 }]
        //             } as ConferenceType
        //         }
        //     }
        //     // insert new conference
        //     await upsertConference(conference as ConferenceType)
        // } else if (body?.conferenceApp && oldEvent.conferenceId) {
        //     // get old conference object
        //     const oldConference = await getConferenceGivenId(oldEvent?.conferenceId)
        //     // create conference object
        //     const zoomToken = await getZoomAPIToken(userId)
        //     // updateZoomMeeting
        //     conference = (zoomToken && (body?.conferenceApp === 'zoom')) ? {} : {
        //         ...oldConference,
        //         id: oldEvent?.conferenceId,
        //         userId,
        //         calendarId: oldEvent?.calendarId,
        //         app: 'google',
        //         name: defaultMeetingPreferences?.name,
        //         notes: body?.description || body?.title,
        //         updatedAt: dayjs().format(),
        //         createdDate: dayjs().format(),
        //         deleted: false,
        //         isHost: true,
        //     }
        //     if (body?.conferenceApp === oldConference.app) {
        //         console.log(zoomToken, ' zoomToken inside if (zoomToken)')
        //         if (zoomToken && (body?.conferenceApp === 'zoom')) {
        //             await updateZoomMeeting(
        //                 zoomToken,
        //                 parseInt(oldEvent?.conferenceId, 10),
        //                 body?.startDate,
        //                 body?.timezone,
        //                 body?.title || body?.description,
        //                 duration || body?.duration || oldEvent?.duration,
        //                 defaultMeetingPreferences?.name,
        //                 defaultMeetingPreferences?.primaryEmail,
        //                 attendees?.length > 0 ? attendees?.map(a => a?.emails?.[0]?.value) : undefined,
        //                 undefined,
        //                 body?.recur as any,
        //             )
        //             conference = {
        //                 ...oldConference,
        //                 id: oldConference?.id,
        //                 userId: userId,
        //                 calendarId: oldEvent?.calendarId,
        //                 app: 'zoom',
        //                 name: defaultMeetingPreferences?.name,
        //                 notes: body?.description || oldEvent?.notes,
        //                 isHost: true,
        //                 updatedAt: dayjs().format(),
        //                 createdDate: dayjs().format(),
        //                 deleted: false,
        //             } as ConferenceType
        //         } else {
        //             conference = {
        //                 ...oldConference,
        //                 userId,
        //                 calendarId: oldEvent?.calendarId,
        //                 app: 'google',
        //                 name: defaultMeetingPreferences?.name,
        //                 notes: body?.description || body?.title,
        //                 updatedAt: dayjs().format(),
        //                 createdDate: dayjs().format(),
        //                 deleted: false,
        //                 isHost: true,
        //             }
        //         }
        //         // insert new conference
        //         await upsertConference(conference as ConferenceType)
        //     } else if (body?.conferenceApp !== oldConference.app) {
        //         // create conference object
        //         const zoomToken = await getZoomAPIToken(userId)
        //         conference = (zoomToken && (body?.conferenceApp === 'zoom')) ? {} : {
        //             id: uuid(),
        //             userId,
        //             calendarId: oldEvent?.calendarId,
        //             app: 'google',
        //             name: defaultMeetingPreferences?.name,
        //             notes: body?.description || body?.title,
        //             updatedAt: dayjs().format(),
        //             createdDate: dayjs().format(),
        //             deleted: false,
        //             isHost: true,
        //         }
        //         if (zoomToken && (body?.conferenceApp === 'zoom')) {
        //             console.log(zoomToken, ' zoomToken inside if (zoomToken)')
        //             const zoomObject = await createZoomMeeting(
        //                 zoomToken,
        //                 body?.startDate,
        //                 timezone,
        //                 body?.title || body?.description,
        //                 duration,
        //                 defaultMeetingPreferences?.name,
        //                 defaultMeetingPreferences?.primaryEmail,
        //                 body?.attendees?.map(a => a?.email),
        //                 body?.recur as any,
        //             )
        //             console.log(zoomObject, ' zoomObject after createZoomMeeting')
        //             if (zoomObject) {
        //                 conference = {
        //                     id: `${zoomObject?.id}`,
        //                     userId: userId,
        //                     calendarId: oldEvent?.id,
        //                     app: 'zoom',
        //                     name: zoomObject?.agenda,
        //                     notes: zoomObject?.agenda,
        //                     joinUrl: zoomObject?.join_url,
        //                     startUrl: zoomObject?.start_url,
        //                     isHost: true,
        //                     updatedAt: dayjs().format(),
        //                     createdDate: dayjs().format(),
        //                     deleted: false,
        //                     entryPoints: [{
        //                         entryPointType: 'video',
        //                         label: zoomObject?.join_url,
        //                         password: zoomObject?.password,
        //                         uri: zoomObject?.join_url,
        //                     }]
        //                 } as ConferenceType
        //             }
        //         }
        //         // delete old conference
        //         await deleteConferenceGivenId(oldConference?.id)
        //         if (oldConference.app === 'zoom') {
        //             await deleteZoomMeeting(zoomToken, parseInt(oldConference.id, 10))
        //         }
        //         // insert new conference
        //         await upsertConference(conference as ConferenceType)
        //     }
        // }
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
        // // create new time preferences and priority
        // const newPreferredTimeRanges: PreferredTimeRangeType[] = []
        // for (const timepreference of body?.timePreferences) {
        //     if (timepreference.dayOfWeek?.length > 0) {
        //         for (const dayOfWeek of timepreference.dayOfWeek) {
        //             const newPreferredTimeRange: PreferredTimeRangeType = {
        //                 id: uuid(),
        //                 eventId,
        //                 dayOfWeek: DayOfWeekEnum[dayOfWeek],
        //                 startTime: timepreference?.timeRange?.startTime,
        //                 endTime: timepreference?.timeRange?.endTime,
        //                 updatedAt: dayjs().format(),
        //                 createdDate: dayjs().format(),
        //                 userId,
        //             }
        //             newPreferredTimeRanges.push(newPreferredTimeRange)
        //         }
        //     } else {
        //         const newPreferredTimeRange: PreferredTimeRangeType = {
        //             id: uuid(),
        //             eventId,
        //             startTime: timepreference?.timeRange?.startTime,
        //             endTime: timepreference?.timeRange?.endTime,
        //             updatedAt: dayjs().format(),
        //             createdDate: dayjs().format(),
        //             userId,
        //         }
        //         newPreferredTimeRanges.push(newPreferredTimeRange)
        //     }
        // }
        // // create new reminders for updated event
        // const remindersToUpdateEventId: ReminderType[] = []
        // if (body?.reminders?.length > 0) {
        //     const newReminders: ReminderType[] = body?.reminders.map(r => ({
        //         id: uuid(),
        //         userId,
        //         eventId,
        //         timezone,
        //         minutes: r,
        //         useDefault: false,
        //         updatedAt: dayjs().format(),
        //         createdDate: dayjs().format(),
        //         deleted: false,
        //     }))
        //     remindersToUpdateEventId.push(...newReminders)
        // }
        // // patchGoogleEvent
        // const startDateTime = startDate ? dayjs(startDate).tz(timezone).format() : oldEvent?.startDate
        // const endDateTime = (startDateTime && duration) ? dayjs(startDateTime).tz(timezone).add(duration, 'minute').format()
        //     : oldEvent?.endDate
        // const eventToUpsertLocal: EventType = {
        //     ...oldEvent,
        //     id: eventId,
        //     userId,
        //     timezone,
        //     isPreEvent: false,
        //     isPostEvent: false,
        //     updatedAt: dayjs().format(),
        // }
        // if (body?.allDay) {
        //     eventToUpsertLocal.allDay = body?.allDay
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
        // if (body?.description || body?.title) {
        //     eventToUpsertLocal.notes = body?.description || body?.title
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
        // if ((conference as ConferenceType)?.id) {
        //     eventToUpsertLocal.conferenceId = (conference as ConferenceType)?.id
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
        //         byMonthDay: (body?.recur as RecurrenceRuleType)?.byMonthDay,
        //     }
        // }
        // const googleReminder: GoogleReminderType = {
        //     overrides: remindersToUpdateEventId?.map(r => ({ method: 'email', minutes: r?.minutes })),
        //     useDefault: false,
        // }
        // await patchGoogleEvent(
        //     userId,
        //     oldEvent?.calendarId,
        //     eventToUpsertLocal?.eventId,
        //     calIntegration?.clientType,
        //     eventToUpsertLocal?.endDate,
        //     eventToUpsertLocal?.startDate,
        //     eventToUpsertLocal?.conferenceId ? 1 : 0,
        //     undefined,
        //     eventToUpsertLocal?.sendUpdates,
        //     eventToUpsertLocal?.anyoneCanAddSelf,
        //     body?.attendees?.map(a => ({ email: a?.email })),
        //     (conference as ConferenceType)?.id ? {
        //         type: (conference as ConferenceType)?.app === 'zoom' ? 'addOn' : 'hangoutsMeet',
        //         name: (conference as ConferenceType)?.name,
        //         conferenceId: (conference as ConferenceType)?.id,
        //         entryPoints: (conference as ConferenceType)?.entryPoints,
        //         createRequest: (conference as ConferenceType)?.app === 'google' ? {
        //             requestId: (conference as ConferenceType)?.requestId,
        //             conferenceSolutionKey: {
        //                 type: 'hangoutsMeet',
        //             }
        //         } : undefined,
        //     } : undefined,
        //     eventToUpsertLocal?.summary,
        //     eventToUpsertLocal?.notes,
        //     eventToUpsertLocal?.timezone,
        //     undefined,
        //     undefined,
        //     undefined,
        //     eventToUpsertLocal?.guestsCanInviteOthers,
        //     eventToUpsertLocal?.guestsCanModify,
        //     eventToUpsertLocal?.guestsCanSeeOtherGuests,
        //     eventToUpsertLocal?.originalStartDate,
        //     undefined,
        //     recur,
        //     remindersToUpdateEventId?.length > 0 ? googleReminder : undefined,
        //     undefined,
        //     undefined,
        //     eventToUpsertLocal?.transparency,
        //     eventToUpsertLocal?.visibility,
        //     undefined,
        //     undefined,
        //     undefined,
        //     undefined,
        //     undefined,
        //     undefined,
        //     'default',
        //     body?.location,
        //     undefined,
        // )
        // // add buffer time
        // // add buffer time if any
        // if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
        //     const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime)
        //     if (returnValues?.afterEvent) {
        //         const googleResValue: GoogleResType = await createGoogleEvent(
        //             userId,
        //             oldEvent?.calendarId,
        //             calIntegration?.clientType,
        //             returnValues?.afterEvent?.id,
        //             returnValues?.afterEvent?.endDate,
        //             returnValues?.afterEvent?.startDate,
        //             0,
        //             undefined,
        //             returnValues?.afterEvent?.sendUpdates,
        //             returnValues?.afterEvent?.anyoneCanAddSelf,
        //             undefined,
        //             undefined,
        //             returnValues?.afterEvent?.title,
        //             returnValues?.afterEvent?.notes,
        //             timezone,
        //             undefined,
        //             undefined,
        //             undefined,
        //             returnValues?.afterEvent?.guestsCanInviteOthers,
        //             returnValues?.afterEvent?.guestsCanModify,
        //             returnValues?.afterEvent?.guestsCanSeeOtherGuests,
        //             returnValues?.afterEvent?.originalStartDate,
        //             undefined,
        //             recur,
        //             undefined,
        //             undefined,
        //             undefined,
        //             returnValues?.afterEvent?.transparency,
        //             returnValues?.afterEvent?.visibility,
        //             undefined,
        //             undefined,
        //             undefined,
        //             undefined,
        //             undefined,
        //             undefined,
        //             'default',
        //             undefined,
        //             undefined,
        //         )
        //         returnValues.afterEvent.id = googleResValue.id
        //         returnValues.afterEvent.eventId = googleResValue.googleEventId
        //         returnValues.newEvent.postEventId = returnValues.afterEvent.id
        //     }
        //     if (returnValues?.beforeEvent) {
        //         const googleResValue: GoogleResType = await createGoogleEvent(
        //             userId,
        //             oldEvent?.calendarId,
        //             calIntegration?.clientType,
        //             returnValues?.beforeEvent?.id,
        //             returnValues?.beforeEvent?.endDate,
        //             returnValues?.beforeEvent?.startDate,
        //             0,
        //             undefined,
        //             returnValues?.beforeEvent?.sendUpdates,
        //             returnValues?.beforeEvent?.anyoneCanAddSelf,
        //             undefined,
        //             undefined,
        //             returnValues?.beforeEvent?.title,
        //             returnValues?.beforeEvent?.notes,
        //             timezone,
        //             undefined,
        //             undefined,
        //             undefined,
        //             returnValues?.beforeEvent?.guestsCanInviteOthers,
        //             returnValues?.beforeEvent?.guestsCanModify,
        //             returnValues?.beforeEvent?.guestsCanSeeOtherGuests,
        //             returnValues?.beforeEvent?.originalStartDate,
        //             undefined,
        //             recur,
        //             undefined,
        //             undefined,
        //             undefined,
        //             returnValues?.beforeEvent?.transparency,
        //             returnValues?.beforeEvent?.visibility,
        //             undefined,
        //             undefined,
        //             undefined,
        //             undefined,
        //             undefined,
        //             undefined,
        //             'default',
        //             undefined,
        //             undefined,
        //         )
        //         returnValues.beforeEvent.id = googleResValue.id
        //         returnValues.beforeEvent.eventId = googleResValue.googleEventId
        //         returnValues.newEvent.preEventId = returnValues.afterEvent.id
        //     }
        //     // insert events
        //     await upsertEvents([returnValues.newEvent, returnValues?.afterEvent, returnValues?.beforeEvent]?.filter(e => !!e))
        // } else {
        //     // insert events
        //     await upsertEvents([eventToUpsertLocal])
        // }
        // // update reminders
        // remindersToUpdateEventId?.forEach(r => ({ ...r, eventId: oldEvent?.id }))
        // // update timePreferences
        // newPreferredTimeRanges?.forEach(pt => ({ ...pt, eventId: oldEvent?.id }))
        // // insert reminders
        // if (remindersToUpdateEventId?.length > 0) {
        //     await insertReminders(remindersToUpdateEventId)
        // }
        // // insert time preferences
        // if (newPreferredTimeRanges?.length > 0) {
        //     await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges)
        // }
        // // add training for time preferences and priority
        // // convert to vector for search
        // if ((newPreferredTimeRanges?.length > 0) || body?.priority > 1) {
        //     const searchVector = await convertEventTitleToOpenAIVector(body?.title)
        //     // train event
        //     await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, userId)
        // }
        // // update attendees for event Id
        // await upsertAttendeesforEvent(attendees)
        // // success response
        // response.query = 'completed'
        // return response
    }
    catch (e) {
        console.log(e, ' unable to update meeting');
    }
};
export const processEditEventMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
    try {
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
        let startDate = searchBoundary.startDate;
        let endDate = searchBoundary.endDate;
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
        const eventStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.relativeTimeFromNow);
        // get default values
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
            const recurEndDate = extrapolateStartDateFromJSONData(currentTime, timezone, dateJSONBody?.recur?.endDate?.year ||
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
                    messageHistoryObject?.prevDateJsonBody?.recur?.frequency ||
                    messageHistoryObject?.prevJsonBody?.params?.recurrence?.frequency ||
                    jsonBody?.params?.recurrence?.frequency,
                interval: dateJSONBody?.recur?.interval ||
                    messageHistoryObject?.prevDateJsonBody?.recur?.interval ||
                    messageHistoryObject?.prevDateJsonBody?.recur?.frequency ||
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
            attendees: jsonBody?.params?.attendees ||
                messageHistoryObject?.prevJsonBody?.params?.attendees,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description ||
                jsonBody?.params?.notes ||
                messageHistoryObject?.prevJsonBody?.params?.description ||
                messageHistoryObject?.prevJsonBody?.params?.notes,
            conferenceApp: jsonBody?.params?.conference?.app ||
                messageHistoryObject?.prevJsonBody?.params?.conference?.app,
            startDate: jsonBody?.params?.startTime ||
                messageHistoryObject?.prevJsonBody?.params?.startTime ||
                eventStartDate,
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
            visibility: jsonBody?.params?.visibility ||
                messageHistoryObject?.prevJsonBody?.params?.visibility,
            isFollowUp: jsonBody?.params?.isFollowUp ||
                messageHistoryObject?.prevJsonBody?.params?.isFollowUp,
            isBreak: jsonBody?.params?.isBreak ||
                messageHistoryObject?.prevJsonBody?.params?.isBreak,
            allDay: dateJSONBody?.allDay || messageHistoryObject?.prevDateJsonBody?.allDay,
        };
        if (recurObject?.frequency) {
            newBody.recur = recurObject;
        }
        // validate for missing fields
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'editEvent',
        };
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
        if (prevBody.isFollowUp === undefined) {
            prevBody.isFollowUp = newBody?.isFollowUp;
        }
        if (prevBody.isBreak === undefined) {
            prevBody.isBreak = newBody?.isBreak;
        }
        if (prevBody.allDay === undefined) {
            prevBody.allDay = newBody?.allDay;
        }
        if (!prevBody?.recur) {
            prevBody.recur = newBody?.recur;
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
        if (!prevBody?.startDate && !day && !isoWeekday) {
            response.query = 'missing_fields';
            missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0]);
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
        if (!prevBody?.startDate &&
            hour === null &&
            minute === null &&
            !startTime) {
            response.query = 'missing_fields';
            missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1]);
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
        // get info of contacts without emails provided and assign values
        const newAttendees = [];
        for (const a of newBody?.attendees) {
            if (!a?.email) {
                const contact = await getContactByNameWithUserId(userId, a?.name);
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
                    response.prevDataExtra = {
                        searchBoundary: {
                            startDate: prevStartDate,
                            endDate: prevEndDate,
                        },
                    };
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
        const response2 = await finalStepEditEvent(prevBody, defaultMeetingPreferences, prevStartDate, prevEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to edit event missing fields returned');
    }
};
export const editEventControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let editEventRes = {
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
                editEventRes = await processEditEventPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                editEventRes = await processEditEventMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (editEventRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, editEventRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (editEventRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, editEventRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = editEventRes?.data;
            messageHistoryObject.prevData = editEventRes?.prevData;
            messageHistoryObject.prevDataExtra = editEventRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = editEventRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = editEventRes?.prevJsonBody;
        }
        else if (editEventRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to edit event control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiwrQkFBK0IsRUFDL0IsaUJBQWlCLEVBQ2pCLCtCQUErQixFQUMvQixpQkFBaUIsRUFDakIsaUJBQWlCLEVBQ2pCLHVCQUF1QixFQUN2QixrQkFBa0IsRUFDbEIsaUJBQWlCLEVBQ2pCLHNCQUFzQixFQUN0QixpQkFBaUIsRUFDakIsbUJBQW1CLEVBQ25CLGdDQUFnQyxFQUNoQyw2QkFBNkIsRUFDN0IsbURBQW1ELEVBQ25ELHFEQUFxRCxFQUNyRCxnQkFBZ0IsRUFDaEIsNkJBQTZCLEVBQzdCLDZCQUE2QixFQUM3QiwwQ0FBMEMsRUFDMUMsNEJBQTRCLEVBQzVCLG9CQUFvQixFQUNwQiwwQkFBMEIsRUFDMUIsc0JBQXNCLEVBQ3RCLDJCQUEyQixFQUMzQixlQUFlLEVBQ2YsZUFBZSxFQUNmLGdCQUFnQixFQUNoQixvQ0FBb0MsRUFDcEMsaUJBQWlCLEVBQ2pCLHVCQUF1QixFQUN2QixnQkFBZ0IsRUFDaEIsWUFBWSxHQUNiLE1BQU0sd0JBQXdCLENBQUM7QUFPaEMsT0FBTyxFQUFFLG1DQUFtQyxFQUFFLE1BQU0sK0JBQStCLENBQUM7QUFDcEYsT0FBTyxFQUFFLEtBQUssRUFBRSxNQUFNLGlDQUFpQyxDQUFDO0FBQ3hELE9BQU8sY0FBYyxNQUFNLGtCQUFrQixDQUFDO0FBQzlDLE9BQU8sRUFBRSxFQUFFLElBQUksSUFBSSxFQUFFLE1BQU0sTUFBTSxDQUFDO0FBSWxDLE9BQU8sRUFBRSxhQUFhLEVBQUUsTUFBTSx1Q0FBdUMsQ0FBQztBQUN0RSxPQUFPLEVBQUUsa0JBQWtCLEVBQUUsTUFBTSx1QkFBdUIsQ0FBQztBQUMzRCxPQUFPLEVBQUUscUNBQXFDLEVBQUUsTUFBTSxzQ0FBc0MsQ0FBQztBQVU3RixPQUFPLEVBQUUsaUNBQWlDLEVBQUUsTUFBTSx3Q0FBd0Ms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SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsOENBQThDLENBQUMsQ0FBQztJQUNqRSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgYWxsRXZlbnRXaXRoRGF0ZXNPcGVuU2VhcmNoLFxuICBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yLFxuICBjcmVhdGVHb29nbGVFdmVudCxcbiAgY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21FdmVudCxcbiAgY3JlYXRlUlJ1bGVTdHJpbmcsXG4gIGNyZWF0ZVpvb21NZWV0aW5nLFxuICBkZWxldGVDb25mZXJlbmNlR2l2ZW5JZCxcbiAgZGVsZXRlRXZlbnRHaXZlbklkLFxuICBkZWxldGVHb29nbGVFdmVudCxcbiAgZGVsZXRlUmVtaW5kZXJzV2l0aElkcyxcbiAgZGVsZXRlWm9vbU1lZXRpbmcsXG4gIGV2ZW50U2VhcmNoQm91bmRhcnksXG4gIGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhLFxuICBmaW5kQ29udGFjdEJ5RW1haWxHaXZlblVzZXJJZCxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyxcbiAgZ2VuZXJhdGVEYXRlVGltZSxcbiAgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lLFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdldENhbGVuZGFySW50ZWdyYXRpb25CeU5hbWUsXG4gIGdldENvbmZlcmVuY2VHaXZlbklkLFxuICBnZXRDb250YWN0QnlOYW1lV2l0aFVzZXJJZCxcbiAgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleSxcbiAgZ2V0VXNlckNvbnRhY3RJbmZvc0dpdmVuSWRzLFxuICBnZXRab29tQVBJVG9rZW4sXG4gIGluc2VydFJlbWluZGVycyxcbiAgcGF0Y2hHb29nbGVFdmVudCxcbiAgcHV0RGF0YUluVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoLFxuICB1cGRhdGVab29tTWVldGluZyxcbiAgdXBzZXJ0QXR0ZW5kZWVzZm9yRXZlbnQsXG4gIHVwc2VydENvbmZlcmVuY2UsXG4gIHVwc2VydEV2ZW50cyxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgRGF0ZVRpbWVKU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9EYXRlVGltZUpTT05KU09OVHlwZSc7XG5pbXBvcnQgVXNlcklucHV0VG9KU09OVHlwZSwge1xuICBNdXRhdGVkQ2FsZW5kYXJFeHRyYWN0ZWRKU09OQXR0ZW5kZWVUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Vc2VySW5wdXRUb0pTT05UeXBlJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCB7IEVkaXRFdmVudFR5cGUgfSBmcm9tICcuL3R5cGVzJztcbmltcG9ydCB7IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUdpdmVuVXNlcklkIH0gZnJvbSAnLi4vc2NoZWR1bGVNZWV0aW5nL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9kYXRlLXV0aWxzJztcbmltcG9ydCByZXF1aXJlZEZpZWxkcyBmcm9tICcuL3JlcXVpcmVkRmllbGRzJztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCB7IFJlbWluZGVyVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0dvb2dsZVR5cGVzJztcbmltcG9ydCB7IEdvb2dsZVJlbWluZGVyVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0dvb2dsZVJlbWluZGVyVHlwZSc7XG5pbXBvcnQgUHJlZmVycmVkVGltZVJhbmdlVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9QcmVmZXJyZWRUaW1lUmFuZ2VUeXBlJztcbmltcG9ydCB7IERheU9mV2Vla0VudW0gfSBmcm9tICcuLi9yZXNvbHZlQ29uZmxpY3RpbmdFdmVudHMvY29uc3RhbnRzJztcbmltcG9ydCB7IGdvb2dsZUNhbGVuZGFyTmFtZSB9IGZyb20gJ0BjaGF0L19saWJzL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkIH0gZnJvbSAnLi4vcmVtb3ZlQWxsUHJlZmVyZWRUaW1lcy9hcGktaGVscGVyJztcbmltcG9ydCB7IENvbmZlcmVuY2VUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQ29uZmVyZW5jZVR5cGUnO1xuaW1wb3J0IHtcbiAgRXZlbnRUeXBlLFxuICBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSxcbiAgUmVjdXJyZW5jZVJ1bGVUeXBlLFxuICBWaXNpYmlsaXR5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvRXZlbnRUeXBlJztcbmltcG9ydCB7IEF0dGVuZGVlVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0F0dGVuZGVlVHlwZSc7XG5pbXBvcnQgeyBHb29nbGVSZXNUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvR29vZ2xlUmVzVHlwZSc7XG5pbXBvcnQgeyB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQgfSBmcm9tICcuLi9yZXNvbHZlQ29uZmxpY3RpbmdFdmVudHMvYXBpLWhlbHBlcic7XG5pbXBvcnQgUmVzcG9uc2VBY3Rpb25UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1Jlc3BvbnNlQWN0aW9uVHlwZSc7XG5pbXBvcnQge1xuICBBc3Npc3RhbnRNZXNzYWdlVHlwZSxcbiAgU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcyc7XG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0NoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlJztcbmltcG9ydCB7IFNlYXJjaEJvdW5kYXJ5VHlwZSB9IGZyb20gJy4uL2RlbGV0ZVRhc2svdHlwZXMnO1xuXG5leHBvcnQgY29uc3QgZmluYWxTdGVwRWRpdEV2ZW50ID0gYXN5bmMgKFxuICBib2R5OiBFZGl0RXZlbnRUeXBlLFxuICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzOiBDaGF0TWVldGluZ1ByZWZlcmVuY2VzVHlwZSxcbiAgc3RhcnREYXRlOiBzdHJpbmcsXG4gIGVuZERhdGU6IHN0cmluZyxcbiAgcmVzcG9uc2U6IGFueVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gY29udmVydCB0byB2ZWN0b3IgZm9yIHNlYXJjaFxuICAgIGNvbnN0IHNlYXJjaFRpdGxlID0gYm9keT8ub2xkVGl0bGUgfHwgYm9keT8udGl0bGU7XG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcihzZWFyY2hUaXRsZSk7XG5cbiAgICAvLyAgYWxsRXZlbnRXaXRoRXZlbnRPcGVuU2VhcmNoXG4gICAgLy8gYWxsRXZlbnRPcGVuU2VhcmNoXG4gICAgaWYgKCFzdGFydERhdGUpIHtcbiAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIWVuZERhdGUpIHtcbiAgICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaChcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGVcbiAgICApO1xuXG4gICAgY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkO1xuXG4gICAgLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICBpZiAoIWlkKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50SWQgPSBpZDtcblxuICAgIC8vIGdldCBjbGllbnQgdHlwZVxuICAgIGNvbnN0IGNhbEludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZShcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIGdvb2dsZUNhbGVuZGFyTmFtZVxuICAgICk7XG5cbiAgICAvLyBkZWxldGUgb2xkIHJlbWluZGVyc1xuICAgIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGRlbGV0ZVJlbWluZGVyc1dpdGhJZHMoW2V2ZW50SWRdLCBib2R5Py51c2VySWQpO1xuICAgIH1cblxuICAgIC8vIGRlbGV0ZSBvbGQgdGltZSBwcmVmZXJlbmNlc1xuICAgIGlmIChib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQoZXZlbnRJZCk7XG4gICAgfVxuXG4gICAgLy8gZ2V0IG9sZCBldmVudFxuICAgIGNvbnN0IG9sZEV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShldmVudElkKTtcblxuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFvbGRFdmVudD8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gb2xkIGV2ZW50IGZvdW5kPyEnKTtcbiAgICB9XG5cbiAgICAvLyBpZiBubyBwcmlvcml0eSB1c2Ugb2xkXG4gICAgaWYgKCFib2R5Py5wcmlvcml0eSkge1xuICAgICAgYm9keS5wcmlvcml0eSA9IG9sZEV2ZW50LnByaW9yaXR5IHx8IDE7XG4gICAgfVxuXG4gICAgLy8gZmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWRcbiAgICAvLyBnZXQgYXR0ZW5kZWVzIHdpdGggcHJvdmlkZWQgZW1haWxzXG4gICAgY29uc3QgYVdpdGhFbWFpbHMgPSBib2R5Py5hdHRlbmRlZXM/LmZpbHRlcigoYSkgPT4gISFhPy5lbWFpbCk7XG5cbiAgICBjb25zdCBhV2l0aENvbnRhY3RJbmZvcyA9IGF3YWl0IGdldFVzZXJDb250YWN0SW5mb3NHaXZlbklkcyhcbiAgICAgIGFXaXRoRW1haWxzPy5tYXAoKGEpID0+IGE/LmVtYWlsKVxuICAgICk7XG5cbiAgICBjb25zdCBhdHRlbmRlZXNGcm9tRXh0cmFjdGVkSlNPTiA9IGJvZHk/LmF0dGVuZGVlcyB8fCBbXTtcbiAgICBjb25zdCBhdHRlbmRlZXM6IEF0dGVuZGVlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGEgb2YgYXR0ZW5kZWVzRnJvbUV4dHJhY3RlZEpTT04pIHtcbiAgICAgIGNvbnN0IGNvbnRhY3QgPSBhd2FpdCBmaW5kQ29udGFjdEJ5RW1haWxHaXZlblVzZXJJZChcbiAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICBhLmVtYWlsXG4gICAgICApO1xuICAgICAgY29uc3QgdXNlcklkRm91bmQgPSBhV2l0aENvbnRhY3RJbmZvcz8uZmluZCgoYikgPT4gYj8uaWQgPT09IGE/LmVtYWlsKTtcblxuICAgICAgY29uc3QgYXR0ZW5kZWU6IEF0dGVuZGVlVHlwZSA9IHtcbiAgICAgICAgaWQ6IHVzZXJJZEZvdW5kPy51c2VySWQgfHwgdXVpZCgpLFxuICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgbmFtZTpcbiAgICAgICAgICBhPy5uYW1lIHx8XG4gICAgICAgICAgY29udGFjdD8ubmFtZSB8fFxuICAgICAgICAgIGAke2NvbnRhY3Q/LmZpcnN0TmFtZX0gJHtjb250YWN0Py5sYXN0TmFtZX1gLFxuICAgICAgICBjb250YWN0SWQ6IGNvbnRhY3Q/LmlkLFxuICAgICAgICBlbWFpbHM6IFt7IHByaW1hcnk6IHRydWUsIHZhbHVlOiBhPy5lbWFpbCB9XSxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICB9O1xuXG4gICAgICBhdHRlbmRlZXMucHVzaChhdHRlbmRlZSk7XG4gICAgfVxuXG4gICAgLy8gdGFrZSBjYXJlIG9mIHJlY3VycmVuY2VcbiAgICBjb25zdCByZWN1ciA9IGNyZWF0ZVJSdWxlU3RyaW5nKFxuICAgICAgYm9keT8ucmVjdXI/LmZyZXF1ZW5jeSxcbiAgICAgIGJvZHk/LnJlY3VyPy5pbnRlcnZhbCxcbiAgICAgIGJvZHk/LnJlY3VyPy5ieVdlZWtEYXksXG4gICAgICBib2R5Py5yZWN1cj8ub2NjdXJyZW5jZSxcbiAgICAgIGJvZHk/LnJlY3VyPy5lbmREYXRlLFxuICAgICAgKGJvZHk/LnJlY3VyIGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmJ5TW9udGhEYXlcbiAgICApO1xuXG4gICAgbGV0IGNvbmZlcmVuY2U6IENvbmZlcmVuY2VUeXBlIHwge30gPSB7fTtcblxuICAgIC8vIGNvbmZlcmVuY2U6IGNyZWF0ZSAvIHVwZGF0ZSBhbmQgc3RvcmUgaW4gZGJcbiAgICBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCAmJiAhb2xkRXZlbnQuY29uZmVyZW5jZUlkKSB7XG4gICAgICAvLyBjcmVhdGUgY29uZmVyZW5jZSBvYmplY3RcbiAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbihib2R5Py51c2VySWQpO1xuXG4gICAgICBjb25mZXJlbmNlID1cbiAgICAgICAgem9vbVRva2VuICYmIGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJ1xuICAgICAgICAgID8ge31cbiAgICAgICAgICA6IHtcbiAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgICAgICBhcHA6ICdnb29nbGUnLFxuICAgICAgICAgICAgICBuYW1lOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgICAgICAgICAgICBub3RlczogYm9keT8uZGVzY3JpcHRpb24gfHwgYm9keT8udGl0bGUsXG4gICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgICAgICAgICB9O1xuXG4gICAgICBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCA9PT0gJ3pvb20nKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKHpvb21Ub2tlbiwgJyB6b29tVG9rZW4gaW5zaWRlIGlmICh6b29tVG9rZW4pJyk7XG5cbiAgICAgICAgY29uc3Qgem9vbU9iamVjdCA9IGF3YWl0IGNyZWF0ZVpvb21NZWV0aW5nKFxuICAgICAgICAgIHpvb21Ub2tlbixcbiAgICAgICAgICBib2R5Py5zdGFydERhdGUsXG4gICAgICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgICAgICAgYm9keT8udGl0bGUsXG4gICAgICAgICAgYm9keT8uZHVyYXRpb24sXG4gICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5wcmltYXJ5RW1haWwsXG4gICAgICAgICAgYm9keT8uYXR0ZW5kZWVzPy5tYXAoKGEpID0+IGE/LmVtYWlsKSxcbiAgICAgICAgICBib2R5Py5yZWN1ciBhcyBhbnlcbiAgICAgICAgKTtcblxuICAgICAgICBjb25zb2xlLmxvZyh6b29tT2JqZWN0LCAnIHpvb21PYmplY3QgYWZ0ZXIgY3JlYXRlWm9vbU1lZXRpbmcnKTtcblxuICAgICAgICBpZiAoem9vbU9iamVjdCkge1xuICAgICAgICAgIGNvbmZlcmVuY2UgPSB7XG4gICAgICAgICAgICBpZDogYCR7em9vbU9iamVjdD8uaWR9YCxcbiAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmlkLFxuICAgICAgICAgICAgYXBwOiAnem9vbScsXG4gICAgICAgICAgICBuYW1lOiB6b29tT2JqZWN0Py5hZ2VuZGEsXG4gICAgICAgICAgICBub3Rlczogem9vbU9iamVjdD8uYWdlbmRhLFxuICAgICAgICAgICAgam9pblVybDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICBzdGFydFVybDogem9vbU9iamVjdD8uc3RhcnRfdXJsLFxuICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgICAgIGVudHJ5UG9pbnRzOiBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBlbnRyeVBvaW50VHlwZTogJ3ZpZGVvJyxcbiAgICAgICAgICAgICAgICBsYWJlbDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICAgICAgcGFzc3dvcmQ6IHpvb21PYmplY3Q/LnBhc3N3b3JkLFxuICAgICAgICAgICAgICAgIHVyaTogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0gYXMgQ29uZmVyZW5jZVR5cGU7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgLy8gaW5zZXJ0IG5ldyBjb25mZXJlbmNlXG4gICAgICBhd2FpdCB1cHNlcnRDb25mZXJlbmNlKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpO1xuICAgIH0gZWxzZSBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCAmJiBvbGRFdmVudC5jb25mZXJlbmNlSWQpIHtcbiAgICAgIC8vIGdldCBvbGQgY29uZmVyZW5jZSBvYmplY3RcbiAgICAgIGNvbnN0IG9sZENvbmZlcmVuY2UgPSBhd2FpdCBnZXRDb25mZXJlbmNlR2l2ZW5JZChvbGRFdmVudD8uY29uZmVyZW5jZUlkKTtcbiAgICAgIC8vIGNyZWF0ZSBjb25mZXJlbmNlIG9iamVjdFxuICAgICAgY29uc3Qgem9vbVRva2VuID0gYXdhaXQgZ2V0Wm9vbUFQSVRva2VuKGJvZHk/LnVzZXJJZCk7XG5cbiAgICAgIC8vIHVwZGF0ZVpvb21NZWV0aW5nXG4gICAgICBjb25mZXJlbmNlID1cbiAgICAgICAgem9vbVRva2VuICYmIGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJ1xuICAgICAgICAgID8ge31cbiAgICAgICAgICA6IHtcbiAgICAgICAgICAgICAgLi4ub2xkQ29uZmVyZW5jZSxcbiAgICAgICAgICAgICAgaWQ6IG9sZEV2ZW50Py5jb25mZXJlbmNlSWQsXG4gICAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgICBjYWxlbmRhcklkOiBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgYXBwOiAnZ29vZ2xlJyxcbiAgICAgICAgICAgICAgbmFtZTogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAgICAgICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlLFxuICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgICAgICAgICAgfTtcblxuICAgICAgaWYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09IG9sZENvbmZlcmVuY2UuYXBwKSB7XG4gICAgICAgIGNvbnNvbGUubG9nKHpvb21Ub2tlbiwgJyB6b29tVG9rZW4gaW5zaWRlIGlmICh6b29tVG9rZW4pJyk7XG5cbiAgICAgICAgaWYgKHpvb21Ub2tlbiAmJiBib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbScpIHtcbiAgICAgICAgICBhd2FpdCB1cGRhdGVab29tTWVldGluZyhcbiAgICAgICAgICAgIHpvb21Ub2tlbixcbiAgICAgICAgICAgIHBhcnNlSW50KG9sZEV2ZW50Py5jb25mZXJlbmNlSWQsIDEwKSxcbiAgICAgICAgICAgIGJvZHk/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgICAgYm9keT8udGl0bGUgfHwgYm9keT8uZGVzY3JpcHRpb24sXG4gICAgICAgICAgICBib2R5Py5kdXJhdGlvbiB8fCBvbGRFdmVudD8uZHVyYXRpb24sXG4gICAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucHJpbWFyeUVtYWlsLFxuICAgICAgICAgICAgYXR0ZW5kZWVzPy5sZW5ndGggPiAwXG4gICAgICAgICAgICAgID8gYXR0ZW5kZWVzPy5tYXAoKGEpID0+IGE/LmVtYWlscz8uWzBdPy52YWx1ZSlcbiAgICAgICAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgICBib2R5Py5yZWN1ciBhcyBhbnlcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uZmVyZW5jZSA9IHtcbiAgICAgICAgICAgIC4uLm9sZENvbmZlcmVuY2UsXG4gICAgICAgICAgICBpZDogb2xkQ29uZmVyZW5jZT8uaWQsXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgICAgYXBwOiAnem9vbScsXG4gICAgICAgICAgICBuYW1lOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgICAgICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uIHx8IG9sZEV2ZW50Py5ub3RlcyxcbiAgICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgfSBhcyBDb25mZXJlbmNlVHlwZTtcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25mZXJlbmNlID0ge1xuICAgICAgICAgICAgLi4ub2xkQ29uZmVyZW5jZSxcbiAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICAgICAgICBhcHA6ICdnb29nbGUnLFxuICAgICAgICAgICAgbmFtZTogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgICAgICAgfTtcbiAgICAgICAgfVxuXG4gICAgICAgIC8vIGluc2VydCBuZXcgY29uZmVyZW5jZVxuICAgICAgICBhd2FpdCB1cHNlcnRDb25mZXJlbmNlKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpO1xuICAgICAgfSBlbHNlIGlmIChib2R5Py5jb25mZXJlbmNlQXBwICE9PSBvbGRDb25mZXJlbmNlLmFwcCkge1xuICAgICAgICAvLyBjcmVhdGUgY29uZmVyZW5jZSBvYmplY3RcbiAgICAgICAgY29uc3Qgem9vbVRva2VuID0gYXdhaXQgZ2V0Wm9vbUFQSVRva2VuKGJvZHk/LnVzZXJJZCk7XG5cbiAgICAgICAgY29uZmVyZW5jZSA9XG4gICAgICAgICAgem9vbVRva2VuICYmIGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJ1xuICAgICAgICAgICAgPyB7fVxuICAgICAgICAgICAgOiB7XG4gICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgICAgICBjYWxlbmRhcklkOiBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgICBhcHA6ICdnb29nbGUnLFxuICAgICAgICAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgICAgICAgICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlLFxuICAgICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgICAgICAgICAgIH07XG5cbiAgICAgICAgaWYgKHpvb21Ub2tlbiAmJiBib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbScpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyh6b29tVG9rZW4sICcgem9vbVRva2VuIGluc2lkZSBpZiAoem9vbVRva2VuKScpO1xuXG4gICAgICAgICAgY29uc3Qgem9vbU9iamVjdCA9IGF3YWl0IGNyZWF0ZVpvb21NZWV0aW5nKFxuICAgICAgICAgICAgem9vbVRva2VuLFxuICAgICAgICAgICAgYm9keT8uc3RhcnREYXRlLFxuICAgICAgICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgICAgICAgICBib2R5Py50aXRsZSB8fCBib2R5Py5kZXNjcmlwdGlvbixcbiAgICAgICAgICAgIGJvZHk/LmR1cmF0aW9uLFxuICAgICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnByaW1hcnlFbWFpbCxcbiAgICAgICAgICAgIGJvZHk/LmF0dGVuZGVlcz8ubWFwKChhKSA9PiBhPy5lbWFpbCksXG4gICAgICAgICAgICBib2R5Py5yZWN1ciBhcyBhbnlcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc29sZS5sb2coem9vbU9iamVjdCwgJyB6b29tT2JqZWN0IGFmdGVyIGNyZWF0ZVpvb21NZWV0aW5nJyk7XG5cbiAgICAgICAgICBpZiAoem9vbU9iamVjdCkge1xuICAgICAgICAgICAgY29uZmVyZW5jZSA9IHtcbiAgICAgICAgICAgICAgaWQ6IGAke3pvb21PYmplY3Q/LmlkfWAsXG4gICAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgICAgICBjYWxlbmRhcklkOiBvbGRFdmVudD8uaWQsXG4gICAgICAgICAgICAgIGFwcDogJ3pvb20nLFxuICAgICAgICAgICAgICBuYW1lOiB6b29tT2JqZWN0Py5hZ2VuZGEsXG4gICAgICAgICAgICAgIG5vdGVzOiB6b29tT2JqZWN0Py5hZ2VuZGEsXG4gICAgICAgICAgICAgIGpvaW5Vcmw6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgICAgICAgICAgICBzdGFydFVybDogem9vbU9iamVjdD8uc3RhcnRfdXJsLFxuICAgICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgICBlbnRyeVBvaW50czogW1xuICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgIGVudHJ5UG9pbnRUeXBlOiAndmlkZW8nLFxuICAgICAgICAgICAgICAgICAgbGFiZWw6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgICAgICAgICAgICAgICAgcGFzc3dvcmQ6IHpvb21PYmplY3Q/LnBhc3N3b3JkLFxuICAgICAgICAgICAgICAgICAgdXJpOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICBdLFxuICAgICAgICAgICAgfSBhcyBDb25mZXJlbmNlVHlwZTtcbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICAvLyBkZWxldGUgb2xkIGNvbmZlcmVuY2VcbiAgICAgICAgYXdhaXQgZGVsZXRlQ29uZmVyZW5jZUdpdmVuSWQob2xkQ29uZmVyZW5jZT8uaWQpO1xuICAgICAgICBpZiAob2xkQ29uZmVyZW5jZS5hcHAgPT09ICd6b29tJykge1xuICAgICAgICAgIGF3YWl0IGRlbGV0ZVpvb21NZWV0aW5nKHpvb21Ub2tlbiwgcGFyc2VJbnQob2xkQ29uZmVyZW5jZS5pZCwgMTApKTtcbiAgICAgICAgfVxuICAgICAgICAvLyBpbnNlcnQgbmV3IGNvbmZlcmVuY2VcbiAgICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKTtcbiAgICAgIH1cbiAgICB9XG4gICAgLy8gaWYgZXhpc3RpbmcgYnVmZmVyIHRpbWVzXG4gICAgLy8gZGVsZXRlIG9sZCBhbmQgY3JlYXRlIG5ldyBvbmVzIGxhdGVyIG9uXG4gICAgaWYgKFxuICAgICAgKG9sZEV2ZW50Py5wcmVFdmVudElkICYmIGJvZHk/LmJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50KSB8fFxuICAgICAgKG9sZEV2ZW50Py5wb3N0RXZlbnRJZCAmJiBib2R5Py5idWZmZXJUaW1lPy5hZnRlckV2ZW50KVxuICAgICkge1xuICAgICAgLy8gZGVsZXRlIGJ1ZmZlcmUgdGltZXMgaWYgYW55XG5cbiAgICAgIGlmIChvbGRFdmVudD8ucHJlRXZlbnRJZCkge1xuICAgICAgICBjb25zdCBwcmVFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkob2xkRXZlbnQ/LnByZUV2ZW50SWQpO1xuICAgICAgICBhd2FpdCBkZWxldGVHb29nbGVFdmVudChcbiAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgcHJlRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICAgICAgcHJlRXZlbnQ/LmV2ZW50SWQsXG4gICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGVcbiAgICAgICAgKTtcbiAgICAgICAgYXdhaXQgZGVsZXRlRXZlbnRHaXZlbklkKG9sZEV2ZW50Py5wcmVFdmVudElkKTtcbiAgICAgIH1cblxuICAgICAgaWYgKG9sZEV2ZW50Py5wb3N0RXZlbnRJZCkge1xuICAgICAgICBjb25zdCBwb3N0RXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KG9sZEV2ZW50Py5wb3N0RXZlbnRJZCk7XG4gICAgICAgIGF3YWl0IGRlbGV0ZUdvb2dsZUV2ZW50KFxuICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICBwb3N0RXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICAgICAgcG9zdEV2ZW50Py5ldmVudElkLFxuICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlXG4gICAgICAgICk7XG4gICAgICAgIGF3YWl0IGRlbGV0ZUV2ZW50R2l2ZW5JZChvbGRFdmVudD8ucG9zdEV2ZW50SWQpO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIGNyZWF0ZSBuZXcgdGltZSBwcmVmZXJlbmNlcyBhbmQgcHJpb3JpdHlcbiAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgdGltZXByZWZlcmVuY2Ugb2YgYm9keT8udGltZVByZWZlcmVuY2VzKSB7XG4gICAgICBpZiAodGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGZvciAoY29uc3QgZGF5T2ZXZWVrIG9mIHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaykge1xuICAgICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICBldmVudElkLFxuICAgICAgICAgICAgZGF5T2ZXZWVrOiBEYXlPZldlZWtFbnVtW2RheU9mV2Vla10sXG4gICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICAgIH07XG5cbiAgICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgfTtcblxuICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBjcmVhdGUgbmV3IHJlbWluZGVycyBmb3IgdXBkYXRlZCBldmVudFxuICAgIGNvbnN0IHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZDogUmVtaW5kZXJUeXBlW10gPSBbXTtcblxuICAgIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnN0IG5ld1JlbWluZGVyczogUmVtaW5kZXJUeXBlW10gPSBib2R5Py5yZW1pbmRlcnMubWFwKChyKSA9PiAoe1xuICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgdGltZXpvbmU6IGJvZHk/LnRpbWV6b25lLFxuICAgICAgICBtaW51dGVzOiByLFxuICAgICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICB9KSk7XG5cbiAgICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZC5wdXNoKC4uLm5ld1JlbWluZGVycyk7XG4gICAgfVxuXG4gICAgLy8gcGF0Y2hHb29nbGVFdmVudFxuICAgIGNvbnN0IHN0YXJ0RGF0ZVRpbWUgPSBzdGFydERhdGVcbiAgICAgID8gZGF5anMoc3RhcnREYXRlKS50eihib2R5Py50aW1lem9uZSkuZm9ybWF0KClcbiAgICAgIDogb2xkRXZlbnQ/LnN0YXJ0RGF0ZTtcbiAgICBjb25zdCBlbmREYXRlVGltZSA9XG4gICAgICBzdGFydERhdGVUaW1lICYmIGJvZHk/LmR1cmF0aW9uXG4gICAgICAgID8gZGF5anMoc3RhcnREYXRlVGltZSlcbiAgICAgICAgICAgIC50eihib2R5Py50aW1lem9uZSlcbiAgICAgICAgICAgIC5hZGQoYm9keT8uZHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgICAgLmZvcm1hdCgpXG4gICAgICAgIDogb2xkRXZlbnQ/LmVuZERhdGU7XG5cbiAgICBjb25zdCBldmVudFRvVXBzZXJ0TG9jYWw6IEV2ZW50VHlwZSA9IHtcbiAgICAgIC4uLm9sZEV2ZW50LFxuICAgICAgaWQ6IGV2ZW50SWQsXG4gICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgIHRpbWV6b25lOiBib2R5Py50aW1lem9uZSxcbiAgICAgIGlzUHJlRXZlbnQ6IGZhbHNlLFxuICAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIH07XG5cbiAgICBpZiAoYm9keT8uYWxsRGF5KSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuYWxsRGF5ID0gYm9keT8uYWxsRGF5O1xuICAgIH1cblxuICAgIGlmIChib2R5Py50aXRsZSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRpdGxlID0gYm9keT8udGl0bGU7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuc3VtbWFyeSA9IGJvZHk/LnRpdGxlO1xuICAgIH1cblxuICAgIGlmIChzdGFydERhdGUpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5zdGFydERhdGUgPSBkYXlqcyhzdGFydERhdGUpXG4gICAgICAgIC50eihib2R5Py50aW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGlmIChlbmREYXRlVGltZSAmJiBlbmREYXRlVGltZSAhPT0gb2xkRXZlbnQ/LmVuZERhdGUpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5lbmREYXRlID0gZGF5anMoc3RhcnREYXRlVGltZSlcbiAgICAgICAgLnR6KGJvZHk/LnRpbWV6b25lKVxuICAgICAgICAuYWRkKGJvZHk/LmR1cmF0aW9uLCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGlmIChib2R5Py5kdXJhdGlvbiAmJiBib2R5Py5kdXJhdGlvbiAhPT0gb2xkRXZlbnQ/LmR1cmF0aW9uKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuZHVyYXRpb24gPSBib2R5Py5kdXJhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8uaXNGb2xsb3dVcCkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmlzRm9sbG93VXAgPSBib2R5LmlzRm9sbG93VXA7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwubm90ZXMgPSBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8ucHJpb3JpdHkpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5wcmlvcml0eSA9IGJvZHkucHJpb3JpdHk7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRyYW5zcGFyZW5jeSA9IGJvZHkudHJhbnNwYXJlbmN5O1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eSA9IHRydWU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC52aXNpYmlsaXR5ID0gYm9keS52aXNpYmlsaXR5IGFzIFZpc2liaWxpdHlUeXBlO1xuICAgIH1cblxuICAgIGlmICgoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuY29uZmVyZW5jZUlkID0gKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZDtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRpbWVCbG9ja2luZyA9IGJvZHkuYnVmZmVyVGltZTtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcgPSB0cnVlO1xuICAgIH1cblxuICAgIGlmIChib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZSA9IHRydWU7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwubW9kaWZpYWJsZSA9IHRydWU7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkTW9kaWZpYWJsZSA9IHRydWU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFJlbWluZGVycyA9IHRydWU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnByaW9yaXR5ID4gMSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWwgPSB0cnVlO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLm1vZGlmaWFibGUgPSB0cnVlO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZE1vZGlmaWFibGUgPSB0cnVlO1xuICAgIH1cblxuICAgIGlmIChib2R5Py5kdXJhdGlvbikge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZER1cmF0aW9uID0gdHJ1ZTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8ubG9jYXRpb24pIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5sb2NhdGlvbiA9IHsgdGl0bGU6IGJvZHk/LmxvY2F0aW9uIH07XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnJlY3VyKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwucmVjdXJyZW5jZSA9IHJlY3VyO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnJlY3VycmVuY2VSdWxlID0ge1xuICAgICAgICBmcmVxdWVuY3k6IGJvZHk/LnJlY3VyPy5mcmVxdWVuY3ksXG4gICAgICAgIGludGVydmFsOiBib2R5Py5yZWN1cj8uaW50ZXJ2YWwsXG4gICAgICAgIGJ5V2Vla0RheTogYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAgICAgb2NjdXJyZW5jZTogYm9keT8ucmVjdXI/Lm9jY3VycmVuY2UsXG4gICAgICAgIGVuZERhdGU6IGJvZHk/LnJlY3VyPy5lbmREYXRlLFxuICAgICAgICBieU1vbnRoRGF5OiAoYm9keT8ucmVjdXIgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uYnlNb250aERheSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgZ29vZ2xlUmVtaW5kZXI6IEdvb2dsZVJlbWluZGVyVHlwZSA9IHtcbiAgICAgIG92ZXJyaWRlczogcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5tYXAoKHIpID0+ICh7XG4gICAgICAgIG1ldGhvZDogJ2VtYWlsJyxcbiAgICAgICAgbWludXRlczogcj8ubWludXRlcyxcbiAgICAgIH0pKSxcbiAgICAgIHVzZURlZmF1bHQ6IGZhbHNlLFxuICAgIH07XG5cbiAgICBhd2FpdCBwYXRjaEdvb2dsZUV2ZW50KFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmV2ZW50SWQsXG4gICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3RhcnREYXRlLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5jb25mZXJlbmNlSWQgPyAxIDogMCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc2VuZFVwZGF0ZXMsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICBib2R5Py5hdHRlbmRlZXM/Lm1hcCgoYSkgPT4gKHsgZW1haWw6IGE/LmVtYWlsIH0pKSxcbiAgICAgIChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uaWRcbiAgICAgICAgPyB7XG4gICAgICAgICAgICB0eXBlOlxuICAgICAgICAgICAgICAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmFwcCA9PT0gJ3pvb20nXG4gICAgICAgICAgICAgICAgPyAnYWRkT24nXG4gICAgICAgICAgICAgICAgOiAnaGFuZ291dHNNZWV0JyxcbiAgICAgICAgICAgIG5hbWU6IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8ubmFtZSxcbiAgICAgICAgICAgIGNvbmZlcmVuY2VJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZCxcbiAgICAgICAgICAgIGVudHJ5UG9pbnRzOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmVudHJ5UG9pbnRzLFxuICAgICAgICAgICAgY3JlYXRlUmVxdWVzdDpcbiAgICAgICAgICAgICAgKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5hcHAgPT09ICdnb29nbGUnXG4gICAgICAgICAgICAgICAgPyB7XG4gICAgICAgICAgICAgICAgICAgIHJlcXVlc3RJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5yZXF1ZXN0SWQsXG4gICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbktleToge1xuICAgICAgICAgICAgICAgICAgICAgIHR5cGU6ICdoYW5nb3V0c01lZXQnLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICAgIH1cbiAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnN1bW1hcnksXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lm5vdGVzLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50aW1lem9uZSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5Nb2RpZnksXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHJlY3VyLFxuICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwID8gZ29vZ2xlUmVtaW5kZXIgOiB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRyYW5zcGFyZW5jeSxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udmlzaWJpbGl0eSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgICdkZWZhdWx0JyxcbiAgICAgIGJvZHk/LmxvY2F0aW9uLFxuICAgICAgdW5kZWZpbmVkXG4gICAgKTtcblxuICAgIC8vIGFkZCBidWZmZXIgdGltZVxuICAgIC8vIGFkZCBidWZmZXIgdGltZSBpZiBhbnlcbiAgICBpZiAoYm9keT8uYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCB8fCBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCkge1xuICAgICAgY29uc3QgcmV0dXJuVmFsdWVzID0gY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21FdmVudChcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLFxuICAgICAgICBib2R5Py5idWZmZXJUaW1lXG4gICAgICApO1xuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50KSB7XG4gICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uaWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgIDAsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50aXRsZSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lm5vdGVzLFxuICAgICAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZWN1cixcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWRcbiAgICAgICAgKTtcblxuICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcbiAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnBvc3RFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQ7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50KSB7XG4gICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmlkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgIDAsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py50aXRsZSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAgICAgICBib2R5Py50aW1lem9uZSxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgcmVjdXIsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWRcbiAgICAgICAgKTtcblxuICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgcmV0dXJuVmFsdWVzLmJlZm9yZUV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucHJlRXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgfVxuXG4gICAgICAvLyBpbnNlcnQgZXZlbnRzXG4gICAgICBhd2FpdCB1cHNlcnRFdmVudHMoXG4gICAgICAgIFtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQsXG4gICAgICAgIF0/LmZpbHRlcigoZSkgPT4gISFlKVxuICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgLy8gaW5zZXJ0IGV2ZW50c1xuICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFtldmVudFRvVXBzZXJ0TG9jYWxdKTtcbiAgICB9XG5cbiAgICAvLyB1cGRhdGUgcmVtaW5kZXJzXG4gICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5mb3JFYWNoKChyKSA9PiAoeyAuLi5yLCBldmVudElkOiBvbGRFdmVudD8uaWQgfSkpO1xuXG4gICAgLy8gdXBkYXRlIHRpbWVQcmVmZXJlbmNlc1xuICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/LmZvckVhY2goKHB0KSA9PiAoeyAuLi5wdCwgZXZlbnRJZDogb2xkRXZlbnQ/LmlkIH0pKTtcblxuICAgIC8vIGluc2VydCByZW1pbmRlcnNcbiAgICBpZiAocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwKSB7XG4gICAgICBhd2FpdCBpbnNlcnRSZW1pbmRlcnMocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkKTtcbiAgICB9XG5cbiAgICAvLyBpbnNlcnQgdGltZSBwcmVmZXJlbmNlc1xuICAgIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcyk7XG4gICAgfVxuXG4gICAgLy8gYWRkIHRyYWluaW5nIGZvciB0aW1lIHByZWZlcmVuY2VzIGFuZCBwcmlvcml0eVxuICAgIC8vIGNvbnZlcnQgdG8gdmVjdG9yIGZvciBzZWFyY2hcbiAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCB8fCBib2R5Py5wcmlvcml0eSA+IDEpIHtcbiAgICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuXG4gICAgICAvLyB0cmFpbiBldmVudFxuICAgICAgYXdhaXQgcHV0RGF0YUluVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoKFxuICAgICAgICBldmVudElkLFxuICAgICAgICBzZWFyY2hWZWN0b3IsXG4gICAgICAgIGJvZHk/LnVzZXJJZFxuICAgICAgKTtcbiAgICB9XG5cbiAgICAvLyB1cGRhdGUgYXR0ZW5kZWVzIGZvciBldmVudCBJZFxuICAgIGF3YWl0IHVwc2VydEF0dGVuZGVlc2ZvckV2ZW50KGF0dGVuZGVlcyk7XG5cbiAgICAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICByZXNwb25zZS5kYXRhID0gJ2V2ZW50IHN1Y2Nlc3NmdWxseSBlZGl0ZWQnO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIGZpbmFsIHN0ZXAgZWRpdCBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0VkaXRFdmVudFBlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nXG4pOiBQcm9taXNlPFJlc3BvbnNlQWN0aW9uVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICBsZXQgZHVyYXRpb24gPSAwO1xuXG4gICAgY29uc3QgeWVhciA9IGRhdGVKU09OQm9keT8ueWVhcjtcbiAgICBjb25zdCBtb250aCA9IGRhdGVKU09OQm9keT8ubW9udGg7XG4gICAgY29uc3QgZGF5ID0gZGF0ZUpTT05Cb2R5Py5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheSA9IGRhdGVKU09OQm9keT8uaXNvV2Vla2RheTtcbiAgICBjb25zdCBob3VyID0gZGF0ZUpTT05Cb2R5Py5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZSA9IGRhdGVKU09OQm9keT8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZSA9IGRhdGVKU09OQm9keT8uc3RhcnRUaW1lO1xuXG4gICAgY29uc3QgZXZlbnRTdGFydERhdGUgPSBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB5ZWFyLFxuICAgICAgbW9udGgsXG4gICAgICBkYXksXG4gICAgICBpc29XZWVrZGF5LFxuICAgICAgaG91cixcbiAgICAgIG1pbnV0ZSxcbiAgICAgIHN0YXJ0VGltZSxcbiAgICAgIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICAvLyBnZXQgZGVmYXVsdCB2YWx1ZXNcbiAgICBjb25zdCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzID1cbiAgICAgIGF3YWl0IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUdpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgJiYgZGF0ZUpTT05Cb2R5Py5lbmRUaW1lKSB7XG4gICAgICAvLyBsaWtlbHkgc3RhcnQgdGltZSBhbHNvIHByZXNlbnRcblxuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUsICdISDptbScpO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKGRhdGVKU09OQm9keS5lbmRUaW1lLCAnSEg6bW0nKTtcblxuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgJiYganNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoanNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKTtcbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIHRha2UgY2FyZSBvZiBhbnkgcmVjdXJyaW5nIGRhdGVzXG4gICAgbGV0IHJlY3VyT2JqZWN0OiBSZWN1cnJlbmNlUnVsZVR5cGUgfCB7fSA9IHt9O1xuICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kpIHtcbiAgICAgIGNvbnN0IHJlY3VyRW5kRGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgICBjdXJyZW50VGltZSxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnllYXIsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1vbnRoLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5kYXksXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/Lmlzb1dlZWtkYXksXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LmhvdXIsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1pbnV0ZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uc3RhcnRUaW1lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgICApO1xuXG4gICAgICByZWN1ck9iamVjdCA9IHtcbiAgICAgICAgZnJlcXVlbmN5OlxuICAgICAgICAgIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUpIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZnJlcXVlbmN5LFxuICAgICAgICBpbnRlcnZhbDpcbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmludGVydmFsLFxuICAgICAgfTtcblxuICAgICAgaWYgKGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5V2Vla0RheSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieVdlZWtEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5V2Vla0RheTtcbiAgICAgIH1cblxuICAgICAgaWYgKGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXkpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlNb250aERheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheTtcbiAgICAgIH1cblxuICAgICAgaWYgKGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2UpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkub2NjdXJyZW5jZSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZTtcbiAgICAgIH1cblxuICAgICAgaWYgKHJlY3VyRW5kRGF0ZSB8fCBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmVuZERhdGUgPVxuICAgICAgICAgIHJlY3VyRW5kRGF0ZSB8fCBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IGJvZHk6IEVkaXRFdmVudFR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBvbGRUaXRsZToganNvbkJvZHk/LnBhcmFtcz8ub2xkVGl0bGUsXG4gICAgICBhdHRlbmRlZXM6IGpzb25Cb2R5Py5wYXJhbXM/LmF0dGVuZGVlcyxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgZHVyYXRpb24sXG4gICAgICBkZXNjcmlwdGlvbjoganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHwganNvbkJvZHk/LnBhcmFtcz8ubm90ZXMsXG4gICAgICBjb25mZXJlbmNlQXBwOiBqc29uQm9keT8ucGFyYW1zPy5jb25mZXJlbmNlPy5hcHAsXG4gICAgICBzdGFydERhdGU6IGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fCBldmVudFN0YXJ0RGF0ZSxcbiAgICAgIGJ1ZmZlclRpbWU6IGpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUsXG4gICAgICByZW1pbmRlcnM6IGpzb25Cb2R5Py5wYXJhbXM/LmFsYXJtcyxcbiAgICAgIHByaW9yaXR5OiBqc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSxcbiAgICAgIHRpbWVQcmVmZXJlbmNlczogZGF0ZUpTT05Cb2R5Py50aW1lUHJlZmVyZW5jZXMsXG4gICAgICBsb2NhdGlvbjoganNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24sXG4gICAgICB0cmFuc3BhcmVuY3k6IGpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6IGpzb25Cb2R5Py5wYXJhbXM/LnZpc2liaWxpdHksXG4gICAgICBpc0ZvbGxvd1VwOiBqc29uQm9keT8ucGFyYW1zPy5pc0ZvbGxvd1VwLFxuICAgICAgaXNCcmVhazoganNvbkJvZHk/LnBhcmFtcz8uaXNCcmVhayxcbiAgICAgIGFsbERheTogZGF0ZUpTT05Cb2R5Py5hbGxEYXksXG4gICAgfTtcblxuICAgIGlmIChcbiAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbiAgICApIHtcbiAgICAgIGJvZHkucmVjdXIgPSByZWN1ck9iamVjdCBhcyBhbnk7XG4gICAgfVxuICAgIC8vIHZhbGlkYXRlIGZvciBtaXNzaW5nIGZpZWxkc1xuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdlZGl0RXZlbnQnLFxuICAgIH07XG5cbiAgICAvLyB2YWxpZGF0ZSByZW1haW5pbmcgcmVxdWlyZWQgZmllbGRzXG4gICAgaWYgKCFib2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgLy8gZ2V0IGluZm8gb2YgY29udGFjdHMgd2l0aG91dCBlbWFpbHMgcHJvdmlkZWQgYW5kIGFzc2lnbiB2YWx1ZXNcbiAgICBjb25zdCBuZXdBdHRlbmRlZXM6IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhIG9mIGJvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQodXNlcklkLCBhPy5uYW1lKTtcbiAgICAgICAgaWYgKGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZSkge1xuICAgICAgICAgIGNvbnN0IHByaW1hcnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uZmluZCgoZSkgPT4gISFlLnByaW1hcnkpPy52YWx1ZTtcbiAgICAgICAgICBjb25zdCBhbnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZTtcbiAgICAgICAgICBuZXdBdHRlbmRlZXMucHVzaCh7IC4uLmEsIGVtYWlsOiBwcmltYXJ5RW1haWwgfHwgYW55RW1haWwgfSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChcbiAgICAgICAgICAgIHJlcXVpcmVkRmllbGRzLm9wdGlvbmFsPy5bN10/LlsnYW5kJ10/LlsyXVxuICAgICAgICAgICk7XG4gICAgICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBib2R5O1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgICAgICB9O1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIG5ld0F0dGVuZGVlcy5wdXNoKGEpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGJvZHkuYXR0ZW5kZWVzID0gbmV3QXR0ZW5kZWVzO1xuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwRWRpdEV2ZW50KFxuICAgICAgYm9keSxcbiAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXMsXG4gICAgICBzdGFydERhdGUsXG4gICAgICBlbmREYXRlLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgICAvLyBjb252ZXJ0IHRvIHZlY3RvciBmb3Igc2VhcmNoXG4gICAgLy8gY29uc3Qgc2VhcmNoVGl0bGUgPSBib2R5Py5vbGRUaXRsZSB8fCBib2R5Py50aXRsZVxuICAgIC8vIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3Ioc2VhcmNoVGl0bGUpXG5cbiAgICAvLyAvLyAgYWxsRXZlbnRXaXRoRXZlbnRPcGVuU2VhcmNoXG4gICAgLy8gLy8gYWxsRXZlbnRPcGVuU2VhcmNoXG4gICAgLy8gaWYgKCFzdGFydERhdGUpIHtcbiAgICAvLyAgICAgc3RhcnREYXRlID0gZGF5anMoKS5zdWJ0cmFjdCgyLCAndycpLmZvcm1hdCgpXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKCFlbmREYXRlKSB7XG4gICAgLy8gICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpXG4gICAgLy8gfVxuXG4gICAgLy8gY29uc3QgcmVzID0gYXdhaXQgYWxsRXZlbnRXaXRoRGF0ZXNPcGVuU2VhcmNoKHVzZXJJZCwgc2VhcmNoVmVjdG9yLCBzdGFydERhdGUsIGVuZERhdGUpXG5cbiAgICAvLyBjb25zdCBpZCA9IHJlcz8uaGl0cz8uaGl0cz8uWzBdPy5faWRcblxuICAgIC8vIC8vIHZhbGlkYXRlIGZvdW5kIGV2ZW50XG4gICAgLy8gaWYgKCFpZCkge1xuICAgIC8vICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnXG4gICAgLy8gICAgIHJldHVybiByZXNwb25zZVxuICAgIC8vIH1cblxuICAgIC8vIGNvbnN0IGV2ZW50SWQgPSBpZFxuXG4gICAgLy8gLy8gZ2V0IGNsaWVudCB0eXBlXG4gICAgLy8gY29uc3QgY2FsSW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKFxuICAgIC8vICAgICB1c2VySWQsXG4gICAgLy8gICAgIGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgICAvLyApXG5cbiAgICAvLyAvLyBkZWxldGUgb2xkIHJlbWluZGVyc1xuICAgIC8vIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcblxuICAgIC8vICAgICBhd2FpdCBkZWxldGVSZW1pbmRlcnNXaXRoSWRzKFtldmVudElkXSwgdXNlcklkKVxuICAgIC8vIH1cblxuICAgIC8vIC8vIGRlbGV0ZSBvbGQgdGltZSBwcmVmZXJlbmNlc1xuICAgIC8vIGlmIChib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgYXdhaXQgZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0dpdmVuRXZlbnRJZChldmVudElkKVxuICAgIC8vIH1cblxuICAgIC8vIC8vIGdldCBvbGQgZXZlbnRcbiAgICAvLyBjb25zdCBvbGRFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkoZXZlbnRJZClcblxuICAgIC8vIC8vIHZhbGlkYXRlXG4gICAgLy8gaWYgKCFvbGRFdmVudD8uaWQpIHtcbiAgICAvLyAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBvbGQgZXZlbnQgZm91bmQ/IScpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gaWYgbm8gcHJpb3JpdHkgdXNlIG9sZFxuICAgIC8vIGlmICghYm9keT8ucHJpb3JpdHkpIHtcbiAgICAvLyAgICAgYm9keS5wcmlvcml0eSA9IG9sZEV2ZW50LnByaW9yaXR5IHx8IDFcbiAgICAvLyB9XG5cbiAgICAvLyAvLyBmaW5kQ29udGFjdEJ5RW1haWxHaXZlblVzZXJJZFxuICAgIC8vIC8vIGdldCBhdHRlbmRlZXMgd2l0aCBwcm92aWRlZCBlbWFpbHNcbiAgICAvLyBjb25zdCBhV2l0aEVtYWlscyA9IGJvZHk/LmF0dGVuZGVlcz8uZmlsdGVyKGEgPT4gISFhPy5lbWFpbClcblxuICAgIC8vIGNvbnN0IGFXaXRoQ29udGFjdEluZm9zID0gYXdhaXQgZ2V0VXNlckNvbnRhY3RJbmZvc0dpdmVuSWRzKGFXaXRoRW1haWxzPy5tYXAoYSA9PiAoYT8uZW1haWwpKSlcblxuICAgIC8vIGNvbnN0IGF0dGVuZGVlc0Zyb21FeHRyYWN0ZWRKU09OID0gYm9keT8uYXR0ZW5kZWVzIHx8IFtdXG4gICAgLy8gY29uc3QgYXR0ZW5kZWVzOiBBdHRlbmRlZVR5cGVbXSA9IFtdXG5cbiAgICAvLyBmb3IgKGNvbnN0IGEgb2YgYXR0ZW5kZWVzRnJvbUV4dHJhY3RlZEpTT04pIHtcbiAgICAvLyAgICAgY29uc3QgY29udGFjdCA9IGF3YWl0IGZpbmRDb250YWN0QnlFbWFpbEdpdmVuVXNlcklkKHVzZXJJZCwgYS5lbWFpbClcbiAgICAvLyAgICAgY29uc3QgdXNlcklkRm91bmQgPSBhV2l0aENvbnRhY3RJbmZvcz8uZmluZChiID0+IChiPy5pZCA9PT0gYT8uZW1haWwpKVxuXG4gICAgLy8gICAgIGNvbnN0IGF0dGVuZGVlOiBBdHRlbmRlZVR5cGUgPSB7XG4gICAgLy8gICAgICAgICBpZDogdXNlcklkRm91bmQ/LnVzZXJJZCB8fCB1dWlkKCksXG4gICAgLy8gICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICBuYW1lOiBhPy5uYW1lIHx8IGNvbnRhY3Q/Lm5hbWUgfHwgYCR7Y29udGFjdD8uZmlyc3ROYW1lfSAke2NvbnRhY3Q/Lmxhc3ROYW1lfWAsXG4gICAgLy8gICAgICAgICBjb250YWN0SWQ6IGNvbnRhY3Q/LmlkLFxuICAgIC8vICAgICAgICAgZW1haWxzOiBbeyBwcmltYXJ5OiB0cnVlLCB2YWx1ZTogYT8uZW1haWwgfV0sXG4gICAgLy8gICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIC8vICAgICAgICAgZXZlbnRJZCxcbiAgICAvLyAgICAgfVxuXG4gICAgLy8gICAgIGF0dGVuZGVlcy5wdXNoKGF0dGVuZGVlKVxuICAgIC8vIH1cblxuICAgIC8vIC8vIHRha2UgY2FyZSBvZiByZWN1cnJlbmNlXG4gICAgLy8gY29uc3QgcmVjdXIgPSBjcmVhdGVSUnVsZVN0cmluZyhib2R5Py5yZWN1cj8uZnJlcXVlbmN5LCBib2R5Py5yZWN1cj8uaW50ZXJ2YWwsIGJvZHk/LnJlY3VyPy5ieVdlZWtEYXksIGJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlLCBib2R5Py5yZWN1cj8uZW5kRGF0ZSwgKGJvZHk/LnJlY3VyIGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmJ5TW9udGhEYXkpXG5cbiAgICAvLyBsZXQgY29uZmVyZW5jZTogQ29uZmVyZW5jZVR5cGUgfCB7fSA9IHt9XG5cbiAgICAvLyAvLyBjb25mZXJlbmNlOiBjcmVhdGUgLyB1cGRhdGUgYW5kIHN0b3JlIGluIGRiXG4gICAgLy8gaWYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgJiYgIW9sZEV2ZW50LmNvbmZlcmVuY2VJZCkge1xuXG4gICAgLy8gICAgIC8vIGNyZWF0ZSBjb25mZXJlbmNlIG9iamVjdFxuICAgIC8vICAgICBjb25zdCB6b29tVG9rZW4gPSBhd2FpdCBnZXRab29tQVBJVG9rZW4odXNlcklkKVxuXG4gICAgLy8gICAgIGNvbmZlcmVuY2UgPSAoem9vbVRva2VuICYmIChib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbScpKSA/IHt9IDoge1xuICAgIC8vICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgIC8vICAgICAgICAgYXBwOiAnZ29vZ2xlJyxcbiAgICAvLyAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgLy8gICAgICAgICBub3RlczogYm9keT8uZGVzY3JpcHRpb24gfHwgYm9keT8udGl0bGUsXG4gICAgLy8gICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIC8vICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIC8vICAgICB9XG5cbiAgICAvLyAgICAgaWYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJykge1xuXG4gICAgLy8gICAgICAgICBjb25zb2xlLmxvZyh6b29tVG9rZW4sICcgem9vbVRva2VuIGluc2lkZSBpZiAoem9vbVRva2VuKScpXG5cbiAgICAvLyAgICAgICAgIGNvbnN0IHpvb21PYmplY3QgPSBhd2FpdCBjcmVhdGVab29tTWVldGluZyhcbiAgICAvLyAgICAgICAgICAgICB6b29tVG9rZW4sXG4gICAgLy8gICAgICAgICAgICAgYm9keT8uc3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgIC8vICAgICAgICAgICAgIGJvZHk/LnRpdGxlLFxuICAgIC8vICAgICAgICAgICAgIGR1cmF0aW9uLFxuICAgIC8vICAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgLy8gICAgICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucHJpbWFyeUVtYWlsLFxuICAgIC8vICAgICAgICAgICAgIGJvZHk/LmF0dGVuZGVlcz8ubWFwKGEgPT4gYT8uZW1haWwpLFxuICAgIC8vICAgICAgICAgICAgIGJvZHk/LnJlY3VyIGFzIGFueSxcbiAgICAvLyAgICAgICAgIClcblxuICAgIC8vICAgICAgICAgY29uc29sZS5sb2coem9vbU9iamVjdCwgJyB6b29tT2JqZWN0IGFmdGVyIGNyZWF0ZVpvb21NZWV0aW5nJylcblxuICAgIC8vICAgICAgICAgaWYgKHpvb21PYmplY3QpIHtcbiAgICAvLyAgICAgICAgICAgICBjb25mZXJlbmNlID0ge1xuICAgIC8vICAgICAgICAgICAgICAgICBpZDogYCR7em9vbU9iamVjdD8uaWR9YCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5pZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgYXBwOiAnem9vbScsXG4gICAgLy8gICAgICAgICAgICAgICAgIG5hbWU6IHpvb21PYmplY3Q/LmFnZW5kYSxcbiAgICAvLyAgICAgICAgICAgICAgICAgbm90ZXM6IHpvb21PYmplY3Q/LmFnZW5kYSxcbiAgICAvLyAgICAgICAgICAgICAgICAgam9pblVybDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgLy8gICAgICAgICAgICAgICAgIHN0YXJ0VXJsOiB6b29tT2JqZWN0Py5zdGFydF91cmwsXG4gICAgLy8gICAgICAgICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgLy8gICAgICAgICAgICAgICAgIGVudHJ5UG9pbnRzOiBbe1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgZW50cnlQb2ludFR5cGU6ICd2aWRlbycsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBsYWJlbDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBwYXNzd29yZDogem9vbU9iamVjdD8ucGFzc3dvcmQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1cmk6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgIC8vICAgICAgICAgICAgICAgICB9XVxuICAgIC8vICAgICAgICAgICAgIH0gYXMgQ29uZmVyZW5jZVR5cGVcblxuICAgIC8vICAgICAgICAgfVxuICAgIC8vICAgICB9XG5cbiAgICAvLyAgICAgLy8gaW5zZXJ0IG5ldyBjb25mZXJlbmNlXG4gICAgLy8gICAgIGF3YWl0IHVwc2VydENvbmZlcmVuY2UoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSlcblxuICAgIC8vIH0gZWxzZSBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCAmJiBvbGRFdmVudC5jb25mZXJlbmNlSWQpIHtcbiAgICAvLyAgICAgLy8gZ2V0IG9sZCBjb25mZXJlbmNlIG9iamVjdFxuICAgIC8vICAgICBjb25zdCBvbGRDb25mZXJlbmNlID0gYXdhaXQgZ2V0Q29uZmVyZW5jZUdpdmVuSWQob2xkRXZlbnQ/LmNvbmZlcmVuY2VJZClcbiAgICAvLyAgICAgLy8gY3JlYXRlIGNvbmZlcmVuY2Ugb2JqZWN0XG4gICAgLy8gICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbih1c2VySWQpXG5cbiAgICAvLyAgICAgLy8gdXBkYXRlWm9vbU1lZXRpbmdcbiAgICAvLyAgICAgY29uZmVyZW5jZSA9ICh6b29tVG9rZW4gJiYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJykpID8ge30gOiB7XG4gICAgLy8gICAgICAgICAuLi5vbGRDb25mZXJlbmNlLFxuICAgIC8vICAgICAgICAgaWQ6IG9sZEV2ZW50Py5jb25mZXJlbmNlSWQsXG4gICAgLy8gICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICBjYWxlbmRhcklkOiBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAvLyAgICAgICAgIGFwcDogJ2dvb2dsZScsXG4gICAgLy8gICAgICAgICBuYW1lOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgIC8vICAgICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlLFxuICAgIC8vICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAvLyAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAvLyAgICAgfVxuXG4gICAgLy8gICAgIGlmIChib2R5Py5jb25mZXJlbmNlQXBwID09PSBvbGRDb25mZXJlbmNlLmFwcCkge1xuXG4gICAgLy8gICAgICAgICBjb25zb2xlLmxvZyh6b29tVG9rZW4sICcgem9vbVRva2VuIGluc2lkZSBpZiAoem9vbVRva2VuKScpXG5cbiAgICAvLyAgICAgICAgIGlmICh6b29tVG9rZW4gJiYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJykpIHtcbiAgICAvLyAgICAgICAgICAgICBhd2FpdCB1cGRhdGVab29tTWVldGluZyhcbiAgICAvLyAgICAgICAgICAgICAgICAgem9vbVRva2VuLFxuICAgIC8vICAgICAgICAgICAgICAgICBwYXJzZUludChvbGRFdmVudD8uY29uZmVyZW5jZUlkLCAxMCksXG4gICAgLy8gICAgICAgICAgICAgICAgIGJvZHk/LnN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgYm9keT8udGltZXpvbmUsXG4gICAgLy8gICAgICAgICAgICAgICAgIGJvZHk/LnRpdGxlIHx8IGJvZHk/LmRlc2NyaXB0aW9uLFxuICAgIC8vICAgICAgICAgICAgICAgICBkdXJhdGlvbiB8fCBib2R5Py5kdXJhdGlvbiB8fCBvbGRFdmVudD8uZHVyYXRpb24sXG4gICAgLy8gICAgICAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnByaW1hcnlFbWFpbCxcbiAgICAvLyAgICAgICAgICAgICAgICAgYXR0ZW5kZWVzPy5sZW5ndGggPiAwID8gYXR0ZW5kZWVzPy5tYXAoYSA9PiBhPy5lbWFpbHM/LlswXT8udmFsdWUpIDogdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIGJvZHk/LnJlY3VyIGFzIGFueSxcbiAgICAvLyAgICAgICAgICAgICApXG5cbiAgICAvLyAgICAgICAgICAgICBjb25mZXJlbmNlID0ge1xuICAgIC8vICAgICAgICAgICAgICAgICAuLi5vbGRDb25mZXJlbmNlLFxuICAgIC8vICAgICAgICAgICAgICAgICBpZDogb2xkQ29uZmVyZW5jZT8uaWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVzZXJJZDogdXNlcklkLFxuICAgIC8vICAgICAgICAgICAgICAgICBjYWxlbmRhcklkOiBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgYXBwOiAnem9vbScsXG4gICAgLy8gICAgICAgICAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBvbGRFdmVudD8ubm90ZXMsXG4gICAgLy8gICAgICAgICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgLy8gICAgICAgICAgICAgfSBhcyBDb25mZXJlbmNlVHlwZVxuICAgIC8vICAgICAgICAgfSBlbHNlIHtcbiAgICAvLyAgICAgICAgICAgICBjb25mZXJlbmNlID0ge1xuICAgIC8vICAgICAgICAgICAgICAgICAuLi5vbGRDb25mZXJlbmNlLFxuICAgIC8vICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgIC8vICAgICAgICAgICAgICAgICBhcHA6ICdnb29nbGUnLFxuICAgIC8vICAgICAgICAgICAgICAgICBuYW1lOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgIC8vICAgICAgICAgICAgICAgICBub3RlczogYm9keT8uZGVzY3JpcHRpb24gfHwgYm9keT8udGl0bGUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIC8vICAgICAgICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgLy8gICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICAvLyBpbnNlcnQgbmV3IGNvbmZlcmVuY2VcbiAgICAvLyAgICAgICAgIGF3YWl0IHVwc2VydENvbmZlcmVuY2UoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSlcblxuICAgIC8vICAgICB9IGVsc2UgaWYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgIT09IG9sZENvbmZlcmVuY2UuYXBwKSB7XG5cbiAgICAvLyAgICAgICAgIC8vIGNyZWF0ZSBjb25mZXJlbmNlIG9iamVjdFxuICAgIC8vICAgICAgICAgY29uc3Qgem9vbVRva2VuID0gYXdhaXQgZ2V0Wm9vbUFQSVRva2VuKHVzZXJJZClcblxuICAgIC8vICAgICAgICAgY29uZmVyZW5jZSA9ICh6b29tVG9rZW4gJiYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJykpID8ge30gOiB7XG4gICAgLy8gICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICAgICAgYXBwOiAnZ29vZ2xlJyxcbiAgICAvLyAgICAgICAgICAgICBuYW1lOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgIC8vICAgICAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAvLyAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgLy8gICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICBpZiAoem9vbVRva2VuICYmIChib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbScpKSB7XG5cbiAgICAvLyAgICAgICAgICAgICBjb25zb2xlLmxvZyh6b29tVG9rZW4sICcgem9vbVRva2VuIGluc2lkZSBpZiAoem9vbVRva2VuKScpXG5cbiAgICAvLyAgICAgICAgICAgICBjb25zdCB6b29tT2JqZWN0ID0gYXdhaXQgY3JlYXRlWm9vbU1lZXRpbmcoXG4gICAgLy8gICAgICAgICAgICAgICAgIHpvb21Ub2tlbixcbiAgICAvLyAgICAgICAgICAgICAgICAgYm9keT8uc3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgICAgICAgICB0aW1lem9uZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgYm9keT8udGl0bGUgfHwgYm9keT8uZGVzY3JpcHRpb24sXG4gICAgLy8gICAgICAgICAgICAgICAgIGR1cmF0aW9uLFxuICAgIC8vICAgICAgICAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgIC8vICAgICAgICAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5wcmltYXJ5RW1haWwsXG4gICAgLy8gICAgICAgICAgICAgICAgIGJvZHk/LmF0dGVuZGVlcz8ubWFwKGEgPT4gYT8uZW1haWwpLFxuICAgIC8vICAgICAgICAgICAgICAgICBib2R5Py5yZWN1ciBhcyBhbnksXG4gICAgLy8gICAgICAgICAgICAgKVxuXG4gICAgLy8gICAgICAgICAgICAgY29uc29sZS5sb2coem9vbU9iamVjdCwgJyB6b29tT2JqZWN0IGFmdGVyIGNyZWF0ZVpvb21NZWV0aW5nJylcblxuICAgIC8vICAgICAgICAgICAgIGlmICh6b29tT2JqZWN0KSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGNvbmZlcmVuY2UgPSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBpZDogYCR7em9vbU9iamVjdD8uaWR9YCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVzZXJJZDogdXNlcklkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmlkLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgYXBwOiAnem9vbScsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBuYW1lOiB6b29tT2JqZWN0Py5hZ2VuZGEsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBub3Rlczogem9vbU9iamVjdD8uYWdlbmRhLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgam9pblVybDogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBzdGFydFVybDogem9vbU9iamVjdD8uc3RhcnRfdXJsLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGVudHJ5UG9pbnRzOiBbe1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIGVudHJ5UG9pbnRUeXBlOiAndmlkZW8nLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIGxhYmVsOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICBwYXNzd29yZDogem9vbU9iamVjdD8ucGFzc3dvcmQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgdXJpOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1dXG4gICAgLy8gICAgICAgICAgICAgICAgIH0gYXMgQ29uZmVyZW5jZVR5cGVcblxuICAgIC8vICAgICAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICAvLyBkZWxldGUgb2xkIGNvbmZlcmVuY2VcbiAgICAvLyAgICAgICAgIGF3YWl0IGRlbGV0ZUNvbmZlcmVuY2VHaXZlbklkKG9sZENvbmZlcmVuY2U/LmlkKVxuICAgIC8vICAgICAgICAgaWYgKG9sZENvbmZlcmVuY2UuYXBwID09PSAnem9vbScpIHtcbiAgICAvLyAgICAgICAgICAgICBhd2FpdCBkZWxldGVab29tTWVldGluZyh6b29tVG9rZW4sIHBhcnNlSW50KG9sZENvbmZlcmVuY2UuaWQsIDEwKSlcbiAgICAvLyAgICAgICAgIH1cbiAgICAvLyAgICAgICAgIC8vIGluc2VydCBuZXcgY29uZmVyZW5jZVxuICAgIC8vICAgICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKVxuICAgIC8vICAgICB9XG5cbiAgICAvLyB9XG4gICAgLy8gLy8gaWYgZXhpc3RpbmcgYnVmZmVyIHRpbWVzXG4gICAgLy8gLy8gZGVsZXRlIG9sZCBhbmQgY3JlYXRlIG5ldyBvbmVzIGxhdGVyIG9uXG4gICAgLy8gaWYgKChvbGRFdmVudD8ucHJlRXZlbnRJZCAmJiBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCkgfHwgKG9sZEV2ZW50Py5wb3N0RXZlbnRJZCAmJiBib2R5Py5idWZmZXJUaW1lPy5hZnRlckV2ZW50KSkge1xuICAgIC8vICAgICAvLyBkZWxldGUgYnVmZmVyZSB0aW1lcyBpZiBhbnlcblxuICAgIC8vICAgICBpZiAob2xkRXZlbnQ/LnByZUV2ZW50SWQpIHtcbiAgICAvLyAgICAgICAgIGNvbnN0IHByZUV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShvbGRFdmVudD8ucHJlRXZlbnRJZClcbiAgICAvLyAgICAgICAgIGF3YWl0IGRlbGV0ZUdvb2dsZUV2ZW50KHVzZXJJZCwgcHJlRXZlbnQ/LmNhbGVuZGFySWQsIHByZUV2ZW50Py5ldmVudElkLCBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSlcbiAgICAvLyAgICAgICAgIGF3YWl0IGRlbGV0ZUV2ZW50R2l2ZW5JZChvbGRFdmVudD8ucHJlRXZlbnRJZClcblxuICAgIC8vICAgICB9XG5cbiAgICAvLyAgICAgaWYgKG9sZEV2ZW50Py5wb3N0RXZlbnRJZCkge1xuXG4gICAgLy8gICAgICAgICBjb25zdCBwb3N0RXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KG9sZEV2ZW50Py5wb3N0RXZlbnRJZClcbiAgICAvLyAgICAgICAgIGF3YWl0IGRlbGV0ZUdvb2dsZUV2ZW50KHVzZXJJZCwgcG9zdEV2ZW50Py5jYWxlbmRhcklkLCBwb3N0RXZlbnQ/LmV2ZW50SWQsIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlKVxuICAgIC8vICAgICAgICAgYXdhaXQgZGVsZXRlRXZlbnRHaXZlbklkKG9sZEV2ZW50Py5wb3N0RXZlbnRJZClcbiAgICAvLyAgICAgfVxuICAgIC8vIH1cblxuICAgIC8vIC8vIGNyZWF0ZSBuZXcgdGltZSBwcmVmZXJlbmNlcyBhbmQgcHJpb3JpdHlcbiAgICAvLyBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXVxuXG4gICAgLy8gZm9yIChjb25zdCB0aW1lcHJlZmVyZW5jZSBvZiBib2R5Py50aW1lUHJlZmVyZW5jZXMpIHtcblxuICAgIC8vICAgICBpZiAodGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgICAgICBmb3IgKGNvbnN0IGRheU9mV2VlayBvZiB0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWspIHtcblxuICAgIC8vICAgICAgICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAvLyAgICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgZGF5T2ZXZWVrOiBEYXlPZldlZWtFbnVtW2RheU9mV2Vla10sXG4gICAgLy8gICAgICAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgIC8vICAgICAgICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgIC8vICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSlcbiAgICAvLyAgICAgICAgIH1cbiAgICAvLyAgICAgfSBlbHNlIHtcblxuICAgIC8vICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgIC8vICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgLy8gICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAvLyAgICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAvLyAgICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgIC8vICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpXG4gICAgLy8gICAgIH1cblxuICAgIC8vIH1cblxuICAgIC8vIC8vIGNyZWF0ZSBuZXcgcmVtaW5kZXJzIGZvciB1cGRhdGVkIGV2ZW50XG4gICAgLy8gY29uc3QgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkOiBSZW1pbmRlclR5cGVbXSA9IFtdXG5cbiAgICAvLyBpZiAoYm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgIGNvbnN0IG5ld1JlbWluZGVyczogUmVtaW5kZXJUeXBlW10gPSBib2R5Py5yZW1pbmRlcnMubWFwKHIgPT4gKHtcbiAgICAvLyAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgLy8gICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICBldmVudElkLFxuICAgIC8vICAgICAgICAgdGltZXpvbmUsXG4gICAgLy8gICAgICAgICBtaW51dGVzOiByLFxuICAgIC8vICAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgLy8gICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIC8vICAgICB9KSlcblxuICAgIC8vICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQucHVzaCguLi5uZXdSZW1pbmRlcnMpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gcGF0Y2hHb29nbGVFdmVudFxuICAgIC8vIGNvbnN0IHN0YXJ0RGF0ZVRpbWUgPSBzdGFydERhdGUgPyBkYXlqcyhzdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoKSA6IG9sZEV2ZW50Py5zdGFydERhdGVcbiAgICAvLyBjb25zdCBlbmREYXRlVGltZSA9IChzdGFydERhdGVUaW1lICYmIGR1cmF0aW9uKSA/IGRheWpzKHN0YXJ0RGF0ZVRpbWUpLnR6KHRpbWV6b25lKS5hZGQoZHVyYXRpb24sICdtaW51dGUnKS5mb3JtYXQoKVxuICAgIC8vICAgICA6IG9sZEV2ZW50Py5lbmREYXRlXG5cbiAgICAvLyBjb25zdCBldmVudFRvVXBzZXJ0TG9jYWw6IEV2ZW50VHlwZSA9IHtcbiAgICAvLyAgICAgLi4ub2xkRXZlbnQsXG4gICAgLy8gICAgIGlkOiBldmVudElkLFxuICAgIC8vICAgICB1c2VySWQsXG4gICAgLy8gICAgIHRpbWV6b25lLFxuICAgIC8vICAgICBpc1ByZUV2ZW50OiBmYWxzZSxcbiAgICAvLyAgICAgaXNQb3N0RXZlbnQ6IGZhbHNlLFxuICAgIC8vICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LmFsbERheSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwuYWxsRGF5ID0gYm9keT8uYWxsRGF5XG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnRpdGxlKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC50aXRsZSA9IGJvZHk/LnRpdGxlXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5zdW1tYXJ5ID0gYm9keT8udGl0bGVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoc3RhcnREYXRlKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5zdGFydERhdGUgPSBkYXlqcyhzdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoKVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChlbmREYXRlVGltZSAmJiAoZW5kRGF0ZVRpbWUgIT09IG9sZEV2ZW50Py5lbmREYXRlKSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwuZW5kRGF0ZSA9IGRheWpzKHN0YXJ0RGF0ZVRpbWUpLnR6KHRpbWV6b25lKS5hZGQoZHVyYXRpb24sICdtaW51dGUnKS5mb3JtYXQoKVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChkdXJhdGlvbiAmJiAoZHVyYXRpb24gIT09IG9sZEV2ZW50Py5kdXJhdGlvbikpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmR1cmF0aW9uID0gZHVyYXRpb25cbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8uaXNGb2xsb3dVcCkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwuaXNGb2xsb3dVcCA9IGJvZHkuaXNGb2xsb3dVcFxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwubm90ZXMgPSBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5wcmlvcml0eSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwucHJpb3JpdHkgPSBib2R5LnByaW9yaXR5XG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudHJhbnNwYXJlbmN5ID0gYm9keS50cmFuc3BhcmVuY3lcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eSA9IHRydWVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8udmlzaWJpbGl0eSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudmlzaWJpbGl0eSA9IGJvZHkudmlzaWJpbGl0eSBhcyBWaXNpYmlsaXR5VHlwZVxuICAgIC8vIH1cblxuICAgIC8vIGlmICgoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5jb25mZXJlbmNlSWQgPSAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LmJ1ZmZlclRpbWUpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRpbWVCbG9ja2luZyA9IGJvZHkuYnVmZmVyVGltZVxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkVGltZUJsb2NraW5nID0gdHJ1ZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlID0gdHJ1ZVxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwubW9kaWZpYWJsZSA9IHRydWVcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZE1vZGlmaWFibGUgPSB0cnVlXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkUmVtaW5kZXJzID0gdHJ1ZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5wcmlvcml0eSA+IDEpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWwgPSB0cnVlXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5tb2RpZmlhYmxlID0gdHJ1ZVxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkTW9kaWZpYWJsZSA9IHRydWVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8uZHVyYXRpb24pIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZER1cmF0aW9uID0gdHJ1ZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5sb2NhdGlvbikge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwubG9jYXRpb24gPSB7IHRpdGxlOiBib2R5Py5sb2NhdGlvbiB9XG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnJlY3VyKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5yZWN1cnJlbmNlID0gcmVjdXJcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnJlY3VycmVuY2VSdWxlID0ge1xuICAgIC8vICAgICAgICAgZnJlcXVlbmN5OiBib2R5Py5yZWN1cj8uZnJlcXVlbmN5LFxuICAgIC8vICAgICAgICAgaW50ZXJ2YWw6IGJvZHk/LnJlY3VyPy5pbnRlcnZhbCxcbiAgICAvLyAgICAgICAgIGJ5V2Vla0RheTogYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAvLyAgICAgICAgIG9jY3VycmVuY2U6IGJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlLFxuICAgIC8vICAgICAgICAgZW5kRGF0ZTogYm9keT8ucmVjdXI/LmVuZERhdGUsXG4gICAgLy8gICAgICAgICBieU1vbnRoRGF5OiAoYm9keT8ucmVjdXIgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uYnlNb250aERheSxcbiAgICAvLyAgICAgfVxuICAgIC8vIH1cblxuICAgIC8vIGNvbnN0IGdvb2dsZVJlbWluZGVyOiBHb29nbGVSZW1pbmRlclR5cGUgPSB7XG4gICAgLy8gICAgIG92ZXJyaWRlczogcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5tYXAociA9PiAoeyBtZXRob2Q6ICdlbWFpbCcsIG1pbnV0ZXM6IHI/Lm1pbnV0ZXMgfSkpLFxuICAgIC8vICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICAvLyB9XG5cbiAgICAvLyBhd2FpdCBwYXRjaEdvb2dsZUV2ZW50KFxuICAgIC8vICAgICB1c2VySWQsXG4gICAgLy8gICAgIG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmV2ZW50SWQsXG4gICAgLy8gICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmVuZERhdGUsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3RhcnREYXRlLFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmNvbmZlcmVuY2VJZCA/IDEgOiAwLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc2VuZFVwZGF0ZXMsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAvLyAgICAgYm9keT8uYXR0ZW5kZWVzPy5tYXAoYSA9PiAoeyBlbWFpbDogYT8uZW1haWwgfSkpLFxuICAgIC8vICAgICAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkID8ge1xuICAgIC8vICAgICAgICAgdHlwZTogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5hcHAgPT09ICd6b29tJyA/ICdhZGRPbicgOiAnaGFuZ291dHNNZWV0JyxcbiAgICAvLyAgICAgICAgIG5hbWU6IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8ubmFtZSxcbiAgICAvLyAgICAgICAgIGNvbmZlcmVuY2VJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZCxcbiAgICAvLyAgICAgICAgIGVudHJ5UG9pbnRzOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmVudHJ5UG9pbnRzLFxuICAgIC8vICAgICAgICAgY3JlYXRlUmVxdWVzdDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5hcHAgPT09ICdnb29nbGUnID8ge1xuICAgIC8vICAgICAgICAgICAgIHJlcXVlc3RJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5yZXF1ZXN0SWQsXG4gICAgLy8gICAgICAgICAgICAgY29uZmVyZW5jZVNvbHV0aW9uS2V5OiB7XG4gICAgLy8gICAgICAgICAgICAgICAgIHR5cGU6ICdoYW5nb3V0c01lZXQnLFxuICAgIC8vICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgIH0gOiB1bmRlZmluZWQsXG4gICAgLy8gICAgIH0gOiB1bmRlZmluZWQsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3VtbWFyeSxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ub3RlcyxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50aW1lem9uZSxcbiAgICAvLyAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lm9yaWdpbmFsU3RhcnREYXRlLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIHJlY3VyLFxuICAgIC8vICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lmxlbmd0aCA+IDAgPyBnb29nbGVSZW1pbmRlciA6IHVuZGVmaW5lZCxcbiAgICAvLyAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udHJhbnNwYXJlbmN5LFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnZpc2liaWxpdHksXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICdkZWZhdWx0JyxcbiAgICAvLyAgICAgYm9keT8ubG9jYXRpb24sXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyApXG5cbiAgICAvLyAvLyBhZGQgYnVmZmVyIHRpbWVcbiAgICAvLyAvLyBhZGQgYnVmZmVyIHRpbWUgaWYgYW55XG4gICAgLy8gaWYgKGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQgfHwgYm9keT8uYnVmZmVyVGltZT8uYmVmb3JlRXZlbnQpIHtcblxuICAgIC8vICAgICBjb25zdCByZXR1cm5WYWx1ZXMgPSBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50KGV2ZW50VG9VcHNlcnRMb2NhbCwgYm9keT8uYnVmZmVyVGltZSlcblxuICAgIC8vICAgICBpZiAocmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50KSB7XG5cbiAgICAvLyAgICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgLy8gICAgICAgICAgICAgdXNlcklkLFxuICAgIC8vICAgICAgICAgICAgIG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgIC8vICAgICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uaWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5lbmREYXRlLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgICAgIDAsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50aXRsZSxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lm5vdGVzLFxuICAgIC8vICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmVjdXIsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50cmFuc3BhcmVuY3ksXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py52aXNpYmlsaXR5LFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgKVxuXG4gICAgLy8gICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkXG4gICAgLy8gICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZFxuICAgIC8vICAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnBvc3RFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWRcblxuICAgIC8vICAgICB9XG5cbiAgICAvLyAgICAgaWYgKHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQpIHtcblxuICAgIC8vICAgICAgICAgY29uc3QgZ29vZ2xlUmVzVmFsdWU6IEdvb2dsZVJlc1R5cGUgPSBhd2FpdCBjcmVhdGVHb29nbGVFdmVudChcbiAgICAvLyAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uaWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZW5kRGF0ZSxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgMCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRpdGxlLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lm5vdGVzLFxuICAgIC8vICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8ub3JpZ2luYWxTdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHJlY3VyLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py52aXNpYmlsaXR5LFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgICdkZWZhdWx0JyxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgKVxuXG4gICAgLy8gICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZFxuICAgIC8vICAgICAgICAgcmV0dXJuVmFsdWVzLmJlZm9yZUV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkXG4gICAgLy8gICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucHJlRXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkXG5cbiAgICAvLyAgICAgfVxuXG4gICAgLy8gICAgIC8vIGluc2VydCBldmVudHNcbiAgICAvLyAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFtyZXR1cm5WYWx1ZXMubmV3RXZlbnQsIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudCwgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudF0/LmZpbHRlcihlID0+ICEhZSkpXG4gICAgLy8gfSBlbHNlIHtcbiAgICAvLyAgICAgLy8gaW5zZXJ0IGV2ZW50c1xuICAgIC8vICAgICBhd2FpdCB1cHNlcnRFdmVudHMoW2V2ZW50VG9VcHNlcnRMb2NhbF0pXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gdXBkYXRlIHJlbWluZGVyc1xuICAgIC8vIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8uZm9yRWFjaChyID0+ICh7IC4uLnIsIGV2ZW50SWQ6IG9sZEV2ZW50Py5pZCB9KSlcblxuICAgIC8vIC8vIHVwZGF0ZSB0aW1lUHJlZmVyZW5jZXNcbiAgICAvLyBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5mb3JFYWNoKHB0ID0+ICh7IC4uLnB0LCBldmVudElkOiBvbGRFdmVudD8uaWQgfSkpXG5cbiAgICAvLyAvLyBpbnNlcnQgcmVtaW5kZXJzXG4gICAgLy8gaWYgKHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICBhd2FpdCBpbnNlcnRSZW1pbmRlcnMocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkKVxuICAgIC8vIH1cblxuICAgIC8vIC8vIGluc2VydCB0aW1lIHByZWZlcmVuY2VzXG4gICAgLy8gaWYgKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgYXdhaXQgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gYWRkIHRyYWluaW5nIGZvciB0aW1lIHByZWZlcmVuY2VzIGFuZCBwcmlvcml0eVxuICAgIC8vIC8vIGNvbnZlcnQgdG8gdmVjdG9yIGZvciBzZWFyY2hcbiAgICAvLyBpZiAoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDApIHx8IGJvZHk/LnByaW9yaXR5ID4gMSkge1xuXG4gICAgLy8gICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpXG5cbiAgICAvLyAgICAgLy8gdHJhaW4gZXZlbnRcbiAgICAvLyAgICAgYXdhaXQgcHV0RGF0YUluVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoKGV2ZW50SWQsIHNlYXJjaFZlY3RvciwgdXNlcklkKVxuICAgIC8vIH1cblxuICAgIC8vIC8vIHVwZGF0ZSBhdHRlbmRlZXMgZm9yIGV2ZW50IElkXG4gICAgLy8gYXdhaXQgdXBzZXJ0QXR0ZW5kZWVzZm9yRXZlbnQoYXR0ZW5kZWVzKVxuXG4gICAgLy8gLy8gc3VjY2VzcyByZXNwb25zZVxuICAgIC8vIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCdcblxuICAgIC8vIHJldHVybiByZXNwb25zZVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NFZGl0RXZlbnRNaXNzaW5nRmllbGRzUmV0dXJuZWQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICBsZXQgZHVyYXRpb24gPSAwO1xuXG4gICAgY29uc3QgeWVhciA9XG4gICAgICBkYXRlSlNPTkJvZHk/LnllYXIgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnllYXI7XG4gICAgY29uc3QgbW9udGggPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5tb250aCB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ubW9udGg7XG4gICAgY29uc3QgZGF5ID1cbiAgICAgIGRhdGVKU09OQm9keT8uZGF5IHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kYXk7XG4gICAgY29uc3QgaXNvV2Vla2RheSA9XG4gICAgICBkYXRlSlNPTkJvZHk/Lmlzb1dlZWtkYXkgfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5pc29XZWVrZGF5O1xuICAgIGNvbnN0IGhvdXIgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5ob3VyIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5ob3VyO1xuICAgIGNvbnN0IG1pbnV0ZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/Lm1pbnV0ZSB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ubWludXRlO1xuICAgIGNvbnN0IHN0YXJ0VGltZSA9XG4gICAgICBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IGV2ZW50U3RhcnREYXRlID0gZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgeWVhcixcbiAgICAgIG1vbnRoLFxuICAgICAgZGF5LFxuICAgICAgaXNvV2Vla2RheSxcbiAgICAgIGhvdXIsXG4gICAgICBtaW51dGUsXG4gICAgICBzdGFydFRpbWUsXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBkYXRlSlNPTkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgLy8gZ2V0IGRlZmF1bHQgdmFsdWVzXG4gICAgY29uc3QgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyA9XG4gICAgICBhd2FpdCBnZXRDaGF0TWVldGluZ1ByZWZlcmVuY2VHaXZlblVzZXJJZCh1c2VySWQpO1xuXG4gICAgaWYgKFxuICAgICAgZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbiB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1cmF0aW9uXG4gICAgKSB7XG4gICAgICBkdXJhdGlvbiA9XG4gICAgICAgIGRhdGVKU09OQm9keT8uZHVyYXRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoXG4gICAgICAoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnN0YXJ0VGltZSkgJiZcbiAgICAgIChkYXRlSlNPTkJvZHk/LmVuZFRpbWUgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmVuZFRpbWUpXG4gICAgKSB7XG4gICAgICAvLyBsaWtlbHkgc3RhcnQgdGltZSBhbHNvIHByZXNlbnRcblxuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoXG4gICAgICAgIGRhdGVKU09OQm9keT8uc3RhcnRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnN0YXJ0VGltZSxcbiAgICAgICAgJ0hIOm1tJ1xuICAgICAgKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhcbiAgICAgICAgZGF0ZUpTT05Cb2R5LmVuZFRpbWUgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmVuZFRpbWUsXG4gICAgICAgICdISDptbSdcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH0gZWxzZSBpZiAoXG4gICAgICAoanNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lKSAmJlxuICAgICAgKGpzb25Cb2R5Py5wYXJhbXM/LmVuZFRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKVxuICAgICkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoXG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lXG4gICAgICApO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lXG4gICAgICApO1xuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gdGFrZSBjYXJlIG9mIGFueSByZWN1cnJpbmcgZGF0ZXNcbiAgICBsZXQgcmVjdXJPYmplY3Q6IFJlY3VycmVuY2VSdWxlVHlwZSB8IHt9ID0ge307XG4gICAgaWYgKFxuICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmZyZXF1ZW5jeVxuICAgICkge1xuICAgICAgY29uc3QgcmVjdXJFbmREYXRlID0gZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhciB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ueWVhcixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGggfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1vbnRoLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5kYXkgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaXNvV2Vla2RheSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91ciB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uaG91cixcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubWludXRlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uc3RhcnRUaW1lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlXG4gICAgICAgICAgICA/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3cgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGVcbiAgICAgICAgICAgID8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICAgKTtcblxuICAgICAgcmVjdXJPYmplY3QgPSB7XG4gICAgICAgIGZyZXF1ZW5jeTpcbiAgICAgICAgICAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlKSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWw6XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmludGVydmFsIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uaW50ZXJ2YWwsXG4gICAgICB9O1xuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5V2Vla0RheSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5V2Vla0RheVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5V2Vla0RheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieVdlZWtEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmJ5TW9udGhEYXlcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieU1vbnRoRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2UgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlXG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkub2NjdXJyZW5jZSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICByZWN1ckVuZERhdGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGVcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5lbmREYXRlID1cbiAgICAgICAgICByZWN1ckVuZERhdGUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmVuZERhdGUgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG5ld0JvZHk6IEVkaXRFdmVudFR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2sgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBvbGRUaXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ub2xkVGl0bGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5vbGRUaXRsZSxcbiAgICAgIGF0dGVuZGVlczpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYXR0ZW5kZWVzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uYXR0ZW5kZWVzLFxuICAgICAgbWV0aG9kOiBkYXRlSlNPTkJvZHk/Lm1ldGhvZCBhcyBhbnksXG4gICAgICBkdXJhdGlvbixcbiAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5ub3RlcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ubm90ZXMsXG4gICAgICBjb25mZXJlbmNlQXBwOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5jb25mZXJlbmNlPy5hcHAgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5jb25mZXJlbmNlPy5hcHAsXG4gICAgICBzdGFydERhdGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICBldmVudFN0YXJ0RGF0ZSxcbiAgICAgIGJ1ZmZlclRpbWU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmJ1ZmZlclRpbWUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5idWZmZXJUaW1lLFxuICAgICAgcmVtaW5kZXJzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHxcbiAgICAgICAgW10sXG4gICAgICBwcmlvcml0eTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucHJpb3JpdHkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fFxuICAgICAgICAxLFxuICAgICAgdGltZVByZWZlcmVuY2VzOlxuICAgICAgICBkYXRlSlNPTkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8udGltZVByZWZlcmVuY2VzIHx8XG4gICAgICAgIFtdLFxuICAgICAgbG9jYXRpb246XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmxvY2F0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24sXG4gICAgICB0cmFuc3BhcmVuY3k6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnZpc2liaWxpdHkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy52aXNpYmlsaXR5LFxuICAgICAgaXNGb2xsb3dVcDpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uaXNGb2xsb3dVcCB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmlzRm9sbG93VXAsXG4gICAgICBpc0JyZWFrOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5pc0JyZWFrIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uaXNCcmVhayxcbiAgICAgIGFsbERheTpcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5hbGxEYXkgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmFsbERheSxcbiAgICB9O1xuXG4gICAgaWYgKFxuICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSk/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZVxuICAgICkge1xuICAgICAgbmV3Qm9keS5yZWN1ciA9IHJlY3VyT2JqZWN0IGFzIGFueTtcbiAgICB9XG4gICAgLy8gdmFsaWRhdGUgZm9yIG1pc3NpbmcgZmllbGRzXG4gICAgY29uc3QgbWlzc2luZ0ZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICAgICAgcmVxdWlyZWQ6IFtdLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ2VkaXRFdmVudCcsXG4gICAgfTtcblxuICAgIGNvbnN0IHByZXZCb2R5OiBFZGl0RXZlbnRUeXBlID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ub2xkVGl0bGUpIHtcbiAgICAgIHByZXZCb2R5Lm9sZFRpdGxlID0gbmV3Qm9keT8ub2xkVGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZHVyYXRpb24pIHtcbiAgICAgIHByZXZCb2R5LmR1cmF0aW9uID0gbmV3Qm9keT8uZHVyYXRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uZGVzY3JpcHRpb24pIHtcbiAgICAgIHByZXZCb2R5LmRlc2NyaXB0aW9uID0gbmV3Qm9keT8uZGVzY3JpcHRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uY29uZmVyZW5jZUFwcCkge1xuICAgICAgcHJldkJvZHkuY29uZmVyZW5jZUFwcCA9IG5ld0JvZHk/LmNvbmZlcmVuY2VBcHA7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uc3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS5zdGFydERhdGUgPSBuZXdCb2R5Py5zdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgcHJldkJvZHkuYnVmZmVyVGltZSA9IG5ld0JvZHk/LmJ1ZmZlclRpbWU7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnJlbWluZGVycyA9IG5ld0JvZHk/LnJlbWluZGVycyB8fCBbXTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5wcmlvcml0eSkge1xuICAgICAgcHJldkJvZHkucHJpb3JpdHkgPSBuZXdCb2R5Py5wcmlvcml0eTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkudGltZVByZWZlcmVuY2VzID0gbmV3Qm9keT8udGltZVByZWZlcmVuY2VzO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LmxvY2F0aW9uKSB7XG4gICAgICBwcmV2Qm9keS5sb2NhdGlvbiA9IG5ld0JvZHk/LmxvY2F0aW9uO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgcHJldkJvZHkudHJhbnNwYXJlbmN5ID0gbmV3Qm9keT8udHJhbnNwYXJlbmN5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIHByZXZCb2R5LnZpc2liaWxpdHkgPSBuZXdCb2R5Py52aXNpYmlsaXR5O1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5pc0ZvbGxvd1VwID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHByZXZCb2R5LmlzRm9sbG93VXAgPSBuZXdCb2R5Py5pc0ZvbGxvd1VwO1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5pc0JyZWFrID09PSB1bmRlZmluZWQpIHtcbiAgICAgIHByZXZCb2R5LmlzQnJlYWsgPSBuZXdCb2R5Py5pc0JyZWFrO1xuICAgIH1cblxuICAgIGlmIChwcmV2Qm9keS5hbGxEYXkgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuYWxsRGF5ID0gbmV3Qm9keT8uYWxsRGF5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnJlY3VyKSB7XG4gICAgICBwcmV2Qm9keS5yZWN1ciA9IG5ld0JvZHk/LnJlY3VyO1xuICAgIH1cblxuICAgIGNvbnN0IHByZXZTZWFyY2hCb3VuZGFyeTogU2VhcmNoQm91bmRhcnlUeXBlID1cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy5zZWFyY2hCb3VuZGFyeTtcblxuICAgIGxldCBwcmV2U3RhcnREYXRlID0gcHJldlNlYXJjaEJvdW5kYXJ5Py5zdGFydERhdGU7XG5cbiAgICBsZXQgcHJldkVuZERhdGUgPSBwcmV2U2VhcmNoQm91bmRhcnk/LmVuZERhdGU7XG5cbiAgICBpZiAoIXByZXZTdGFydERhdGUpIHtcbiAgICAgIHByZXZTdGFydERhdGUgPSBzdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2RW5kRGF0ZSkge1xuICAgICAgcHJldkVuZERhdGUgPSBlbmREYXRlO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnN0YXJ0RGF0ZSAmJiAhZGF5ICYmICFpc29XZWVrZGF5KSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkLnB1c2goXG4gICAgICAgIHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkPy5bMF1cbiAgICAgICk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeToge1xuICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgIXByZXZCb2R5Py5zdGFydERhdGUgJiZcbiAgICAgIGhvdXIgPT09IG51bGwgJiZcbiAgICAgIG1pbnV0ZSA9PT0gbnVsbCAmJlxuICAgICAgIXN0YXJ0VGltZVxuICAgICkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZC5wdXNoKFxuICAgICAgICByZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzFdXG4gICAgICApO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgc2VhcmNoQm91bmRhcnk6IHtcbiAgICAgICAgICBzdGFydERhdGU6IHByZXZTdGFydERhdGUsXG4gICAgICAgICAgZW5kRGF0ZTogcHJldkVuZERhdGUsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIC8vIGdldCBpbmZvIG9mIGNvbnRhY3RzIHdpdGhvdXQgZW1haWxzIHByb3ZpZGVkIGFuZCBhc3NpZ24gdmFsdWVzXG4gICAgY29uc3QgbmV3QXR0ZW5kZWVzOiBNdXRhdGVkQ2FsZW5kYXJFeHRyYWN0ZWRKU09OQXR0ZW5kZWVUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgYSBvZiBuZXdCb2R5Py5hdHRlbmRlZXMpIHtcbiAgICAgIGlmICghYT8uZW1haWwpIHtcbiAgICAgICAgY29uc3QgY29udGFjdCA9IGF3YWl0IGdldENvbnRhY3RCeU5hbWVXaXRoVXNlcklkKHVzZXJJZCwgYT8ubmFtZSk7XG4gICAgICAgIGlmIChjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWUpIHtcbiAgICAgICAgICBjb25zdCBwcmltYXJ5RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LmZpbmQoKGUpID0+ICEhZS5wcmltYXJ5KT8udmFsdWU7XG4gICAgICAgICAgY29uc3QgYW55RW1haWwgPSBjb250YWN0Py5lbWFpbHM/LlswXT8udmFsdWU7XG4gICAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goeyAuLi5hLCBlbWFpbDogcHJpbWFyeUVtYWlsIHx8IGFueUVtYWlsIH0pO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2goXG4gICAgICAgICAgICByZXF1aXJlZEZpZWxkcy5vcHRpb25hbD8uWzddPy5bJ2FuZCddPy5bMl1cbiAgICAgICAgICApO1xuICAgICAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgICAgIHNlYXJjaEJvdW5kYXJ5OiB7XG4gICAgICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAgICAgICAgICAgZW5kRGF0ZTogcHJldkVuZERhdGUsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH07XG4gICAgICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIHtcbiAgICAgICAgbmV3QXR0ZW5kZWVzLnB1c2goYSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgbmV3Qm9keS5hdHRlbmRlZXMgPSBuZXdBdHRlbmRlZXM7XG5cbiAgICBpZiAoIShwcmV2Qm9keT8uYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkuYXR0ZW5kZWVzID0gbmV3Qm9keT8uYXR0ZW5kZWVzO1xuICAgIH1cblxuICAgIC8vIHZhbGlkYXRlIHJlbWFpbmluZyByZXF1aXJlZCBmaWVsZHNcbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgc2VhcmNoQm91bmRhcnk6IHtcbiAgICAgICAgICBzdGFydERhdGU6IHByZXZTdGFydERhdGUsXG4gICAgICAgICAgZW5kRGF0ZTogcHJldkVuZERhdGUsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcEVkaXRFdmVudChcbiAgICAgIHByZXZCb2R5LFxuICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyxcbiAgICAgIHByZXZTdGFydERhdGUsXG4gICAgICBwcmV2RW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBlZGl0IGV2ZW50IG1pc3NpbmcgZmllbGRzIHJldHVybmVkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBlZGl0RXZlbnRDb250cm9sQ2VudGVyID0gYXN5bmMgKFxuICBvcGVuYWk6IE9wZW5BSSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbiAgdXNlckN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIHF1ZXJ5OiAnbWlzc2luZ19maWVsZHMnIHwgJ2NvbXBsZXRlZCcgfCAnZXZlbnRfbm90X2ZvdW5kJyB8ICdwZW5kaW5nJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGg7XG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG4gICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICB1c2VyTWVzc2FnZSA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgYnJlYWs7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgdXNlcklucHV0ID0gdXNlck1lc3NhZ2U7XG5cbiAgICBsZXQgZWRpdEV2ZW50UmVzOiBSZXNwb25zZUFjdGlvblR5cGUgPSB7XG4gICAgICBxdWVyeTogJ2NvbXBsZXRlZCcsXG4gICAgICBkYXRhOiAnJyxcbiAgICAgIHNraWxsOiAnJyxcbiAgICAgIHByZXZEYXRhOiB7fSxcbiAgICAgIHByZXZEYXRhRXh0cmE6IHt9LFxuICAgIH07XG5cbiAgICBzd2l0Y2ggKHF1ZXJ5KSB7XG4gICAgICBjYXNlICdwZW5kaW5nJzpcbiAgICAgICAgY29uc3QganNvbkJvZHkgPSBhd2FpdCBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVUaW1lID0gYXdhaXQgZ2VuZXJhdGVEYXRlVGltZShcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICk7XG4gICAgICAgIGVkaXRFdmVudFJlcyA9IGF3YWl0IHByb2Nlc3NFZGl0RXZlbnRQZW5kaW5nKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uQm9keSxcbiAgICAgICAgICBkYXRlVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdtaXNzaW5nX2ZpZWxkcyc6XG4gICAgICAgIGxldCBwcmlvclVzZXJJbnB1dCA9ICcnO1xuICAgICAgICBsZXQgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSAnJztcblxuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAnYXNzaXN0YW50Jykge1xuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgIGlmIChtZXNzYWdlLmNvbnRlbnQgIT09IHVzZXJJbnB1dCkge1xuICAgICAgICAgICAgICBwcmlvclVzZXJJbnB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmlvclVzZXJJbnB1dCB8fCAhcHJpb3JBc3Npc3RhbnRPdXRwdXQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvclVzZXJJbnB1dCwgJyBwcmlvclVzZXJJbnB1dCcpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yQXNzaXN0YW50T3V0cHV0LCAnIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBwcmlvclVzZXJpbnB1dCBvciBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGpzb25NaXNzaW5nRmllbGRzQm9keSA9XG4gICAgICAgICAgYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVNaXNzaW5nRmllbGRzVGltZSA9IGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcblxuICAgICAgICBlZGl0RXZlbnRSZXMgPSBhd2FpdCBwcm9jZXNzRWRpdEV2ZW50TWlzc2luZ0ZpZWxkc1JldHVybmVkKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uTWlzc2luZ0ZpZWxkc0JvZHksXG4gICAgICAgICAgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICB9XG5cbiAgICBpZiAoZWRpdEV2ZW50UmVzPy5xdWVyeSA9PT0gJ2NvbXBsZXRlZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnkoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGVkaXRFdmVudFJlcy5kYXRhIGFzIHN0cmluZyxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9IGVsc2UgaWYgKGVkaXRFdmVudFJlcz8ucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyhcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgZWRpdEV2ZW50UmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBlZGl0RXZlbnRSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGEgPSBlZGl0RXZlbnRSZXM/LnByZXZEYXRhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGFFeHRyYSA9IGVkaXRFdmVudFJlcz8ucHJldkRhdGFFeHRyYTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPSBlZGl0RXZlbnRSZXM/LnByZXZEYXRlSnNvbkJvZHk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2SnNvbkJvZHkgPSBlZGl0RXZlbnRSZXM/LnByZXZKc29uQm9keTtcbiAgICB9IGVsc2UgaWYgKGVkaXRFdmVudFJlcz8ucXVlcnkgPT09ICdldmVudF9ub3RfZm91bmQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6IFwiT29wcy4uLiBJIGNvdWxkbid0IGZpbmQgdGhlIGV2ZW50LiBTb3JyeSA6KFwiLFxuICAgICAgfTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfVxuXG4gICAgcmV0dXJuIG1lc3NhZ2VIaXN0b3J5T2JqZWN0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZWRpdCBldmVudCBjb250cm9sIGNlbnRlciBwZW5kaW5nJyk7XG4gIH1cbn07XG4iXX0=