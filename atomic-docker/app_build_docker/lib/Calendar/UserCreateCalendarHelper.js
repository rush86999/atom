"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteEventForTask = exports.createNewEvent = exports.createConference = exports.upsertConferenceInDb = exports.getConferenceInDb = exports.createNewEventInGoogle = exports.getRRuleDay = exports.atomicUpsertEventInDb = exports.getRruleFreq = exports.upsertLocalCalendar = exports.getCalendarInDb = exports.getCurrentEvents = exports.setCurrentEventsForCalendarWeb = exports.reformatToCalendarEventsUIWebForCalendarFromDb = void 0;
const uuid_1 = require("uuid");
const rrule_1 = require("rrule");
const date_utils_1 = require("@lib/date-utils");
const googleCalendarHelper_1 = require("@lib/calendarLib/googleCalendarHelper");
const constants_1 = require("@lib/calendarLib/constants");
const constants_2 = require("@lib/zoom/constants");
const zoomMeetingHelper_1 = require("@lib/zoom/zoomMeetingHelper");
const CategoryHelper_1 = require("@lib/Category/CategoryHelper");
const ReminderHelper_1 = require("@lib/Calendar/Reminder/ReminderHelper");
const AttendeeHelper_1 = require("@lib/Calendar/Attendee/AttendeeHelper");
const client_1 = require("@apollo/client");
const getCalendarById_1 = __importDefault(require("@lib/apollo/gql/getCalendarById"));
const getGlobalPrimaryCalendar_1 = __importDefault(require("@lib/apollo/gql/getGlobalPrimaryCalendar"));
const getAnyCalendar_1 = __importDefault(require("@lib/apollo/gql/getAnyCalendar"));
const getCalendarWithResource_1 = __importDefault(require("@lib/apollo/gql/getCalendarWithResource"));
const getCalendarIntegrationByResourceAndName_1 = __importDefault(require("@lib/apollo/gql/getCalendarIntegrationByResourceAndName"));
const listAllEvents_1 = __importDefault(require("@lib/apollo/gql/listAllEvents"));
const listCategoriesForEvents_1 = __importDefault(require("@lib/apollo/gql/listCategoriesForEvents"));
const getConferenceById_1 = __importDefault(require("@lib/apollo/gql/getConferenceById"));
const deleteEventById_1 = __importDefault(require("@lib/apollo/gql/deleteEventById"));
const constants_3 = require("@lib/Schedule/constants");
const reformatToCalendarEventsUIWebForCalendarFromDb = async (events, client) => {
    try {
        console.log(events, ' events inside reformatToEventsUIForCalendarFromDb');
        if (!(events?.length > 0)) {
            return;
        }
        const tags = (await client.query({
            query: listCategoriesForEvents_1.default,
            variables: {
                eventIds: events?.map(e => e.id),
            },
        }))?.data?.Category_Event?.map(c => ({
            id: c.Category.id,
            name: c.Category.name,
            color: c.Category.color,
            eventId: c.eventId,
        }));
        const eventsModified = events?.map((e) => {
            const tagsForEvent = tags?.filter(t => (t.eventId === e.id));
            const tagsModified = tagsForEvent?.map(t => ({
                id: t.id,
                name: t.name,
                color: t.color
            }));
            return {
                id: e?.id,
                start: date_utils_1.dayjs.tz(e?.startDate.slice(0, 19), e?.timezone || date_utils_1.dayjs.tz.guess()).toDate(),
                end: date_utils_1.dayjs.tz(e?.endDate.slice(0, 19), e?.timezone || date_utils_1.dayjs.tz.guess()).toDate(),
                title: e?.title || e?.summary,
                allDay: e?.allDay,
                calendarId: e?.calendarId,
                eventId: e?.eventId,
                color: tagsForEvent?.[0]?.color || e?.backgroundColor,
                notes: e?.notes,
                tags: tagsModified,
                unlink: e?.unlink,
                modifiable: e?.modifiable,
                priority: e?.priority,
                recurringEndDate: e?.recurrenceRule?.endDate,
                frequency: e?.recurrenceRule?.frequency,
                interval: `${e?.recurrenceRule?.interval}`,
            };
        });
        return eventsModified;
    }
    catch (e) {
        console.log(e, ' unable to reformat to calendar events UI for web');
    }
};
exports.reformatToCalendarEventsUIWebForCalendarFromDb = reformatToCalendarEventsUIWebForCalendarFromDb;
const setCurrentEventsForCalendarWeb = async (userId, client, setCalendarEvents) => {
    try {
        // validate
        if (!userId) {
            console.log('no userId inside setCurrentEventsForCalendar');
            return;
        }
        if (!client) {
            console.log('no client inside setCurrentEventsForCalendar');
            return;
        }
        const eventsFromDb = await (0, exports.getCurrentEvents)(client, userId);
        console.log(eventsFromDb, ' eventsFromDb inside setCurrentEventsForCalendar');
        const events = await (0, exports.reformatToCalendarEventsUIWebForCalendarFromDb)(eventsFromDb, client);
        setCalendarEvents(events);
    }
    catch (e) {
        console.log(e, ' unable to set current for calendar web');
    }
};
exports.setCurrentEventsForCalendarWeb = setCurrentEventsForCalendarWeb;
// do it by limit operator
const getCurrentEvents = async (client, userId) => {
    try {
        const { data } = await client.query({
            query: listAllEvents_1.default,
            variables: {
                userId,
                start: (0, date_utils_1.dayjs)().subtract(2, 'y').format(),
                end: (0, date_utils_1.dayjs)().add(2, 'y').format(),
            },
            fetchPolicy: 'no-cache'
        });
        return data?.Event;
    }
    catch (e) {
        console.log(e, ' unable to get current events');
    }
};
exports.getCurrentEvents = getCurrentEvents;
/**
{
  id?: string;
  start: string; format --> YY-MM-DD HH:MM:ss
  end: string;
  title: string;
  summary?: string;
  color?: string;
}
 */
