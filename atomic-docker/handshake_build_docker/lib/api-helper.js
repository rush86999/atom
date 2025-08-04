"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createRecurringMeetingAssists = exports.updateMeetingAssistInviteResponse = exports.listMeetingAssistInvitesGivenMeetingId = exports.getMeetingAssistInviteGivenId = exports.getCustomAvailableTimes = exports.startMeetingAssist = exports.AtoB = exports.BtoA = exports.upsertMeetingAssistPreferredTimes = exports.deleteMeetingAssistPreferredTimesByIds = exports.cancelMeetingAssist = exports.generateAvailableSlotsForDate = exports.generateAvailableSlotsforTimeWindow = exports.listMeetingAssistPreferredTimeRangesGivenMeetingId = exports.findEventsForUserGivenMeetingId = exports.listEventsForUserGivenDates = exports.getUserContactInfo = exports.updateMeetingAssistAttendanceCount = exports.getMeetingAssistAttendeeByEmail = exports.getMeetingAssistAttendee = exports.deleteMeetingAssistAttendee = exports.upsertOneMeetingAssistAttendee = exports.insertMeetingAssistAttendees = exports.generateAttendeesAndPreferredTimesForRecurringMeetingAssists = exports.generateAttendeesAndPreferredTimesForRecurringMeetingAssist = exports.generatePreferredTimesForRecurringMeetingAssist = exports.updateMeetingAssistAttendee = exports.listMeetingAssistEventsForAttendeeGivenDates = exports.listMeetingAssistAttendeesGivenMeetingId = exports.getMeetingAssist = exports.getCalendarIntegration = exports.googleCalendarSync = exports.upsertMeetingAssistEvents = exports.upsertMeetingAssistCalendars = exports.insertMeetingAssists = exports.getUserGivenId = exports.getUserPreferences = exports.generateDatesForFutureMeetingAssistsUsingRrule = exports.generateRecurringMeetingAssists = exports.getRruleFreq = void 0;
const got_1 = __importDefault(require("got"));
const uuid_1 = require("uuid");
const date_fns_1 = require("date-fns");
const dayjs_1 = __importDefault(require("dayjs"));
// import isoWeek from 'dayjs/plugin/isoWeek'
const duration_1 = __importDefault(require("dayjs/plugin/duration"));
const isBetween_1 = __importDefault(require("dayjs/plugin/isBetween"));
const isSameOrAfter_1 = __importDefault(require("dayjs/plugin/isSameOrAfter"));
const isSameOrBefore_1 = __importDefault(require("dayjs/plugin/isSameOrBefore"));
const timezone_1 = __importDefault(require("dayjs/plugin/timezone"));
const utc_1 = __importDefault(require("dayjs/plugin/utc"));
const customParseFormat_1 = __importDefault(require("dayjs/plugin/customParseFormat"));
const lodash_1 = __importDefault(require("lodash"));
const constants_1 = require("@lib/constants");
const googleapis_1 = require("googleapis");
const rrule_1 = require("rrule");
// dayjs.extend(isoWeek)
dayjs_1.default.extend(duration_1.default);
dayjs_1.default.extend(isBetween_1.default);
dayjs_1.default.extend(timezone_1.default);
dayjs_1.default.extend(utc_1.default);
dayjs_1.default.extend(customParseFormat_1.default);
dayjs_1.default.extend(isSameOrAfter_1.default);
dayjs_1.default.extend(isSameOrBefore_1.default);
const getRruleFreq = (freq) => {
    switch (freq) {
        case 'daily':
            return rrule_1.RRule.DAILY;
        case 'weekly':
            return rrule_1.RRule.WEEKLY;
        case 'monthly':
            return rrule_1.RRule.MONTHLY;
        case 'yearly':
            return rrule_1.RRule.YEARLY;
    }
};
exports.getRruleFreq = getRruleFreq;
const generateRecurringMeetingAssists = (originalMeetingAssist) => {
    // validate
    if (!originalMeetingAssist?.frequency) {
        console.log('no frequency present inside generateRecurringMeetingAssists');
        return;
    }
    if (!originalMeetingAssist?.interval) {
        console.log('no internval present inside generateRecurringMeetingAssists');
        return;
    }
    if (!originalMeetingAssist?.until) {
        console.log('no until present inside generateRecurringMeetingAssists');
        return;
    }
    console.log('generateRecurringMeetingAssists called');
    const recurringMeetingAssists = [];
    const timeWindows = (0, exports.generateDatesForFutureMeetingAssistsUsingRrule)(originalMeetingAssist?.windowStartDate, originalMeetingAssist?.windowEndDate, originalMeetingAssist?.frequency, originalMeetingAssist?.interval, originalMeetingAssist?.until);
    console.log(timeWindows, ' timeWindows inside generateRecurringMeetingAssists');
    for (let i = 0; i < timeWindows.length; i++) {
        if (i === 0) {
            continue;
        }
        const meetingId = (0, uuid_1.v4)();
        const newRecurringMeetingAssist = {
            id: meetingId,
            userId: originalMeetingAssist?.userId,
            summary: originalMeetingAssist?.summary,
            notes: originalMeetingAssist?.notes,
            windowStartDate: timeWindows[i]?.windowStartDate,
            windowEndDate: timeWindows[i]?.windowEndDate,
            timezone: originalMeetingAssist?.timezone,
            location: originalMeetingAssist?.location,
            priority: 1,
            enableConference: originalMeetingAssist?.enableConference,
            conferenceApp: originalMeetingAssist?.conferenceApp,
            sendUpdates: originalMeetingAssist?.sendUpdates,
            guestsCanInviteOthers: originalMeetingAssist?.guestsCanInviteOthers,
            transparency: originalMeetingAssist?.transparency,
            visibility: originalMeetingAssist?.visibility,
            createdDate: (0, dayjs_1.default)().format(),
            updatedAt: (0, dayjs_1.default)().format(),
            colorId: originalMeetingAssist?.colorId,
            backgroundColor: originalMeetingAssist?.backgroundColor,
            foregroundColor: originalMeetingAssist?.foregroundColor,
            useDefaultAlarms: originalMeetingAssist?.useDefaultAlarms,
            reminders: originalMeetingAssist?.reminders,
            cancelIfAnyRefuse: originalMeetingAssist?.cancelIfAnyRefuse,
            enableHostPreferences: originalMeetingAssist?.enableHostPreferences,
            enableAttendeePreferences: originalMeetingAssist?.enableAttendeePreferences,
            attendeeCanModify: originalMeetingAssist?.attendeeCanModify,
            expireDate: originalMeetingAssist?.expireDate,
            cancelled: originalMeetingAssist?.cancelled,
            duration: originalMeetingAssist?.duration,
            calendarId: originalMeetingAssist?.calendarId,
            bufferTime: originalMeetingAssist?.bufferTime,
            anyoneCanAddSelf: originalMeetingAssist?.anyoneCanAddSelf,
            guestsCanSeeOtherGuests: originalMeetingAssist?.guestsCanSeeOtherGuests,
            minThresholdCount: originalMeetingAssist?.minThresholdCount,
            guaranteeAvailability: originalMeetingAssist?.guaranteeAvailability,
            frequency: originalMeetingAssist?.frequency,
            interval: originalMeetingAssist?.interval,
            until: originalMeetingAssist?.until,
            originalMeetingId: originalMeetingAssist?.id,
            attendeeRespondedCount: originalMeetingAssist?.attendeeRespondedCount,
            attendeeCount: originalMeetingAssist?.attendeeCount,
        };
        recurringMeetingAssists.push(newRecurringMeetingAssist);
    }
    recurringMeetingAssists?.forEach((a) => console.log(a, ' recurringMeetingAssist inside generateRecurringMeetingAssists'));
    return recurringMeetingAssists;
};
exports.generateRecurringMeetingAssists = generateRecurringMeetingAssists;
const generateDatesForFutureMeetingAssistsUsingRrule = (windowStartDate, windowEndDate, frequency, interval, until) => {
    const ruleStartDate = new rrule_1.RRule({
        dtstart: (0, dayjs_1.default)(windowStartDate).utc().toDate(),
        freq: (0, exports.getRruleFreq)(frequency),
        interval,
        until: (0, dayjs_1.default)(until).utc().toDate(),
    });
    console.log(ruleStartDate, ' ruleStartDate inside generateDatesForFutureMeetingAssistsUsingRrule');
    const windowStartDatesForRecurrence = ruleStartDate
        .all()
        ?.map((d) => dayjs_1.default.utc(d).format());
    windowStartDatesForRecurrence?.forEach((e) => console.log(e, ' windowDateforrecurrence inside generateDatesForFutureMeetingAssistsUsingRrule'));
    const ruleEndDate = new rrule_1.RRule({
        dtstart: (0, dayjs_1.default)(windowEndDate).utc().toDate(),
        freq: (0, exports.getRruleFreq)(frequency),
        interval,
        until: (0, dayjs_1.default)(until).utc().toDate(),
    });
    console.log(ruleEndDate, ' ruleEndDate inside generateDatesForFutureMeetingAssistsUsingRrule');
    const windowEndDatesForRecurrence = ruleEndDate
        .all()
        ?.map((d) => dayjs_1.default.utc(d).format());
    windowEndDatesForRecurrence?.forEach((e) => console.log(e, ' windowEndDateforrecurrence inside generateDatesForFutureMeetingAssistsUsingRrule'));
    // reformat into windowStartDates and windowEndDates
    const timeWindows = windowStartDatesForRecurrence
        ?.slice(0, windowEndDatesForRecurrence?.length)
        ?.map((windowStartDate, inx) => {
        return {
            windowStartDate,
            windowEndDate: windowEndDatesForRecurrence?.[inx],
        };
    });
    return timeWindows;
};
exports.generateDatesForFutureMeetingAssistsUsingRrule = generateDatesForFutureMeetingAssistsUsingRrule;
const getUserPreferences = async (userId) => {
    try {
        if (!userId) {
            console.log('userId is null');
            return null;
        }
        const operationName = 'getUserPreferences';
        const query = `
    query getUserPreferences($userId: uuid!) {
      User_Preference(where: {userId: {_eq: $userId}}) {
        startTimes
        endTimes
        backToBackMeetings
        copyAvailability
        copyCategories
        copyIsBreak
        copyModifiable
        copyPriorityLevel
        copyReminders
        copyTimeBlocking
        copyTimePreference
        createdDate
        deleted
        followUp
        id
        isPublicCalendar
        maxNumberOfMeetings
        maxWorkLoadPercent
        publicCalendarCategories
        reminders
        updatedAt
        userId
        minNumberOfBreaks
        breakColor
        breakLength
        copyColor
        copyIsExternalMeeting
        copyIsMeeting
        onBoarded
      }
    }    
  `;
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables: {
                    userId,
                },
            },
        })
            .json();
        return res?.data?.User_Preference?.[0];
    }
    catch (e) {
        console.log(e, ' getUserPreferences');
        return null;
    }
};
exports.getUserPreferences = getUserPreferences;
const getUserGivenId = async (userId) => {
    try {
        const operationName = 'GetUserById';
        const query = `
            query GetUserById($id: uuid!) {
                User_by_pk(id: $id) {
                    createdDate
                    deleted
                    email
                    id
                    name
                    updatedAt
                    userPreferenceId
                }
            }
        `;
        const variables = {
            id: userId,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        console.log(res, ' successfully got user by id');
        return res?.data?.User_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get user given id');
    }
};
exports.getUserGivenId = getUserGivenId;
const insertMeetingAssists = async (meetingAssists) => {
    try {
        console.log(meetingAssists, 'insertMeetingAssists called');
        const operationName = 'InsertMeetingAssist';
        const query = `
            mutation InsertMeetingAssist($meetingAssists: [Meeting_Assist_insert_input!]!) {
                insert_Meeting_Assist(objects: $meetingAssists) {
                    affected_rows
                    returning {
                    allowAttendeeUpdatePreferences
                    anyoneCanAddSelf
                    attendeeCanModify
                    attendeeCount
                    attendeeRespondedCount
                    backgroundColor
                    bufferTime
                    calendarId
                    cancelIfAnyRefuse
                    cancelled
                    colorId
                    conferenceApp
                    createdDate
                    duration
                    enableAttendeePreferences
                    enableConference
                    enableHostPreferences
                    endDate
                    eventId
                    expireDate
                    foregroundColor
                    frequency
                    guaranteeAvailability
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    id
                    interval
                    location
                    minThresholdCount
                    notes
                    originalMeetingId
                    priority
                    reminders
                    sendUpdates
                    startDate
                    summary
                    timezone
                    transparency
                    until
                    updatedAt
                    useDefaultAlarms
                    userId
                    visibility
                    windowEndDate
                    windowStartDate
                    }
                }
            }
        `;
        const variables = {
            meetingAssists,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        console.log(res?.data?.insert_Meeting_Assist?.affected_rows, ' successfully added recurring meeting assists');
        return res?.data?.insert_Meeting_Assist?.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable insert meeting assists');
    }
};
exports.insertMeetingAssists = insertMeetingAssists;
const upsertMeetingAssistCalendars = async (calendarList) => {
    try {
        const operationName = 'UpsertMeetingAssistCalendarList';
        const query = `
            mutation UpsertMeetingAssistCalendarList($calendarList: [Meeting_Assist_Calendar_insert_input!]!) {
                insert_Meeting_Assist_Calendar(objects: $calendarList, on_conflict: {
                    constraint: Meeting_Assist_Calendar_pkey, 
                    update_columns: [
                        accessLevel,
                    account,
                    attendeeId,
                    backgroundColor,
                    colorId,
                    defaultReminders,
                    foregroundColor,
                    modifiable,
                    primary,
                    resource,
                    title,
                    ]}) {
                    affected_rows
                    returning {
                        accessLevel
                        account
                        attendeeId
                        backgroundColor
                        colorId
                        defaultReminders
                        foregroundColor
                        id
                        modifiable
                        primary
                        resource
                        title
                    }
                }
            }
        `;
        const variables = {
            calendarList,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        console.log(res, ' res inside upsertMeetingAssistCalendars');
    }
    catch (e) {
        console.log(e, ' unable to upsert meeting assist calendar list');
    }
};
exports.upsertMeetingAssistCalendars = upsertMeetingAssistCalendars;
const upsertMeetingAssistEvents = async (events) => {
    try {
        const operationName = 'upsertMeetingAssistEvents';
        const query = `
            mutation upsertMeetingAssistEvents($events: [Meeting_Assist_Event_insert_input!]!) {
                insert_Meeting_Assist_Event(objects: $events, on_conflict: {
                    constraint: Meeting_Assist_Event_pkey, 
                    update_columns: [
                        allDay,
                        attachments,
                        attendeeId,
                        attendeesOmitted,
                        backgroundColor,
                        calendarId,
                        colorId,
                        createdDate,
                        creator,
                        endDate,
                        endTimeUnspecified,
                        eventType,
                        extendedProperties,
                        externalUser,
                        foregroundColor,
                        guestsCanModify,
                        hangoutLink,
                        htmlLink,
                        iCalUID,
                        links,
                        location,
                        locked,
                        meetingId,
                        notes,
                        organizer,
                        privateCopy,
                        recurrence,
                        recurrenceRule,
                        recurringEventId,
                        source,
                        startDate,
                        summary,
                        timezone,
                        transparency,
                        updatedAt,
                        useDefaultAlarms,
                        visibility,
                        eventId,
                    ]}) {
                    affected_rows
                    returning {
                    allDay
                    attachments
                    attendeeId
                    attendeesOmitted
                    backgroundColor
                    calendarId
                    colorId
                    createdDate
                    creator
                    endDate
                    endTimeUnspecified
                    eventType
                    extendedProperties
                    externalUser
                    foregroundColor
                    guestsCanModify
                    hangoutLink
                    htmlLink
                    iCalUID
                    id
                    links
                    location
                    locked
                    meetingId
                    notes
                    organizer
                    privateCopy
                    recurrence
                    recurrenceRule
                    recurringEventId
                    source
                    startDate
                    summary
                    timezone
                    transparency
                    updatedAt
                    useDefaultAlarms
                    visibility
                    eventId
                    }
                }
            }
        `;
        const variables = {
            events,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        console.log(res, ' res inside upsertMeetingAssistEvents');
        res?.errors?.forEach((e) => console.log(e));
    }
    catch (e) {
        console.log(e, ' unable ot upsert meeting assistant events');
    }
};
exports.upsertMeetingAssistEvents = upsertMeetingAssistEvents;
const googleCalendarSync = async (token, // access_token returned by Google Auth
windowStartDate, windowEndDate, attendeeId, hostTimezone) => {
    try {
        const googleCalendar = googleapis_1.google.calendar({
            version: 'v3',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        const calendarListRes = await googleCalendar.calendarList.list();
        const calendarList = calendarListRes?.data?.items;
        if ((calendarList && !(calendarList?.length > 0)) || !calendarList) {
            console.log(' no calendars found');
            throw new Error('no calendars were found from google calendar');
        }
        const calendarListModified = calendarList.map((c) => ({
            id: c.id || c?.summary,
            attendeeId,
            title: c?.summary,
            backgroundColor: c?.backgroundColor,
            accessLevel: c?.accessRole,
            modifiable: true,
            defaultReminders: c?.defaultReminders,
            primary: c?.primary,
            colorId: c?.colorId,
            foregroundColor: c?.foregroundColor,
        }));
        // validate
        if (!calendarListModified) {
            throw new Error('no calendarListModified');
        }
        await (0, exports.upsertMeetingAssistCalendars)(calendarListModified);
        const timeMin = (0, dayjs_1.default)(windowStartDate.slice(0, 19)).format();
        const timeMax = (0, dayjs_1.default)(windowEndDate.slice(0, 19)).format();
        const calendarListAsMeetingAssistCalendar = calendarListModified;
        for (let i = 0; i < calendarListAsMeetingAssistCalendar?.length; i++) {
            const initialVariables = {
                calendarId: calendarListAsMeetingAssistCalendar?.[i]?.id,
                showDeleted: false,
                singleEvents: true,
                timeMin,
                timeMax,
                timeZone: hostTimezone,
            };
            const res = await googleCalendar.events.list(initialVariables);
            const events = res?.data?.items;
            if (!events || !(events?.length > 0)) {
                return null;
            }
            // format events for insert
            // filter events without id or timezone
            const formattedEvents = events
                ?.filter((e) => !!e?.id)
                ?.filter((e) => !!e?.start?.timeZone || !!e?.end?.timeZone)
                ?.map((event) => {
                return {
                    id: `${event?.id}#${calendarListAsMeetingAssistCalendar?.[i]?.id}`, //
                    attendeeId, //
                    htmlLink: event?.htmlLink, //
                    createdDate: event?.created, //
                    updatedAt: event?.updated, //
                    summary: event?.summary, //
                    notes: event?.description, //
                    location: {
                        title: event?.location,
                    }, //
                    colorId: event?.colorId, //
                    creator: event?.creator, //
                    organizer: event?.organizer, //
                    startDate: event?.start?.dateTime ||
                        (0, dayjs_1.default)(event?.start?.date)
                            .tz(event?.start?.timeZone || dayjs_1.default.tz.guess(), true)
                            .format(), //
                    endDate: event?.end?.dateTime ||
                        (0, dayjs_1.default)(event?.end?.date)
                            .tz(event?.end?.timeZone || dayjs_1.default.tz.guess(), true)
                            .format(), //
                    allDay: event?.start?.date ? true : false, //
                    timezone: event?.start?.timeZone || event?.end?.timeZone, //
                    endTimeUnspecified: event?.endTimeUnspecified, //
                    recurrence: event?.recurrence, //
                    transparency: event?.transparency, //
                    visibility: event?.visibility, //
                    iCalUID: event?.iCalUID, //
                    attendeesOmitted: event?.attendeesOmitted, //
                    extendedProperties: event?.extendedProperties?.private ||
                        event?.extendedProperties?.shared
                        ? {
                            private: event?.extendedProperties?.private && {
                                keys: Object.keys(event?.extendedProperties?.private),
                                values: Object.values(event?.extendedProperties?.private),
                            },
                            shared: event?.extendedProperties?.shared && {
                                keys: Object.keys(event?.extendedProperties?.shared),
                                values: Object.values(event?.extendedProperties?.shared),
                            },
                        }
                        : null, //
                    hangoutLink: event?.hangoutLink, //
                    anyoneCanAddSelf: event?.anyoneCanAddSelf,
                    guestsCanInviteOthers: event?.guestsCanInviteOthers,
                    guestsCanModify: event?.guestsCanModify, //
                    guestsCanSeeOtherGuests: event?.guestsCanSeeOtherGuests,
                    source: event?.source, //
                    attachments: event?.attachments, //
                    eventType: event?.eventType, //
                    privateCopy: event?.privateCopy, //
                    locked: event?.locked, //
                    calendarId: calendarListAsMeetingAssistCalendar?.[i]?.id, //
                    useDefaultAlarms: event?.reminders?.useDefault, //
                    externalUser: true, //
                    eventId: event?.id,
                };
            });
            if (!(formattedEvents?.length > 0)) {
                continue;
            }
            await (0, exports.upsertMeetingAssistEvents)(formattedEvents);
        }
    }
    catch (e) {
        console.log(e, ' unable to google calendar sync');
    }
};
exports.googleCalendarSync = googleCalendarSync;
const getCalendarIntegration = async (userId, resource) => {
    try {
        const operationName = 'getCalendarIntegration';
        const query = `
      query getCalendarIntegration($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
          token
          expiresAt
          id
          refreshToken
          resource
          name
          clientType
        }
      }
    `;
        const variables = {
            userId,
            resource,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
        })
            .json();
        // console.log(res, ' res inside getCalendarIntegration')
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0];
        }
    }
    catch (e) {
        console.log(e, ' unable to get calendar integration');
    }
};
exports.getCalendarIntegration = getCalendarIntegration;
const getMeetingAssist = async (id) => {
    try {
        const operationName = 'GetMeetingAssistById';
        const query = `
           query GetMeetingAssistById($id: uuid!) {
                Meeting_Assist_by_pk(id: $id) {
                    anyoneCanAddSelf
                    attendeeCanModify
                    attendeeCount
                    attendeeRespondedCount
                    backgroundColor
                    bufferTime
                    calendarId
                    cancelIfAnyRefuse
                    cancelled
                    colorId
                    conferenceApp
                    createdDate
                    duration
                    enableAttendeePreferences
                    enableConference
                    enableHostPreferences
                    endDate
                    eventId
                    expireDate
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    foregroundColor
                    id
                    location
                    minThresholdCount
                    notes
                    priority
                    reminders
                    sendUpdates
                    startDate
                    summary
                    timezone
                    transparency
                    updatedAt
                    useDefaultAlarms
                    userId
                    visibility
                    windowEndDate
                    windowStartDate
                    allowAttendeeUpdatePreferences
                    guaranteeAvailability
                    until
                    originalMeetingId
                    interval
                    frequency
                }
            }

        `;
        const variables = {
            id,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from getMeetingAssist');
        return res?.data?.Meeting_Assist_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get meeting assist from id');
    }
};
exports.getMeetingAssist = getMeetingAssist;
const listMeetingAssistAttendeesGivenMeetingId = async (meetingId) => {
    try {
        const operationName = 'ListMeetingAssistAttendeesByMeetingId';
        const query = `
            query ListMeetingAssistAttendeesByMeetingId($meetingId: uuid!) {
                Meeting_Assist_Attendee(where: {meetingId: {_eq: $meetingId}}) {
                    contactId
                    createdDate
                    emails
                    externalAttendee
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    timezone
                    updatedAt
                    userId
                    primaryEmail
                }
            }
        `;
        const variables = {
            meetingId,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from listMeetingAssistAttendees ');
        return res?.data?.Meeting_Assist_Attendee;
    }
    catch (e) {
        console.log(e, ' unable to list meeting assist attendees');
    }
};
exports.listMeetingAssistAttendeesGivenMeetingId = listMeetingAssistAttendeesGivenMeetingId;
const listMeetingAssistEventsForAttendeeGivenDates = async (attendeeId, hostStartDate, hostEndDate, userTimezone, hostTimezone) => {
    try {
        const operationName = 'ListMeetingAssistEventsForAttendeeGivenDates';
        const query = `
            query ListMeetingAssistEventsForAttendeeGivenDates($attendeeId: String!, $startDate: timestamp!, $endDate: timestamp!) {
                Meeting_Assist_Event(where: {attendeeId: {_eq: $attendeeId}, startDate: {_lte: $endDate}, endDate: {_gte: $startDate}}) {
                    allDay
                    attachments
                    attendeeId
                    attendeesOmitted
                    backgroundColor
                    calendarId
                    colorId
                    createdDate
                    creator
                    endDate
                    endTimeUnspecified
                    eventId
                    eventType
                    extendedProperties
                    externalUser
                    foregroundColor
                    guestsCanModify
                    hangoutLink
                    htmlLink
                    iCalUID
                    id
                    links
                    location
                    locked
                    meetingId
                    notes
                    organizer
                    privateCopy
                    recurrence
                    recurrenceRule
                    recurringEventId
                    source
                    startDate
                    summary
                    timezone
                    transparency
                    updatedAt
                    useDefaultAlarms
                    visibility
                }
            }
        `;
        const startDateInHostTimezone = (0, dayjs_1.default)(hostStartDate.slice(0, 19)).tz(hostTimezone, true);
        const endDateInHostTimezone = (0, dayjs_1.default)(hostEndDate.slice(0, 19)).tz(hostTimezone, true);
        const startDateInUserTimezone = (0, dayjs_1.default)(startDateInHostTimezone)
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const endDateInUserTimezone = (0, dayjs_1.default)(endDateInHostTimezone)
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables: {
                    attendeeId,
                    startDate: startDateInUserTimezone,
                    endDate: endDateInUserTimezone,
                },
            },
        })
            .json();
        console.log(res, ' res from listMeetingAssistEventsForAttendeeGivenDates');
        return res?.data?.Meeting_Assist_Event;
    }
    catch (e) {
        console.log(e, ' unable to list meeting assist events for attendee given dates');
    }
};
exports.listMeetingAssistEventsForAttendeeGivenDates = listMeetingAssistEventsForAttendeeGivenDates;
const updateMeetingAssistAttendee = async (attendee) => {
    try {
        const operationName = 'UpdateMeetingAssistAttendeeById';
        const query = `mutation UpdateMeetingAssistAttendeeById($id: String!${attendee?.emails?.[0]?.value ? ', $emails: jsonb' : ''}${attendee?.hostId ? ', $hostId: uuid!' : null}${attendee?.imAddresses?.[0]?.username ? ', $imAddresses: jsonb' : ''}${attendee?.meetingId ? ', $meetingId: uuid!' : ''}${attendee?.name ? ', $name: String' : ''}${attendee?.phoneNumbers?.[0]?.value ? ', $phoneNumbers: jsonb' : ''}${attendee?.timezone ? ', $timezone: String' : ''}${attendee?.userId ? ', $userId: uuid!' : ''}${attendee?.externalAttendee !== undefined ? ', $externalAttendee: Boolean}' : ''}}) {
            update_Meeting_Assist_Attendee_by_pk(pk_columns: {id: $id}, _set: {${attendee?.emails?.[0]?.value ? 'emails: $emails' : ''}${attendee?.externalAttendee ? ', externalAttendee: true' : ''}${attendee?.hostId ? ', hostId: $hostId' : ''}${attendee?.imAddresses?.[0]?.username ? ', imAddresses: $imAddresses' : ''}${attendee?.meetingId ? ', meetingId: $meetingId' : ''}${attendee?.name ? ', name: $name' : ''}${attendee?.phoneNumbers?.[0]?.value ? ', phoneNumbers: $phoneNumbers' : ''}${attendee?.timezone ? ', timezone: $timezone' : ''}${attendee?.userId ? ', userId: $userId' : ''}}) {
                contactId
                createdDate
                emails
                externalAttendee
                hostId
                id
                imAddresses
                meetingId
                name
                phoneNumbers
                timezone
                updatedAt
                userId
            }
        }
        `;
        let values = {
            id: attendee?.id,
        };
        if (attendee?.name) {
            values.name = attendee?.name;
        }
        if (attendee?.hostId) {
            values.hostId = attendee?.hostId;
        }
        if (attendee?.userId) {
            values.userId = attendee?.userId;
        }
        if (attendee?.emails?.[0]?.value) {
            values.emails = attendee?.emails;
        }
        if (attendee?.phoneNumbers?.[0]?.value) {
            values.phoneNumbers = attendee?.phoneNumbers;
        }
        if (attendee?.imAddresses?.[0]?.username) {
            values.imAddresses = attendee?.imAddresses;
        }
        if (attendee?.meetingId) {
            values.meetingId = attendee?.meetingId;
        }
        if (attendee?.timezone) {
            values.timezone = attendee?.timezone;
        }
        const variables = values;
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from insert_Meeting_Assist_Attendee_one');
    }
    catch (e) {
        console.log(e, ' unable to update meeting attendee');
    }
};
exports.updateMeetingAssistAttendee = updateMeetingAssistAttendee;
const generatePreferredTimesForRecurringMeetingAssist = (originalPreferredTimes, recurringMeetingAssist, recurringAttendee) => {
    console.log(originalPreferredTimes, recurringMeetingAssist, ' originalPreferredTimes, recurringMeetingAssist');
    const recurringPreferredTimes = [];
    for (const preferredTime of originalPreferredTimes) {
        const recurringPreferredTime = {
            id: (0, uuid_1.v4)(),
            meetingId: recurringMeetingAssist?.id,
            startTime: preferredTime?.startTime,
            endTime: preferredTime?.endTime,
            updatedAt: (0, dayjs_1.default)().format(),
            createdDate: (0, dayjs_1.default)().format(),
            hostId: recurringMeetingAssist?.userId,
            attendeeId: recurringAttendee?.id,
        };
        if (preferredTime?.dayOfWeek && preferredTime?.dayOfWeek > 0) {
            recurringPreferredTime.dayOfWeek = preferredTime.dayOfWeek;
        }
        recurringPreferredTimes.push(recurringPreferredTime);
    }
    return recurringPreferredTimes;
};
exports.generatePreferredTimesForRecurringMeetingAssist = generatePreferredTimesForRecurringMeetingAssist;
const generateAttendeesAndPreferredTimesForRecurringMeetingAssist = (originalAttendees, recurringMeetingAssist, originalPreferredTimes) => {
    console.log(originalAttendees, recurringMeetingAssist, originalPreferredTimes, ' originalAttendees, recurringMeetingAssist, originalPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist before');
    const recurringAttendees = [];
    const recurringPreferredTimes = [];
    for (const originalAttendee of originalAttendees) {
        const recurringAttendee = {
            id: (0, uuid_1.v4)(),
            name: originalAttendee?.name,
            hostId: originalAttendee?.hostId,
            userId: originalAttendee?.userId,
            emails: originalAttendee?.emails,
            contactId: originalAttendee?.contactId,
            phoneNumbers: originalAttendee?.phoneNumbers,
            imAddresses: originalAttendee?.imAddresses,
            meetingId: recurringMeetingAssist?.id,
            createdDate: (0, dayjs_1.default)().format(),
            updatedAt: (0, dayjs_1.default)().format(),
            timezone: recurringMeetingAssist?.timezone,
            externalAttendee: originalAttendee?.externalAttendee,
            primaryEmail: originalAttendee?.primaryEmail,
        };
        const attendeeIndex = originalPreferredTimes?.findIndex((o) => o?.attendeeId === originalAttendee?.id);
        console.log(attendeeIndex, ' attendeeIndex inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist');
        console.log(originalPreferredTimes, ' originalPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist');
        if (originalPreferredTimes &&
            originalPreferredTimes?.length > 0 &&
            typeof attendeeIndex === 'number' &&
            attendeeIndex > -1) {
            const recurringPreferredTimesForAttendee = (0, exports.generatePreferredTimesForRecurringMeetingAssist)(originalPreferredTimes?.filter((o) => o?.attendeeId === originalAttendee?.id), recurringMeetingAssist, recurringAttendee);
            recurringPreferredTimes.push(...recurringPreferredTimesForAttendee);
        }
        recurringAttendees.push(recurringAttendee);
    }
    console.log(recurringAttendees, ' recurringAttendees after inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist');
    console.log(recurringPreferredTimes, ' recurringPreferredTimes after inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist');
    return { recurringAttendees, recurringPreferredTimes };
};
exports.generateAttendeesAndPreferredTimesForRecurringMeetingAssist = generateAttendeesAndPreferredTimesForRecurringMeetingAssist;
const generateAttendeesAndPreferredTimesForRecurringMeetingAssists = (originalAttendees, recurringMeetingAssists, originalPreferredTimes) => {
    const recurringAttendees = [];
    const recurringPreferredTimes = [];
    console.log(recurringAttendees, ' recurringAttendees inside generateAttendeesForRecurringMeetingAssists before');
    for (const recurringMeetingAssist of recurringMeetingAssists) {
        const newRecurringAttendeesAndPreferredTimes = (0, exports.generateAttendeesAndPreferredTimesForRecurringMeetingAssist)(originalAttendees, recurringMeetingAssist, originalPreferredTimes);
        recurringAttendees.push(...newRecurringAttendeesAndPreferredTimes?.recurringAttendees);
        if (newRecurringAttendeesAndPreferredTimes?.recurringPreferredTimes?.length >
            0) {
            recurringPreferredTimes.push(...newRecurringAttendeesAndPreferredTimes?.recurringPreferredTimes);
        }
    }
    console.log(recurringAttendees, ' recurringAttendees inside generateAttendeesAndPreferredTimesForRecurringMeetingAssists after');
    console.log(recurringPreferredTimes, ' recurringPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssists after generation');
    return { recurringAttendees, recurringPreferredTimes };
};
exports.generateAttendeesAndPreferredTimesForRecurringMeetingAssists = generateAttendeesAndPreferredTimesForRecurringMeetingAssists;
const insertMeetingAssistAttendees = async (attendees) => {
    try {
        console.log(attendees, ' attendees called inside insertMeetingAssistAttendees');
        const operationName = 'InsertMeetingAssistAttendees';
        const query = `
            mutation InsertMeetingAssistAttendees($attendees: [Meeting_Assist_Attendee_insert_input!]!) {
                insert_Meeting_Assist_Attendee(objects: $attendees) {
                    affected_rows
                    returning {
                    contactId
                    createdDate
                    emails
                    externalAttendee
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    primaryEmail
                    timezone
                    updatedAt
                    userId
                    }
                }
            }
        `;
        const variables = {
            attendees,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from insert_Meeting_Assist_Attendee');
        return res?.data?.insert_Meeting_Assist_Attendee?.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable to insert meeting assist attendees');
    }
};
exports.insertMeetingAssistAttendees = insertMeetingAssistAttendees;
const upsertOneMeetingAssistAttendee = async (attendee) => {
    try {
        const operationName = 'InsertMeetingAssistAttendee';
        const query = `
            mutation InsertMeetingAssistAttendee($attendee: Meeting_Assist_Attendee_insert_input!) {
                insert_Meeting_Assist_Attendee_one(object: $attendee, 
                    on_conflict: {
                    constraint: Meeting_Assist_Attendee_pkey, 
                    update_columns: [
                        contactId,
                        emails,
                        externalAttendee,
                        imAddresses,
                        name,
                        phoneNumbers,
                        primaryEmail,
                        timezone,
                        updatedAt,
                        userId,
                ]}) {
                    contactId
                    createdDate
                    emails
                    externalAttendee
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    primaryEmail
                    timezone
                    updatedAt
                    userId
                }
            }

        `;
        const variables = {
            attendee,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from insert_Meeting_Assist_Attendee_one');
        return res?.data?.insert_Meeting_Assist_Attendee_one;
    }
    catch (e) { }
};
exports.upsertOneMeetingAssistAttendee = upsertOneMeetingAssistAttendee;
const deleteMeetingAssistAttendee = async (id) => {
    try {
        const operationName = 'DeletMeetingAssistAttendee';
        const query = `
            mutation DeletMeetingAssistAttendee($id: String!) {
                delete_Meeting_Assist_Attendee_by_pk(id: $id) {
                    contactId
                    createdDate
                    emails
                    externalAttendee
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    primaryEmail
                    timezone
                    updatedAt
                    userId
                }
            }
        `;
        const variables = {
            id,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from deleteMeetingAssistAttendee ');
        return res?.data?.delete_Meeting_Assist_Attendee_by_pk;
    }
    catch (e) {
        console.log(e, ' delete attendee');
    }
};
exports.deleteMeetingAssistAttendee = deleteMeetingAssistAttendee;
const getMeetingAssistAttendee = async (id) => {
    try {
        const operationName = 'GetMeetingAssistAttendeeById';
        const query = `
            query GetMeetingAssistAttendeeById($id: String!) {
                Meeting_Assist_Attendee_by_pk(id: $id) {
                    contactId
                    createdDate
                    emails
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    timezone
                    updatedAt
                    userId
                    externalAttendee
                    primaryEmail
                }
            }
        `;
        const variables = {
            id,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from getMeetingAssistAttendee');
        return res?.data?.Meeting_Assist_Attendee_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get meeting assist attendee');
    }
};
exports.getMeetingAssistAttendee = getMeetingAssistAttendee;
const getMeetingAssistAttendeeByEmail = async (primaryEmail, meetingId) => {
    try {
        const operationName = 'ListMeetingAssistAttendeeByEmail';
        const query = `
            query ListMeetingAssistAttendeeByEmail($meetingId: uuid!, $primaryEmail: String) {
                Meeting_Assist_Attendee(where: {meetingId: {_eq: $meetingId}, primaryEmail: {_eq: $primaryEmail}}, limit: 1) {
                    contactId
                    createdDate
                    emails
                    externalAttendee
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    primaryEmail
                    timezone
                    updatedAt
                    userId
                }
            }
        `;
        const variables = {
            primaryEmail,
            meetingId,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from getMeetingAssistAttendee');
        return res?.data?.Meeting_Assist_Attendee?.[0];
    }
    catch (e) {
        console.log(e, ' unable to get meeting assist attendee by email');
    }
};
exports.getMeetingAssistAttendeeByEmail = getMeetingAssistAttendeeByEmail;
const updateMeetingAssistAttendanceCount = async (id, attendeeCount, attendeeRespondedCount) => {
    try {
        const operationName = 'UpdateMeetingAssistCount';
        const query = `
        mutation UpdateMeetingAssistCount($id: uuid!, $attendeeCount: Int!, $attendeeRespondedCount: Int!) {
            update_Meeting_Assist_by_pk(pk_columns: {id: $id}, _set: {attendeeCount: $attendeeCount, attendeeRespondedCount: $attendeeRespondedCount}) {
              anyoneCanAddSelf
              attendeeCanModify
              attendeeCount
              attendeeRespondedCount
              backgroundColor
              bufferTime
              calendarId
              cancelIfAnyRefuse
              cancelled
              colorId
              conferenceApp
              createdDate
              duration
              enableAttendeePreferences
              enableConference
              enableHostPreferences
              endDate
              eventId
              expireDate
              foregroundColor
              guestsCanInviteOthers
              id
              guestsCanSeeOtherGuests
              location
              minThresholdCount
              notes
              priority
              reminders
              sendUpdates
              startDate
              summary
              timezone
              transparency
              updatedAt
              useDefaultAlarms
              userId
              visibility
              windowEndDate
              windowStartDate
              allowAttendeeUpdatePreferences
              guaranteeAvailability
            }
          }          
        `;
        const variables = {
            id,
            attendeeCount,
            attendeeRespondedCount,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from updateMeetingAssistAttendanceCount');
        return res?.data?.update_Meeting_Assist_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to update attendance count');
    }
};
exports.updateMeetingAssistAttendanceCount = updateMeetingAssistAttendanceCount;
const getUserContactInfo = async (id) => {
    try {
        const operationName = 'GetUserContactInfo';
        const query = `
            query GetUserContactInfo($id: String!) {
                User_Contact_Info_by_pk(id: $id) {
                    createdDate
                    id
                    name
                    primary
                    type
                    updatedAt
                    userId
                }
            }
        `;
        const variables = {
            id,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from getUserContactInfo');
        return res?.data?.User_Contact_Info_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get user contact info');
    }
};
exports.getUserContactInfo = getUserContactInfo;
const listEventsForUserGivenDates = async (userId, hostStartDate, hostEndDate, userTimezone, hostTimezone) => {
    try {
        const operationName = 'listEventsForUser';
        const query = `
            query listEventsForUser($userId: uuid!, $startDate: timestamp!, $endDate: timestamp!) {
                Event(where: {userId: {_eq: $userId}, endDate: {_gte: $startDate}, startDate: {_lte: $endDate}, deleted: {_neq: true}, allDay: {_neq: true}}) {
                    allDay
                    anyoneCanAddSelf
                    attachments
                    attendeesOmitted
                    backgroundColor
                    calendarId
                    colorId
                    conferenceId
                    copyAvailability
                    copyCategories
                    copyDuration
                    copyIsBreak
                    copyIsExternalMeeting
                    copyIsMeeting
                    copyModifiable
                    copyPriorityLevel
                    copyReminders
                    copyTimeBlocking
                    copyTimePreference
                    createdDate
                    creator
                    dailyTaskList
                    deleted
                    duration
                    endDate
                    endTimeUnspecified
                    eventId
                    eventType
                    extendedProperties
                    followUpEventId
                    forEventId
                    foregroundColor
                    guestsCanInviteOthers
                    guestsCanModify
                    guestsCanSeeOtherGuests
                    hangoutLink
                    hardDeadline
                    htmlLink
                    iCalUID
                    id
                    isBreak
                    isExternalMeeting
                    isExternalMeetingModifiable
                    isFollowUp
                    isMeeting
                    isMeetingModifiable
                    isPostEvent
                    isPreEvent
                    links
                    location
                    locked
                    maxAttendees
                    meetingId
                    method
                    modifiable
                    negativeImpactDayOfWeek
                    negativeImpactScore
                    negativeImpactTime
                    notes
                    organizer
                    originalAllDay
                    originalStartDate
                    originalTimezone
                    positiveImpactDayOfWeek
                    positiveImpactScore
                    positiveImpactTime
                    postEventId
                    preEventId
                    preferredDayOfWeek
                    preferredEndTimeRange
                    preferredStartTimeRange
                    preferredTime
                    priority
                    privateCopy
                    recurrence
                    recurrenceRule
                    recurringEventId
                    sendUpdates
                    softDeadline
                    source
                    startDate
                    status
                    summary
                    taskId
                    taskType
                    timeBlocking
                    timezone
                    title
                    transparency
                    unlink
                    updatedAt
                    useDefaultAlarms
                    userId
                    userModifiedAvailability
                    userModifiedCategories
                    userModifiedDuration
                    userModifiedIsBreak
                    userModifiedIsExternalMeeting
                    userModifiedIsMeeting
                    userModifiedModifiable
                    userModifiedPriorityLevel
                    userModifiedReminders
                    userModifiedTimeBlocking
                    userModifiedTimePreference
                    visibility
                    weeklyTaskList
                    byWeekDay
                    localSynced
                    userModifiedColor
                    copyColor
                    copyExternalMeetingModifiable
                    userModifiedExternalMeetingModifiable
                    userModifiedMeetingModifiable
                }
            }
        `;
        // get events
        // local date
        const startDateInHostTimezone = (0, dayjs_1.default)(hostStartDate.slice(0, 19)).tz(hostTimezone, true);
        const endDateInHostTimezone = (0, dayjs_1.default)(hostEndDate.slice(0, 19)).tz(hostTimezone, true);
        const startDateInUserTimezone = startDateInHostTimezone
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const endDateInUserTimezone = endDateInHostTimezone
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables: {
                    userId,
                    startDate: startDateInUserTimezone,
                    endDate: endDateInUserTimezone,
                },
            },
        })
            .json();
        console.log(res, ' res from listEventsforUser');
        return res?.data?.Event;
    }
    catch (e) {
        console.log(e, ' listEventsForUser');
    }
};
exports.listEventsForUserGivenDates = listEventsForUserGivenDates;
const findEventsForUserGivenMeetingId = async (userId, hostStartDate, hostEndDate, userTimezone, hostTimezone, meetingId) => {
    try {
        const operationName = 'findEventsForUserGivenMeetingId';
        const query = `
            query findEventsForUserGivenMeetingId($userId: uuid!, $startDate: timestamp!, $endDate: timestamp!, $meetingId: String!) {
                Event(where: {userId: {_eq: $userId}, startDate: {_lte: $endDate}, endDate: {_gte: $startDate}, deleted: {_neq: true}, allDay: {_neq: true}, meetingId: {_eq: $meetingId}}, limit: 1) {
                    allDay
                    anyoneCanAddSelf
                    attachments
                    attendeesOmitted
                    backgroundColor
                    calendarId
                    colorId
                    conferenceId
                    copyAvailability
                    copyCategories
                    copyDuration
                    copyIsBreak
                    copyIsExternalMeeting
                    copyIsMeeting
                    copyModifiable
                    copyPriorityLevel
                    copyReminders
                    copyTimeBlocking
                    copyTimePreference
                    createdDate
                    creator
                    dailyTaskList
                    deleted
                    duration
                    endDate
                    endTimeUnspecified
                    eventId
                    eventType
                    extendedProperties
                    followUpEventId
                    forEventId
                    foregroundColor
                    guestsCanInviteOthers
                    guestsCanModify
                    guestsCanSeeOtherGuests
                    hangoutLink
                    hardDeadline
                    htmlLink
                    iCalUID
                    id
                    isBreak
                    isExternalMeeting
                    isExternalMeetingModifiable
                    isFollowUp
                    isMeeting
                    isMeetingModifiable
                    isPostEvent
                    isPreEvent
                    links
                    location
                    locked
                    maxAttendees
                    meetingId
                    method
                    modifiable
                    negativeImpactDayOfWeek
                    negativeImpactScore
                    negativeImpactTime
                    notes
                    organizer
                    originalAllDay
                    originalStartDate
                    originalTimezone
                    positiveImpactDayOfWeek
                    positiveImpactScore
                    positiveImpactTime
                    postEventId
                    preEventId
                    preferredDayOfWeek
                    preferredEndTimeRange
                    preferredStartTimeRange
                    preferredTime
                    priority
                    privateCopy
                    recurrence
                    recurrenceRule
                    recurringEventId
                    sendUpdates
                    softDeadline
                    source
                    startDate
                    status
                    summary
                    taskId
                    taskType
                    timeBlocking
                    timezone
                    title
                    transparency
                    unlink
                    updatedAt
                    useDefaultAlarms
                    userId
                    userModifiedAvailability
                    userModifiedCategories
                    userModifiedDuration
                    userModifiedIsBreak
                    userModifiedIsExternalMeeting
                    userModifiedIsMeeting
                    userModifiedModifiable
                    userModifiedPriorityLevel
                    userModifiedReminders
                    userModifiedTimeBlocking
                    userModifiedTimePreference
                    visibility
                    weeklyTaskList
                    byWeekDay
                    localSynced
                    userModifiedColor
                    copyColor
                    copyExternalMeetingModifiable
                    userModifiedExternalMeetingModifiable
                    userModifiedMeetingModifiable
                }
            }
        `;
        // get events
        // local date
        const startDateInHostTimezone = (0, dayjs_1.default)(hostStartDate.slice(0, 19)).tz(hostTimezone, true);
        const endDateInHostTimezone = (0, dayjs_1.default)(hostEndDate.slice(0, 19)).tz(hostTimezone, true);
        const startDateInUserTimezone = (0, dayjs_1.default)(startDateInHostTimezone)
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const endDateInUserTimezone = (0, dayjs_1.default)(endDateInHostTimezone)
            .tz(userTimezone)
            .format()
            .slice(0, 19);
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables: {
                    userId,
                    startDate: startDateInUserTimezone,
                    endDate: endDateInUserTimezone,
                    meetingId,
                },
            },
        })
            .json();
        console.log(res, ' res from findEventsForUserGivenMeetingId');
        return res?.data?.Event;
    }
    catch (e) {
        console.log(e, ' unable to find event for user given meetingId');
    }
};
exports.findEventsForUserGivenMeetingId = findEventsForUserGivenMeetingId;
const listMeetingAssistPreferredTimeRangesGivenMeetingId = async (meetingId) => {
    try {
        const operationName = 'ListMeetingAssistPrefereredTimeRangesByMeetingId';
        const query = `
            query ListMeetingAssistPrefereredTimeRangesByMeetingId($meetingId: uuid!) {
                Meeting_Assist_Preferred_Time_Range(where: {meetingId: {_eq: $meetingId}}) {
                    attendeeId
                    createdDate
                    dayOfWeek
                    endTime
                    hostId
                    id
                    meetingId
                    startTime
                    updatedAt
                }
             }

        `;
        const variables = {
            meetingId,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from listMeetingAssistAttendees ');
        return res?.data?.Meeting_Assist_Preferred_Time_Range;
    }
    catch (e) {
        console.log(e, ' uanble to list meeting assist preferred time ranges');
    }
};
exports.listMeetingAssistPreferredTimeRangesGivenMeetingId = listMeetingAssistPreferredTimeRangesGivenMeetingId;
const generateAvailableSlotsforTimeWindow = (windowStartDate, windowEndDate, slotDuration, hostPreferences, hostTimezone, userTimezone, notAvailableSlotsInUserTimezone) => {
    const uniqNotAvailableSlotsInUserTimezone = lodash_1.default.uniqWith(notAvailableSlotsInUserTimezone, (val, other) => (0, dayjs_1.default)(val.startDate).tz(userTimezone).format('YYYY-MM-DDTHH:mm') ===
        (0, dayjs_1.default)(other.startDate).tz(userTimezone).format('YYYY-MM-DDTHH:mm') &&
        (0, dayjs_1.default)(val.endDate).tz(userTimezone).format('YYYY-MM-DDTHH:mm') ===
            (0, dayjs_1.default)(other.endDate).tz(userTimezone).format('YYYY-MM-DDTHH:mm'));
    const diffDays = (0, dayjs_1.default)(windowEndDate).diff((0, dayjs_1.default)(windowStartDate), 'd');
    const startDatesForEachDayInHostTimezone = [];
    const availableSlots = [];
    const availableSlotsByDate = {};
    for (let i = 0; i <= diffDays; i++) {
        startDatesForEachDayInHostTimezone.push((0, dayjs_1.default)(windowStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .add(i, 'day')
            .format());
    }
    if (diffDays < 1) {
        const generatedSlots = (0, exports.generateAvailableSlotsForDate)(slotDuration, (0, dayjs_1.default)(windowStartDate.slice(0, 19)).tz(hostTimezone, true).format(), hostPreferences, hostTimezone, userTimezone, notAvailableSlotsInUserTimezone, true, true, (0, dayjs_1.default)(windowEndDate.slice(0, 19)).tz(hostTimezone, true).format());
        //  0123456789
        //  2020-04-02T08:02:17-05:00
        availableSlots.push(...generatedSlots);
        availableSlotsByDate[`${windowStartDate?.slice(0, 10)}`] = generatedSlots;
    }
    else {
        for (let i = 0; i < startDatesForEachDayInHostTimezone.length; i++) {
            const filteredNotAvailableSlotsInUserTimezone = uniqNotAvailableSlotsInUserTimezone?.filter((na) => (0, dayjs_1.default)(na?.startDate).tz(userTimezone).format('YYYY-MM-DD') ===
                (0, dayjs_1.default)(startDatesForEachDayInHostTimezone?.[i])
                    .tz(userTimezone)
                    .format('YYYY-MM-DD'));
            if (i === 0) {
                const generatedSlots = (0, exports.generateAvailableSlotsForDate)(slotDuration, startDatesForEachDayInHostTimezone?.[i], hostPreferences, hostTimezone, userTimezone, filteredNotAvailableSlotsInUserTimezone, true, false, (0, dayjs_1.default)(windowEndDate.slice(0, 19)).tz(hostTimezone, true).format());
                //  0123456789
                //  2020-04-02T08:02:17-05:00
                availableSlots.push(...generatedSlots);
                availableSlotsByDate[`${startDatesForEachDayInHostTimezone?.[i]?.slice(0, 10)}`] = generatedSlots;
                continue;
            }
            if (i === startDatesForEachDayInHostTimezone.length - 1) {
                const generatedSlots = (0, exports.generateAvailableSlotsForDate)(slotDuration, startDatesForEachDayInHostTimezone?.[i], hostPreferences, hostTimezone, userTimezone, filteredNotAvailableSlotsInUserTimezone, false, true, (0, dayjs_1.default)(windowEndDate.slice(0, 19)).tz(hostTimezone, true).format());
                availableSlots.push(...generatedSlots);
                availableSlotsByDate[`${startDatesForEachDayInHostTimezone?.[i]?.slice(0, 10)}`] = generatedSlots;
                continue;
            }
            const generatedSlots = (0, exports.generateAvailableSlotsForDate)(slotDuration, startDatesForEachDayInHostTimezone?.[i], hostPreferences, hostTimezone, userTimezone, filteredNotAvailableSlotsInUserTimezone);
            availableSlots.push(...generatedSlots);
            availableSlotsByDate[`${startDatesForEachDayInHostTimezone?.[i]?.slice(0, 10)}`] = generatedSlots;
        }
    }
    console.log(availableSlotsByDate, ' availableSlotsByDate inside function');
    return { availableSlots, availableSlotsByDate };
};
exports.generateAvailableSlotsforTimeWindow = generateAvailableSlotsforTimeWindow;
/**
 * @params notAvailableSlotsInUserTimezone - events with transparency: 'opaque' as not available
 */
const generateAvailableSlotsForDate = (slotDuration, userStartDateInHostTimezone, hostPreferences, hostTimezone, userTimezone, notAvailableSlotsInUserTimezone, isFirstDay, isLastDay, userEndDateInHostTimezone) => {
    if (isFirstDay && isLastDay && userEndDateInHostTimezone) {
        const endTimesByHost = hostPreferences.endTimes;
        const dayOfWeekIntByUser = (0, date_fns_1.getISODay)((0, dayjs_1.default)(userStartDateInHostTimezone).tz(userTimezone).toDate());
        const dayOfMonthByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .date();
        let startHourByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .hour();
        const flooredValue = Math.floor(60 / slotDuration);
        let minuteValueByUser = 0;
        if ((0, dayjs_1.default)(userStartDateInHostTimezone).tz(userTimezone).minute() !== 0) {
            for (let i = 0; i < flooredValue; i++) {
                const endMinutes = (i + 1) * slotDuration;
                const startMinutes = i * slotDuration;
                if ((0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .isBetween((0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .minute(startMinutes), (0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .minute(endMinutes), 'minute', '[)')) {
                    minuteValueByUser = endMinutes;
                }
            }
        }
        if ((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .isBetween((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .minute(flooredValue * slotDuration), (0, dayjs_1.default)(userStartDateInHostTimezone).tz(userTimezone).minute(59), 'minute', '[)')) {
            startHourByUser += 1;
            minuteValueByUser = 0;
        }
        const startMinuteByUser = minuteValueByUser;
        const endHourByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.hour ?? 20;
        const endMinuteByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.minutes ?? 0;
        const endHourByUser = (0, dayjs_1.default)(userEndDateInHostTimezone)
            .tz(hostTimezone)
            .hour(endHourByHost)
            .tz(userTimezone)
            .hour();
        const endMinuteByUser = (0, dayjs_1.default)(userEndDateInHostTimezone)
            .tz(hostTimezone)
            .minute(endMinuteByHost)
            .tz(userTimezone)
            .minute();
        // validate values before calculating
        const startTimes = hostPreferences.startTimes;
        const workStartHourByHost = startTimes?.find((i) => i.day === dayOfWeekIntByUser)?.hour || 8;
        const workStartMinuteByHost = startTimes?.find((i) => i.day === dayOfWeekIntByUser)?.minutes || 0;
        const workStartHourByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .hour(workStartHourByHost)
            .tz(userTimezone)
            .hour();
        const workStartMinuteByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .minute(workStartMinuteByHost)
            .tz(userTimezone)
            .minute();
        if ((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .isAfter((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .hour(endHourByHost)
            .minute(endMinuteByHost))) {
            // return empty as outside of work time
            return [];
        }
        // change to work start time as after host start time
        if ((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .isBefore((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost))) {
            const startDuration = dayjs_1.default.duration({
                hours: workStartHourByUser,
                minutes: workStartMinuteByUser,
            });
            const endDuration = dayjs_1.default.duration({
                hours: endHourByUser,
                minutes: endMinuteByUser,
            });
            const totalDuration = endDuration.subtract(startDuration);
            const totalMinutes = totalDuration.asMinutes();
            const availableSlotsInUserTimezone = [];
            console.log(userStartDateInHostTimezone, endTimesByHost, dayOfWeekIntByUser, dayOfMonthByUser, startHourByUser, startMinuteByUser, endHourByUser, endMinuteByUser, timezone_1.default, `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
            for (let i = 0; i < totalMinutes; i += slotDuration) {
                if (i > totalMinutes) {
                    continue;
                }
                availableSlotsInUserTimezone.push({
                    id: (0, uuid_1.v4)(),
                    startDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                        .tz(userTimezone)
                        .hour(startHourByUser)
                        .minute(startMinuteByUser)
                        .add(i, 'minute')
                        .second(0)
                        .format(),
                    endDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                        .tz(userTimezone)
                        .hour(startHourByUser)
                        .minute(startMinuteByUser)
                        .add(i + slotDuration, 'minute')
                        .second(0)
                        .format(),
                });
            }
            console.log(availableSlotsInUserTimezone, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
            // filter out unavailable times
            const filteredAvailableSlotsInUserTimezone = availableSlotsInUserTimezone.filter((a) => {
                const foundIndex = notAvailableSlotsInUserTimezone?.findIndex((na) => {
                    const partA = (0, dayjs_1.default)(a.endDate)
                        .tz(userTimezone)
                        .second(0)
                        .isBetween((0, dayjs_1.default)(na.startDate).tz(userTimezone).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).tz(userTimezone).subtract(1, 'm').second(0), 'm', '[]');
                    const partB = (0, dayjs_1.default)(a.startDate)
                        .tz(userTimezone)
                        .second(0)
                        .isBetween((0, dayjs_1.default)(na.startDate).tz(userTimezone).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).tz(userTimezone).subtract(1, 'm').second(0), 'm', '[]');
                    const partC = (0, dayjs_1.default)(na.startDate)
                        .tz(userTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') ===
                        (0, dayjs_1.default)(a.startDate)
                            .tz(userTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm') &&
                        (0, dayjs_1.default)(na.endDate)
                            .tz(userTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm') ===
                            (0, dayjs_1.default)(a.endDate)
                                .tz(userTimezone)
                                .second(0)
                                .format('YYYY-MM-DDTHH:mm');
                    const isNotAvailable = partA || partB || partC;
                    console.log(a, na, ' a, na');
                    return isNotAvailable;
                });
                console.log(foundIndex, ' foundIndex');
                if (foundIndex !== undefined && foundIndex > -1) {
                    return false;
                }
                return true;
            });
            console.log(filteredAvailableSlotsInUserTimezone, ' filteredAvailableSlots');
            return filteredAvailableSlotsInUserTimezone;
        }
        const startDuration = dayjs_1.default.duration({
            hours: startHourByUser,
            minutes: startMinuteByUser,
        });
        const endDuration = dayjs_1.default.duration({
            hours: endHourByUser,
            minutes: endMinuteByUser,
        });
        const totalDuration = endDuration.subtract(startDuration);
        const totalMinutes = totalDuration.asMinutes();
        console.log(totalMinutes, ' totalMinutes inside first and last same day');
        const availableSlotsInUserTimezone = [];
        console.log(userStartDateInHostTimezone, endTimesByHost, dayOfWeekIntByUser, endHourByHost, endMinuteByHost, hostTimezone, `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside first & last Day inside generateTimeslots`);
        for (let i = 0; i < totalMinutes; i += slotDuration) {
            if (i > totalMinutes) {
                continue;
            }
            availableSlotsInUserTimezone.push({
                id: (0, uuid_1.v4)(),
                startDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .hour(startHourByUser)
                    .minute(startMinuteByUser)
                    .add(i, 'minute')
                    .second(0)
                    .format(),
                endDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .hour(startHourByUser)
                    .minute(startMinuteByUser)
                    .add(i + slotDuration, 'minute')
                    .second(0)
                    .format(),
            });
        }
        console.log(availableSlotsInUserTimezone, ' availableSlots inside first & last same day');
        const filteredAvailableSlotsInUserTimezone = availableSlotsInUserTimezone.filter((a) => {
            const foundIndex = notAvailableSlotsInUserTimezone?.findIndex((na) => {
                const partA = (0, dayjs_1.default)(a.endDate)
                    .tz(userTimezone)
                    .second(0)
                    .isBetween((0, dayjs_1.default)(na.startDate).tz(userTimezone).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).tz(userTimezone).subtract(1, 'm').second(0), 'm', '[]');
                const partB = (0, dayjs_1.default)(a.startDate)
                    .tz(userTimezone)
                    .second(0)
                    .isBetween((0, dayjs_1.default)(na.startDate).tz(userTimezone).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).tz(userTimezone).subtract(1, 'm').second(0), 'm', '[]');
                const partC = (0, dayjs_1.default)(na.startDate)
                    .tz(userTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') ===
                    (0, dayjs_1.default)(a.startDate)
                        .tz(userTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') &&
                    (0, dayjs_1.default)(na.endDate)
                        .tz(userTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') ===
                        (0, dayjs_1.default)(a.endDate)
                            .tz(userTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm');
                const isNotAvailable = partA || partB || partC;
                console.log(a, na, ' a, na');
                return isNotAvailable;
            });
            console.log(foundIndex, ' foundIndex');
            if (foundIndex !== undefined && foundIndex > -1) {
                return false;
            }
            return true;
        });
        console.log(filteredAvailableSlotsInUserTimezone, ' filteredAvailableSlots');
        return filteredAvailableSlotsInUserTimezone;
    }
    if (isFirstDay) {
        // firstday can be started outside of work time
        // if firstDay start is after end time -- return []
        const endTimesByHost = hostPreferences.endTimes;
        const dayOfWeekIntByUser = (0, date_fns_1.getISODay)((0, dayjs_1.default)(userStartDateInHostTimezone).tz(userTimezone).toDate());
        // month is zero-indexed
        // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
        const dayOfMonthByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .date();
        let startHourByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .hour();
        // create slot sizes
        const flooredValue = Math.floor(60 / slotDuration);
        let minuteValueByUser = 0;
        if ((0, dayjs_1.default)(userStartDateInHostTimezone).tz(userTimezone).minute() !== 0) {
            for (let i = 0; i < flooredValue; i++) {
                const endMinutes = (i + 1) * slotDuration;
                const startMinutes = i * slotDuration;
                if ((0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .isBetween((0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .minute(startMinutes), (0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .minute(endMinutes), 'minute', '[)')) {
                    minuteValueByUser = endMinutes;
                }
            }
        }
        if ((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .isBetween((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .minute(flooredValue * slotDuration), (0, dayjs_1.default)(userStartDateInHostTimezone).tz(userTimezone).minute(59), 'minute', '[)')) {
            startHourByUser += 1;
            minuteValueByUser = 0;
        }
        const startMinuteByUser = minuteValueByUser;
        // convert to user timezone so everything is linked to user timezone
        const endHourByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.hour ?? 20;
        const endMinuteByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.minutes ?? 0;
        const endHourByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .hour(endHourByHost)
            .tz(userTimezone)
            .hour();
        const endMinuteByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .minute(endMinuteByHost)
            .tz(userTimezone)
            .minute();
        // validate values before calculating
        const startTimes = hostPreferences.startTimes;
        const workStartHourByHost = startTimes?.find((i) => i.day === dayOfWeekIntByUser)?.hour || 8;
        const workStartMinuteByHost = startTimes?.find((i) => i.day === dayOfWeekIntByUser)?.minutes || 0;
        const workStartHourByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .hour(workStartHourByHost)
            .tz(userTimezone)
            .hour();
        const workStartMinuteByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .minute(workStartMinuteByHost)
            .tz(userTimezone)
            .minute();
        if ((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .isAfter((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .hour(endHourByHost)
            .minute(endMinuteByHost)
            .tz(userTimezone))) {
            // return empty as outside of work time
            return [];
        }
        // change to work start time as after host start time
        if ((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(userTimezone)
            .isBefore((0, dayjs_1.default)(userStartDateInHostTimezone)
            .tz(hostTimezone)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost)
            .tz(userTimezone))) {
            const startDuration = dayjs_1.default.duration({
                hours: workStartHourByUser,
                minutes: workStartMinuteByUser,
            });
            const endDuration = dayjs_1.default.duration({
                hours: endHourByUser,
                minutes: endMinuteByUser,
            });
            const totalDuration = endDuration.subtract(startDuration);
            const totalMinutes = totalDuration.asMinutes();
            const availableSlotsInUserTimezone = [];
            console.log(userStartDateInHostTimezone, endTimesByHost, dayOfWeekIntByUser, dayOfMonthByUser, startHourByUser, startMinuteByUser, endHourByUser, endMinuteByUser, timezone_1.default, `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
            for (let i = 0; i < totalMinutes; i += slotDuration) {
                if (i > totalMinutes) {
                    continue;
                }
                availableSlotsInUserTimezone.push({
                    id: (0, uuid_1.v4)(),
                    startDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                        .tz(userTimezone)
                        .hour(workStartHourByUser)
                        .minute(workStartMinuteByUser)
                        .add(i, 'minute')
                        .second(0)
                        .format(),
                    endDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                        .tz(userTimezone)
                        .hour(workStartHourByUser)
                        .minute(workStartMinuteByUser)
                        .add(i + slotDuration, 'minute')
                        .second(0)
                        .format(),
                });
            }
            console.log(availableSlotsInUserTimezone, ' timeSlots inside generateTimeSlots for first day where startDate is before work start time');
            // filter out unavailable times
            const filteredAvailableSlotsInUserTimezone = availableSlotsInUserTimezone.filter((a) => {
                const foundIndex = notAvailableSlotsInUserTimezone?.findIndex((na) => {
                    const partA = (0, dayjs_1.default)(a.endDate)
                        .second(0)
                        .isBetween((0, dayjs_1.default)(na.startDate).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).subtract(1, 'm').second(0), 'm', '[]');
                    const partB = (0, dayjs_1.default)(a.startDate)
                        .second(0)
                        .isBetween((0, dayjs_1.default)(na.startDate).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).subtract(1, 'm').second(0), 'm', '[]');
                    const partC = (0, dayjs_1.default)(na.startDate).second(0).format('YYYY-MM-DDTHH:mm') ===
                        (0, dayjs_1.default)(a.startDate).second(0).format('YYYY-MM-DDTHH:mm') &&
                        (0, dayjs_1.default)(na.endDate).second(0).format('YYYY-MM-DDTHH:mm') ===
                            (0, dayjs_1.default)(a.endDate).second(0).format('YYYY-MM-DDTHH:mm');
                    const isNotAvailable = partA || partB || partC;
                    console.log(a, na, ' a, na');
                    return isNotAvailable;
                });
                console.log(foundIndex, ' foundIndex');
                if (foundIndex !== undefined && foundIndex > -1) {
                    return false;
                }
                return true;
            });
            console.log(filteredAvailableSlotsInUserTimezone, ' filteredAvailableSlots');
            return filteredAvailableSlotsInUserTimezone;
        }
        const startDuration = dayjs_1.default.duration({
            hours: startHourByUser,
            minutes: startMinuteByUser,
        });
        const endDuration = dayjs_1.default.duration({
            hours: endHourByUser,
            minutes: endMinuteByUser,
        });
        const totalDuration = endDuration.subtract(startDuration);
        const totalMinutes = totalDuration.asMinutes();
        const availableSlotsInUserTimezone = [];
        console.log(userStartDateInHostTimezone, endTimesByHost, dayOfWeekIntByUser, endHourByHost, endMinuteByHost, hostTimezone, `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`);
        for (let i = 0; i < totalMinutes; i += slotDuration) {
            if (i > totalMinutes) {
                continue;
            }
            availableSlotsInUserTimezone.push({
                id: (0, uuid_1.v4)(),
                startDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .hour(startHourByUser)
                    .minute(startMinuteByUser)
                    .add(i, 'minute')
                    .second(0)
                    .format(),
                endDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                    .tz(userTimezone)
                    .hour(startHourByUser)
                    .minute(startMinuteByUser)
                    .add(i + slotDuration, 'minute')
                    .second(0)
                    .format(),
            });
        }
        const filteredAvailableSlotsInUserTimezone = availableSlotsInUserTimezone.filter((a) => {
            const foundIndex = notAvailableSlotsInUserTimezone?.findIndex((na) => {
                const partA = (0, dayjs_1.default)(a.endDate)
                    .tz(userTimezone)
                    .second(0)
                    .isBetween((0, dayjs_1.default)(na.startDate).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).subtract(1, 'm').second(0), 'm', '[]');
                const partB = (0, dayjs_1.default)(a.startDate)
                    .tz(userTimezone)
                    .second(0)
                    .isBetween((0, dayjs_1.default)(na.startDate).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).subtract(1, 'm').second(0), 'm', '[]');
                const partC = (0, dayjs_1.default)(na.startDate)
                    .tz(userTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') ===
                    (0, dayjs_1.default)(a.startDate)
                        .tz(userTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') &&
                    (0, dayjs_1.default)(na.endDate)
                        .tz(userTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm') ===
                        (0, dayjs_1.default)(a.endDate)
                            .tz(userTimezone)
                            .second(0)
                            .format('YYYY-MM-DDTHH:mm');
                const isNotAvailable = partA || partB || partC;
                console.log(a, na, ' a, na');
                return isNotAvailable;
            });
            console.log(foundIndex, ' foundIndex');
            if (foundIndex !== undefined && foundIndex > -1) {
                return false;
            }
            return true;
        });
        console.log(filteredAvailableSlotsInUserTimezone, ' filteredAvailableSlots');
        return filteredAvailableSlotsInUserTimezone;
    }
    // not first day of time window
    const startTimesByHost = hostPreferences.startTimes;
    const endTimesByHost = hostPreferences.endTimes;
    const dayOfWeekIntByUser = (0, date_fns_1.getISODay)((0, dayjs_1.default)(userStartDateInHostTimezone).tz(userTimezone).toDate());
    const dayOfMonthByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
        .tz(userTimezone)
        .date();
    // convert to user timezone so everything is linked to user timezone
    const endHourByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.hour ?? 20;
    const endMinuteByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.minutes ?? 0;
    let endHourByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
        .tz(hostTimezone)
        .hour(endHourByHost)
        .minute(endMinuteByHost)
        .tz(userTimezone)
        .hour();
    let endMinuteByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
        .tz(hostTimezone)
        .hour(endHourByHost)
        .minute(endMinuteByHost)
        .tz(userTimezone)
        .minute();
    // if last day change end time to hostEndDate provided
    if (isLastDay && userEndDateInHostTimezone) {
        if ((0, dayjs_1.default)(userEndDateInHostTimezone)
            .tz(userTimezone)
            .isBefore((0, dayjs_1.default)(userEndDateInHostTimezone)
            .tz(userTimezone)
            .hour(endHourByUser)
            .minute(endMinuteByUser))) {
            endHourByUser = (0, dayjs_1.default)(userEndDateInHostTimezone).tz(userTimezone).hour();
            // create slot sizes
            const flooredValue = Math.floor(60 / slotDuration);
            let minuteValueByUser = 0;
            for (let i = 0; i < flooredValue; i++) {
                const endMinutes = (i + 1) * slotDuration;
                const startMinutes = i * slotDuration;
                if ((0, dayjs_1.default)(userEndDateInHostTimezone)
                    .tz(userTimezone)
                    .isBetween((0, dayjs_1.default)(userEndDateInHostTimezone)
                    .tz(userTimezone)
                    .minute(startMinutes), (0, dayjs_1.default)(userEndDateInHostTimezone)
                    .tz(userTimezone)
                    .minute(endMinutes), 'minute', '[)')) {
                    minuteValueByUser = startMinutes;
                }
            }
            endMinuteByUser = minuteValueByUser;
        }
    }
    const startHourByHost = startTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.hour;
    const startMinuteByHost = startTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.minutes;
    const startHourByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
        .tz(hostTimezone)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .tz(userTimezone)
        .hour();
    const startMinuteByUser = (0, dayjs_1.default)(userStartDateInHostTimezone)
        .tz(hostTimezone)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .tz(userTimezone)
        .minute();
    const startDuration = dayjs_1.default.duration({
        hours: startHourByUser,
        minutes: startMinuteByUser,
    });
    const endDuration = dayjs_1.default.duration({
        hours: endHourByUser,
        minutes: endMinuteByUser,
    });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    const availableSlotsInUserTimezone = [];
    console.log(userStartDateInHostTimezone, endTimesByHost, dayOfWeekIntByUser, dayOfMonthByUser, startHourByUser, startMinuteByUser, endHourByUser, endMinuteByUser, timezone_1.default, `startDate, endTimes, dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateAvailableslots`);
    for (let i = 0; i < totalMinutes; i += slotDuration) {
        if (i > totalMinutes) {
            continue;
        }
        availableSlotsInUserTimezone.push({
            id: (0, uuid_1.v4)(),
            startDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                .tz(userTimezone)
                .hour(startHourByUser)
                .minute(startMinuteByUser)
                .add(i, 'minute')
                .second(0)
                .format(),
            endDate: (0, dayjs_1.default)(userStartDateInHostTimezone)
                .tz(userTimezone)
                .hour(startHourByUser)
                .minute(startMinuteByUser)
                .add(i + slotDuration, 'minute')
                .second(0)
                .format(),
        });
    }
    console.log(availableSlotsInUserTimezone, ' timeSlots inside generateTimeSlots not first day');
    // filter out unavailable times
    const filteredAvailableSlotsInUserTimezone = availableSlotsInUserTimezone.filter((a) => {
        const foundIndex = notAvailableSlotsInUserTimezone?.findIndex((na) => {
            const partA = (0, dayjs_1.default)(a.endDate)
                .tz(userTimezone)
                .second(0)
                .isBetween((0, dayjs_1.default)(na.startDate).tz(userTimezone).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).tz(userTimezone).subtract(1, 'm').second(0), 'm', '[]');
            const partB = (0, dayjs_1.default)(a.startDate)
                .tz(userTimezone)
                .second(0)
                .isBetween((0, dayjs_1.default)(na.startDate).tz(userTimezone).add(1, 'm').second(0), (0, dayjs_1.default)(na.endDate).tz(userTimezone).subtract(1, 'm').second(0), 'm', '[]');
            const partC = (0, dayjs_1.default)(na.startDate)
                .tz(userTimezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm') ===
                (0, dayjs_1.default)(a.startDate)
                    .tz(userTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') &&
                (0, dayjs_1.default)(na.endDate)
                    .tz(userTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') ===
                    (0, dayjs_1.default)(a.endDate)
                        .tz(userTimezone)
                        .second(0)
                        .format('YYYY-MM-DDTHH:mm');
            const isNotAvailable = partA || partB || partC;
            console.log(a, na, ' a, na');
            return isNotAvailable;
        });
        console.log(foundIndex, ' foundIndex');
        if (foundIndex !== undefined && foundIndex > -1) {
            return false;
        }
        return true;
    });
    console.log(filteredAvailableSlotsInUserTimezone, ' filteredAvailableSlots');
    return filteredAvailableSlotsInUserTimezone;
};
exports.generateAvailableSlotsForDate = generateAvailableSlotsForDate;
const cancelMeetingAssist = async (id) => {
    try {
        const operationName = 'CancelMeetingAssist';
        const query = `
            mutation CancelMeetingAssist($id: uuid!) {
                update_Meeting_Assist_by_pk(pk_columns: {id: $id}, _set: {cancelled: true}) {
                    allowAttendeeUpdatePreferences
                    anyoneCanAddSelf
                    attendeeCanModify
                    attendeeCount
                    attendeeRespondedCount
                    backgroundColor
                    bufferTime
                    calendarId
                    cancelIfAnyRefuse
                    cancelled
                    colorId
                    conferenceApp
                    createdDate
                    duration
                    enableAttendeePreferences
                    enableConference
                    enableHostPreferences
                    endDate
                    eventId
                    expireDate
                    foregroundColor
                    guaranteeAvailability
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    id
                    location
                    minThresholdCount
                    notes
                    priority
                    reminders
                    sendUpdates
                    startDate
                    summary
                    timezone
                    transparency
                    updatedAt
                    useDefaultAlarms
                    userId
                    visibility
                    windowEndDate
                    windowStartDate
                }
            }
        `;
        const variables = {
            id,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from listMeetingAssistAttendees ');
        return res?.data?.update_Meeting_Assist_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to cancel meeting assit');
    }
};
exports.cancelMeetingAssist = cancelMeetingAssist;
const deleteMeetingAssistPreferredTimesByIds = async (ids) => {
    try {
        const operationName = 'deleteMeetingAssistPreferredTimesByIds';
        const query = `
            mutation deleteMeetingAssistPreferredTimesByIds($ids: [uuid!]!) {
                delete_Meeting_Assist_Preferred_Time_Range(where: {id: {_in: $ids}}) {
                    affected_rows
                    returning {
                    attendeeId
                    createdDate
                    dayOfWeek
                    endTime
                    hostId
                    id
                    meetingId
                    startTime
                    updatedAt
                    }
                }
            }
        `;
        const variables = {
            ids,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from listMeetingAssistAttendees ');
        return res?.data?.delete_Meeting_Assist_Preferred_Time_Range?.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable to delete meeting assist preferred Times by ids');
    }
};
exports.deleteMeetingAssistPreferredTimesByIds = deleteMeetingAssistPreferredTimesByIds;
const upsertMeetingAssistPreferredTimes = async (preferredTimes) => {
    try {
        console.log(preferredTimes, ' preferredTimes inside upsertMeetingAssistPreferredTimes');
        const operationName = 'insertMeetingAssistPreferredTimes';
        const query = `
            mutation insertMeetingAssistPreferredTimes($preferredTimes: [Meeting_Assist_Preferred_Time_Range_insert_input!]!) {
                insert_Meeting_Assist_Preferred_Time_Range(objects: $preferredTimes, 
                    on_conflict: {
                    constraint: Meeting_Assist_Preferred_Time_Ranges_pkey, 
                    update_columns: [
                        attendeeId,
                        dayOfWeek,
                        endTime,
                        hostId,
                        meetingId,
                        startTime,
                        updatedAt,
                    ]
                    }) {
                    affected_rows
                    returning {
                        attendeeId
                        createdDate
                        dayOfWeek
                        endTime
                        hostId
                        id
                        meetingId
                        startTime
                        updatedAt
                    }
                }
            }
        `;
        const variables = {
            preferredTimes: preferredTimes?.map((pt) => ({
                ...pt,
                dayOfWeek: pt?.dayOfWeek === -1 ? null : pt?.dayOfWeek,
            })),
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' res from upsertMeetingAsistPreferredTimes ');
        return res?.data?.insert_Meeting_Assist_Preferred_Time_Range?.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable to upsertMeetingAssistPreferredTimes');
    }
};
exports.upsertMeetingAssistPreferredTimes = upsertMeetingAssistPreferredTimes;
// encode base64
const BtoA = (str) => Buffer.from(str).toString('base64');
exports.BtoA = BtoA;
// decode base64
const AtoB = (str) => Buffer.from(str, 'base64').toString();
exports.AtoB = AtoB;
// admin auth call
// 'Basic ' + BtoA(`admin:${authApiToken}`)
const startMeetingAssist = async (body) => {
    try {
        const res = await got_1.default.post(constants_1.meetingAssistAdminUrl, {
            headers: {
                Authorization: 'Basic ' + (0, exports.BtoA)(`admin:${constants_1.authApiToken}`),
                'Content-Type': 'application/json',
            },
            json: body,
        });
        console.log(' successfully started startMeetingAssist');
    }
    catch (e) {
        console.log(e, ' unable to start meeting assist');
    }
};
exports.startMeetingAssist = startMeetingAssist;
const getCustomAvailableTimes = (slotDuration, hostStartDate, hostPreferences, hostTimezone, userTimezone, isFirstDay, isLastDay) => {
    if (isFirstDay) {
        const endTimesByHost = hostPreferences.endTimes;
        const dayOfWeekIntByUser = (0, date_fns_1.getISODay)((0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .toDate());
        let startHourByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .hour();
        // const dayOfMonthByUser = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).date()
        // create slot sizes
        const flooredValue = Math.floor(60 / slotDuration);
        let minuteValueByUser = 0;
        for (let i = 0; i < flooredValue; i++) {
            const endMinutes = (i + 1) * slotDuration;
            const startMinutes = i * slotDuration;
            if ((0, dayjs_1.default)(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .isBetween((0, dayjs_1.default)(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .minute(startMinutes), (0, dayjs_1.default)(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .minute(endMinutes), 'minute', '[)')) {
                minuteValueByUser = endMinutes;
            }
        }
        if ((0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .isBetween((0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .minute(flooredValue * slotDuration), (0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .minute(59), 'minute', '[)')) {
            startHourByUser += 1;
            minuteValueByUser = 0;
        }
        const startMinuteByUser = minuteValueByUser;
        const endHourByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.hour ?? 20;
        const endMinuteByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByUser)?.minutes ?? 0;
        const endHourByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(endHourByHost)
            .tz(userTimezone)
            .hour();
        const endMinuteByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .minute(endMinuteByHost)
            .tz(userTimezone)
            .minute();
        // validate values before calculating
        const startTimes = hostPreferences.startTimes;
        const workStartHourByHost = startTimes?.find((i) => i.day === dayOfWeekIntByUser)?.hour || 8;
        const workStartMinuteByHost = startTimes?.find((i) => i.day === dayOfWeekIntByUser)?.minutes || 0;
        const workStartHourByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .tz(userTimezone)
            .hour();
        const workStartMinuteByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .minute(workStartMinuteByHost)
            .tz(userTimezone)
            .minute();
        if ((0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isAfter((0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(endHourByHost)
            .minute(endMinuteByHost))) {
            // return empty as outside of work time
            return null;
        }
        // change to work start time as after host start time
        if ((0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .isBefore((0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .hour(workStartHourByHost)
            .minute(workStartMinuteByHost))) {
            return {
                startTime: (0, dayjs_1.default)(hostStartDate?.slice(0, 19))
                    .tz(hostTimezone, true)
                    .tz(userTimezone)
                    .hour(workStartHourByUser)
                    .minute(workStartMinuteByUser)
                    .format('HH:mm'),
                endTime: (0, dayjs_1.default)(hostStartDate?.slice(0, 19))
                    .tz(hostTimezone, true)
                    .tz(userTimezone)
                    .hour(endHourByUser)
                    .minute(endMinuteByUser)
                    .format('HH:mm'),
                dayOfWeekInt: dayOfWeekIntByUser,
            };
        }
        return {
            startTime: (0, dayjs_1.default)(hostStartDate?.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .hour(startHourByUser)
                .minute(startMinuteByUser)
                .format('HH:mm'),
            endTime: (0, dayjs_1.default)(hostStartDate?.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .hour(endHourByUser)
                .minute(endMinuteByUser)
                .format('HH:mm'),
            dayOfWeekInt: dayOfWeekIntByUser,
        };
    }
    // not first day start from work start time schedule
    const startTimesByHost = hostPreferences.startTimes;
    const endTimesByHost = hostPreferences.endTimes;
    const dayOfWeekIntByHost = (0, date_fns_1.getISODay)((0, dayjs_1.default)(hostStartDate.slice(0, 19)).tz(hostTimezone, true).toDate());
    const dayOfWeekIntByUser = (0, date_fns_1.getISODay)((0, dayjs_1.default)(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .tz(userTimezone)
        .toDate());
    const startHourByHost = startTimesByHost?.find((i) => i.day === dayOfWeekIntByHost)?.hour;
    const startMinuteByHost = startTimesByHost?.find((i) => i.day === dayOfWeekIntByHost)?.minutes;
    const startHourByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .tz(userTimezone)
        .hour();
    const startMinuteByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(startHourByHost)
        .minute(startMinuteByHost)
        .tz(userTimezone)
        .minute();
    // convert to user timezone so everything is linked to user timezone
    const endHourByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByHost)?.hour ?? 20;
    const endMinuteByHost = endTimesByHost?.find((i) => i.day === dayOfWeekIntByHost)?.minutes ?? 0;
    // if last day change end time to hostStartDate provided
    if (isLastDay) {
        const endHourByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .hour();
        // create slot sizes
        const flooredValue = Math.floor(60 / slotDuration);
        let minuteValueByUser = 0;
        for (let i = 0; i < flooredValue; i++) {
            const endMinutes = (i + 1) * slotDuration;
            const startMinutes = i * slotDuration;
            if ((0, dayjs_1.default)(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .isBetween((0, dayjs_1.default)(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .minute(startMinutes), (0, dayjs_1.default)(hostStartDate.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .minute(endMinutes), 'minute', '[)')) {
                minuteValueByUser = startMinutes;
            }
        }
        const endMinuteByUser = minuteValueByUser;
        return {
            startTime: (0, dayjs_1.default)(hostStartDate?.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .hour(startHourByUser)
                .minute(startMinuteByUser)
                .format('HH:mm'),
            endTime: (0, dayjs_1.default)(hostStartDate?.slice(0, 19))
                .tz(hostTimezone, true)
                .tz(userTimezone)
                .hour(endHourByUser)
                .minute(endMinuteByUser)
                .format('HH:mm'),
            dayOfWeekInt: dayOfWeekIntByUser,
        };
    }
    const endHourByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(endHourByHost)
        .minute(endMinuteByHost)
        .tz(userTimezone)
        .hour();
    const endMinuteByUser = (0, dayjs_1.default)(hostStartDate.slice(0, 19))
        .tz(hostTimezone, true)
        .hour(endHourByHost)
        .minute(endMinuteByHost)
        .tz(userTimezone)
        .minute();
    return {
        startTime: (0, dayjs_1.default)(hostStartDate?.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .hour(startHourByUser)
            .minute(startMinuteByUser)
            .format('HH:mm'),
        endTime: (0, dayjs_1.default)(hostStartDate?.slice(0, 19))
            .tz(hostTimezone, true)
            .tz(userTimezone)
            .hour(endHourByUser)
            .minute(endMinuteByUser)
            .format('HH:mm'),
        dayOfWeekInt: dayOfWeekIntByUser,
    };
};
exports.getCustomAvailableTimes = getCustomAvailableTimes;
const getMeetingAssistInviteGivenId = async (id) => {
    try {
        const operationName = 'GetMeetingAssistInviteByKey';
        const query = `
            query GetMeetingAssistInviteByKey($id: uuid!) {
                Meeting_Assist_Invite_by_pk(id: $id) {
                    createdDate
                    email
                    hostId
                    hostName
                    id
                    meetingId
                    name
                    response
                    updatedAt
                    userId
                }
            }
        `;
        const variables = {
            id,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' successfully retrieved meetingassistinvites');
        return res?.data?.Meeting_Assist_Invite_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get meeting assist invite by id');
    }
};
exports.getMeetingAssistInviteGivenId = getMeetingAssistInviteGivenId;
const listMeetingAssistInvitesGivenMeetingId = async (meetingId) => {
    try {
        const operationName = 'listMeetingAssistInviteByMeetingId';
        const query = `
            query listMeetingAssistInviteByMeetingId($meetingId: uuid!) {
                Meeting_Assist_Invite(where: {meetingId: {_eq: $meetingId}}) {
                    createdDate
                    email
                    hostId
                    hostName
                    id
                    meetingId
                    name
                    response
                    updatedAt
                    userId
                }
            }
        `;
        const variables = {
            meetingId,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' successfully retrieved meetingassistinvites');
        return res?.data?.Meeting_Assist_Invite;
    }
    catch (e) {
        console.log(e, ' unable to list meeting assist invites given meeting Id');
    }
};
exports.listMeetingAssistInvitesGivenMeetingId = listMeetingAssistInvitesGivenMeetingId;
// attendeeId ==== inviteId
const updateMeetingAssistInviteResponse = async (id, response) => {
    try {
        const operationName = 'updateMeetingAssistInviteResponse';
        const query = `
            mutation updateMeetingAssistInviteResponse($id: String!, $response: String) {
                update_Meeting_Assist_Invite_by_pk(pk_columns: {id: $id}, _set: {response: $response}) {
                    createdDate
                    email
                    hostId
                    hostName
                    id
                    meetingId
                    name
                    response
                    updatedAt
                    userId
                }
            }
        `;
        const variables = {
            id,
            response,
        };
        const res = await got_1.default
            .post(constants_1.postgraphileGraphUrl, {
            headers: {
                'X-Postgraphile-Admin-Secret': constants_1.postgraphileAdminSecret,
                'Content-Type': 'application/json',
                'X-Postgraphile-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(res, ' successfully updated meetingassistinvites');
        return res?.data?.update_Meeting_Assist_Invite_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to update meeting assist invite response');
    }
};
exports.updateMeetingAssistInviteResponse = updateMeetingAssistInviteResponse;
const createRecurringMeetingAssists = async (originalMeetingAssist, originalPreferredTimes) => {
    try {
        console.log('createRecurringMeetingAssists called');
        console.log(originalPreferredTimes, ' originalPreferredTimes  inside createRecurringMeetingAssists');
        const meetingAssistAttendees = await (0, exports.listMeetingAssistAttendeesGivenMeetingId)(originalMeetingAssist?.id);
        console.log(meetingAssistAttendees, ' meetingAssistAttendees inside createRecurringMeetingAssists');
        if (!(meetingAssistAttendees && meetingAssistAttendees?.length > 0)) {
            console.log('no attendees is present');
            return;
        }
        const recurringMeetingAssists = (0, exports.generateRecurringMeetingAssists)(originalMeetingAssist);
        console.log(recurringMeetingAssists, ' recurringMeetingAssists');
        if (!(recurringMeetingAssists && recurringMeetingAssists?.length > 0)) {
            console.log('no recurringMeetingassists generated');
            return;
        }
        await (0, exports.insertMeetingAssists)(recurringMeetingAssists);
        const recurringMeetingAssistAttendeesAndRecurringPreferredTimes = (0, exports.generateAttendeesAndPreferredTimesForRecurringMeetingAssists)(meetingAssistAttendees, recurringMeetingAssists, originalPreferredTimes);
        console.log(recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringAttendees, ' recurringMeetingAssistAttendees');
        console.log(recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringPreferredTimes, ' recurringPreferredTimes');
        await (0, exports.insertMeetingAssistAttendees)(recurringMeetingAssistAttendeesAndRecurringPreferredTimes.recurringAttendees);
        if (recurringMeetingAssistAttendeesAndRecurringPreferredTimes
            ?.recurringPreferredTimes?.length > 0) {
            await (0, exports.upsertMeetingAssistPreferredTimes)(recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringPreferredTimes);
        }
    }
    catch (e) {
        console.log(e, ' unable to create recurring meeting assist');
    }
};
exports.createRecurringMeetingAssists = createRecurringMeetingAssists;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBQUEsOENBQXNCO0FBQ3RCLCtCQUFrQztBQUNsQyx1Q0FBcUM7QUFDckMsa0RBQTBCO0FBQzFCLDZDQUE2QztBQUM3QyxxRUFBNkM7QUFDN0MsdUVBQStDO0FBQy9DLCtFQUF1RDtBQUN2RCxpRkFBeUQ7QUFDekQscUVBQTZDO0FBQzdDLDJEQUFtQztBQUNuQyx1RkFBK0Q7QUFDL0Qsb0RBQXVCO0FBQ3ZCLDhDQUt3QjtBQXFCeEIsMkNBQW9DO0FBQ3BDLGlDQUE4QjtBQUU5Qix3QkFBd0I7QUFDeEIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxrQkFBUSxDQUFDLENBQUM7QUFDdkIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxtQkFBUyxDQUFDLENBQUM7QUFDeEIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxrQkFBUSxDQUFDLENBQUM7QUFDdkIsZUFBSyxDQUFDLE1BQU0sQ0FBQyxhQUFHLENBQUMsQ0FBQztBQUNsQixlQUFLLENBQUMsTUFBTSxDQUFDLDJCQUFpQixDQUFDLENBQUM7QUFDaEMsZUFBSyxDQUFDLE1BQU0sQ0FBQyx1QkFBYSxDQUFDLENBQUM7QUFDNUIsZUFBSyxDQUFDLE1BQU0sQ0FBQyx3QkFBYyxDQUFDLENBQUM7QUFFdEIsTUFBTSxZQUFZLEdBQUcsQ0FBQyxJQUE2QixFQUFFLEVBQUU7SUFDNUQsUUFBUSxJQUFJLEVBQUUsQ0FBQztRQUNiLEtBQUssT0FBTztZQUNWLE9BQU8sYUFBSyxDQUFDLEtBQUssQ0FBQztRQUNyQixLQUFLLFFBQVE7WUFDWCxPQUFPLGFBQUssQ0FBQyxNQUFNLENBQUM7UUFDdEIsS0FBSyxTQUFTO1lBQ1osT0FBTyxhQUFLLENBQUMsT0FBTyxDQUFDO1FBQ3ZCLEtBQUssUUFBUTtZQUNYLE9BQU8sYUFBSyxDQUFDLE1BQU0sQ0FBQztJQUN4QixDQUFDO0FBQ0gsQ0FBQyxDQUFD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LENBQ25DLENBQUM7UUFDRixPQUFPLENBQUMsR0FBRyxDQUNULHlEQUF5RCxFQUFFLHVCQUF1QixFQUNsRiwwQkFBMEIsQ0FDM0IsQ0FBQztRQUVGLE1BQU0sSUFBQSxvQ0FBNEIsRUFDaEMseURBQXlELENBQUMsa0JBQWtCLENBQzdFLENBQUM7UUFFRixJQUNFLHlEQUF5RDtZQUN2RCxFQUFFLHVCQUF1QixFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQ3ZDLENBQUM7WUFDRCxNQUFNLElBQUEseUNBQWlDLEVBQ3JDLHlEQUF5RCxFQUFFLHVCQUF1QixDQUNuRixDQUFDO1FBQ0osQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsNENBQTRDLENBQUMsQ0FBQztJQUMvRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBbEVXLFFBQUEsNkJBQTZCLGlDQWtFeEMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgZ290IGZyb20gJ2dvdCc7XG5pbXBvcnQgeyB2NCBhcyB1dWlkIH0gZnJvbSAndXVpZCc7XG5pbXBvcnQgeyBnZXRJU09EYXkgfSBmcm9tICdkYXRlLWZucyc7XG5pbXBvcnQgZGF5anMgZnJvbSAnZGF5anMnO1xuLy8gaW1wb3J0IGlzb1dlZWsgZnJvbSAnZGF5anMvcGx1Z2luL2lzb1dlZWsnXG5pbXBvcnQgZHVyYXRpb24gZnJvbSAnZGF5anMvcGx1Z2luL2R1cmF0aW9uJztcbmltcG9ydCBpc0JldHdlZW4gZnJvbSAnZGF5anMvcGx1Z2luL2lzQmV0d2Vlbic7XG5pbXBvcnQgaXNTYW1lT3JBZnRlciBmcm9tICdkYXlqcy9wbHVnaW4vaXNTYW1lT3JBZnRlcic7XG5pbXBvcnQgaXNTYW1lT3JCZWZvcmUgZnJvbSAnZGF5anMvcGx1Z2luL2lzU2FtZU9yQmVmb3JlJztcbmltcG9ydCB0aW1lem9uZSBmcm9tICdkYXlqcy9wbHVnaW4vdGltZXpvbmUnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcbmltcG9ydCBjdXN0b21QYXJzZUZvcm1hdCBmcm9tICdkYXlqcy9wbHVnaW4vY3VzdG9tUGFyc2VGb3JtYXQnO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCB7XG4gIGF1dGhBcGlUb2tlbixcbiAgcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gIHBvc3RncmFwaGlsZUdyYXBoVXJsLFxuICBtZWV0aW5nQXNzaXN0QWRtaW5VcmwsXG59IGZyb20gJ0BsaWIvY29uc3RhbnRzJztcbmltcG9ydCB7XG4gIEF2YWlsYWJsZVNsb3QsXG4gIEF2YWlsYWJsZVNsb3RzQnlEYXRlLFxuICBDYWxlbmRhckludGVncmF0aW9uVHlwZSxcbiAgQ3VzdG9tQXZhaWxhYmxlVGltZVR5cGUsXG4gIEV2ZW50VHlwZSxcbiAgTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSxcbiAgTWVldGluZ0Fzc2lzdENhbGVuZGFyVHlwZSxcbiAgTWVldGluZ0Fzc2lzdEV2ZW50VHlwZSxcbiAgTWVldGluZ0Fzc2lzdEludml0ZVR5cGUsXG4gIE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlLFxuICBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZSxcbiAgTWVldGluZ0Fzc2lzdFR5cGUsXG4gIE5vdEF2YWlsYWJsZVNsb3QsXG4gIFRpbWUsXG4gIFVzZXJDb250YWN0SW5mb1R5cGUsXG4gIFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG4gIFVzZXJUeXBlLFxufSBmcm9tICdAbGliL3R5cGVzJztcbmltcG9ydCB7IGdvb2dsZSB9IGZyb20gJ2dvb2dsZWFwaXMnO1xuaW1wb3J0IHsgUlJ1bGUgfSBmcm9tICdycnVsZSc7XG5cbi8vIGRheWpzLmV4dGVuZChpc29XZWVrKVxuZGF5anMuZXh0ZW5kKGR1cmF0aW9uKTtcbmRheWpzLmV4dGVuZChpc0JldHdlZW4pO1xuZGF5anMuZXh0ZW5kKHRpbWV6b25lKTtcbmRheWpzLmV4dGVuZCh1dGMpO1xuZGF5anMuZXh0ZW5kKGN1c3RvbVBhcnNlRm9ybWF0KTtcbmRheWpzLmV4dGVuZChpc1NhbWVPckFmdGVyKTtcbmRheWpzLmV4dGVuZChpc1NhbWVPckJlZm9yZSk7XG5cbmV4cG9ydCBjb25zdCBnZXRScnVsZUZyZXEgPSAoZnJlcTogUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUpID0+IHtcbiAgc3dpdGNoIChmcmVxKSB7XG4gICAgY2FzZSAnZGFpbHknOlxuICAgICAgcmV0dXJuIFJSdWxlLkRBSUxZO1xuICAgIGNhc2UgJ3dlZWtseSc6XG4gICAgICByZXR1cm4gUlJ1bGUuV0VFS0xZO1xuICAgIGNhc2UgJ21vbnRobHknOlxuICAgICAgcmV0dXJuIFJSdWxlLk1PTlRITFk7XG4gICAgY2FzZSAneWVhcmx5JzpcbiAgICAgIHJldHVybiBSUnVsZS5ZRUFSTFk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVJlY3VycmluZ01lZXRpbmdBc3Npc3RzID0gKFxuICBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q6IE1lZXRpbmdBc3Npc3RUeXBlXG4pID0+IHtcbiAgLy8gdmFsaWRhdGVcbiAgaWYgKCFvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmZyZXF1ZW5jeSkge1xuICAgIGNvbnNvbGUubG9nKCdubyBmcmVxdWVuY3kgcHJlc2VudCBpbnNpZGUgZ2VuZXJhdGVSZWN1cnJpbmdNZWV0aW5nQXNzaXN0cycpO1xuICAgIHJldHVybjtcbiAgfVxuXG4gIGlmICghb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5pbnRlcnZhbCkge1xuICAgIGNvbnNvbGUubG9nKCdubyBpbnRlcm52YWwgcHJlc2VudCBpbnNpZGUgZ2VuZXJhdGVSZWN1cnJpbmdNZWV0aW5nQXNzaXN0cycpO1xuICAgIHJldHVybjtcbiAgfVxuXG4gIGlmICghb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py51bnRpbCkge1xuICAgIGNvbnNvbGUubG9nKCdubyB1bnRpbCBwcmVzZW50IGluc2lkZSBnZW5lcmF0ZVJlY3VycmluZ01lZXRpbmdBc3Npc3RzJyk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgY29uc29sZS5sb2coJ2dlbmVyYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgY2FsbGVkJyk7XG5cbiAgY29uc3QgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdHM6IE1lZXRpbmdBc3Npc3RUeXBlW10gPSBbXTtcblxuICBjb25zdCB0aW1lV2luZG93cyA9IGdlbmVyYXRlRGF0ZXNGb3JGdXR1cmVNZWV0aW5nQXNzaXN0c1VzaW5nUnJ1bGUoXG4gICAgb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py53aW5kb3dTdGFydERhdGUsXG4gICAgb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py53aW5kb3dFbmREYXRlLFxuICAgIG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uZnJlcXVlbmN5IGFzIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlLFxuICAgIG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uaW50ZXJ2YWwsXG4gICAgb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py51bnRpbFxuICApO1xuXG4gIGNvbnNvbGUubG9nKFxuICAgIHRpbWVXaW5kb3dzLFxuICAgICcgdGltZVdpbmRvd3MgaW5zaWRlIGdlbmVyYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMnXG4gICk7XG5cbiAgZm9yIChsZXQgaSA9IDA7IGkgPCB0aW1lV2luZG93cy5sZW5ndGg7IGkrKykge1xuICAgIGlmIChpID09PSAwKSB7XG4gICAgICBjb250aW51ZTtcbiAgICB9XG5cbiAgICBjb25zdCBtZWV0aW5nSWQgPSB1dWlkKCk7XG4gICAgY29uc3QgbmV3UmVjdXJyaW5nTWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGUgPSB7XG4gICAgICBpZDogbWVldGluZ0lkLFxuICAgICAgdXNlcklkOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LnVzZXJJZCxcbiAgICAgIHN1bW1hcnk6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uc3VtbWFyeSxcbiAgICAgIG5vdGVzOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/Lm5vdGVzLFxuICAgICAgd2luZG93U3RhcnREYXRlOiB0aW1lV2luZG93c1tpXT8ud2luZG93U3RhcnREYXRlLFxuICAgICAgd2luZG93RW5kRGF0ZTogdGltZVdpbmRvd3NbaV0/LndpbmRvd0VuZERhdGUsXG4gICAgICB0aW1lem9uZTogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py50aW1lem9uZSxcbiAgICAgIGxvY2F0aW9uOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmxvY2F0aW9uLFxuICAgICAgcHJpb3JpdHk6IDEsXG4gICAgICBlbmFibGVDb25mZXJlbmNlOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmVuYWJsZUNvbmZlcmVuY2UsXG4gICAgICBjb25mZXJlbmNlQXBwOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmNvbmZlcmVuY2VBcHAsXG4gICAgICBzZW5kVXBkYXRlczogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5zZW5kVXBkYXRlcyxcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyczogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5ndWVzdHNDYW5JbnZpdGVPdGhlcnMsXG4gICAgICB0cmFuc3BhcmVuY3k6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8udHJhbnNwYXJlbmN5LFxuICAgICAgdmlzaWJpbGl0eTogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py52aXNpYmlsaXR5LFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICBjb2xvcklkOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmNvbG9ySWQsXG4gICAgICBiYWNrZ3JvdW5kQ29sb3I6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uYmFja2dyb3VuZENvbG9yLFxuICAgICAgZm9yZWdyb3VuZENvbG9yOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmZvcmVncm91bmRDb2xvcixcbiAgICAgIHVzZURlZmF1bHRBbGFybXM6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8udXNlRGVmYXVsdEFsYXJtcyxcbiAgICAgIHJlbWluZGVyczogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5yZW1pbmRlcnMsXG4gICAgICBjYW5jZWxJZkFueVJlZnVzZTogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5jYW5jZWxJZkFueVJlZnVzZSxcbiAgICAgIGVuYWJsZUhvc3RQcmVmZXJlbmNlczogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5lbmFibGVIb3N0UHJlZmVyZW5jZXMsXG4gICAgICBlbmFibGVBdHRlbmRlZVByZWZlcmVuY2VzOlxuICAgICAgICBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXMsXG4gICAgICBhdHRlbmRlZUNhbk1vZGlmeTogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5hdHRlbmRlZUNhbk1vZGlmeSxcbiAgICAgIGV4cGlyZURhdGU6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uZXhwaXJlRGF0ZSxcbiAgICAgIGNhbmNlbGxlZDogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5jYW5jZWxsZWQsXG4gICAgICBkdXJhdGlvbjogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5kdXJhdGlvbixcbiAgICAgIGNhbGVuZGFySWQ6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uY2FsZW5kYXJJZCxcbiAgICAgIGJ1ZmZlclRpbWU6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uYnVmZmVyVGltZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uYW55b25lQ2FuQWRkU2VsZixcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/Lmd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgbWluVGhyZXNob2xkQ291bnQ6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8ubWluVGhyZXNob2xkQ291bnQsXG4gICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHk6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uZ3VhcmFudGVlQXZhaWxhYmlsaXR5LFxuICAgICAgZnJlcXVlbmN5OiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmZyZXF1ZW5jeSxcbiAgICAgIGludGVydmFsOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmludGVydmFsLFxuICAgICAgdW50aWw6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8udW50aWwsXG4gICAgICBvcmlnaW5hbE1lZXRpbmdJZDogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5pZCxcbiAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnQ6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uYXR0ZW5kZWVSZXNwb25kZWRDb3VudCxcbiAgICAgIGF0dGVuZGVlQ291bnQ6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uYXR0ZW5kZWVDb3VudCxcbiAgICB9O1xuXG4gICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMucHVzaChuZXdSZWN1cnJpbmdNZWV0aW5nQXNzaXN0KTtcbiAgfVxuXG4gIHJlY3VycmluZ01lZXRpbmdBc3Npc3RzPy5mb3JFYWNoKChhKSA9PlxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYSxcbiAgICAgICcgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdCBpbnNpZGUgZ2VuZXJhdGVSZWN1cnJpbmdNZWV0aW5nQXNzaXN0cydcbiAgICApXG4gICk7XG4gIHJldHVybiByZWN1cnJpbmdNZWV0aW5nQXNzaXN0cztcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZURhdGVzRm9yRnV0dXJlTWVldGluZ0Fzc2lzdHNVc2luZ1JydWxlID0gKFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBmcmVxdWVuY3k6IFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlLFxuICBpbnRlcnZhbDogbnVtYmVyLFxuICB1bnRpbDogc3RyaW5nXG4pID0+IHtcbiAgY29uc3QgcnVsZVN0YXJ0RGF0ZSA9IG5ldyBSUnVsZSh7XG4gICAgZHRzdGFydDogZGF5anMod2luZG93U3RhcnREYXRlKS51dGMoKS50b0RhdGUoKSxcbiAgICBmcmVxOiBnZXRScnVsZUZyZXEoZnJlcXVlbmN5KSxcbiAgICBpbnRlcnZhbCxcbiAgICB1bnRpbDogZGF5anModW50aWwpLnV0YygpLnRvRGF0ZSgpLFxuICB9KTtcblxuICBjb25zb2xlLmxvZyhcbiAgICBydWxlU3RhcnREYXRlLFxuICAgICcgcnVsZVN0YXJ0RGF0ZSBpbnNpZGUgZ2VuZXJhdGVEYXRlc0ZvckZ1dHVyZU1lZXRpbmdBc3Npc3RzVXNpbmdScnVsZSdcbiAgKTtcblxuICBjb25zdCB3aW5kb3dTdGFydERhdGVzRm9yUmVjdXJyZW5jZSA9IHJ1bGVTdGFydERhdGVcbiAgICAuYWxsKClcbiAgICA/Lm1hcCgoZCkgPT4gZGF5anMudXRjKGQpLmZvcm1hdCgpKTtcblxuICB3aW5kb3dTdGFydERhdGVzRm9yUmVjdXJyZW5jZT8uZm9yRWFjaCgoZSkgPT5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHdpbmRvd0RhdGVmb3JyZWN1cnJlbmNlIGluc2lkZSBnZW5lcmF0ZURhdGVzRm9yRnV0dXJlTWVldGluZ0Fzc2lzdHNVc2luZ1JydWxlJ1xuICAgIClcbiAgKTtcblxuICBjb25zdCBydWxlRW5kRGF0ZSA9IG5ldyBSUnVsZSh7XG4gICAgZHRzdGFydDogZGF5anMod2luZG93RW5kRGF0ZSkudXRjKCkudG9EYXRlKCksXG4gICAgZnJlcTogZ2V0UnJ1bGVGcmVxKGZyZXF1ZW5jeSksXG4gICAgaW50ZXJ2YWwsXG4gICAgdW50aWw6IGRheWpzKHVudGlsKS51dGMoKS50b0RhdGUoKSxcbiAgfSk7XG5cbiAgY29uc29sZS5sb2coXG4gICAgcnVsZUVuZERhdGUsXG4gICAgJyBydWxlRW5kRGF0ZSBpbnNpZGUgZ2VuZXJhdGVEYXRlc0ZvckZ1dHVyZU1lZXRpbmdBc3Npc3RzVXNpbmdScnVsZSdcbiAgKTtcblxuICBjb25zdCB3aW5kb3dFbmREYXRlc0ZvclJlY3VycmVuY2UgPSBydWxlRW5kRGF0ZVxuICAgIC5hbGwoKVxuICAgID8ubWFwKChkKSA9PiBkYXlqcy51dGMoZCkuZm9ybWF0KCkpO1xuXG4gIHdpbmRvd0VuZERhdGVzRm9yUmVjdXJyZW5jZT8uZm9yRWFjaCgoZSkgPT5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHdpbmRvd0VuZERhdGVmb3JyZWN1cnJlbmNlIGluc2lkZSBnZW5lcmF0ZURhdGVzRm9yRnV0dXJlTWVldGluZ0Fzc2lzdHNVc2luZ1JydWxlJ1xuICAgIClcbiAgKTtcblxuICAvLyByZWZvcm1hdCBpbnRvIHdpbmRvd1N0YXJ0RGF0ZXMgYW5kIHdpbmRvd0VuZERhdGVzXG4gIGNvbnN0IHRpbWVXaW5kb3dzID0gd2luZG93U3RhcnREYXRlc0ZvclJlY3VycmVuY2VcbiAgICA/LnNsaWNlKDAsIHdpbmRvd0VuZERhdGVzRm9yUmVjdXJyZW5jZT8ubGVuZ3RoKVxuICAgID8ubWFwKCh3aW5kb3dTdGFydERhdGUsIGlueCkgPT4ge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICB3aW5kb3dFbmREYXRlOiB3aW5kb3dFbmREYXRlc0ZvclJlY3VycmVuY2U/LltpbnhdLFxuICAgICAgfTtcbiAgICB9KTtcblxuICByZXR1cm4gdGltZVdpbmRvd3M7XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0VXNlclByZWZlcmVuY2VzID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZ1xuKTogUHJvbWlzZTxVc2VyUHJlZmVyZW5jZVR5cGUgfCBudWxsPiA9PiB7XG4gIHRyeSB7XG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCd1c2VySWQgaXMgbnVsbCcpO1xuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0VXNlclByZWZlcmVuY2VzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICBxdWVyeSBnZXRVc2VyUHJlZmVyZW5jZXMoJHVzZXJJZDogdXVpZCEpIHtcbiAgICAgIFVzZXJfUHJlZmVyZW5jZSh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH19KSB7XG4gICAgICAgIHN0YXJ0VGltZXNcbiAgICAgICAgZW5kVGltZXNcbiAgICAgICAgYmFja1RvQmFja01lZXRpbmdzXG4gICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBkZWxldGVkXG4gICAgICAgIGZvbGxvd1VwXG4gICAgICAgIGlkXG4gICAgICAgIGlzUHVibGljQ2FsZW5kYXJcbiAgICAgICAgbWF4TnVtYmVyT2ZNZWV0aW5nc1xuICAgICAgICBtYXhXb3JrTG9hZFBlcmNlbnRcbiAgICAgICAgcHVibGljQ2FsZW5kYXJDYXRlZ29yaWVzXG4gICAgICAgIHJlbWluZGVyc1xuICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgdXNlcklkXG4gICAgICAgIG1pbk51bWJlck9mQnJlYWtzXG4gICAgICAgIGJyZWFrQ29sb3JcbiAgICAgICAgYnJlYWtMZW5ndGhcbiAgICAgICAgY29weUNvbG9yXG4gICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgIG9uQm9hcmRlZFxuICAgICAgfVxuICAgIH0gICAgXG4gIGA7XG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgVXNlcl9QcmVmZXJlbmNlOiBVc2VyUHJlZmVyZW5jZVR5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICByZXR1cm4gcmVzPy5kYXRhPy5Vc2VyX1ByZWZlcmVuY2U/LlswXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZ2V0VXNlclByZWZlcmVuY2VzJyk7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRVc2VyR2l2ZW5JZCA9IGFzeW5jICh1c2VySWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0VXNlckJ5SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgR2V0VXNlckJ5SWQoJGlkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIFVzZXJfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgIGVtYWlsXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJQcmVmZXJlbmNlSWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZDogdXNlcklkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBVc2VyX2J5X3BrOiBVc2VyVHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHN1Y2Nlc3NmdWxseSBnb3QgdXNlciBieSBpZCcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uVXNlcl9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCB1c2VyIGdpdmVuIGlkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBpbnNlcnRNZWV0aW5nQXNzaXN0cyA9IGFzeW5jIChcbiAgbWVldGluZ0Fzc2lzdHM6IE1lZXRpbmdBc3Npc3RUeXBlW11cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKG1lZXRpbmdBc3Npc3RzLCAnaW5zZXJ0TWVldGluZ0Fzc2lzdHMgY2FsbGVkJyk7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdJbnNlcnRNZWV0aW5nQXNzaXN0JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIEluc2VydE1lZXRpbmdBc3Npc3QoJG1lZXRpbmdBc3Npc3RzOiBbTWVldGluZ19Bc3Npc3RfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgICAgICAgICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0KG9iamVjdHM6ICRtZWV0aW5nQXNzaXN0cykge1xuICAgICAgICAgICAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgICAgIGFsbG93QXR0ZW5kZWVVcGRhdGVQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlQ2FuTW9kaWZ5XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlQ291bnRcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVSZXNwb25kZWRDb3VudFxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgYnVmZmVyVGltZVxuICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICAgIGNhbmNlbElmQW55UmVmdXNlXG4gICAgICAgICAgICAgICAgICAgIGNhbmNlbGxlZFxuICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VBcHBcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlQXR0ZW5kZWVQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICBlbmFibGVDb25mZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUhvc3RQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgZXhwaXJlRGF0ZVxuICAgICAgICAgICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgZnJlcXVlbmN5XG4gICAgICAgICAgICAgICAgICAgIGd1YXJhbnRlZUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaW50ZXJ2YWxcbiAgICAgICAgICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgICAgICAgICAgbWluVGhyZXNob2xkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxNZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgICAgICAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1bnRpbFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICB3aW5kb3dFbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgbWVldGluZ0Fzc2lzdHMsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YToge1xuICAgICAgICBpbnNlcnRfTWVldGluZ19Bc3Npc3Q6IHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzOiBudW1iZXI7XG4gICAgICAgICAgcmV0dXJuaW5nOiBNZWV0aW5nQXNzaXN0VHlwZVtdO1xuICAgICAgICB9O1xuICAgICAgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzPy5kYXRhPy5pbnNlcnRfTWVldGluZ19Bc3Npc3Q/LmFmZmVjdGVkX3Jvd3MsXG4gICAgICAnIHN1Y2Nlc3NmdWxseSBhZGRlZCByZWN1cnJpbmcgbWVldGluZyBhc3Npc3RzJ1xuICAgICk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5pbnNlcnRfTWVldGluZ19Bc3Npc3Q/LmFmZmVjdGVkX3Jvd3M7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSBpbnNlcnQgbWVldGluZyBhc3Npc3RzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cHNlcnRNZWV0aW5nQXNzaXN0Q2FsZW5kYXJzID0gYXN5bmMgKFxuICBjYWxlbmRhckxpc3Q6IE1lZXRpbmdBc3Npc3RDYWxlbmRhclR5cGVbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdVcHNlcnRNZWV0aW5nQXNzaXN0Q2FsZW5kYXJMaXN0JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIFVwc2VydE1lZXRpbmdBc3Npc3RDYWxlbmRhckxpc3QoJGNhbGVuZGFyTGlzdDogW01lZXRpbmdfQXNzaXN0X0NhbGVuZGFyX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICAgICAgICAgIGluc2VydF9NZWV0aW5nX0Fzc2lzdF9DYWxlbmRhcihvYmplY3RzOiAkY2FsZW5kYXJMaXN0LCBvbl9jb25mbGljdDoge1xuICAgICAgICAgICAgICAgICAgICBjb25zdHJhaW50OiBNZWV0aW5nX0Fzc2lzdF9DYWxlbmRhcl9wa2V5LCBcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICAgICAgICAgIGFjY2Vzc0xldmVsLFxuICAgICAgICAgICAgICAgICAgICBhY2NvdW50LFxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUlkLFxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3IsXG4gICAgICAgICAgICAgICAgICAgIGNvbG9ySWQsXG4gICAgICAgICAgICAgICAgICAgIGRlZmF1bHRSZW1pbmRlcnMsXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvcixcbiAgICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZSxcbiAgICAgICAgICAgICAgICAgICAgcHJpbWFyeSxcbiAgICAgICAgICAgICAgICAgICAgcmVzb3VyY2UsXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlLFxuICAgICAgICAgICAgICAgICAgICBdfSkge1xuICAgICAgICAgICAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgICAgICAgICBhY2Nlc3NMZXZlbFxuICAgICAgICAgICAgICAgICAgICAgICAgYWNjb3VudFxuICAgICAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVJZFxuICAgICAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgICAgICBwcmltYXJ5XG4gICAgICAgICAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgICAgICAgICAgdGl0bGVcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGNhbGVuZGFyTGlzdCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7XG4gICAgICAgIGluc2VydF9NZWV0aW5nX0Fzc2lzdF9DYWxlbmRhcjoge1xuICAgICAgICAgIGFmZmVjdGVkX3Jvd3M6IG51bWJlcjtcbiAgICAgICAgICByZXR1cm5pbmc6IE1lZXRpbmdBc3Npc3RDYWxlbmRhclR5cGVbXTtcbiAgICAgICAgfTtcbiAgICAgIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSB1cHNlcnRNZWV0aW5nQXNzaXN0Q2FsZW5kYXJzJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cHNlcnQgbWVldGluZyBhc3Npc3QgY2FsZW5kYXIgbGlzdCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBzZXJ0TWVldGluZ0Fzc2lzdEV2ZW50cyA9IGFzeW5jIChcbiAgZXZlbnRzOiBNZWV0aW5nQXNzaXN0RXZlbnRUeXBlW11cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAndXBzZXJ0TWVldGluZ0Fzc2lzdEV2ZW50cyc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiB1cHNlcnRNZWV0aW5nQXNzaXN0RXZlbnRzKCRldmVudHM6IFtNZWV0aW5nX0Fzc2lzdF9FdmVudF9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgICAgICAgICBpbnNlcnRfTWVldGluZ19Bc3Npc3RfRXZlbnQob2JqZWN0czogJGV2ZW50cywgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3RyYWludDogTWVldGluZ19Bc3Npc3RfRXZlbnRfcGtleSwgXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgICAgICAgICAgICAgICBhbGxEYXksXG4gICAgICAgICAgICAgICAgICAgICAgICBhdHRhY2htZW50cyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWQsXG4gICAgICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkLFxuICAgICAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yLFxuICAgICAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbG9ySWQsXG4gICAgICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0b3IsXG4gICAgICAgICAgICAgICAgICAgICAgICBlbmREYXRlLFxuICAgICAgICAgICAgICAgICAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkLFxuICAgICAgICAgICAgICAgICAgICAgICAgZXZlbnRUeXBlLFxuICAgICAgICAgICAgICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzLFxuICAgICAgICAgICAgICAgICAgICAgICAgZXh0ZXJuYWxVc2VyLFxuICAgICAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yLFxuICAgICAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5LFxuICAgICAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmssXG4gICAgICAgICAgICAgICAgICAgICAgICBodG1sTGluayxcbiAgICAgICAgICAgICAgICAgICAgICAgIGlDYWxVSUQsXG4gICAgICAgICAgICAgICAgICAgICAgICBsaW5rcyxcbiAgICAgICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uLFxuICAgICAgICAgICAgICAgICAgICAgICAgbG9ja2VkLFxuICAgICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkLFxuICAgICAgICAgICAgICAgICAgICAgICAgbm90ZXMsXG4gICAgICAgICAgICAgICAgICAgICAgICBvcmdhbml6ZXIsXG4gICAgICAgICAgICAgICAgICAgICAgICBwcml2YXRlQ29weSxcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2UsXG4gICAgICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlUnVsZSxcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgICAgICAgICAgICAgICAgICAgICBzb3VyY2UsXG4gICAgICAgICAgICAgICAgICAgICAgICBzdGFydERhdGUsXG4gICAgICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5LFxuICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zLFxuICAgICAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eSxcbiAgICAgICAgICAgICAgICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgICAgICAgICAgIF19KSB7XG4gICAgICAgICAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgICAgICAgICAgYWxsRGF5XG4gICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWRcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0b3JcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgICAgICAgICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbFVzZXJcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgb3JnYW5pemVyXG4gICAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBzb3VyY2VcbiAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgZXZlbnRzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IGFueSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSB1cHNlcnRNZWV0aW5nQXNzaXN0RXZlbnRzJyk7XG5cbiAgICByZXM/LmVycm9ycz8uZm9yRWFjaCgoZTogYW55KSA9PiBjb25zb2xlLmxvZyhlKSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSBvdCB1cHNlcnQgbWVldGluZyBhc3Npc3RhbnQgZXZlbnRzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnb29nbGVDYWxlbmRhclN5bmMgPSBhc3luYyAoXG4gIHRva2VuOiBzdHJpbmcsIC8vIGFjY2Vzc190b2tlbiByZXR1cm5lZCBieSBHb29nbGUgQXV0aFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBhdHRlbmRlZUlkOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBnb29nbGVDYWxlbmRhciA9IGdvb2dsZS5jYWxlbmRhcih7XG4gICAgICB2ZXJzaW9uOiAndjMnLFxuICAgICAgaGVhZGVyczoge1xuICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zdCBjYWxlbmRhckxpc3RSZXMgPSBhd2FpdCBnb29nbGVDYWxlbmRhci5jYWxlbmRhckxpc3QubGlzdCgpO1xuXG4gICAgY29uc3QgY2FsZW5kYXJMaXN0ID0gY2FsZW5kYXJMaXN0UmVzPy5kYXRhPy5pdGVtcztcblxuICAgIGlmICgoY2FsZW5kYXJMaXN0ICYmICEoY2FsZW5kYXJMaXN0Py5sZW5ndGggPiAwKSkgfHwgIWNhbGVuZGFyTGlzdCkge1xuICAgICAgY29uc29sZS5sb2coJyBubyBjYWxlbmRhcnMgZm91bmQnKTtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gY2FsZW5kYXJzIHdlcmUgZm91bmQgZnJvbSBnb29nbGUgY2FsZW5kYXInKTtcbiAgICB9XG5cbiAgICBjb25zdCBjYWxlbmRhckxpc3RNb2RpZmllZDogYW55ID0gY2FsZW5kYXJMaXN0Lm1hcCgoYykgPT4gKHtcbiAgICAgIGlkOiBjLmlkIHx8IGM/LnN1bW1hcnksXG4gICAgICBhdHRlbmRlZUlkLFxuICAgICAgdGl0bGU6IGM/LnN1bW1hcnksXG4gICAgICBiYWNrZ3JvdW5kQ29sb3I6IGM/LmJhY2tncm91bmRDb2xvcixcbiAgICAgIGFjY2Vzc0xldmVsOiBjPy5hY2Nlc3NSb2xlLFxuICAgICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgIGRlZmF1bHRSZW1pbmRlcnM6IGM/LmRlZmF1bHRSZW1pbmRlcnMsXG4gICAgICBwcmltYXJ5OiBjPy5wcmltYXJ5LFxuICAgICAgY29sb3JJZDogYz8uY29sb3JJZCxcbiAgICAgIGZvcmVncm91bmRDb2xvcjogYz8uZm9yZWdyb3VuZENvbG9yLFxuICAgIH0pKTtcblxuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFjYWxlbmRhckxpc3RNb2RpZmllZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBjYWxlbmRhckxpc3RNb2RpZmllZCcpO1xuICAgIH1cblxuICAgIGF3YWl0IHVwc2VydE1lZXRpbmdBc3Npc3RDYWxlbmRhcnMoY2FsZW5kYXJMaXN0TW9kaWZpZWQpO1xuXG4gICAgY29uc3QgdGltZU1pbiA9IGRheWpzKHdpbmRvd1N0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLmZvcm1hdCgpO1xuICAgIGNvbnN0IHRpbWVNYXggPSBkYXlqcyh3aW5kb3dFbmREYXRlLnNsaWNlKDAsIDE5KSkuZm9ybWF0KCk7XG5cbiAgICBjb25zdCBjYWxlbmRhckxpc3RBc01lZXRpbmdBc3Npc3RDYWxlbmRhciA9XG4gICAgICBjYWxlbmRhckxpc3RNb2RpZmllZCBhcyBNZWV0aW5nQXNzaXN0Q2FsZW5kYXJUeXBlW107XG5cbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGNhbGVuZGFyTGlzdEFzTWVldGluZ0Fzc2lzdENhbGVuZGFyPy5sZW5ndGg7IGkrKykge1xuICAgICAgY29uc3QgaW5pdGlhbFZhcmlhYmxlcyA9IHtcbiAgICAgICAgY2FsZW5kYXJJZDogY2FsZW5kYXJMaXN0QXNNZWV0aW5nQXNzaXN0Q2FsZW5kYXI/LltpXT8uaWQsXG4gICAgICAgIHNob3dEZWxldGVkOiBmYWxzZSxcbiAgICAgICAgc2luZ2xlRXZlbnRzOiB0cnVlLFxuICAgICAgICB0aW1lTWluLFxuICAgICAgICB0aW1lTWF4LFxuICAgICAgICB0aW1lWm9uZTogaG9zdFRpbWV6b25lLFxuICAgICAgfTtcblxuICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlQ2FsZW5kYXIuZXZlbnRzLmxpc3QoaW5pdGlhbFZhcmlhYmxlcyk7XG5cbiAgICAgIGNvbnN0IGV2ZW50cyA9IHJlcz8uZGF0YT8uaXRlbXM7XG5cbiAgICAgIGlmICghZXZlbnRzIHx8ICEoZXZlbnRzPy5sZW5ndGggPiAwKSkge1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cblxuICAgICAgLy8gZm9ybWF0IGV2ZW50cyBmb3IgaW5zZXJ0XG4gICAgICAvLyBmaWx0ZXIgZXZlbnRzIHdpdGhvdXQgaWQgb3IgdGltZXpvbmVcbiAgICAgIGNvbnN0IGZvcm1hdHRlZEV2ZW50czogYW55W10gPSBldmVudHNcbiAgICAgICAgPy5maWx0ZXIoKGUpID0+ICEhZT8uaWQpXG4gICAgICAgID8uZmlsdGVyKChlKSA9PiAhIWU/LnN0YXJ0Py50aW1lWm9uZSB8fCAhIWU/LmVuZD8udGltZVpvbmUpXG4gICAgICAgID8ubWFwKChldmVudCkgPT4ge1xuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBpZDogYCR7ZXZlbnQ/LmlkfSMke2NhbGVuZGFyTGlzdEFzTWVldGluZ0Fzc2lzdENhbGVuZGFyPy5baV0/LmlkfWAsIC8vXG4gICAgICAgICAgICBhdHRlbmRlZUlkLCAvL1xuICAgICAgICAgICAgaHRtbExpbms6IGV2ZW50Py5odG1sTGluaywgLy9cbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBldmVudD8uY3JlYXRlZCwgLy9cbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZXZlbnQ/LnVwZGF0ZWQsIC8vXG4gICAgICAgICAgICBzdW1tYXJ5OiBldmVudD8uc3VtbWFyeSwgLy9cbiAgICAgICAgICAgIG5vdGVzOiBldmVudD8uZGVzY3JpcHRpb24sIC8vXG4gICAgICAgICAgICBsb2NhdGlvbjoge1xuICAgICAgICAgICAgICB0aXRsZTogZXZlbnQ/LmxvY2F0aW9uLFxuICAgICAgICAgICAgfSwgLy9cbiAgICAgICAgICAgIGNvbG9ySWQ6IGV2ZW50Py5jb2xvcklkLCAvL1xuICAgICAgICAgICAgY3JlYXRvcjogZXZlbnQ/LmNyZWF0b3IsIC8vXG4gICAgICAgICAgICBvcmdhbml6ZXI6IGV2ZW50Py5vcmdhbml6ZXIsIC8vXG4gICAgICAgICAgICBzdGFydERhdGU6XG4gICAgICAgICAgICAgIGV2ZW50Py5zdGFydD8uZGF0ZVRpbWUgfHxcbiAgICAgICAgICAgICAgZGF5anMoZXZlbnQ/LnN0YXJ0Py5kYXRlKVxuICAgICAgICAgICAgICAgIC50eihldmVudD8uc3RhcnQ/LnRpbWVab25lIHx8IGRheWpzLnR6Lmd1ZXNzKCksIHRydWUpXG4gICAgICAgICAgICAgICAgLmZvcm1hdCgpLCAvL1xuICAgICAgICAgICAgZW5kRGF0ZTpcbiAgICAgICAgICAgICAgZXZlbnQ/LmVuZD8uZGF0ZVRpbWUgfHxcbiAgICAgICAgICAgICAgZGF5anMoZXZlbnQ/LmVuZD8uZGF0ZSlcbiAgICAgICAgICAgICAgICAudHooZXZlbnQ/LmVuZD8udGltZVpvbmUgfHwgZGF5anMudHouZ3Vlc3MoKSwgdHJ1ZSlcbiAgICAgICAgICAgICAgICAuZm9ybWF0KCksIC8vXG4gICAgICAgICAgICBhbGxEYXk6IGV2ZW50Py5zdGFydD8uZGF0ZSA/IHRydWUgOiBmYWxzZSwgLy9cbiAgICAgICAgICAgIHRpbWV6b25lOiBldmVudD8uc3RhcnQ/LnRpbWVab25lIHx8IGV2ZW50Py5lbmQ/LnRpbWVab25lLCAvL1xuICAgICAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkOiBldmVudD8uZW5kVGltZVVuc3BlY2lmaWVkLCAvL1xuICAgICAgICAgICAgcmVjdXJyZW5jZTogZXZlbnQ/LnJlY3VycmVuY2UsIC8vXG4gICAgICAgICAgICB0cmFuc3BhcmVuY3k6IGV2ZW50Py50cmFuc3BhcmVuY3ksIC8vXG4gICAgICAgICAgICB2aXNpYmlsaXR5OiBldmVudD8udmlzaWJpbGl0eSwgLy9cbiAgICAgICAgICAgIGlDYWxVSUQ6IGV2ZW50Py5pQ2FsVUlELCAvL1xuICAgICAgICAgICAgYXR0ZW5kZWVzT21pdHRlZDogZXZlbnQ/LmF0dGVuZGVlc09taXR0ZWQsIC8vXG4gICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXM6XG4gICAgICAgICAgICAgIGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXM/LnByaXZhdGUgfHxcbiAgICAgICAgICAgICAgZXZlbnQ/LmV4dGVuZGVkUHJvcGVydGllcz8uc2hhcmVkXG4gICAgICAgICAgICAgICAgPyB7XG4gICAgICAgICAgICAgICAgICAgIHByaXZhdGU6IGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXM/LnByaXZhdGUgJiYge1xuICAgICAgICAgICAgICAgICAgICAgIGtleXM6IE9iamVjdC5rZXlzKGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXM/LnByaXZhdGUpLFxuICAgICAgICAgICAgICAgICAgICAgIHZhbHVlczogT2JqZWN0LnZhbHVlcyhldmVudD8uZXh0ZW5kZWRQcm9wZXJ0aWVzPy5wcml2YXRlKSxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgICAgc2hhcmVkOiBldmVudD8uZXh0ZW5kZWRQcm9wZXJ0aWVzPy5zaGFyZWQgJiYge1xuICAgICAgICAgICAgICAgICAgICAgIGtleXM6IE9iamVjdC5rZXlzKGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXM/LnNoYXJlZCksXG4gICAgICAgICAgICAgICAgICAgICAgdmFsdWVzOiBPYmplY3QudmFsdWVzKGV2ZW50Py5leHRlbmRlZFByb3BlcnRpZXM/LnNoYXJlZCksXG4gICAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgOiBudWxsLCAvL1xuICAgICAgICAgICAgaGFuZ291dExpbms6IGV2ZW50Py5oYW5nb3V0TGluaywgLy9cbiAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGV2ZW50Py5hbnlvbmVDYW5BZGRTZWxmLFxuICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBldmVudD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5OiBldmVudD8uZ3Vlc3RzQ2FuTW9kaWZ5LCAvL1xuICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM6IGV2ZW50Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgICAgIHNvdXJjZTogZXZlbnQ/LnNvdXJjZSwgLy9cbiAgICAgICAgICAgIGF0dGFjaG1lbnRzOiBldmVudD8uYXR0YWNobWVudHMsIC8vXG4gICAgICAgICAgICBldmVudFR5cGU6IGV2ZW50Py5ldmVudFR5cGUsIC8vXG4gICAgICAgICAgICBwcml2YXRlQ29weTogZXZlbnQ/LnByaXZhdGVDb3B5LCAvL1xuICAgICAgICAgICAgbG9ja2VkOiBldmVudD8ubG9ja2VkLCAvL1xuICAgICAgICAgICAgY2FsZW5kYXJJZDogY2FsZW5kYXJMaXN0QXNNZWV0aW5nQXNzaXN0Q2FsZW5kYXI/LltpXT8uaWQsIC8vXG4gICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zOiBldmVudD8ucmVtaW5kZXJzPy51c2VEZWZhdWx0LCAvL1xuICAgICAgICAgICAgZXh0ZXJuYWxVc2VyOiB0cnVlLCAvL1xuICAgICAgICAgICAgZXZlbnRJZDogZXZlbnQ/LmlkLFxuICAgICAgICAgIH07XG4gICAgICAgIH0pO1xuXG4gICAgICBpZiAoIShmb3JtYXR0ZWRFdmVudHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuICAgICAgYXdhaXQgdXBzZXJ0TWVldGluZ0Fzc2lzdEV2ZW50cyhmb3JtYXR0ZWRFdmVudHMpO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdvb2dsZSBjYWxlbmRhciBzeW5jJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRDYWxlbmRhckludGVncmF0aW9uID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcmVzb3VyY2U6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRDYWxlbmRhckludGVncmF0aW9uJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIHF1ZXJ5IGdldENhbGVuZGFySW50ZWdyYXRpb24oJHVzZXJJZDogdXVpZCEsICRyZXNvdXJjZTogU3RyaW5nISkge1xuICAgICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbih3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIHJlc291cmNlOiB7X2VxOiAkcmVzb3VyY2V9fSkge1xuICAgICAgICAgIHRva2VuXG4gICAgICAgICAgZXhwaXJlc0F0XG4gICAgICAgICAgaWRcbiAgICAgICAgICByZWZyZXNoVG9rZW5cbiAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgIG5hbWVcbiAgICAgICAgICBjbGllbnRUeXBlXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHJlc291cmNlLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBDYWxlbmRhcl9JbnRlZ3JhdGlvbjogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGVbXSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICAuanNvbigpO1xuXG4gICAgLy8gY29uc29sZS5sb2cocmVzLCAnIHJlcyBpbnNpZGUgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbicpXG4gICAgaWYgKHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHJldHVybiByZXM/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5bMF07XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNhbGVuZGFyIGludGVncmF0aW9uJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRNZWV0aW5nQXNzaXN0ID0gYXN5bmMgKGlkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldE1lZXRpbmdBc3Npc3RCeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgcXVlcnkgR2V0TWVldGluZ0Fzc2lzdEJ5SWQoJGlkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X2J5X3BrKGlkOiAkaWQpIHtcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNvdW50XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGJ1ZmZlclRpbWVcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxJZkFueVJlZnVzZVxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxsZWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlQXBwXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgICBtaW5UaHJlc2hvbGRDb3VudFxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgICAgICAgICByZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgIHdpbmRvd0VuZERhdGVcbiAgICAgICAgICAgICAgICAgICAgd2luZG93U3RhcnREYXRlXG4gICAgICAgICAgICAgICAgICAgIGFsbG93QXR0ZW5kZWVVcGRhdGVQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICAgICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgdW50aWxcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxNZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgaW50ZXJ2YWxcbiAgICAgICAgICAgICAgICAgICAgZnJlcXVlbmN5XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgTWVldGluZ19Bc3Npc3RfYnlfcGs6IE1lZXRpbmdBc3Npc3RUeXBlIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gZ2V0TWVldGluZ0Fzc2lzdCcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgbWVldGluZyBhc3Npc3QgZnJvbSBpZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNHaXZlbk1lZXRpbmdJZCA9IGFzeW5jIChcbiAgbWVldGluZ0lkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnTGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNCeU1lZXRpbmdJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBMaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlc0J5TWVldGluZ0lkKCRtZWV0aW5nSWQ6IHV1aWQhKSB7XG4gICAgICAgICAgICAgICAgTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWUod2hlcmU6IHttZWV0aW5nSWQ6IHtfZXE6ICRtZWV0aW5nSWR9fSkge1xuICAgICAgICAgICAgICAgICAgICBjb250YWN0SWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZW1haWxzXG4gICAgICAgICAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVcbiAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGltQWRkcmVzc2VzXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIHBob25lTnVtYmVyc1xuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIG1lZXRpbmdJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7IE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10gfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBsaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlcyAnKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbGlzdCBtZWV0aW5nIGFzc2lzdCBhdHRlbmRlZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzID0gYXN5bmMgKFxuICBhdHRlbmRlZUlkOiBzdHJpbmcsXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdEVuZERhdGU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IExpc3RNZWV0aW5nQXNzaXN0RXZlbnRzRm9yQXR0ZW5kZWVHaXZlbkRhdGVzKCRhdHRlbmRlZUlkOiBTdHJpbmchLCAkc3RhcnREYXRlOiB0aW1lc3RhbXAhLCAkZW5kRGF0ZTogdGltZXN0YW1wISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0V2ZW50KHdoZXJlOiB7YXR0ZW5kZWVJZDoge19lcTogJGF0dGVuZGVlSWR9LCBzdGFydERhdGU6IHtfbHRlOiAkZW5kRGF0ZX0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWxsRGF5XG4gICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWRcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVzT21pdHRlZFxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0b3JcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBldmVudFR5cGVcbiAgICAgICAgICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICAgICAgICAgICAgICAgIGV4dGVybmFsVXNlclxuICAgICAgICAgICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rXG4gICAgICAgICAgICAgICAgICAgIGh0bWxMaW5rXG4gICAgICAgICAgICAgICAgICAgIGlDYWxVSURcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgbGlua3NcbiAgICAgICAgICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgICAgICAgICAgbG9ja2VkXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBvcmdhbml6ZXJcbiAgICAgICAgICAgICAgICAgICAgcHJpdmF0ZUNvcHlcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVxuICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlUnVsZVxuICAgICAgICAgICAgICAgICAgICByZWN1cnJpbmdFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHNvdXJjZVxuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgdHJ1ZVxuICAgICk7XG4gICAgY29uc3QgZW5kRGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdEVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIGNvbnN0IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lID0gZGF5anMoc3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpXG4gICAgICAuc2xpY2UoMCwgMTkpO1xuICAgIGNvbnN0IGVuZERhdGVJblVzZXJUaW1lem9uZSA9IGRheWpzKGVuZERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZm9ybWF0KClcbiAgICAgIC5zbGljZSgwLCAxOSk7XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9FdmVudDogTWVldGluZ0Fzc2lzdEV2ZW50VHlwZVtdIH0gfSA9XG4gICAgICBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgIGF0dGVuZGVlSWQsXG4gICAgICAgICAgICAgIHN0YXJ0RGF0ZTogc3RhcnREYXRlSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICAgICAgIGVuZERhdGU6IGVuZERhdGVJblVzZXJUaW1lem9uZSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBsaXN0TWVldGluZ0Fzc2lzdEV2ZW50c0ZvckF0dGVuZGVlR2l2ZW5EYXRlcycpO1xuICAgIHJldHVybiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0V2ZW50O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLFxuICAgICAgJyB1bmFibGUgdG8gbGlzdCBtZWV0aW5nIGFzc2lzdCBldmVudHMgZm9yIGF0dGVuZGVlIGdpdmVuIGRhdGVzJ1xuICAgICk7XG4gIH1cbn07XG5leHBvcnQgY29uc3QgdXBkYXRlTWVldGluZ0Fzc2lzdEF0dGVuZGVlID0gYXN5bmMgKFxuICBhdHRlbmRlZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdVcGRhdGVNZWV0aW5nQXNzaXN0QXR0ZW5kZWVCeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBtdXRhdGlvbiBVcGRhdGVNZWV0aW5nQXNzaXN0QXR0ZW5kZWVCeUlkKCRpZDogU3RyaW5nISR7YXR0ZW5kZWU/LmVtYWlscz8uWzBdPy52YWx1ZSA/ICcsICRlbWFpbHM6IGpzb25iJyA6ICcnfSR7YXR0ZW5kZWU/Lmhvc3RJZCA/ICcsICRob3N0SWQ6IHV1aWQhJyA6IG51bGx9JHthdHRlbmRlZT8uaW1BZGRyZXNzZXM/LlswXT8udXNlcm5hbWUgPyAnLCAkaW1BZGRyZXNzZXM6IGpzb25iJyA6ICcnfSR7YXR0ZW5kZWU/Lm1lZXRpbmdJZCA/ICcsICRtZWV0aW5nSWQ6IHV1aWQhJyA6ICcnfSR7YXR0ZW5kZWU/Lm5hbWUgPyAnLCAkbmFtZTogU3RyaW5nJyA6ICcnfSR7YXR0ZW5kZWU/LnBob25lTnVtYmVycz8uWzBdPy52YWx1ZSA/ICcsICRwaG9uZU51bWJlcnM6IGpzb25iJyA6ICcnfSR7YXR0ZW5kZWU/LnRpbWV6b25lID8gJywgJHRpbWV6b25lOiBTdHJpbmcnIDogJyd9JHthdHRlbmRlZT8udXNlcklkID8gJywgJHVzZXJJZDogdXVpZCEnIDogJyd9JHthdHRlbmRlZT8uZXh0ZXJuYWxBdHRlbmRlZSAhPT0gdW5kZWZpbmVkID8gJywgJGV4dGVybmFsQXR0ZW5kZWU6IEJvb2xlYW59JyA6ICcnfX0pIHtcbiAgICAgICAgICAgIHVwZGF0ZV9NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9ieV9wayhwa19jb2x1bW5zOiB7aWQ6ICRpZH0sIF9zZXQ6IHske2F0dGVuZGVlPy5lbWFpbHM/LlswXT8udmFsdWUgPyAnZW1haWxzOiAkZW1haWxzJyA6ICcnfSR7YXR0ZW5kZWU/LmV4dGVybmFsQXR0ZW5kZWUgPyAnLCBleHRlcm5hbEF0dGVuZGVlOiB0cnVlJyA6ICcnfSR7YXR0ZW5kZWU/Lmhvc3RJZCA/ICcsIGhvc3RJZDogJGhvc3RJZCcgOiAnJ30ke2F0dGVuZGVlPy5pbUFkZHJlc3Nlcz8uWzBdPy51c2VybmFtZSA/ICcsIGltQWRkcmVzc2VzOiAkaW1BZGRyZXNzZXMnIDogJyd9JHthdHRlbmRlZT8ubWVldGluZ0lkID8gJywgbWVldGluZ0lkOiAkbWVldGluZ0lkJyA6ICcnfSR7YXR0ZW5kZWU/Lm5hbWUgPyAnLCBuYW1lOiAkbmFtZScgOiAnJ30ke2F0dGVuZGVlPy5waG9uZU51bWJlcnM/LlswXT8udmFsdWUgPyAnLCBwaG9uZU51bWJlcnM6ICRwaG9uZU51bWJlcnMnIDogJyd9JHthdHRlbmRlZT8udGltZXpvbmUgPyAnLCB0aW1lem9uZTogJHRpbWV6b25lJyA6ICcnfSR7YXR0ZW5kZWU/LnVzZXJJZCA/ICcsIHVzZXJJZDogJHVzZXJJZCcgOiAnJ319KSB7XG4gICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICBlbWFpbHNcbiAgICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlXG4gICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICBpbUFkZHJlc3Nlc1xuICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBsZXQgdmFsdWVzOiBhbnkgPSB7XG4gICAgICBpZDogYXR0ZW5kZWU/LmlkLFxuICAgIH07XG5cbiAgICBpZiAoYXR0ZW5kZWU/Lm5hbWUpIHtcbiAgICAgIHZhbHVlcy5uYW1lID0gYXR0ZW5kZWU/Lm5hbWU7XG4gICAgfVxuXG4gICAgaWYgKGF0dGVuZGVlPy5ob3N0SWQpIHtcbiAgICAgIHZhbHVlcy5ob3N0SWQgPSBhdHRlbmRlZT8uaG9zdElkO1xuICAgIH1cblxuICAgIGlmIChhdHRlbmRlZT8udXNlcklkKSB7XG4gICAgICB2YWx1ZXMudXNlcklkID0gYXR0ZW5kZWU/LnVzZXJJZDtcbiAgICB9XG5cbiAgICBpZiAoYXR0ZW5kZWU/LmVtYWlscz8uWzBdPy52YWx1ZSkge1xuICAgICAgdmFsdWVzLmVtYWlscyA9IGF0dGVuZGVlPy5lbWFpbHM7XG4gICAgfVxuXG4gICAgaWYgKGF0dGVuZGVlPy5waG9uZU51bWJlcnM/LlswXT8udmFsdWUpIHtcbiAgICAgIHZhbHVlcy5waG9uZU51bWJlcnMgPSBhdHRlbmRlZT8ucGhvbmVOdW1iZXJzO1xuICAgIH1cblxuICAgIGlmIChhdHRlbmRlZT8uaW1BZGRyZXNzZXM/LlswXT8udXNlcm5hbWUpIHtcbiAgICAgIHZhbHVlcy5pbUFkZHJlc3NlcyA9IGF0dGVuZGVlPy5pbUFkZHJlc3NlcztcbiAgICB9XG5cbiAgICBpZiAoYXR0ZW5kZWU/Lm1lZXRpbmdJZCkge1xuICAgICAgdmFsdWVzLm1lZXRpbmdJZCA9IGF0dGVuZGVlPy5tZWV0aW5nSWQ7XG4gICAgfVxuXG4gICAgaWYgKGF0dGVuZGVlPy50aW1lem9uZSkge1xuICAgICAgdmFsdWVzLnRpbWV6b25lID0gYXR0ZW5kZWU/LnRpbWV6b25lO1xuICAgIH1cblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHZhbHVlcztcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YTogeyB1cGRhdGVfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfYnlfcGs6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBpbnNlcnRfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfb25lJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgbWVldGluZyBhdHRlbmRlZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3QgPSAoXG4gIG9yaWdpbmFsUHJlZmVycmVkVGltZXM6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10sXG4gIHJlY3VycmluZ01lZXRpbmdBc3Npc3Q6IE1lZXRpbmdBc3Npc3RUeXBlLFxuICByZWN1cnJpbmdBdHRlbmRlZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVxuKSA9PiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIG9yaWdpbmFsUHJlZmVycmVkVGltZXMsXG4gICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdCxcbiAgICAnIG9yaWdpbmFsUHJlZmVycmVkVGltZXMsIHJlY3VycmluZ01lZXRpbmdBc3Npc3QnXG4gICk7XG5cbiAgY29uc3QgcmVjdXJyaW5nUHJlZmVycmVkVGltZXM6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXTtcblxuICBmb3IgKGNvbnN0IHByZWZlcnJlZFRpbWUgb2Ygb3JpZ2luYWxQcmVmZXJyZWRUaW1lcykge1xuICAgIGNvbnN0IHJlY3VycmluZ1ByZWZlcnJlZFRpbWU6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgIG1lZXRpbmdJZDogcmVjdXJyaW5nTWVldGluZ0Fzc2lzdD8uaWQsXG4gICAgICBzdGFydFRpbWU6IHByZWZlcnJlZFRpbWU/LnN0YXJ0VGltZSxcbiAgICAgIGVuZFRpbWU6IHByZWZlcnJlZFRpbWU/LmVuZFRpbWUsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgIGhvc3RJZDogcmVjdXJyaW5nTWVldGluZ0Fzc2lzdD8udXNlcklkLFxuICAgICAgYXR0ZW5kZWVJZDogcmVjdXJyaW5nQXR0ZW5kZWU/LmlkLFxuICAgIH07XG5cbiAgICBpZiAocHJlZmVycmVkVGltZT8uZGF5T2ZXZWVrICYmIHByZWZlcnJlZFRpbWU/LmRheU9mV2VlayA+IDApIHtcbiAgICAgIHJlY3VycmluZ1ByZWZlcnJlZFRpbWUuZGF5T2ZXZWVrID0gcHJlZmVycmVkVGltZS5kYXlPZldlZWs7XG4gICAgfVxuXG4gICAgcmVjdXJyaW5nUHJlZmVycmVkVGltZXMucHVzaChyZWN1cnJpbmdQcmVmZXJyZWRUaW1lKTtcbiAgfVxuXG4gIHJldHVybiByZWN1cnJpbmdQcmVmZXJyZWRUaW1lcztcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUF0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzRm9yUmVjdXJyaW5nTWVldGluZ0Fzc2lzdCA9IChcbiAgb3JpZ2luYWxBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSxcbiAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGUsXG4gIG9yaWdpbmFsUHJlZmVycmVkVGltZXM/OiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVtdXG4pID0+IHtcbiAgY29uc29sZS5sb2coXG4gICAgb3JpZ2luYWxBdHRlbmRlZXMsXG4gICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdCxcbiAgICBvcmlnaW5hbFByZWZlcnJlZFRpbWVzLFxuICAgICcgb3JpZ2luYWxBdHRlbmRlZXMsIHJlY3VycmluZ01lZXRpbmdBc3Npc3QsIG9yaWdpbmFsUHJlZmVycmVkVGltZXMgaW5zaWRlIGdlbmVyYXRlQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXNGb3JSZWN1cnJpbmdNZWV0aW5nQXNzaXN0IGJlZm9yZSdcbiAgKTtcbiAgY29uc3QgcmVjdXJyaW5nQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10gPSBbXTtcblxuICBjb25zdCByZWN1cnJpbmdQcmVmZXJyZWRUaW1lczogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSA9IFtdO1xuXG4gIGZvciAoY29uc3Qgb3JpZ2luYWxBdHRlbmRlZSBvZiBvcmlnaW5hbEF0dGVuZGVlcykge1xuICAgIGNvbnN0IHJlY3VycmluZ0F0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlID0ge1xuICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgIG5hbWU6IG9yaWdpbmFsQXR0ZW5kZWU/Lm5hbWUsXG4gICAgICBob3N0SWQ6IG9yaWdpbmFsQXR0ZW5kZWU/Lmhvc3RJZCxcbiAgICAgIHVzZXJJZDogb3JpZ2luYWxBdHRlbmRlZT8udXNlcklkLFxuICAgICAgZW1haWxzOiBvcmlnaW5hbEF0dGVuZGVlPy5lbWFpbHMsXG4gICAgICBjb250YWN0SWQ6IG9yaWdpbmFsQXR0ZW5kZWU/LmNvbnRhY3RJZCxcbiAgICAgIHBob25lTnVtYmVyczogb3JpZ2luYWxBdHRlbmRlZT8ucGhvbmVOdW1iZXJzLFxuICAgICAgaW1BZGRyZXNzZXM6IG9yaWdpbmFsQXR0ZW5kZWU/LmltQWRkcmVzc2VzLFxuICAgICAgbWVldGluZ0lkOiByZWN1cnJpbmdNZWV0aW5nQXNzaXN0Py5pZCxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgdGltZXpvbmU6IHJlY3VycmluZ01lZXRpbmdBc3Npc3Q/LnRpbWV6b25lLFxuICAgICAgZXh0ZXJuYWxBdHRlbmRlZTogb3JpZ2luYWxBdHRlbmRlZT8uZXh0ZXJuYWxBdHRlbmRlZSxcbiAgICAgIHByaW1hcnlFbWFpbDogb3JpZ2luYWxBdHRlbmRlZT8ucHJpbWFyeUVtYWlsLFxuICAgIH07XG5cbiAgICBjb25zdCBhdHRlbmRlZUluZGV4ID0gb3JpZ2luYWxQcmVmZXJyZWRUaW1lcz8uZmluZEluZGV4KFxuICAgICAgKG8pID0+IG8/LmF0dGVuZGVlSWQgPT09IG9yaWdpbmFsQXR0ZW5kZWU/LmlkXG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYXR0ZW5kZWVJbmRleCxcbiAgICAgICcgYXR0ZW5kZWVJbmRleCBpbnNpZGUgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3QnXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIG9yaWdpbmFsUHJlZmVycmVkVGltZXMsXG4gICAgICAnIG9yaWdpbmFsUHJlZmVycmVkVGltZXMgaW5zaWRlIGdlbmVyYXRlQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXNGb3JSZWN1cnJpbmdNZWV0aW5nQXNzaXN0J1xuICAgICk7XG5cbiAgICBpZiAoXG4gICAgICBvcmlnaW5hbFByZWZlcnJlZFRpbWVzICYmXG4gICAgICBvcmlnaW5hbFByZWZlcnJlZFRpbWVzPy5sZW5ndGggPiAwICYmXG4gICAgICB0eXBlb2YgYXR0ZW5kZWVJbmRleCA9PT0gJ251bWJlcicgJiZcbiAgICAgIGF0dGVuZGVlSW5kZXggPiAtMVxuICAgICkge1xuICAgICAgY29uc3QgcmVjdXJyaW5nUHJlZmVycmVkVGltZXNGb3JBdHRlbmRlZSA9XG4gICAgICAgIGdlbmVyYXRlUHJlZmVycmVkVGltZXNGb3JSZWN1cnJpbmdNZWV0aW5nQXNzaXN0KFxuICAgICAgICAgIG9yaWdpbmFsUHJlZmVycmVkVGltZXM/LmZpbHRlcihcbiAgICAgICAgICAgIChvKSA9PiBvPy5hdHRlbmRlZUlkID09PSBvcmlnaW5hbEF0dGVuZGVlPy5pZFxuICAgICAgICAgICksXG4gICAgICAgICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdCxcbiAgICAgICAgICByZWN1cnJpbmdBdHRlbmRlZVxuICAgICAgICApO1xuXG4gICAgICByZWN1cnJpbmdQcmVmZXJyZWRUaW1lcy5wdXNoKC4uLnJlY3VycmluZ1ByZWZlcnJlZFRpbWVzRm9yQXR0ZW5kZWUpO1xuICAgIH1cblxuICAgIHJlY3VycmluZ0F0dGVuZGVlcy5wdXNoKHJlY3VycmluZ0F0dGVuZGVlKTtcbiAgfVxuXG4gIGNvbnNvbGUubG9nKFxuICAgIHJlY3VycmluZ0F0dGVuZGVlcyxcbiAgICAnIHJlY3VycmluZ0F0dGVuZGVlcyBhZnRlciBpbnNpZGUgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3QnXG4gICk7XG4gIGNvbnNvbGUubG9nKFxuICAgIHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzLFxuICAgICcgcmVjdXJyaW5nUHJlZmVycmVkVGltZXMgYWZ0ZXIgaW5zaWRlIGdlbmVyYXRlQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXNGb3JSZWN1cnJpbmdNZWV0aW5nQXNzaXN0J1xuICApO1xuXG4gIHJldHVybiB7IHJlY3VycmluZ0F0dGVuZGVlcywgcmVjdXJyaW5nUHJlZmVycmVkVGltZXMgfTtcbn07XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZUF0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzRm9yUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgPSAoXG4gIG9yaWdpbmFsQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10sXG4gIHJlY3VycmluZ01lZXRpbmdBc3Npc3RzOiBNZWV0aW5nQXNzaXN0VHlwZVtdLFxuICBvcmlnaW5hbFByZWZlcnJlZFRpbWVzPzogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXVxuKSA9PiB7XG4gIGNvbnN0IHJlY3VycmluZ0F0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdID0gW107XG4gIGNvbnN0IHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzOiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW107XG5cbiAgY29uc29sZS5sb2coXG4gICAgcmVjdXJyaW5nQXR0ZW5kZWVzLFxuICAgICcgcmVjdXJyaW5nQXR0ZW5kZWVzIGluc2lkZSBnZW5lcmF0ZUF0dGVuZGVlc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3RzIGJlZm9yZSdcbiAgKTtcblxuICBmb3IgKGNvbnN0IHJlY3VycmluZ01lZXRpbmdBc3Npc3Qgb2YgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMpIHtcbiAgICBjb25zdCBuZXdSZWN1cnJpbmdBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lcyA9XG4gICAgICBnZW5lcmF0ZUF0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzRm9yUmVjdXJyaW5nTWVldGluZ0Fzc2lzdChcbiAgICAgICAgb3JpZ2luYWxBdHRlbmRlZXMsXG4gICAgICAgIHJlY3VycmluZ01lZXRpbmdBc3Npc3QsXG4gICAgICAgIG9yaWdpbmFsUHJlZmVycmVkVGltZXNcbiAgICAgICk7XG5cbiAgICByZWN1cnJpbmdBdHRlbmRlZXMucHVzaChcbiAgICAgIC4uLm5ld1JlY3VycmluZ0F0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzPy5yZWN1cnJpbmdBdHRlbmRlZXNcbiAgICApO1xuICAgIGlmIChcbiAgICAgIG5ld1JlY3VycmluZ0F0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzPy5yZWN1cnJpbmdQcmVmZXJyZWRUaW1lcz8ubGVuZ3RoID5cbiAgICAgIDBcbiAgICApIHtcbiAgICAgIHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzLnB1c2goXG4gICAgICAgIC4uLm5ld1JlY3VycmluZ0F0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzPy5yZWN1cnJpbmdQcmVmZXJyZWRUaW1lc1xuICAgICAgKTtcbiAgICB9XG4gIH1cblxuICBjb25zb2xlLmxvZyhcbiAgICByZWN1cnJpbmdBdHRlbmRlZXMsXG4gICAgJyByZWN1cnJpbmdBdHRlbmRlZXMgaW5zaWRlIGdlbmVyYXRlQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXNGb3JSZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyBhZnRlcidcbiAgKTtcbiAgY29uc29sZS5sb2coXG4gICAgcmVjdXJyaW5nUHJlZmVycmVkVGltZXMsXG4gICAgJyByZWN1cnJpbmdQcmVmZXJyZWRUaW1lcyBpbnNpZGUgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3RzIGFmdGVyIGdlbmVyYXRpb24nXG4gICk7XG5cbiAgcmV0dXJuIHsgcmVjdXJyaW5nQXR0ZW5kZWVzLCByZWN1cnJpbmdQcmVmZXJyZWRUaW1lcyB9O1xufTtcblxuZXhwb3J0IGNvbnN0IGluc2VydE1lZXRpbmdBc3Npc3RBdHRlbmRlZXMgPSBhc3luYyAoXG4gIGF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGF0dGVuZGVlcyxcbiAgICAgICcgYXR0ZW5kZWVzIGNhbGxlZCBpbnNpZGUgaW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlcydcbiAgICApO1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlcyc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBJbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzKCRhdHRlbmRlZXM6IFtNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgICAgICAgICBpbnNlcnRfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWUob2JqZWN0czogJGF0dGVuZGVlcykge1xuICAgICAgICAgICAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnRhY3RJZFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbWFpbHNcbiAgICAgICAgICAgICAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZVxuICAgICAgICAgICAgICAgICAgICBob3N0SWRcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgcGhvbmVOdW1iZXJzXG4gICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBhdHRlbmRlZXMsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YToge1xuICAgICAgICBpbnNlcnRfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWU6IHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzOiBudW1iZXI7XG4gICAgICAgICAgcmV0dXJuaW5nOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW107XG4gICAgICAgIH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGluc2VydF9NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZScpO1xuICAgIHJldHVybiByZXM/LmRhdGE/Lmluc2VydF9NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZT8uYWZmZWN0ZWRfcm93cztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGluc2VydCBtZWV0aW5nIGFzc2lzdCBhdHRlbmRlZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydE9uZU1lZXRpbmdBc3Npc3RBdHRlbmRlZSA9IGFzeW5jIChcbiAgYXR0ZW5kZWU6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIEluc2VydE1lZXRpbmdBc3Npc3RBdHRlbmRlZSgkYXR0ZW5kZWU6IE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2luc2VydF9pbnB1dCEpIHtcbiAgICAgICAgICAgICAgICBpbnNlcnRfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfb25lKG9iamVjdDogJGF0dGVuZGVlLCBcbiAgICAgICAgICAgICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3RyYWludDogTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfcGtleSwgXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgICAgICAgICAgICAgICBjb250YWN0SWQsXG4gICAgICAgICAgICAgICAgICAgICAgICBlbWFpbHMsXG4gICAgICAgICAgICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlLFxuICAgICAgICAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXMsXG4gICAgICAgICAgICAgICAgICAgICAgICBuYW1lLFxuICAgICAgICAgICAgICAgICAgICAgICAgcGhvbmVOdW1iZXJzLFxuICAgICAgICAgICAgICAgICAgICAgICAgcHJpbWFyeUVtYWlsLFxuICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgICAgXX0pIHtcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVtYWlsc1xuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlXG4gICAgICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBpbUFkZHJlc3Nlc1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICAgICAgcHJpbWFyeUVtYWlsXG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGF0dGVuZGVlLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHsgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX29uZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGluc2VydF9NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZV9vbmUnKTtcbiAgICByZXR1cm4gcmVzPy5kYXRhPy5pbnNlcnRfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfb25lO1xuICB9IGNhdGNoIChlKSB7fVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZU1lZXRpbmdBc3Npc3RBdHRlbmRlZSA9IGFzeW5jIChpZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdEZWxldE1lZXRpbmdBc3Npc3RBdHRlbmRlZSc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBEZWxldE1lZXRpbmdBc3Npc3RBdHRlbmRlZSgkaWQ6IFN0cmluZyEpIHtcbiAgICAgICAgICAgICAgICBkZWxldGVfTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgICAgICAgICAgICAgICBjb250YWN0SWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZW1haWxzXG4gICAgICAgICAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVcbiAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGltQWRkcmVzc2VzXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIHBob25lTnVtYmVyc1xuICAgICAgICAgICAgICAgICAgICBwcmltYXJ5RW1haWxcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHsgZGVsZXRlX01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2J5X3BrOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gZGVsZXRlTWVldGluZ0Fzc2lzdEF0dGVuZGVlICcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uZGVsZXRlX01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBkZWxldGUgYXR0ZW5kZWUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldE1lZXRpbmdBc3Npc3RBdHRlbmRlZSA9IGFzeW5jIChpZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdHZXRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVCeUlkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IEdldE1lZXRpbmdBc3Npc3RBdHRlbmRlZUJ5SWQoJGlkOiBTdHJpbmchKSB7XG4gICAgICAgICAgICAgICAgTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgICAgICAgICAgICAgICBjb250YWN0SWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZW1haWxzXG4gICAgICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBpbUFkZHJlc3Nlc1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlXG4gICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHsgTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWVfYnlfcGs6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBnZXRNZWV0aW5nQXNzaXN0QXR0ZW5kZWUnKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IG1lZXRpbmcgYXNzaXN0IGF0dGVuZGVlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVCeUVtYWlsID0gYXN5bmMgKFxuICBwcmltYXJ5RW1haWw6IHN0cmluZyxcbiAgbWVldGluZ0lkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnTGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZUJ5RW1haWwnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgTGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZUJ5RW1haWwoJG1lZXRpbmdJZDogdXVpZCEsICRwcmltYXJ5RW1haWw6IFN0cmluZykge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlKHdoZXJlOiB7bWVldGluZ0lkOiB7X2VxOiAkbWVldGluZ0lkfSwgcHJpbWFyeUVtYWlsOiB7X2VxOiAkcHJpbWFyeUVtYWlsfX0sIGxpbWl0OiAxKSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnRhY3RJZFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbWFpbHNcbiAgICAgICAgICAgICAgICAgICAgZXh0ZXJuYWxBdHRlbmRlZVxuICAgICAgICAgICAgICAgICAgICBob3N0SWRcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgcGhvbmVOdW1iZXJzXG4gICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgcHJpbWFyeUVtYWlsLFxuICAgICAgbWVldGluZ0lkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHsgTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWU6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGdldE1lZXRpbmdBc3Npc3RBdHRlbmRlZScpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWU/LlswXTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBtZWV0aW5nIGFzc2lzdCBhdHRlbmRlZSBieSBlbWFpbCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlTWVldGluZ0Fzc2lzdEF0dGVuZGFuY2VDb3VudCA9IGFzeW5jIChcbiAgaWQ6IHN0cmluZyxcbiAgYXR0ZW5kZWVDb3VudDogbnVtYmVyLFxuICBhdHRlbmRlZVJlc3BvbmRlZENvdW50OiBudW1iZXJcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBkYXRlTWVldGluZ0Fzc2lzdENvdW50JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgbXV0YXRpb24gVXBkYXRlTWVldGluZ0Fzc2lzdENvdW50KCRpZDogdXVpZCEsICRhdHRlbmRlZUNvdW50OiBJbnQhLCAkYXR0ZW5kZWVSZXNwb25kZWRDb3VudDogSW50ISkge1xuICAgICAgICAgICAgdXBkYXRlX01lZXRpbmdfQXNzaXN0X2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDoge2F0dGVuZGVlQ291bnQ6ICRhdHRlbmRlZUNvdW50LCBhdHRlbmRlZVJlc3BvbmRlZENvdW50OiAkYXR0ZW5kZWVSZXNwb25kZWRDb3VudH0pIHtcbiAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICBhdHRlbmRlZUNhbk1vZGlmeVxuICAgICAgICAgICAgICBhdHRlbmRlZUNvdW50XG4gICAgICAgICAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgIGJ1ZmZlclRpbWVcbiAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICBjYW5jZWxJZkFueVJlZnVzZVxuICAgICAgICAgICAgICBjYW5jZWxsZWRcbiAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICBjb25mZXJlbmNlQXBwXG4gICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgIGVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICBtaW5UaHJlc2hvbGRDb3VudFxuICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgICByZW1pbmRlcnNcbiAgICAgICAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgIHdpbmRvd0VuZERhdGVcbiAgICAgICAgICAgICAgd2luZG93U3RhcnREYXRlXG4gICAgICAgICAgICAgIGFsbG93QXR0ZW5kZWVVcGRhdGVQcmVmZXJlbmNlc1xuICAgICAgICAgICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9ICAgICAgICAgIFxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgICBhdHRlbmRlZUNvdW50LFxuICAgICAgYXR0ZW5kZWVSZXNwb25kZWRDb3VudCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgdXBkYXRlX01lZXRpbmdfQXNzaXN0X2J5X3BrOiBNZWV0aW5nQXNzaXN0VHlwZSB9IH0gPVxuICAgICAgYXdhaXQgZ290XG4gICAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLUFkbWluLVNlY3JldCc6IHBvc3RncmFwaGlsZUFkbWluU2VjcmV0LFxuICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIHVwZGF0ZU1lZXRpbmdBc3Npc3RBdHRlbmRhbmNlQ291bnQnKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LnVwZGF0ZV9NZWV0aW5nX0Fzc2lzdF9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSBhdHRlbmRhbmNlIGNvdW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRVc2VyQ29udGFjdEluZm8gPSBhc3luYyAoaWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnR2V0VXNlckNvbnRhY3RJbmZvJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IEdldFVzZXJDb250YWN0SW5mbygkaWQ6IFN0cmluZyEpIHtcbiAgICAgICAgICAgICAgICBVc2VyX0NvbnRhY3RfSW5mb19ieV9wayhpZDogJGlkKSB7XG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgcHJpbWFyeVxuICAgICAgICAgICAgICAgICAgICB0eXBlXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgVXNlcl9Db250YWN0X0luZm9fYnlfcGs6IFVzZXJDb250YWN0SW5mb1R5cGUgfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBnZXRVc2VyQ29udGFjdEluZm8nKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LlVzZXJfQ29udGFjdF9JbmZvX2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHVzZXIgY29udGFjdCBpbmZvJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0RXZlbnRzRm9yVXNlckdpdmVuRGF0ZXMgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RFbmREYXRlOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nLFxuICBob3N0VGltZXpvbmU6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdsaXN0RXZlbnRzRm9yVXNlcic7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBsaXN0RXZlbnRzRm9yVXNlcigkdXNlcklkOiB1dWlkISwgJHN0YXJ0RGF0ZTogdGltZXN0YW1wISwgJGVuZERhdGU6IHRpbWVzdGFtcCEpIHtcbiAgICAgICAgICAgICAgICBFdmVudCh3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfSwgc3RhcnREYXRlOiB7X2x0ZTogJGVuZERhdGV9LCBkZWxldGVkOiB7X25lcTogdHJ1ZX0sIGFsbERheToge19uZXE6IHRydWV9fSkge1xuICAgICAgICAgICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRhY2htZW50c1xuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZXNPbWl0dGVkXG4gICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICAgICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgY29weUR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRvclxuICAgICAgICAgICAgICAgICAgICBkYWlseVRhc2tMaXN0XG4gICAgICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBldmVudFR5cGVcbiAgICAgICAgICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICAgICAgICAgICAgICAgIGZvbGxvd1VwRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBmb3JFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rXG4gICAgICAgICAgICAgICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGlzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIGlzRm9sbG93VXBcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgaXNQb3N0RXZlbnRcbiAgICAgICAgICAgICAgICAgICAgaXNQcmVFdmVudFxuICAgICAgICAgICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgICBsb2NrZWRcbiAgICAgICAgICAgICAgICAgICAgbWF4QXR0ZW5kZWVzXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBvcmdhbml6ZXJcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxTdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBwcmVFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgICAgICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgc2VuZFVwZGF0ZXNcbiAgICAgICAgICAgICAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgIHNvdXJjZVxuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3RhdHVzXG4gICAgICAgICAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgICAgICAgICAgdGFza0lkXG4gICAgICAgICAgICAgICAgICAgIHRhc2tUeXBlXG4gICAgICAgICAgICAgICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdW5saW5rXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgIHdlZWtseVRhc2tMaXN0XG4gICAgICAgICAgICAgICAgICAgIGJ5V2Vla0RheVxuICAgICAgICAgICAgICAgICAgICBsb2NhbFN5bmNlZFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICAgICAgICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgICAgICAgICAgICAgY29weUV4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcbiAgICAvLyBnZXQgZXZlbnRzXG4gICAgLy8gbG9jYWwgZGF0ZVxuICAgIGNvbnN0IHN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpLnR6KFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgdHJ1ZVxuICAgICk7XG4gICAgY29uc3QgZW5kRGF0ZUluSG9zdFRpbWV6b25lID0gZGF5anMoaG9zdEVuZERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIGNvbnN0IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lID0gc3RhcnREYXRlSW5Ib3N0VGltZXpvbmVcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuZm9ybWF0KClcbiAgICAgIC5zbGljZSgwLCAxOSk7XG4gICAgY29uc3QgZW5kRGF0ZUluVXNlclRpbWV6b25lID0gZW5kRGF0ZUluSG9zdFRpbWV6b25lXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpXG4gICAgICAuc2xpY2UoMCwgMTkpO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgICAgICAgZW5kRGF0ZTogZW5kRGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBsaXN0RXZlbnRzZm9yVXNlcicpO1xuICAgIHJldHVybiByZXM/LmRhdGE/LkV2ZW50O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBsaXN0RXZlbnRzRm9yVXNlcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZmluZEV2ZW50c0ZvclVzZXJHaXZlbk1lZXRpbmdJZCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGhvc3RTdGFydERhdGU6IHN0cmluZyxcbiAgaG9zdEVuZERhdGU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICBtZWV0aW5nSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdmaW5kRXZlbnRzRm9yVXNlckdpdmVuTWVldGluZ0lkJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIHF1ZXJ5IGZpbmRFdmVudHNGb3JVc2VyR2l2ZW5NZWV0aW5nSWQoJHVzZXJJZDogdXVpZCEsICRzdGFydERhdGU6IHRpbWVzdGFtcCEsICRlbmREYXRlOiB0aW1lc3RhbXAhLCAkbWVldGluZ0lkOiBTdHJpbmchKSB7XG4gICAgICAgICAgICAgICAgRXZlbnQod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCBzdGFydERhdGU6IHtfbHRlOiAkZW5kRGF0ZX0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfSwgZGVsZXRlZDoge19uZXE6IHRydWV9LCBhbGxEYXk6IHtfbmVxOiB0cnVlfSwgbWVldGluZ0lkOiB7X2VxOiAkbWVldGluZ0lkfX0sIGxpbWl0OiAxKSB7XG4gICAgICAgICAgICAgICAgICAgIGFsbERheVxuICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlSWRcbiAgICAgICAgICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICAgICAgICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgICBjb3B5VGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdG9yXG4gICAgICAgICAgICAgICAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgICAgICAgICAgICAgZm9sbG93VXBFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgIGh0bWxMaW5rXG4gICAgICAgICAgICAgICAgICAgIGlDYWxVSURcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaXNCcmVha1xuICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgaXNGb2xsb3dVcFxuICAgICAgICAgICAgICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICBpc1Bvc3RFdmVudFxuICAgICAgICAgICAgICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgICAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG1ldGhvZFxuICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICAgIHBvc3RFdmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByZUV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRUaW1lXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0YXNrSWRcbiAgICAgICAgICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgICAgICAgICAgdGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1bmxpbmtcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgICAgICAgICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGNvcHlDb2xvclxuICAgICAgICAgICAgICAgICAgICBjb3B5RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgLy8gZ2V0IGV2ZW50c1xuICAgIC8vIGxvY2FsIGRhdGVcbiAgICBjb25zdCBzdGFydERhdGVJbkhvc3RUaW1lem9uZSA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihcbiAgICAgIGhvc3RUaW1lem9uZSxcbiAgICAgIHRydWVcbiAgICApO1xuICAgIGNvbnN0IGVuZERhdGVJbkhvc3RUaW1lem9uZSA9IGRheWpzKGhvc3RFbmREYXRlLnNsaWNlKDAsIDE5KSkudHooXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICB0cnVlXG4gICAgKTtcbiAgICBjb25zdCBzdGFydERhdGVJblVzZXJUaW1lem9uZSA9IGRheWpzKHN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5mb3JtYXQoKVxuICAgICAgLnNsaWNlKDAsIDE5KTtcbiAgICBjb25zdCBlbmREYXRlSW5Vc2VyVGltZXpvbmUgPSBkYXlqcyhlbmREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmZvcm1hdCgpXG4gICAgICAuc2xpY2UoMCwgMTkpO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBzdGFydERhdGU6IHN0YXJ0RGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgICAgICAgZW5kRGF0ZTogZW5kRGF0ZUluVXNlclRpbWV6b25lLFxuICAgICAgICAgICAgbWVldGluZ0lkLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBmaW5kRXZlbnRzRm9yVXNlckdpdmVuTWVldGluZ0lkJyk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uRXZlbnQ7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBmaW5kIGV2ZW50IGZvciB1c2VyIGdpdmVuIG1lZXRpbmdJZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5NZWV0aW5nSWQgPSBhc3luYyAoXG4gIG1lZXRpbmdJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0xpc3RNZWV0aW5nQXNzaXN0UHJlZmVyZXJlZFRpbWVSYW5nZXNCeU1lZXRpbmdJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBMaXN0TWVldGluZ0Fzc2lzdFByZWZlcmVyZWRUaW1lUmFuZ2VzQnlNZWV0aW5nSWQoJG1lZXRpbmdJZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICBNZWV0aW5nX0Fzc2lzdF9QcmVmZXJyZWRfVGltZV9SYW5nZSh3aGVyZToge21lZXRpbmdJZDoge19lcTogJG1lZXRpbmdJZH19KSB7XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgIGVuZFRpbWVcbiAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBzdGFydFRpbWVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgIH1cblxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgbWVldGluZ0lkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2U6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW107XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzICcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVhbmJsZSB0byBsaXN0IG1lZXRpbmcgYXNzaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVBdmFpbGFibGVTbG90c2ZvclRpbWVXaW5kb3cgPSAoXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIHNsb3REdXJhdGlvbjogbnVtYmVyLFxuICBob3N0UHJlZmVyZW5jZXM6IFVzZXJQcmVmZXJlbmNlVHlwZSxcbiAgaG9zdFRpbWV6b25lOiBzdHJpbmcsXG4gIHVzZXJUaW1lem9uZTogc3RyaW5nLFxuICBub3RBdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lPzogTm90QXZhaWxhYmxlU2xvdFtdXG4pID0+IHtcbiAgY29uc3QgdW5pcU5vdEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUgPSBfLnVuaXFXaXRoKFxuICAgIG5vdEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUsXG4gICAgKHZhbCwgb3RoZXIpID0+XG4gICAgICBkYXlqcyh2YWwuc3RhcnREYXRlKS50eih1c2VyVGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICBkYXlqcyhvdGhlci5zdGFydERhdGUpLnR6KHVzZXJUaW1lem9uZSkuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgJiZcbiAgICAgIGRheWpzKHZhbC5lbmREYXRlKS50eih1c2VyVGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICBkYXlqcyhvdGhlci5lbmREYXRlKS50eih1c2VyVGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpXG4gICk7XG4gIGNvbnN0IGRpZmZEYXlzID0gZGF5anMod2luZG93RW5kRGF0ZSkuZGlmZihkYXlqcyh3aW5kb3dTdGFydERhdGUpLCAnZCcpO1xuXG4gIGNvbnN0IHN0YXJ0RGF0ZXNGb3JFYWNoRGF5SW5Ib3N0VGltZXpvbmU6IHN0cmluZ1tdID0gW107XG4gIGNvbnN0IGF2YWlsYWJsZVNsb3RzOiBBdmFpbGFibGVTbG90W10gPSBbXTtcbiAgY29uc3QgYXZhaWxhYmxlU2xvdHNCeURhdGU6IEF2YWlsYWJsZVNsb3RzQnlEYXRlID0ge307XG4gIGZvciAobGV0IGkgPSAwOyBpIDw9IGRpZmZEYXlzOyBpKyspIHtcbiAgICBzdGFydERhdGVzRm9yRWFjaERheUluSG9zdFRpbWV6b25lLnB1c2goXG4gICAgICBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuYWRkKGksICdkYXknKVxuICAgICAgICAuZm9ybWF0KClcbiAgICApO1xuICB9XG5cbiAgaWYgKGRpZmZEYXlzIDwgMSkge1xuICAgIGNvbnN0IGdlbmVyYXRlZFNsb3RzID0gZ2VuZXJhdGVBdmFpbGFibGVTbG90c0ZvckRhdGUoXG4gICAgICBzbG90RHVyYXRpb24sXG4gICAgICBkYXlqcyh3aW5kb3dTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLmZvcm1hdCgpLFxuICAgICAgaG9zdFByZWZlcmVuY2VzLFxuICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgdXNlclRpbWV6b25lLFxuICAgICAgbm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZSxcbiAgICAgIHRydWUsXG4gICAgICB0cnVlLFxuICAgICAgZGF5anMod2luZG93RW5kRGF0ZS5zbGljZSgwLCAxOSkpLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSkuZm9ybWF0KClcbiAgICApO1xuICAgIC8vICAwMTIzNDU2Nzg5XG4gICAgLy8gIDIwMjAtMDQtMDJUMDg6MDI6MTctMDU6MDBcbiAgICBhdmFpbGFibGVTbG90cy5wdXNoKC4uLmdlbmVyYXRlZFNsb3RzKTtcbiAgICBhdmFpbGFibGVTbG90c0J5RGF0ZVtgJHt3aW5kb3dTdGFydERhdGU/LnNsaWNlKDAsIDEwKX1gXSA9IGdlbmVyYXRlZFNsb3RzO1xuICB9IGVsc2Uge1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgc3RhcnREYXRlc0ZvckVhY2hEYXlJbkhvc3RUaW1lem9uZS5sZW5ndGg7IGkrKykge1xuICAgICAgY29uc3QgZmlsdGVyZWROb3RBdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lID1cbiAgICAgICAgdW5pcU5vdEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmU/LmZpbHRlcihcbiAgICAgICAgICAobmEpID0+XG4gICAgICAgICAgICBkYXlqcyhuYT8uc3RhcnREYXRlKS50eih1c2VyVGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpID09PVxuICAgICAgICAgICAgZGF5anMoc3RhcnREYXRlc0ZvckVhY2hEYXlJbkhvc3RUaW1lem9uZT8uW2ldKVxuICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREJylcbiAgICAgICAgKTtcblxuICAgICAgaWYgKGkgPT09IDApIHtcbiAgICAgICAgY29uc3QgZ2VuZXJhdGVkU2xvdHMgPSBnZW5lcmF0ZUF2YWlsYWJsZVNsb3RzRm9yRGF0ZShcbiAgICAgICAgICBzbG90RHVyYXRpb24sXG4gICAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXlJbkhvc3RUaW1lem9uZT8uW2ldLFxuICAgICAgICAgIGhvc3RQcmVmZXJlbmNlcyxcbiAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgdXNlclRpbWV6b25lLFxuICAgICAgICAgIGZpbHRlcmVkTm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZSxcbiAgICAgICAgICB0cnVlLFxuICAgICAgICAgIGZhbHNlLFxuICAgICAgICAgIGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLmZvcm1hdCgpXG4gICAgICAgICk7XG4gICAgICAgIC8vICAwMTIzNDU2Nzg5XG4gICAgICAgIC8vICAyMDIwLTA0LTAyVDA4OjAyOjE3LTA1OjAwXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzLnB1c2goLi4uZ2VuZXJhdGVkU2xvdHMpO1xuICAgICAgICBhdmFpbGFibGVTbG90c0J5RGF0ZVtcbiAgICAgICAgICBgJHtzdGFydERhdGVzRm9yRWFjaERheUluSG9zdFRpbWV6b25lPy5baV0/LnNsaWNlKDAsIDEwKX1gXG4gICAgICAgIF0gPSBnZW5lcmF0ZWRTbG90cztcbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG5cbiAgICAgIGlmIChpID09PSBzdGFydERhdGVzRm9yRWFjaERheUluSG9zdFRpbWV6b25lLmxlbmd0aCAtIDEpIHtcbiAgICAgICAgY29uc3QgZ2VuZXJhdGVkU2xvdHMgPSBnZW5lcmF0ZUF2YWlsYWJsZVNsb3RzRm9yRGF0ZShcbiAgICAgICAgICBzbG90RHVyYXRpb24sXG4gICAgICAgICAgc3RhcnREYXRlc0ZvckVhY2hEYXlJbkhvc3RUaW1lem9uZT8uW2ldLFxuICAgICAgICAgIGhvc3RQcmVmZXJlbmNlcyxcbiAgICAgICAgICBob3N0VGltZXpvbmUsXG4gICAgICAgICAgdXNlclRpbWV6b25lLFxuICAgICAgICAgIGZpbHRlcmVkTm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZSxcbiAgICAgICAgICBmYWxzZSxcbiAgICAgICAgICB0cnVlLFxuICAgICAgICAgIGRheWpzKHdpbmRvd0VuZERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLmZvcm1hdCgpXG4gICAgICAgICk7XG5cbiAgICAgICAgYXZhaWxhYmxlU2xvdHMucHVzaCguLi5nZW5lcmF0ZWRTbG90cyk7XG4gICAgICAgIGF2YWlsYWJsZVNsb3RzQnlEYXRlW1xuICAgICAgICAgIGAke3N0YXJ0RGF0ZXNGb3JFYWNoRGF5SW5Ib3N0VGltZXpvbmU/LltpXT8uc2xpY2UoMCwgMTApfWBcbiAgICAgICAgXSA9IGdlbmVyYXRlZFNsb3RzO1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cblxuICAgICAgY29uc3QgZ2VuZXJhdGVkU2xvdHMgPSBnZW5lcmF0ZUF2YWlsYWJsZVNsb3RzRm9yRGF0ZShcbiAgICAgICAgc2xvdER1cmF0aW9uLFxuICAgICAgICBzdGFydERhdGVzRm9yRWFjaERheUluSG9zdFRpbWV6b25lPy5baV0sXG4gICAgICAgIGhvc3RQcmVmZXJlbmNlcyxcbiAgICAgICAgaG9zdFRpbWV6b25lLFxuICAgICAgICB1c2VyVGltZXpvbmUsXG4gICAgICAgIGZpbHRlcmVkTm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZVxuICAgICAgKTtcblxuICAgICAgYXZhaWxhYmxlU2xvdHMucHVzaCguLi5nZW5lcmF0ZWRTbG90cyk7XG4gICAgICBhdmFpbGFibGVTbG90c0J5RGF0ZVtcbiAgICAgICAgYCR7c3RhcnREYXRlc0ZvckVhY2hEYXlJbkhvc3RUaW1lem9uZT8uW2ldPy5zbGljZSgwLCAxMCl9YFxuICAgICAgXSA9IGdlbmVyYXRlZFNsb3RzO1xuICAgIH1cbiAgfVxuICBjb25zb2xlLmxvZyhhdmFpbGFibGVTbG90c0J5RGF0ZSwgJyBhdmFpbGFibGVTbG90c0J5RGF0ZSBpbnNpZGUgZnVuY3Rpb24nKTtcbiAgcmV0dXJuIHsgYXZhaWxhYmxlU2xvdHMsIGF2YWlsYWJsZVNsb3RzQnlEYXRlIH07XG59O1xuXG4vKipcbiAqIEBwYXJhbXMgbm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZSAtIGV2ZW50cyB3aXRoIHRyYW5zcGFyZW5jeTogJ29wYXF1ZScgYXMgbm90IGF2YWlsYWJsZVxuICovXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVBdmFpbGFibGVTbG90c0ZvckRhdGUgPSAoXG4gIHNsb3REdXJhdGlvbjogbnVtYmVyLFxuICB1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmU6IHN0cmluZyxcbiAgaG9zdFByZWZlcmVuY2VzOiBVc2VyUHJlZmVyZW5jZVR5cGUsXG4gIGhvc3RUaW1lem9uZTogc3RyaW5nLFxuICB1c2VyVGltZXpvbmU6IHN0cmluZyxcbiAgbm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZT86IE5vdEF2YWlsYWJsZVNsb3RbXSxcbiAgaXNGaXJzdERheT86IGJvb2xlYW4sXG4gIGlzTGFzdERheT86IGJvb2xlYW4sXG4gIHVzZXJFbmREYXRlSW5Ib3N0VGltZXpvbmU/OiBzdHJpbmdcbikgPT4ge1xuICBpZiAoaXNGaXJzdERheSAmJiBpc0xhc3REYXkgJiYgdXNlckVuZERhdGVJbkhvc3RUaW1lem9uZSkge1xuICAgIGNvbnN0IGVuZFRpbWVzQnlIb3N0ID0gaG9zdFByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludEJ5VXNlciA9IGdldElTT0RheShcbiAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSkudHoodXNlclRpbWV6b25lKS50b0RhdGUoKVxuICAgICk7XG5cbiAgICBjb25zdCBkYXlPZk1vbnRoQnlVc2VyID0gZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5kYXRlKCk7XG4gICAgbGV0IHN0YXJ0SG91ckJ5VXNlciA9IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuXG4gICAgY29uc3QgZmxvb3JlZFZhbHVlID0gTWF0aC5mbG9vcig2MCAvIHNsb3REdXJhdGlvbik7XG5cbiAgICBsZXQgbWludXRlVmFsdWVCeVVzZXIgPSAwO1xuICAgIGlmIChkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpLnR6KHVzZXJUaW1lem9uZSkubWludXRlKCkgIT09IDApIHtcbiAgICAgIGZvciAobGV0IGkgPSAwOyBpIDwgZmxvb3JlZFZhbHVlOyBpKyspIHtcbiAgICAgICAgY29uc3QgZW5kTWludXRlcyA9IChpICsgMSkgKiBzbG90RHVyYXRpb247XG4gICAgICAgIGNvbnN0IHN0YXJ0TWludXRlcyA9IGkgKiBzbG90RHVyYXRpb247XG4gICAgICAgIGlmIChcbiAgICAgICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZXMpLFxuICAgICAgICAgICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZXMpLFxuICAgICAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAgICAgJ1spJ1xuICAgICAgICAgICAgKVxuICAgICAgICApIHtcbiAgICAgICAgICBtaW51dGVWYWx1ZUJ5VXNlciA9IGVuZE1pbnV0ZXM7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5taW51dGUoZmxvb3JlZFZhbHVlICogc2xvdER1cmF0aW9uKSxcbiAgICAgICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpLnR6KHVzZXJUaW1lem9uZSkubWludXRlKDU5KSxcbiAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAnWyknXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIHN0YXJ0SG91ckJ5VXNlciArPSAxO1xuICAgICAgbWludXRlVmFsdWVCeVVzZXIgPSAwO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0TWludXRlQnlVc2VyID0gbWludXRlVmFsdWVCeVVzZXI7XG5cbiAgICBjb25zdCBlbmRIb3VyQnlIb3N0ID1cbiAgICAgIGVuZFRpbWVzQnlIb3N0Py5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QnlVc2VyKT8uaG91ciA/PyAyMDtcbiAgICBjb25zdCBlbmRNaW51dGVCeUhvc3QgPVxuICAgICAgZW5kVGltZXNCeUhvc3Q/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRCeVVzZXIpPy5taW51dGVzID8/IDA7XG4gICAgY29uc3QgZW5kSG91ckJ5VXNlciA9IGRheWpzKHVzZXJFbmREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIoZW5kSG91ckJ5SG9zdClcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IGVuZE1pbnV0ZUJ5VXNlciA9IGRheWpzKHVzZXJFbmREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLm1pbnV0ZShlbmRNaW51dGVCeUhvc3QpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLm1pbnV0ZSgpO1xuXG4gICAgLy8gdmFsaWRhdGUgdmFsdWVzIGJlZm9yZSBjYWxjdWxhdGluZ1xuICAgIGNvbnN0IHN0YXJ0VGltZXMgPSBob3N0UHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyQnlIb3N0ID1cbiAgICAgIHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRCeVVzZXIpPy5ob3VyIHx8IDg7XG4gICAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlIb3N0ID1cbiAgICAgIHN0YXJ0VGltZXM/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRCeVVzZXIpPy5taW51dGVzIHx8IDA7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5VXNlciA9IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3Qgd29ya1N0YXJ0TWludXRlQnlVc2VyID0gZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5taW51dGUoKTtcblxuICAgIGlmIChcbiAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgLmlzQWZ0ZXIoXG4gICAgICAgICAgZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgLy8gcmV0dXJuIGVtcHR5IGFzIG91dHNpZGUgb2Ygd29yayB0aW1lXG4gICAgICByZXR1cm4gW107XG4gICAgfVxuXG4gICAgLy8gY2hhbmdlIHRvIHdvcmsgc3RhcnQgdGltZSBhcyBhZnRlciBob3N0IHN0YXJ0IHRpbWVcbiAgICBpZiAoXG4gICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgICAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya1N0YXJ0SG91ckJ5VXNlcixcbiAgICAgICAgbWludXRlczogd29ya1N0YXJ0TWludXRlQnlVc2VyLFxuICAgICAgfSk7XG4gICAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IGVuZEhvdXJCeVVzZXIsXG4gICAgICAgIG1pbnV0ZXM6IGVuZE1pbnV0ZUJ5VXNlcixcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICAgICAgY29uc3QgYXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFtdID0gW107XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lLFxuICAgICAgICBlbmRUaW1lc0J5SG9zdCxcbiAgICAgICAgZGF5T2ZXZWVrSW50QnlVc2VyLFxuICAgICAgICBkYXlPZk1vbnRoQnlVc2VyLFxuICAgICAgICBzdGFydEhvdXJCeVVzZXIsXG4gICAgICAgIHN0YXJ0TWludXRlQnlVc2VyLFxuICAgICAgICBlbmRIb3VyQnlVc2VyLFxuICAgICAgICBlbmRNaW51dGVCeVVzZXIsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50QnlVc2VyLCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICAgICk7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSBzbG90RHVyYXRpb24pIHtcbiAgICAgICAgaWYgKGkgPiB0b3RhbE1pbnV0ZXMpIHtcbiAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgfVxuXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUucHVzaCh7XG4gICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICBzdGFydERhdGU6IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXJCeVVzZXIpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlVc2VyKVxuICAgICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgICBlbmREYXRlOiBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlVc2VyKVxuICAgICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5VXNlcilcbiAgICAgICAgICAgIC5hZGQoaSArIHNsb3REdXJhdGlvbiwgJ21pbnV0ZScpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICcgdGltZVNsb3RzIGluc2lkZSBnZW5lcmF0ZVRpbWVTbG90cyBmb3IgZmlyc3QgZGF5IHdoZXJlIHN0YXJ0RGF0ZSBpcyBiZWZvcmUgd29yayBzdGFydCB0aW1lJ1xuICAgICAgKTtcblxuICAgICAgLy8gZmlsdGVyIG91dCB1bmF2YWlsYWJsZSB0aW1lc1xuICAgICAgY29uc3QgZmlsdGVyZWRBdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lID1cbiAgICAgICAgYXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZS5maWx0ZXIoKGEpID0+IHtcbiAgICAgICAgICBjb25zdCBmb3VuZEluZGV4ID0gbm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZT8uZmluZEluZGV4KFxuICAgICAgICAgICAgKG5hKSA9PiB7XG4gICAgICAgICAgICAgIGNvbnN0IHBhcnRBID0gZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHVzZXJUaW1lem9uZSkuYWRkKDEsICdtJykuc2Vjb25kKDApLFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodXNlclRpbWV6b25lKS5zdWJ0cmFjdCgxLCAnbScpLnNlY29uZCgwKSxcbiAgICAgICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICAgICApO1xuXG4gICAgICAgICAgICAgIGNvbnN0IHBhcnRCID0gZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodXNlclRpbWV6b25lKS5hZGQoMSwgJ20nKS5zZWNvbmQoMCksXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eih1c2VyVGltZXpvbmUpLnN1YnRyYWN0KDEsICdtJykuc2Vjb25kKDApLFxuICAgICAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgICAgY29uc3QgcGFydEMgPVxuICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgICAgICBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgJiZcbiAgICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKVxuICAgICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJyk7XG5cbiAgICAgICAgICAgICAgY29uc3QgaXNOb3RBdmFpbGFibGUgPSBwYXJ0QSB8fCBwYXJ0QiB8fCBwYXJ0QztcblxuICAgICAgICAgICAgICBjb25zb2xlLmxvZyhhLCBuYSwgJyBhLCBuYScpO1xuICAgICAgICAgICAgICByZXR1cm4gaXNOb3RBdmFpbGFibGU7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnNvbGUubG9nKGZvdW5kSW5kZXgsICcgZm91bmRJbmRleCcpO1xuXG4gICAgICAgICAgaWYgKGZvdW5kSW5kZXggIT09IHVuZGVmaW5lZCAmJiBmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICByZXR1cm4gdHJ1ZTtcbiAgICAgICAgfSk7XG5cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUsXG4gICAgICAgICcgZmlsdGVyZWRBdmFpbGFibGVTbG90cydcbiAgICAgICk7XG5cbiAgICAgIHJldHVybiBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmU7XG4gICAgfVxuXG4gICAgY29uc3Qgc3RhcnREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiBzdGFydEhvdXJCeVVzZXIsXG4gICAgICBtaW51dGVzOiBzdGFydE1pbnV0ZUJ5VXNlcixcbiAgICB9KTtcbiAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgIGhvdXJzOiBlbmRIb3VyQnlVc2VyLFxuICAgICAgbWludXRlczogZW5kTWludXRlQnlVc2VyLFxuICAgIH0pO1xuICAgIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgICBjb25zdCB0b3RhbE1pbnV0ZXMgPSB0b3RhbER1cmF0aW9uLmFzTWludXRlcygpO1xuICAgIGNvbnNvbGUubG9nKHRvdGFsTWludXRlcywgJyB0b3RhbE1pbnV0ZXMgaW5zaWRlIGZpcnN0IGFuZCBsYXN0IHNhbWUgZGF5Jyk7XG4gICAgY29uc3QgYXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFtdID0gW107XG4gICAgY29uc29sZS5sb2coXG4gICAgICB1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUsXG4gICAgICBlbmRUaW1lc0J5SG9zdCxcbiAgICAgIGRheU9mV2Vla0ludEJ5VXNlcixcbiAgICAgIGVuZEhvdXJCeUhvc3QsXG4gICAgICBlbmRNaW51dGVCeUhvc3QsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0ICYgbGFzdCBEYXkgaW5zaWRlIGdlbmVyYXRlVGltZXNsb3RzYFxuICAgICk7XG4gICAgZm9yIChsZXQgaSA9IDA7IGkgPCB0b3RhbE1pbnV0ZXM7IGkgKz0gc2xvdER1cmF0aW9uKSB7XG4gICAgICBpZiAoaSA+IHRvdGFsTWludXRlcykge1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH1cbiAgICAgIGF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUucHVzaCh7XG4gICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgIHN0YXJ0RGF0ZTogZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlVc2VyKVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeVVzZXIpXG4gICAgICAgICAgLmFkZChpLCAnbWludXRlJylcbiAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICBlbmREYXRlOiBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAuaG91cihzdGFydEhvdXJCeVVzZXIpXG4gICAgICAgICAgLm1pbnV0ZShzdGFydE1pbnV0ZUJ5VXNlcilcbiAgICAgICAgICAuYWRkKGkgKyBzbG90RHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAuZm9ybWF0KCksXG4gICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUsXG4gICAgICAnIGF2YWlsYWJsZVNsb3RzIGluc2lkZSBmaXJzdCAmIGxhc3Qgc2FtZSBkYXknXG4gICAgKTtcbiAgICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUgPVxuICAgICAgYXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZS5maWx0ZXIoKGEpID0+IHtcbiAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmU/LmZpbmRJbmRleCgobmEpID0+IHtcbiAgICAgICAgICBjb25zdCBwYXJ0QSA9IGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHVzZXJUaW1lem9uZSkuYWRkKDEsICdtJykuc2Vjb25kKDApLFxuICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS50eih1c2VyVGltZXpvbmUpLnN1YnRyYWN0KDEsICdtJykuc2Vjb25kKDApLFxuICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICBjb25zdCBwYXJ0QiA9IGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkudHoodXNlclRpbWV6b25lKS5hZGQoMSwgJ20nKS5zZWNvbmQoMCksXG4gICAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHVzZXJUaW1lem9uZSkuc3VidHJhY3QoMSwgJ20nKS5zZWNvbmQoMCksXG4gICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnN0IHBhcnRDID1cbiAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgIGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSAmJlxuICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJyk7XG5cbiAgICAgICAgICBjb25zdCBpc05vdEF2YWlsYWJsZSA9IHBhcnRBIHx8IHBhcnRCIHx8IHBhcnRDO1xuXG4gICAgICAgICAgY29uc29sZS5sb2coYSwgbmEsICcgYSwgbmEnKTtcblxuICAgICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgICAgfSk7XG5cbiAgICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgICAgaWYgKGZvdW5kSW5kZXggIT09IHVuZGVmaW5lZCAmJiBmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gdHJ1ZTtcbiAgICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUsXG4gICAgICAnIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHMnXG4gICAgKTtcbiAgICByZXR1cm4gZmlsdGVyZWRBdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lO1xuICB9XG5cbiAgaWYgKGlzRmlyc3REYXkpIHtcbiAgICAvLyBmaXJzdGRheSBjYW4gYmUgc3RhcnRlZCBvdXRzaWRlIG9mIHdvcmsgdGltZVxuICAgIC8vIGlmIGZpcnN0RGF5IHN0YXJ0IGlzIGFmdGVyIGVuZCB0aW1lIC0tIHJldHVybiBbXVxuICAgIGNvbnN0IGVuZFRpbWVzQnlIb3N0ID0gaG9zdFByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludEJ5VXNlciA9IGdldElTT0RheShcbiAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSkudHoodXNlclRpbWV6b25lKS50b0RhdGUoKVxuICAgICk7XG5cbiAgICAvLyBtb250aCBpcyB6ZXJvLWluZGV4ZWRcbiAgICAvLyBjb25zdCBtb250aCA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnR6KHVzZXJUaW1lem9uZSkubW9udGgoKVxuICAgIGNvbnN0IGRheU9mTW9udGhCeVVzZXIgPSBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmRhdGUoKTtcbiAgICBsZXQgc3RhcnRIb3VyQnlVc2VyID0gZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgLy8gY3JlYXRlIHNsb3Qgc2l6ZXNcbiAgICBjb25zdCBmbG9vcmVkVmFsdWUgPSBNYXRoLmZsb29yKDYwIC8gc2xvdER1cmF0aW9uKTtcblxuICAgIGxldCBtaW51dGVWYWx1ZUJ5VXNlciA9IDA7XG4gICAgaWYgKGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSkudHoodXNlclRpbWV6b25lKS5taW51dGUoKSAhPT0gMCkge1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBmbG9vcmVkVmFsdWU7IGkrKykge1xuICAgICAgICBjb25zdCBlbmRNaW51dGVzID0gKGkgKyAxKSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgY29uc3Qgc3RhcnRNaW51dGVzID0gaSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlcyksXG4gICAgICAgICAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlcyksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgICkge1xuICAgICAgICAgIG1pbnV0ZVZhbHVlQnlVc2VyID0gZW5kTWludXRlcztcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChcbiAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLm1pbnV0ZShmbG9vcmVkVmFsdWUgKiBzbG90RHVyYXRpb24pLFxuICAgICAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSkudHoodXNlclRpbWV6b25lKS5taW51dGUoNTkpLFxuICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICdbKSdcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgc3RhcnRIb3VyQnlVc2VyICs9IDE7XG4gICAgICBtaW51dGVWYWx1ZUJ5VXNlciA9IDA7XG4gICAgfVxuXG4gICAgY29uc3Qgc3RhcnRNaW51dGVCeVVzZXIgPSBtaW51dGVWYWx1ZUJ5VXNlcjtcblxuICAgIC8vIGNvbnZlcnQgdG8gdXNlciB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byB1c2VyIHRpbWV6b25lXG5cbiAgICBjb25zdCBlbmRIb3VyQnlIb3N0ID1cbiAgICAgIGVuZFRpbWVzQnlIb3N0Py5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QnlVc2VyKT8uaG91ciA/PyAyMDtcbiAgICBjb25zdCBlbmRNaW51dGVCeUhvc3QgPVxuICAgICAgZW5kVGltZXNCeUhvc3Q/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRCeVVzZXIpPy5taW51dGVzID8/IDA7XG4gICAgY29uc3QgZW5kSG91ckJ5VXNlciA9IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAuaG91cihlbmRIb3VyQnlIb3N0KVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgY29uc3QgZW5kTWludXRlQnlVc2VyID0gZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAgIC5taW51dGUoZW5kTWludXRlQnlIb3N0KVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5taW51dGUoKTtcblxuICAgIC8vIHZhbGlkYXRlIHZhbHVlcyBiZWZvcmUgY2FsY3VsYXRpbmdcbiAgICBjb25zdCBzdGFydFRpbWVzID0gaG9zdFByZWZlcmVuY2VzLnN0YXJ0VGltZXM7XG4gICAgY29uc3Qgd29ya1N0YXJ0SG91ckJ5SG9zdCA9XG4gICAgICBzdGFydFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QnlVc2VyKT8uaG91ciB8fCA4O1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5SG9zdCA9XG4gICAgICBzdGFydFRpbWVzPy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QnlVc2VyKT8ubWludXRlcyB8fCAwO1xuICAgIGNvbnN0IHdvcmtTdGFydEhvdXJCeVVzZXIgPSBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAudHooaG9zdFRpbWV6b25lKVxuICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5VXNlciA9IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAubWludXRlKCk7XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgIC5pc0FmdGVyKFxuICAgICAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICAvLyByZXR1cm4gZW1wdHkgYXMgb3V0c2lkZSBvZiB3b3JrIHRpbWVcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICAvLyBjaGFuZ2UgdG8gd29yayBzdGFydCB0aW1lIGFzIGFmdGVyIGhvc3Qgc3RhcnQgdGltZVxuICAgIGlmIChcbiAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeUhvc3QpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICApXG4gICAgKSB7XG4gICAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgICBob3Vyczogd29ya1N0YXJ0SG91ckJ5VXNlcixcbiAgICAgICAgbWludXRlczogd29ya1N0YXJ0TWludXRlQnlVc2VyLFxuICAgICAgfSk7XG4gICAgICBjb25zdCBlbmREdXJhdGlvbiA9IGRheWpzLmR1cmF0aW9uKHtcbiAgICAgICAgaG91cnM6IGVuZEhvdXJCeVVzZXIsXG4gICAgICAgIG1pbnV0ZXM6IGVuZE1pbnV0ZUJ5VXNlcixcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgICAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICAgICAgY29uc3QgYXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFtdID0gW107XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgdXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lLFxuICAgICAgICBlbmRUaW1lc0J5SG9zdCxcbiAgICAgICAgZGF5T2ZXZWVrSW50QnlVc2VyLFxuICAgICAgICBkYXlPZk1vbnRoQnlVc2VyLFxuICAgICAgICBzdGFydEhvdXJCeVVzZXIsXG4gICAgICAgIHN0YXJ0TWludXRlQnlVc2VyLFxuICAgICAgICBlbmRIb3VyQnlVc2VyLFxuICAgICAgICBlbmRNaW51dGVCeVVzZXIsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50QnlVc2VyLCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICAgICk7XG4gICAgICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSBzbG90RHVyYXRpb24pIHtcbiAgICAgICAgaWYgKGkgPiB0b3RhbE1pbnV0ZXMpIHtcbiAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgfVxuXG4gICAgICAgIGF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUucHVzaCh7XG4gICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICBzdGFydERhdGU6IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlVc2VyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeVVzZXIpXG4gICAgICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICAgIGVuZERhdGU6IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAuaG91cih3b3JrU3RhcnRIb3VyQnlVc2VyKVxuICAgICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeVVzZXIpXG4gICAgICAgICAgICAuYWRkKGkgKyBzbG90RHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBhdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lLFxuICAgICAgICAnIHRpbWVTbG90cyBpbnNpZGUgZ2VuZXJhdGVUaW1lU2xvdHMgZm9yIGZpcnN0IGRheSB3aGVyZSBzdGFydERhdGUgaXMgYmVmb3JlIHdvcmsgc3RhcnQgdGltZSdcbiAgICAgICk7XG5cbiAgICAgIC8vIGZpbHRlciBvdXQgdW5hdmFpbGFibGUgdGltZXNcbiAgICAgIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZSA9XG4gICAgICAgIGF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUuZmlsdGVyKChhKSA9PiB7XG4gICAgICAgICAgY29uc3QgZm91bmRJbmRleCA9IG5vdEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmU/LmZpbmRJbmRleChcbiAgICAgICAgICAgIChuYSkgPT4ge1xuICAgICAgICAgICAgICBjb25zdCBwYXJ0QSA9IGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkuYWRkKDEsICdtJykuc2Vjb25kKDApLFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkuc3VidHJhY3QoMSwgJ20nKS5zZWNvbmQoMCksXG4gICAgICAgICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgICBjb25zdCBwYXJ0QiA9IGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS5hZGQoMSwgJ20nKS5zZWNvbmQoMCksXG4gICAgICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS5zdWJ0cmFjdCgxLCAnbScpLnNlY29uZCgwKSxcbiAgICAgICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgICAgICdbXSdcbiAgICAgICAgICAgICAgICApO1xuXG4gICAgICAgICAgICAgIGNvbnN0IHBhcnRDID1cbiAgICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnNlY29uZCgwKS5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSA9PT1cbiAgICAgICAgICAgICAgICAgIGRheWpzKGEuc3RhcnREYXRlKS5zZWNvbmQoMCkuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgJiZcbiAgICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS5zZWNvbmQoMCkuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgICAgICBkYXlqcyhhLmVuZERhdGUpLnNlY29uZCgwKS5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKTtcblxuICAgICAgICAgICAgICBjb25zdCBpc05vdEF2YWlsYWJsZSA9IHBhcnRBIHx8IHBhcnRCIHx8IHBhcnRDO1xuXG4gICAgICAgICAgICAgIGNvbnNvbGUubG9nKGEsIG5hLCAnIGEsIG5hJyk7XG4gICAgICAgICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgICAgICBpZiAoZm91bmRJbmRleCAhPT0gdW5kZWZpbmVkICYmIGZvdW5kSW5kZXggPiAtMSkge1xuICAgICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIHJldHVybiB0cnVlO1xuICAgICAgICB9KTtcblxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZSxcbiAgICAgICAgJyBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzJ1xuICAgICAgKTtcblxuICAgICAgcmV0dXJuIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZTtcbiAgICB9XG5cbiAgICBjb25zdCBzdGFydER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgaG91cnM6IHN0YXJ0SG91ckJ5VXNlcixcbiAgICAgIG1pbnV0ZXM6IHN0YXJ0TWludXRlQnlVc2VyLFxuICAgIH0pO1xuICAgIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgICAgaG91cnM6IGVuZEhvdXJCeVVzZXIsXG4gICAgICBtaW51dGVzOiBlbmRNaW51dGVCeVVzZXIsXG4gICAgfSk7XG4gICAgY29uc3QgdG90YWxEdXJhdGlvbiA9IGVuZER1cmF0aW9uLnN1YnRyYWN0KHN0YXJ0RHVyYXRpb24pO1xuICAgIGNvbnN0IHRvdGFsTWludXRlcyA9IHRvdGFsRHVyYXRpb24uYXNNaW51dGVzKCk7XG4gICAgY29uc3QgYXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZTogQXZhaWxhYmxlU2xvdFtdID0gW107XG4gICAgY29uc29sZS5sb2coXG4gICAgICB1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUsXG4gICAgICBlbmRUaW1lc0J5SG9zdCxcbiAgICAgIGRheU9mV2Vla0ludEJ5VXNlcixcbiAgICAgIGVuZEhvdXJCeUhvc3QsXG4gICAgICBlbmRNaW51dGVCeUhvc3QsXG4gICAgICBob3N0VGltZXpvbmUsXG4gICAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZVRpbWVzbG90c2BcbiAgICApO1xuICAgIGZvciAobGV0IGkgPSAwOyBpIDwgdG90YWxNaW51dGVzOyBpICs9IHNsb3REdXJhdGlvbikge1xuICAgICAgaWYgKGkgPiB0b3RhbE1pbnV0ZXMpIHtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9XG4gICAgICBhdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lLnB1c2goe1xuICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICBzdGFydERhdGU6IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHN0YXJ0SG91ckJ5VXNlcilcbiAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlVc2VyKVxuICAgICAgICAgIC5hZGQoaSwgJ21pbnV0ZScpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5mb3JtYXQoKSxcbiAgICAgICAgZW5kRGF0ZTogZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlVc2VyKVxuICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeVVzZXIpXG4gICAgICAgICAgLmFkZChpICsgc2xvdER1cmF0aW9uLCAnbWludXRlJylcbiAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgfSk7XG4gICAgfVxuICAgIGNvbnN0IGZpbHRlcmVkQXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZSA9XG4gICAgICBhdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lLmZpbHRlcigoYSkgPT4ge1xuICAgICAgICBjb25zdCBmb3VuZEluZGV4ID0gbm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZT8uZmluZEluZGV4KChuYSkgPT4ge1xuICAgICAgICAgIGNvbnN0IHBhcnRBID0gZGF5anMoYS5lbmREYXRlKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSkuYWRkKDEsICdtJykuc2Vjb25kKDApLFxuICAgICAgICAgICAgICBkYXlqcyhuYS5lbmREYXRlKS5zdWJ0cmFjdCgxLCAnbScpLnNlY29uZCgwKSxcbiAgICAgICAgICAgICAgJ20nLFxuICAgICAgICAgICAgICAnW10nXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgY29uc3QgcGFydEIgPSBkYXlqcyhhLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLmFkZCgxLCAnbScpLnNlY29uZCgwKSxcbiAgICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkuc3VidHJhY3QoMSwgJ20nKS5zZWNvbmQoMCksXG4gICAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICAgJ1tdJ1xuICAgICAgICAgICAgKTtcblxuICAgICAgICAgIGNvbnN0IHBhcnRDID1cbiAgICAgICAgICAgIGRheWpzKG5hLnN0YXJ0RGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgIGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAgIC5mb3JtYXQoJ1lZWVktTU0tRERUSEg6bW0nKSAmJlxuICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICAgIGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJyk7XG5cbiAgICAgICAgICBjb25zdCBpc05vdEF2YWlsYWJsZSA9IHBhcnRBIHx8IHBhcnRCIHx8IHBhcnRDO1xuXG4gICAgICAgICAgY29uc29sZS5sb2coYSwgbmEsICcgYSwgbmEnKTtcblxuICAgICAgICAgIHJldHVybiBpc05vdEF2YWlsYWJsZTtcbiAgICAgICAgfSk7XG5cbiAgICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgICAgaWYgKGZvdW5kSW5kZXggIT09IHVuZGVmaW5lZCAmJiBmb3VuZEluZGV4ID4gLTEpIHtcbiAgICAgICAgICByZXR1cm4gZmFsc2U7XG4gICAgICAgIH1cblxuICAgICAgICByZXR1cm4gdHJ1ZTtcbiAgICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUsXG4gICAgICAnIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHMnXG4gICAgKTtcbiAgICByZXR1cm4gZmlsdGVyZWRBdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lO1xuICB9XG5cbiAgLy8gbm90IGZpcnN0IGRheSBvZiB0aW1lIHdpbmRvd1xuXG4gIGNvbnN0IHN0YXJ0VGltZXNCeUhvc3QgPSBob3N0UHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcblxuICBjb25zdCBlbmRUaW1lc0J5SG9zdCA9IGhvc3RQcmVmZXJlbmNlcy5lbmRUaW1lcztcblxuICBjb25zdCBkYXlPZldlZWtJbnRCeVVzZXIgPSBnZXRJU09EYXkoXG4gICAgZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKS50eih1c2VyVGltZXpvbmUpLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IGRheU9mTW9udGhCeVVzZXIgPSBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAuZGF0ZSgpO1xuXG4gIC8vIGNvbnZlcnQgdG8gdXNlciB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byB1c2VyIHRpbWV6b25lXG4gIGNvbnN0IGVuZEhvdXJCeUhvc3QgPVxuICAgIGVuZFRpbWVzQnlIb3N0Py5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QnlVc2VyKT8uaG91ciA/PyAyMDtcbiAgY29uc3QgZW5kTWludXRlQnlIb3N0ID1cbiAgICBlbmRUaW1lc0J5SG9zdD8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludEJ5VXNlcik/Lm1pbnV0ZXMgPz8gMDtcbiAgbGV0IGVuZEhvdXJCeVVzZXIgPSBkYXlqcyh1c2VyU3RhcnREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgLnR6KGhvc3RUaW1lem9uZSlcbiAgICAuaG91cihlbmRIb3VyQnlIb3N0KVxuICAgIC5taW51dGUoZW5kTWludXRlQnlIb3N0KVxuICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgbGV0IGVuZE1pbnV0ZUJ5VXNlciA9IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKGVuZEhvdXJCeUhvc3QpXG4gICAgLm1pbnV0ZShlbmRNaW51dGVCeUhvc3QpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAubWludXRlKCk7XG5cbiAgLy8gaWYgbGFzdCBkYXkgY2hhbmdlIGVuZCB0aW1lIHRvIGhvc3RFbmREYXRlIHByb3ZpZGVkXG4gIGlmIChpc0xhc3REYXkgJiYgdXNlckVuZERhdGVJbkhvc3RUaW1lem9uZSkge1xuICAgIGlmIChcbiAgICAgIGRheWpzKHVzZXJFbmREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgIC5pc0JlZm9yZShcbiAgICAgICAgICBkYXlqcyh1c2VyRW5kRGF0ZUluSG9zdFRpbWV6b25lKVxuICAgICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAgIC5ob3VyKGVuZEhvdXJCeVVzZXIpXG4gICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZUJ5VXNlcilcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgZW5kSG91ckJ5VXNlciA9IGRheWpzKHVzZXJFbmREYXRlSW5Ib3N0VGltZXpvbmUpLnR6KHVzZXJUaW1lem9uZSkuaG91cigpO1xuICAgICAgLy8gY3JlYXRlIHNsb3Qgc2l6ZXNcbiAgICAgIGNvbnN0IGZsb29yZWRWYWx1ZSA9IE1hdGguZmxvb3IoNjAgLyBzbG90RHVyYXRpb24pO1xuXG4gICAgICBsZXQgbWludXRlVmFsdWVCeVVzZXIgPSAwO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCBmbG9vcmVkVmFsdWU7IGkrKykge1xuICAgICAgICBjb25zdCBlbmRNaW51dGVzID0gKGkgKyAxKSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgY29uc3Qgc3RhcnRNaW51dGVzID0gaSAqIHNsb3REdXJhdGlvbjtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIGRheWpzKHVzZXJFbmREYXRlSW5Ib3N0VGltZXpvbmUpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICAgICAgZGF5anModXNlckVuZERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVzKSxcbiAgICAgICAgICAgICAgZGF5anModXNlckVuZERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAgIC5taW51dGUoZW5kTWludXRlcyksXG4gICAgICAgICAgICAgICdtaW51dGUnLFxuICAgICAgICAgICAgICAnWyknXG4gICAgICAgICAgICApXG4gICAgICAgICkge1xuICAgICAgICAgIG1pbnV0ZVZhbHVlQnlVc2VyID0gc3RhcnRNaW51dGVzO1xuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGVuZE1pbnV0ZUJ5VXNlciA9IG1pbnV0ZVZhbHVlQnlVc2VyO1xuICAgIH1cbiAgfVxuXG4gIGNvbnN0IHN0YXJ0SG91ckJ5SG9zdCA9IHN0YXJ0VGltZXNCeUhvc3Q/LmZpbmQoXG4gICAgKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRCeVVzZXJcbiAgKT8uaG91ciBhcyBudW1iZXI7XG4gIGNvbnN0IHN0YXJ0TWludXRlQnlIb3N0ID0gc3RhcnRUaW1lc0J5SG9zdD8uZmluZChcbiAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludEJ5VXNlclxuICApPy5taW51dGVzIGFzIG51bWJlcjtcbiAgY29uc3Qgc3RhcnRIb3VyQnlVc2VyID0gZGF5anModXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lKVxuICAgIC50eihob3N0VGltZXpvbmUpXG4gICAgLmhvdXIoc3RhcnRIb3VyQnlIb3N0KVxuICAgIC5taW51dGUoc3RhcnRNaW51dGVCeUhvc3QpXG4gICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAuaG91cigpO1xuICBjb25zdCBzdGFydE1pbnV0ZUJ5VXNlciA9IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAudHooaG9zdFRpbWV6b25lKVxuICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgLm1pbnV0ZSgpO1xuXG4gIGNvbnN0IHN0YXJ0RHVyYXRpb24gPSBkYXlqcy5kdXJhdGlvbih7XG4gICAgaG91cnM6IHN0YXJ0SG91ckJ5VXNlcixcbiAgICBtaW51dGVzOiBzdGFydE1pbnV0ZUJ5VXNlcixcbiAgfSk7XG4gIGNvbnN0IGVuZER1cmF0aW9uID0gZGF5anMuZHVyYXRpb24oe1xuICAgIGhvdXJzOiBlbmRIb3VyQnlVc2VyLFxuICAgIG1pbnV0ZXM6IGVuZE1pbnV0ZUJ5VXNlcixcbiAgfSk7XG4gIGNvbnN0IHRvdGFsRHVyYXRpb24gPSBlbmREdXJhdGlvbi5zdWJ0cmFjdChzdGFydER1cmF0aW9uKTtcbiAgY29uc3QgdG90YWxNaW51dGVzID0gdG90YWxEdXJhdGlvbi5hc01pbnV0ZXMoKTtcblxuICBjb25zdCBhdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lOiBBdmFpbGFibGVTbG90W10gPSBbXTtcbiAgY29uc29sZS5sb2coXG4gICAgdXNlclN0YXJ0RGF0ZUluSG9zdFRpbWV6b25lLFxuICAgIGVuZFRpbWVzQnlIb3N0LFxuICAgIGRheU9mV2Vla0ludEJ5VXNlcixcbiAgICBkYXlPZk1vbnRoQnlVc2VyLFxuICAgIHN0YXJ0SG91ckJ5VXNlcixcbiAgICBzdGFydE1pbnV0ZUJ5VXNlcixcbiAgICBlbmRIb3VyQnlVc2VyLFxuICAgIGVuZE1pbnV0ZUJ5VXNlcixcbiAgICB0aW1lem9uZSxcbiAgICBgc3RhcnREYXRlLCBlbmRUaW1lcywgZGF5T2ZXZWVrSW50QnlIb3N0LCBkYXlPZk1vbnRoLCBzdGFydEhvdXIsIHN0YXJ0TWludXRlLCBlbmRIb3VyLCBlbmRNaW51dGUgdG90YWxNaW51dGVzLCB0aW1lem9uZSwgaW5zaWRlIGZpcnN0RGF5IGluc2lkZSBnZW5lcmF0ZUF2YWlsYWJsZXNsb3RzYFxuICApO1xuICBmb3IgKGxldCBpID0gMDsgaSA8IHRvdGFsTWludXRlczsgaSArPSBzbG90RHVyYXRpb24pIHtcbiAgICBpZiAoaSA+IHRvdGFsTWludXRlcykge1xuICAgICAgY29udGludWU7XG4gICAgfVxuXG4gICAgYXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZS5wdXNoKHtcbiAgICAgIGlkOiB1dWlkKCksXG4gICAgICBzdGFydERhdGU6IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlVc2VyKVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlVc2VyKVxuICAgICAgICAuYWRkKGksICdtaW51dGUnKVxuICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICAgIGVuZERhdGU6IGRheWpzKHVzZXJTdGFydERhdGVJbkhvc3RUaW1lem9uZSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlVc2VyKVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlVc2VyKVxuICAgICAgICAuYWRkKGkgKyBzbG90RHVyYXRpb24sICdtaW51dGUnKVxuICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgIC5mb3JtYXQoKSxcbiAgICB9KTtcbiAgfVxuXG4gIGNvbnNvbGUubG9nKFxuICAgIGF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUsXG4gICAgJyB0aW1lU2xvdHMgaW5zaWRlIGdlbmVyYXRlVGltZVNsb3RzIG5vdCBmaXJzdCBkYXknXG4gICk7XG5cbiAgLy8gZmlsdGVyIG91dCB1bmF2YWlsYWJsZSB0aW1lc1xuICBjb25zdCBmaWx0ZXJlZEF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUgPVxuICAgIGF2YWlsYWJsZVNsb3RzSW5Vc2VyVGltZXpvbmUuZmlsdGVyKChhKSA9PiB7XG4gICAgICBjb25zdCBmb3VuZEluZGV4ID0gbm90QXZhaWxhYmxlU2xvdHNJblVzZXJUaW1lem9uZT8uZmluZEluZGV4KChuYSkgPT4ge1xuICAgICAgICBjb25zdCBwYXJ0QSA9IGRheWpzKGEuZW5kRGF0ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMobmEuc3RhcnREYXRlKS50eih1c2VyVGltZXpvbmUpLmFkZCgxLCAnbScpLnNlY29uZCgwKSxcbiAgICAgICAgICAgIGRheWpzKG5hLmVuZERhdGUpLnR6KHVzZXJUaW1lem9uZSkuc3VidHJhY3QoMSwgJ20nKS5zZWNvbmQoMCksXG4gICAgICAgICAgICAnbScsXG4gICAgICAgICAgICAnW10nXG4gICAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBwYXJ0QiA9IGRheWpzKGEuc3RhcnREYXRlKVxuICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgIC5pc0JldHdlZW4oXG4gICAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpLnR6KHVzZXJUaW1lem9uZSkuYWRkKDEsICdtJykuc2Vjb25kKDApLFxuICAgICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSkudHoodXNlclRpbWV6b25lKS5zdWJ0cmFjdCgxLCAnbScpLnNlY29uZCgwKSxcbiAgICAgICAgICAgICdtJyxcbiAgICAgICAgICAgICdbXSdcbiAgICAgICAgICApO1xuXG4gICAgICAgIGNvbnN0IHBhcnRDID1cbiAgICAgICAgICBkYXlqcyhuYS5zdGFydERhdGUpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLnNlY29uZCgwKVxuICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpID09PVxuICAgICAgICAgICAgZGF5anMoYS5zdGFydERhdGUpXG4gICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpICYmXG4gICAgICAgICAgZGF5anMobmEuZW5kRGF0ZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAuc2Vjb25kKDApXG4gICAgICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tJykgPT09XG4gICAgICAgICAgICBkYXlqcyhhLmVuZERhdGUpXG4gICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5zZWNvbmQoMClcbiAgICAgICAgICAgICAgLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbScpO1xuXG4gICAgICAgIGNvbnN0IGlzTm90QXZhaWxhYmxlID0gcGFydEEgfHwgcGFydEIgfHwgcGFydEM7XG5cbiAgICAgICAgY29uc29sZS5sb2coYSwgbmEsICcgYSwgbmEnKTtcblxuICAgICAgICByZXR1cm4gaXNOb3RBdmFpbGFibGU7XG4gICAgICB9KTtcblxuICAgICAgY29uc29sZS5sb2coZm91bmRJbmRleCwgJyBmb3VuZEluZGV4Jyk7XG5cbiAgICAgIGlmIChmb3VuZEluZGV4ICE9PSB1bmRlZmluZWQgJiYgZm91bmRJbmRleCA+IC0xKSB7XG4gICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgIH1cblxuICAgICAgcmV0dXJuIHRydWU7XG4gICAgfSk7XG5cbiAgY29uc29sZS5sb2coZmlsdGVyZWRBdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lLCAnIGZpbHRlcmVkQXZhaWxhYmxlU2xvdHMnKTtcblxuICByZXR1cm4gZmlsdGVyZWRBdmFpbGFibGVTbG90c0luVXNlclRpbWV6b25lO1xufTtcblxuZXhwb3J0IGNvbnN0IGNhbmNlbE1lZXRpbmdBc3Npc3QgPSBhc3luYyAoaWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnQ2FuY2VsTWVldGluZ0Fzc2lzdCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBDYW5jZWxNZWV0aW5nQXNzaXN0KCRpZDogdXVpZCEpIHtcbiAgICAgICAgICAgICAgICB1cGRhdGVfTWVldGluZ19Bc3Npc3RfYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiB7Y2FuY2VsbGVkOiB0cnVlfSkge1xuICAgICAgICAgICAgICAgICAgICBhbGxvd0F0dGVuZGVlVXBkYXRlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNvdW50XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGJ1ZmZlclRpbWVcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxJZkFueVJlZnVzZVxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxsZWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlQXBwXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGd1YXJhbnRlZUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHNcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgbG9jYXRpb25cbiAgICAgICAgICAgICAgICAgICAgbWluVGhyZXNob2xkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgICAgICAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICBzdW1tYXJ5XG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICB3aW5kb3dFbmREYXRlXG4gICAgICAgICAgICAgICAgICAgIHdpbmRvd1N0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyB1cGRhdGVfTWVldGluZ19Bc3Npc3RfYnlfcGs6IE1lZXRpbmdBc3Npc3RUeXBlIH0gfSA9XG4gICAgICBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgJ1gtUG9zdGdyYXBoaWxlLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXMgJyk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy51cGRhdGVfTWVldGluZ19Bc3Npc3RfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjYW5jZWwgbWVldGluZyBhc3NpdCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVzQnlJZHMgPSBhc3luYyAoaWRzOiBzdHJpbmdbXSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZGVsZXRlTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVzQnlJZHMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgbXV0YXRpb24gZGVsZXRlTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVzQnlJZHMoJGlkczogW3V1aWQhXSEpIHtcbiAgICAgICAgICAgICAgICBkZWxldGVfTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2Uod2hlcmU6IHtpZDoge19pbjogJGlkc319KSB7XG4gICAgICAgICAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVJZFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBkYXlPZldlZWtcbiAgICAgICAgICAgICAgICAgICAgZW5kVGltZVxuICAgICAgICAgICAgICAgICAgICBob3N0SWRcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIHN0YXJ0VGltZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkcyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7XG4gICAgICAgIGRlbGV0ZV9NZWV0aW5nX0Fzc2lzdF9QcmVmZXJyZWRfVGltZV9SYW5nZToge1xuICAgICAgICAgIGFmZmVjdGVkX3Jvd3M6IG51bWJlcjtcbiAgICAgICAgICByZXR1cm5pbmc6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW107XG4gICAgICAgIH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzICcpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uZGVsZXRlX01lZXRpbmdfQXNzaXN0X1ByZWZlcnJlZF9UaW1lX1JhbmdlPy5hZmZlY3RlZF9yb3dzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZGVsZXRlIG1lZXRpbmcgYXNzaXN0IHByZWZlcnJlZCBUaW1lcyBieSBpZHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lcyA9IGFzeW5jIChcbiAgcHJlZmVycmVkVGltZXM6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW11cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcHJlZmVycmVkVGltZXMsXG4gICAgICAnIHByZWZlcnJlZFRpbWVzIGluc2lkZSB1cHNlcnRNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZXMnXG4gICAgKTtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2luc2VydE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lcyc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBpbnNlcnRNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZXMoJHByZWZlcnJlZFRpbWVzOiBbTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2VfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgICAgICAgICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X1ByZWZlcnJlZF9UaW1lX1JhbmdlKG9iamVjdHM6ICRwcmVmZXJyZWRUaW1lcywgXG4gICAgICAgICAgICAgICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgICAgICAgICAgIGNvbnN0cmFpbnQ6IE1lZXRpbmdfQXNzaXN0X1ByZWZlcnJlZF9UaW1lX1Jhbmdlc19wa2V5LCBcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlSWQsXG4gICAgICAgICAgICAgICAgICAgICAgICBkYXlPZldlZWssXG4gICAgICAgICAgICAgICAgICAgICAgICBlbmRUaW1lLFxuICAgICAgICAgICAgICAgICAgICAgICAgaG9zdElkLFxuICAgICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkLFxuICAgICAgICAgICAgICAgICAgICAgICAgc3RhcnRUaW1lLFxuICAgICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICAgICAgICAgICAgICBdXG4gICAgICAgICAgICAgICAgICAgIH0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVJZFxuICAgICAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgICAgIGRheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICAgICAgZW5kVGltZVxuICAgICAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgICAgICBzdGFydFRpbWVcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgcHJlZmVycmVkVGltZXM6IHByZWZlcnJlZFRpbWVzPy5tYXAoKHB0KSA9PiAoe1xuICAgICAgICAuLi5wdCxcbiAgICAgICAgZGF5T2ZXZWVrOiBwdD8uZGF5T2ZXZWVrID09PSAtMSA/IG51bGwgOiBwdD8uZGF5T2ZXZWVrLFxuICAgICAgfSkpLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X1ByZWZlcnJlZF9UaW1lX1JhbmdlOiB7XG4gICAgICAgICAgYWZmZWN0ZWRfcm93czogbnVtYmVyO1xuICAgICAgICAgIHJldHVybmluZzogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXTtcbiAgICAgICAgfTtcbiAgICAgIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gdXBzZXJ0TWVldGluZ0FzaXN0UHJlZmVycmVkVGltZXMgJyk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5pbnNlcnRfTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2U/LmFmZmVjdGVkX3Jvd3M7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cHNlcnRNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZXMnKTtcbiAgfVxufTtcblxuLy8gZW5jb2RlIGJhc2U2NFxuZXhwb3J0IGNvbnN0IEJ0b0EgPSAoc3RyOiBzdHJpbmcpID0+IEJ1ZmZlci5mcm9tKHN0cikudG9TdHJpbmcoJ2Jhc2U2NCcpO1xuLy8gZGVjb2RlIGJhc2U2NFxuZXhwb3J0IGNvbnN0IEF0b0IgPSAoc3RyOiBzdHJpbmcpID0+IEJ1ZmZlci5mcm9tKHN0ciwgJ2Jhc2U2NCcpLnRvU3RyaW5nKCk7XG5cbi8vIGFkbWluIGF1dGggY2FsbFxuLy8gJ0Jhc2ljICcgKyBCdG9BKGBhZG1pbjoke2F1dGhBcGlUb2tlbn1gKVxuXG5leHBvcnQgY29uc3Qgc3RhcnRNZWV0aW5nQXNzaXN0ID0gYXN5bmMgKFxuICBib2R5OiBTY2hlZHVsZUFzc2lzdFdpdGhNZWV0aW5nUXVldWVCb2R5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ290LnBvc3QobWVldGluZ0Fzc2lzdEFkbWluVXJsLCB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246ICdCYXNpYyAnICsgQnRvQShgYWRtaW46JHthdXRoQXBpVG9rZW59YCksXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgICAganNvbjogYm9keSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKCcgc3VjY2Vzc2Z1bGx5IHN0YXJ0ZWQgc3RhcnRNZWV0aW5nQXNzaXN0Jyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzdGFydCBtZWV0aW5nIGFzc2lzdCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0Q3VzdG9tQXZhaWxhYmxlVGltZXMgPSAoXG4gIHNsb3REdXJhdGlvbjogbnVtYmVyLFxuICBob3N0U3RhcnREYXRlOiBzdHJpbmcsXG4gIGhvc3RQcmVmZXJlbmNlczogVXNlclByZWZlcmVuY2VUeXBlLFxuICBob3N0VGltZXpvbmU6IHN0cmluZyxcbiAgdXNlclRpbWV6b25lOiBzdHJpbmcsXG4gIGlzRmlyc3REYXk/OiBib29sZWFuLFxuICBpc0xhc3REYXk/OiBib29sZWFuXG4pOiBDdXN0b21BdmFpbGFibGVUaW1lVHlwZSB8IG51bGwgPT4ge1xuICBpZiAoaXNGaXJzdERheSkge1xuICAgIGNvbnN0IGVuZFRpbWVzQnlIb3N0ID0gaG9zdFByZWZlcmVuY2VzLmVuZFRpbWVzO1xuICAgIGNvbnN0IGRheU9mV2Vla0ludEJ5VXNlciA9IGdldElTT0RheShcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAudG9EYXRlKClcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0SG91ckJ5VXNlciA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuXG4gICAgLy8gY29uc3QgZGF5T2ZNb250aEJ5VXNlciA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnR6KHVzZXJUaW1lem9uZSkuZGF0ZSgpXG5cbiAgICAvLyBjcmVhdGUgc2xvdCBzaXplc1xuICAgIGNvbnN0IGZsb29yZWRWYWx1ZSA9IE1hdGguZmxvb3IoNjAgLyBzbG90RHVyYXRpb24pO1xuXG4gICAgbGV0IG1pbnV0ZVZhbHVlQnlVc2VyID0gMDtcbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGZsb29yZWRWYWx1ZTsgaSsrKSB7XG4gICAgICBjb25zdCBlbmRNaW51dGVzID0gKGkgKyAxKSAqIHNsb3REdXJhdGlvbjtcbiAgICAgIGNvbnN0IHN0YXJ0TWludXRlcyA9IGkgKiBzbG90RHVyYXRpb247XG4gICAgICBpZiAoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVzKSxcbiAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZXMpLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnWyknXG4gICAgICAgICAgKVxuICAgICAgKSB7XG4gICAgICAgIG1pbnV0ZVZhbHVlQnlVc2VyID0gZW5kTWludXRlcztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgLmlzQmV0d2VlbihcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgLm1pbnV0ZShmbG9vcmVkVmFsdWUgKiBzbG90RHVyYXRpb24pLFxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAubWludXRlKDU5KSxcbiAgICAgICAgICAnbWludXRlJyxcbiAgICAgICAgICAnWyknXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIHN0YXJ0SG91ckJ5VXNlciArPSAxO1xuICAgICAgbWludXRlVmFsdWVCeVVzZXIgPSAwO1xuICAgIH1cblxuICAgIGNvbnN0IHN0YXJ0TWludXRlQnlVc2VyID0gbWludXRlVmFsdWVCeVVzZXI7XG5cbiAgICBjb25zdCBlbmRIb3VyQnlIb3N0ID1cbiAgICAgIGVuZFRpbWVzQnlIb3N0Py5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QnlVc2VyKT8uaG91ciA/PyAyMDtcbiAgICBjb25zdCBlbmRNaW51dGVCeUhvc3QgPVxuICAgICAgZW5kVGltZXNCeUhvc3Q/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRCeVVzZXIpPy5taW51dGVzID8/IDA7XG4gICAgY29uc3QgZW5kSG91ckJ5VXNlciA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5ob3VyKGVuZEhvdXJCeUhvc3QpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmhvdXIoKTtcbiAgICBjb25zdCBlbmRNaW51dGVCeVVzZXIgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAubWludXRlKGVuZE1pbnV0ZUJ5SG9zdClcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAubWludXRlKCk7XG5cbiAgICAvLyB2YWxpZGF0ZSB2YWx1ZXMgYmVmb3JlIGNhbGN1bGF0aW5nXG4gICAgY29uc3Qgc3RhcnRUaW1lcyA9IGhvc3RQcmVmZXJlbmNlcy5zdGFydFRpbWVzO1xuICAgIGNvbnN0IHdvcmtTdGFydEhvdXJCeUhvc3QgPVxuICAgICAgc3RhcnRUaW1lcz8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludEJ5VXNlcik/LmhvdXIgfHwgODtcbiAgICBjb25zdCB3b3JrU3RhcnRNaW51dGVCeUhvc3QgPVxuICAgICAgc3RhcnRUaW1lcz8uZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludEJ5VXNlcik/Lm1pbnV0ZXMgfHwgMDtcbiAgICBjb25zdCB3b3JrU3RhcnRIb3VyQnlVc2VyID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLmhvdXIod29ya1N0YXJ0SG91ckJ5SG9zdClcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuaG91cigpO1xuICAgIGNvbnN0IHdvcmtTdGFydE1pbnV0ZUJ5VXNlciA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC5taW51dGUod29ya1N0YXJ0TWludXRlQnlIb3N0KVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5taW51dGUoKTtcblxuICAgIGlmIChcbiAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuaXNBZnRlcihcbiAgICAgICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAuaG91cihlbmRIb3VyQnlIb3N0KVxuICAgICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVCeUhvc3QpXG4gICAgICAgIClcbiAgICApIHtcbiAgICAgIC8vIHJldHVybiBlbXB0eSBhcyBvdXRzaWRlIG9mIHdvcmsgdGltZVxuICAgICAgcmV0dXJuIG51bGw7XG4gICAgfVxuXG4gICAgLy8gY2hhbmdlIHRvIHdvcmsgc3RhcnQgdGltZSBhcyBhZnRlciBob3N0IHN0YXJ0IHRpbWVcbiAgICBpZiAoXG4gICAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLmlzQmVmb3JlKFxuICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXJCeUhvc3QpXG4gICAgICAgICAgICAubWludXRlKHdvcmtTdGFydE1pbnV0ZUJ5SG9zdClcbiAgICAgICAgKVxuICAgICkge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgc3RhcnRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKHdvcmtTdGFydEhvdXJCeVVzZXIpXG4gICAgICAgICAgLm1pbnV0ZSh3b3JrU3RhcnRNaW51dGVCeVVzZXIpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgICBlbmRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgIC5ob3VyKGVuZEhvdXJCeVVzZXIpXG4gICAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVCeVVzZXIpXG4gICAgICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgICAgICBkYXlPZldlZWtJbnQ6IGRheU9mV2Vla0ludEJ5VXNlcixcbiAgICAgIH07XG4gICAgfVxuXG4gICAgcmV0dXJuIHtcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAuaG91cihzdGFydEhvdXJCeVVzZXIpXG4gICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVCeVVzZXIpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGU/LnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgLmhvdXIoZW5kSG91ckJ5VXNlcilcbiAgICAgICAgLm1pbnV0ZShlbmRNaW51dGVCeVVzZXIpXG4gICAgICAgIC5mb3JtYXQoJ0hIOm1tJykgYXMgVGltZSxcbiAgICAgIGRheU9mV2Vla0ludDogZGF5T2ZXZWVrSW50QnlVc2VyLFxuICAgIH07XG4gIH1cblxuICAvLyBub3QgZmlyc3QgZGF5IHN0YXJ0IGZyb20gd29yayBzdGFydCB0aW1lIHNjaGVkdWxlXG4gIGNvbnN0IHN0YXJ0VGltZXNCeUhvc3QgPSBob3N0UHJlZmVyZW5jZXMuc3RhcnRUaW1lcztcbiAgY29uc3QgZW5kVGltZXNCeUhvc3QgPSBob3N0UHJlZmVyZW5jZXMuZW5kVGltZXM7XG5cbiAgY29uc3QgZGF5T2ZXZWVrSW50QnlIb3N0ID0gZ2V0SVNPRGF5KFxuICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKS50eihob3N0VGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpXG4gICk7XG4gIGNvbnN0IGRheU9mV2Vla0ludEJ5VXNlciA9IGdldElTT0RheShcbiAgICBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLnRvRGF0ZSgpXG4gICk7XG5cbiAgY29uc3Qgc3RhcnRIb3VyQnlIb3N0ID0gc3RhcnRUaW1lc0J5SG9zdD8uZmluZChcbiAgICAoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludEJ5SG9zdFxuICApPy5ob3VyIGFzIG51bWJlcjtcbiAgY29uc3Qgc3RhcnRNaW51dGVCeUhvc3QgPSBzdGFydFRpbWVzQnlIb3N0Py5maW5kKFxuICAgIChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QnlIb3N0XG4gICk/Lm1pbnV0ZXMgYXMgbnVtYmVyO1xuICBjb25zdCBzdGFydEhvdXJCeVVzZXIgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgLmhvdXIoKTtcbiAgY29uc3Qgc3RhcnRNaW51dGVCeVVzZXIgPSBkYXlqcyhob3N0U3RhcnREYXRlLnNsaWNlKDAsIDE5KSlcbiAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgIC5ob3VyKHN0YXJ0SG91ckJ5SG9zdClcbiAgICAubWludXRlKHN0YXJ0TWludXRlQnlIb3N0KVxuICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgLm1pbnV0ZSgpO1xuXG4gIC8vIGNvbnZlcnQgdG8gdXNlciB0aW1lem9uZSBzbyBldmVyeXRoaW5nIGlzIGxpbmtlZCB0byB1c2VyIHRpbWV6b25lXG4gIGNvbnN0IGVuZEhvdXJCeUhvc3Q6IG51bWJlciA9XG4gICAgZW5kVGltZXNCeUhvc3Q/LmZpbmQoKGkpID0+IGkuZGF5ID09PSBkYXlPZldlZWtJbnRCeUhvc3QpPy5ob3VyID8/IDIwO1xuICBjb25zdCBlbmRNaW51dGVCeUhvc3QgPVxuICAgIGVuZFRpbWVzQnlIb3N0Py5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50QnlIb3N0KT8ubWludXRlcyA/PyAwO1xuXG4gIC8vIGlmIGxhc3QgZGF5IGNoYW5nZSBlbmQgdGltZSB0byBob3N0U3RhcnREYXRlIHByb3ZpZGVkXG4gIGlmIChpc0xhc3REYXkpIHtcbiAgICBjb25zdCBlbmRIb3VyQnlVc2VyID0gZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgIC5ob3VyKCk7XG4gICAgLy8gY3JlYXRlIHNsb3Qgc2l6ZXNcbiAgICBjb25zdCBmbG9vcmVkVmFsdWUgPSBNYXRoLmZsb29yKDYwIC8gc2xvdER1cmF0aW9uKTtcblxuICAgIGxldCBtaW51dGVWYWx1ZUJ5VXNlciA9IDA7XG5cbiAgICBmb3IgKGxldCBpID0gMDsgaSA8IGZsb29yZWRWYWx1ZTsgaSsrKSB7XG4gICAgICBjb25zdCBlbmRNaW51dGVzID0gKGkgKyAxKSAqIHNsb3REdXJhdGlvbjtcbiAgICAgIGNvbnN0IHN0YXJ0TWludXRlcyA9IGkgKiBzbG90RHVyYXRpb247XG4gICAgICBpZiAoXG4gICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgICAuaXNCZXR3ZWVuKFxuICAgICAgICAgICAgZGF5anMoaG9zdFN0YXJ0RGF0ZS5zbGljZSgwLCAxOSkpXG4gICAgICAgICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgICAgICAgIC5taW51dGUoc3RhcnRNaW51dGVzKSxcbiAgICAgICAgICAgIGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgICAgICAgICAgICAudHooaG9zdFRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgICAgICAgICAubWludXRlKGVuZE1pbnV0ZXMpLFxuICAgICAgICAgICAgJ21pbnV0ZScsXG4gICAgICAgICAgICAnWyknXG4gICAgICAgICAgKVxuICAgICAgKSB7XG4gICAgICAgIG1pbnV0ZVZhbHVlQnlVc2VyID0gc3RhcnRNaW51dGVzO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IGVuZE1pbnV0ZUJ5VXNlciA9IG1pbnV0ZVZhbHVlQnlVc2VyO1xuICAgIHJldHVybiB7XG4gICAgICBzdGFydFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGU/LnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgICAgLnR6KHVzZXJUaW1lem9uZSlcbiAgICAgICAgLmhvdXIoc3RhcnRIb3VyQnlVc2VyKVxuICAgICAgICAubWludXRlKHN0YXJ0TWludXRlQnlVc2VyKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBlbmRUaW1lOiBkYXlqcyhob3N0U3RhcnREYXRlPy5zbGljZSgwLCAxOSkpXG4gICAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAgIC5ob3VyKGVuZEhvdXJCeVVzZXIpXG4gICAgICAgIC5taW51dGUoZW5kTWludXRlQnlVc2VyKVxuICAgICAgICAuZm9ybWF0KCdISDptbScpIGFzIFRpbWUsXG4gICAgICBkYXlPZldlZWtJbnQ6IGRheU9mV2Vla0ludEJ5VXNlcixcbiAgICB9O1xuICB9XG5cbiAgY29uc3QgZW5kSG91ckJ5VXNlciA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmhvdXIoZW5kSG91ckJ5SG9zdClcbiAgICAubWludXRlKGVuZE1pbnV0ZUJ5SG9zdClcbiAgICAudHoodXNlclRpbWV6b25lKVxuICAgIC5ob3VyKCk7XG4gIGNvbnN0IGVuZE1pbnV0ZUJ5VXNlciA9IGRheWpzKGhvc3RTdGFydERhdGUuc2xpY2UoMCwgMTkpKVxuICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgLmhvdXIoZW5kSG91ckJ5SG9zdClcbiAgICAubWludXRlKGVuZE1pbnV0ZUJ5SG9zdClcbiAgICAudHoodXNlclRpbWV6b25lKVxuICAgIC5taW51dGUoKTtcblxuICByZXR1cm4ge1xuICAgIHN0YXJ0VGltZTogZGF5anMoaG9zdFN0YXJ0RGF0ZT8uc2xpY2UoMCwgMTkpKVxuICAgICAgLnR6KGhvc3RUaW1lem9uZSwgdHJ1ZSlcbiAgICAgIC50eih1c2VyVGltZXpvbmUpXG4gICAgICAuaG91cihzdGFydEhvdXJCeVVzZXIpXG4gICAgICAubWludXRlKHN0YXJ0TWludXRlQnlVc2VyKVxuICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgIGVuZFRpbWU6IGRheWpzKGhvc3RTdGFydERhdGU/LnNsaWNlKDAsIDE5KSlcbiAgICAgIC50eihob3N0VGltZXpvbmUsIHRydWUpXG4gICAgICAudHoodXNlclRpbWV6b25lKVxuICAgICAgLmhvdXIoZW5kSG91ckJ5VXNlcilcbiAgICAgIC5taW51dGUoZW5kTWludXRlQnlVc2VyKVxuICAgICAgLmZvcm1hdCgnSEg6bW0nKSBhcyBUaW1lLFxuICAgIGRheU9mV2Vla0ludDogZGF5T2ZXZWVrSW50QnlVc2VyLFxuICB9O1xufTtcblxuZXhwb3J0IGNvbnN0IGdldE1lZXRpbmdBc3Npc3RJbnZpdGVHaXZlbklkID0gYXN5bmMgKGlkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldE1lZXRpbmdBc3Npc3RJbnZpdGVCeUtleSc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBHZXRNZWV0aW5nQXNzaXN0SW52aXRlQnlLZXkoJGlkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0ludml0ZV9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVtYWlsXG4gICAgICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgICAgICBob3N0TmFtZVxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICByZXNwb25zZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9JbnZpdGVfYnlfcGs6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QocG9zdGdyYXBoaWxlR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgc3VjY2Vzc2Z1bGx5IHJldHJpZXZlZCBtZWV0aW5nYXNzaXN0aW52aXRlcycpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uTWVldGluZ19Bc3Npc3RfSW52aXRlX2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IG1lZXRpbmcgYXNzaXN0IGludml0ZSBieSBpZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdE1lZXRpbmdBc3Npc3RJbnZpdGVzR2l2ZW5NZWV0aW5nSWQgPSBhc3luYyAoXG4gIG1lZXRpbmdJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2xpc3RNZWV0aW5nQXNzaXN0SW52aXRlQnlNZWV0aW5nSWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgbGlzdE1lZXRpbmdBc3Npc3RJbnZpdGVCeU1lZXRpbmdJZCgkbWVldGluZ0lkOiB1dWlkISkge1xuICAgICAgICAgICAgICAgIE1lZXRpbmdfQXNzaXN0X0ludml0ZSh3aGVyZToge21lZXRpbmdJZDoge19lcTogJG1lZXRpbmdJZH19KSB7XG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVtYWlsXG4gICAgICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgICAgICBob3N0TmFtZVxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICByZXNwb25zZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgbWVldGluZ0lkLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBNZWV0aW5nX0Fzc2lzdF9JbnZpdGU6IE1lZXRpbmdBc3Npc3RJbnZpdGVUeXBlW10gfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChwb3N0Z3JhcGhpbGVHcmFwaFVybCwge1xuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLVBvc3RncmFwaGlsZS1BZG1pbi1TZWNyZXQnOiBwb3N0Z3JhcGhpbGVBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyBzdWNjZXNzZnVsbHkgcmV0cmlldmVkIG1lZXRpbmdhc3Npc3RpbnZpdGVzJyk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5NZWV0aW5nX0Fzc2lzdF9JbnZpdGU7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IG1lZXRpbmcgYXNzaXN0IGludml0ZXMgZ2l2ZW4gbWVldGluZyBJZCcpO1xuICB9XG59O1xuXG4vLyBhdHRlbmRlZUlkID09PT0gaW52aXRlSWRcbmV4cG9ydCBjb25zdCB1cGRhdGVNZWV0aW5nQXNzaXN0SW52aXRlUmVzcG9uc2UgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmcsXG4gIHJlc3BvbnNlOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAndXBkYXRlTWVldGluZ0Fzc2lzdEludml0ZVJlc3BvbnNlJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIHVwZGF0ZU1lZXRpbmdBc3Npc3RJbnZpdGVSZXNwb25zZSgkaWQ6IFN0cmluZyEsICRyZXNwb25zZTogU3RyaW5nKSB7XG4gICAgICAgICAgICAgICAgdXBkYXRlX01lZXRpbmdfQXNzaXN0X0ludml0ZV9ieV9wayhwa19jb2x1bW5zOiB7aWQ6ICRpZH0sIF9zZXQ6IHtyZXNwb25zZTogJHJlc3BvbnNlfSkge1xuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBlbWFpbFxuICAgICAgICAgICAgICAgICAgICBob3N0SWRcbiAgICAgICAgICAgICAgICAgICAgaG9zdE5hbWVcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICAgICAgcmVzcG9uc2VcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgICAgcmVzcG9uc2UsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YTogeyB1cGRhdGVfTWVldGluZ19Bc3Npc3RfSW52aXRlX2J5X3BrOiBNZWV0aW5nQXNzaXN0SW52aXRlVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KHBvc3RncmFwaGlsZUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtQWRtaW4tU2VjcmV0JzogcG9zdGdyYXBoaWxlQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1Qb3N0Z3JhcGhpbGUtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIHN1Y2Nlc3NmdWxseSB1cGRhdGVkIG1lZXRpbmdhc3Npc3RpbnZpdGVzJyk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy51cGRhdGVfTWVldGluZ19Bc3Npc3RfSW52aXRlX2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIG1lZXRpbmcgYXNzaXN0IGludml0ZSByZXNwb25zZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgPSBhc3luYyAoXG4gIG9yaWdpbmFsTWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGUsXG4gIG9yaWdpbmFsUHJlZmVycmVkVGltZXM/OiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZygnY3JlYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgY2FsbGVkJyk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBvcmlnaW5hbFByZWZlcnJlZFRpbWVzLFxuICAgICAgJyBvcmlnaW5hbFByZWZlcnJlZFRpbWVzICBpbnNpZGUgY3JlYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMnXG4gICAgKTtcbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVzID1cbiAgICAgIGF3YWl0IGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzR2l2ZW5NZWV0aW5nSWQob3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5pZCk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIG1lZXRpbmdBc3Npc3RBdHRlbmRlZXMsXG4gICAgICAnIG1lZXRpbmdBc3Npc3RBdHRlbmRlZXMgaW5zaWRlIGNyZWF0ZVJlY3VycmluZ01lZXRpbmdBc3Npc3RzJ1xuICAgICk7XG4gICAgaWYgKCEobWVldGluZ0Fzc2lzdEF0dGVuZGVlcyAmJiBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIGF0dGVuZGVlcyBpcyBwcmVzZW50Jyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3QgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgPSBnZW5lcmF0ZVJlY3VycmluZ01lZXRpbmdBc3Npc3RzKFxuICAgICAgb3JpZ2luYWxNZWV0aW5nQXNzaXN0XG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKHJlY3VycmluZ01lZXRpbmdBc3Npc3RzLCAnIHJlY3VycmluZ01lZXRpbmdBc3Npc3RzJyk7XG5cbiAgICBpZiAoIShyZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyAmJiByZWN1cnJpbmdNZWV0aW5nQXNzaXN0cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyByZWN1cnJpbmdNZWV0aW5nYXNzaXN0cyBnZW5lcmF0ZWQnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBhd2FpdCBpbnNlcnRNZWV0aW5nQXNzaXN0cyhyZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyk7XG5cbiAgICBjb25zdCByZWN1cnJpbmdNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQW5kUmVjdXJyaW5nUHJlZmVycmVkVGltZXMgPVxuICAgICAgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3RzKFxuICAgICAgICBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVzLFxuICAgICAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyxcbiAgICAgICAgb3JpZ2luYWxQcmVmZXJyZWRUaW1lc1xuICAgICAgKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdEF0dGVuZGVlc0FuZFJlY3VycmluZ1ByZWZlcnJlZFRpbWVzPy5yZWN1cnJpbmdBdHRlbmRlZXMsXG4gICAgICAnIHJlY3VycmluZ01lZXRpbmdBc3Npc3RBdHRlbmRlZXMnXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlY3VycmluZ01lZXRpbmdBc3Npc3RBdHRlbmRlZXNBbmRSZWN1cnJpbmdQcmVmZXJyZWRUaW1lcz8ucmVjdXJyaW5nUHJlZmVycmVkVGltZXMsXG4gICAgICAnIHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzJ1xuICAgICk7XG5cbiAgICBhd2FpdCBpbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzKFxuICAgICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdEF0dGVuZGVlc0FuZFJlY3VycmluZ1ByZWZlcnJlZFRpbWVzLnJlY3VycmluZ0F0dGVuZGVlc1xuICAgICk7XG5cbiAgICBpZiAoXG4gICAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQW5kUmVjdXJyaW5nUHJlZmVycmVkVGltZXNcbiAgICAgICAgPy5yZWN1cnJpbmdQcmVmZXJyZWRUaW1lcz8ubGVuZ3RoID4gMFxuICAgICkge1xuICAgICAgYXdhaXQgdXBzZXJ0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVzKFxuICAgICAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQW5kUmVjdXJyaW5nUHJlZmVycmVkVGltZXM/LnJlY3VycmluZ1ByZWZlcnJlZFRpbWVzXG4gICAgICApO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSByZWN1cnJpbmcgbWVldGluZyBhc3Npc3QnKTtcbiAgfVxufTtcbiJdfQ==