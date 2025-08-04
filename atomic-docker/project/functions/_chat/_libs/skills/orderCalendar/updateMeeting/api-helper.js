import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, createGoogleEvent, createPreAndPostEventsFromEvent, createRRuleString, createZoomMeeting, deleteConferenceGivenId, deleteEventGivenId, deleteGoogleEvent, deleteRemindersWithIds, deleteZoomMeeting, eventSearchBoundary, extrapolateDateFromJSONData, extrapolateStartDateFromJSONData, findContactByEmailGivenUserId, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, getCalendarIntegrationByName, getConferenceGivenId, getContactByNameWithUserId, getEventFromPrimaryKey, getUserContactInfosGivenIds, getZoomAPIToken, insertReminders, patchGoogleEvent, putDataInTrainEventIndexInOpenSearch, updateZoomMeeting, upsertAttendeesforEvent, upsertConference, upsertEvents, } from '@chat/_libs/api-helper';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import requiredFields from './requiredFields';
import { v4 as uuid } from 'uuid';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { googleCalendarName } from '@chat/_libs/constants';
import { deletePreferredTimeRangesGivenEventId } from '../removeAllPreferedTimes/api-helper';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
export const finalStepUpdateMeeting = async (body, defaultMeetingPreferences, startDate, endDate, response) => {
    try {
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
            if (zoomToken && body?.conferenceApp === 'zoom') {
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
                eventId, // generatedId
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
        // need to be updated
        const eventToUpsertLocal = {
            ...oldEvent,
            id: eventId,
            userId: body?.userId,
            allDay: false,
            timezone: body?.timezone,
            isPreEvent: false,
            isPostEvent: false,
            updatedAt: dayjs().format(),
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
        response.data = 'successfully updated meeting';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step update meeting');
    }
};
export const processUpdateMeetingPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
    try {
        let duration = 0;
        const year = dateJSONBody?.year;
        const month = dateJSONBody?.month;
        const day = dateJSONBody?.day;
        const isoWeekday = dateJSONBody?.isoWeekday;
        const hour = dateJSONBody?.hour;
        const minute = dateJSONBody?.minute;
        const startTime = dateJSONBody?.startTime;
        const meetingStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow);
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
            oldTitle: jsonBody?.params?.oldTitle,
            attendees: jsonBody?.params?.attendees,
            method: dateJSONBody?.method,
            duration,
            description: jsonBody?.params?.description || jsonBody?.params?.notes,
            conferenceApp: jsonBody?.params?.conference?.app,
            startDate: jsonBody?.params?.startTime || meetingStartDate,
            bufferTime: jsonBody?.params?.bufferTime,
            reminders: jsonBody?.params?.alarms || [],
            priority: jsonBody?.params?.priority || 1,
            timePreferences: dateJSONBody?.timePreferences || [],
            location: jsonBody?.params?.location,
            transparency: jsonBody?.params?.transparency,
            visibility: jsonBody?.params?.visibility,
            isFollowUp: jsonBody?.params?.isFollowUp,
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
            skill: 'updateMeeting',
        };
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
        let startDate = searchBoundary.startDate;
        let endDate = searchBoundary.endDate;
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
                    missingFields.required.push(requiredFields.required?.[1]?.['and']?.[2]);
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
        // validate remaining required fields
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
        const response2 = await finalStepUpdateMeeting(body, defaultMeetingPreferences, startDate, endDate, response);
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
        // // get info of contacts without emails provided and assign values
        // const newAttendees: MutatedCalendarExtractedJSONAttendeeType[] = []
        // for (const a of body?.attendees) {
        //     if (!a?.email) {
        //         const contact = await getContactByNameWithUserId(userId, a?.name)
        //         if (contact?.emails?.[0]?.value) {
        //             const primaryEmail = contact?.emails?.find(e => !!e.primary)?.value
        //             const anyEmail = contact?.emails?.[0]?.value
        //             newAttendees.push({ ...a, email: primaryEmail || anyEmail })
        //         } else {
        //             response.query = 'missing_fields'
        //             missingFields.required.push(requiredFields.required?.[1]?.['and']?.[2])
        //             response.data = missingFields
        //         }
        //     } else {
        //         newAttendees.push(a)
        //     }
        // }
        // body.attendees = newAttendees
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
        // const recur = createRRuleString(body?.recur?.frequency, body?.recur?.interval, body?.recur?.byWeekDay, body?.recur?.occurrence, body?.recur?.endDate, body?.recur?.byMonthDay)
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
        //     if (zoomToken && (body?.conferenceApp === 'zoom')) {
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
        //         eventId, // generatedId
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
        // // need to be updated
        // const eventToUpsertLocal: EventType = {
        //     ...oldEvent,
        //     id: eventId,
        //     userId,
        //     allDay: false,
        //     timezone,
        //     isPreEvent: false,
        //     isPostEvent: false,
        //     updatedAt: dayjs().format(),
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
        //         byMonthDay: body?.recur?.byMonthDay,
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
export const processUpdateMeetingMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
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
        const meetingStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, year, month, day, isoWeekday, hour, minute, startTime, dateJSONBody?.relativeTimeChangeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
                ?.relativeTimeChangeFromNow, dateJSONBody?.relativeTimeFromNow ||
            messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
                ?.relativeTimeFromNow);
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
                meetingStartDate,
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
            skill: 'updateMeeting',
        };
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
        let startDate = searchBoundary.startDate;
        let endDate = searchBoundary.endDate;
        const newAttendees = [];
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
                    missingFields.required.push(requiredFields.required?.[1]?.['and']?.[2]);
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
        const response2 = await finalStepUpdateMeeting(prevBody, defaultMeetingPreferences, prevStartDate, prevEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to update meetings');
    }
};
export const updateMeetingControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let updateMeetingRes = {
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
                updateMeetingRes = await processUpdateMeetingPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                updateMeetingRes = await processUpdateMeetingMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (updateMeetingRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, updateMeetingRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (updateMeetingRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, updateMeetingRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required =
                updateMeetingRes?.data;
            messageHistoryObject.prevData = updateMeetingRes?.prevData;
            messageHistoryObject.prevDataExtra = updateMeetingRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody =
                updateMeetingRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = updateMeetingRes?.prevJsonBody;
        }
        else if (updateMeetingRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to update meeting control center');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiwrQkFBK0IsRUFDL0IsaUJBQWlCLEVBQ2pCLCtCQUErQixFQUMvQixpQkFBaUIsRUFDakIsaUJBQWlCLEVBQ2pCLHVCQUF1QixFQUN2QixrQkFBa0IsRUFDbEIsaUJBQWlCLEVBQ2pCLHNCQUFzQixFQUN0QixpQkFBaUIsRUFDakIsbUJBQW1CLEVBQ25CLDJCQUEyQixFQUMzQixnQ0FBZ0MsRUFDaEMsNkJBQTZCLEVBQzdCLG1EQUFtRCxFQUNuRCxxREFBcUQsRUFDckQsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3Qiw2QkFBNkIsRUFDN0IsMENBQTBDLEVBQzFDLDRCQUE0QixFQUM1QixvQkFBb0IsRUFDcEIsMEJBQTBCLEVBQzFCLHNCQUFzQixFQUN0QiwyQkFBMkIsRUFDM0IsZUFBZSxFQUNmLGVBQWUsRUFDZixnQkFBZ0IsRUFDaEIsb0NBQW9DLEVBQ3BDLGlCQUFpQixFQUNqQix1QkFBdUIsRUFDdkIsZ0JBQWdCLEVBQ2hCLFlBQVksR0FDYixNQUFNLHdCQUF3QixDQUFDO0FBT2hDLE9BQU8sRUFBRSxtQ0FBbUMsRUFBRSxNQUFNLCtCQUErQixDQUFDO0FBQ3BGLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQUN4RCxPQUFPLGNBQWMsTUFBTSxrQkFBa0IsQ0FBQztBQUM5QyxPQUFPLEVBQUUsRUFBRSxJQUFJLElBQUksRUFBRSxNQUFNLE1BQU0sQ0FBQztBQUlsQyxPQUFPLEVBQUUsYUFBYSxFQUFFLE1BQU0sdUNBQXVDLENBQUM7QUFDdEUsT0FBTyxFQUFFLGtCQUFrQixFQUFFLE1BQU0sdUJBQXVCLENBQUM7QUFDM0QsT0FBTyxFQUFFLHFDQUFxQyxFQUFFLE1BQU0sc0NBQXNDLENBQUM7QUFVN0YsT0FBTyxFQUFFLGlDQUFpQyxFQUFF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QyxvQkFBb0IsQ0FBQyxRQUFRO2dCQUMzQixnQkFBZ0IsRUFBRSxJQUEwQixDQUFDO1lBQy9DLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxnQkFBZ0IsRUFBRSxRQUFRLENBQUM7WUFDM0Qsb0JBQW9CLENBQUMsYUFBYSxHQUFHLGdCQUFnQixFQUFFLGFBQWEsQ0FBQztZQUNyRSxvQkFBb0IsQ0FBQyxnQkFBZ0I7Z0JBQ25DLGdCQUFnQixFQUFFLGdCQUFnQixDQUFDO1lBQ3JDLG9CQUFvQixDQUFDLFlBQVksR0FBRyxnQkFBZ0IsRUFBRSxZQUFZLENBQUM7UUFDckUsQ0FBQzthQUFNLElBQUksZ0JBQWdCLEVBQUUsS0FBSyxLQUFLLGlCQUFpQixFQUFFLENBQUM7WUFDekQsTUFBTSxnQkFBZ0IsR0FBeUI7Z0JBQzdDLElBQUksRUFBRSxXQUFXO2dCQUNqQixPQUFPLEVBQUUsNkNBQTZDO2FBQ3ZELENBQUM7WUFFRixvQkFBb0IsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7WUFDckQsb0JBQW9CLENBQUMsS0FBSyxHQUFHLGlCQUFpQixDQUFDO1lBQy9DLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxJQUFJLENBQUM7UUFDdkMsQ0FBQztRQUVELE9BQU8sb0JBQW9CLENBQUM7SUFDOUIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSwwQ0FBMEMsQ0FBQyxDQUFDO0lBQzdELENBQUM7QUFDSCxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBhbGxFdmVudFdpdGhEYXRlc09wZW5TZWFyY2gsXG4gIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IsXG4gIGNyZWF0ZUdvb2dsZUV2ZW50LFxuICBjcmVhdGVQcmVBbmRQb3N0RXZlbnRzRnJvbUV2ZW50LFxuICBjcmVhdGVSUnVsZVN0cmluZyxcbiAgY3JlYXRlWm9vbU1lZXRpbmcsXG4gIGRlbGV0ZUNvbmZlcmVuY2VHaXZlbklkLFxuICBkZWxldGVFdmVudEdpdmVuSWQsXG4gIGRlbGV0ZUdvb2dsZUV2ZW50LFxuICBkZWxldGVSZW1pbmRlcnNXaXRoSWRzLFxuICBkZWxldGVab29tTWVldGluZyxcbiAgZXZlbnRTZWFyY2hCb3VuZGFyeSxcbiAgZXh0cmFwb2xhdGVEYXRlRnJvbUpTT05EYXRhLFxuICBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YSxcbiAgZmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWQsXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMsXG4gIGdlbmVyYXRlRGF0ZVRpbWUsXG4gIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZSxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lLFxuICBnZXRDb25mZXJlbmNlR2l2ZW5JZCxcbiAgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQsXG4gIGdldEV2ZW50RnJvbVByaW1hcnlLZXksXG4gIGdldFVzZXJDb250YWN0SW5mb3NHaXZlbklkcyxcbiAgZ2V0Wm9vbUFQSVRva2VuLFxuICBpbnNlcnRSZW1pbmRlcnMsXG4gIHBhdGNoR29vZ2xlRXZlbnQsXG4gIHB1dERhdGFJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaCxcbiAgdXBkYXRlWm9vbU1lZXRpbmcsXG4gIHVwc2VydEF0dGVuZGVlc2ZvckV2ZW50LFxuICB1cHNlcnRDb25mZXJlbmNlLFxuICB1cHNlcnRFdmVudHMsXG59IGZyb20gJ0BjaGF0L19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IERhdGVUaW1lSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvRGF0ZVRpbWVKU09OSlNPTlR5cGUnO1xuaW1wb3J0IFVzZXJJbnB1dFRvSlNPTlR5cGUsIHtcbiAgTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVXNlcklucHV0VG9KU09OVHlwZSc7XG5pbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5pbXBvcnQgeyBVcGRhdGVNZWV0aW5nVHlwZSB9IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IHsgZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlR2l2ZW5Vc2VySWQgfSBmcm9tICcuLi9zY2hlZHVsZU1lZXRpbmcvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHJlcXVpcmVkRmllbGRzIGZyb20gJy4vcmVxdWlyZWRGaWVsZHMnO1xuaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IHsgUmVtaW5kZXJUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvR29vZ2xlVHlwZXMnO1xuaW1wb3J0IHsgR29vZ2xlUmVtaW5kZXJUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvR29vZ2xlUmVtaW5kZXJUeXBlJztcbmltcG9ydCBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1ByZWZlcnJlZFRpbWVSYW5nZVR5cGUnO1xuaW1wb3J0IHsgRGF5T2ZXZWVrRW51bSB9IGZyb20gJy4uL3Jlc29sdmVDb25mbGljdGluZ0V2ZW50cy9jb25zdGFudHMnO1xuaW1wb3J0IHsgZ29vZ2xlQ2FsZW5kYXJOYW1lIH0gZnJvbSAnQGNoYXQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQgfSBmcm9tICcuLi9yZW1vdmVBbGxQcmVmZXJlZFRpbWVzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgQ29uZmVyZW5jZVR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Db25mZXJlbmNlVHlwZSc7XG5pbXBvcnQge1xuICBFdmVudFR5cGUsXG4gIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlLFxuICBSZWN1cnJlbmNlUnVsZVR5cGUsXG4gIFZpc2liaWxpdHlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IHsgQXR0ZW5kZWVUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQXR0ZW5kZWVUeXBlJztcbmltcG9ydCB7IEdvb2dsZVJlc1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Hb29nbGVSZXNUeXBlJztcbmltcG9ydCB7IHVwc2VydFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCB9IGZyb20gJy4uL3Jlc29sdmVDb25mbGljdGluZ0V2ZW50cy9hcGktaGVscGVyJztcbmltcG9ydCBSZXNwb25zZUFjdGlvblR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVzcG9uc2VBY3Rpb25UeXBlJztcbmltcG9ydCB7XG4gIEFzc2lzdGFudE1lc3NhZ2VUeXBlLFxuICBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvTWVzc2FnaW5nL01lc3NhZ2luZ1R5cGVzJztcbmltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCB7IENoYXRNZWV0aW5nUHJlZmVyZW5jZXNUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUnO1xuaW1wb3J0IHsgU2VhcmNoQm91bmRhcnlUeXBlIH0gZnJvbSAnLi4vZGVsZXRlVGFzay90eXBlcyc7XG5cbmV4cG9ydCBjb25zdCBmaW5hbFN0ZXBVcGRhdGVNZWV0aW5nID0gYXN5bmMgKFxuICBib2R5OiBVcGRhdGVNZWV0aW5nVHlwZSxcbiAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlczogQ2hhdE1lZXRpbmdQcmVmZXJlbmNlc1R5cGUsXG4gIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICBlbmREYXRlOiBzdHJpbmcsXG4gIHJlc3BvbnNlOiBhbnlcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNlYXJjaFRpdGxlID0gYm9keT8ub2xkVGl0bGUgfHwgYm9keT8udGl0bGU7XG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcihzZWFyY2hUaXRsZSk7XG5cbiAgICAvLyAgYWxsRXZlbnRXaXRoRXZlbnRPcGVuU2VhcmNoXG4gICAgLy8gYWxsRXZlbnRPcGVuU2VhcmNoXG4gICAgaWYgKCFzdGFydERhdGUpIHtcbiAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIWVuZERhdGUpIHtcbiAgICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaChcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGVcbiAgICApO1xuXG4gICAgY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkO1xuXG4gICAgLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICBpZiAoIWlkKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50SWQgPSBpZDtcblxuICAgIC8vIGdldCBjbGllbnQgdHlwZVxuICAgIGNvbnN0IGNhbEludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZShcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIGdvb2dsZUNhbGVuZGFyTmFtZVxuICAgICk7XG5cbiAgICAvLyBkZWxldGUgb2xkIHJlbWluZGVyc1xuICAgIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGRlbGV0ZVJlbWluZGVyc1dpdGhJZHMoW2V2ZW50SWRdLCBib2R5Py51c2VySWQpO1xuICAgIH1cblxuICAgIC8vIGRlbGV0ZSBvbGQgdGltZSBwcmVmZXJlbmNlc1xuICAgIGlmIChib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQoZXZlbnRJZCk7XG4gICAgfVxuXG4gICAgLy8gZ2V0IG9sZCBldmVudFxuICAgIGNvbnN0IG9sZEV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShldmVudElkKTtcblxuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFvbGRFdmVudD8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gb2xkIGV2ZW50IGZvdW5kPyEnKTtcbiAgICB9XG5cbiAgICAvLyBpZiBubyBwcmlvcml0eSB1c2Ugb2xkXG4gICAgaWYgKCFib2R5Py5wcmlvcml0eSkge1xuICAgICAgYm9keS5wcmlvcml0eSA9IG9sZEV2ZW50LnByaW9yaXR5IHx8IDE7XG4gICAgfVxuXG4gICAgY29uc3QgYVdpdGhFbWFpbHMgPSBib2R5Py5hdHRlbmRlZXM/LmZpbHRlcigoYSkgPT4gISFhPy5lbWFpbCk7XG5cbiAgICBjb25zdCBhV2l0aENvbnRhY3RJbmZvcyA9IGF3YWl0IGdldFVzZXJDb250YWN0SW5mb3NHaXZlbklkcyhcbiAgICAgIGFXaXRoRW1haWxzPy5tYXAoKGEpID0+IGE/LmVtYWlsKVxuICAgICk7XG5cbiAgICBjb25zdCBhdHRlbmRlZXNGcm9tRXh0cmFjdGVkSlNPTiA9IGJvZHk/LmF0dGVuZGVlcyB8fCBbXTtcbiAgICBjb25zdCBhdHRlbmRlZXM6IEF0dGVuZGVlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IGEgb2YgYXR0ZW5kZWVzRnJvbUV4dHJhY3RlZEpTT04pIHtcbiAgICAgIGNvbnN0IGNvbnRhY3QgPSBhd2FpdCBmaW5kQ29udGFjdEJ5RW1haWxHaXZlblVzZXJJZChcbiAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICBhLmVtYWlsXG4gICAgICApO1xuICAgICAgY29uc3QgdXNlcklkRm91bmQgPSBhV2l0aENvbnRhY3RJbmZvcz8uZmluZCgoYikgPT4gYj8uaWQgPT09IGE/LmVtYWlsKTtcblxuICAgICAgY29uc3QgYXR0ZW5kZWU6IEF0dGVuZGVlVHlwZSA9IHtcbiAgICAgICAgaWQ6IHVzZXJJZEZvdW5kPy51c2VySWQgfHwgdXVpZCgpLFxuICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgbmFtZTpcbiAgICAgICAgICBhPy5uYW1lIHx8XG4gICAgICAgICAgY29udGFjdD8ubmFtZSB8fFxuICAgICAgICAgIGAke2NvbnRhY3Q/LmZpcnN0TmFtZX0gJHtjb250YWN0Py5sYXN0TmFtZX1gLFxuICAgICAgICBjb250YWN0SWQ6IGNvbnRhY3Q/LmlkLFxuICAgICAgICBlbWFpbHM6IFt7IHByaW1hcnk6IHRydWUsIHZhbHVlOiBhPy5lbWFpbCB9XSxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICB9O1xuXG4gICAgICBhdHRlbmRlZXMucHVzaChhdHRlbmRlZSk7XG4gICAgfVxuXG4gICAgLy8gdGFrZSBjYXJlIG9mIHJlY3VycmVuY2VcbiAgICBjb25zdCByZWN1ciA9IGNyZWF0ZVJSdWxlU3RyaW5nKFxuICAgICAgYm9keT8ucmVjdXI/LmZyZXF1ZW5jeSxcbiAgICAgIGJvZHk/LnJlY3VyPy5pbnRlcnZhbCxcbiAgICAgIGJvZHk/LnJlY3VyPy5ieVdlZWtEYXksXG4gICAgICBib2R5Py5yZWN1cj8ub2NjdXJyZW5jZSxcbiAgICAgIGJvZHk/LnJlY3VyPy5lbmREYXRlLFxuICAgICAgYm9keT8ucmVjdXI/LmJ5TW9udGhEYXlcbiAgICApO1xuXG4gICAgbGV0IGNvbmZlcmVuY2U6IENvbmZlcmVuY2VUeXBlIHwge30gPSB7fTtcblxuICAgIC8vIGNvbmZlcmVuY2U6IGNyZWF0ZSAvIHVwZGF0ZSBhbmQgc3RvcmUgaW4gZGJcbiAgICBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCAmJiAhb2xkRXZlbnQuY29uZmVyZW5jZUlkKSB7XG4gICAgICAvLyBjcmVhdGUgY29uZmVyZW5jZSBvYmplY3RcbiAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbihib2R5Py51c2VySWQpO1xuXG4gICAgICBjb25mZXJlbmNlID1cbiAgICAgICAgem9vbVRva2VuICYmIGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJ1xuICAgICAgICAgID8ge31cbiAgICAgICAgICA6IHtcbiAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgICAgICBhcHA6ICdnb29nbGUnLFxuICAgICAgICAgICAgICBuYW1lOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgICAgICAgICAgICBub3RlczogYm9keT8uZGVzY3JpcHRpb24gfHwgYm9keT8udGl0bGUsXG4gICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgICAgICAgICB9O1xuXG4gICAgICBpZiAoem9vbVRva2VuICYmIGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJykge1xuICAgICAgICBjb25zb2xlLmxvZyh6b29tVG9rZW4sICcgem9vbVRva2VuIGluc2lkZSBpZiAoem9vbVRva2VuKScpO1xuXG4gICAgICAgIGNvbnN0IHpvb21PYmplY3QgPSBhd2FpdCBjcmVhdGVab29tTWVldGluZyhcbiAgICAgICAgICB6b29tVG9rZW4sXG4gICAgICAgICAgYm9keT8uc3RhcnREYXRlLFxuICAgICAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgIGJvZHk/LnRpdGxlLFxuICAgICAgICAgIGJvZHk/LmR1cmF0aW9uLFxuICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucHJpbWFyeUVtYWlsLFxuICAgICAgICAgIGJvZHk/LmF0dGVuZGVlcz8ubWFwKChhKSA9PiBhPy5lbWFpbCksXG4gICAgICAgICAgYm9keT8ucmVjdXIgYXMgYW55XG4gICAgICAgICk7XG5cbiAgICAgICAgY29uc29sZS5sb2coem9vbU9iamVjdCwgJyB6b29tT2JqZWN0IGFmdGVyIGNyZWF0ZVpvb21NZWV0aW5nJyk7XG5cbiAgICAgICAgaWYgKHpvb21PYmplY3QpIHtcbiAgICAgICAgICBjb25mZXJlbmNlID0ge1xuICAgICAgICAgICAgaWQ6IGAke3pvb21PYmplY3Q/LmlkfWAsXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5pZCxcbiAgICAgICAgICAgIGFwcDogJ3pvb20nLFxuICAgICAgICAgICAgbmFtZTogem9vbU9iamVjdD8uYWdlbmRhLFxuICAgICAgICAgICAgbm90ZXM6IHpvb21PYmplY3Q/LmFnZW5kYSxcbiAgICAgICAgICAgIGpvaW5Vcmw6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgICAgICAgICAgc3RhcnRVcmw6IHpvb21PYmplY3Q/LnN0YXJ0X3VybCxcbiAgICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgICBlbnRyeVBvaW50czogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgZW50cnlQb2ludFR5cGU6ICd2aWRlbycsXG4gICAgICAgICAgICAgICAgbGFiZWw6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgICAgICAgICAgICAgIHBhc3N3b3JkOiB6b29tT2JqZWN0Py5wYXNzd29yZCxcbiAgICAgICAgICAgICAgICB1cmk6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9IGFzIENvbmZlcmVuY2VUeXBlO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIC8vIGluc2VydCBuZXcgY29uZmVyZW5jZVxuICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKTtcbiAgICB9IGVsc2UgaWYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgJiYgb2xkRXZlbnQuY29uZmVyZW5jZUlkKSB7XG4gICAgICAvLyBnZXQgb2xkIGNvbmZlcmVuY2Ugb2JqZWN0XG4gICAgICBjb25zdCBvbGRDb25mZXJlbmNlID0gYXdhaXQgZ2V0Q29uZmVyZW5jZUdpdmVuSWQob2xkRXZlbnQ/LmNvbmZlcmVuY2VJZCk7XG4gICAgICAvLyBjcmVhdGUgY29uZmVyZW5jZSBvYmplY3RcbiAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbihib2R5Py51c2VySWQpO1xuXG4gICAgICAvLyB1cGRhdGVab29tTWVldGluZ1xuICAgICAgY29uZmVyZW5jZSA9XG4gICAgICAgIHpvb21Ub2tlbiAmJiBib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbSdcbiAgICAgICAgICA/IHt9XG4gICAgICAgICAgOiB7XG4gICAgICAgICAgICAgIC4uLm9sZENvbmZlcmVuY2UsXG4gICAgICAgICAgICAgIGlkOiBvbGRFdmVudD8uY29uZmVyZW5jZUlkLFxuICAgICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICAgICAgICAgIGFwcDogJ2dvb2dsZScsXG4gICAgICAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgICAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAgICAgICAgIH07XG5cbiAgICAgIGlmIChib2R5Py5jb25mZXJlbmNlQXBwID09PSBvbGRDb25mZXJlbmNlLmFwcCkge1xuICAgICAgICBjb25zb2xlLmxvZyh6b29tVG9rZW4sICcgem9vbVRva2VuIGluc2lkZSBpZiAoem9vbVRva2VuKScpO1xuXG4gICAgICAgIGlmICh6b29tVG9rZW4gJiYgYm9keT8uY29uZmVyZW5jZUFwcCA9PT0gJ3pvb20nKSB7XG4gICAgICAgICAgYXdhaXQgdXBkYXRlWm9vbU1lZXRpbmcoXG4gICAgICAgICAgICB6b29tVG9rZW4sXG4gICAgICAgICAgICBwYXJzZUludChvbGRFdmVudD8uY29uZmVyZW5jZUlkLCAxMCksXG4gICAgICAgICAgICBib2R5Py5zdGFydERhdGUsXG4gICAgICAgICAgICBib2R5Py50aW1lem9uZSxcbiAgICAgICAgICAgIGJvZHk/LnRpdGxlIHx8IGJvZHk/LmRlc2NyaXB0aW9uLFxuICAgICAgICAgICAgYm9keT8uZHVyYXRpb24gfHwgb2xkRXZlbnQ/LmR1cmF0aW9uLFxuICAgICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnByaW1hcnlFbWFpbCxcbiAgICAgICAgICAgIGF0dGVuZGVlcz8ubGVuZ3RoID4gMFxuICAgICAgICAgICAgICA/IGF0dGVuZGVlcz8ubWFwKChhKSA9PiBhPy5lbWFpbHM/LlswXT8udmFsdWUpXG4gICAgICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgICAgYm9keT8ucmVjdXIgYXMgYW55XG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbmZlcmVuY2UgPSB7XG4gICAgICAgICAgICAuLi5vbGRDb25mZXJlbmNlLFxuICAgICAgICAgICAgaWQ6IG9sZENvbmZlcmVuY2U/LmlkLFxuICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgICBjYWxlbmRhcklkOiBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAgICAgICAgIGFwcDogJ3pvb20nLFxuICAgICAgICAgICAgbmFtZTogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBvbGRFdmVudD8ubm90ZXMsXG4gICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgIH0gYXMgQ29uZmVyZW5jZVR5cGU7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uZmVyZW5jZSA9IHtcbiAgICAgICAgICAgIC4uLm9sZENvbmZlcmVuY2UsXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgICAgYXBwOiAnZ29vZ2xlJyxcbiAgICAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgICAgICAgICBub3RlczogYm9keT8uZGVzY3JpcHRpb24gfHwgYm9keT8udGl0bGUsXG4gICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgICAgICAgIH07XG4gICAgICAgIH1cblxuICAgICAgICAvLyBpbnNlcnQgbmV3IGNvbmZlcmVuY2VcbiAgICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKTtcbiAgICAgIH0gZWxzZSBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCAhPT0gb2xkQ29uZmVyZW5jZS5hcHApIHtcbiAgICAgICAgLy8gY3JlYXRlIGNvbmZlcmVuY2Ugb2JqZWN0XG4gICAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbihib2R5Py51c2VySWQpO1xuXG4gICAgICAgIGNvbmZlcmVuY2UgPVxuICAgICAgICAgIHpvb21Ub2tlbiAmJiBib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbSdcbiAgICAgICAgICAgID8ge31cbiAgICAgICAgICAgIDoge1xuICAgICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICAgICAgICAgICAgYXBwOiAnZ29vZ2xlJyxcbiAgICAgICAgICAgICAgICBuYW1lOiBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5uYW1lLFxuICAgICAgICAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgICAgICAgICAgICB9O1xuXG4gICAgICAgIGlmICh6b29tVG9rZW4gJiYgYm9keT8uY29uZmVyZW5jZUFwcCA9PT0gJ3pvb20nKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coem9vbVRva2VuLCAnIHpvb21Ub2tlbiBpbnNpZGUgaWYgKHpvb21Ub2tlbiknKTtcblxuICAgICAgICAgIGNvbnN0IHpvb21PYmplY3QgPSBhd2FpdCBjcmVhdGVab29tTWVldGluZyhcbiAgICAgICAgICAgIHpvb21Ub2tlbixcbiAgICAgICAgICAgIGJvZHk/LnN0YXJ0RGF0ZSxcbiAgICAgICAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgICAgYm9keT8udGl0bGUgfHwgYm9keT8uZGVzY3JpcHRpb24sXG4gICAgICAgICAgICBib2R5Py5kdXJhdGlvbixcbiAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5wcmltYXJ5RW1haWwsXG4gICAgICAgICAgICBib2R5Py5hdHRlbmRlZXM/Lm1hcCgoYSkgPT4gYT8uZW1haWwpLFxuICAgICAgICAgICAgYm9keT8ucmVjdXIgYXMgYW55XG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnNvbGUubG9nKHpvb21PYmplY3QsICcgem9vbU9iamVjdCBhZnRlciBjcmVhdGVab29tTWVldGluZycpO1xuXG4gICAgICAgICAgaWYgKHpvb21PYmplY3QpIHtcbiAgICAgICAgICAgIGNvbmZlcmVuY2UgPSB7XG4gICAgICAgICAgICAgIGlkOiBgJHt6b29tT2JqZWN0Py5pZH1gLFxuICAgICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmlkLFxuICAgICAgICAgICAgICBhcHA6ICd6b29tJyxcbiAgICAgICAgICAgICAgbmFtZTogem9vbU9iamVjdD8uYWdlbmRhLFxuICAgICAgICAgICAgICBub3Rlczogem9vbU9iamVjdD8uYWdlbmRhLFxuICAgICAgICAgICAgICBqb2luVXJsOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAgICAgICAgICAgc3RhcnRVcmw6IHpvb21PYmplY3Q/LnN0YXJ0X3VybCxcbiAgICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgICAgICAgZW50cnlQb2ludHM6IFtcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBlbnRyeVBvaW50VHlwZTogJ3ZpZGVvJyxcbiAgICAgICAgICAgICAgICAgIGxhYmVsOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAgICAgICAgICAgICAgIHBhc3N3b3JkOiB6b29tT2JqZWN0Py5wYXNzd29yZCxcbiAgICAgICAgICAgICAgICAgIHVyaTogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgXSxcbiAgICAgICAgICAgIH0gYXMgQ29uZmVyZW5jZVR5cGU7XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgLy8gZGVsZXRlIG9sZCBjb25mZXJlbmNlXG4gICAgICAgIGF3YWl0IGRlbGV0ZUNvbmZlcmVuY2VHaXZlbklkKG9sZENvbmZlcmVuY2U/LmlkKTtcbiAgICAgICAgaWYgKG9sZENvbmZlcmVuY2UuYXBwID09PSAnem9vbScpIHtcbiAgICAgICAgICBhd2FpdCBkZWxldGVab29tTWVldGluZyh6b29tVG9rZW4sIHBhcnNlSW50KG9sZENvbmZlcmVuY2UuaWQsIDEwKSk7XG4gICAgICAgIH1cbiAgICAgICAgLy8gaW5zZXJ0IG5ldyBjb25mZXJlbmNlXG4gICAgICAgIGF3YWl0IHVwc2VydENvbmZlcmVuY2UoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk7XG4gICAgICB9XG4gICAgfVxuICAgIC8vIGlmIGV4aXN0aW5nIGJ1ZmZlciB0aW1lc1xuICAgIC8vIGRlbGV0ZSBvbGQgYW5kIGNyZWF0ZSBuZXcgb25lcyBsYXRlciBvblxuICAgIGlmIChcbiAgICAgIChvbGRFdmVudD8ucHJlRXZlbnRJZCAmJiBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCkgfHxcbiAgICAgIChvbGRFdmVudD8ucG9zdEV2ZW50SWQgJiYgYm9keT8uYnVmZmVyVGltZT8uYWZ0ZXJFdmVudClcbiAgICApIHtcbiAgICAgIC8vIGRlbGV0ZSBidWZmZXJlIHRpbWVzIGlmIGFueVxuXG4gICAgICBpZiAob2xkRXZlbnQ/LnByZUV2ZW50SWQpIHtcbiAgICAgICAgY29uc3QgcHJlRXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KG9sZEV2ZW50Py5wcmVFdmVudElkKTtcbiAgICAgICAgYXdhaXQgZGVsZXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIHByZUV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgIHByZUV2ZW50Py5ldmVudElkLFxuICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlXG4gICAgICAgICk7XG4gICAgICAgIGF3YWl0IGRlbGV0ZUV2ZW50R2l2ZW5JZChvbGRFdmVudD8ucHJlRXZlbnRJZCk7XG4gICAgICB9XG5cbiAgICAgIGlmIChvbGRFdmVudD8ucG9zdEV2ZW50SWQpIHtcbiAgICAgICAgY29uc3QgcG9zdEV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShvbGRFdmVudD8ucG9zdEV2ZW50SWQpO1xuICAgICAgICBhd2FpdCBkZWxldGVHb29nbGVFdmVudChcbiAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgcG9zdEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgIHBvc3RFdmVudD8uZXZlbnRJZCxcbiAgICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZVxuICAgICAgICApO1xuICAgICAgICBhd2FpdCBkZWxldGVFdmVudEdpdmVuSWQob2xkRXZlbnQ/LnBvc3RFdmVudElkKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBjcmVhdGUgbmV3IHRpbWUgcHJlZmVyZW5jZXMgYW5kIHByaW9yaXR5XG4gICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlczogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IHRpbWVwcmVmZXJlbmNlIG9mIGJvZHk/LnRpbWVQcmVmZXJlbmNlcykge1xuICAgICAgaWYgKHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBmb3IgKGNvbnN0IGRheU9mV2VlayBvZiB0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWspIHtcbiAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICAgIGRheU9mV2VlazogRGF5T2ZXZWVrRW51bVtkYXlPZldlZWtdLFxuICAgICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICB9O1xuXG4gICAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgIH07XG5cbiAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gY3JlYXRlIG5ldyByZW1pbmRlcnMgZm9yIHVwZGF0ZWQgZXZlbnRcbiAgICBjb25zdCByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ6IFJlbWluZGVyVHlwZVtdID0gW107XG5cbiAgICBpZiAoYm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBuZXdSZW1pbmRlcnM6IFJlbWluZGVyVHlwZVtdID0gYm9keT8ucmVtaW5kZXJzLm1hcCgocikgPT4gKHtcbiAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgIGV2ZW50SWQsIC8vIGdlbmVyYXRlZElkXG4gICAgICAgIHRpbWV6b25lOiBib2R5Py50aW1lem9uZSxcbiAgICAgICAgbWludXRlczogcixcbiAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgfSkpO1xuXG4gICAgICByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQucHVzaCguLi5uZXdSZW1pbmRlcnMpO1xuICAgIH1cblxuICAgIC8vIHBhdGNoR29vZ2xlRXZlbnRcbiAgICBjb25zdCBzdGFydERhdGVUaW1lID0gc3RhcnREYXRlXG4gICAgICA/IGRheWpzKHN0YXJ0RGF0ZSkudHooYm9keT8udGltZXpvbmUpLmZvcm1hdCgpXG4gICAgICA6IG9sZEV2ZW50Py5zdGFydERhdGU7XG4gICAgY29uc3QgZW5kRGF0ZVRpbWUgPVxuICAgICAgc3RhcnREYXRlVGltZSAmJiBib2R5Py5kdXJhdGlvblxuICAgICAgICA/IGRheWpzKHN0YXJ0RGF0ZVRpbWUpXG4gICAgICAgICAgICAudHooYm9keT8udGltZXpvbmUpXG4gICAgICAgICAgICAuYWRkKGJvZHk/LmR1cmF0aW9uLCAnbWludXRlJylcbiAgICAgICAgICAgIC5mb3JtYXQoKVxuICAgICAgICA6IG9sZEV2ZW50Py5lbmREYXRlO1xuXG4gICAgLy8gbmVlZCB0byBiZSB1cGRhdGVkXG4gICAgY29uc3QgZXZlbnRUb1Vwc2VydExvY2FsOiBFdmVudFR5cGUgPSB7XG4gICAgICAuLi5vbGRFdmVudCxcbiAgICAgIGlkOiBldmVudElkLFxuICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICBhbGxEYXk6IGZhbHNlLFxuICAgICAgdGltZXpvbmU6IGJvZHk/LnRpbWV6b25lLFxuICAgICAgaXNQcmVFdmVudDogZmFsc2UsXG4gICAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgfTtcblxuICAgIGlmIChib2R5Py50aXRsZSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRpdGxlID0gYm9keT8udGl0bGU7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuc3VtbWFyeSA9IGJvZHk/LnRpdGxlO1xuICAgIH1cblxuICAgIGlmIChzdGFydERhdGUpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5zdGFydERhdGUgPSBkYXlqcyhzdGFydERhdGUpXG4gICAgICAgIC50eihib2R5Py50aW1lem9uZSlcbiAgICAgICAgLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGlmIChlbmREYXRlVGltZSAmJiBlbmREYXRlVGltZSAhPT0gb2xkRXZlbnQ/LmVuZERhdGUpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5lbmREYXRlID0gZGF5anMoc3RhcnREYXRlVGltZSlcbiAgICAgICAgLnR6KGJvZHk/LnRpbWV6b25lKVxuICAgICAgICAuYWRkKGJvZHk/LmR1cmF0aW9uLCAnbWludXRlJylcbiAgICAgICAgLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGlmIChib2R5Py5kdXJhdGlvbiAmJiBib2R5Py5kdXJhdGlvbiAhPT0gb2xkRXZlbnQ/LmR1cmF0aW9uKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuZHVyYXRpb24gPSBib2R5Py5kdXJhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8uaXNGb2xsb3dVcCkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmlzRm9sbG93VXAgPSBib2R5LmlzRm9sbG93VXA7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwubm90ZXMgPSBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8ucHJpb3JpdHkpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5wcmlvcml0eSA9IGJvZHkucHJpb3JpdHk7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnRyYW5zcGFyZW5jeSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRyYW5zcGFyZW5jeSA9IGJvZHkudHJhbnNwYXJlbmN5O1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eSA9IHRydWU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnZpc2liaWxpdHkpIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC52aXNpYmlsaXR5ID0gYm9keS52aXNpYmlsaXR5IGFzIFZpc2liaWxpdHlUeXBlO1xuICAgIH1cblxuICAgIGlmICgoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwuY29uZmVyZW5jZUlkID0gKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZDtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8uYnVmZmVyVGltZSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRpbWVCbG9ja2luZyA9IGJvZHkuYnVmZmVyVGltZTtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcgPSB0cnVlO1xuICAgIH1cblxuICAgIGlmIChib2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZSA9IHRydWU7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwubW9kaWZpYWJsZSA9IHRydWU7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkTW9kaWZpYWJsZSA9IHRydWU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFJlbWluZGVycyA9IHRydWU7XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnByaW9yaXR5ID4gMSkge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWwgPSB0cnVlO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLm1vZGlmaWFibGUgPSB0cnVlO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZE1vZGlmaWFibGUgPSB0cnVlO1xuICAgIH1cblxuICAgIGlmIChib2R5Py5kdXJhdGlvbikge1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnVzZXJNb2RpZmllZER1cmF0aW9uID0gdHJ1ZTtcbiAgICB9XG5cbiAgICBpZiAoYm9keT8ubG9jYXRpb24pIHtcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5sb2NhdGlvbiA9IHsgdGl0bGU6IGJvZHk/LmxvY2F0aW9uIH07XG4gICAgfVxuXG4gICAgaWYgKGJvZHk/LnJlY3VyKSB7XG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWwucmVjdXJyZW5jZSA9IHJlY3VyO1xuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnJlY3VycmVuY2VSdWxlID0ge1xuICAgICAgICBmcmVxdWVuY3k6IGJvZHk/LnJlY3VyPy5mcmVxdWVuY3ksXG4gICAgICAgIGludGVydmFsOiBib2R5Py5yZWN1cj8uaW50ZXJ2YWwsXG4gICAgICAgIGJ5V2Vla0RheTogYm9keT8ucmVjdXI/LmJ5V2Vla0RheSxcbiAgICAgICAgb2NjdXJyZW5jZTogYm9keT8ucmVjdXI/Lm9jY3VycmVuY2UsXG4gICAgICAgIGVuZERhdGU6IGJvZHk/LnJlY3VyPy5lbmREYXRlLFxuICAgICAgICBieU1vbnRoRGF5OiBib2R5Py5yZWN1cj8uYnlNb250aERheSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgZ29vZ2xlUmVtaW5kZXI6IEdvb2dsZVJlbWluZGVyVHlwZSA9IHtcbiAgICAgIG92ZXJyaWRlczogcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5tYXAoKHIpID0+ICh7XG4gICAgICAgIG1ldGhvZDogJ2VtYWlsJyxcbiAgICAgICAgbWludXRlczogcj8ubWludXRlcyxcbiAgICAgIH0pKSxcbiAgICAgIHVzZURlZmF1bHQ6IGZhbHNlLFxuICAgIH07XG5cbiAgICBhd2FpdCBwYXRjaEdvb2dsZUV2ZW50KFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmV2ZW50SWQsXG4gICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc3RhcnREYXRlLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5jb25mZXJlbmNlSWQgPyAxIDogMCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uc2VuZFVwZGF0ZXMsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICBib2R5Py5hdHRlbmRlZXM/Lm1hcCgoYSkgPT4gKHsgZW1haWw6IGE/LmVtYWlsIH0pKSxcbiAgICAgIChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uaWRcbiAgICAgICAgPyB7XG4gICAgICAgICAgICB0eXBlOlxuICAgICAgICAgICAgICAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmFwcCA9PT0gJ3pvb20nXG4gICAgICAgICAgICAgICAgPyAnYWRkT24nXG4gICAgICAgICAgICAgICAgOiAnaGFuZ291dHNNZWV0JyxcbiAgICAgICAgICAgIG5hbWU6IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8ubmFtZSxcbiAgICAgICAgICAgIGNvbmZlcmVuY2VJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5pZCxcbiAgICAgICAgICAgIGVudHJ5UG9pbnRzOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmVudHJ5UG9pbnRzLFxuICAgICAgICAgICAgY3JlYXRlUmVxdWVzdDpcbiAgICAgICAgICAgICAgKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5hcHAgPT09ICdnb29nbGUnXG4gICAgICAgICAgICAgICAgPyB7XG4gICAgICAgICAgICAgICAgICAgIHJlcXVlc3RJZDogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5yZXF1ZXN0SWQsXG4gICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VTb2x1dGlvbktleToge1xuICAgICAgICAgICAgICAgICAgICAgIHR5cGU6ICdoYW5nb3V0c01lZXQnLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIDogdW5kZWZpbmVkLFxuICAgICAgICAgIH1cbiAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnN1bW1hcnksXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lm5vdGVzLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50aW1lem9uZSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5Nb2RpZnksXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHJlY3VyLFxuICAgICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwID8gZ29vZ2xlUmVtaW5kZXIgOiB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRyYW5zcGFyZW5jeSxcbiAgICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udmlzaWJpbGl0eSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgICdkZWZhdWx0JyxcbiAgICAgIGJvZHk/LmxvY2F0aW9uLFxuICAgICAgdW5kZWZpbmVkXG4gICAgKTtcblxuICAgIC8vIGFkZCBidWZmZXIgdGltZVxuICAgIC8vIGFkZCBidWZmZXIgdGltZSBpZiBhbnlcbiAgICBpZiAoYm9keT8uYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCB8fCBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCkge1xuICAgICAgY29uc3QgcmV0dXJuVmFsdWVzID0gY3JlYXRlUHJlQW5kUG9zdEV2ZW50c0Zyb21FdmVudChcbiAgICAgICAgZXZlbnRUb1Vwc2VydExvY2FsLFxuICAgICAgICBib2R5Py5idWZmZXJUaW1lXG4gICAgICApO1xuXG4gICAgICBpZiAocmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50KSB7XG4gICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uaWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5lbmREYXRlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgIDAsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uc2VuZFVwZGF0ZXMsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py50aXRsZSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lm5vdGVzLFxuICAgICAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZWN1cixcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWRcbiAgICAgICAgKTtcblxuICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkO1xuICAgICAgICByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5ldmVudElkID0gZ29vZ2xlUmVzVmFsdWUuZ29vZ2xlRXZlbnRJZDtcbiAgICAgICAgcmV0dXJuVmFsdWVzLm5ld0V2ZW50LnBvc3RFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWQ7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50KSB7XG4gICAgICAgIGNvbnN0IGdvb2dsZVJlc1ZhbHVlOiBHb29nbGVSZXNUeXBlID0gYXdhaXQgY3JlYXRlR29vZ2xlRXZlbnQoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgICAgICAgIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmlkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmVuZERhdGUsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uc3RhcnREYXRlLFxuICAgICAgICAgIDAsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnNlbmRVcGRhdGVzLFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py50aXRsZSxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ub3RlcyxcbiAgICAgICAgICBib2R5Py50aW1lem9uZSxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgcmVjdXIsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgJ2RlZmF1bHQnLFxuICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgICB1bmRlZmluZWRcbiAgICAgICAgKTtcblxuICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuaWQgPSBnb29nbGVSZXNWYWx1ZS5pZDtcbiAgICAgICAgcmV0dXJuVmFsdWVzLmJlZm9yZUV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkO1xuICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucHJlRXZlbnRJZCA9IHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkO1xuICAgICAgfVxuXG4gICAgICAvLyBpbnNlcnQgZXZlbnRzXG4gICAgICBhd2FpdCB1cHNlcnRFdmVudHMoXG4gICAgICAgIFtcbiAgICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQsXG4gICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50LFxuICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQsXG4gICAgICAgIF0/LmZpbHRlcigoZSkgPT4gISFlKVxuICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgLy8gaW5zZXJ0IGV2ZW50c1xuICAgICAgYXdhaXQgdXBzZXJ0RXZlbnRzKFtldmVudFRvVXBzZXJ0TG9jYWxdKTtcbiAgICB9XG5cbiAgICAvLyB1cGRhdGUgcmVtaW5kZXJzXG4gICAgcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5mb3JFYWNoKChyKSA9PiAoeyAuLi5yLCBldmVudElkOiBvbGRFdmVudD8uaWQgfSkpO1xuXG4gICAgLy8gdXBkYXRlIHRpbWVQcmVmZXJlbmNlc1xuICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/LmZvckVhY2goKHB0KSA9PiAoeyAuLi5wdCwgZXZlbnRJZDogb2xkRXZlbnQ/LmlkIH0pKTtcblxuICAgIC8vIGluc2VydCByZW1pbmRlcnNcbiAgICBpZiAocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwKSB7XG4gICAgICBhd2FpdCBpbnNlcnRSZW1pbmRlcnMocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkKTtcbiAgICB9XG5cbiAgICAvLyBpbnNlcnQgdGltZSBwcmVmZXJlbmNlc1xuICAgIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG4gICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcyk7XG4gICAgfVxuXG4gICAgLy8gYWRkIHRyYWluaW5nIGZvciB0aW1lIHByZWZlcmVuY2VzIGFuZCBwcmlvcml0eVxuICAgIC8vIGNvbnZlcnQgdG8gdmVjdG9yIGZvciBzZWFyY2hcbiAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCB8fCBib2R5Py5wcmlvcml0eSA+IDEpIHtcbiAgICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuXG4gICAgICAvLyB0cmFpbiBldmVudFxuICAgICAgYXdhaXQgcHV0RGF0YUluVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoKFxuICAgICAgICBldmVudElkLFxuICAgICAgICBzZWFyY2hWZWN0b3IsXG4gICAgICAgIGJvZHk/LnVzZXJJZFxuICAgICAgKTtcbiAgICB9XG5cbiAgICAvLyB1cGRhdGUgYXR0ZW5kZWVzIGZvciBldmVudCBJZFxuICAgIGF3YWl0IHVwc2VydEF0dGVuZGVlc2ZvckV2ZW50KGF0dGVuZGVlcyk7XG5cbiAgICAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICByZXNwb25zZS5kYXRhID0gJ3N1Y2Nlc3NmdWxseSB1cGRhdGVkIG1lZXRpbmcnO1xuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGZpbmFsIHN0ZXAgdXBkYXRlIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NVcGRhdGVNZWV0aW5nUGVuZGluZyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICBkYXRlSlNPTkJvZHk6IERhdGVUaW1lSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmdcbik6IFByb21pc2U8UmVzcG9uc2VBY3Rpb25UeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IGR1cmF0aW9uID0gMDtcblxuICAgIGNvbnN0IHllYXIgPSBkYXRlSlNPTkJvZHk/LnllYXI7XG4gICAgY29uc3QgbW9udGggPSBkYXRlSlNPTkJvZHk/Lm1vbnRoO1xuICAgIGNvbnN0IGRheSA9IGRhdGVKU09OQm9keT8uZGF5O1xuICAgIGNvbnN0IGlzb1dlZWtkYXkgPSBkYXRlSlNPTkJvZHk/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ciA9IGRhdGVKU09OQm9keT8uaG91cjtcbiAgICBjb25zdCBtaW51dGUgPSBkYXRlSlNPTkJvZHk/Lm1pbnV0ZTtcbiAgICBjb25zdCBzdGFydFRpbWUgPSBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZTtcblxuICAgIGNvbnN0IG1lZXRpbmdTdGFydERhdGUgPSBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB5ZWFyLFxuICAgICAgbW9udGgsXG4gICAgICBkYXksXG4gICAgICBpc29XZWVrZGF5LFxuICAgICAgaG91cixcbiAgICAgIG1pbnV0ZSxcbiAgICAgIHN0YXJ0VGltZSxcbiAgICAgIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIGRhdGVKU09OQm9keT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICAvLyBnZXQgZGVmYXVsdCB2YWx1ZXNcbiAgICBjb25zdCBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzID1cbiAgICAgIGF3YWl0IGdldENoYXRNZWV0aW5nUHJlZmVyZW5jZUdpdmVuVXNlcklkKHVzZXJJZCk7XG5cbiAgICBpZiAoZGF0ZUpTT05Cb2R5Py5kdXJhdGlvbikge1xuICAgICAgZHVyYXRpb24gPSBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uO1xuICAgIH0gZWxzZSBpZiAoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUgJiYgZGF0ZUpTT05Cb2R5Py5lbmRUaW1lKSB7XG4gICAgICAvLyBsaWtlbHkgc3RhcnQgdGltZSBhbHNvIHByZXNlbnRcblxuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoZGF0ZUpTT05Cb2R5Py5zdGFydFRpbWUsICdISDptbScpO1xuICAgICAgY29uc3QgZW5kVGltZU9iamVjdCA9IGRheWpzKGRhdGVKU09OQm9keS5lbmRUaW1lLCAnSEg6bW0nKTtcblxuICAgICAgY29uc3QgbWludXRlcyA9IGVuZFRpbWVPYmplY3QuZGlmZihzdGFydFRpbWVPYmplY3QsICdtJyk7XG5cbiAgICAgIGlmIChtaW51dGVzID4gMCkge1xuICAgICAgICBkdXJhdGlvbiA9IG1pbnV0ZXM7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgJiYganNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSkge1xuICAgICAgY29uc3Qgc3RhcnRUaW1lT2JqZWN0ID0gZGF5anMoanNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lKTtcbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIHRha2UgY2FyZSBvZiBhbnkgcmVjdXJyaW5nIGRhdGVzXG4gICAgbGV0IHJlY3VyT2JqZWN0OiBSZWN1cnJlbmNlUnVsZVR5cGUgfCB7fSA9IHt9O1xuICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kpIHtcbiAgICAgIGNvbnN0IHJlY3VyRW5kRGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgICAgY3VycmVudFRpbWUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5tb250aCxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnN0YXJ0VGltZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICAgKTtcblxuICAgICAgcmVjdXJPYmplY3QgPSB7XG4gICAgICAgIGZyZXF1ZW5jeTpcbiAgICAgICAgICAoZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlKSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWw6XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCxcbiAgICAgIH07XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXkpIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlXZWVrRGF5ID1cbiAgICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5KSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLmJ5TW9udGhEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXk7XG4gICAgICB9XG5cbiAgICAgIGlmIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLm9jY3VycmVuY2UgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2U7XG4gICAgICB9XG5cbiAgICAgIGlmIChyZWN1ckVuZERhdGUgfHwganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZSkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5lbmREYXRlID1cbiAgICAgICAgICByZWN1ckVuZERhdGUgfHwganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBib2R5OiBVcGRhdGVNZWV0aW5nVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG9sZFRpdGxlOiBqc29uQm9keT8ucGFyYW1zPy5vbGRUaXRsZSxcbiAgICAgIGF0dGVuZGVlczoganNvbkJvZHk/LnBhcmFtcz8uYXR0ZW5kZWVzLFxuICAgICAgbWV0aG9kOiBkYXRlSlNPTkJvZHk/Lm1ldGhvZCBhcyBhbnksXG4gICAgICBkdXJhdGlvbixcbiAgICAgIGRlc2NyaXB0aW9uOiBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fCBqc29uQm9keT8ucGFyYW1zPy5ub3RlcyxcbiAgICAgIGNvbmZlcmVuY2VBcHA6IGpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCxcbiAgICAgIHN0YXJ0RGF0ZToganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8IG1lZXRpbmdTdGFydERhdGUsXG4gICAgICBidWZmZXJUaW1lOiBqc29uQm9keT8ucGFyYW1zPy5idWZmZXJUaW1lLFxuICAgICAgcmVtaW5kZXJzOiBqc29uQm9keT8ucGFyYW1zPy5hbGFybXMgfHwgW10sXG4gICAgICBwcmlvcml0eToganNvbkJvZHk/LnBhcmFtcz8ucHJpb3JpdHkgfHwgMSxcbiAgICAgIHRpbWVQcmVmZXJlbmNlczogZGF0ZUpTT05Cb2R5Py50aW1lUHJlZmVyZW5jZXMgfHwgW10sXG4gICAgICBsb2NhdGlvbjoganNvbkJvZHk/LnBhcmFtcz8ubG9jYXRpb24sXG4gICAgICB0cmFuc3BhcmVuY3k6IGpzb25Cb2R5Py5wYXJhbXM/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6IGpzb25Cb2R5Py5wYXJhbXM/LnZpc2liaWxpdHksXG4gICAgICBpc0ZvbGxvd1VwOiBqc29uQm9keT8ucGFyYW1zPy5pc0ZvbGxvd1VwLFxuICAgIH07XG5cbiAgICBpZiAoXG4gICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlXG4gICAgKSB7XG4gICAgICBib2R5LnJlY3VyID0gcmVjdXJPYmplY3QgYXMgYW55O1xuICAgIH1cbiAgICAvLyB2YWxpZGF0ZSBmb3IgbWlzc2luZyBmaWVsZHNcbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAndXBkYXRlTWVldGluZycsXG4gICAgfTtcblxuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICBjb25zdCBuZXdBdHRlbmRlZXM6IE11dGF0ZWRDYWxlbmRhckV4dHJhY3RlZEpTT05BdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgZm9yIChjb25zdCBhIG9mIGJvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQodXNlcklkLCBhPy5uYW1lKTtcbiAgICAgICAgaWYgKGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZSkge1xuICAgICAgICAgIGNvbnN0IHByaW1hcnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uZmluZCgoZSkgPT4gISFlLnByaW1hcnkpPy52YWx1ZTtcbiAgICAgICAgICBjb25zdCBhbnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZTtcbiAgICAgICAgICBuZXdBdHRlbmRlZXMucHVzaCh7IC4uLmEsIGVtYWlsOiBwcmltYXJ5RW1haWwgfHwgYW55RW1haWwgfSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChcbiAgICAgICAgICAgIHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMV0/LlsnYW5kJ10/LlsyXVxuICAgICAgICAgICk7XG4gICAgICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBib2R5O1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgICAgICB9O1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIG5ld0F0dGVuZGVlcy5wdXNoKGEpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGJvZHkuYXR0ZW5kZWVzID0gbmV3QXR0ZW5kZWVzO1xuXG4gICAgLy8gdmFsaWRhdGUgcmVtYWluaW5nIHJlcXVpcmVkIGZpZWxkc1xuICAgIGlmICghYm9keT8udGl0bGUpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzBdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBib2R5O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcFVwZGF0ZU1lZXRpbmcoXG4gICAgICBib2R5LFxuICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyxcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuXG4gICAgLy8gY29udmVydCB0byB2ZWN0b3IgZm9yIHNlYXJjaFxuICAgIC8vIGNvbnN0IHNlYXJjaFRpdGxlID0gYm9keT8ub2xkVGl0bGUgfHwgYm9keT8udGl0bGVcbiAgICAvLyBjb25zdCBzZWFyY2hWZWN0b3IgPSBhd2FpdCBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yKHNlYXJjaFRpdGxlKVxuXG4gICAgLy8gLy8gIGFsbEV2ZW50V2l0aEV2ZW50T3BlblNlYXJjaFxuICAgIC8vIC8vIGFsbEV2ZW50T3BlblNlYXJjaFxuICAgIC8vIGlmICghc3RhcnREYXRlKSB7XG4gICAgLy8gICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKVxuICAgIC8vIH1cblxuICAgIC8vIGlmICghZW5kRGF0ZSkge1xuICAgIC8vICAgICBlbmREYXRlID0gZGF5anMoKS5hZGQoNCwgJ3cnKS5mb3JtYXQoKVxuICAgIC8vIH1cblxuICAgIC8vIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaCh1c2VySWQsIHNlYXJjaFZlY3Rvciwgc3RhcnREYXRlLCBlbmREYXRlKVxuXG4gICAgLy8gY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkXG5cbiAgICAvLyAvLyB2YWxpZGF0ZSBmb3VuZCBldmVudFxuICAgIC8vIGlmICghaWQpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJ1xuICAgIC8vICAgICByZXR1cm4gcmVzcG9uc2VcbiAgICAvLyB9XG5cbiAgICAvLyBjb25zdCBldmVudElkID0gaWRcblxuICAgIC8vIC8vIGdldCBjbGllbnQgdHlwZVxuICAgIC8vIGNvbnN0IGNhbEludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZShcbiAgICAvLyAgICAgdXNlcklkLFxuICAgIC8vICAgICBnb29nbGVDYWxlbmRhck5hbWUsXG4gICAgLy8gKVxuXG4gICAgLy8gLy8gZGVsZXRlIG9sZCByZW1pbmRlcnNcbiAgICAvLyBpZiAoYm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSB7XG5cbiAgICAvLyAgICAgYXdhaXQgZGVsZXRlUmVtaW5kZXJzV2l0aElkcyhbZXZlbnRJZF0sIHVzZXJJZClcbiAgICAvLyB9XG5cbiAgICAvLyAvLyBkZWxldGUgb2xkIHRpbWUgcHJlZmVyZW5jZXNcbiAgICAvLyBpZiAoYm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgIGF3YWl0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQoZXZlbnRJZClcbiAgICAvLyB9XG5cbiAgICAvLyAvLyBnZXQgb2xkIGV2ZW50XG4gICAgLy8gY29uc3Qgb2xkRXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KGV2ZW50SWQpXG5cbiAgICAvLyAvLyB2YWxpZGF0ZVxuICAgIC8vIGlmICghb2xkRXZlbnQ/LmlkKSB7XG4gICAgLy8gICAgIHRocm93IG5ldyBFcnJvcignbm8gb2xkIGV2ZW50IGZvdW5kPyEnKVxuICAgIC8vIH1cblxuICAgIC8vIC8vIGlmIG5vIHByaW9yaXR5IHVzZSBvbGRcbiAgICAvLyBpZiAoIWJvZHk/LnByaW9yaXR5KSB7XG4gICAgLy8gICAgIGJvZHkucHJpb3JpdHkgPSBvbGRFdmVudC5wcmlvcml0eSB8fCAxXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gZmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWRcbiAgICAvLyAvLyBnZXQgYXR0ZW5kZWVzIHdpdGggcHJvdmlkZWQgZW1haWxzXG5cbiAgICAvLyAvLyBnZXQgaW5mbyBvZiBjb250YWN0cyB3aXRob3V0IGVtYWlscyBwcm92aWRlZCBhbmQgYXNzaWduIHZhbHVlc1xuICAgIC8vIGNvbnN0IG5ld0F0dGVuZGVlczogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZVtdID0gW11cblxuICAgIC8vIGZvciAoY29uc3QgYSBvZiBib2R5Py5hdHRlbmRlZXMpIHtcblxuICAgIC8vICAgICBpZiAoIWE/LmVtYWlsKSB7XG4gICAgLy8gICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQodXNlcklkLCBhPy5uYW1lKVxuICAgIC8vICAgICAgICAgaWYgKGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZSkge1xuICAgIC8vICAgICAgICAgICAgIGNvbnN0IHByaW1hcnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uZmluZChlID0+ICEhZS5wcmltYXJ5KT8udmFsdWVcbiAgICAvLyAgICAgICAgICAgICBjb25zdCBhbnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZVxuICAgIC8vICAgICAgICAgICAgIG5ld0F0dGVuZGVlcy5wdXNoKHsgLi4uYSwgZW1haWw6IHByaW1hcnlFbWFpbCB8fCBhbnlFbWFpbCB9KVxuICAgIC8vICAgICAgICAgfSBlbHNlIHtcbiAgICAvLyAgICAgICAgICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcydcbiAgICAvLyAgICAgICAgICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlsxXT8uWydhbmQnXT8uWzJdKVxuICAgIC8vICAgICAgICAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzXG4gICAgLy8gICAgICAgICB9XG4gICAgLy8gICAgIH0gZWxzZSB7XG4gICAgLy8gICAgICAgICBuZXdBdHRlbmRlZXMucHVzaChhKVxuICAgIC8vICAgICB9XG4gICAgLy8gfVxuXG4gICAgLy8gYm9keS5hdHRlbmRlZXMgPSBuZXdBdHRlbmRlZXNcblxuICAgIC8vIGNvbnN0IGFXaXRoRW1haWxzID0gYm9keT8uYXR0ZW5kZWVzPy5maWx0ZXIoYSA9PiAhIWE/LmVtYWlsKVxuXG4gICAgLy8gY29uc3QgYVdpdGhDb250YWN0SW5mb3MgPSBhd2FpdCBnZXRVc2VyQ29udGFjdEluZm9zR2l2ZW5JZHMoYVdpdGhFbWFpbHM/Lm1hcChhID0+IChhPy5lbWFpbCkpKVxuXG4gICAgLy8gY29uc3QgYXR0ZW5kZWVzRnJvbUV4dHJhY3RlZEpTT04gPSBib2R5Py5hdHRlbmRlZXMgfHwgW11cbiAgICAvLyBjb25zdCBhdHRlbmRlZXM6IEF0dGVuZGVlVHlwZVtdID0gW11cblxuICAgIC8vIGZvciAoY29uc3QgYSBvZiBhdHRlbmRlZXNGcm9tRXh0cmFjdGVkSlNPTikge1xuICAgIC8vICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZmluZENvbnRhY3RCeUVtYWlsR2l2ZW5Vc2VySWQodXNlcklkLCBhLmVtYWlsKVxuICAgIC8vICAgICBjb25zdCB1c2VySWRGb3VuZCA9IGFXaXRoQ29udGFjdEluZm9zPy5maW5kKGIgPT4gKGI/LmlkID09PSBhPy5lbWFpbCkpXG5cbiAgICAvLyAgICAgY29uc3QgYXR0ZW5kZWU6IEF0dGVuZGVlVHlwZSA9IHtcbiAgICAvLyAgICAgICAgIGlkOiB1c2VySWRGb3VuZD8udXNlcklkIHx8IHV1aWQoKSxcbiAgICAvLyAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgIG5hbWU6IGE/Lm5hbWUgfHwgY29udGFjdD8ubmFtZSB8fCBgJHtjb250YWN0Py5maXJzdE5hbWV9ICR7Y29udGFjdD8ubGFzdE5hbWV9YCxcbiAgICAvLyAgICAgICAgIGNvbnRhY3RJZDogY29udGFjdD8uaWQsXG4gICAgLy8gICAgICAgICBlbWFpbHM6IFt7IHByaW1hcnk6IHRydWUsIHZhbHVlOiBhPy5lbWFpbCB9XSxcbiAgICAvLyAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgLy8gICAgICAgICBldmVudElkLFxuICAgIC8vICAgICB9XG5cbiAgICAvLyAgICAgYXR0ZW5kZWVzLnB1c2goYXR0ZW5kZWUpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gdGFrZSBjYXJlIG9mIHJlY3VycmVuY2VcbiAgICAvLyBjb25zdCByZWN1ciA9IGNyZWF0ZVJSdWxlU3RyaW5nKGJvZHk/LnJlY3VyPy5mcmVxdWVuY3ksIGJvZHk/LnJlY3VyPy5pbnRlcnZhbCwgYm9keT8ucmVjdXI/LmJ5V2Vla0RheSwgYm9keT8ucmVjdXI/Lm9jY3VycmVuY2UsIGJvZHk/LnJlY3VyPy5lbmREYXRlLCBib2R5Py5yZWN1cj8uYnlNb250aERheSlcblxuICAgIC8vIGxldCBjb25mZXJlbmNlOiBDb25mZXJlbmNlVHlwZSB8IHt9ID0ge31cblxuICAgIC8vIC8vIGNvbmZlcmVuY2U6IGNyZWF0ZSAvIHVwZGF0ZSBhbmQgc3RvcmUgaW4gZGJcbiAgICAvLyBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCAmJiAhb2xkRXZlbnQuY29uZmVyZW5jZUlkKSB7XG5cbiAgICAvLyAgICAgLy8gY3JlYXRlIGNvbmZlcmVuY2Ugb2JqZWN0XG4gICAgLy8gICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbih1c2VySWQpXG5cbiAgICAvLyAgICAgY29uZmVyZW5jZSA9ICh6b29tVG9rZW4gJiYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJykpID8ge30gOiB7XG4gICAgLy8gICAgICAgICBpZDogdXVpZCgpLFxuICAgIC8vICAgICAgICAgdXNlcklkLFxuICAgIC8vICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICBhcHA6ICdnb29nbGUnLFxuICAgIC8vICAgICAgICAgbmFtZTogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAvLyAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAvLyAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgLy8gICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgLy8gICAgIH1cblxuICAgIC8vICAgICBpZiAoem9vbVRva2VuICYmIChib2R5Py5jb25mZXJlbmNlQXBwID09PSAnem9vbScpKSB7XG5cbiAgICAvLyAgICAgICAgIGNvbnNvbGUubG9nKHpvb21Ub2tlbiwgJyB6b29tVG9rZW4gaW5zaWRlIGlmICh6b29tVG9rZW4pJylcblxuICAgIC8vICAgICAgICAgY29uc3Qgem9vbU9iamVjdCA9IGF3YWl0IGNyZWF0ZVpvb21NZWV0aW5nKFxuICAgIC8vICAgICAgICAgICAgIHpvb21Ub2tlbixcbiAgICAvLyAgICAgICAgICAgICBib2R5Py5zdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgLy8gICAgICAgICAgICAgYm9keT8udGl0bGUsXG4gICAgLy8gICAgICAgICAgICAgZHVyYXRpb24sXG4gICAgLy8gICAgICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAvLyAgICAgICAgICAgICBkZWZhdWx0TWVldGluZ1ByZWZlcmVuY2VzPy5wcmltYXJ5RW1haWwsXG4gICAgLy8gICAgICAgICAgICAgYm9keT8uYXR0ZW5kZWVzPy5tYXAoYSA9PiBhPy5lbWFpbCksXG4gICAgLy8gICAgICAgICAgICAgYm9keT8ucmVjdXIgYXMgYW55LFxuICAgIC8vICAgICAgICAgKVxuXG4gICAgLy8gICAgICAgICBjb25zb2xlLmxvZyh6b29tT2JqZWN0LCAnIHpvb21PYmplY3QgYWZ0ZXIgY3JlYXRlWm9vbU1lZXRpbmcnKVxuXG4gICAgLy8gICAgICAgICBpZiAoem9vbU9iamVjdCkge1xuICAgIC8vICAgICAgICAgICAgIGNvbmZlcmVuY2UgPSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGlkOiBgJHt6b29tT2JqZWN0Py5pZH1gLFxuICAgIC8vICAgICAgICAgICAgICAgICB1c2VySWQ6IHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmlkLFxuICAgIC8vICAgICAgICAgICAgICAgICBhcHA6ICd6b29tJyxcbiAgICAvLyAgICAgICAgICAgICAgICAgbmFtZTogem9vbU9iamVjdD8uYWdlbmRhLFxuICAgIC8vICAgICAgICAgICAgICAgICBub3Rlczogem9vbU9iamVjdD8uYWdlbmRhLFxuICAgIC8vICAgICAgICAgICAgICAgICBqb2luVXJsOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAvLyAgICAgICAgICAgICAgICAgc3RhcnRVcmw6IHpvb21PYmplY3Q/LnN0YXJ0X3VybCxcbiAgICAvLyAgICAgICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIC8vICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZW50cnlQb2ludHM6IFt7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBlbnRyeVBvaW50VHlwZTogJ3ZpZGVvJyxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGxhYmVsOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHBhc3N3b3JkOiB6b29tT2JqZWN0Py5wYXNzd29yZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHVyaTogem9vbU9iamVjdD8uam9pbl91cmwsXG4gICAgLy8gICAgICAgICAgICAgICAgIH1dXG4gICAgLy8gICAgICAgICAgICAgfSBhcyBDb25mZXJlbmNlVHlwZVxuXG4gICAgLy8gICAgICAgICB9XG4gICAgLy8gICAgIH1cblxuICAgIC8vICAgICAvLyBpbnNlcnQgbmV3IGNvbmZlcmVuY2VcbiAgICAvLyAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKVxuXG4gICAgLy8gfSBlbHNlIGlmIChib2R5Py5jb25mZXJlbmNlQXBwICYmIG9sZEV2ZW50LmNvbmZlcmVuY2VJZCkge1xuICAgIC8vICAgICAvLyBnZXQgb2xkIGNvbmZlcmVuY2Ugb2JqZWN0XG4gICAgLy8gICAgIGNvbnN0IG9sZENvbmZlcmVuY2UgPSBhd2FpdCBnZXRDb25mZXJlbmNlR2l2ZW5JZChvbGRFdmVudD8uY29uZmVyZW5jZUlkKVxuICAgIC8vICAgICAvLyBjcmVhdGUgY29uZmVyZW5jZSBvYmplY3RcbiAgICAvLyAgICAgY29uc3Qgem9vbVRva2VuID0gYXdhaXQgZ2V0Wm9vbUFQSVRva2VuKHVzZXJJZClcblxuICAgIC8vICAgICAvLyB1cGRhdGVab29tTWVldGluZ1xuICAgIC8vICAgICBjb25mZXJlbmNlID0gKHpvb21Ub2tlbiAmJiAoYm9keT8uY29uZmVyZW5jZUFwcCA9PT0gJ3pvb20nKSkgPyB7fSA6IHtcbiAgICAvLyAgICAgICAgIC4uLm9sZENvbmZlcmVuY2UsXG4gICAgLy8gICAgICAgICBpZDogb2xkRXZlbnQ/LmNvbmZlcmVuY2VJZCxcbiAgICAvLyAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgIC8vICAgICAgICAgYXBwOiAnZ29vZ2xlJyxcbiAgICAvLyAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgLy8gICAgICAgICBub3RlczogYm9keT8uZGVzY3JpcHRpb24gfHwgYm9keT8udGl0bGUsXG4gICAgLy8gICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIC8vICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIC8vICAgICB9XG5cbiAgICAvLyAgICAgaWYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09IG9sZENvbmZlcmVuY2UuYXBwKSB7XG5cbiAgICAvLyAgICAgICAgIGNvbnNvbGUubG9nKHpvb21Ub2tlbiwgJyB6b29tVG9rZW4gaW5zaWRlIGlmICh6b29tVG9rZW4pJylcblxuICAgIC8vICAgICAgICAgaWYgKHpvb21Ub2tlbiAmJiAoYm9keT8uY29uZmVyZW5jZUFwcCA9PT0gJ3pvb20nKSkge1xuICAgIC8vICAgICAgICAgICAgIGF3YWl0IHVwZGF0ZVpvb21NZWV0aW5nKFxuICAgIC8vICAgICAgICAgICAgICAgICB6b29tVG9rZW4sXG4gICAgLy8gICAgICAgICAgICAgICAgIHBhcnNlSW50KG9sZEV2ZW50Py5jb25mZXJlbmNlSWQsIDEwKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgYm9keT8uc3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgICAgICAgICBib2R5Py50aW1lem9uZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgYm9keT8udGl0bGUgfHwgYm9keT8uZGVzY3JpcHRpb24sXG4gICAgLy8gICAgICAgICAgICAgICAgIGR1cmF0aW9uIHx8IGJvZHk/LmR1cmF0aW9uIHx8IG9sZEV2ZW50Py5kdXJhdGlvbixcbiAgICAvLyAgICAgICAgICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ucHJpbWFyeUVtYWlsLFxuICAgIC8vICAgICAgICAgICAgICAgICBhdHRlbmRlZXM/Lmxlbmd0aCA+IDAgPyBhdHRlbmRlZXM/Lm1hcChhID0+IGE/LmVtYWlscz8uWzBdPy52YWx1ZSkgOiB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgYm9keT8ucmVjdXIgYXMgYW55LFxuICAgIC8vICAgICAgICAgICAgIClcblxuICAgIC8vICAgICAgICAgICAgIGNvbmZlcmVuY2UgPSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIC4uLm9sZENvbmZlcmVuY2UsXG4gICAgLy8gICAgICAgICAgICAgICAgIGlkOiBvbGRDb25mZXJlbmNlPy5pZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIGNhbGVuZGFySWQ6IG9sZEV2ZW50Py5jYWxlbmRhcklkLFxuICAgIC8vICAgICAgICAgICAgICAgICBhcHA6ICd6b29tJyxcbiAgICAvLyAgICAgICAgICAgICAgICAgbmFtZTogZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcz8ubmFtZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uIHx8IG9sZEV2ZW50Py5ub3RlcyxcbiAgICAvLyAgICAgICAgICAgICAgICAgaXNIb3N0OiB0cnVlLFxuICAgIC8vICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAvLyAgICAgICAgICAgICB9IGFzIENvbmZlcmVuY2VUeXBlXG4gICAgLy8gICAgICAgICB9IGVsc2Uge1xuICAgIC8vICAgICAgICAgICAgIGNvbmZlcmVuY2UgPSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIC4uLm9sZENvbmZlcmVuY2UsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZDogb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIGFwcDogJ2dvb2dsZScsXG4gICAgLy8gICAgICAgICAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIG5vdGVzOiBib2R5Py5kZXNjcmlwdGlvbiB8fCBib2R5Py50aXRsZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgLy8gICAgICAgICAgICAgICAgIGlzSG9zdDogdHJ1ZSxcbiAgICAvLyAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIC8vIGluc2VydCBuZXcgY29uZmVyZW5jZVxuICAgIC8vICAgICAgICAgYXdhaXQgdXBzZXJ0Q29uZmVyZW5jZShjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKVxuXG4gICAgLy8gICAgIH0gZWxzZSBpZiAoYm9keT8uY29uZmVyZW5jZUFwcCAhPT0gb2xkQ29uZmVyZW5jZS5hcHApIHtcblxuICAgIC8vICAgICAgICAgLy8gY3JlYXRlIGNvbmZlcmVuY2Ugb2JqZWN0XG4gICAgLy8gICAgICAgICBjb25zdCB6b29tVG9rZW4gPSBhd2FpdCBnZXRab29tQVBJVG9rZW4odXNlcklkKVxuXG4gICAgLy8gICAgICAgICBjb25mZXJlbmNlID0gKHpvb21Ub2tlbiAmJiAoYm9keT8uY29uZmVyZW5jZUFwcCA9PT0gJ3pvb20nKSkgPyB7fSA6IHtcbiAgICAvLyAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgIC8vICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICBjYWxlbmRhcklkOiBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAvLyAgICAgICAgICAgICBhcHA6ICdnb29nbGUnLFxuICAgIC8vICAgICAgICAgICAgIG5hbWU6IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgLy8gICAgICAgICAgICAgbm90ZXM6IGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlLFxuICAgIC8vICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAvLyAgICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIGlmICh6b29tVG9rZW4gJiYgKGJvZHk/LmNvbmZlcmVuY2VBcHAgPT09ICd6b29tJykpIHtcblxuICAgIC8vICAgICAgICAgICAgIGNvbnNvbGUubG9nKHpvb21Ub2tlbiwgJyB6b29tVG9rZW4gaW5zaWRlIGlmICh6b29tVG9rZW4pJylcblxuICAgIC8vICAgICAgICAgICAgIGNvbnN0IHpvb21PYmplY3QgPSBhd2FpdCBjcmVhdGVab29tTWVldGluZyhcbiAgICAvLyAgICAgICAgICAgICAgICAgem9vbVRva2VuLFxuICAgIC8vICAgICAgICAgICAgICAgICBib2R5Py5zdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHRpbWV6b25lLFxuICAgIC8vICAgICAgICAgICAgICAgICBib2R5Py50aXRsZSB8fCBib2R5Py5kZXNjcmlwdGlvbixcbiAgICAvLyAgICAgICAgICAgICAgICAgZHVyYXRpb24sXG4gICAgLy8gICAgICAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/Lm5hbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXM/LnByaW1hcnlFbWFpbCxcbiAgICAvLyAgICAgICAgICAgICAgICAgYm9keT8uYXR0ZW5kZWVzPy5tYXAoYSA9PiBhPy5lbWFpbCksXG4gICAgLy8gICAgICAgICAgICAgICAgIGJvZHk/LnJlY3VyIGFzIGFueSxcbiAgICAvLyAgICAgICAgICAgICApXG5cbiAgICAvLyAgICAgICAgICAgICBjb25zb2xlLmxvZyh6b29tT2JqZWN0LCAnIHpvb21PYmplY3QgYWZ0ZXIgY3JlYXRlWm9vbU1lZXRpbmcnKVxuXG4gICAgLy8gICAgICAgICAgICAgaWYgKHpvb21PYmplY3QpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgY29uZmVyZW5jZSA9IHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGlkOiBgJHt6b29tT2JqZWN0Py5pZH1gLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkOiBvbGRFdmVudD8uaWQsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBhcHA6ICd6b29tJyxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIG5hbWU6IHpvb21PYmplY3Q/LmFnZW5kYSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIG5vdGVzOiB6b29tT2JqZWN0Py5hZ2VuZGEsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBqb2luVXJsOiB6b29tT2JqZWN0Py5qb2luX3VybCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHN0YXJ0VXJsOiB6b29tT2JqZWN0Py5zdGFydF91cmwsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBpc0hvc3Q6IHRydWUsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgZW50cnlQb2ludHM6IFt7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgZW50cnlQb2ludFR5cGU6ICd2aWRlbycsXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgbGFiZWw6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIHBhc3N3b3JkOiB6b29tT2JqZWN0Py5wYXNzd29yZCxcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICB1cmk6IHpvb21PYmplY3Q/LmpvaW5fdXJsLFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgfV1cbiAgICAvLyAgICAgICAgICAgICAgICAgfSBhcyBDb25mZXJlbmNlVHlwZVxuXG4gICAgLy8gICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIC8vIGRlbGV0ZSBvbGQgY29uZmVyZW5jZVxuICAgIC8vICAgICAgICAgYXdhaXQgZGVsZXRlQ29uZmVyZW5jZUdpdmVuSWQob2xkQ29uZmVyZW5jZT8uaWQpXG4gICAgLy8gICAgICAgICBpZiAob2xkQ29uZmVyZW5jZS5hcHAgPT09ICd6b29tJykge1xuICAgIC8vICAgICAgICAgICAgIGF3YWl0IGRlbGV0ZVpvb21NZWV0aW5nKHpvb21Ub2tlbiwgcGFyc2VJbnQob2xkQ29uZmVyZW5jZS5pZCwgMTApKVxuICAgIC8vICAgICAgICAgfVxuICAgIC8vICAgICAgICAgLy8gaW5zZXJ0IG5ldyBjb25mZXJlbmNlXG4gICAgLy8gICAgICAgICBhd2FpdCB1cHNlcnRDb25mZXJlbmNlKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpXG4gICAgLy8gICAgIH1cblxuICAgIC8vIH1cbiAgICAvLyAvLyBpZiBleGlzdGluZyBidWZmZXIgdGltZXNcbiAgICAvLyAvLyBkZWxldGUgb2xkIGFuZCBjcmVhdGUgbmV3IG9uZXMgbGF0ZXIgb25cbiAgICAvLyBpZiAoKG9sZEV2ZW50Py5wcmVFdmVudElkICYmIGJvZHk/LmJ1ZmZlclRpbWU/LmJlZm9yZUV2ZW50KSB8fCAob2xkRXZlbnQ/LnBvc3RFdmVudElkICYmIGJvZHk/LmJ1ZmZlclRpbWU/LmFmdGVyRXZlbnQpKSB7XG4gICAgLy8gICAgIC8vIGRlbGV0ZSBidWZmZXJlIHRpbWVzIGlmIGFueVxuXG4gICAgLy8gICAgIGlmIChvbGRFdmVudD8ucHJlRXZlbnRJZCkge1xuICAgIC8vICAgICAgICAgY29uc3QgcHJlRXZlbnQgPSBhd2FpdCBnZXRFdmVudEZyb21QcmltYXJ5S2V5KG9sZEV2ZW50Py5wcmVFdmVudElkKVxuICAgIC8vICAgICAgICAgYXdhaXQgZGVsZXRlR29vZ2xlRXZlbnQodXNlcklkLCBwcmVFdmVudD8uY2FsZW5kYXJJZCwgcHJlRXZlbnQ/LmV2ZW50SWQsIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlKVxuICAgIC8vICAgICAgICAgYXdhaXQgZGVsZXRlRXZlbnRHaXZlbklkKG9sZEV2ZW50Py5wcmVFdmVudElkKVxuXG4gICAgLy8gICAgIH1cblxuICAgIC8vICAgICBpZiAob2xkRXZlbnQ/LnBvc3RFdmVudElkKSB7XG5cbiAgICAvLyAgICAgICAgIGNvbnN0IHBvc3RFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkob2xkRXZlbnQ/LnBvc3RFdmVudElkKVxuICAgIC8vICAgICAgICAgYXdhaXQgZGVsZXRlR29vZ2xlRXZlbnQodXNlcklkLCBwb3N0RXZlbnQ/LmNhbGVuZGFySWQsIHBvc3RFdmVudD8uZXZlbnRJZCwgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUpXG4gICAgLy8gICAgICAgICBhd2FpdCBkZWxldGVFdmVudEdpdmVuSWQob2xkRXZlbnQ/LnBvc3RFdmVudElkKVxuICAgIC8vICAgICB9XG4gICAgLy8gfVxuXG4gICAgLy8gLy8gY3JlYXRlIG5ldyB0aW1lIHByZWZlcmVuY2VzIGFuZCBwcmlvcml0eVxuICAgIC8vIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSA9IFtdXG5cbiAgICAvLyBmb3IgKGNvbnN0IHRpbWVwcmVmZXJlbmNlIG9mIGJvZHk/LnRpbWVQcmVmZXJlbmNlcykge1xuXG4gICAgLy8gICAgIGlmICh0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWs/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgICAgIGZvciAoY29uc3QgZGF5T2ZXZWVrIG9mIHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaykge1xuXG4gICAgLy8gICAgICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgIC8vICAgICAgICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICBldmVudElkLFxuICAgIC8vICAgICAgICAgICAgICAgICBkYXlPZldlZWs6IERheU9mV2Vla0VudW1bZGF5T2ZXZWVrXSxcbiAgICAvLyAgICAgICAgICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKVxuICAgIC8vICAgICAgICAgfVxuICAgIC8vICAgICB9IGVsc2Uge1xuXG4gICAgLy8gICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgLy8gICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgICAgICBldmVudElkLFxuICAgIC8vICAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgIC8vICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSlcbiAgICAvLyAgICAgfVxuXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gY3JlYXRlIG5ldyByZW1pbmRlcnMgZm9yIHVwZGF0ZWQgZXZlbnRcbiAgICAvLyBjb25zdCByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ6IFJlbWluZGVyVHlwZVtdID0gW11cblxuICAgIC8vIGlmIChib2R5Py5yZW1pbmRlcnM/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgY29uc3QgbmV3UmVtaW5kZXJzOiBSZW1pbmRlclR5cGVbXSA9IGJvZHk/LnJlbWluZGVycy5tYXAociA9PiAoe1xuICAgIC8vICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgIGV2ZW50SWQsIC8vIGdlbmVyYXRlZElkXG4gICAgLy8gICAgICAgICB0aW1lem9uZSxcbiAgICAvLyAgICAgICAgIG1pbnV0ZXM6IHIsXG4gICAgLy8gICAgICAgICB1c2VEZWZhdWx0OiBmYWxzZSxcbiAgICAvLyAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgZGVsZXRlZDogZmFsc2UsXG4gICAgLy8gICAgIH0pKVxuXG4gICAgLy8gICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZC5wdXNoKC4uLm5ld1JlbWluZGVycylcbiAgICAvLyB9XG5cbiAgICAvLyAvLyBwYXRjaEdvb2dsZUV2ZW50XG4gICAgLy8gY29uc3Qgc3RhcnREYXRlVGltZSA9IHN0YXJ0RGF0ZSA/IGRheWpzKHN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgpIDogb2xkRXZlbnQ/LnN0YXJ0RGF0ZVxuICAgIC8vIGNvbnN0IGVuZERhdGVUaW1lID0gKHN0YXJ0RGF0ZVRpbWUgJiYgZHVyYXRpb24pID8gZGF5anMoc3RhcnREYXRlVGltZSkudHoodGltZXpvbmUpLmFkZChkdXJhdGlvbiwgJ21pbnV0ZScpLmZvcm1hdCgpXG4gICAgLy8gICAgIDogb2xkRXZlbnQ/LmVuZERhdGVcblxuICAgIC8vIC8vIG5lZWQgdG8gYmUgdXBkYXRlZFxuICAgIC8vIGNvbnN0IGV2ZW50VG9VcHNlcnRMb2NhbDogRXZlbnRUeXBlID0ge1xuICAgIC8vICAgICAuLi5vbGRFdmVudCxcbiAgICAvLyAgICAgaWQ6IGV2ZW50SWQsXG4gICAgLy8gICAgIHVzZXJJZCxcbiAgICAvLyAgICAgYWxsRGF5OiBmYWxzZSxcbiAgICAvLyAgICAgdGltZXpvbmUsXG4gICAgLy8gICAgIGlzUHJlRXZlbnQ6IGZhbHNlLFxuICAgIC8vICAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgLy8gICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8udGl0bGUpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnRpdGxlID0gYm9keT8udGl0bGVcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnN1bW1hcnkgPSBib2R5Py50aXRsZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChzdGFydERhdGUpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnN0YXJ0RGF0ZSA9IGRheWpzKHN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgpXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGVuZERhdGVUaW1lICYmIChlbmREYXRlVGltZSAhPT0gb2xkRXZlbnQ/LmVuZERhdGUpKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5lbmREYXRlID0gZGF5anMoc3RhcnREYXRlVGltZSkudHoodGltZXpvbmUpLmFkZChkdXJhdGlvbiwgJ21pbnV0ZScpLmZvcm1hdCgpXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGR1cmF0aW9uICYmIChkdXJhdGlvbiAhPT0gb2xkRXZlbnQ/LmR1cmF0aW9uKSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwuZHVyYXRpb24gPSBkdXJhdGlvblxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5pc0ZvbGxvd1VwKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5pc0ZvbGxvd1VwID0gYm9keS5pc0ZvbGxvd1VwXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5ub3RlcyA9IGJvZHk/LmRlc2NyaXB0aW9uIHx8IGJvZHk/LnRpdGxlXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnByaW9yaXR5KSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5wcmlvcml0eSA9IGJvZHkucHJpb3JpdHlcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8udHJhbnNwYXJlbmN5KSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC50cmFuc3BhcmVuY3kgPSBib2R5LnRyYW5zcGFyZW5jeVxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5ID0gdHJ1ZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py52aXNpYmlsaXR5KSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC52aXNpYmlsaXR5ID0gYm9keS52aXNpYmlsaXR5IGFzIFZpc2liaWxpdHlUeXBlXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uaWQpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLmNvbmZlcmVuY2VJZCA9IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uaWRcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8uYnVmZmVyVGltZSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudGltZUJsb2NraW5nID0gYm9keS5idWZmZXJUaW1lXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcgPSB0cnVlXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UgPSB0cnVlXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5tb2RpZmlhYmxlID0gdHJ1ZVxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkTW9kaWZpYWJsZSA9IHRydWVcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRSZW1pbmRlcnMgPSB0cnVlXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LnByaW9yaXR5ID4gMSkge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbCA9IHRydWVcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLm1vZGlmaWFibGUgPSB0cnVlXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC51c2VyTW9kaWZpZWRNb2RpZmlhYmxlID0gdHJ1ZVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChib2R5Py5kdXJhdGlvbikge1xuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwudXNlck1vZGlmaWVkRHVyYXRpb24gPSB0cnVlXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGJvZHk/LmxvY2F0aW9uKSB7XG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbC5sb2NhdGlvbiA9IHsgdGl0bGU6IGJvZHk/LmxvY2F0aW9uIH1cbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoYm9keT8ucmVjdXIpIHtcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsLnJlY3VycmVuY2UgPSByZWN1clxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWwucmVjdXJyZW5jZVJ1bGUgPSB7XG4gICAgLy8gICAgICAgICBmcmVxdWVuY3k6IGJvZHk/LnJlY3VyPy5mcmVxdWVuY3ksXG4gICAgLy8gICAgICAgICBpbnRlcnZhbDogYm9keT8ucmVjdXI/LmludGVydmFsLFxuICAgIC8vICAgICAgICAgYnlXZWVrRGF5OiBib2R5Py5yZWN1cj8uYnlXZWVrRGF5LFxuICAgIC8vICAgICAgICAgb2NjdXJyZW5jZTogYm9keT8ucmVjdXI/Lm9jY3VycmVuY2UsXG4gICAgLy8gICAgICAgICBlbmREYXRlOiBib2R5Py5yZWN1cj8uZW5kRGF0ZSxcbiAgICAvLyAgICAgICAgIGJ5TW9udGhEYXk6IGJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5LFxuICAgIC8vICAgICB9XG4gICAgLy8gfVxuXG4gICAgLy8gY29uc3QgZ29vZ2xlUmVtaW5kZXI6IEdvb2dsZVJlbWluZGVyVHlwZSA9IHtcbiAgICAvLyAgICAgb3ZlcnJpZGVzOiByZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQ/Lm1hcChyID0+ICh7IG1ldGhvZDogJ2VtYWlsJywgbWludXRlczogcj8ubWludXRlcyB9KSksXG4gICAgLy8gICAgIHVzZURlZmF1bHQ6IGZhbHNlLFxuICAgIC8vIH1cblxuICAgIC8vIGF3YWl0IHBhdGNoR29vZ2xlRXZlbnQoXG4gICAgLy8gICAgIHVzZXJJZCxcbiAgICAvLyAgICAgb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZXZlbnRJZCxcbiAgICAvLyAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZW5kRGF0ZSxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zdGFydERhdGUsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uY29uZmVyZW5jZUlkID8gMSA6IDAsXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zZW5kVXBkYXRlcyxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5hbnlvbmVDYW5BZGRTZWxmLFxuICAgIC8vICAgICBib2R5Py5hdHRlbmRlZXM/Lm1hcChhID0+ICh7IGVtYWlsOiBhPy5lbWFpbCB9KSksXG4gICAgLy8gICAgIChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uaWQgPyB7XG4gICAgLy8gICAgICAgICB0eXBlOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmFwcCA9PT0gJ3pvb20nID8gJ2FkZE9uJyA6ICdoYW5nb3V0c01lZXQnLFxuICAgIC8vICAgICAgICAgbmFtZTogKGNvbmZlcmVuY2UgYXMgQ29uZmVyZW5jZVR5cGUpPy5uYW1lLFxuICAgIC8vICAgICAgICAgY29uZmVyZW5jZUlkOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmlkLFxuICAgIC8vICAgICAgICAgZW50cnlQb2ludHM6IChjb25mZXJlbmNlIGFzIENvbmZlcmVuY2VUeXBlKT8uZW50cnlQb2ludHMsXG4gICAgLy8gICAgICAgICBjcmVhdGVSZXF1ZXN0OiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LmFwcCA9PT0gJ2dvb2dsZScgPyB7XG4gICAgLy8gICAgICAgICAgICAgcmVxdWVzdElkOiAoY29uZmVyZW5jZSBhcyBDb25mZXJlbmNlVHlwZSk/LnJlcXVlc3RJZCxcbiAgICAvLyAgICAgICAgICAgICBjb25mZXJlbmNlU29sdXRpb25LZXk6IHtcbiAgICAvLyAgICAgICAgICAgICAgICAgdHlwZTogJ2hhbmdvdXRzTWVldCcsXG4gICAgLy8gICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgfSA6IHVuZGVmaW5lZCxcbiAgICAvLyAgICAgfSA6IHVuZGVmaW5lZCxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5zdW1tYXJ5LFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lm5vdGVzLFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/LnRpbWV6b25lLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICBldmVudFRvVXBzZXJ0TG9jYWw/Lmd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy5ndWVzdHNDYW5Nb2RpZnksXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8uZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8ub3JpZ2luYWxTdGFydERhdGUsXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgcmVjdXIsXG4gICAgLy8gICAgIHJlbWluZGVyc1RvVXBkYXRlRXZlbnRJZD8ubGVuZ3RoID4gMCA/IGdvb2dsZVJlbWluZGVyIDogdW5kZWZpbmVkLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgZXZlbnRUb1Vwc2VydExvY2FsPy50cmFuc3BhcmVuY3ksXG4gICAgLy8gICAgIGV2ZW50VG9VcHNlcnRMb2NhbD8udmlzaWJpbGl0eSxcbiAgICAvLyAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgJ2RlZmF1bHQnLFxuICAgIC8vICAgICBib2R5Py5sb2NhdGlvbixcbiAgICAvLyAgICAgdW5kZWZpbmVkLFxuICAgIC8vIClcblxuICAgIC8vIC8vIGFkZCBidWZmZXIgdGltZVxuICAgIC8vIC8vIGFkZCBidWZmZXIgdGltZSBpZiBhbnlcbiAgICAvLyBpZiAoYm9keT8uYnVmZmVyVGltZT8uYWZ0ZXJFdmVudCB8fCBib2R5Py5idWZmZXJUaW1lPy5iZWZvcmVFdmVudCkge1xuXG4gICAgLy8gICAgIGNvbnN0IHJldHVyblZhbHVlcyA9IGNyZWF0ZVByZUFuZFBvc3RFdmVudHNGcm9tRXZlbnQoZXZlbnRUb1Vwc2VydExvY2FsLCBib2R5Py5idWZmZXJUaW1lKVxuXG4gICAgLy8gICAgIGlmIChyZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQpIHtcblxuICAgIC8vICAgICAgICAgY29uc3QgZ29vZ2xlUmVzVmFsdWU6IEdvb2dsZVJlc1R5cGUgPSBhd2FpdCBjcmVhdGVHb29nbGVFdmVudChcbiAgICAvLyAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICAgICAgb2xkRXZlbnQ/LmNhbGVuZGFySWQsXG4gICAgLy8gICAgICAgICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGUsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5pZCxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmVuZERhdGUsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zdGFydERhdGUsXG4gICAgLy8gICAgICAgICAgICAgMCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5zZW5kVXBkYXRlcyxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRpdGxlLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYWZ0ZXJFdmVudD8ubm90ZXMsXG4gICAgLy8gICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5Nb2RpZnksXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/Lm9yaWdpbmFsU3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICByZWN1cixcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnRyYW5zcGFyZW5jeSxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmFmdGVyRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICApXG5cbiAgICAvLyAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmlkID0gZ29vZ2xlUmVzVmFsdWUuaWRcbiAgICAvLyAgICAgICAgIHJldHVyblZhbHVlcy5hZnRlckV2ZW50LmV2ZW50SWQgPSBnb29nbGVSZXNWYWx1ZS5nb29nbGVFdmVudElkXG4gICAgLy8gICAgICAgICByZXR1cm5WYWx1ZXMubmV3RXZlbnQucG9zdEV2ZW50SWQgPSByZXR1cm5WYWx1ZXMuYWZ0ZXJFdmVudC5pZFxuXG4gICAgLy8gICAgIH1cblxuICAgIC8vICAgICBpZiAocmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudCkge1xuXG4gICAgLy8gICAgICAgICBjb25zdCBnb29nbGVSZXNWYWx1ZTogR29vZ2xlUmVzVHlwZSA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgIC8vICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAvLyAgICAgICAgICAgICBjYWxJbnRlZ3JhdGlvbj8uY2xpZW50VHlwZSxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5pZCxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5lbmREYXRlLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICAwLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5zZW5kVXBkYXRlcyxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udGl0bGUsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8ubm90ZXMsXG4gICAgLy8gICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/Lmd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAvLyAgICAgICAgICAgICByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50Py5vcmlnaW5hbFN0YXJ0RGF0ZSxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmVjdXIsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgcmV0dXJuVmFsdWVzPy5iZWZvcmVFdmVudD8udHJhbnNwYXJlbmN5LFxuICAgIC8vICAgICAgICAgICAgIHJldHVyblZhbHVlcz8uYmVmb3JlRXZlbnQ/LnZpc2liaWxpdHksXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgdW5kZWZpbmVkLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICAgICAgJ2RlZmF1bHQnLFxuICAgIC8vICAgICAgICAgICAgIHVuZGVmaW5lZCxcbiAgICAvLyAgICAgICAgICAgICB1bmRlZmluZWQsXG4gICAgLy8gICAgICAgICApXG5cbiAgICAvLyAgICAgICAgIHJldHVyblZhbHVlcy5iZWZvcmVFdmVudC5pZCA9IGdvb2dsZVJlc1ZhbHVlLmlkXG4gICAgLy8gICAgICAgICByZXR1cm5WYWx1ZXMuYmVmb3JlRXZlbnQuZXZlbnRJZCA9IGdvb2dsZVJlc1ZhbHVlLmdvb2dsZUV2ZW50SWRcbiAgICAvLyAgICAgICAgIHJldHVyblZhbHVlcy5uZXdFdmVudC5wcmVFdmVudElkID0gcmV0dXJuVmFsdWVzLmFmdGVyRXZlbnQuaWRcblxuICAgIC8vICAgICB9XG5cbiAgICAvLyAgICAgLy8gaW5zZXJ0IGV2ZW50c1xuICAgIC8vICAgICBhd2FpdCB1cHNlcnRFdmVudHMoW3JldHVyblZhbHVlcy5uZXdFdmVudCwgcmV0dXJuVmFsdWVzPy5hZnRlckV2ZW50LCByZXR1cm5WYWx1ZXM/LmJlZm9yZUV2ZW50XT8uZmlsdGVyKGUgPT4gISFlKSlcbiAgICAvLyB9IGVsc2Uge1xuICAgIC8vICAgICAvLyBpbnNlcnQgZXZlbnRzXG4gICAgLy8gICAgIGF3YWl0IHVwc2VydEV2ZW50cyhbZXZlbnRUb1Vwc2VydExvY2FsXSlcbiAgICAvLyB9XG5cbiAgICAvLyAvLyB1cGRhdGUgcmVtaW5kZXJzXG4gICAgLy8gcmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5mb3JFYWNoKHIgPT4gKHsgLi4uciwgZXZlbnRJZDogb2xkRXZlbnQ/LmlkIH0pKVxuXG4gICAgLy8gLy8gdXBkYXRlIHRpbWVQcmVmZXJlbmNlc1xuICAgIC8vIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXM/LmZvckVhY2gocHQgPT4gKHsgLi4ucHQsIGV2ZW50SWQ6IG9sZEV2ZW50Py5pZCB9KSlcblxuICAgIC8vIC8vIGluc2VydCByZW1pbmRlcnNcbiAgICAvLyBpZiAocmVtaW5kZXJzVG9VcGRhdGVFdmVudElkPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgIGF3YWl0IGluc2VydFJlbWluZGVycyhyZW1pbmRlcnNUb1VwZGF0ZUV2ZW50SWQpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gaW5zZXJ0IHRpbWUgcHJlZmVyZW5jZXNcbiAgICAvLyBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICBhd2FpdCB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQobmV3UHJlZmVycmVkVGltZVJhbmdlcylcbiAgICAvLyB9XG5cbiAgICAvLyAvLyBhZGQgdHJhaW5pbmcgZm9yIHRpbWUgcHJlZmVyZW5jZXMgYW5kIHByaW9yaXR5XG4gICAgLy8gLy8gY29udmVydCB0byB2ZWN0b3IgZm9yIHNlYXJjaFxuICAgIC8vIGlmICgobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkgfHwgYm9keT8ucHJpb3JpdHkgPiAxKSB7XG5cbiAgICAvLyAgICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSlcblxuICAgIC8vICAgICAvLyB0cmFpbiBldmVudFxuICAgIC8vICAgICBhd2FpdCBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2goZXZlbnRJZCwgc2VhcmNoVmVjdG9yLCB1c2VySWQpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gdXBkYXRlIGF0dGVuZGVlcyBmb3IgZXZlbnQgSWRcbiAgICAvLyBhd2FpdCB1cHNlcnRBdHRlbmRlZXNmb3JFdmVudChhdHRlbmRlZXMpXG5cbiAgICAvLyAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgLy8gcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJ1xuXG4gICAgLy8gcmV0dXJuIHJlc3BvbnNlXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgbWVldGluZycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc1VwZGF0ZU1lZXRpbmdNaXNzaW5nRmllbGRzUmV0dXJuZWQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGxldCBkdXJhdGlvbiA9IDA7XG5cbiAgICBjb25zdCB5ZWFyID1cbiAgICAgIGRhdGVKU09OQm9keT8ueWVhciB8fCBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ueWVhcjtcbiAgICBjb25zdCBtb250aCA9XG4gICAgICBkYXRlSlNPTkJvZHk/Lm1vbnRoIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5tb250aDtcbiAgICBjb25zdCBkYXkgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5kYXkgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5ID1cbiAgICAgIGRhdGVKU09OQm9keT8uaXNvV2Vla2RheSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ciA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmhvdXIgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmhvdXI7XG4gICAgY29uc3QgbWludXRlID1cbiAgICAgIGRhdGVKU09OQm9keT8ubWludXRlIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5taW51dGU7XG4gICAgY29uc3Qgc3RhcnRUaW1lID1cbiAgICAgIGRhdGVKU09OQm9keT8uc3RhcnRUaW1lIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uc3RhcnRUaW1lO1xuXG4gICAgY29uc3QgbWVldGluZ1N0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHllYXIsXG4gICAgICBtb250aCxcbiAgICAgIGRheSxcbiAgICAgIGlzb1dlZWtkYXksXG4gICAgICBob3VyLFxuICAgICAgbWludXRlLFxuICAgICAgc3RhcnRUaW1lLFxuICAgICAgZGF0ZUpTT05Cb2R5Py5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0XG4gICAgICAgICAgPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgZGF0ZUpTT05Cb2R5Py5yZWxhdGl2ZVRpbWVGcm9tTm93IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5maW5kVGltZVdpbmRvd1N0YXJ0XG4gICAgICAgICAgPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIC8vIGdldCBkZWZhdWx0IHZhbHVlc1xuICAgIGNvbnN0IGRlZmF1bHRNZWV0aW5nUHJlZmVyZW5jZXMgPVxuICAgICAgYXdhaXQgZ2V0Q2hhdE1lZXRpbmdQcmVmZXJlbmNlR2l2ZW5Vc2VySWQodXNlcklkKTtcblxuICAgIGlmIChcbiAgICAgIGRhdGVKU09OQm9keT8uZHVyYXRpb24gfHxcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kdXJhdGlvblxuICAgICkge1xuICAgICAgZHVyYXRpb24gPVxuICAgICAgICBkYXRlSlNPTkJvZHk/LmR1cmF0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5kdXJhdGlvbjtcbiAgICB9IGVsc2UgaWYgKFxuICAgICAgKGRhdGVKU09OQm9keT8uc3RhcnRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5zdGFydFRpbWUpICYmXG4gICAgICAoZGF0ZUpTT05Cb2R5Py5lbmRUaW1lIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5lbmRUaW1lKVxuICAgICkge1xuICAgICAgLy8gbGlrZWx5IHN0YXJ0IHRpbWUgYWxzbyBwcmVzZW50XG5cbiAgICAgIGNvbnN0IHN0YXJ0VGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnN0YXJ0VGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5zdGFydFRpbWUsXG4gICAgICAgICdISDptbSdcbiAgICAgICk7XG4gICAgICBjb25zdCBlbmRUaW1lT2JqZWN0ID0gZGF5anMoXG4gICAgICAgIGRhdGVKU09OQm9keS5lbmRUaW1lIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5lbmRUaW1lLFxuICAgICAgICAnSEg6bW0nXG4gICAgICApO1xuXG4gICAgICBjb25zdCBtaW51dGVzID0gZW5kVGltZU9iamVjdC5kaWZmKHN0YXJ0VGltZU9iamVjdCwgJ20nKTtcblxuICAgICAgaWYgKG1pbnV0ZXMgPiAwKSB7XG4gICAgICAgIGR1cmF0aW9uID0gbWludXRlcztcbiAgICAgIH1cbiAgICB9IGVsc2UgaWYgKFxuICAgICAgKGpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZSkgJiZcbiAgICAgIChqc29uQm9keT8ucGFyYW1zPy5lbmRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSlcbiAgICApIHtcbiAgICAgIGNvbnN0IHN0YXJ0VGltZU9iamVjdCA9IGRheWpzKFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdGFydFRpbWUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN0YXJ0VGltZVxuICAgICAgKTtcbiAgICAgIGNvbnN0IGVuZFRpbWVPYmplY3QgPSBkYXlqcyhcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZW5kVGltZVxuICAgICAgKTtcbiAgICAgIGNvbnN0IG1pbnV0ZXMgPSBlbmRUaW1lT2JqZWN0LmRpZmYoc3RhcnRUaW1lT2JqZWN0LCAnbScpO1xuXG4gICAgICBpZiAobWludXRlcyA+IDApIHtcbiAgICAgICAgZHVyYXRpb24gPSBtaW51dGVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIHRha2UgY2FyZSBvZiBhbnkgcmVjdXJyaW5nIGRhdGVzXG4gICAgbGV0IHJlY3VyT2JqZWN0OiBSZWN1cnJlbmNlUnVsZVR5cGUgfCB7fSA9IHt9O1xuICAgIGlmIChcbiAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmZyZXF1ZW5jeSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5mcmVxdWVuY3lcbiAgICApIHtcbiAgICAgIGNvbnN0IHJlY3VyRW5kRGF0ZSA9IGV4dHJhcG9sYXRlRGF0ZUZyb21KU09ORGF0YShcbiAgICAgICAgY3VycmVudFRpbWUsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy55ZWFyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5tb250aCB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ubW9udGgsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LmRheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5IHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5pc29XZWVrZGF5LFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5ob3VyLFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5lbmREYXRlPy5taW51dGUgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGU/Lm1pbnV0ZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8uc3RhcnRUaW1lIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5lbmREYXRlPy5zdGFydFRpbWUsXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmVuZERhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3cgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmVuZERhdGVcbiAgICAgICAgICAgID8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uZW5kRGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vdyB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uZW5kRGF0ZVxuICAgICAgICAgICAgPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgICApO1xuXG4gICAgICByZWN1ck9iamVjdCA9IHtcbiAgICAgICAgZnJlcXVlbmN5OlxuICAgICAgICAgIChkYXRlSlNPTkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUpIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5mcmVxdWVuY3kgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWw6XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uaW50ZXJ2YWwgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/LmludGVydmFsIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5pbnRlcnZhbCB8fFxuICAgICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnJlY3VycmVuY2U/LmludGVydmFsLFxuICAgICAgfTtcblxuICAgICAgaWYgKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5ieVdlZWtEYXkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieVdlZWtEYXlcbiAgICAgICkge1xuICAgICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKS5ieVdlZWtEYXkgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5V2Vla0RheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlXZWVrRGF5O1xuICAgICAgfVxuXG4gICAgICBpZiAoXG4gICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/LmJ5TW9udGhEYXkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnJlY3VyPy5ieU1vbnRoRGF5XG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuYnlNb250aERheSA9XG4gICAgICAgICAgZGF0ZUpTT05Cb2R5Py5yZWN1cj8uYnlNb250aERheSB8fFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8uYnlNb250aERheTtcbiAgICAgIH1cblxuICAgICAgaWYgKFxuICAgICAgICBkYXRlSlNPTkJvZHk/LnJlY3VyPy5vY2N1cnJlbmNlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5yZWN1cj8ub2NjdXJyZW5jZVxuICAgICAgKSB7XG4gICAgICAgIChyZWN1ck9iamVjdCBhcyBSZWN1cnJlbmNlUnVsZVR5cGUpLm9jY3VycmVuY2UgPVxuICAgICAgICAgIGRhdGVKU09OQm9keT8ucmVjdXI/Lm9jY3VycmVuY2UgfHxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8ucmVjdXI/Lm9jY3VycmVuY2U7XG4gICAgICB9XG5cbiAgICAgIGlmIChcbiAgICAgICAgcmVjdXJFbmREYXRlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlXG4gICAgICApIHtcbiAgICAgICAgKHJlY3VyT2JqZWN0IGFzIFJlY3VycmVuY2VSdWxlVHlwZSkuZW5kRGF0ZSA9XG4gICAgICAgICAgcmVjdXJFbmREYXRlIHx8XG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5yZWN1cnJlbmNlPy5lbmREYXRlIHx8XG4gICAgICAgICAganNvbkJvZHk/LnBhcmFtcz8ucmVjdXJyZW5jZT8uZW5kRGF0ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCBuZXdCb2R5OiBVcGRhdGVNZWV0aW5nVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG9sZFRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5vbGRUaXRsZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/Lm9sZFRpdGxlLFxuICAgICAgYXR0ZW5kZWVzOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5hdHRlbmRlZXMsXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/Lm5vdGVzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5ub3RlcyxcbiAgICAgIGNvbmZlcmVuY2VBcHA6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmNvbmZlcmVuY2U/LmFwcCxcbiAgICAgIHN0YXJ0RGF0ZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3RhcnRUaW1lIHx8XG4gICAgICAgIG1lZXRpbmdTdGFydERhdGUsXG4gICAgICBidWZmZXJUaW1lOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5idWZmZXJUaW1lIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uYnVmZmVyVGltZSxcbiAgICAgIHJlbWluZGVyczpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uYWxhcm1zIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uYWxhcm1zIHx8XG4gICAgICAgIFtdLFxuICAgICAgcHJpb3JpdHk6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8ucHJpb3JpdHkgfHxcbiAgICAgICAgMSxcbiAgICAgIHRpbWVQcmVmZXJlbmNlczpcbiAgICAgICAgZGF0ZUpTT05Cb2R5Py50aW1lUHJlZmVyZW5jZXMgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fFxuICAgICAgICBbXSxcbiAgICAgIGxvY2F0aW9uOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5sb2NhdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmxvY2F0aW9uLFxuICAgICAgdHJhbnNwYXJlbmN5OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50cmFuc3BhcmVuY3kgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy52aXNpYmlsaXR5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udmlzaWJpbGl0eSxcbiAgICAgIGlzRm9sbG93VXA6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmlzRm9sbG93VXAgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5pc0ZvbGxvd1VwLFxuICAgIH07XG5cbiAgICBpZiAoXG4gICAgICAocmVjdXJPYmplY3QgYXMgUmVjdXJyZW5jZVJ1bGVUeXBlKT8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlXG4gICAgKSB7XG4gICAgICBuZXdCb2R5LnJlY3VyID0gcmVjdXJPYmplY3QgYXMgYW55O1xuICAgIH1cblxuICAgIC8vIHZhbGlkYXRlIGZvciBtaXNzaW5nIGZpZWxkc1xuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICd1cGRhdGVNZWV0aW5nJyxcbiAgICB9O1xuXG4gICAgY29uc3Qgc2VhcmNoQm91bmRhcnkgPSBldmVudFNlYXJjaEJvdW5kYXJ5KFxuICAgICAgdGltZXpvbmUsXG4gICAgICBkYXRlSlNPTkJvZHksXG4gICAgICBjdXJyZW50VGltZVxuICAgICk7XG5cbiAgICBsZXQgc3RhcnREYXRlID0gc2VhcmNoQm91bmRhcnkuc3RhcnREYXRlO1xuICAgIGxldCBlbmREYXRlID0gc2VhcmNoQm91bmRhcnkuZW5kRGF0ZTtcblxuICAgIGNvbnN0IG5ld0F0dGVuZGVlczogTXV0YXRlZENhbGVuZGFyRXh0cmFjdGVkSlNPTkF0dGVuZGVlVHlwZVtdID0gW107XG5cbiAgICBjb25zdCBwcmV2Qm9keTogVXBkYXRlTWVldGluZ1R5cGUgPSB7XG4gICAgICAuLi5tZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGEsXG4gICAgfTtcblxuICAgIGlmICghcHJldkJvZHk/LnVzZXJJZCkge1xuICAgICAgcHJldkJvZHkudXNlcklkID0gdXNlcklkIHx8IG5ld0JvZHk/LnVzZXJJZDtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aW1lem9uZSkge1xuICAgICAgcHJldkJvZHkudGltZXpvbmUgPSB0aW1lem9uZSB8fCBuZXdCb2R5Py50aW1lem9uZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcHJldkJvZHkudGl0bGUgPSBuZXdCb2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5vbGRUaXRsZSkge1xuICAgICAgcHJldkJvZHkub2xkVGl0bGUgPSBuZXdCb2R5Py5vbGRUaXRsZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5kdXJhdGlvbikge1xuICAgICAgcHJldkJvZHkuZHVyYXRpb24gPSBuZXdCb2R5Py5kdXJhdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5kZXNjcmlwdGlvbikge1xuICAgICAgcHJldkJvZHkuZGVzY3JpcHRpb24gPSBuZXdCb2R5Py5kZXNjcmlwdGlvbjtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5jb25mZXJlbmNlQXBwKSB7XG4gICAgICBwcmV2Qm9keS5jb25mZXJlbmNlQXBwID0gbmV3Qm9keT8uY29uZmVyZW5jZUFwcDtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5zdGFydERhdGUpIHtcbiAgICAgIHByZXZCb2R5LnN0YXJ0RGF0ZSA9IG5ld0JvZHk/LnN0YXJ0RGF0ZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py5idWZmZXJUaW1lKSB7XG4gICAgICBwcmV2Qm9keS5idWZmZXJUaW1lID0gbmV3Qm9keT8uYnVmZmVyVGltZTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8ucmVtaW5kZXJzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkucmVtaW5kZXJzID0gbmV3Qm9keT8ucmVtaW5kZXJzIHx8IFtdO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnByaW9yaXR5KSB7XG4gICAgICBwcmV2Qm9keS5wcmlvcml0eSA9IG5ld0JvZHk/LnByaW9yaXR5O1xuICAgIH1cblxuICAgIGlmICghKHByZXZCb2R5Py50aW1lUHJlZmVyZW5jZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBwcmV2Qm9keS50aW1lUHJlZmVyZW5jZXMgPSBuZXdCb2R5Py50aW1lUHJlZmVyZW5jZXM7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ubG9jYXRpb24pIHtcbiAgICAgIHByZXZCb2R5LmxvY2F0aW9uID0gbmV3Qm9keT8ubG9jYXRpb247XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udHJhbnNwYXJlbmN5KSB7XG4gICAgICBwcmV2Qm9keS50cmFuc3BhcmVuY3kgPSBuZXdCb2R5Py50cmFuc3BhcmVuY3k7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udmlzaWJpbGl0eSkge1xuICAgICAgcHJldkJvZHkudmlzaWJpbGl0eSA9IG5ld0JvZHk/LnZpc2liaWxpdHk7XG4gICAgfVxuXG4gICAgaWYgKHByZXZCb2R5LmlzRm9sbG93VXAgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuaXNGb2xsb3dVcCA9IG5ld0JvZHk/LmlzRm9sbG93VXA7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ucmVjdXIpIHtcbiAgICAgIHByZXZCb2R5LnJlY3VyID0gbmV3Qm9keT8ucmVjdXI7XG4gICAgfVxuXG4gICAgY29uc3QgcHJldlNlYXJjaEJvdW5kYXJ5OiBTZWFyY2hCb3VuZGFyeVR5cGUgPVxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhRXh0cmE/LnNlYXJjaEJvdW5kYXJ5O1xuXG4gICAgbGV0IHByZXZTdGFydERhdGUgPSBwcmV2U2VhcmNoQm91bmRhcnk/LnN0YXJ0RGF0ZTtcblxuICAgIGxldCBwcmV2RW5kRGF0ZSA9IHByZXZTZWFyY2hCb3VuZGFyeT8uZW5kRGF0ZTtcblxuICAgIGlmICghcHJldlN0YXJ0RGF0ZSkge1xuICAgICAgcHJldlN0YXJ0RGF0ZSA9IHN0YXJ0RGF0ZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZFbmREYXRlKSB7XG4gICAgICBwcmV2RW5kRGF0ZSA9IGVuZERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8uc3RhcnREYXRlICYmICFkYXkgJiYgIWlzb1dlZWtkYXkpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChcbiAgICAgICAgcmVxdWlyZWRGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQ/LlswXVxuICAgICAgKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgIHNlYXJjaEJvdW5kYXJ5OiB7XG4gICAgICAgICAgc3RhcnREYXRlOiBwcmV2U3RhcnREYXRlLFxuICAgICAgICAgIGVuZERhdGU6IHByZXZFbmREYXRlLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICAhcHJldkJvZHk/LnN0YXJ0RGF0ZSAmJlxuICAgICAgaG91ciA9PT0gbnVsbCAmJlxuICAgICAgbWludXRlID09PSBudWxsICYmXG4gICAgICAhc3RhcnRUaW1lXG4gICAgKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkLnB1c2goXG4gICAgICAgIHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lLnJlcXVpcmVkPy5bMV1cbiAgICAgICk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeToge1xuICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgZm9yIChjb25zdCBhIG9mIG5ld0JvZHk/LmF0dGVuZGVlcykge1xuICAgICAgaWYgKCFhPy5lbWFpbCkge1xuICAgICAgICBjb25zdCBjb250YWN0ID0gYXdhaXQgZ2V0Q29udGFjdEJ5TmFtZVdpdGhVc2VySWQodXNlcklkLCBhPy5uYW1lKTtcbiAgICAgICAgaWYgKGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZSkge1xuICAgICAgICAgIGNvbnN0IHByaW1hcnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uZmluZCgoZSkgPT4gISFlLnByaW1hcnkpPy52YWx1ZTtcbiAgICAgICAgICBjb25zdCBhbnlFbWFpbCA9IGNvbnRhY3Q/LmVtYWlscz8uWzBdPy52YWx1ZTtcbiAgICAgICAgICBuZXdBdHRlbmRlZXMucHVzaCh7IC4uLmEsIGVtYWlsOiBwcmltYXJ5RW1haWwgfHwgYW55RW1haWwgfSk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChcbiAgICAgICAgICAgIHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMV0/LlsnYW5kJ10/LlsyXVxuICAgICAgICAgICk7XG4gICAgICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICAgICAgc2VhcmNoQm91bmRhcnk6IHtcbiAgICAgICAgICAgICAgc3RhcnREYXRlOiBwcmV2U3RhcnREYXRlLFxuICAgICAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBuZXdBdHRlbmRlZXMucHVzaChhKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBuZXdCb2R5LmF0dGVuZGVlcyA9IG5ld0F0dGVuZGVlcztcblxuICAgIGlmICghKHByZXZCb2R5Py5hdHRlbmRlZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBwcmV2Qm9keS5hdHRlbmRlZXMgPSBuZXdCb2R5Py5hdHRlbmRlZXM7XG4gICAgfVxuXG4gICAgLy8gdmFsaWRhdGUgcmVtYWluaW5nIHJlcXVpcmVkIGZpZWxkc1xuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlswXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeToge1xuICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwVXBkYXRlTWVldGluZyhcbiAgICAgIHByZXZCb2R5LFxuICAgICAgZGVmYXVsdE1lZXRpbmdQcmVmZXJlbmNlcyxcbiAgICAgIHByZXZTdGFydERhdGUsXG4gICAgICBwcmV2RW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgbWVldGluZ3MnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZU1lZXRpbmdDb250cm9sQ2VudGVyID0gYXN5bmMgKFxuICBvcGVuYWk6IE9wZW5BSSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbiAgdXNlckN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIHF1ZXJ5OiAnbWlzc2luZ19maWVsZHMnIHwgJ2NvbXBsZXRlZCcgfCAnZXZlbnRfbm90X2ZvdW5kJyB8ICdwZW5kaW5nJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGg7XG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG4gICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICB1c2VyTWVzc2FnZSA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgYnJlYWs7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgdXNlcklucHV0ID0gdXNlck1lc3NhZ2U7XG5cbiAgICBsZXQgdXBkYXRlTWVldGluZ1JlczogUmVzcG9uc2VBY3Rpb25UeXBlID0ge1xuICAgICAgcXVlcnk6ICdjb21wbGV0ZWQnLFxuICAgICAgZGF0YTogJycsXG4gICAgICBza2lsbDogJycsXG4gICAgICBwcmV2RGF0YToge30sXG4gICAgICBwcmV2RGF0YUV4dHJhOiB7fSxcbiAgICB9O1xuXG4gICAgc3dpdGNoIChxdWVyeSkge1xuICAgICAgY2FzZSAncGVuZGluZyc6XG4gICAgICAgIGNvbnN0IGpzb25Cb2R5ID0gYXdhaXQgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBjb25zdCBkYXRlVGltZSA9IGF3YWl0IGdlbmVyYXRlRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuICAgICAgICB1cGRhdGVNZWV0aW5nUmVzID0gYXdhaXQgcHJvY2Vzc1VwZGF0ZU1lZXRpbmdQZW5kaW5nKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uQm9keSxcbiAgICAgICAgICBkYXRlVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdtaXNzaW5nX2ZpZWxkcyc6XG4gICAgICAgIGxldCBwcmlvclVzZXJJbnB1dCA9ICcnO1xuICAgICAgICBsZXQgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSAnJztcblxuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAnYXNzaXN0YW50Jykge1xuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgIGlmIChtZXNzYWdlLmNvbnRlbnQgIT09IHVzZXJJbnB1dCkge1xuICAgICAgICAgICAgICBwcmlvclVzZXJJbnB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmlvclVzZXJJbnB1dCB8fCAhcHJpb3JBc3Npc3RhbnRPdXRwdXQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvclVzZXJJbnB1dCwgJyBwcmlvclVzZXJJbnB1dCcpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yQXNzaXN0YW50T3V0cHV0LCAnIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBwcmlvclVzZXJpbnB1dCBvciBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGpzb25NaXNzaW5nRmllbGRzQm9keSA9XG4gICAgICAgICAgYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVNaXNzaW5nRmllbGRzVGltZSA9IGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcblxuICAgICAgICB1cGRhdGVNZWV0aW5nUmVzID0gYXdhaXQgcHJvY2Vzc1VwZGF0ZU1lZXRpbmdNaXNzaW5nRmllbGRzUmV0dXJuZWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25NaXNzaW5nRmllbGRzQm9keSxcbiAgICAgICAgICBkYXRlTWlzc2luZ0ZpZWxkc1RpbWUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgIH1cblxuICAgIGlmICh1cGRhdGVNZWV0aW5nUmVzPy5xdWVyeSA9PT0gJ2NvbXBsZXRlZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnkoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIHVwZGF0ZU1lZXRpbmdSZXMuZGF0YSBhcyBzdHJpbmcsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfSBlbHNlIGlmICh1cGRhdGVNZWV0aW5nUmVzPy5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzKFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICB1cGRhdGVNZWV0aW5nUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPVxuICAgICAgICB1cGRhdGVNZWV0aW5nUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhID0gdXBkYXRlTWVldGluZ1Jlcz8ucHJldkRhdGE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YUV4dHJhID0gdXBkYXRlTWVldGluZ1Jlcz8ucHJldkRhdGFFeHRyYTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPVxuICAgICAgICB1cGRhdGVNZWV0aW5nUmVzPy5wcmV2RGF0ZUpzb25Cb2R5O1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkpzb25Cb2R5ID0gdXBkYXRlTWVldGluZ1Jlcz8ucHJldkpzb25Cb2R5O1xuICAgIH0gZWxzZSBpZiAodXBkYXRlTWVldGluZ1Jlcz8ucXVlcnkgPT09ICdldmVudF9ub3RfZm91bmQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6IFwiT29wcy4uLiBJIGNvdWxkbid0IGZpbmQgdGhlIGV2ZW50LiBTb3JyeSA6KFwiLFxuICAgICAgfTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfVxuXG4gICAgcmV0dXJuIG1lc3NhZ2VIaXN0b3J5T2JqZWN0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIG1lZXRpbmcgY29udHJvbCBjZW50ZXInKTtcbiAgfVxufTtcbiJdfQ==