const getCalendarInDb = async (client, userId, calendarId, globalPrimary, resource) => {
    try {
        if (calendarId) {
            const calendar = (await client.query({
                query: getCalendarById_1.default,
                variables: {
                    id: calendarId,
                },
            })).data?.Calendar_by_pk;
            return calendar;
        }
        else if (globalPrimary && !calendarId) {
            const calendar = (await client.query({
                query: getGlobalPrimaryCalendar_1.default,
                variables: {
                    userId,
                },
            })).data?.Calendar?.[0];
            return calendar;
        }
        else if (!globalPrimary && !calendarId && !resource) {
            const calendar = (await client.query({
                query: getAnyCalendar_1.default,
                variables: {
                    userId,
                },
            })).data?.Calendar?.[0];
            return calendar;
        }
        else if (!globalPrimary && !calendarId && resource?.length > 0) {
            const calendar = (await client.query({
                query: getCalendarWithResource_1.default,
                variables: {
                    userId,
                    resource,
                },
            })).data?.Calendar?.[0];
            return calendar;
        }
    }
    catch (e) {
        console.log(e, ' unable to get calendar from collection');
    }
};
exports.getCalendarInDb = getCalendarInDb;
const upsertLocalCalendar = async (client, id, userId, title, backgroundColor, accessLevel, resource, globalPrimary, foregroundColor) => {
    try {
        const calendarValueToUpsert = {
            id,
            userId,
            title,
            backgroundColor,
            accessLevel,
            resource,
            globalPrimary,
            deleted: false,
            createdDate: (0, date_utils_1.dayjs)().toISOString(),
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        };
        // ASSUMPTION: A custom PG function 'upsertCalendar' handles the upsert logic.
        // Dynamic update_columns are now part of the PG function's ON CONFLICT clause.
        const upsertCalendarMutation = (0, client_1.gql) `
    mutation UpsertCalendar($calendar: CalendarInput!) { # Assuming CalendarInput is the type for a single calendar
      upsertCalendar(input: { calendar: $calendar }) { # Standard PostGraphile mutation input pattern
        calendar { # Assuming the payload returns the calendar
          id
          # Include other fields as needed from CalendarType if they are returned
        }
      }
    }
  `;
        // The type for client.mutate and variable preparation will need to adjust.
        const result = await client.mutate({
            mutation: upsertCalendarMutation,
            variables: {
                calendar: calendarValueToUpsert, // Pass the single object
            },
        });
        return result.data?.upsertCalendar?.calendar; // Adjust access to returned data
    }
    catch (e) {
        console.log(e, ' unable to save local calendar');
    }
};
exports.upsertLocalCalendar = upsertLocalCalendar;
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
const atomicUpsertEventInDb = async (client, id, eventId, userId, startDate, endDate, createdDate, deleted, priority, isFollowUp, isPreEvent, isPostEvent, modifiable, anyoneCanAddSelf, guestsCanInviteOthers, guestsCanSeeOtherGuests, originalStartDate, originalAllDay, updatedAt, calendarId, title, allDay, recurrenceRule, location, notes, attachments, links, 
// alarms?: alarms,
timezone, taskId, taskType, followUpEventId, preEventId, postEventId, forEventId, conferenceId, maxAttendees, sendUpdates, status, summary, transparency, visibility, recurringEventId, iCalUID, htmlLink, colorId, creator, organizer, endTimeUnspecified, recurrence, originalTimezone, attendeesOmitted, extendedProperties, hangoutLink, guestsCanModify, locked, source, eventType, privateCopy, backgroundColor, foregroundColor, useDefaultAlarms, positiveImpactScore, negativeImpactScore, positiveImpactDayOfWeek, positiveImpactTime, negativeImpactDayOfWeek, negativeImpactTime, preferredDayOfWeek, preferredTime, isExternalMeeting, isExternalMeetingModifiable, isMeetingModifiable, isMeeting, dailyTaskList, weeklyTaskList, isBreak, preferredStartTimeRange, preferredEndTimeRange, copyAvailability, copyTimeBlocking, copyTimePreference, copyReminders, copyPriorityLevel, copyModifiable, copyCategories, copyIsBreak, timeBlocking, userModifiedAvailability, userModifiedTimeBlocking, userModifiedTimePreference, userModifiedReminders, userModifiedPriorityLevel, userModifiedCategories, userModifiedModifiable, userModifiedIsBreak, hardDeadline, softDeadline, copyIsMeeting, copyIsExternalMeeting, userModifiedIsMeeting, userModifiedIsExternalMeeting, duration, copyDuration, userModifiedDuration, method, unlink, byWeekDay, localSynced, copyColor, userModifiedColor, meetingId) => {
    try {
        console.log(hardDeadline, softDeadline, ' hardDeadline, softDeadline inside atomicUpsertEventInDb');
        // ASSUMPTION: A custom PG function 'upsertEvent' handles the complex upsert logic.
        // The extensive dynamic update_columns list is now part of the PG function's ON CONFLICT clause.
        // The input type will be something like EventInput!
        const upsertEventMutation = (0, client_1.gql) `
      mutation UpsertEvent($event: EventInput!) { # Assuming EventInput is the type for a single event
        upsertEvent(input: { event: $event }) { # Standard PostGraphile mutation input pattern
          event { # Assuming the payload returns the event
            # It's crucial that the 'returning' fields here match what PostGraphile actually returns
            # based on the PG function's RETURNING clause and PostGraphile's schema generation.
            # This is a best guess based on the original Hasura query.
            # Many of these might be objects or need different casing (camelCase).
            id
            startDate
            endDate
                  allDay
                  recurrence
                  recurrenceRule
                  location
                  notes
                  attachments
                  links
                  timezone
                  taskId
                  taskType
                  priority
                  followUpEventId
                  isFollowUp
                  isPreEvent
                  isPostEvent
                  preEventId
                  postEventId
                  modifiable
                  forEventId
                  conferenceId
                  maxAttendees
                  attendeesOmitted
                  sendUpdates
                  anyoneCanAddSelf
                  guestsCanInviteOthers
                  guestsCanSeeOtherGuests
                  originalStartDate
                  originalTimezone
                  originalAllDay
                  status
                  summary
                  title
                  transparency
                  visibility
                  recurringEventId
                  iCalUID
                  htmlLink
                  colorId
                  creator
                  organizer
                  endTimeUnspecified
                  extendedProperties
                  hangoutLink
                  guestsCanModify
                  locked
                  source
                  eventType
                  privateCopy
                  backgroundColor
                  foregroundColor
                  useDefaultAlarms
                  deleted
                  createdDate
                  updatedAt
                  userId
                  calendarId
                  positiveImpactScore
                  negativeImpactScore
                  positiveImpactDayOfWeek
                  positiveImpactTime
                  negativeImpactDayOfWeek
                  negativeImpactTime
                  preferredDayOfWeek
                  preferredTime
                  isExternalMeeting
                  isExternalMeetingModifiable
                  isMeetingModifiable
                  isMeeting
                  dailyTaskList
                  weeklyTaskList
                  isBreak
                  preferredStartTimeRange
                  preferredEndTimeRange
                  copyAvailability
                  copyTimeBlocking
                  copyTimePreference
                  copyReminders
                  copyPriorityLevel
                  copyModifiable
                  copyCategories
                  copyIsBreak
                  userModifiedAvailability
                  userModifiedTimeBlocking
                  userModifiedTimePreference
                  userModifiedReminders
                  userModifiedPriorityLevel
                  userModifiedCategories
                  userModifiedModifiable
                  userModifiedIsBreak
                  hardDeadline
                  softDeadline
                  copyIsMeeting
                  copyIsExternalMeeting
                  userModifiedIsMeeting
                  userModifiedIsExternalMeeting
                  duration
                  copyDuration
                  userModifiedDuration
                  method
                  unlink
                  copyColor
                  userModifiedColor
                  byWeekDay
                  localSynced
                  timeBlocking
                  meetingId
                  eventId
                }
                # affected_rows # This is not standard in PostGraphile return types for mutations like this.
                                # The upserted event itself is the primary return.
              }
            }
          `;
        let event = {
            // Its structure must match 'EventInput' expected by PostGraphile.
            // Many fields might be optional or have different casing (camelCase).
            id,
            eventId, // Ensure this and other IDs are correctly mapped if casing changes (e.g. eventID)
            meetingId,
            userId,
            startDate,
            endDate,
            createdDate, // Usually set by DB
            deleted,
            priority: 1,
            isFollowUp: false,
            isPreEvent: false,
            isPostEvent: false,
            modifiable: false,
            anyoneCanAddSelf: false,
            guestsCanInviteOthers: false,
            guestsCanSeeOtherGuests: false,
            originalStartDate: undefined,
            originalAllDay: false,
            updatedAt: undefined, // Usually set by DB
            calendarId: undefined,
            // Ensure all fields below are correctly cased (camelCase) and match EventInput
        };
        /**
         *
            priority,
            isFollowUp,
            isPreEvent,
            isPostEvent,
            modifiable,
            anyoneCanAddSelf,
            guestsCanInviteOthers,
            guestsCanSeeOtherGuests,
            originalStartDate,
            originalAllDay,
            updatedAt,
            calendarId,
            title,
            allDay,
            recurrenceRule,
            location,
            notes,
            attachments,
            links,
            timezone,
            taskId,
            taskType,
            followUpEventId,
            preEventId,
            postEventId,
            forEventId,
            conferenceId,
            maxAttendees,
            sendUpdates,
            status,
            summary,
            transparency,
            visibility,
            recurringEventId,
            iCalUID,
            htmlLink,
            colorId,
            creator,
            organizer,
            endTimeUnspecified,
            recurrence,
            originalTimezone,
            attendeesOmitted,
            hangoutLink,
            guestsCanModify,
            locked,
            source,
            eventType,
            privateCopy,
            backgroundColor,
            foregroundColor,
            useDefaultAlarms,
            positiveImpactScore,
            negativeImpactScore,
            positiveImpactDayOfWeek,
            positiveImpactTime,
            negativeImpactDayOfWeek,
            negativeImpactTime,
            preferredDayOfWeek,
            preferredTime,
            isExternalMeeting,
            isExternalMeetingModifiable,
            isMeetingModifiable,
            isMeeting,
            dailyTaskList,
            weeklyTaskList,
            isBreak,
            preferredStartTimeRange,
            preferredEndTimeRange,
            copyAvailability,
            copyTimeBlocking,
            copyTimePreference,
            copyReminders,
            copyPriorityLevel,
            copyModifiable,
            copyCategories,
            copyIsBreak,
            timeBlocking,
            userModifiedAvailability,
            userModifiedTimeBlocking,
            userModifiedTimePreference,
            userModifiedReminders,
            userModifiedPriorityLevel,
            userModifiedCategories,
            userModifiedModifiable,
            userModifiedIsBreak,
            hardDeadline,
            softDeadline,
            copyIsMeeting,
            copyIsExternalMeeting,
            userModifiedIsMeeting,
            userModifiedIsExternalMeeting,
            duration,
            copyDuration,
            userModifiedDuration,
            method,
            unlink,
            copyColor,
            userModifiedColor,
            byWeekDay,
            localSynced,
         */
        if (priority) {
            event.priority = priority;
        }
        if (isFollowUp !== undefined) {
            event.isFollowUp = isFollowUp;
        }
        if (isPreEvent !== undefined) {
            event.isPreEvent = isPreEvent;
        }
        if (isPostEvent !== undefined) {
            event.isPostEvent = isPostEvent;
        }
        if (modifiable !== undefined) {
            event.modifiable = modifiable;
        }
        if (anyoneCanAddSelf !== undefined) {
            event.anyoneCanAddSelf = anyoneCanAddSelf;
        }
        if (guestsCanInviteOthers !== undefined) {
            event.guestsCanInviteOthers = guestsCanInviteOthers;
        }
        if (guestsCanSeeOtherGuests !== undefined) {
            event.guestsCanSeeOtherGuests = guestsCanSeeOtherGuests;
        }
        if (originalStartDate !== undefined) {
            event.originalStartDate = originalStartDate;
        }
        if (originalAllDay !== undefined) {
            event.originalAllDay = originalAllDay;
        }
        if (updatedAt !== undefined) {
            event.updatedAt = updatedAt;
        }
        if (calendarId !== undefined) {
            event.calendarId = calendarId;
        }
        if (title !== undefined) {
            event.title = title;
        }
        if (allDay !== undefined) {
            event.allDay = allDay;
        }
        if (recurrenceRule !== undefined) {
            event.recurrenceRule = recurrenceRule;
        }
        if (location !== undefined) {
            event.location = location;
        }
        if (notes !== undefined) {
            event.notes = notes;
        }
        if (attachments !== undefined) {
            event.attachments = attachments;
        }
        if (links !== undefined) {
            event.links = links;
        }
        if (timezone !== undefined) {
            event.timezone = timezone;
        }
        if (taskId !== undefined) {
            event.taskId = taskId;
        }
        if (taskType !== undefined) {
            event.taskType = taskType;
        }
        if (followUpEventId !== undefined) {
            event.followUpEventId = followUpEventId;
        }
        if (preEventId !== undefined) {
            event.preEventId = preEventId;
        }
        if (postEventId !== undefined) {
            event.postEventId = postEventId;
        }
        if (forEventId !== undefined) {
            event.forEventId = forEventId;
        }
        if (conferenceId !== undefined) {
            event.conferenceId = conferenceId;
        }
        if (maxAttendees !== undefined) {
            event.maxAttendees = maxAttendees;
        }
        if (sendUpdates !== undefined) {
            event.sendUpdates = sendUpdates;
        }
        if (status !== undefined) {
            event.status = status;
        }
        if (summary !== undefined) {
            event.summary = summary;
        }
        if (transparency !== undefined) {
            event.transparency = transparency;
        }
        if (visibility !== undefined) {
            event.visibility = visibility;
        }
        if (recurringEventId !== undefined) {
            event.recurringEventId = recurringEventId;
        }
        if (iCalUID !== undefined) {
            event.iCalUID = iCalUID;
        }
        if (htmlLink !== undefined) {
            event.htmlLink = htmlLink;
        }
        if (colorId !== undefined) {
            event.colorId = colorId;
        }
        if (creator !== undefined) {
            event.creator = creator;
        }
        if (organizer !== undefined) {
            event.organizer = organizer;
        }
        if (endTimeUnspecified !== undefined) {
            event.endTimeUnspecified = endTimeUnspecified;
        }
        if (recurrence !== undefined) {
            event.recurrence = recurrence;
        }
        if (originalTimezone !== undefined) {
            event.originalTimezone = originalTimezone;
        }
        if (attendeesOmitted !== undefined) {
            event.attendeesOmitted = attendeesOmitted;
        }
        if (hangoutLink !== undefined) {
            event.hangoutLink = hangoutLink;
        }
        if (guestsCanModify !== undefined) {
            event.guestsCanModify = guestsCanModify;
        }
        if (locked !== undefined) {
            event.locked = locked;
        }
        if (source !== undefined) {
            event.source = source;
        }
        if (eventType !== undefined) {
            event.eventType = eventType;
        }
        if (privateCopy !== undefined) {
            event.privateCopy = privateCopy;
        }
        if (guestsCanSeeOtherGuests !== undefined) {
            event.guestsCanSeeOtherGuests = guestsCanSeeOtherGuests;
        }
        if (backgroundColor !== undefined) {
            event.backgroundColor = backgroundColor;
        }
        if (foregroundColor !== undefined) {
            event.foregroundColor = foregroundColor;
        }
        if (useDefaultAlarms !== undefined) {
            event.useDefaultAlarms = useDefaultAlarms;
        }
        if (positiveImpactScore !== undefined) {
            event.positiveImpactScore = positiveImpactScore;
        }
        if (negativeImpactScore !== undefined) {
            event.negativeImpactScore = negativeImpactScore;
        }
        if (positiveImpactDayOfWeek !== undefined) {
            event.positiveImpactDayOfWeek = positiveImpactDayOfWeek;
        }
        if (negativeImpactDayOfWeek !== undefined) {
            event.negativeImpactDayOfWeek = negativeImpactDayOfWeek;
        }
        if (positiveImpactTime !== undefined) {
            event.positiveImpactTime = positiveImpactTime;
        }
        if (negativeImpactTime !== undefined) {
            event.negativeImpactTime = negativeImpactTime;
        }
        if (preferredDayOfWeek !== undefined) {
            event.preferredDayOfWeek = preferredDayOfWeek;
        }
        if (preferredTime !== undefined) {
            event.preferredTime = preferredTime;
        }
        if (isExternalMeeting !== undefined) {
            event.isExternalMeeting = isExternalMeeting;
        }
        if (isExternalMeetingModifiable !== undefined) {
            event.isExternalMeetingModifiable = isExternalMeetingModifiable;
        }
        if (isMeetingModifiable !== undefined) {
            event.isMeetingModifiable = isMeetingModifiable;
        }
        if (isMeeting !== undefined) {
            event.isMeeting = isMeeting;
        }
        if (dailyTaskList !== undefined) {
            event.dailyTaskList = dailyTaskList;
        }
        if (weeklyTaskList !== undefined) {
            event.weeklyTaskList = weeklyTaskList;
        }
        if (isBreak !== undefined) {
            event.isBreak = isBreak;
        }
        if (preferredStartTimeRange !== undefined) {
            event.preferredStartTimeRange = preferredStartTimeRange;
        }
        if (preferredEndTimeRange !== undefined) {
            event.preferredEndTimeRange = preferredEndTimeRange;
        }
        if (copyAvailability !== undefined) {
            event.copyAvailability = copyAvailability;
        }
        if (copyTimeBlocking !== undefined) {
            event.copyTimeBlocking = copyTimeBlocking;
        }
        if (copyTimePreference !== undefined) {
            event.copyTimePreference = copyTimePreference;
        }
        if (copyReminders !== undefined) {
            event.copyReminders = copyReminders;
        }
        if (copyPriorityLevel !== undefined) {
            event.copyPriorityLevel = copyPriorityLevel;
        }
        if (copyModifiable !== undefined) {
            event.copyModifiable = copyModifiable;
        }
        if (copyCategories !== undefined) {
            event.copyCategories = copyCategories;
        }
        if (copyIsBreak !== undefined) {
            event.copyIsBreak = copyIsBreak;
        }
        if (timeBlocking !== undefined) {
            event.timeBlocking = timeBlocking;
        }
        if (userModifiedAvailability !== undefined) {
            event.userModifiedAvailability = userModifiedAvailability;
        }
        if (userModifiedTimeBlocking !== undefined) {
            event.userModifiedTimeBlocking = userModifiedTimeBlocking;
        }
        if (userModifiedTimePreference !== undefined) {
            event.userModifiedTimePreference = userModifiedTimePreference;
        }
        if (userModifiedReminders !== undefined) {
            event.userModifiedReminders = userModifiedReminders;
        }
        if (userModifiedPriorityLevel !== undefined) {
            event.userModifiedPriorityLevel = userModifiedPriorityLevel;
        }
        if (userModifiedCategories !== undefined) {
            event.userModifiedCategories = userModifiedCategories;
        }
        if (userModifiedModifiable !== undefined) {
            event.userModifiedModifiable = userModifiedModifiable;
        }
        if (userModifiedIsBreak !== undefined) {
            event.userModifiedIsBreak = userModifiedIsBreak;
        }
        if (hardDeadline !== undefined) {
            event.hardDeadline = hardDeadline;
        }
        if (softDeadline !== undefined) {
            event.softDeadline = softDeadline;
        }
        if (copyIsMeeting !== undefined) {
            event.copyIsMeeting = copyIsMeeting;
        }
        if (copyIsExternalMeeting !== undefined) {
            event.copyIsExternalMeeting = copyIsExternalMeeting;
        }
        if (userModifiedIsMeeting !== undefined) {
            event.userModifiedIsMeeting = userModifiedIsMeeting;
        }
        if (userModifiedIsExternalMeeting !== undefined) {
            event.userModifiedIsExternalMeeting = userModifiedIsExternalMeeting;
        }
        if (duration !== undefined) {
            event.duration = duration;
        }
        if (copyDuration !== undefined) {
            event.copyDuration = copyDuration;
        }
        if (userModifiedDuration !== undefined) {
            event.userModifiedDuration = userModifiedDuration;
        }
        if (method !== undefined) {
            event.method = method;
        }
        if (unlink !== undefined) {
            event.unlink = unlink;
        }
        if (copyColor !== undefined) {
            event.copyColor = copyColor;
        }
        if (userModifiedColor !== undefined) {
            event.userModifiedColor = userModifiedColor;
        }
        if (byWeekDay !== undefined) {
            event.byWeekDay = byWeekDay;
        }
        if (localSynced !== undefined) {
            event.localSynced = localSynced;
        }
        event.eventId = eventId;
        if (meetingId !== undefined) {
            event.meetingId = meetingId;
        }
        console.log(event, ' event inside atomicUpsertEventInDb');
        const variables = {
            event: event // Pass the single event object, matching the $event: EventInput! in the mutation
        };
        // Adjust the generic type for client.mutate based on the actual PostGraphile mutation payload
        const response = await client.mutate({
            mutation: upsertEventMutation, // Use the renamed mutation variable
            variables,
            // refetchQueries might be a more robust way to handle cache updates initially
            // refetchQueries: [
            //   { query: listAllEvents, variables: { /* appropriate variables for listAllEvents */ } }
            // ],
            update(cache, { data }) {
                const upsertedEvent = data?.upsertEvent?.event;
                if (upsertedEvent) {
                    console.log('upsertEvent result', upsertedEvent);
                    // The cache update logic here is highly speculative and needs verification.
                    // It assumes a root field 'Event' for a list, which is unlikely with PostGraphile.
                    // It would more likely be 'allEvents' or a similar connection field.
                    cache.modify({
                        fields: {
                            // This field name 'Event' is likely incorrect for PostGraphile.
                            Event: (existingEvents = [], { readField }) => {
                                // Attempt to find and replace or add the new event.
                                // This simple replacement might not work well with pagination or complex list structures.
                                const newEventRef = cache.writeFragment({
                                    data: upsertedEvent,
                                    fragment: (0, client_1.gql) `
                    fragment NewEvent on Event { # Type name 'Event' should be checked against PostGraphile schema
                      id
                      startDate
                      endDate
                      allDay
                      recurrence
                      recurrenceRule
                      location
                      notes
                      attachments
                      links
                      timezone
                      taskId
                      taskType
                      priority
                      followUpEventId
                      isFollowUp
                      isPreEvent
                      isPostEvent
                      preEventId
                      postEventId
                      modifiable
                      forEventId
                      conferenceId
                      maxAttendees
                      attendeesOmitted
                      sendUpdates
                      anyoneCanAddSelf
                      guestsCanInviteOthers
                      guestsCanSeeOtherGuests
                      originalStartDate
                      originalTimezone
                      originalAllDay
                      status
                      summary
                      title
                      transparency
                      visibility
                      recurringEventId
                      iCalUID
                      htmlLink
                      colorId
                      creator
                      organizer
                      endTimeUnspecified
                      extendedProperties
                      hangoutLink
                      guestsCanModify
                      locked
                      source
                      eventType
                      privateCopy
                      backgroundColor
                      foregroundColor
                      useDefaultAlarms
                      deleted
                      createdDate
                      updatedAt
                      userId
                      calendarId
                      positiveImpactScore
                      negativeImpactScore
                      positiveImpactDayOfWeek
                      positiveImpactTime
                      negativeImpactDayOfWeek
                      negativeImpactTime
                      preferredDayOfWeek
                      preferredTime
                      isExternalMeeting
                      isExternalMeetingModifiable
                      isMeetingModifiable
                      isMeeting
                      dailyTaskList
                      weeklyTaskList
                      isBreak
                      preferredStartTimeRange
                      preferredEndTimeRange
                      copyAvailability
                      copyTimeBlocking
                      copyTimePreference
                      copyReminders
                      copyPriorityLevel
                      copyModifiable
                      copyCategories
                      copyIsBreak
                      userModifiedAvailability
                      userModifiedTimeBlocking
                      userModifiedTimePreference
                      userModifiedReminders
                      userModifiedPriorityLevel
                      userModifiedCategories
                      userModifiedModifiable
                      userModifiedIsBreak
                      hardDeadline
                      softDeadline
                      copyIsMeeting
                      copyIsExternalMeeting
                      userModifiedIsMeeting
                      userModifiedIsExternalMeeting
                      duration
                      copyDuration
                      userModifiedDuration
                      method
                      unlink
                      copyColor
                      userModifiedColor
                      byWeekDay
                      localSynced
                      timeBlocking
                      meetingId
                      eventId
                    }
                  `,
                                });
                                const filteredEvents = existingEvents?.filter((e) => (e?.id !== data?.insert_Event?.returning?.[0]?.id)) || [];
                                console.log(filteredEvents, ' filteredEvents inside atomicUpsertEventInDb');
                                if (filteredEvents?.length > 0) {
                                    return filteredEvents.concat([newEventRef]);
                                }
                                return [newEventRef];
                            }
                        }
                    });
                }
            }
        });
        console.log(response?.data?.insert_Event?.returning?.[0], ' response?.data?.insert_Event?.returning?.[0] inside atomiceupserteventindb');
        return response?.data?.insert_Event?.returning?.[0];
    }
    catch (e) {
        console.log(e, ' unable to save calendar event');
    }
};
exports.atomicUpsertEventInDb = atomicUpsertEventInDb;
const getRRuleDay = (value) => {
    switch (value) {
        case constants_3.Day.MO:
            return rrule_1.RRule.MO;
        case constants_3.Day.TU:
            return rrule_1.RRule.TU;
        case constants_3.Day.WE:
            return rrule_1.RRule.WE;
        case constants_3.Day.TH:
            return rrule_1.RRule.TH;
        case constants_3.Day.FR:
            return rrule_1.RRule.FR;
        case constants_3.Day.SA:
            return rrule_1.RRule.SA;
        case constants_3.Day.SU:
            return rrule_1.RRule.SU;
        default:
            return undefined;
    }
};
exports.getRRuleDay = getRRuleDay;
const createNewEventInGoogle = async (startDate, endDate, userId, client, calendar, conferenceData, attendees, title, allDay, recurringEndDate, frequency, interval, notes, location, isFollowUp, isPreEvent, isPostEvent, modifiable, anyoneCanAddSelf, guestsCanInviteOthers, guestsCanSeeOtherGuests, originalAllDay, alarms, timezone, taskId, taskType, followUpEventId, preEventId, postEventId, forEventId, maxAttendees, sendUpdates, status, transparency, visibility, iCalUID, backgroundColor, foregroundColor, colorId, originalTimezone, useDefaultAlarms, positiveImpactScore, negativeImpactScore, positiveImpactDayOfWeek, positiveImpactTime, negativeImpactDayOfWeek, negativeImpactTime, preferredDayOfWeek, preferredTime, isExternalMeeting, isExternalMeetingModifiable, isMeetingModifiable, isMeeting, dailyTaskList, weeklyTaskList, isBreak, preferredStartTimeRange, preferredEndTimeRange, copyAvailability, copyTimeBlocking, copyTimePreference, copyReminders, copyPriorityLevel, copyModifiable, copyCategories, copyIsBreak, timeBlocking, userModifiedAvailability, userModifiedTimeBlocking, userModifiedTimePreference, userModifiedReminders, userModifiedPriorityLevel, userModifiedCategories, userModifiedModifiable, userModifiedIsBreak, hardDeadline, softDeadline, copyIsMeeting, copyIsExternalMeeting, userModifiedIsMeeting, userModifiedIsExternalMeeting, duration, copyDuration, userModifiedDuration, method, unlink, byWeekDay, priority) => {
    try {
        console.log(hardDeadline, softDeadline, ' hardDeadline, softDeadline inside createNewEventInGoogle');
        let rule = {};
        if ((recurringEndDate?.length > 0) && frequency) {
            rule = new rrule_1.RRule({
                freq: (0, exports.getRruleFreq)(frequency),
                interval,
                until: (0, date_utils_1.dayjs)(recurringEndDate).toDate(),
                byweekday: byWeekDay?.map(i => (0, exports.getRRuleDay)(i))
            });
        }
        let modifiedAlarms = null;
        if (typeof alarms?.[0] === 'string') {
            modifiedAlarms = {
                useDefault: false, overrides: alarms.map(i => ({
                    method: 'email',
                    minutes: (0, date_utils_1.dayjs)(startDate).diff(i, 'm'),
                }))
            };
        }
        else if (typeof alarms?.[0] === 'number') {
            modifiedAlarms = { useDefault: false, overrides: alarms.map(i => ({ method: 'email', minutes: i })) };
        }
        if (useDefaultAlarms) {
            modifiedAlarms = { useDefault: useDefaultAlarms };
        }
        console.log(modifiedAlarms, ' modifiedAlarms inside createNewEventInGoogle');
        const eventId = await (0, googleCalendarHelper_1.createGoogleEvent)(client, userId, calendar?.id, endDate, startDate, undefined, maxAttendees, sendUpdates, anyoneCanAddSelf, attendees, conferenceData, title, notes, timezone, allDay && (0, date_utils_1.dayjs)(startDate).format('YYYY-MM-DD'), allDay && (endDate || startDate), undefined, guestsCanInviteOthers, false, // guestsCanModify
        guestsCanSeeOtherGuests, undefined, undefined, frequency
            && recurringEndDate
            && interval
            && [rule.toString()], modifiedAlarms, undefined, status, transparency, visibility, iCalUID, false, undefined, undefined, undefined, undefined, undefined, location?.title);
        console.log(eventId, ' inside createNewEventInGoogle after createGoogleEvent');
        await (0, exports.atomicUpsertEventInDb)(client, `${eventId}#${calendar?.id}`, eventId, userId, (0, date_utils_1.dayjs)(startDate).format(), (0, date_utils_1.dayjs)(endDate).format(), (0, date_utils_1.dayjs)().toISOString(), false, priority || 1, isFollowUp ?? false, isPreEvent ?? false, isPostEvent ?? false, modifiable ?? true, anyoneCanAddSelf ?? false, guestsCanInviteOthers ?? false, guestsCanSeeOtherGuests ?? true, (0, date_utils_1.dayjs)(startDate).format(), originalAllDay ?? false, (0, date_utils_1.dayjs)().toISOString(), calendar?.id, title ?? 'New Event', allDay ?? false, frequency
            && recurringEndDate
            && interval
            && { frequency, endDate: recurringEndDate, interval }, location, notes, undefined, undefined, 
        // modifiedAlarms,
        timezone ?? date_utils_1.dayjs.tz.guess(), taskId, taskType, followUpEventId, preEventId, postEventId, forEventId, conferenceData?.conferenceId, maxAttendees, sendUpdates, status, title, transparency, visibility, recurringEndDate
            && frequency
            && eventId, iCalUID, undefined, colorId, undefined, // creator - read only G-event
        undefined, // organizer - G-event import only
        false, // endTimeUnspecified - only for G-events
        frequency
            && recurringEndDate
            && interval
            && [rule.toString()], originalTimezone, //timezone of recurrence instance
        undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, backgroundColor, foregroundColor, useDefaultAlarms, positiveImpactScore, negativeImpactScore, positiveImpactDayOfWeek, positiveImpactTime, negativeImpactDayOfWeek, negativeImpactTime, preferredDayOfWeek, preferredTime, isExternalMeeting, isExternalMeetingModifiable, isMeetingModifiable, isMeeting, dailyTaskList, weeklyTaskList, isBreak, preferredStartTimeRange, preferredEndTimeRange, copyAvailability, copyTimeBlocking, copyTimePreference, copyReminders, copyPriorityLevel, copyModifiable, copyCategories, copyIsBreak, timeBlocking, userModifiedAvailability, userModifiedTimeBlocking, userModifiedTimePreference, userModifiedReminders, userModifiedPriorityLevel, userModifiedCategories, userModifiedModifiable, userModifiedIsBreak, hardDeadline, softDeadline, copyIsMeeting, copyIsExternalMeeting, userModifiedIsMeeting, userModifiedIsExternalMeeting, duration, copyDuration, userModifiedDuration, method, unlink, byWeekDay);
        if (alarms?.length > 0) {
            const promises = alarms?.map((a) => (0, ReminderHelper_1.createReminderForEvent)(client, userId, `${eventId}#${calendar?.id}`, (typeof a === 'string') && a, timezone, (typeof a === 'number') && a, useDefaultAlarms));
            await Promise.all(promises);
        }
        console.log(eventId, ' eventId before returning inside createNewEventInGoogle');
        return eventId;
    }
    catch (e) {
        console.log(e, ' unable to create new event in google calendar');
    }
};
exports.createNewEventInGoogle = createNewEventInGoogle;
const getConferenceInDb = async (client, conferenceId) => {
    try {
        const conference = (await client.query({
            query: getConferenceById_1.default,
            variables: {
                id: conferenceId,
            },
        })).data?.Conference_by_pk;
        return conference;
    }
    catch (e) {
        console.log(e, ' unable to get conference in db');
    }
};
exports.getConferenceInDb = getConferenceInDb;
const upsertConferenceInDb = async (client, id, userId, calendarId, app, requestId, type, status, iconUri, name, notes, entryPoints, parameters, key, hangoutLink, joinUrl, startUrl, zoomPrivateMeeting) => {
    try {
        const conferenceValuesToUpsert = {
            id,
            userId,
            // requestId,
            // type,
            calendarId,
            app,
            status,
            // iconUri,
            // name,
            // notes,
            // entryPoints,
            // parameters,
            // key,
            // hangoutLink,
            // joinUrl,
            // startUrl,
            // zoomPrivateMeeting,
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
            createdDate: (0, date_utils_1.dayjs)().toISOString(),
            deleted: false,
        };
        if (requestId) {
            conferenceValuesToUpsert.requestId = requestId;
        }
        if (type) {
            conferenceValuesToUpsert.type = type;
        }
        if (iconUri) {
            conferenceValuesToUpsert.iconUri = iconUri;
        }
        if (name) {
            conferenceValuesToUpsert.name = name;
        }
        if (entryPoints?.[0]) {
            conferenceValuesToUpsert.entryPoints = entryPoints;
        }
        if (parameters) {
            conferenceValuesToUpsert.parameters = parameters;
        }
        if (key) {
            conferenceValuesToUpsert.key = key;
        }
        if (hangoutLink) {
            conferenceValuesToUpsert.hangoutLink = hangoutLink;
        }
        if (joinUrl) {
            conferenceValuesToUpsert.joinUrl = joinUrl;
        }
        if (startUrl) {
            conferenceValuesToUpsert.startUrl = startUrl;
        }
        if (zoomPrivateMeeting) {
            conferenceValuesToUpsert.zoomPrivateMeeting = zoomPrivateMeeting;
        }
        const upsertConference = (0, client_1.gql) `
      mutation InsertConference($conferences: [Conference_insert_input!]!) {
        insert_Conference(
            objects: $conferences,
            on_conflict: {
                constraint: Conference_pkey,
                update_columns: [
                  ${requestId ? 'requestId,' : ''}
                  ${type ? 'type,' : ''}
                  ${status ? 'status,' : ''}
                  calendarId,
                  ${iconUri ? 'iconUri,' : ''}
                  ${name ? 'name,' : ''}
                  ${notes ? 'notes,' : ''}
                  ${entryPoints ? 'entryPoints,' : ''}
                  ${parameters ? 'parameters,' : ''}
                  app,
                  ${key ? 'key,' : ''}
                  ${hangoutLink ? 'hangoutLink,' : ''}
                  ${joinUrl ? 'joinUrl,' : ''}
                  ${startUrl ? 'startUrl,' : ''}
                  ${zoomPrivateMeeting ? 'zoomPrivateMeeting,' : ''}
                  deleted,
                  updatedAt,
                ]
            }){
            returning {
              id
            }
          }
      }
    `;
        const { data } = await client.mutate({
            mutation: upsertConference,
            variables: {
                conferences: [conferenceValuesToUpsert],
            },
        });
        console.log(data.insert_Conference, ' data.insert_Conference');
        return data.insert_Conference.returning[0];
    }
    catch (e) {
        console.log(e, ' unable to save conference in db');
    }
};
exports.upsertConferenceInDb = upsertConferenceInDb;
const createConference = async (startDate, endDate, client, calendarId, zoomMeet = false, googleMeet = false, userId, meetingTypeString, attendees, requestId, summary, taskType, notes, zoomPassword, zoomPrivateMeeting) => {
    try {
        // validate
        if (zoomMeet && googleMeet) {
            throw new Error('cannot create both zoom and google meet');
        }
        if (!zoomMeet && !googleMeet) {
            throw new Error('must create either zoom or google meet');
        }
        if (!startDate || !endDate) {
            throw new Error('startDate and endDate are required');
        }
        if (!calendarId) {
            throw new Error('calendarId is required');
        }
        // create conference if any
        let newConferenceId = '';
        let newJoinUrl = '';
        let newStartUrl = '';
        let newConferenceStatus = '';
        let conferenceName = constants_2.zoomName;
        let conferenceType = 'addOn';
        let conferenceData = {
            type: 'addOn',
            name: conferenceName,
            requestId: (0, uuid_1.v4)(),
            conferenceId: newConferenceId,
            createRequest: false,
            entryPoints: [{
                    label: constants_2.zoomName,
                    entryPointType: 'video',
                    uri: newJoinUrl,
                    password: zoomPassword,
                }]
        };
        let newRequestId = requestId || (0, uuid_1.v4)();
        if (zoomMeet) {
            const isZoomAvailable = await (0, zoomMeetingHelper_1.zoomAvailable)(client, userId);
            if (isZoomAvailable) {
                const zoomInteg = (await client.query({
                    query: getCalendarIntegrationByResourceAndName_1.default,
                    variables: {
                        userId,
                        name: constants_2.zoomName,
                        resource: constants_2.zoomResourceName,
                    }
                }))?.data?.Calendar_Integration?.[0];
                const { id: zoomConferenceId, join_url: zoomJoinUrl, start_url: zoomStartUrl, status: zoomStatus, } = await (0, zoomMeetingHelper_1.createZoomMeeting)(userId, (0, date_utils_1.dayjs)(startDate).format(), date_utils_1.dayjs.tz.guess(), summary ?? taskType ?? notes, date_utils_1.dayjs.duration({ hours: (0, date_utils_1.dayjs)(endDate).hour(), minutes: (0, date_utils_1.dayjs)(endDate).minute() }).asMinutes(), zoomInteg?.contactName, zoomInteg?.contactEmail, attendees.map(i => i?.email), zoomPrivateMeeting);
                newConferenceId = zoomConferenceId;
                newJoinUrl = zoomJoinUrl;
                newStartUrl = zoomStartUrl;
                newConferenceStatus = zoomStatus;
                conferenceName = constants_2.zoomName;
                conferenceType = 'addOn';
                conferenceData = {
                    type: conferenceType,
                    name: conferenceName,
                    requestId: newRequestId,
                    conferenceId: `${newConferenceId}`,
                    createRequest: false,
                    entryPoints: [{
                            label: constants_2.zoomName,
                            entryPointType: 'video',
                            uri: newJoinUrl,
                            password: zoomPassword,
                        }]
                };
            }
        }
        else if (googleMeet) {
            newConferenceId = (0, uuid_1.v4)();
            conferenceName = constants_1.googleMeetName;
            conferenceType = 'hangoutsMeet';
            conferenceData = {
                type: conferenceType,
                conferenceId: newConferenceId,
                name: conferenceName,
                requestId: newRequestId,
                createRequest: true,
            };
        }
        await (0, exports.upsertConferenceInDb)(client, typeof newConferenceId === 'number' ? `${newConferenceId}` : newConferenceId, userId, calendarId, zoomMeet ? constants_2.zoomResourceName : constants_1.googleResourceName, newRequestId, meetingTypeString, undefined, undefined, zoomMeet ? constants_2.zoomName : constants_1.googleMeetName, notes, conferenceData?.entryPoints, undefined, undefined, undefined, newJoinUrl, newStartUrl, zoomPrivateMeeting);
        return {
            newConferenceId,
            newJoinUrl,
            newStartUrl,
            newConferenceStatus,
            conferenceName,
            conferenceType,
            conferenceData,
        };
    }
    catch (e) {
        console.log(e, ' unable to create conference');
    }
};
exports.createConference = createConference;
const createNewEvent = async (startDate, endDate, userId, client, selectedCalendarId, categoryIds, title, allDay, recurringEndDate, frequency, interval, alarms, notes, location, isFollowUp, isPreEvent, isPostEvent, modifiable, anyoneCanAddSelf, guestsCanInviteOthers, guestsCanSeeOtherGuests, originalAllDay, timezone, taskId, taskType, followUpEventId, preEventId, postEventId, forEventId, zoomMeet, googleMeet, meetingTypeString, zoomPassword, zoomPrivateMeeting, attendees, conferenceId, maxAttendees, sendUpdates, status, summary, transparency, visibility, recurringEventId, iCalUID, htmlLink, colorId, originalTimezone, backgroundColor, foregroundColor, useDefaultAlarms, positiveImpactScore, negativeImpactScore, positiveImpactDayOfWeek, positiveImpactTime, negativeImpactDayOfWeek, negativeImpactTime, preferredDayOfWeek, preferredTime, isExternalMeeting, isExternalMeetingModifiable, isMeetingModifiable, isMeeting, dailyTaskList, weeklyTaskList, isBreak, preferredStartTimeRange, preferredEndTimeRange, copyAvailability, copyTimeBlocking, copyTimePreference, copyReminders, copyPriorityLevel, copyModifiable, copyCategories, copyIsBreak, timeBlocking, userModifiedAvailability, userModifiedTimeBlocking, userModifiedTimePreference, userModifiedReminders, userModifiedPriorityLevel, userModifiedCategories, userModifiedModifiable, userModifiedIsBreak, hardDeadline, softDeadline, copyIsMeeting, copyIsExternalMeeting, userModifiedIsMeeting, userModifiedIsExternalMeeting, duration, copyDuration, userModifiedDuration, method, unlink, byWeekDay, priority) => {
    try {
        /**
        2. check if any calendars are active
        3. create in global primary calendar
        if none create in any calendar available
        finally try create local calendar if none available
        and save to calendar db
         */
        let calendar = {};
        if (selectedCalendarId?.length > 0) {
            calendar = await (0, exports.getCalendarInDb)(client, userId, selectedCalendarId);
        }
        if (!selectedCalendarId) {
            // global primary if none selectedCalendarId
            calendar = await (0, exports.getCalendarInDb)(client, userId, undefined, true);
        }
        // if no  calendar get google calendar
        if (!selectedCalendarId && !calendar && constants_1.googleResourceName) {
            calendar = await (0, exports.getCalendarInDb)(client, userId, undefined, undefined, constants_1.googleResourceName);
        }
        if (!(calendar?.id) && !selectedCalendarId) {
            // get any if none set to globalPrimary and no selectedCalendarId
            calendar = await (0, exports.getCalendarInDb)(client, userId);
        }
        if (calendar?.resource === constants_1.googleResourceName) {
            const modifiedAttendees = attendees?.map(a => ({
                additionalGuests: a?.additionalGuests,
                displayName: a?.name,
                email: a?.emails?.[0]?.value,
                id: a?.id,
            }));
            let conferenceData = null;
            // create conferece
            if (modifiedAttendees?.length > 0) {
                const { 
                // newConferenceId,
                // newJoinUrl,
                // newStartUrl,
                // newConferenceStatus,
                // conferenceName,
                // conferenceType,
                conferenceData: conferenceData1, } = await (0, exports.createConference)(startDate, endDate, client, calendar?.id, zoomMeet, googleMeet, userId, meetingTypeString, modifiedAttendees, undefined, summary, taskType, notes, zoomPassword, zoomPrivateMeeting);
                conferenceData = conferenceData1;
            }
            console.log(hardDeadline, softDeadline, ' hardDeadline, softDeadline inside createNewEvent');
            const eventId = await (0, exports.createNewEventInGoogle)(startDate, endDate, userId, client, calendar, conferenceData, modifiedAttendees, title, allDay, recurringEndDate, frequency, interval, notes, location, isFollowUp, isPreEvent, isPostEvent, modifiable, anyoneCanAddSelf, guestsCanInviteOthers, guestsCanSeeOtherGuests, originalAllDay, alarms, timezone, taskId, taskType, followUpEventId, preEventId, postEventId, forEventId, maxAttendees, sendUpdates, status, transparency, visibility, iCalUID, backgroundColor, foregroundColor, colorId, originalTimezone, useDefaultAlarms, positiveImpactScore, negativeImpactScore, positiveImpactDayOfWeek, positiveImpactTime, negativeImpactDayOfWeek, negativeImpactTime, preferredDayOfWeek, preferredTime, isExternalMeeting, isExternalMeetingModifiable, isMeetingModifiable, isMeeting, dailyTaskList, weeklyTaskList, isBreak, preferredStartTimeRange, preferredEndTimeRange, copyAvailability, copyTimeBlocking, copyTimePreference, copyReminders, copyPriorityLevel, copyModifiable, copyCategories, copyIsBreak, timeBlocking, userModifiedAvailability, userModifiedTimeBlocking, userModifiedTimePreference, userModifiedReminders, userModifiedPriorityLevel, userModifiedCategories, userModifiedModifiable, userModifiedIsBreak, hardDeadline, softDeadline, copyIsMeeting, copyIsExternalMeeting, userModifiedIsMeeting, userModifiedIsExternalMeeting, duration, copyDuration, userModifiedDuration, method, unlink, byWeekDay, priority);
            console.log(eventId, ' eventId inside createNewEvent after createNewEventInGoogle');
            // save attendees
            if (attendees?.length > 0) {
                const attendeePromises = attendees?.map(a => {
                    return (0, AttendeeHelper_1.upsertAttendeesInDb)(client, (0, uuid_1.v4)(), userId, eventId, a?.emails, a?.name, a?.id, a?.phoneNumbers, a?.imAddresses, a?.additionalGuests, a?.optional, a?.resource);
                });
                await Promise.all(attendeePromises);
            }
            if (categoryIds?.length > 0) {
                // create category_event connections
                const categoryPromises = categoryIds.map(i => (0, CategoryHelper_1.upsertCategoryEventConnection)(client, userId, i, eventId));
                await Promise.all(categoryPromises);
            }
            return eventId;
        }
    }
    catch (e) {
        console.log(e, ' unable to create new event');
    }
};
exports.createNewEvent = createNewEvent;
const deleteEventForTask = async (eventId, client) => {
    try {
        const { data } = (await client.mutate({
            mutation: deleteEventById_1.default,
            variables: {
                id: eventId,
            },
            // refetchQueries: [
            //   listAllEvents, // DocumentNode object parsed with gql
            //   'listAllEvents' // Query name
            // ],
            update(cache, { data }) {
                const deletedEvent = data?.delete_Event_by_pk;
                const normalizedId = cache.identify({ id: deletedEvent.id, __typename: deletedEvent.__typename });
                cache.evict({ id: normalizedId });
                cache.gc();
            }
        }));
        console.log(data, ' delete event');
        return data?.delete_Event_by_pk?.id;
    }
    catch (e) {
        console.log(e, 'error for deleteEvent');
    }
};
exports.deleteEventForTask = deleteEventForTask;
/**
end
 */
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlckNyZWF0ZUNhbGVuZGFySGVscGVyLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiVXNlckNyZWF0ZUNhbGVuZGFySGVscGVyLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUlBLCtCQUFpQztBQUVqQyxpQ0FBNkI7QUFFN0IsZ0RBQXdDO0FBRXhDLGdGQUU4QztBQXlCOUMsMERBS21DO0FBU25DLG1EQUc0QjtBQUM1QixtRUFHb0M7QUFPcEMsaUVBRXFDO0FBQ3JDLDBFQUU4QztBQVE5QywwRUFBMkU7QUFFM0UsMkNBQTBFO0FBQzFFLHNGQUE2RDtBQUM3RCx3R0FBK0U7QUFDL0Usb0ZBQTJEO0FBQzNELHNHQUE2RTtBQUM3RSxzSUFBc0c7QUFDdEcsa0ZBQXlEO0FBQ3pELHNHQUE2RTtBQUM3RSwwRkFBaUU7QUFDakUsc0ZBQTZEO0FBTTdELHVEQUE2QztBQXlCdEMsTUFBTSw4Q0FBOEMsR0FBRyxLQUFLLEVBQ2pFLE1BQW1CLEVBQ25CLE1BQTJDLEVBQzNDLEVBQUU7SUFDRixJQUFJLENBQUM7UUFFSCxPQUFPLENBQUMsR0FBRyxDQUFDLE1BQU0sRUFBRSxvREFBb0QsQ0FBQyxDQUFBO1FBQ3pFLElBQUksQ0FBQyxDQUFDLE1BQU0sRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLEVBQUUsQ0FBQztZQUMxQixPQUFNO1FBQ1IsQ0FBQztRQUVELE1BQU0sSUFBSSxHQUFHLENBQUMsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUEwQztZQUN4RSxLQUFLLEVBQUUsaUNBQXVCO1lBQzlCLFNBQVMsRUFBRTtnQkFDVCxRQUFRLEVBQUUsTUFBTSxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUM7YUFDakM7U0FDRixDQUFDLENBQUMsRUFBRSxJQUFJLEVBQUUsY0FBYyxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxDQUFDLENBQUM7WUFDbkMsRUFBRSxFQUFFLENBQUMsQ0FBQyxRQUFR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QUNILE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxFQUFFLGVBQWUsQ0FBQyxDQUFBO1FBQ2xDLE9BQU8sSUFBSSxFQUFFLGtCQUFrQixFQUFFLEVBQUUsQ0FBQTtJQUNyQyxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHVCQUF1QixDQUFDLENBQUE7SUFDekMsQ0FBQztBQUNILENBQUMsQ0FBQTtBQTFCWSxRQUFBLGtCQUFrQixzQkEwQjlCO0FBR0Q7O0dBRUciLCJzb3VyY2VzQ29udGVudCI6WyJcblxuXG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnXG5pbXBvcnQgeyB2NCBhcyB1dWlkIH0gZnJvbSAndXVpZCdcbmltcG9ydCB7IERpc3BhdGNoLCBTZXRTdGF0ZUFjdGlvbiB9IGZyb20gJ3JlYWN0J1xuaW1wb3J0IHsgUlJ1bGUgfSBmcm9tICdycnVsZSdcblxuaW1wb3J0IHsgZGF5anMsIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJ1xuXG5pbXBvcnQge1xuICBjcmVhdGVHb29nbGVFdmVudCxcbn0gZnJvbSAnQGxpYi9jYWxlbmRhckxpYi9nb29nbGVDYWxlbmRhckhlbHBlcidcblxuaW1wb3J0IHsgcGFsZXR0ZSB9IGZyb20gJ0BsaWIvdGhlbWUvdGhlbWUnXG5cbmltcG9ydCB7XG4gIENhbGVuZGFyVHlwZSxcbn0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ2FsZW5kYXJUeXBlJ1xuaW1wb3J0IHtcbiAgVGltZSxcbiAgQnVmZmVyVGltZVR5cGUsXG59IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0V2ZW50VHlwZSdcbmltcG9ydCB7XG4gIENhbGVuZGFySW50ZWdyYXRpb25UeXBlLFxufSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYWxlbmRhcl9JbnRlZ3JhdGlvblR5cGUnXG5pbXBvcnQge1xuICBFdmVudFR5cGUsXG4gIFJlY3VycmVuY2VSdWxlVHlwZSxcbiAgQXR0YWNobWVudFR5cGUsXG4gIExvY2F0aW9uVHlwZSxcbiAgQ3JlYXRvclR5cGUsXG4gIE9yZ2FuaXplclR5cGUsXG4gIEV4dGVuZGVkUHJvcGVydGllc1R5cGUsXG4gIFNvdXJjZVR5cGUsXG4gIExpbmtUeXBlLFxufSBmcm9tICdAbGliL2RhdGFUeXBlcy9FdmVudFR5cGUnXG5pbXBvcnQge1xuICBnb29nbGVNZWV0TmFtZSxcbiAgZ29vZ2xlUmVzb3VyY2VOYW1lLFxuICBsb2NhbENhbGVuZGFyTmFtZSxcbiAgbG9jYWxDYWxlbmRhclJlc291cmNlLFxufSBmcm9tICdAbGliL2NhbGVuZGFyTGliL2NvbnN0YW50cydcbmltcG9ydCB7XG4gIEdvb2dsZUF0dGVuZGVlVHlwZSxcbiAgQ29uZmVyZW5jZURhdGFUeXBlLFxuICBHb29nbGVSZW1pbmRlclR5cGUsXG4gIFNlbmRVcGRhdGVzVHlwZSxcbiAgVHJhbnNwYXJlbmN5VHlwZSxcbiAgVmlzaWJpbGl0eVR5cGUsXG59IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvdHlwZXMnXG5pbXBvcnQge1xuICB6b29tTmFtZSxcbiAgem9vbVJlc291cmNlTmFtZSxcbn0gZnJvbSAnQGxpYi96b29tL2NvbnN0YW50cydcbmltcG9ydCB7XG4gIHpvb21BdmFpbGFibGUsXG4gIGNyZWF0ZVpvb21NZWV0aW5nLFxufSBmcm9tICdAbGliL3pvb20vem9vbU1lZXRpbmdIZWxwZXInXG5pbXBvcnQge1xuICBhY2Nlc3NSb2xlLFxuICBQZXJzb24sXG4gIFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlLFxuICBUYWdUeXBlLFxufSBmcm9tICdAbGliL0NhbGVuZGFyL3R5cGVzJ1xuaW1wb3J0IHtcbiAgdXBzZXJ0Q2F0ZWdvcnlFdmVudENvbm5lY3Rpb24sXG59IGZyb20gJ0BsaWIvQ2F0ZWdvcnkvQ2F0ZWdvcnlIZWxwZXInXG5pbXBvcnQge1xuICBjcmVhdGVSZW1pbmRlckZvckV2ZW50LFxufSBmcm9tICdAbGliL0NhbGVuZGFyL1JlbWluZGVyL1JlbWluZGVySGVscGVyJ1xuaW1wb3J0IHtcbiAgUGFyYW1ldGVyVHlwZSxcbiAgRW50cnlQb2ludFR5cGUsXG4gIEFwcFR5cGUsXG4gIENvbmZlcmVuY2VOYW1lVHlwZSxcbiAgQ29uZmVyZW5jZVR5cGUsXG59IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NvbmZlcmVuY2VUeXBlJ1xuaW1wb3J0IHsgdXBzZXJ0QXR0ZW5kZWVzSW5EYiB9IGZyb20gJ0BsaWIvQ2FsZW5kYXIvQXR0ZW5kZWUvQXR0ZW5kZWVIZWxwZXInXG5cbmltcG9ydCB7IEFwb2xsb0NsaWVudCwgTm9ybWFsaXplZENhY2hlT2JqZWN0LCBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5pbXBvcnQgZ2V0Q2FsZW5kYXJCeUlkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRDYWxlbmRhckJ5SWQnXG5pbXBvcnQgZ2V0R2xvYmFsUHJpbWFyeUNhbGVuZGFyIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRHbG9iYWxQcmltYXJ5Q2FsZW5kYXInXG5pbXBvcnQgZ2V0QW55Q2FsZW5kYXIgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldEFueUNhbGVuZGFyJ1xuaW1wb3J0IGdldENhbGVuZGFyV2l0aFJlc291cmNlIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRDYWxlbmRhcldpdGhSZXNvdXJjZSdcbmltcG9ydCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZSBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2VBbmROYW1lJ1xuaW1wb3J0IGxpc3RBbGxFdmVudHMgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2xpc3RBbGxFdmVudHMnXG5pbXBvcnQgbGlzdENhdGVnb3JpZXNGb3JFdmVudHMgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2xpc3RDYXRlZ29yaWVzRm9yRXZlbnRzJ1xuaW1wb3J0IGdldENvbmZlcmVuY2VCeUlkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRDb25mZXJlbmNlQnlJZCdcbmltcG9ydCBkZWxldGVFdmVudEJ5SWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2RlbGV0ZUV2ZW50QnlJZCdcbmltcG9ydCB7IENhdGVnb3J5RXZlbnRUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvQ2F0ZWdvcnlfRXZlbnRUeXBlJ1xuaW1wb3J0IHtcbiAgdHlwZSBFdmVudCBhcyBDYWxlbmRhckV2ZW50LFxuICB0eXBlIHN0cmluZ09yRGF0ZSxcbn0gZnJvbSAncmVhY3QtYmlnLWNhbGVuZGFyJ1xuaW1wb3J0IHsgRGF5IH0gZnJvbSAnQGxpYi9TY2hlZHVsZS9jb25zdGFudHMnXG5cbmV4cG9ydCB0eXBlIENhbGVuZGFyRXZlbnRQcm8gPSBDYWxlbmRhckV2ZW50ICYge1xuICAvLyBldmVudElkI2NhbGVuZGFySWRcbiAgaWQ6IHN0cmluZyxcbiAgY2FsZW5kYXJJZDogc3RyaW5nLFxuICBldmVudElkOiBzdHJpbmcsXG4gIGNvbG9yPzogc3RyaW5nLFxuICBub3Rlcz86IHN0cmluZyxcbiAgdGFnczogVGFnVHlwZVtdLFxuICB1bmxpbms6IGJvb2xlYW4sXG4gIG1vZGlmaWFibGU6IGJvb2xlYW4sXG4gIHByaW9yaXR5OiBudW1iZXIsXG4gIHJlY3VycmluZ0VuZERhdGU/OiBzdHJpbmcsXG4gIGZyZXF1ZW5jeT86IFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlLFxuICBpbnRlcnZhbD86IHN0cmluZyxcbn1cblxuXG5leHBvcnQgaW50ZXJmYWNlIE5ld0V2ZW50VGltZSB7XG4gIGhvdXI6IG51bWJlcjtcbiAgbWludXRlczogbnVtYmVyO1xuICBkYXRlPzogc3RyaW5nO1xufVxuXG5leHBvcnQgY29uc3QgcmVmb3JtYXRUb0NhbGVuZGFyRXZlbnRzVUlXZWJGb3JDYWxlbmRhckZyb21EYiA9IGFzeW5jIChcbiAgZXZlbnRzOiBFdmVudFR5cGVbXSxcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbikgPT4ge1xuICB0cnkge1xuXG4gICAgY29uc29sZS5sb2coZXZlbnRzLCAnIGV2ZW50cyBpbnNpZGUgcmVmb3JtYXRUb0V2ZW50c1VJRm9yQ2FsZW5kYXJGcm9tRGInKVxuICAgIGlmICghKGV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJldHVyblxuICAgIH1cblxuICAgIGNvbnN0IHRhZ3MgPSAoYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQ2F0ZWdvcnlfRXZlbnQ6IENhdGVnb3J5RXZlbnRUeXBlW10gfT4oe1xuICAgICAgcXVlcnk6IGxpc3RDYXRlZ29yaWVzRm9yRXZlbnRzLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGV2ZW50SWRzOiBldmVudHM/Lm1hcChlID0+IGUuaWQpLFxuICAgICAgfSxcbiAgICB9KSk/LmRhdGE/LkNhdGVnb3J5X0V2ZW50Py5tYXAoYyA9PiAoe1xuICAgICAgaWQ6IGMuQ2F0ZWdvcnkuaWQsXG4gICAgICBuYW1lOiBjLkNhdGVnb3J5Lm5hbWUsXG4gICAgICBjb2xvcjogYy5DYXRlZ29yeS5jb2xvcixcbiAgICAgIGV2ZW50SWQ6IGMuZXZlbnRJZCxcbiAgICB9KSlcblxuXG4gICAgY29uc3QgZXZlbnRzTW9kaWZpZWQ6IENhbGVuZGFyRXZlbnRQcm9bXSA9IGV2ZW50cz8ubWFwKChlKSA9PiB7XG5cbiAgICAgIGNvbnN0IHRhZ3NGb3JFdmVudCA9IHRhZ3M/LmZpbHRlcih0ID0+ICh0LmV2ZW50SWQgPT09IGUuaWQpKVxuICAgICAgY29uc3QgdGFnc01vZGlmaWVkID0gdGFnc0ZvckV2ZW50Py5tYXAodCA9PiAoe1xuICAgICAgICBpZDogdC5pZCxcbiAgICAgICAgbmFtZTogdC5uYW1lLFxuICAgICAgICBjb2xvcjogdC5jb2xvclxuICAgICAgfSkpXG5cbiAgICAgIHJldHVybiB7XG4gICAgICAgIGlkOiBlPy5pZCxcbiAgICAgICAgc3RhcnQ6IGRheWpzLnR6KGU/LnN0YXJ0RGF0ZS5zbGljZSgwLCAxOSksIGU/LnRpbWV6b25lIHx8IGRheWpzLnR6Lmd1ZXNzKCkpLnRvRGF0ZSgpLFxuICAgICAgICBlbmQ6IGRheWpzLnR6KGU/LmVuZERhdGUuc2xpY2UoMCwgMTkpLCBlPy50aW1lem9uZSB8fCBkYXlqcy50ei5ndWVzcygpKS50b0RhdGUoKSxcbiAgICAgICAgdGl0bGU6IGU/LnRpdGxlIHx8IGU/LnN1bW1hcnksXG4gICAgICAgIGFsbERheTogZT8uYWxsRGF5LFxuICAgICAgICBjYWxlbmRhcklkOiBlPy5jYWxlbmRhcklkLFxuICAgICAgICBldmVudElkOiBlPy5ldmVudElkLFxuICAgICAgICBjb2xvcjogdGFnc0ZvckV2ZW50Py5bMF0/LmNvbG9yIHx8IGU/LmJhY2tncm91bmRDb2xvcixcbiAgICAgICAgbm90ZXM6IGU/Lm5vdGVzLFxuICAgICAgICB0YWdzOiB0YWdzTW9kaWZpZWQsXG4gICAgICAgIHVubGluazogZT8udW5saW5rLFxuICAgICAgICBtb2RpZmlhYmxlOiBlPy5tb2RpZmlhYmxlLFxuICAgICAgICBwcmlvcml0eTogZT8ucHJpb3JpdHksXG4gICAgICAgIHJlY3VycmluZ0VuZERhdGU6IGU/LnJlY3VycmVuY2VSdWxlPy5lbmREYXRlLFxuICAgICAgICBmcmVxdWVuY3k6IGU/LnJlY3VycmVuY2VSdWxlPy5mcmVxdWVuY3kgYXMgUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG4gICAgICAgIGludGVydmFsOiBgJHtlPy5yZWN1cnJlbmNlUnVsZT8uaW50ZXJ2YWx9YCxcbiAgICAgIH1cblxuICAgIH0pXG5cbiAgICByZXR1cm4gZXZlbnRzTW9kaWZpZWRcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlZm9ybWF0IHRvIGNhbGVuZGFyIGV2ZW50cyBVSSBmb3Igd2ViJylcbiAgfVxufVxuXG5cbmV4cG9ydCBjb25zdCBzZXRDdXJyZW50RXZlbnRzRm9yQ2FsZW5kYXJXZWIgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBzZXRDYWxlbmRhckV2ZW50czogRGlzcGF0Y2g8U2V0U3RhdGVBY3Rpb248Q2FsZW5kYXJFdmVudFByb1tdPj4sXG5cbikgPT4ge1xuICB0cnkge1xuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyB1c2VySWQgaW5zaWRlIHNldEN1cnJlbnRFdmVudHNGb3JDYWxlbmRhcicpXG4gICAgICByZXR1cm5cbiAgICB9XG4gICAgaWYgKCFjbGllbnQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyBjbGllbnQgaW5zaWRlIHNldEN1cnJlbnRFdmVudHNGb3JDYWxlbmRhcicpXG4gICAgICByZXR1cm5cbiAgICB9XG5cbiAgICBjb25zdCBldmVudHNGcm9tRGIgPSBhd2FpdCBnZXRDdXJyZW50RXZlbnRzKGNsaWVudCwgdXNlcklkKVxuICAgIGNvbnNvbGUubG9nKGV2ZW50c0Zyb21EYiwgJyBldmVudHNGcm9tRGIgaW5zaWRlIHNldEN1cnJlbnRFdmVudHNGb3JDYWxlbmRhcicpXG5cbiAgICBjb25zdCBldmVudHMgPSBhd2FpdCByZWZvcm1hdFRvQ2FsZW5kYXJFdmVudHNVSVdlYkZvckNhbGVuZGFyRnJvbURiKGV2ZW50c0Zyb21EYiwgY2xpZW50KVxuXG4gICAgc2V0Q2FsZW5kYXJFdmVudHMoZXZlbnRzKVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gc2V0IGN1cnJlbnQgZm9yIGNhbGVuZGFyIHdlYicpXG4gIH1cbn1cblxuLy8gZG8gaXQgYnkgbGltaXQgb3BlcmF0b3JcbmV4cG9ydCBjb25zdCBnZXRDdXJyZW50RXZlbnRzID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZyxcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50LnF1ZXJ5PHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH0+KHtcbiAgICAgIHF1ZXJ5OiBsaXN0QWxsRXZlbnRzLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgc3RhcnQ6IGRheWpzKCkuc3VidHJhY3QoMiwgJ3knKS5mb3JtYXQoKSxcbiAgICAgICAgZW5kOiBkYXlqcygpLmFkZCgyLCAneScpLmZvcm1hdCgpLFxuICAgICAgfSxcbiAgICAgIGZldGNoUG9saWN5OiAnbm8tY2FjaGUnXG4gICAgfSlcblxuICAgIHJldHVybiBkYXRhPy5FdmVudFxuXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgY3VycmVudCBldmVudHMnKVxuICB9XG59XG5cblxuLyoqXG57XG4gIGlkPzogc3RyaW5nO1xuICBzdGFydDogc3RyaW5nOyBmb3JtYXQgLS0+IFlZLU1NLUREIEhIOk1NOnNzXG4gIGVuZDogc3RyaW5nO1xuICB0aXRsZTogc3RyaW5nO1xuICBzdW1tYXJ5Pzogc3RyaW5nO1xuICBjb2xvcj86IHN0cmluZztcbn1cbiAqL1xuXG5cblxuZXhwb3J0IGNvbnN0IGdldENhbGVuZGFySW5EYiA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ/OiBzdHJpbmcsXG4gIGdsb2JhbFByaW1hcnk/OiBib29sZWFuLFxuICByZXNvdXJjZT86IHN0cmluZyxcbikgPT4ge1xuICB0cnkge1xuICAgIGlmIChjYWxlbmRhcklkKSB7XG4gICAgICBjb25zdCBjYWxlbmRhciA9IChhd2FpdCBjbGllbnQucXVlcnk8eyBDYWxlbmRhcl9ieV9wazogQ2FsZW5kYXJUeXBlIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldENhbGVuZGFyQnlJZCxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgaWQ6IGNhbGVuZGFySWQsXG4gICAgICAgIH0sXG4gICAgICB9KSkuZGF0YT8uQ2FsZW5kYXJfYnlfcGtcbiAgICAgIHJldHVybiBjYWxlbmRhclxuICAgIH0gZWxzZSBpZiAoZ2xvYmFsUHJpbWFyeSAmJiAhY2FsZW5kYXJJZCkge1xuICAgICAgY29uc3QgY2FsZW5kYXIgPSAoYXdhaXQgY2xpZW50LnF1ZXJ5PHsgQ2FsZW5kYXI6IENhbGVuZGFyVHlwZVtdIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldEdsb2JhbFByaW1hcnlDYWxlbmRhcixcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICB9LFxuICAgICAgfSkpLmRhdGE/LkNhbGVuZGFyPy5bMF1cbiAgICAgIHJldHVybiBjYWxlbmRhclxuICAgIH0gZWxzZSBpZiAoIWdsb2JhbFByaW1hcnkgJiYgIWNhbGVuZGFySWQgJiYgIXJlc291cmNlKSB7XG4gICAgICBjb25zdCBjYWxlbmRhciA9IChhd2FpdCBjbGllbnQucXVlcnk8eyBDYWxlbmRhcjogQ2FsZW5kYXJUeXBlW10gfT4oe1xuICAgICAgICBxdWVyeTogZ2V0QW55Q2FsZW5kYXIsXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgfSxcbiAgICAgIH0pKS5kYXRhPy5DYWxlbmRhcj8uWzBdXG4gICAgICByZXR1cm4gY2FsZW5kYXJcbiAgICB9IGVsc2UgaWYgKCFnbG9iYWxQcmltYXJ5ICYmICFjYWxlbmRhcklkICYmIHJlc291cmNlPy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBjYWxlbmRhciA9IChhd2FpdCBjbGllbnQucXVlcnk8eyBDYWxlbmRhcjogQ2FsZW5kYXJUeXBlW10gfT4oe1xuICAgICAgICBxdWVyeTogZ2V0Q2FsZW5kYXJXaXRoUmVzb3VyY2UsXG4gICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICByZXNvdXJjZSxcbiAgICAgICAgfSxcbiAgICAgIH0pKS5kYXRhPy5DYWxlbmRhcj8uWzBdXG4gICAgICByZXR1cm4gY2FsZW5kYXJcbiAgICB9XG5cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBjYWxlbmRhciBmcm9tIGNvbGxlY3Rpb24nKVxuICB9XG59XG5cbmV4cG9ydCBjb25zdCB1cHNlcnRMb2NhbENhbGVuZGFyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBpZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGl0bGU6IHN0cmluZyxcbiAgYmFja2dyb3VuZENvbG9yOiBzdHJpbmcsXG4gIGFjY2Vzc0xldmVsPzogYWNjZXNzUm9sZSxcbiAgcmVzb3VyY2U/OiBzdHJpbmcsXG4gIGdsb2JhbFByaW1hcnk/OiBib29sZWFuLFxuICBmb3JlZ3JvdW5kQ29sb3I/OiBzdHJpbmcsXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjYWxlbmRhclZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICBpZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpdGxlLFxuICAgICAgYmFja2dyb3VuZENvbG9yLFxuICAgICAgYWNjZXNzTGV2ZWwsXG4gICAgICByZXNvdXJjZSxcbiAgICAgIGdsb2JhbFByaW1hcnksXG4gICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICB9XG5cbiAgICAvLyBBU1NVTVBUSU9OOiBBIGN1c3RvbSBQRyBmdW5jdGlvbiAndXBzZXJ0Q2FsZW5kYXInIGhhbmRsZXMgdGhlIHVwc2VydCBsb2dpYy5cbiAgICAvLyBEeW5hbWljIHVwZGF0ZV9jb2x1bW5zIGFyZSBub3cgcGFydCBvZiB0aGUgUEcgZnVuY3Rpb24ncyBPTiBDT05GTElDVCBjbGF1c2UuXG4gICAgY29uc3QgdXBzZXJ0Q2FsZW5kYXJNdXRhdGlvbiA9IGdxbGBcbiAgICBtdXRhdGlvbiBVcHNlcnRDYWxlbmRhcigkY2FsZW5kYXI6IENhbGVuZGFySW5wdXQhKSB7ICMgQXNzdW1pbmcgQ2FsZW5kYXJJbnB1dCBpcyB0aGUgdHlwZSBmb3IgYSBzaW5nbGUgY2FsZW5kYXJcbiAgICAgIHVwc2VydENhbGVuZGFyKGlucHV0OiB7IGNhbGVuZGFyOiAkY2FsZW5kYXIgfSkgeyAjIFN0YW5kYXJkIFBvc3RHcmFwaGlsZSBtdXRhdGlvbiBpbnB1dCBwYXR0ZXJuXG4gICAgICAgIGNhbGVuZGFyIHsgIyBBc3N1bWluZyB0aGUgcGF5bG9hZCByZXR1cm5zIHRoZSBjYWxlbmRhclxuICAgICAgICAgIGlkXG4gICAgICAgICAgIyBJbmNsdWRlIG90aGVyIGZpZWxkcyBhcyBuZWVkZWQgZnJvbSBDYWxlbmRhclR5cGUgaWYgdGhleSBhcmUgcmV0dXJuZWRcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cbiAgYFxuICAgIC8vIFRoZSB0eXBlIGZvciBjbGllbnQubXV0YXRlIGFuZCB2YXJpYWJsZSBwcmVwYXJhdGlvbiB3aWxsIG5lZWQgdG8gYWRqdXN0LlxuICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGNsaWVudC5tdXRhdGU8eyB1cHNlcnRDYWxlbmRhcjogeyBjYWxlbmRhcjogeyBpZDogc3RyaW5nIH0gfSB9Pih7IC8vIEFkanVzdCByZXR1cm4gdHlwZVxuICAgICAgbXV0YXRpb246IHVwc2VydENhbGVuZGFyTXV0YXRpb24sXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgY2FsZW5kYXI6IGNhbGVuZGFyVmFsdWVUb1Vwc2VydCwgLy8gUGFzcyB0aGUgc2luZ2xlIG9iamVjdFxuICAgICAgfSxcbiAgICB9KVxuXG4gICAgcmV0dXJuIHJlc3VsdC5kYXRhPy51cHNlcnRDYWxlbmRhcj8uY2FsZW5kYXIgLy8gQWRqdXN0IGFjY2VzcyB0byByZXR1cm5lZCBkYXRhXG5cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHNhdmUgbG9jYWwgY2FsZW5kYXInKVxuICB9XG59XG5cblxuZXhwb3J0IGNvbnN0IGdldFJydWxlRnJlcSA9IChcbiAgZnJlcTogUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGVcbikgPT4ge1xuICBzd2l0Y2ggKGZyZXEpIHtcbiAgICBjYXNlICdkYWlseSc6XG4gICAgICByZXR1cm4gUlJ1bGUuREFJTFlcbiAgICBjYXNlICd3ZWVrbHknOlxuICAgICAgcmV0dXJuIFJSdWxlLldFRUtMWVxuICAgIGNhc2UgJ21vbnRobHknOlxuICAgICAgcmV0dXJuIFJSdWxlLk1PTlRITFlcbiAgICBjYXNlICd5ZWFybHknOlxuICAgICAgcmV0dXJuIFJSdWxlLllFQVJMWVxuICB9XG59XG5cbmV4cG9ydCBjb25zdCBhdG9taWNVcHNlcnRFdmVudEluRGIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGlkOiBzdHJpbmcsXG4gIGV2ZW50SWQ6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgZW5kRGF0ZT86IHN0cmluZyxcbiAgY3JlYXRlZERhdGU/OiBzdHJpbmcsXG4gIGRlbGV0ZWQ/OiBib29sZWFuLFxuICBwcmlvcml0eT86IG51bWJlcixcbiAgaXNGb2xsb3dVcD86IGJvb2xlYW4sXG4gIGlzUHJlRXZlbnQ/OiBib29sZWFuLFxuICBpc1Bvc3RFdmVudD86IGJvb2xlYW4sXG4gIG1vZGlmaWFibGU/OiBib29sZWFuLFxuICBhbnlvbmVDYW5BZGRTZWxmPzogYm9vbGVhbixcbiAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzPzogYm9vbGVhbixcbiAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHM/OiBib29sZWFuLFxuICBvcmlnaW5hbFN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgb3JpZ2luYWxBbGxEYXk/OiBib29sZWFuLFxuICB1cGRhdGVkQXQ/OiBzdHJpbmcsXG4gIGNhbGVuZGFySWQ/OiBzdHJpbmcsXG4gIHRpdGxlPzogc3RyaW5nLFxuICBhbGxEYXk/OiBib29sZWFuLFxuICByZWN1cnJlbmNlUnVsZT86IFJlY3VycmVuY2VSdWxlVHlwZSxcbiAgbG9jYXRpb24/OiBMb2NhdGlvblR5cGUsXG4gIG5vdGVzPzogc3RyaW5nLFxuICBhdHRhY2htZW50cz86IEF0dGFjaG1lbnRUeXBlW10sXG4gIGxpbmtzPzogTGlua1R5cGVbXSxcbiAgLy8gYWxhcm1zPzogYWxhcm1zLFxuICB0aW1lem9uZT86IHN0cmluZyxcbiAgdGFza0lkPzogc3RyaW5nLFxuICB0YXNrVHlwZT86IHN0cmluZyxcbiAgZm9sbG93VXBFdmVudElkPzogc3RyaW5nLFxuICBwcmVFdmVudElkPzogc3RyaW5nLFxuICBwb3N0RXZlbnRJZD86IHN0cmluZyxcbiAgZm9yRXZlbnRJZD86IHN0cmluZyxcbiAgY29uZmVyZW5jZUlkPzogc3RyaW5nLFxuICBtYXhBdHRlbmRlZXM/OiBudW1iZXIsXG4gIHNlbmRVcGRhdGVzPzogU2VuZFVwZGF0ZXNUeXBlLFxuICBzdGF0dXM/OiBzdHJpbmcsXG4gIHN1bW1hcnk/OiBzdHJpbmcsXG4gIHRyYW5zcGFyZW5jeT86IFRyYW5zcGFyZW5jeVR5cGUsXG4gIHZpc2liaWxpdHk/OiBWaXNpYmlsaXR5VHlwZSxcbiAgcmVjdXJyaW5nRXZlbnRJZD86IHN0cmluZyxcbiAgaUNhbFVJRD86IHN0cmluZyxcbiAgaHRtbExpbms/OiBzdHJpbmcsXG4gIGNvbG9ySWQ/OiBzdHJpbmcsXG4gIGNyZWF0b3I/OiBDcmVhdG9yVHlwZSxcbiAgb3JnYW5pemVyPzogT3JnYW5pemVyVHlwZSxcbiAgZW5kVGltZVVuc3BlY2lmaWVkPzogYm9vbGVhbixcbiAgcmVjdXJyZW5jZT86IHN0cmluZ1tdLFxuICBvcmlnaW5hbFRpbWV6b25lPzogc3RyaW5nLFxuICBhdHRlbmRlZXNPbWl0dGVkPzogYm9vbGVhbixcbiAgZXh0ZW5kZWRQcm9wZXJ0aWVzPzogRXh0ZW5kZWRQcm9wZXJ0aWVzVHlwZSxcbiAgaGFuZ291dExpbms/OiBzdHJpbmcsXG4gIGd1ZXN0c0Nhbk1vZGlmeT86IGJvb2xlYW4sXG4gIGxvY2tlZD86IGJvb2xlYW4sXG4gIHNvdXJjZT86IFNvdXJjZVR5cGUsXG4gIGV2ZW50VHlwZT86IHN0cmluZyxcbiAgcHJpdmF0ZUNvcHk/OiBib29sZWFuLFxuICBiYWNrZ3JvdW5kQ29sb3I/OiBzdHJpbmcsXG4gIGZvcmVncm91bmRDb2xvcj86IHN0cmluZyxcbiAgdXNlRGVmYXVsdEFsYXJtcz86IGJvb2xlYW4sXG4gIHBvc2l0aXZlSW1wYWN0U2NvcmU/OiBudW1iZXIsXG4gIG5lZ2F0aXZlSW1wYWN0U2NvcmU/OiBudW1iZXIsXG4gIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrPzogbnVtYmVyLFxuICBwb3NpdGl2ZUltcGFjdFRpbWU/OiBUaW1lLFxuICBuZWdhdGl2ZUltcGFjdERheU9mV2Vlaz86IG51bWJlcixcbiAgbmVnYXRpdmVJbXBhY3RUaW1lPzogVGltZSxcbiAgcHJlZmVycmVkRGF5T2ZXZWVrPzogbnVtYmVyLFxuICBwcmVmZXJyZWRUaW1lPzogVGltZSxcbiAgaXNFeHRlcm5hbE1lZXRpbmc/OiBib29sZWFuLFxuICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGU/OiBib29sZWFuLFxuICBpc01lZXRpbmdNb2RpZmlhYmxlPzogYm9vbGVhbixcbiAgaXNNZWV0aW5nPzogYm9vbGVhbixcbiAgZGFpbHlUYXNrTGlzdD86IGJvb2xlYW4sXG4gIHdlZWtseVRhc2tMaXN0PzogYm9vbGVhbixcbiAgaXNCcmVhaz86IGJvb2xlYW4sXG4gIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPzogVGltZSxcbiAgcHJlZmVycmVkRW5kVGltZVJhbmdlPzogVGltZSxcbiAgY29weUF2YWlsYWJpbGl0eT86IGJvb2xlYW4sXG4gIGNvcHlUaW1lQmxvY2tpbmc/OiBib29sZWFuLFxuICBjb3B5VGltZVByZWZlcmVuY2U/OiBib29sZWFuLFxuICBjb3B5UmVtaW5kZXJzPzogYm9vbGVhbixcbiAgY29weVByaW9yaXR5TGV2ZWw/OiBib29sZWFuLFxuICBjb3B5TW9kaWZpYWJsZT86IGJvb2xlYW4sXG4gIGNvcHlDYXRlZ29yaWVzPzogYm9vbGVhbixcbiAgY29weUlzQnJlYWs/OiBib29sZWFuLFxuICB0aW1lQmxvY2tpbmc/OiBCdWZmZXJUaW1lVHlwZSxcbiAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5PzogYm9vbGVhbixcbiAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nPzogYm9vbGVhbixcbiAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2U/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRSZW1pbmRlcnM/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsPzogYm9vbGVhbixcbiAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllcz86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZE1vZGlmaWFibGU/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRJc0JyZWFrPzogYm9vbGVhbixcbiAgaGFyZERlYWRsaW5lPzogc3RyaW5nLFxuICBzb2Z0RGVhZGxpbmU/OiBzdHJpbmcsXG4gIGNvcHlJc01lZXRpbmc/OiBib29sZWFuLFxuICBjb3B5SXNFeHRlcm5hbE1lZXRpbmc/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRJc01lZXRpbmc/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZz86IGJvb2xlYW4sXG4gIGR1cmF0aW9uPzogbnVtYmVyLFxuICBjb3B5RHVyYXRpb24/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWREdXJhdGlvbj86IGJvb2xlYW4sXG4gIG1ldGhvZD86ICdjcmVhdGUnIHwgJ3VwZGF0ZScsXG4gIHVubGluaz86IGJvb2xlYW4sXG4gIGJ5V2Vla0RheT86IERheVtdLFxuICBsb2NhbFN5bmNlZD86IGJvb2xlYW4sXG4gIGNvcHlDb2xvcj86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZENvbG9yPzogYm9vbGVhbixcbiAgbWVldGluZ0lkPzogc3RyaW5nLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coaGFyZERlYWRsaW5lLCBzb2Z0RGVhZGxpbmUsICcgaGFyZERlYWRsaW5lLCBzb2Z0RGVhZGxpbmUgaW5zaWRlIGF0b21pY1Vwc2VydEV2ZW50SW5EYicpXG4gICAgLy8gQVNTVU1QVElPTjogQSBjdXN0b20gUEcgZnVuY3Rpb24gJ3Vwc2VydEV2ZW50JyBoYW5kbGVzIHRoZSBjb21wbGV4IHVwc2VydCBsb2dpYy5cbiAgICAvLyBUaGUgZXh0ZW5zaXZlIGR5bmFtaWMgdXBkYXRlX2NvbHVtbnMgbGlzdCBpcyBub3cgcGFydCBvZiB0aGUgUEcgZnVuY3Rpb24ncyBPTiBDT05GTElDVCBjbGF1c2UuXG4gICAgLy8gVGhlIGlucHV0IHR5cGUgd2lsbCBiZSBzb21ldGhpbmcgbGlrZSBFdmVudElucHV0IVxuICAgIGNvbnN0IHVwc2VydEV2ZW50TXV0YXRpb24gPSBncWxgXG4gICAgICBtdXRhdGlvbiBVcHNlcnRFdmVudCgkZXZlbnQ6IEV2ZW50SW5wdXQhKSB7ICMgQXNzdW1pbmcgRXZlbnRJbnB1dCBpcyB0aGUgdHlwZSBmb3IgYSBzaW5nbGUgZXZlbnRcbiAgICAgICAgdXBzZXJ0RXZlbnQoaW5wdXQ6IHsgZXZlbnQ6ICRldmVudCB9KSB7ICMgU3RhbmRhcmQgUG9zdEdyYXBoaWxlIG11dGF0aW9uIGlucHV0IHBhdHRlcm5cbiAgICAgICAgICBldmVudCB7ICMgQXNzdW1pbmcgdGhlIHBheWxvYWQgcmV0dXJucyB0aGUgZXZlbnRcbiAgICAgICAgICAgICMgSXQncyBjcnVjaWFsIHRoYXQgdGhlICdyZXR1cm5pbmcnIGZpZWxkcyBoZXJlIG1hdGNoIHdoYXQgUG9zdEdyYXBoaWxlIGFjdHVhbGx5IHJldHVybnNcbiAgICAgICAgICAgICMgYmFzZWQgb24gdGhlIFBHIGZ1bmN0aW9uJ3MgUkVUVVJOSU5HIGNsYXVzZSBhbmQgUG9zdEdyYXBoaWxlJ3Mgc2NoZW1hIGdlbmVyYXRpb24uXG4gICAgICAgICAgICAjIFRoaXMgaXMgYSBiZXN0IGd1ZXNzIGJhc2VkIG9uIHRoZSBvcmlnaW5hbCBIYXN1cmEgcXVlcnkuXG4gICAgICAgICAgICAjIE1hbnkgb2YgdGhlc2UgbWlnaHQgYmUgb2JqZWN0cyBvciBuZWVkIGRpZmZlcmVudCBjYXNpbmcgKGNhbWVsQ2FzZSkuXG4gICAgICAgICAgICBpZFxuICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgIHRhc2tJZFxuICAgICAgICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgICAgICAgICAgICAgIGlzRm9sbG93VXBcbiAgICAgICAgICAgICAgICAgIGlzUHJlRXZlbnRcbiAgICAgICAgICAgICAgICAgIGlzUG9zdEV2ZW50XG4gICAgICAgICAgICAgICAgICBwcmVFdmVudElkXG4gICAgICAgICAgICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgZm9yRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgICAgICAgICAgIHN0YXR1c1xuICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgdGl0bGVcbiAgICAgICAgICAgICAgICAgIHRyYW5zcGFyZW5jeVxuICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgICAgcmVjdXJyaW5nRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgaUNhbFVJRFxuICAgICAgICAgICAgICAgICAgaHRtbExpbmtcbiAgICAgICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgICAgIGNyZWF0b3JcbiAgICAgICAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgICAgICAgZW5kVGltZVVuc3BlY2lmaWVkXG4gICAgICAgICAgICAgICAgICBleHRlbmRlZFByb3BlcnRpZXNcbiAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rXG4gICAgICAgICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgICAgICAgICAgIGxvY2tlZFxuICAgICAgICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICAgICAgICBldmVudFR5cGVcbiAgICAgICAgICAgICAgICAgIHByaXZhdGVDb3B5XG4gICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdEFsYXJtc1xuICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICBjYWxlbmRhcklkXG4gICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWtcbiAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFRpbWVcbiAgICAgICAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgIGlzTWVldGluZ1xuICAgICAgICAgICAgICAgICAgZGFpbHlUYXNrTGlzdFxuICAgICAgICAgICAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgIGlzQnJlYWtcbiAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlXG4gICAgICAgICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICAgICAgICAgICAgY29weUlzQnJlYWtcbiAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsXG4gICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzXG4gICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrXG4gICAgICAgICAgICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgICAgICAgICAgIHNvZnREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgY29weUlzTWVldGluZ1xuICAgICAgICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgY29weUR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWREdXJhdGlvblxuICAgICAgICAgICAgICAgICAgbWV0aG9kXG4gICAgICAgICAgICAgICAgICB1bmxpbmtcbiAgICAgICAgICAgICAgICAgIGNvcHlDb2xvclxuICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQ29sb3JcbiAgICAgICAgICAgICAgICAgIGJ5V2Vla0RheVxuICAgICAgICAgICAgICAgICAgbG9jYWxTeW5jZWRcbiAgICAgICAgICAgICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICMgYWZmZWN0ZWRfcm93cyAjIFRoaXMgaXMgbm90IHN0YW5kYXJkIGluIFBvc3RHcmFwaGlsZSByZXR1cm4gdHlwZXMgZm9yIG11dGF0aW9ucyBsaWtlIHRoaXMuXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICMgVGhlIHVwc2VydGVkIGV2ZW50IGl0c2VsZiBpcyB0aGUgcHJpbWFyeSByZXR1cm4uXG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgICBgXG4gICAgbGV0IGV2ZW50OiBFdmVudFR5cGUgPSB7IC8vIFRoaXMgb2JqZWN0IGlzIHVzZWQgdG8gYnVpbGQgdGhlICd2YXJpYWJsZXMnIGZvciB0aGUgbXV0YXRpb24uXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgIC8vIEl0cyBzdHJ1Y3R1cmUgbXVzdCBtYXRjaCAnRXZlbnRJbnB1dCcgZXhwZWN0ZWQgYnkgUG9zdEdyYXBoaWxlLlxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAvLyBNYW55IGZpZWxkcyBtaWdodCBiZSBvcHRpb25hbCBvciBoYXZlIGRpZmZlcmVudCBjYXNpbmcgKGNhbWVsQ2FzZSkuXG4gICAgICBpZCxcbiAgICAgIGV2ZW50SWQsIC8vIEVuc3VyZSB0aGlzIGFuZCBvdGhlciBJRHMgYXJlIGNvcnJlY3RseSBtYXBwZWQgaWYgY2FzaW5nIGNoYW5nZXMgKGUuZy4gZXZlbnRJRClcbiAgICAgIG1lZXRpbmdJZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGUsXG4gICAgICBjcmVhdGVkRGF0ZSwgLy8gVXN1YWxseSBzZXQgYnkgREJcbiAgICAgIGRlbGV0ZWQsXG4gICAgICBwcmlvcml0eTogMSxcbiAgICAgIGlzRm9sbG93VXA6IGZhbHNlLFxuICAgICAgaXNQcmVFdmVudDogZmFsc2UsXG4gICAgICBpc1Bvc3RFdmVudDogZmFsc2UsXG4gICAgICBtb2RpZmlhYmxlOiBmYWxzZSxcbiAgICAgIGFueW9uZUNhbkFkZFNlbGY6IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiBmYWxzZSxcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiBmYWxzZSxcbiAgICAgIG9yaWdpbmFsU3RhcnREYXRlOiB1bmRlZmluZWQsXG4gICAgICBvcmlnaW5hbEFsbERheTogZmFsc2UsXG4gICAgICB1cGRhdGVkQXQ6IHVuZGVmaW5lZCwgLy8gVXN1YWxseSBzZXQgYnkgREJcbiAgICAgIGNhbGVuZGFySWQ6IHVuZGVmaW5lZCxcbiAgICAgIC8vIEVuc3VyZSBhbGwgZmllbGRzIGJlbG93IGFyZSBjb3JyZWN0bHkgY2FzZWQgKGNhbWVsQ2FzZSkgYW5kIG1hdGNoIEV2ZW50SW5wdXRcbiAgICB9XG4gICAgLyoqXG4gICAgICogXG4gICAgICAgIHByaW9yaXR5LFxuICAgICAgICBpc0ZvbGxvd1VwLFxuICAgICAgICBpc1ByZUV2ZW50LFxuICAgICAgICBpc1Bvc3RFdmVudCxcbiAgICAgICAgbW9kaWZpYWJsZSxcbiAgICAgICAgYW55b25lQ2FuQWRkU2VsZixcbiAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgICAgb3JpZ2luYWxTdGFydERhdGUsXG4gICAgICAgIG9yaWdpbmFsQWxsRGF5LFxuICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgIGNhbGVuZGFySWQsXG4gICAgICAgIHRpdGxlLFxuICAgICAgICBhbGxEYXksXG4gICAgICAgIHJlY3VycmVuY2VSdWxlLFxuICAgICAgICBsb2NhdGlvbixcbiAgICAgICAgbm90ZXMsXG4gICAgICAgIGF0dGFjaG1lbnRzLFxuICAgICAgICBsaW5rcyxcbiAgICAgICAgdGltZXpvbmUsXG4gICAgICAgIHRhc2tJZCxcbiAgICAgICAgdGFza1R5cGUsXG4gICAgICAgIGZvbGxvd1VwRXZlbnRJZCxcbiAgICAgICAgcHJlRXZlbnRJZCxcbiAgICAgICAgcG9zdEV2ZW50SWQsXG4gICAgICAgIGZvckV2ZW50SWQsXG4gICAgICAgIGNvbmZlcmVuY2VJZCxcbiAgICAgICAgbWF4QXR0ZW5kZWVzLFxuICAgICAgICBzZW5kVXBkYXRlcyxcbiAgICAgICAgc3RhdHVzLFxuICAgICAgICBzdW1tYXJ5LFxuICAgICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICAgIHZpc2liaWxpdHksXG4gICAgICAgIHJlY3VycmluZ0V2ZW50SWQsXG4gICAgICAgIGlDYWxVSUQsXG4gICAgICAgIGh0bWxMaW5rLFxuICAgICAgICBjb2xvcklkLFxuICAgICAgICBjcmVhdG9yLFxuICAgICAgICBvcmdhbml6ZXIsXG4gICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZCxcbiAgICAgICAgcmVjdXJyZW5jZSxcbiAgICAgICAgb3JpZ2luYWxUaW1lem9uZSxcbiAgICAgICAgYXR0ZW5kZWVzT21pdHRlZCxcbiAgICAgICAgaGFuZ291dExpbmssXG4gICAgICAgIGd1ZXN0c0Nhbk1vZGlmeSxcbiAgICAgICAgbG9ja2VkLFxuICAgICAgICBzb3VyY2UsXG4gICAgICAgIGV2ZW50VHlwZSxcbiAgICAgICAgcHJpdmF0ZUNvcHksXG4gICAgICAgIGJhY2tncm91bmRDb2xvcixcbiAgICAgICAgZm9yZWdyb3VuZENvbG9yLFxuICAgICAgICB1c2VEZWZhdWx0QWxhcm1zLFxuICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlLFxuICAgICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgcG9zaXRpdmVJbXBhY3RUaW1lLFxuICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lLFxuICAgICAgICBwcmVmZXJyZWREYXlPZldlZWssXG4gICAgICAgIHByZWZlcnJlZFRpbWUsXG4gICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUsXG4gICAgICAgIGlzTWVldGluZ01vZGlmaWFibGUsXG4gICAgICAgIGlzTWVldGluZyxcbiAgICAgICAgZGFpbHlUYXNrTGlzdCxcbiAgICAgICAgd2Vla2x5VGFza0xpc3QsXG4gICAgICAgIGlzQnJlYWssXG4gICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlLFxuICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2UsXG4gICAgICAgIGNvcHlBdmFpbGFiaWxpdHksXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmcsXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZSxcbiAgICAgICAgY29weVJlbWluZGVycyxcbiAgICAgICAgY29weVByaW9yaXR5TGV2ZWwsXG4gICAgICAgIGNvcHlNb2RpZmlhYmxlLFxuICAgICAgICBjb3B5Q2F0ZWdvcmllcyxcbiAgICAgICAgY29weUlzQnJlYWssXG4gICAgICAgIHRpbWVCbG9ja2luZyxcbiAgICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5LFxuICAgICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcsXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlLFxuICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnMsXG4gICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWwsXG4gICAgICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXMsXG4gICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGUsXG4gICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWssXG4gICAgICAgIGhhcmREZWFkbGluZSxcbiAgICAgICAgc29mdERlYWRsaW5lLFxuICAgICAgICBjb3B5SXNNZWV0aW5nLFxuICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZyxcbiAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgIGR1cmF0aW9uLFxuICAgICAgICBjb3B5RHVyYXRpb24sXG4gICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uLFxuICAgICAgICBtZXRob2QsXG4gICAgICAgIHVubGluayxcbiAgICAgICAgY29weUNvbG9yLFxuICAgICAgICB1c2VyTW9kaWZpZWRDb2xvcixcbiAgICAgICAgYnlXZWVrRGF5LFxuICAgICAgICBsb2NhbFN5bmNlZCxcbiAgICAgKi9cblxuICAgIGlmIChwcmlvcml0eSkge1xuICAgICAgZXZlbnQucHJpb3JpdHkgPSBwcmlvcml0eVxuICAgIH1cblxuICAgIGlmIChpc0ZvbGxvd1VwICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmlzRm9sbG93VXAgPSBpc0ZvbGxvd1VwXG4gICAgfVxuXG4gICAgaWYgKGlzUHJlRXZlbnQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuaXNQcmVFdmVudCA9IGlzUHJlRXZlbnRcbiAgICB9XG5cbiAgICBpZiAoaXNQb3N0RXZlbnQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuaXNQb3N0RXZlbnQgPSBpc1Bvc3RFdmVudFxuICAgIH1cblxuICAgIGlmIChtb2RpZmlhYmxlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50Lm1vZGlmaWFibGUgPSBtb2RpZmlhYmxlXG4gICAgfVxuXG4gICAgaWYgKGFueW9uZUNhbkFkZFNlbGYgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuYW55b25lQ2FuQWRkU2VsZiA9IGFueW9uZUNhbkFkZFNlbGZcbiAgICB9XG5cbiAgICBpZiAoZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50Lmd1ZXN0c0Nhbkludml0ZU90aGVycyA9IGd1ZXN0c0Nhbkludml0ZU90aGVyc1xuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyA9IGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgfVxuXG4gICAgaWYgKG9yaWdpbmFsU3RhcnREYXRlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50Lm9yaWdpbmFsU3RhcnREYXRlID0gb3JpZ2luYWxTdGFydERhdGVcbiAgICB9XG5cbiAgICBpZiAob3JpZ2luYWxBbGxEYXkgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQub3JpZ2luYWxBbGxEYXkgPSBvcmlnaW5hbEFsbERheVxuICAgIH1cblxuICAgIGlmICh1cGRhdGVkQXQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudXBkYXRlZEF0ID0gdXBkYXRlZEF0XG4gICAgfVxuXG4gICAgaWYgKGNhbGVuZGFySWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuY2FsZW5kYXJJZCA9IGNhbGVuZGFySWRcbiAgICB9XG5cbiAgICBpZiAodGl0bGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudGl0bGUgPSB0aXRsZVxuICAgIH1cblxuICAgIGlmIChhbGxEYXkgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuYWxsRGF5ID0gYWxsRGF5XG4gICAgfVxuXG4gICAgaWYgKHJlY3VycmVuY2VSdWxlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnJlY3VycmVuY2VSdWxlID0gcmVjdXJyZW5jZVJ1bGVcbiAgICB9XG5cbiAgICBpZiAobG9jYXRpb24gIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQubG9jYXRpb24gPSBsb2NhdGlvblxuICAgIH1cblxuICAgIGlmIChub3RlcyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5ub3RlcyA9IG5vdGVzXG4gICAgfVxuXG4gICAgaWYgKGF0dGFjaG1lbnRzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmF0dGFjaG1lbnRzID0gYXR0YWNobWVudHNcbiAgICB9XG5cbiAgICBpZiAobGlua3MgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQubGlua3MgPSBsaW5rc1xuICAgIH1cblxuICAgIGlmICh0aW1lem9uZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC50aW1lem9uZSA9IHRpbWV6b25lXG4gICAgfVxuXG4gICAgaWYgKHRhc2tJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC50YXNrSWQgPSB0YXNrSWRcbiAgICB9XG5cbiAgICBpZiAodGFza1R5cGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudGFza1R5cGUgPSB0YXNrVHlwZVxuICAgIH1cblxuICAgIGlmIChmb2xsb3dVcEV2ZW50SWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuZm9sbG93VXBFdmVudElkID0gZm9sbG93VXBFdmVudElkXG4gICAgfVxuXG4gICAgaWYgKHByZUV2ZW50SWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQucHJlRXZlbnRJZCA9IHByZUV2ZW50SWRcbiAgICB9XG5cbiAgICBpZiAocG9zdEV2ZW50SWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQucG9zdEV2ZW50SWQgPSBwb3N0RXZlbnRJZFxuICAgIH1cblxuICAgIGlmIChmb3JFdmVudElkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmZvckV2ZW50SWQgPSBmb3JFdmVudElkXG4gICAgfVxuXG4gICAgaWYgKGNvbmZlcmVuY2VJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5jb25mZXJlbmNlSWQgPSBjb25mZXJlbmNlSWRcbiAgICB9XG5cbiAgICBpZiAobWF4QXR0ZW5kZWVzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50Lm1heEF0dGVuZGVlcyA9IG1heEF0dGVuZGVlc1xuICAgIH1cblxuICAgIGlmIChzZW5kVXBkYXRlcyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5zZW5kVXBkYXRlcyA9IHNlbmRVcGRhdGVzXG4gICAgfVxuXG4gICAgaWYgKHN0YXR1cyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5zdGF0dXMgPSBzdGF0dXNcbiAgICB9XG5cbiAgICBpZiAoc3VtbWFyeSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5zdW1tYXJ5ID0gc3VtbWFyeVxuICAgIH1cblxuICAgIGlmICh0cmFuc3BhcmVuY3kgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudHJhbnNwYXJlbmN5ID0gdHJhbnNwYXJlbmN5XG4gICAgfVxuXG4gICAgaWYgKHZpc2liaWxpdHkgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudmlzaWJpbGl0eSA9IHZpc2liaWxpdHlcbiAgICB9XG5cbiAgICBpZiAocmVjdXJyaW5nRXZlbnRJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5yZWN1cnJpbmdFdmVudElkID0gcmVjdXJyaW5nRXZlbnRJZFxuICAgIH1cblxuICAgIGlmIChpQ2FsVUlEICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmlDYWxVSUQgPSBpQ2FsVUlEXG4gICAgfVxuXG4gICAgaWYgKGh0bWxMaW5rICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50Lmh0bWxMaW5rID0gaHRtbExpbmtcbiAgICB9XG5cbiAgICBpZiAoY29sb3JJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5jb2xvcklkID0gY29sb3JJZFxuICAgIH1cblxuICAgIGlmIChjcmVhdG9yICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmNyZWF0b3IgPSBjcmVhdG9yXG4gICAgfVxuXG4gICAgaWYgKG9yZ2FuaXplciAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5vcmdhbml6ZXIgPSBvcmdhbml6ZXJcbiAgICB9XG5cbiAgICBpZiAoZW5kVGltZVVuc3BlY2lmaWVkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmVuZFRpbWVVbnNwZWNpZmllZCA9IGVuZFRpbWVVbnNwZWNpZmllZFxuICAgIH1cblxuICAgIGlmIChyZWN1cnJlbmNlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnJlY3VycmVuY2UgPSByZWN1cnJlbmNlXG4gICAgfVxuXG4gICAgaWYgKG9yaWdpbmFsVGltZXpvbmUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQub3JpZ2luYWxUaW1lem9uZSA9IG9yaWdpbmFsVGltZXpvbmVcbiAgICB9XG5cbiAgICBpZiAoYXR0ZW5kZWVzT21pdHRlZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5hdHRlbmRlZXNPbWl0dGVkID0gYXR0ZW5kZWVzT21pdHRlZFxuICAgIH1cblxuICAgIGlmIChoYW5nb3V0TGluayAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5oYW5nb3V0TGluayA9IGhhbmdvdXRMaW5rXG4gICAgfVxuXG4gICAgaWYgKGd1ZXN0c0Nhbk1vZGlmeSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5ndWVzdHNDYW5Nb2RpZnkgPSBndWVzdHNDYW5Nb2RpZnlcbiAgICB9XG5cbiAgICBpZiAobG9ja2VkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmxvY2tlZCA9IGxvY2tlZFxuICAgIH1cblxuICAgIGlmIChzb3VyY2UgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuc291cmNlID0gc291cmNlXG4gICAgfVxuXG4gICAgaWYgKGV2ZW50VHlwZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5ldmVudFR5cGUgPSBldmVudFR5cGVcbiAgICB9XG5cbiAgICBpZiAocHJpdmF0ZUNvcHkgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQucHJpdmF0ZUNvcHkgPSBwcml2YXRlQ29weVxuICAgIH1cblxuICAgIGlmIChndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyA9IGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgfVxuXG4gICAgaWYgKGJhY2tncm91bmRDb2xvciAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5iYWNrZ3JvdW5kQ29sb3IgPSBiYWNrZ3JvdW5kQ29sb3JcbiAgICB9XG5cbiAgICBpZiAoZm9yZWdyb3VuZENvbG9yICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmZvcmVncm91bmRDb2xvciA9IGZvcmVncm91bmRDb2xvclxuICAgIH1cblxuICAgIGlmICh1c2VEZWZhdWx0QWxhcm1zICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnVzZURlZmF1bHRBbGFybXMgPSB1c2VEZWZhdWx0QWxhcm1zXG4gICAgfVxuXG4gICAgaWYgKHBvc2l0aXZlSW1wYWN0U2NvcmUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQucG9zaXRpdmVJbXBhY3RTY29yZSA9IHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICB9XG5cbiAgICBpZiAobmVnYXRpdmVJbXBhY3RTY29yZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5uZWdhdGl2ZUltcGFjdFNjb3JlID0gbmVnYXRpdmVJbXBhY3RTY29yZVxuICAgIH1cblxuICAgIGlmIChwb3NpdGl2ZUltcGFjdERheU9mV2VlayAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5wb3NpdGl2ZUltcGFjdERheU9mV2VlayA9IHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgfVxuXG4gICAgaWYgKG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50Lm5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrID0gbmVnYXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICB9XG5cbiAgICBpZiAocG9zaXRpdmVJbXBhY3RUaW1lICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnBvc2l0aXZlSW1wYWN0VGltZSA9IHBvc2l0aXZlSW1wYWN0VGltZVxuICAgIH1cblxuICAgIGlmIChuZWdhdGl2ZUltcGFjdFRpbWUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQubmVnYXRpdmVJbXBhY3RUaW1lID0gbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgfVxuXG4gICAgaWYgKHByZWZlcnJlZERheU9mV2VlayAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5wcmVmZXJyZWREYXlPZldlZWsgPSBwcmVmZXJyZWREYXlPZldlZWtcbiAgICB9XG5cbiAgICBpZiAocHJlZmVycmVkVGltZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5wcmVmZXJyZWRUaW1lID0gcHJlZmVycmVkVGltZVxuICAgIH1cblxuICAgIGlmIChpc0V4dGVybmFsTWVldGluZyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5pc0V4dGVybmFsTWVldGluZyA9IGlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgfVxuXG4gICAgaWYgKGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5pc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGUgPSBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICB9XG5cbiAgICBpZiAoaXNNZWV0aW5nTW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5pc01lZXRpbmdNb2RpZmlhYmxlID0gaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgIH1cblxuICAgIGlmIChpc01lZXRpbmcgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuaXNNZWV0aW5nID0gaXNNZWV0aW5nXG4gICAgfVxuXG4gICAgaWYgKGRhaWx5VGFza0xpc3QgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuZGFpbHlUYXNrTGlzdCA9IGRhaWx5VGFza0xpc3RcbiAgICB9XG5cbiAgICBpZiAod2Vla2x5VGFza0xpc3QgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQud2Vla2x5VGFza0xpc3QgPSB3ZWVrbHlUYXNrTGlzdFxuICAgIH1cblxuICAgIGlmIChpc0JyZWFrICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmlzQnJlYWsgPSBpc0JyZWFrXG4gICAgfVxuXG4gICAgaWYgKHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnByZWZlcnJlZFN0YXJ0VGltZVJhbmdlID0gcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICB9XG5cbiAgICBpZiAocHJlZmVycmVkRW5kVGltZVJhbmdlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnByZWZlcnJlZEVuZFRpbWVSYW5nZSA9IHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgIH1cblxuICAgIGlmIChjb3B5QXZhaWxhYmlsaXR5ICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmNvcHlBdmFpbGFiaWxpdHkgPSBjb3B5QXZhaWxhYmlsaXR5XG4gICAgfVxuXG4gICAgaWYgKGNvcHlUaW1lQmxvY2tpbmcgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuY29weVRpbWVCbG9ja2luZyA9IGNvcHlUaW1lQmxvY2tpbmdcbiAgICB9XG5cbiAgICBpZiAoY29weVRpbWVQcmVmZXJlbmNlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmNvcHlUaW1lUHJlZmVyZW5jZSA9IGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgIH1cblxuICAgIGlmIChjb3B5UmVtaW5kZXJzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmNvcHlSZW1pbmRlcnMgPSBjb3B5UmVtaW5kZXJzXG4gICAgfVxuXG4gICAgaWYgKGNvcHlQcmlvcml0eUxldmVsICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmNvcHlQcmlvcml0eUxldmVsID0gY29weVByaW9yaXR5TGV2ZWxcbiAgICB9XG5cbiAgICBpZiAoY29weU1vZGlmaWFibGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuY29weU1vZGlmaWFibGUgPSBjb3B5TW9kaWZpYWJsZVxuICAgIH1cblxuICAgIGlmIChjb3B5Q2F0ZWdvcmllcyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5jb3B5Q2F0ZWdvcmllcyA9IGNvcHlDYXRlZ29yaWVzXG4gICAgfVxuXG4gICAgaWYgKGNvcHlJc0JyZWFrICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmNvcHlJc0JyZWFrID0gY29weUlzQnJlYWtcbiAgICB9XG5cbiAgICBpZiAodGltZUJsb2NraW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnRpbWVCbG9ja2luZyA9IHRpbWVCbG9ja2luZ1xuICAgIH1cblxuICAgIGlmICh1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHkgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5ID0gdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgfVxuXG4gICAgaWYgKHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC51c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmcgPSB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmdcbiAgICB9XG5cbiAgICBpZiAodXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UgPSB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgIH1cblxuICAgIGlmICh1c2VyTW9kaWZpZWRSZW1pbmRlcnMgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudXNlck1vZGlmaWVkUmVtaW5kZXJzID0gdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgfVxuXG4gICAgaWYgKHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWwgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbCA9IHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICB9XG5cbiAgICBpZiAodXNlck1vZGlmaWVkQ2F0ZWdvcmllcyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC51c2VyTW9kaWZpZWRDYXRlZ29yaWVzID0gdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgIH1cblxuICAgIGlmICh1c2VyTW9kaWZpZWRNb2RpZmlhYmxlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnVzZXJNb2RpZmllZE1vZGlmaWFibGUgPSB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgfVxuXG4gICAgaWYgKHVzZXJNb2RpZmllZElzQnJlYWsgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudXNlck1vZGlmaWVkSXNCcmVhayA9IHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICB9XG5cbiAgICBpZiAoaGFyZERlYWRsaW5lICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmhhcmREZWFkbGluZSA9IGhhcmREZWFkbGluZVxuICAgIH1cblxuICAgIGlmIChzb2Z0RGVhZGxpbmUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuc29mdERlYWRsaW5lID0gc29mdERlYWRsaW5lXG4gICAgfVxuXG4gICAgaWYgKGNvcHlJc01lZXRpbmcgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuY29weUlzTWVldGluZyA9IGNvcHlJc01lZXRpbmdcbiAgICB9XG5cbiAgICBpZiAoY29weUlzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmNvcHlJc0V4dGVybmFsTWVldGluZyA9IGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgIH1cblxuICAgIGlmICh1c2VyTW9kaWZpZWRJc01lZXRpbmcgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudXNlck1vZGlmaWVkSXNNZWV0aW5nID0gdXNlck1vZGlmaWVkSXNNZWV0aW5nXG4gICAgfVxuXG4gICAgaWYgKHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nID0gdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICB9XG5cbiAgICBpZiAoZHVyYXRpb24gIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuZHVyYXRpb24gPSBkdXJhdGlvblxuICAgIH1cblxuICAgIGlmIChjb3B5RHVyYXRpb24gIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuY29weUR1cmF0aW9uID0gY29weUR1cmF0aW9uXG4gICAgfVxuXG4gICAgaWYgKHVzZXJNb2RpZmllZER1cmF0aW9uICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LnVzZXJNb2RpZmllZER1cmF0aW9uID0gdXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICB9XG5cbiAgICBpZiAobWV0aG9kICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50Lm1ldGhvZCA9IG1ldGhvZFxuICAgIH1cblxuICAgIGlmICh1bmxpbmsgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudW5saW5rID0gdW5saW5rXG4gICAgfVxuXG4gICAgaWYgKGNvcHlDb2xvciAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5jb3B5Q29sb3IgPSBjb3B5Q29sb3JcbiAgICB9XG5cbiAgICBpZiAodXNlck1vZGlmaWVkQ29sb3IgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQudXNlck1vZGlmaWVkQ29sb3IgPSB1c2VyTW9kaWZpZWRDb2xvclxuICAgIH1cblxuICAgIGlmIChieVdlZWtEYXkgIT09IHVuZGVmaW5lZCkge1xuICAgICAgZXZlbnQuYnlXZWVrRGF5ID0gYnlXZWVrRGF5XG4gICAgfVxuXG4gICAgaWYgKGxvY2FsU3luY2VkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGV2ZW50LmxvY2FsU3luY2VkID0gbG9jYWxTeW5jZWRcbiAgICB9XG5cbiAgICBldmVudC5ldmVudElkID0gZXZlbnRJZFxuXG4gICAgaWYgKG1lZXRpbmdJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICBldmVudC5tZWV0aW5nSWQgPSBtZWV0aW5nSWRcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZyhldmVudCwgJyBldmVudCBpbnNpZGUgYXRvbWljVXBzZXJ0RXZlbnRJbkRiJylcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBldmVudDogZXZlbnQgLy8gUGFzcyB0aGUgc2luZ2xlIGV2ZW50IG9iamVjdCwgbWF0Y2hpbmcgdGhlICRldmVudDogRXZlbnRJbnB1dCEgaW4gdGhlIG11dGF0aW9uXG4gICAgfVxuXG4gICAgLy8gQWRqdXN0IHRoZSBnZW5lcmljIHR5cGUgZm9yIGNsaWVudC5tdXRhdGUgYmFzZWQgb24gdGhlIGFjdHVhbCBQb3N0R3JhcGhpbGUgbXV0YXRpb24gcGF5bG9hZFxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IHVwc2VydEV2ZW50OiB7IGV2ZW50OiBFdmVudFR5cGUgfSB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBzZXJ0RXZlbnRNdXRhdGlvbiwgLy8gVXNlIHRoZSByZW5hbWVkIG11dGF0aW9uIHZhcmlhYmxlXG4gICAgICB2YXJpYWJsZXMsXG4gICAgICAvLyByZWZldGNoUXVlcmllcyBtaWdodCBiZSBhIG1vcmUgcm9idXN0IHdheSB0byBoYW5kbGUgY2FjaGUgdXBkYXRlcyBpbml0aWFsbHlcbiAgICAgIC8vIHJlZmV0Y2hRdWVyaWVzOiBbXG4gICAgICAvLyAgIHsgcXVlcnk6IGxpc3RBbGxFdmVudHMsIHZhcmlhYmxlczogeyAvKiBhcHByb3ByaWF0ZSB2YXJpYWJsZXMgZm9yIGxpc3RBbGxFdmVudHMgKi8gfSB9XG4gICAgICAvLyBdLFxuICAgICAgdXBkYXRlKGNhY2hlLCB7IGRhdGEgfSkge1xuICAgICAgICBjb25zdCB1cHNlcnRlZEV2ZW50ID0gZGF0YT8udXBzZXJ0RXZlbnQ/LmV2ZW50O1xuICAgICAgICBpZiAodXBzZXJ0ZWRFdmVudCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKCd1cHNlcnRFdmVudCByZXN1bHQnLCB1cHNlcnRlZEV2ZW50KTtcblxuICAgICAgICAgIC8vIFRoZSBjYWNoZSB1cGRhdGUgbG9naWMgaGVyZSBpcyBoaWdobHkgc3BlY3VsYXRpdmUgYW5kIG5lZWRzIHZlcmlmaWNhdGlvbi5cbiAgICAgICAgICAvLyBJdCBhc3N1bWVzIGEgcm9vdCBmaWVsZCAnRXZlbnQnIGZvciBhIGxpc3QsIHdoaWNoIGlzIHVubGlrZWx5IHdpdGggUG9zdEdyYXBoaWxlLlxuICAgICAgICAgIC8vIEl0IHdvdWxkIG1vcmUgbGlrZWx5IGJlICdhbGxFdmVudHMnIG9yIGEgc2ltaWxhciBjb25uZWN0aW9uIGZpZWxkLlxuICAgICAgICAgIGNhY2hlLm1vZGlmeSh7XG4gICAgICAgICAgICBmaWVsZHM6IHtcbiAgICAgICAgICAgICAgLy8gVGhpcyBmaWVsZCBuYW1lICdFdmVudCcgaXMgbGlrZWx5IGluY29ycmVjdCBmb3IgUG9zdEdyYXBoaWxlLlxuICAgICAgICAgICAgICBFdmVudDogKGV4aXN0aW5nRXZlbnRzID0gW10sIHsgcmVhZEZpZWxkIH0pID0+IHsgLy8gUGxhY2Vob2xkZXIgZm9yIGV4aXN0aW5nIGNhY2hlIHVwZGF0ZSBsb2dpY1xuICAgICAgICAgICAgICAgIC8vIEF0dGVtcHQgdG8gZmluZCBhbmQgcmVwbGFjZSBvciBhZGQgdGhlIG5ldyBldmVudC5cbiAgICAgICAgICAgICAgICAvLyBUaGlzIHNpbXBsZSByZXBsYWNlbWVudCBtaWdodCBub3Qgd29yayB3ZWxsIHdpdGggcGFnaW5hdGlvbiBvciBjb21wbGV4IGxpc3Qgc3RydWN0dXJlcy5cbiAgICAgICAgICAgICAgICBjb25zdCBuZXdFdmVudFJlZiA9IGNhY2hlLndyaXRlRnJhZ21lbnQoe1xuICAgICAgICAgICAgICAgICAgZGF0YTogdXBzZXJ0ZWRFdmVudCxcbiAgICAgICAgICAgICAgICAgIGZyYWdtZW50OiBncWxgXG4gICAgICAgICAgICAgICAgICAgIGZyYWdtZW50IE5ld0V2ZW50IG9uIEV2ZW50IHsgIyBUeXBlIG5hbWUgJ0V2ZW50JyBzaG91bGQgYmUgY2hlY2tlZCBhZ2FpbnN0IFBvc3RHcmFwaGlsZSBzY2hlbWFcbiAgICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICAgIHN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICAgIGVuZERhdGVcbiAgICAgICAgICAgICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgICByZWN1cnJlbmNlXG4gICAgICAgICAgICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgICAgYXR0YWNobWVudHNcbiAgICAgICAgICAgICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgICAgdGFza0lkXG4gICAgICAgICAgICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgICAgICAgICAgICBwcmlvcml0eVxuICAgICAgICAgICAgICAgICAgICAgIGZvbGxvd1VwRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICAgIGlzRm9sbG93VXBcbiAgICAgICAgICAgICAgICAgICAgICBpc1ByZUV2ZW50XG4gICAgICAgICAgICAgICAgICAgICAgaXNQb3N0RXZlbnRcbiAgICAgICAgICAgICAgICAgICAgICBwcmVFdmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgcG9zdEV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgICAgZm9yRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICAgIGNvbmZlcmVuY2VJZFxuICAgICAgICAgICAgICAgICAgICAgIG1heEF0dGVuZGVlc1xuICAgICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICAgIGFueW9uZUNhbkFkZFNlbGZcbiAgICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0c1xuICAgICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsU3RhcnREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsQWxsRGF5XG4gICAgICAgICAgICAgICAgICAgICAgc3RhdHVzXG4gICAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICAgICAgICAgICAgaHRtbExpbmtcbiAgICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgICAgY3JlYXRvclxuICAgICAgICAgICAgICAgICAgICAgIG9yZ2FuaXplclxuICAgICAgICAgICAgICAgICAgICAgIGVuZFRpbWVVbnNwZWNpZmllZFxuICAgICAgICAgICAgICAgICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICAgICAgICAgICAgICAgIGhhbmdvdXRMaW5rXG4gICAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuTW9kaWZ5XG4gICAgICAgICAgICAgICAgICAgICAgbG9ja2VkXG4gICAgICAgICAgICAgICAgICAgICAgc291cmNlXG4gICAgICAgICAgICAgICAgICAgICAgZXZlbnRUeXBlXG4gICAgICAgICAgICAgICAgICAgICAgcHJpdmF0ZUNvcHlcbiAgICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICAgICAgICAgICAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWtcbiAgICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFRpbWVcbiAgICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0VGltZVxuICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFRpbWVcbiAgICAgICAgICAgICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICAgIGlzTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgICBpc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICBkYWlseVRhc2tMaXN0XG4gICAgICAgICAgICAgICAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgICAgICAgICAgICAgICBpc0JyZWFrXG4gICAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICAgICAgICAgIGNvcHlNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgICAgY29weUNhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNCcmVha1xuICAgICAgICAgICAgICAgICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICAgIHNvZnREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc01lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgICAgY29weUR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgICAgICAgICAgICB1bmxpbmtcbiAgICAgICAgICAgICAgICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICAgICAgICAgICAgICAgIGJ5V2Vla0RheVxuICAgICAgICAgICAgICAgICAgICAgIGxvY2FsU3luY2VkXG4gICAgICAgICAgICAgICAgICAgICAgdGltZUJsb2NraW5nXG4gICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICBgLFxuICAgICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV4aXN0aW5nRXZlbnRzPy5maWx0ZXIoKGU6IEV2ZW50VHlwZSkgPT4gKGU/LmlkICE9PSBkYXRhPy5pbnNlcnRfRXZlbnQ/LnJldHVybmluZz8uWzBdPy5pZCkpIHx8IFtdXG4gICAgICAgICAgICAgIGNvbnNvbGUubG9nKGZpbHRlcmVkRXZlbnRzLCAnIGZpbHRlcmVkRXZlbnRzIGluc2lkZSBhdG9taWNVcHNlcnRFdmVudEluRGInKVxuICAgICAgICAgICAgICBpZiAoZmlsdGVyZWRFdmVudHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gZmlsdGVyZWRFdmVudHMuY29uY2F0KFtuZXdFdmVudFJlZl0pXG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgcmV0dXJuIFtuZXdFdmVudFJlZl1cbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH0pXG4gICAgICB9XG4gICAgfSlcbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZT8uZGF0YT8uaW5zZXJ0X0V2ZW50Py5yZXR1cm5pbmc/LlswXSwgJyByZXNwb25zZT8uZGF0YT8uaW5zZXJ0X0V2ZW50Py5yZXR1cm5pbmc/LlswXSBpbnNpZGUgYXRvbWljZXVwc2VydGV2ZW50aW5kYicpXG4gICAgcmV0dXJuIHJlc3BvbnNlPy5kYXRhPy5pbnNlcnRfRXZlbnQ/LnJldHVybmluZz8uWzBdXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBzYXZlIGNhbGVuZGFyIGV2ZW50JylcbiAgfVxufVxuXG5leHBvcnQgY29uc3QgZ2V0UlJ1bGVEYXkgPSAodmFsdWU6IERheSB8IHVuZGVmaW5lZCkgPT4ge1xuICBzd2l0Y2ggKHZhbHVlKSB7XG4gICAgY2FzZSBEYXkuTU86XG4gICAgICByZXR1cm4gUlJ1bGUuTU9cbiAgICBjYXNlIERheS5UVTpcbiAgICAgIHJldHVybiBSUnVsZS5UVVxuICAgIGNhc2UgRGF5LldFOlxuICAgICAgcmV0dXJuIFJSdWxlLldFXG4gICAgY2FzZSBEYXkuVEg6XG4gICAgICByZXR1cm4gUlJ1bGUuVEhcbiAgICBjYXNlIERheS5GUjpcbiAgICAgIHJldHVybiBSUnVsZS5GUlxuICAgIGNhc2UgRGF5LlNBOlxuICAgICAgcmV0dXJuIFJSdWxlLlNBXG4gICAgY2FzZSBEYXkuU1U6XG4gICAgICByZXR1cm4gUlJ1bGUuU1VcbiAgICBkZWZhdWx0OlxuICAgICAgcmV0dXJuIHVuZGVmaW5lZFxuICB9XG59XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVOZXdFdmVudEluR29vZ2xlID0gYXN5bmMgKFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY2FsZW5kYXI6IENhbGVuZGFyVHlwZSxcbiAgY29uZmVyZW5jZURhdGE/OiBDb25mZXJlbmNlRGF0YVR5cGUsXG4gIGF0dGVuZGVlcz86IEdvb2dsZUF0dGVuZGVlVHlwZVtdLFxuICB0aXRsZT86IHN0cmluZyxcbiAgYWxsRGF5PzogYm9vbGVhbixcbiAgcmVjdXJyaW5nRW5kRGF0ZT86IHN0cmluZyxcbiAgZnJlcXVlbmN5PzogUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG4gIGludGVydmFsPzogbnVtYmVyLFxuICBub3Rlcz86IHN0cmluZyxcbiAgbG9jYXRpb24/OiBMb2NhdGlvblR5cGUsXG4gIGlzRm9sbG93VXA/OiBib29sZWFuLFxuICBpc1ByZUV2ZW50PzogYm9vbGVhbixcbiAgaXNQb3N0RXZlbnQ/OiBib29sZWFuLFxuICBtb2RpZmlhYmxlPzogYm9vbGVhbixcbiAgYW55b25lQ2FuQWRkU2VsZj86IGJvb2xlYW4sXG4gIGd1ZXN0c0Nhbkludml0ZU90aGVycz86IGJvb2xlYW4sXG4gIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzPzogYm9vbGVhbixcbiAgb3JpZ2luYWxBbGxEYXk/OiBib29sZWFuLFxuICBhbGFybXM/OiBzdHJpbmdbXSB8IG51bWJlcltdLFxuICB0aW1lem9uZT86IHN0cmluZyxcbiAgdGFza0lkPzogc3RyaW5nLFxuICB0YXNrVHlwZT86IHN0cmluZyxcbiAgZm9sbG93VXBFdmVudElkPzogc3RyaW5nLFxuICBwcmVFdmVudElkPzogc3RyaW5nLFxuICBwb3N0RXZlbnRJZD86IHN0cmluZyxcbiAgZm9yRXZlbnRJZD86IHN0cmluZyxcbiAgbWF4QXR0ZW5kZWVzPzogbnVtYmVyLFxuICBzZW5kVXBkYXRlcz86IFNlbmRVcGRhdGVzVHlwZSxcbiAgc3RhdHVzPzogc3RyaW5nLFxuICB0cmFuc3BhcmVuY3k/OiBUcmFuc3BhcmVuY3lUeXBlLFxuICB2aXNpYmlsaXR5PzogVmlzaWJpbGl0eVR5cGUsXG4gIGlDYWxVSUQ/OiBzdHJpbmcsXG4gIGJhY2tncm91bmRDb2xvcj86IHN0cmluZyxcbiAgZm9yZWdyb3VuZENvbG9yPzogc3RyaW5nLFxuICBjb2xvcklkPzogc3RyaW5nLFxuICBvcmlnaW5hbFRpbWV6b25lPzogc3RyaW5nLFxuICB1c2VEZWZhdWx0QWxhcm1zPzogYm9vbGVhbixcbiAgcG9zaXRpdmVJbXBhY3RTY29yZT86IG51bWJlcixcbiAgbmVnYXRpdmVJbXBhY3RTY29yZT86IG51bWJlcixcbiAgcG9zaXRpdmVJbXBhY3REYXlPZldlZWs/OiBudW1iZXIsXG4gIHBvc2l0aXZlSW1wYWN0VGltZT86IFRpbWUsXG4gIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrPzogbnVtYmVyLFxuICBuZWdhdGl2ZUltcGFjdFRpbWU/OiBUaW1lLFxuICBwcmVmZXJyZWREYXlPZldlZWs/OiBudW1iZXIsXG4gIHByZWZlcnJlZFRpbWU/OiBUaW1lLFxuICBpc0V4dGVybmFsTWVldGluZz86IGJvb2xlYW4sXG4gIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZT86IGJvb2xlYW4sXG4gIGlzTWVldGluZ01vZGlmaWFibGU/OiBib29sZWFuLFxuICBpc01lZXRpbmc/OiBib29sZWFuLFxuICBkYWlseVRhc2tMaXN0PzogYm9vbGVhbixcbiAgd2Vla2x5VGFza0xpc3Q/OiBib29sZWFuLFxuICBpc0JyZWFrPzogYm9vbGVhbixcbiAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U/OiBUaW1lLFxuICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U/OiBUaW1lLFxuICBjb3B5QXZhaWxhYmlsaXR5PzogYm9vbGVhbixcbiAgY29weVRpbWVCbG9ja2luZz86IGJvb2xlYW4sXG4gIGNvcHlUaW1lUHJlZmVyZW5jZT86IGJvb2xlYW4sXG4gIGNvcHlSZW1pbmRlcnM/OiBib29sZWFuLFxuICBjb3B5UHJpb3JpdHlMZXZlbD86IGJvb2xlYW4sXG4gIGNvcHlNb2RpZmlhYmxlPzogYm9vbGVhbixcbiAgY29weUNhdGVnb3JpZXM/OiBib29sZWFuLFxuICBjb3B5SXNCcmVhaz86IGJvb2xlYW4sXG4gIHRpbWVCbG9ja2luZz86IEJ1ZmZlclRpbWVUeXBlLFxuICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHk/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmc/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZT86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZFJlbWluZGVycz86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWw/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRDYXRlZ29yaWVzPzogYm9vbGVhbixcbiAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZT86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZElzQnJlYWs/OiBib29sZWFuLFxuICBoYXJkRGVhZGxpbmU/OiBzdHJpbmcsXG4gIHNvZnREZWFkbGluZT86IHN0cmluZyxcbiAgY29weUlzTWVldGluZz86IGJvb2xlYW4sXG4gIGNvcHlJc0V4dGVybmFsTWVldGluZz86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZElzTWVldGluZz86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nPzogYm9vbGVhbixcbiAgZHVyYXRpb24/OiBudW1iZXIsXG4gIGNvcHlEdXJhdGlvbj86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZER1cmF0aW9uPzogYm9vbGVhbixcbiAgbWV0aG9kPzogJ2NyZWF0ZScgfCAndXBkYXRlJyxcbiAgdW5saW5rPzogYm9vbGVhbixcbiAgYnlXZWVrRGF5PzogRGF5W10sXG4gIHByaW9yaXR5PzogbnVtYmVyLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coaGFyZERlYWRsaW5lLCBzb2Z0RGVhZGxpbmUsICcgaGFyZERlYWRsaW5lLCBzb2Z0RGVhZGxpbmUgaW5zaWRlIGNyZWF0ZU5ld0V2ZW50SW5Hb29nbGUnKVxuICAgIGxldCBydWxlOiBhbnkgPSB7fVxuXG4gICAgaWYgKChyZWN1cnJpbmdFbmREYXRlPy5sZW5ndGggPiAwKSAmJiBmcmVxdWVuY3kpIHtcbiAgICAgIHJ1bGUgPSBuZXcgUlJ1bGUoe1xuICAgICAgICBmcmVxOiBnZXRScnVsZUZyZXEoZnJlcXVlbmN5KSxcbiAgICAgICAgaW50ZXJ2YWwsXG4gICAgICAgIHVudGlsOiBkYXlqcyhyZWN1cnJpbmdFbmREYXRlKS50b0RhdGUoKSxcbiAgICAgICAgYnl3ZWVrZGF5OiBieVdlZWtEYXk/Lm1hcChpID0+IGdldFJSdWxlRGF5KGkpKVxuICAgICAgfSlcbiAgICB9XG5cbiAgICBsZXQgbW9kaWZpZWRBbGFybXM6IEdvb2dsZVJlbWluZGVyVHlwZSA9IG51bGxcblxuICAgIGlmICh0eXBlb2YgYWxhcm1zPy5bMF0gPT09ICdzdHJpbmcnKSB7XG4gICAgICBtb2RpZmllZEFsYXJtcyA9IHtcbiAgICAgICAgdXNlRGVmYXVsdDogZmFsc2UsIG92ZXJyaWRlczogYWxhcm1zLm1hcChpID0+ICh7XG4gICAgICAgICAgbWV0aG9kOiAnZW1haWwnLFxuICAgICAgICAgIG1pbnV0ZXM6IGRheWpzKHN0YXJ0RGF0ZSkuZGlmZihpLCAnbScpLFxuICAgICAgICB9KSlcbiAgICAgIH1cbiAgICB9IGVsc2UgaWYgKHR5cGVvZiBhbGFybXM/LlswXSA9PT0gJ251bWJlcicpIHtcbiAgICAgIG1vZGlmaWVkQWxhcm1zID0geyB1c2VEZWZhdWx0OiBmYWxzZSwgb3ZlcnJpZGVzOiBhbGFybXMubWFwKGkgPT4gKHsgbWV0aG9kOiAnZW1haWwnLCBtaW51dGVzOiBpIGFzIG51bWJlciB9KSkgfVxuICAgIH1cblxuICAgIGlmICh1c2VEZWZhdWx0QWxhcm1zKSB7XG4gICAgICBtb2RpZmllZEFsYXJtcyA9IHsgdXNlRGVmYXVsdDogdXNlRGVmYXVsdEFsYXJtcyB9XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2cobW9kaWZpZWRBbGFybXMsICcgbW9kaWZpZWRBbGFybXMgaW5zaWRlIGNyZWF0ZU5ld0V2ZW50SW5Hb29nbGUnKVxuXG4gICAgY29uc3QgZXZlbnRJZCA9IGF3YWl0IGNyZWF0ZUdvb2dsZUV2ZW50KFxuICAgICAgY2xpZW50LFxuICAgICAgdXNlcklkLFxuICAgICAgY2FsZW5kYXI/LmlkLFxuICAgICAgZW5kRGF0ZSxcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIG1heEF0dGVuZGVlcyxcbiAgICAgIHNlbmRVcGRhdGVzLFxuICAgICAgYW55b25lQ2FuQWRkU2VsZixcbiAgICAgIGF0dGVuZGVlcyxcbiAgICAgIGNvbmZlcmVuY2VEYXRhLFxuICAgICAgdGl0bGUsXG4gICAgICBub3RlcyxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgYWxsRGF5ICYmIGRheWpzKHN0YXJ0RGF0ZSkuZm9ybWF0KCdZWVlZLU1NLUREJyksXG4gICAgICBhbGxEYXkgJiYgKGVuZERhdGUgfHwgc3RhcnREYXRlKSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgIGZhbHNlLCAvLyBndWVzdHNDYW5Nb2RpZnlcbiAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgZnJlcXVlbmN5XG4gICAgICAmJiByZWN1cnJpbmdFbmREYXRlXG4gICAgICAmJiBpbnRlcnZhbFxuICAgICAgJiYgW3J1bGUudG9TdHJpbmcoKV0sXG4gICAgICBtb2RpZmllZEFsYXJtcyxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHN0YXR1cyxcbiAgICAgIHRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHksXG4gICAgICBpQ2FsVUlELFxuICAgICAgZmFsc2UsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBsb2NhdGlvbj8udGl0bGUsXG4gICAgKVxuXG4gICAgY29uc29sZS5sb2coZXZlbnRJZCwgJyBpbnNpZGUgY3JlYXRlTmV3RXZlbnRJbkdvb2dsZSBhZnRlciBjcmVhdGVHb29nbGVFdmVudCcpXG5cbiAgICBhd2FpdCBhdG9taWNVcHNlcnRFdmVudEluRGIoXG4gICAgICBjbGllbnQsXG4gICAgICBgJHtldmVudElkfSMke2NhbGVuZGFyPy5pZH1gLFxuICAgICAgZXZlbnRJZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZSkuZm9ybWF0KCksXG4gICAgICBkYXlqcyhlbmREYXRlKS5mb3JtYXQoKSxcbiAgICAgIGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGZhbHNlLFxuICAgICAgcHJpb3JpdHkgfHwgMSxcbiAgICAgIGlzRm9sbG93VXAgPz8gZmFsc2UsXG4gICAgICBpc1ByZUV2ZW50ID8/IGZhbHNlLFxuICAgICAgaXNQb3N0RXZlbnQgPz8gZmFsc2UsXG4gICAgICBtb2RpZmlhYmxlID8/IHRydWUsXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmID8/IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzID8/IGZhbHNlLFxuICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMgPz8gdHJ1ZSxcbiAgICAgIGRheWpzKHN0YXJ0RGF0ZSkuZm9ybWF0KCksXG4gICAgICBvcmlnaW5hbEFsbERheSA/PyBmYWxzZSxcbiAgICAgIGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGNhbGVuZGFyPy5pZCxcbiAgICAgIHRpdGxlID8/ICdOZXcgRXZlbnQnLFxuICAgICAgYWxsRGF5ID8/IGZhbHNlLFxuICAgICAgZnJlcXVlbmN5XG4gICAgICAmJiByZWN1cnJpbmdFbmREYXRlXG4gICAgICAmJiBpbnRlcnZhbFxuICAgICAgJiYgeyBmcmVxdWVuY3ksIGVuZERhdGU6IHJlY3VycmluZ0VuZERhdGUsIGludGVydmFsIH0sXG4gICAgICBsb2NhdGlvbixcbiAgICAgIG5vdGVzLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgLy8gbW9kaWZpZWRBbGFybXMsXG4gICAgICB0aW1lem9uZSA/PyBkYXlqcy50ei5ndWVzcygpLFxuICAgICAgdGFza0lkLFxuICAgICAgdGFza1R5cGUsXG4gICAgICBmb2xsb3dVcEV2ZW50SWQsXG4gICAgICBwcmVFdmVudElkLFxuICAgICAgcG9zdEV2ZW50SWQsXG4gICAgICBmb3JFdmVudElkLFxuICAgICAgY29uZmVyZW5jZURhdGE/LmNvbmZlcmVuY2VJZCxcbiAgICAgIG1heEF0dGVuZGVlcyxcbiAgICAgIHNlbmRVcGRhdGVzLFxuICAgICAgc3RhdHVzLFxuICAgICAgdGl0bGUsXG4gICAgICB0cmFuc3BhcmVuY3ksXG4gICAgICB2aXNpYmlsaXR5LFxuICAgICAgcmVjdXJyaW5nRW5kRGF0ZVxuICAgICAgJiYgZnJlcXVlbmN5XG4gICAgICAmJiBldmVudElkLFxuICAgICAgaUNhbFVJRCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIGNvbG9ySWQsXG4gICAgICB1bmRlZmluZWQsIC8vIGNyZWF0b3IgLSByZWFkIG9ubHkgRy1ldmVudFxuICAgICAgdW5kZWZpbmVkLCAvLyBvcmdhbml6ZXIgLSBHLWV2ZW50IGltcG9ydCBvbmx5XG4gICAgICBmYWxzZSwgLy8gZW5kVGltZVVuc3BlY2lmaWVkIC0gb25seSBmb3IgRy1ldmVudHNcbiAgICAgIGZyZXF1ZW5jeVxuICAgICAgJiYgcmVjdXJyaW5nRW5kRGF0ZVxuICAgICAgJiYgaW50ZXJ2YWxcbiAgICAgICYmIFtydWxlLnRvU3RyaW5nKCldLFxuICAgICAgb3JpZ2luYWxUaW1lem9uZSwgLy90aW1lem9uZSBvZiByZWN1cnJlbmNlIGluc3RhbmNlXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBiYWNrZ3JvdW5kQ29sb3IsXG4gICAgICBmb3JlZ3JvdW5kQ29sb3IsXG4gICAgICB1c2VEZWZhdWx0QWxhcm1zLFxuICAgICAgcG9zaXRpdmVJbXBhY3RTY29yZSxcbiAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmUsXG4gICAgICBwb3NpdGl2ZUltcGFjdERheU9mV2VlayxcbiAgICAgIHBvc2l0aXZlSW1wYWN0VGltZSxcbiAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lLFxuICAgICAgcHJlZmVycmVkRGF5T2ZXZWVrLFxuICAgICAgcHJlZmVycmVkVGltZSxcbiAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgaXNFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlLFxuICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgIGlzTWVldGluZyxcbiAgICAgIGRhaWx5VGFza0xpc3QsXG4gICAgICB3ZWVrbHlUYXNrTGlzdCxcbiAgICAgIGlzQnJlYWssXG4gICAgICBwcmVmZXJyZWRTdGFydFRpbWVSYW5nZSxcbiAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICAgIGNvcHlBdmFpbGFiaWxpdHksXG4gICAgICBjb3B5VGltZUJsb2NraW5nLFxuICAgICAgY29weVRpbWVQcmVmZXJlbmNlLFxuICAgICAgY29weVJlbWluZGVycyxcbiAgICAgIGNvcHlQcmlvcml0eUxldmVsLFxuICAgICAgY29weU1vZGlmaWFibGUsXG4gICAgICBjb3B5Q2F0ZWdvcmllcyxcbiAgICAgIGNvcHlJc0JyZWFrLFxuICAgICAgdGltZUJsb2NraW5nLFxuICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5LFxuICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nLFxuICAgICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UsXG4gICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnMsXG4gICAgICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsLFxuICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllcyxcbiAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGUsXG4gICAgICB1c2VyTW9kaWZpZWRJc0JyZWFrLFxuICAgICAgaGFyZERlYWRsaW5lLFxuICAgICAgc29mdERlYWRsaW5lLFxuICAgICAgY29weUlzTWVldGluZyxcbiAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZyxcbiAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZyxcbiAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nLFxuICAgICAgZHVyYXRpb24sXG4gICAgICBjb3B5RHVyYXRpb24sXG4gICAgICB1c2VyTW9kaWZpZWREdXJhdGlvbixcbiAgICAgIG1ldGhvZCxcbiAgICAgIHVubGluayxcbiAgICAgIGJ5V2Vla0RheSxcbiAgICApXG5cbiAgICBpZiAoYWxhcm1zPy5sZW5ndGggPiAwKSB7XG4gICAgICBjb25zdCBwcm9taXNlcyA9IGFsYXJtcz8ubWFwKChhOiBhbnkpID0+IGNyZWF0ZVJlbWluZGVyRm9yRXZlbnQoXG4gICAgICAgIGNsaWVudCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBgJHtldmVudElkfSMke2NhbGVuZGFyPy5pZH1gLFxuICAgICAgICAodHlwZW9mIGEgPT09ICdzdHJpbmcnKSAmJiBhLFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgKHR5cGVvZiBhID09PSAnbnVtYmVyJykgJiYgYSxcbiAgICAgICAgdXNlRGVmYXVsdEFsYXJtcyxcbiAgICAgICkpXG5cbiAgICAgIGF3YWl0IFByb21pc2UuYWxsKHByb21pc2VzKVxuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKGV2ZW50SWQsICcgZXZlbnRJZCBiZWZvcmUgcmV0dXJuaW5nIGluc2lkZSBjcmVhdGVOZXdFdmVudEluR29vZ2xlJylcbiAgICByZXR1cm4gZXZlbnRJZFxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gY3JlYXRlIG5ldyBldmVudCBpbiBnb29nbGUgY2FsZW5kYXInKVxuICB9XG59XG5cbmV4cG9ydCB0eXBlIG1lZXRpbmdUeXBlU3RyaW5nVHlwZSA9ICdzY2hlZHVsZWQnIHwgJ3JlY3VycmluZ19maXhlZCdcbmV4cG9ydCB0eXBlIGNvbmZlcmVuY2VOYW1lID0gdHlwZW9mIHpvb21OYW1lIHwgdHlwZW9mIGdvb2dsZU1lZXROYW1lXG5leHBvcnQgdHlwZSBjb25mZXJlbmNlVHlwZSA9ICdoYW5nb3V0c01lZXQnIHwgJ2FkZE9uJ1xuXG5leHBvcnQgY29uc3QgZ2V0Q29uZmVyZW5jZUluRGIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNvbmZlcmVuY2VJZDogc3RyaW5nLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgY29uZmVyZW5jZSA9IChhd2FpdCBjbGllbnQucXVlcnk8eyBDb25mZXJlbmNlX2J5X3BrOiBDb25mZXJlbmNlVHlwZSB9Pih7XG4gICAgICBxdWVyeTogZ2V0Q29uZmVyZW5jZUJ5SWQsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgaWQ6IGNvbmZlcmVuY2VJZCxcbiAgICAgIH0sXG4gICAgfSkpLmRhdGE/LkNvbmZlcmVuY2VfYnlfcGtcblxuICAgIHJldHVybiBjb25mZXJlbmNlXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgY29uZmVyZW5jZSBpbiBkYicpXG4gIH1cbn1cblxuZXhwb3J0IGNvbnN0IHVwc2VydENvbmZlcmVuY2VJbkRiID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBpZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY2FsZW5kYXJJZDogc3RyaW5nLFxuICBhcHA6IEFwcFR5cGUsXG4gIHJlcXVlc3RJZD86IHN0cmluZyB8IG51bGwsXG4gIHR5cGU/OiBtZWV0aW5nVHlwZVN0cmluZ1R5cGUgfCBudWxsLFxuICBzdGF0dXM/OiBzdHJpbmcgfCBudWxsLFxuICBpY29uVXJpPzogc3RyaW5nLFxuICBuYW1lPzogQ29uZmVyZW5jZU5hbWVUeXBlIHwgbnVsbCxcbiAgbm90ZXM/OiBzdHJpbmcgfCBudWxsLFxuICBlbnRyeVBvaW50cz86IEVudHJ5UG9pbnRUeXBlW10gfCBudWxsLFxuICBwYXJhbWV0ZXJzPzoge1xuICAgIGFkZE9uUGFyYW1ldGVycz86IHtcbiAgICAgIHBhcmFtZXRlcnM/OiBQYXJhbWV0ZXJUeXBlW10sXG4gICAgfVxuICB9IHwgbnVsbCxcbiAga2V5Pzogc3RyaW5nIHwgbnVsbCxcbiAgaGFuZ291dExpbms/OiBzdHJpbmcgfCBudWxsLFxuICBqb2luVXJsPzogc3RyaW5nIHwgbnVsbCxcbiAgc3RhcnRVcmw/OiBzdHJpbmcgfCBudWxsLFxuICB6b29tUHJpdmF0ZU1lZXRpbmc/OiBib29sZWFuIHwgbnVsbCxcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGNvbmZlcmVuY2VWYWx1ZXNUb1Vwc2VydDogYW55ID0ge1xuICAgICAgaWQsXG4gICAgICB1c2VySWQsXG4gICAgICAvLyByZXF1ZXN0SWQsXG4gICAgICAvLyB0eXBlLFxuICAgICAgY2FsZW5kYXJJZCxcbiAgICAgIGFwcCxcbiAgICAgIHN0YXR1cyxcbiAgICAgIC8vIGljb25VcmksXG4gICAgICAvLyBuYW1lLFxuICAgICAgLy8gbm90ZXMsXG4gICAgICAvLyBlbnRyeVBvaW50cyxcbiAgICAgIC8vIHBhcmFtZXRlcnMsXG4gICAgICAvLyBrZXksXG4gICAgICAvLyBoYW5nb3V0TGluayxcbiAgICAgIC8vIGpvaW5VcmwsXG4gICAgICAvLyBzdGFydFVybCxcbiAgICAgIC8vIHpvb21Qcml2YXRlTWVldGluZyxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgIH1cblxuICAgIGlmIChyZXF1ZXN0SWQpIHtcbiAgICAgIGNvbmZlcmVuY2VWYWx1ZXNUb1Vwc2VydC5yZXF1ZXN0SWQgPSByZXF1ZXN0SWRcbiAgICB9XG5cbiAgICBpZiAodHlwZSkge1xuICAgICAgY29uZmVyZW5jZVZhbHVlc1RvVXBzZXJ0LnR5cGUgPSB0eXBlXG4gICAgfVxuXG4gICAgaWYgKGljb25VcmkpIHtcbiAgICAgIGNvbmZlcmVuY2VWYWx1ZXNUb1Vwc2VydC5pY29uVXJpID0gaWNvblVyaVxuICAgIH1cblxuICAgIGlmIChuYW1lKSB7XG4gICAgICBjb25mZXJlbmNlVmFsdWVzVG9VcHNlcnQubmFtZSA9IG5hbWVcbiAgICB9XG5cbiAgICBpZiAoZW50cnlQb2ludHM/LlswXSkge1xuICAgICAgY29uZmVyZW5jZVZhbHVlc1RvVXBzZXJ0LmVudHJ5UG9pbnRzID0gZW50cnlQb2ludHNcbiAgICB9XG5cbiAgICBpZiAocGFyYW1ldGVycykge1xuICAgICAgY29uZmVyZW5jZVZhbHVlc1RvVXBzZXJ0LnBhcmFtZXRlcnMgPSBwYXJhbWV0ZXJzXG4gICAgfVxuXG4gICAgaWYgKGtleSkge1xuICAgICAgY29uZmVyZW5jZVZhbHVlc1RvVXBzZXJ0LmtleSA9IGtleVxuICAgIH1cblxuICAgIGlmIChoYW5nb3V0TGluaykge1xuICAgICAgY29uZmVyZW5jZVZhbHVlc1RvVXBzZXJ0LmhhbmdvdXRMaW5rID0gaGFuZ291dExpbmtcbiAgICB9XG5cblxuICAgIGlmIChqb2luVXJsKSB7XG4gICAgICBjb25mZXJlbmNlVmFsdWVzVG9VcHNlcnQuam9pblVybCA9IGpvaW5VcmxcbiAgICB9XG5cbiAgICBpZiAoc3RhcnRVcmwpIHtcbiAgICAgIGNvbmZlcmVuY2VWYWx1ZXNUb1Vwc2VydC5zdGFydFVybCA9IHN0YXJ0VXJsXG4gICAgfVxuXG4gICAgaWYgKHpvb21Qcml2YXRlTWVldGluZykge1xuICAgICAgY29uZmVyZW5jZVZhbHVlc1RvVXBzZXJ0Lnpvb21Qcml2YXRlTWVldGluZyA9IHpvb21Qcml2YXRlTWVldGluZ1xuICAgIH1cblxuICAgIGNvbnN0IHVwc2VydENvbmZlcmVuY2UgPSBncWxgXG4gICAgICBtdXRhdGlvbiBJbnNlcnRDb25mZXJlbmNlKCRjb25mZXJlbmNlczogW0NvbmZlcmVuY2VfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgIGluc2VydF9Db25mZXJlbmNlKFxuICAgICAgICAgICAgb2JqZWN0czogJGNvbmZlcmVuY2VzLFxuICAgICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgICBjb25zdHJhaW50OiBDb25mZXJlbmNlX3BrZXksXG4gICAgICAgICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICAgICR7cmVxdWVzdElkID8gJ3JlcXVlc3RJZCwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAke3R5cGUgPyAndHlwZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAke3N0YXR1cyA/ICdzdGF0dXMsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgICAgICAgICAgICAgICR7aWNvblVyaSA/ICdpY29uVXJpLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICR7bmFtZSA/ICduYW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICR7bm90ZXMgPyAnbm90ZXMsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgJHtlbnRyeVBvaW50cyA/ICdlbnRyeVBvaW50cywnIDogJyd9XG4gICAgICAgICAgICAgICAgICAke3BhcmFtZXRlcnMgPyAncGFyYW1ldGVycywnIDogJyd9XG4gICAgICAgICAgICAgICAgICBhcHAsXG4gICAgICAgICAgICAgICAgICAke2tleSA/ICdrZXksJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgJHtoYW5nb3V0TGluayA/ICdoYW5nb3V0TGluaywnIDogJyd9XG4gICAgICAgICAgICAgICAgICAke2pvaW5VcmwgPyAnam9pblVybCwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAke3N0YXJ0VXJsID8gJ3N0YXJ0VXJsLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAgICR7em9vbVByaXZhdGVNZWV0aW5nID8gJ3pvb21Qcml2YXRlTWVldGluZywnIDogJyd9XG4gICAgICAgICAgICAgICAgICBkZWxldGVkLFxuICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICAgICAgICAgIF1cbiAgICAgICAgICAgIH0pe1xuICAgICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICB9XG4gICAgYFxuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGluc2VydF9Db25mZXJlbmNlOiB7IHJldHVybmluZzogQ29uZmVyZW5jZVR5cGVbXSB9IH0+KHtcbiAgICAgIG11dGF0aW9uOiB1cHNlcnRDb25mZXJlbmNlLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGNvbmZlcmVuY2VzOiBbY29uZmVyZW5jZVZhbHVlc1RvVXBzZXJ0XSxcbiAgICAgIH0sXG4gICAgfSlcbiAgICBjb25zb2xlLmxvZyhkYXRhLmluc2VydF9Db25mZXJlbmNlLCAnIGRhdGEuaW5zZXJ0X0NvbmZlcmVuY2UnKVxuICAgIHJldHVybiBkYXRhLmluc2VydF9Db25mZXJlbmNlLnJldHVybmluZ1swXVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gc2F2ZSBjb25mZXJlbmNlIGluIGRiJylcbiAgfVxufVxuXG5leHBvcnQgY29uc3QgY3JlYXRlQ29uZmVyZW5jZSA9IGFzeW5jIChcbiAgc3RhcnREYXRlOiBzdHJpbmcsXG4gIGVuZERhdGU6IHN0cmluZyxcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY2FsZW5kYXJJZDogc3RyaW5nLFxuICB6b29tTWVldDogYm9vbGVhbiA9IGZhbHNlLFxuICBnb29nbGVNZWV0OiBib29sZWFuID0gZmFsc2UsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBtZWV0aW5nVHlwZVN0cmluZzogbWVldGluZ1R5cGVTdHJpbmdUeXBlLFxuICBhdHRlbmRlZXM6IEdvb2dsZUF0dGVuZGVlVHlwZVtdLFxuICByZXF1ZXN0SWQ/OiBzdHJpbmcsXG4gIHN1bW1hcnk/OiBzdHJpbmcsXG4gIHRhc2tUeXBlPzogc3RyaW5nLFxuICBub3Rlcz86IHN0cmluZyxcbiAgem9vbVBhc3N3b3JkPzogc3RyaW5nLFxuICB6b29tUHJpdmF0ZU1lZXRpbmc/OiBib29sZWFuLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gdmFsaWRhdGVcbiAgICBpZiAoem9vbU1lZXQgJiYgZ29vZ2xlTWVldCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdjYW5ub3QgY3JlYXRlIGJvdGggem9vbSBhbmQgZ29vZ2xlIG1lZXQnKVxuICAgIH1cblxuICAgIGlmICghem9vbU1lZXQgJiYgIWdvb2dsZU1lZXQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbXVzdCBjcmVhdGUgZWl0aGVyIHpvb20gb3IgZ29vZ2xlIG1lZXQnKVxuICAgIH1cblxuICAgIGlmICghc3RhcnREYXRlIHx8ICFlbmREYXRlKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ3N0YXJ0RGF0ZSBhbmQgZW5kRGF0ZSBhcmUgcmVxdWlyZWQnKVxuICAgIH1cblxuICAgIGlmICghY2FsZW5kYXJJZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdjYWxlbmRhcklkIGlzIHJlcXVpcmVkJylcbiAgICB9XG5cbiAgICAvLyBjcmVhdGUgY29uZmVyZW5jZSBpZiBhbnlcbiAgICBsZXQgbmV3Q29uZmVyZW5jZUlkOiBzdHJpbmcgfCBudW1iZXIgPSAnJ1xuICAgIGxldCBuZXdKb2luVXJsID0gJydcbiAgICBsZXQgbmV3U3RhcnRVcmwgPSAnJ1xuICAgIGxldCBuZXdDb25mZXJlbmNlU3RhdHVzID0gJydcbiAgICBsZXQgY29uZmVyZW5jZU5hbWU6IGNvbmZlcmVuY2VOYW1lID0gem9vbU5hbWVcbiAgICBsZXQgY29uZmVyZW5jZVR5cGU6IGNvbmZlcmVuY2VUeXBlID0gJ2FkZE9uJ1xuICAgIGxldCBjb25mZXJlbmNlRGF0YTogQ29uZmVyZW5jZURhdGFUeXBlID0ge1xuICAgICAgdHlwZTogJ2FkZE9uJyxcbiAgICAgIG5hbWU6IGNvbmZlcmVuY2VOYW1lLFxuICAgICAgcmVxdWVzdElkOiB1dWlkKCksXG4gICAgICBjb25mZXJlbmNlSWQ6IG5ld0NvbmZlcmVuY2VJZCxcbiAgICAgIGNyZWF0ZVJlcXVlc3Q6IGZhbHNlLFxuICAgICAgZW50cnlQb2ludHM6IFt7XG4gICAgICAgIGxhYmVsOiB6b29tTmFtZSxcbiAgICAgICAgZW50cnlQb2ludFR5cGU6ICd2aWRlbycsXG4gICAgICAgIHVyaTogbmV3Sm9pblVybCxcbiAgICAgICAgcGFzc3dvcmQ6IHpvb21QYXNzd29yZCxcbiAgICAgIH1dXG4gICAgfVxuICAgIGxldCBuZXdSZXF1ZXN0SWQgPSByZXF1ZXN0SWQgfHwgdXVpZCgpXG4gICAgaWYgKHpvb21NZWV0KSB7XG4gICAgICBjb25zdCBpc1pvb21BdmFpbGFibGUgPSBhd2FpdCB6b29tQXZhaWxhYmxlKGNsaWVudCwgdXNlcklkKVxuXG4gICAgICBpZiAoaXNab29tQXZhaWxhYmxlKSB7XG5cbiAgICAgICAgY29uc3Qgem9vbUludGVnID0gKGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH0+KHtcbiAgICAgICAgICBxdWVyeTogZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2UsXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBuYW1lOiB6b29tTmFtZSxcbiAgICAgICAgICAgIHJlc291cmNlOiB6b29tUmVzb3VyY2VOYW1lLFxuICAgICAgICAgIH1cbiAgICAgICAgfSkpPy5kYXRhPy5DYWxlbmRhcl9JbnRlZ3JhdGlvbj8uWzBdXG4gICAgICAgIGNvbnN0IHtcbiAgICAgICAgICBpZDogem9vbUNvbmZlcmVuY2VJZCxcbiAgICAgICAgICBqb2luX3VybDogem9vbUpvaW5VcmwsXG4gICAgICAgICAgc3RhcnRfdXJsOiB6b29tU3RhcnRVcmwsXG4gICAgICAgICAgc3RhdHVzOiB6b29tU3RhdHVzLFxuICAgICAgICB9ID0gYXdhaXQgY3JlYXRlWm9vbU1lZXRpbmcoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGRheWpzKHN0YXJ0RGF0ZSkuZm9ybWF0KCksXG4gICAgICAgICAgZGF5anMudHouZ3Vlc3MoKSxcbiAgICAgICAgICBzdW1tYXJ5ID8/IHRhc2tUeXBlID8/IG5vdGVzLFxuICAgICAgICAgIGRheWpzLmR1cmF0aW9uKHsgaG91cnM6IGRheWpzKGVuZERhdGUpLmhvdXIoKSwgbWludXRlczogZGF5anMoZW5kRGF0ZSkubWludXRlKCkgfSkuYXNNaW51dGVzKCksXG4gICAgICAgICAgem9vbUludGVnPy5jb250YWN0TmFtZSxcbiAgICAgICAgICB6b29tSW50ZWc/LmNvbnRhY3RFbWFpbCxcbiAgICAgICAgICBhdHRlbmRlZXMubWFwKGkgPT4gaT8uZW1haWwpLFxuICAgICAgICAgIHpvb21Qcml2YXRlTWVldGluZyxcbiAgICAgICAgKVxuXG5cbiAgICAgICAgbmV3Q29uZmVyZW5jZUlkID0gem9vbUNvbmZlcmVuY2VJZFxuICAgICAgICBuZXdKb2luVXJsID0gem9vbUpvaW5VcmxcbiAgICAgICAgbmV3U3RhcnRVcmwgPSB6b29tU3RhcnRVcmxcbiAgICAgICAgbmV3Q29uZmVyZW5jZVN0YXR1cyA9IHpvb21TdGF0dXNcbiAgICAgICAgY29uZmVyZW5jZU5hbWUgPSB6b29tTmFtZVxuICAgICAgICBjb25mZXJlbmNlVHlwZSA9ICdhZGRPbidcbiAgICAgICAgY29uZmVyZW5jZURhdGEgPSB7XG4gICAgICAgICAgdHlwZTogY29uZmVyZW5jZVR5cGUsXG4gICAgICAgICAgbmFtZTogY29uZmVyZW5jZU5hbWUsXG4gICAgICAgICAgcmVxdWVzdElkOiBuZXdSZXF1ZXN0SWQsXG4gICAgICAgICAgY29uZmVyZW5jZUlkOiBgJHtuZXdDb25mZXJlbmNlSWR9YCxcbiAgICAgICAgICBjcmVhdGVSZXF1ZXN0OiBmYWxzZSxcbiAgICAgICAgICBlbnRyeVBvaW50czogW3tcbiAgICAgICAgICAgIGxhYmVsOiB6b29tTmFtZSxcbiAgICAgICAgICAgIGVudHJ5UG9pbnRUeXBlOiAndmlkZW8nLFxuICAgICAgICAgICAgdXJpOiBuZXdKb2luVXJsLFxuICAgICAgICAgICAgcGFzc3dvcmQ6IHpvb21QYXNzd29yZCxcbiAgICAgICAgICB9XVxuICAgICAgICB9XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChnb29nbGVNZWV0KSB7XG4gICAgICBuZXdDb25mZXJlbmNlSWQgPSB1dWlkKClcbiAgICAgIGNvbmZlcmVuY2VOYW1lID0gZ29vZ2xlTWVldE5hbWVcbiAgICAgIGNvbmZlcmVuY2VUeXBlID0gJ2hhbmdvdXRzTWVldCdcbiAgICAgIGNvbmZlcmVuY2VEYXRhID0ge1xuICAgICAgICB0eXBlOiBjb25mZXJlbmNlVHlwZSxcbiAgICAgICAgY29uZmVyZW5jZUlkOiBuZXdDb25mZXJlbmNlSWQsXG4gICAgICAgIG5hbWU6IGNvbmZlcmVuY2VOYW1lLFxuICAgICAgICByZXF1ZXN0SWQ6IG5ld1JlcXVlc3RJZCxcbiAgICAgICAgY3JlYXRlUmVxdWVzdDogdHJ1ZSxcbiAgICAgIH1cbiAgICB9XG5cbiAgICBhd2FpdCB1cHNlcnRDb25mZXJlbmNlSW5EYihcbiAgICAgIGNsaWVudCxcbiAgICAgIHR5cGVvZiBuZXdDb25mZXJlbmNlSWQgPT09ICdudW1iZXInID8gYCR7bmV3Q29uZmVyZW5jZUlkfWAgOiBuZXdDb25mZXJlbmNlSWQsXG4gICAgICB1c2VySWQsXG4gICAgICBjYWxlbmRhcklkLFxuICAgICAgem9vbU1lZXQgPyB6b29tUmVzb3VyY2VOYW1lIDogZ29vZ2xlUmVzb3VyY2VOYW1lLFxuICAgICAgbmV3UmVxdWVzdElkLFxuICAgICAgbWVldGluZ1R5cGVTdHJpbmcsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB1bmRlZmluZWQsXG4gICAgICB6b29tTWVldCA/IHpvb21OYW1lIDogZ29vZ2xlTWVldE5hbWUsXG4gICAgICBub3RlcyxcbiAgICAgIGNvbmZlcmVuY2VEYXRhPy5lbnRyeVBvaW50cyxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIG5ld0pvaW5VcmwsXG4gICAgICBuZXdTdGFydFVybCxcbiAgICAgIHpvb21Qcml2YXRlTWVldGluZyxcbiAgICApXG5cbiAgICByZXR1cm4ge1xuICAgICAgbmV3Q29uZmVyZW5jZUlkLFxuICAgICAgbmV3Sm9pblVybCxcbiAgICAgIG5ld1N0YXJ0VXJsLFxuICAgICAgbmV3Q29uZmVyZW5jZVN0YXR1cyxcbiAgICAgIGNvbmZlcmVuY2VOYW1lLFxuICAgICAgY29uZmVyZW5jZVR5cGUsXG4gICAgICBjb25mZXJlbmNlRGF0YSxcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjcmVhdGUgY29uZmVyZW5jZScpXG4gIH1cbn1cblxuZXhwb3J0IGNvbnN0IGNyZWF0ZU5ld0V2ZW50ID0gYXN5bmMgKFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgc2VsZWN0ZWRDYWxlbmRhcklkPzogc3RyaW5nLFxuICBjYXRlZ29yeUlkcz86IHN0cmluZ1tdLFxuICB0aXRsZT86IHN0cmluZyxcbiAgYWxsRGF5PzogYm9vbGVhbixcbiAgcmVjdXJyaW5nRW5kRGF0ZT86IHN0cmluZyxcbiAgZnJlcXVlbmN5PzogUmVjdXJyZW5jZUZyZXF1ZW5jeVR5cGUsXG4gIGludGVydmFsPzogbnVtYmVyLFxuICBhbGFybXM/OiBzdHJpbmdbXSB8IG51bWJlcltdLFxuICBub3Rlcz86IHN0cmluZyxcbiAgbG9jYXRpb24/OiBMb2NhdGlvblR5cGUsXG4gIGlzRm9sbG93VXA/OiBib29sZWFuLFxuICBpc1ByZUV2ZW50PzogYm9vbGVhbixcbiAgaXNQb3N0RXZlbnQ/OiBib29sZWFuLFxuICBtb2RpZmlhYmxlPzogYm9vbGVhbixcbiAgYW55b25lQ2FuQWRkU2VsZj86IGJvb2xlYW4sXG4gIGd1ZXN0c0Nhbkludml0ZU90aGVycz86IGJvb2xlYW4sXG4gIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzPzogYm9vbGVhbixcbiAgb3JpZ2luYWxBbGxEYXk/OiBib29sZWFuLFxuICB0aW1lem9uZT86IHN0cmluZyxcbiAgdGFza0lkPzogc3RyaW5nLFxuICB0YXNrVHlwZT86IHN0cmluZyxcbiAgZm9sbG93VXBFdmVudElkPzogc3RyaW5nLFxuICBwcmVFdmVudElkPzogc3RyaW5nLFxuICBwb3N0RXZlbnRJZD86IHN0cmluZyxcbiAgZm9yRXZlbnRJZD86IHN0cmluZyxcbiAgem9vbU1lZXQ/OiBib29sZWFuLFxuICBnb29nbGVNZWV0PzogYm9vbGVhbixcbiAgbWVldGluZ1R5cGVTdHJpbmc/OiBtZWV0aW5nVHlwZVN0cmluZ1R5cGUsXG4gIHpvb21QYXNzd29yZD86IHN0cmluZyxcbiAgem9vbVByaXZhdGVNZWV0aW5nPzogYm9vbGVhbixcbiAgYXR0ZW5kZWVzPzogUGVyc29uW10sXG4gIGNvbmZlcmVuY2VJZD86IHN0cmluZyxcbiAgbWF4QXR0ZW5kZWVzPzogbnVtYmVyLFxuICBzZW5kVXBkYXRlcz86IFNlbmRVcGRhdGVzVHlwZSxcbiAgc3RhdHVzPzogc3RyaW5nLFxuICBzdW1tYXJ5Pzogc3RyaW5nLFxuICB0cmFuc3BhcmVuY3k/OiBUcmFuc3BhcmVuY3lUeXBlLFxuICB2aXNpYmlsaXR5PzogVmlzaWJpbGl0eVR5cGUsXG4gIHJlY3VycmluZ0V2ZW50SWQ/OiBzdHJpbmcsXG4gIGlDYWxVSUQ/OiBzdHJpbmcsXG4gIGh0bWxMaW5rPzogc3RyaW5nLFxuICBjb2xvcklkPzogc3RyaW5nLFxuICBvcmlnaW5hbFRpbWV6b25lPzogc3RyaW5nLFxuICBiYWNrZ3JvdW5kQ29sb3I/OiBzdHJpbmcsXG4gIGZvcmVncm91bmRDb2xvcj86IHN0cmluZyxcbiAgdXNlRGVmYXVsdEFsYXJtcz86IGJvb2xlYW4sXG4gIHBvc2l0aXZlSW1wYWN0U2NvcmU/OiBudW1iZXIsXG4gIG5lZ2F0aXZlSW1wYWN0U2NvcmU/OiBudW1iZXIsXG4gIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrPzogbnVtYmVyLFxuICBwb3NpdGl2ZUltcGFjdFRpbWU/OiBUaW1lLFxuICBuZWdhdGl2ZUltcGFjdERheU9mV2Vlaz86IG51bWJlcixcbiAgbmVnYXRpdmVJbXBhY3RUaW1lPzogVGltZSxcbiAgcHJlZmVycmVkRGF5T2ZXZWVrPzogbnVtYmVyLFxuICBwcmVmZXJyZWRUaW1lPzogVGltZSxcbiAgaXNFeHRlcm5hbE1lZXRpbmc/OiBib29sZWFuLFxuICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGU/OiBib29sZWFuLFxuICBpc01lZXRpbmdNb2RpZmlhYmxlPzogYm9vbGVhbixcbiAgaXNNZWV0aW5nPzogYm9vbGVhbixcbiAgZGFpbHlUYXNrTGlzdD86IGJvb2xlYW4sXG4gIHdlZWtseVRhc2tMaXN0PzogYm9vbGVhbixcbiAgaXNCcmVhaz86IGJvb2xlYW4sXG4gIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPzogVGltZSxcbiAgcHJlZmVycmVkRW5kVGltZVJhbmdlPzogVGltZSxcbiAgY29weUF2YWlsYWJpbGl0eT86IGJvb2xlYW4sXG4gIGNvcHlUaW1lQmxvY2tpbmc/OiBib29sZWFuLFxuICBjb3B5VGltZVByZWZlcmVuY2U/OiBib29sZWFuLFxuICBjb3B5UmVtaW5kZXJzPzogYm9vbGVhbixcbiAgY29weVByaW9yaXR5TGV2ZWw/OiBib29sZWFuLFxuICBjb3B5TW9kaWZpYWJsZT86IGJvb2xlYW4sXG4gIGNvcHlDYXRlZ29yaWVzPzogYm9vbGVhbixcbiAgY29weUlzQnJlYWs/OiBib29sZWFuLFxuICB0aW1lQmxvY2tpbmc/OiBCdWZmZXJUaW1lVHlwZSxcbiAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5PzogYm9vbGVhbixcbiAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nPzogYm9vbGVhbixcbiAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2U/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRSZW1pbmRlcnM/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRQcmlvcml0eUxldmVsPzogYm9vbGVhbixcbiAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllcz86IGJvb2xlYW4sXG4gIHVzZXJNb2RpZmllZE1vZGlmaWFibGU/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRJc0JyZWFrPzogYm9vbGVhbixcbiAgaGFyZERlYWRsaW5lPzogc3RyaW5nLFxuICBzb2Z0RGVhZGxpbmU/OiBzdHJpbmcsXG4gIGNvcHlJc01lZXRpbmc/OiBib29sZWFuLFxuICBjb3B5SXNFeHRlcm5hbE1lZXRpbmc/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRJc01lZXRpbmc/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZz86IGJvb2xlYW4sXG4gIGR1cmF0aW9uPzogbnVtYmVyLFxuICBjb3B5RHVyYXRpb24/OiBib29sZWFuLFxuICB1c2VyTW9kaWZpZWREdXJhdGlvbj86IGJvb2xlYW4sXG4gIG1ldGhvZD86ICdjcmVhdGUnIHwgJ3VwZGF0ZScsXG4gIHVubGluaz86IGJvb2xlYW4sXG4gIGJ5V2Vla0RheT86IERheVtdLFxuICBwcmlvcml0eT86IG51bWJlcixcbikgPT4ge1xuICB0cnkge1xuICAgIC8qKlxuICAgIDIuIGNoZWNrIGlmIGFueSBjYWxlbmRhcnMgYXJlIGFjdGl2ZVxuICAgIDMuIGNyZWF0ZSBpbiBnbG9iYWwgcHJpbWFyeSBjYWxlbmRhclxuICAgIGlmIG5vbmUgY3JlYXRlIGluIGFueSBjYWxlbmRhciBhdmFpbGFibGVcbiAgICBmaW5hbGx5IHRyeSBjcmVhdGUgbG9jYWwgY2FsZW5kYXIgaWYgbm9uZSBhdmFpbGFibGVcbiAgICBhbmQgc2F2ZSB0byBjYWxlbmRhciBkYlxuICAgICAqL1xuXG4gICAgbGV0IGNhbGVuZGFyOiBDYWxlbmRhclR5cGUgfCB7fSA9IHt9XG5cbiAgICBpZiAoc2VsZWN0ZWRDYWxlbmRhcklkPy5sZW5ndGggPiAwKSB7XG4gICAgICBjYWxlbmRhciA9IGF3YWl0IGdldENhbGVuZGFySW5EYihjbGllbnQsIHVzZXJJZCwgc2VsZWN0ZWRDYWxlbmRhcklkKVxuICAgIH1cblxuICAgIGlmICghc2VsZWN0ZWRDYWxlbmRhcklkKSB7XG4gICAgICAvLyBnbG9iYWwgcHJpbWFyeSBpZiBub25lIHNlbGVjdGVkQ2FsZW5kYXJJZFxuICAgICAgY2FsZW5kYXIgPSBhd2FpdCBnZXRDYWxlbmRhckluRGIoY2xpZW50LCB1c2VySWQsIHVuZGVmaW5lZCwgdHJ1ZSlcbiAgICB9XG5cbiAgICAvLyBpZiBubyAgY2FsZW5kYXIgZ2V0IGdvb2dsZSBjYWxlbmRhclxuICAgIGlmICghc2VsZWN0ZWRDYWxlbmRhcklkICYmICFjYWxlbmRhciAmJiBnb29nbGVSZXNvdXJjZU5hbWUpIHtcbiAgICAgIGNhbGVuZGFyID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbkRiKGNsaWVudCwgdXNlcklkLCB1bmRlZmluZWQsIHVuZGVmaW5lZCwgZ29vZ2xlUmVzb3VyY2VOYW1lKVxuICAgIH1cblxuICAgIGlmICghKChjYWxlbmRhciBhcyBDYWxlbmRhclR5cGUpPy5pZCkgJiYgIXNlbGVjdGVkQ2FsZW5kYXJJZCkge1xuICAgICAgLy8gZ2V0IGFueSBpZiBub25lIHNldCB0byBnbG9iYWxQcmltYXJ5IGFuZCBubyBzZWxlY3RlZENhbGVuZGFySWRcbiAgICAgIGNhbGVuZGFyID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbkRiKGNsaWVudCwgdXNlcklkKVxuICAgIH1cblxuICAgIGlmICgoY2FsZW5kYXIgYXMgQ2FsZW5kYXJUeXBlKT8ucmVzb3VyY2UgPT09IGdvb2dsZVJlc291cmNlTmFtZSkge1xuICAgICAgY29uc3QgbW9kaWZpZWRBdHRlbmRlZXM6IEdvb2dsZUF0dGVuZGVlVHlwZVtdID0gYXR0ZW5kZWVzPy5tYXAoYSA9PiAoe1xuICAgICAgICBhZGRpdGlvbmFsR3Vlc3RzOiBhPy5hZGRpdGlvbmFsR3Vlc3RzLFxuICAgICAgICBkaXNwbGF5TmFtZTogYT8ubmFtZSxcbiAgICAgICAgZW1haWw6IGE/LmVtYWlscz8uWzBdPy52YWx1ZSxcbiAgICAgICAgaWQ6IGE/LmlkLFxuICAgICAgfSkpXG4gICAgICBsZXQgY29uZmVyZW5jZURhdGEgPSBudWxsXG4gICAgICAvLyBjcmVhdGUgY29uZmVyZWNlXG4gICAgICBpZiAobW9kaWZpZWRBdHRlbmRlZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3Qge1xuICAgICAgICAgIC8vIG5ld0NvbmZlcmVuY2VJZCxcbiAgICAgICAgICAvLyBuZXdKb2luVXJsLFxuICAgICAgICAgIC8vIG5ld1N0YXJ0VXJsLFxuICAgICAgICAgIC8vIG5ld0NvbmZlcmVuY2VTdGF0dXMsXG4gICAgICAgICAgLy8gY29uZmVyZW5jZU5hbWUsXG4gICAgICAgICAgLy8gY29uZmVyZW5jZVR5cGUsXG4gICAgICAgICAgY29uZmVyZW5jZURhdGE6IGNvbmZlcmVuY2VEYXRhMSxcbiAgICAgICAgfSA9IGF3YWl0IGNyZWF0ZUNvbmZlcmVuY2UoXG4gICAgICAgICAgc3RhcnREYXRlLFxuICAgICAgICAgIGVuZERhdGUsXG4gICAgICAgICAgY2xpZW50LFxuICAgICAgICAgIChjYWxlbmRhciBhcyBDYWxlbmRhclR5cGUpPy5pZCxcbiAgICAgICAgICB6b29tTWVldCxcbiAgICAgICAgICBnb29nbGVNZWV0LFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICBtZWV0aW5nVHlwZVN0cmluZyxcbiAgICAgICAgICBtb2RpZmllZEF0dGVuZGVlcyxcbiAgICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgICAgc3VtbWFyeSxcbiAgICAgICAgICB0YXNrVHlwZSxcbiAgICAgICAgICBub3RlcyxcbiAgICAgICAgICB6b29tUGFzc3dvcmQsXG4gICAgICAgICAgem9vbVByaXZhdGVNZWV0aW5nLFxuICAgICAgICApXG4gICAgICAgIGNvbmZlcmVuY2VEYXRhID0gY29uZmVyZW5jZURhdGExXG4gICAgICB9XG5cbiAgICAgIGNvbnNvbGUubG9nKGhhcmREZWFkbGluZSwgc29mdERlYWRsaW5lLCAnIGhhcmREZWFkbGluZSwgc29mdERlYWRsaW5lIGluc2lkZSBjcmVhdGVOZXdFdmVudCcpXG4gICAgICBjb25zdCBldmVudElkID0gYXdhaXQgY3JlYXRlTmV3RXZlbnRJbkdvb2dsZShcbiAgICAgICAgc3RhcnREYXRlLFxuICAgICAgICBlbmREYXRlLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNsaWVudCxcbiAgICAgICAgY2FsZW5kYXIgYXMgQ2FsZW5kYXJUeXBlLFxuICAgICAgICBjb25mZXJlbmNlRGF0YSxcbiAgICAgICAgbW9kaWZpZWRBdHRlbmRlZXMsXG4gICAgICAgIHRpdGxlLFxuICAgICAgICBhbGxEYXksXG4gICAgICAgIHJlY3VycmluZ0VuZERhdGUsXG4gICAgICAgIGZyZXF1ZW5jeSxcbiAgICAgICAgaW50ZXJ2YWwsXG4gICAgICAgIG5vdGVzLFxuICAgICAgICBsb2NhdGlvbixcbiAgICAgICAgaXNGb2xsb3dVcCxcbiAgICAgICAgaXNQcmVFdmVudCxcbiAgICAgICAgaXNQb3N0RXZlbnQsXG4gICAgICAgIG1vZGlmaWFibGUsXG4gICAgICAgIGFueW9uZUNhbkFkZFNlbGYsXG4gICAgICAgIGd1ZXN0c0Nhbkludml0ZU90aGVycyxcbiAgICAgICAgZ3Vlc3RzQ2FuU2VlT3RoZXJHdWVzdHMsXG4gICAgICAgIG9yaWdpbmFsQWxsRGF5LFxuICAgICAgICBhbGFybXMsXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICB0YXNrSWQsXG4gICAgICAgIHRhc2tUeXBlLFxuICAgICAgICBmb2xsb3dVcEV2ZW50SWQsXG4gICAgICAgIHByZUV2ZW50SWQsXG4gICAgICAgIHBvc3RFdmVudElkLFxuICAgICAgICBmb3JFdmVudElkLFxuICAgICAgICBtYXhBdHRlbmRlZXMsXG4gICAgICAgIHNlbmRVcGRhdGVzLFxuICAgICAgICBzdGF0dXMsXG4gICAgICAgIHRyYW5zcGFyZW5jeSxcbiAgICAgICAgdmlzaWJpbGl0eSxcbiAgICAgICAgaUNhbFVJRCxcbiAgICAgICAgYmFja2dyb3VuZENvbG9yLFxuICAgICAgICBmb3JlZ3JvdW5kQ29sb3IsXG4gICAgICAgIGNvbG9ySWQsXG4gICAgICAgIG9yaWdpbmFsVGltZXpvbmUsXG4gICAgICAgIHVzZURlZmF1bHRBbGFybXMsXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmUsXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmUsXG4gICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgICBwb3NpdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrLFxuICAgICAgICBuZWdhdGl2ZUltcGFjdFRpbWUsXG4gICAgICAgIHByZWZlcnJlZERheU9mV2VlayxcbiAgICAgICAgcHJlZmVycmVkVGltZSxcbiAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmcsXG4gICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZSxcbiAgICAgICAgaXNNZWV0aW5nLFxuICAgICAgICBkYWlseVRhc2tMaXN0LFxuICAgICAgICB3ZWVrbHlUYXNrTGlzdCxcbiAgICAgICAgaXNCcmVhayxcbiAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsXG4gICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZSxcbiAgICAgICAgY29weUF2YWlsYWJpbGl0eSxcbiAgICAgICAgY29weVRpbWVCbG9ja2luZyxcbiAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlLFxuICAgICAgICBjb3B5UmVtaW5kZXJzLFxuICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbCxcbiAgICAgICAgY29weU1vZGlmaWFibGUsXG4gICAgICAgIGNvcHlDYXRlZ29yaWVzLFxuICAgICAgICBjb3B5SXNCcmVhayxcbiAgICAgICAgdGltZUJsb2NraW5nLFxuICAgICAgICB1c2VyTW9kaWZpZWRBdmFpbGFiaWxpdHksXG4gICAgICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZyxcbiAgICAgICAgdXNlck1vZGlmaWVkVGltZVByZWZlcmVuY2UsXG4gICAgICAgIHVzZXJNb2RpZmllZFJlbWluZGVycyxcbiAgICAgICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbCxcbiAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllcyxcbiAgICAgICAgdXNlck1vZGlmaWVkTW9kaWZpYWJsZSxcbiAgICAgICAgdXNlck1vZGlmaWVkSXNCcmVhayxcbiAgICAgICAgaGFyZERlYWRsaW5lLFxuICAgICAgICBzb2Z0RGVhZGxpbmUsXG4gICAgICAgIGNvcHlJc01lZXRpbmcsXG4gICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZyxcbiAgICAgICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nLFxuICAgICAgICB1c2VyTW9kaWZpZWRJc0V4dGVybmFsTWVldGluZyxcbiAgICAgICAgZHVyYXRpb24sXG4gICAgICAgIGNvcHlEdXJhdGlvbixcbiAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb24sXG4gICAgICAgIG1ldGhvZCxcbiAgICAgICAgdW5saW5rLFxuICAgICAgICBieVdlZWtEYXksXG4gICAgICAgIHByaW9yaXR5LFxuICAgICAgKVxuXG4gICAgICBjb25zb2xlLmxvZyhldmVudElkLCAnIGV2ZW50SWQgaW5zaWRlIGNyZWF0ZU5ld0V2ZW50IGFmdGVyIGNyZWF0ZU5ld0V2ZW50SW5Hb29nbGUnKVxuXG4gICAgICAvLyBzYXZlIGF0dGVuZGVlc1xuICAgICAgaWYgKGF0dGVuZGVlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBjb25zdCBhdHRlbmRlZVByb21pc2VzID0gYXR0ZW5kZWVzPy5tYXAoYSA9PiB7XG4gICAgICAgICAgcmV0dXJuIHVwc2VydEF0dGVuZGVlc0luRGIoXG4gICAgICAgICAgICBjbGllbnQsXG4gICAgICAgICAgICB1dWlkKCksXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBldmVudElkLFxuICAgICAgICAgICAgYT8uZW1haWxzLFxuICAgICAgICAgICAgYT8ubmFtZSxcbiAgICAgICAgICAgIGE/LmlkLFxuICAgICAgICAgICAgYT8ucGhvbmVOdW1iZXJzLFxuICAgICAgICAgICAgYT8uaW1BZGRyZXNzZXMsXG4gICAgICAgICAgICBhPy5hZGRpdGlvbmFsR3Vlc3RzLFxuICAgICAgICAgICAgYT8ub3B0aW9uYWwsXG4gICAgICAgICAgICBhPy5yZXNvdXJjZSxcbiAgICAgICAgICApXG4gICAgICAgIH0pXG4gICAgICAgIGF3YWl0IFByb21pc2UuYWxsKGF0dGVuZGVlUHJvbWlzZXMpXG4gICAgICB9XG5cbiAgICAgIGlmIChjYXRlZ29yeUlkcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAvLyBjcmVhdGUgY2F0ZWdvcnlfZXZlbnQgY29ubmVjdGlvbnNcbiAgICAgICAgY29uc3QgY2F0ZWdvcnlQcm9taXNlcyA9IGNhdGVnb3J5SWRzLm1hcChpID0+IHVwc2VydENhdGVnb3J5RXZlbnRDb25uZWN0aW9uKFxuICAgICAgICAgIGNsaWVudCwgdXNlcklkLCBpLCBldmVudElkLFxuICAgICAgICApKVxuXG4gICAgICAgIGF3YWl0IFByb21pc2UuYWxsKGNhdGVnb3J5UHJvbWlzZXMpXG4gICAgICB9XG5cbiAgICAgIHJldHVybiBldmVudElkXG4gICAgfVxuXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjcmVhdGUgbmV3IGV2ZW50JylcbiAgfVxufVxuXG5leHBvcnQgY29uc3QgZGVsZXRlRXZlbnRGb3JUYXNrID0gYXN5bmMgKFxuICBldmVudElkOiBzdHJpbmcsXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IChhd2FpdCBjbGllbnQubXV0YXRlPHsgZGVsZXRlX0V2ZW50X2J5X3BrOiBFdmVudFR5cGUgfT4oe1xuICAgICAgbXV0YXRpb246IGRlbGV0ZUV2ZW50QnlJZCxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBpZDogZXZlbnRJZCxcbiAgICAgIH0sXG4gICAgICAvLyByZWZldGNoUXVlcmllczogW1xuICAgICAgLy8gICBsaXN0QWxsRXZlbnRzLCAvLyBEb2N1bWVudE5vZGUgb2JqZWN0IHBhcnNlZCB3aXRoIGdxbFxuICAgICAgLy8gICAnbGlzdEFsbEV2ZW50cycgLy8gUXVlcnkgbmFtZVxuICAgICAgLy8gXSxcbiAgICAgIHVwZGF0ZShjYWNoZSwgeyBkYXRhIH0pIHtcbiAgICAgICAgY29uc3QgZGVsZXRlZEV2ZW50ID0gZGF0YT8uZGVsZXRlX0V2ZW50X2J5X3BrXG4gICAgICAgIGNvbnN0IG5vcm1hbGl6ZWRJZCA9IGNhY2hlLmlkZW50aWZ5KHsgaWQ6IGRlbGV0ZWRFdmVudC5pZCwgX190eXBlbmFtZTogZGVsZXRlZEV2ZW50Ll9fdHlwZW5hbWUgfSlcbiAgICAgICAgY2FjaGUuZXZpY3QoeyBpZDogbm9ybWFsaXplZElkIH0pXG4gICAgICAgIGNhY2hlLmdjKClcbiAgICAgIH1cbiAgICB9KSlcbiAgICBjb25zb2xlLmxvZyhkYXRhLCAnIGRlbGV0ZSBldmVudCcpXG4gICAgcmV0dXJuIGRhdGE/LmRlbGV0ZV9FdmVudF9ieV9waz8uaWRcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICdlcnJvciBmb3IgZGVsZXRlRXZlbnQnKVxuICB9XG59XG5cblxuLyoqXG5lbmRcbiAqL1xuIl19