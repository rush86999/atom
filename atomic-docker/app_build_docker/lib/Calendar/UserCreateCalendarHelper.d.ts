import { Dispatch, SetStateAction } from 'react';
import { CalendarType } from '@lib/dataTypes/CalendarType';
import { Time, BufferTimeType } from '@lib/dataTypes/EventType';
import { EventType, RecurrenceRuleType, AttachmentType, LocationType, CreatorType, OrganizerType, ExtendedPropertiesType, SourceType, LinkType } from '@lib/dataTypes/EventType';
import { googleMeetName } from '@lib/calendarLib/constants';
import { GoogleAttendeeType, ConferenceDataType, SendUpdatesType, TransparencyType, VisibilityType } from '@lib/calendarLib/types';
import { zoomName } from '@lib/zoom/constants';
import { accessRole, Person, RecurrenceFrequencyType, TagType } from '@lib/Calendar/types';
import { ParameterType, EntryPointType, AppType, ConferenceNameType } from '@lib/dataTypes/ConferenceType';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { type Event as CalendarEvent } from 'react-big-calendar';
import { Day } from '@lib/Schedule/constants';
export type CalendarEventPro = CalendarEvent & {
    id: string;
    calendarId: string;
    eventId: string;
    color?: string;
    notes?: string;
    tags: TagType[];
    unlink: boolean;
    modifiable: boolean;
    priority: number;
    recurringEndDate?: string;
    frequency?: RecurrenceFrequencyType;
    interval?: string;
};
export interface NewEventTime {
    hour: number;
    minutes: number;
    date?: string;
}
export declare const reformatToCalendarEventsUIWebForCalendarFromDb: (events: EventType[], client: ApolloClient<NormalizedCacheObject>) => Promise<CalendarEventPro[] | undefined>;
export declare const setCurrentEventsForCalendarWeb: (userId: string, client: ApolloClient<NormalizedCacheObject>, setCalendarEvents: Dispatch<SetStateAction<CalendarEventPro[]>>) => Promise<void>;
export declare const getCurrentEvents: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<any>;
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
export declare const getCalendarInDb: (client: ApolloClient<NormalizedCacheObject>, userId: string, calendarId?: string, globalPrimary?: boolean, resource?: string) => Promise<any>;
export declare const upsertLocalCalendar: (client: ApolloClient<NormalizedCacheObject>, id: string, userId: string, title: string, backgroundColor: string, accessLevel?: accessRole, resource?: string, globalPrimary?: boolean, foregroundColor?: string) => Promise<any>;
export declare const getRruleFreq: (freq: RecurrenceFrequencyType) => import("rrule").Frequency.YEARLY | import("rrule").Frequency.MONTHLY | import("rrule").Frequency.WEEKLY | import("rrule").Frequency.DAILY | undefined;
export declare const atomicUpsertEventInDb: (client: ApolloClient<NormalizedCacheObject>, id: string, eventId: string, userId: string, startDate?: string, endDate?: string, createdDate?: string, deleted?: boolean, priority?: number, isFollowUp?: boolean, isPreEvent?: boolean, isPostEvent?: boolean, modifiable?: boolean, anyoneCanAddSelf?: boolean, guestsCanInviteOthers?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDate?: string, originalAllDay?: boolean, updatedAt?: string, calendarId?: string, title?: string, allDay?: boolean, recurrenceRule?: RecurrenceRuleType, location?: LocationType, notes?: string, attachments?: AttachmentType[], links?: LinkType[], timezone?: string, taskId?: string, taskType?: string, followUpEventId?: string, preEventId?: string, postEventId?: string, forEventId?: string, conferenceId?: string, maxAttendees?: number, sendUpdates?: SendUpdatesType, status?: string, summary?: string, transparency?: TransparencyType, visibility?: VisibilityType, recurringEventId?: string, iCalUID?: string, htmlLink?: string, colorId?: string, creator?: CreatorType, organizer?: OrganizerType, endTimeUnspecified?: boolean, recurrence?: string[], originalTimezone?: string, attendeesOmitted?: boolean, extendedProperties?: ExtendedPropertiesType, hangoutLink?: string, guestsCanModify?: boolean, locked?: boolean, source?: SourceType, eventType?: string, privateCopy?: boolean, backgroundColor?: string, foregroundColor?: string, useDefaultAlarms?: boolean, positiveImpactScore?: number, negativeImpactScore?: number, positiveImpactDayOfWeek?: number, positiveImpactTime?: Time, negativeImpactDayOfWeek?: number, negativeImpactTime?: Time, preferredDayOfWeek?: number, preferredTime?: Time, isExternalMeeting?: boolean, isExternalMeetingModifiable?: boolean, isMeetingModifiable?: boolean, isMeeting?: boolean, dailyTaskList?: boolean, weeklyTaskList?: boolean, isBreak?: boolean, preferredStartTimeRange?: Time, preferredEndTimeRange?: Time, copyAvailability?: boolean, copyTimeBlocking?: boolean, copyTimePreference?: boolean, copyReminders?: boolean, copyPriorityLevel?: boolean, copyModifiable?: boolean, copyCategories?: boolean, copyIsBreak?: boolean, timeBlocking?: BufferTimeType, userModifiedAvailability?: boolean, userModifiedTimeBlocking?: boolean, userModifiedTimePreference?: boolean, userModifiedReminders?: boolean, userModifiedPriorityLevel?: boolean, userModifiedCategories?: boolean, userModifiedModifiable?: boolean, userModifiedIsBreak?: boolean, hardDeadline?: string, softDeadline?: string, copyIsMeeting?: boolean, copyIsExternalMeeting?: boolean, userModifiedIsMeeting?: boolean, userModifiedIsExternalMeeting?: boolean, duration?: number, copyDuration?: boolean, userModifiedDuration?: boolean, method?: "create" | "update", unlink?: boolean, byWeekDay?: Day[], localSynced?: boolean, copyColor?: boolean, userModifiedColor?: boolean, meetingId?: string) => Promise<any>;
export declare const getRRuleDay: (value: Day | undefined) => import("rrule").Weekday | undefined;
export declare const createNewEventInGoogle: (startDate: string, endDate: string, userId: string, client: ApolloClient<NormalizedCacheObject>, calendar: CalendarType, conferenceData?: ConferenceDataType, attendees?: GoogleAttendeeType[], title?: string, allDay?: boolean, recurringEndDate?: string, frequency?: RecurrenceFrequencyType, interval?: number, notes?: string, location?: LocationType, isFollowUp?: boolean, isPreEvent?: boolean, isPostEvent?: boolean, modifiable?: boolean, anyoneCanAddSelf?: boolean, guestsCanInviteOthers?: boolean, guestsCanSeeOtherGuests?: boolean, originalAllDay?: boolean, alarms?: string[] | number[], timezone?: string, taskId?: string, taskType?: string, followUpEventId?: string, preEventId?: string, postEventId?: string, forEventId?: string, maxAttendees?: number, sendUpdates?: SendUpdatesType, status?: string, transparency?: TransparencyType, visibility?: VisibilityType, iCalUID?: string, backgroundColor?: string, foregroundColor?: string, colorId?: string, originalTimezone?: string, useDefaultAlarms?: boolean, positiveImpactScore?: number, negativeImpactScore?: number, positiveImpactDayOfWeek?: number, positiveImpactTime?: Time, negativeImpactDayOfWeek?: number, negativeImpactTime?: Time, preferredDayOfWeek?: number, preferredTime?: Time, isExternalMeeting?: boolean, isExternalMeetingModifiable?: boolean, isMeetingModifiable?: boolean, isMeeting?: boolean, dailyTaskList?: boolean, weeklyTaskList?: boolean, isBreak?: boolean, preferredStartTimeRange?: Time, preferredEndTimeRange?: Time, copyAvailability?: boolean, copyTimeBlocking?: boolean, copyTimePreference?: boolean, copyReminders?: boolean, copyPriorityLevel?: boolean, copyModifiable?: boolean, copyCategories?: boolean, copyIsBreak?: boolean, timeBlocking?: BufferTimeType, userModifiedAvailability?: boolean, userModifiedTimeBlocking?: boolean, userModifiedTimePreference?: boolean, userModifiedReminders?: boolean, userModifiedPriorityLevel?: boolean, userModifiedCategories?: boolean, userModifiedModifiable?: boolean, userModifiedIsBreak?: boolean, hardDeadline?: string, softDeadline?: string, copyIsMeeting?: boolean, copyIsExternalMeeting?: boolean, userModifiedIsMeeting?: boolean, userModifiedIsExternalMeeting?: boolean, duration?: number, copyDuration?: boolean, userModifiedDuration?: boolean, method?: "create" | "update", unlink?: boolean, byWeekDay?: Day[], priority?: number) => Promise<any>;
export type meetingTypeStringType = 'scheduled' | 'recurring_fixed';
export type conferenceName = typeof zoomName | typeof googleMeetName;
export type conferenceType = 'hangoutsMeet' | 'addOn';
export declare const getConferenceInDb: (client: ApolloClient<NormalizedCacheObject>, conferenceId: string) => Promise<any>;
export declare const upsertConferenceInDb: (client: ApolloClient<NormalizedCacheObject>, id: string, userId: string, calendarId: string, app: AppType, requestId?: string | null, type?: meetingTypeStringType | null, status?: string | null, iconUri?: string, name?: ConferenceNameType | null, notes?: string | null, entryPoints?: EntryPointType[] | null, parameters?: {
    addOnParameters?: {
        parameters?: ParameterType[];
    };
} | null, key?: string | null, hangoutLink?: string | null, joinUrl?: string | null, startUrl?: string | null, zoomPrivateMeeting?: boolean | null) => Promise<any>;
export declare const createConference: (startDate: string, endDate: string, client: ApolloClient<NormalizedCacheObject>, calendarId: string, zoomMeet: boolean | undefined, googleMeet: boolean | undefined, userId: string, meetingTypeString: meetingTypeStringType, attendees: GoogleAttendeeType[], requestId?: string, summary?: string, taskType?: string, notes?: string, zoomPassword?: string, zoomPrivateMeeting?: boolean) => Promise<{
    newConferenceId: string | number;
    newJoinUrl: string;
    newStartUrl: string;
    newConferenceStatus: string;
    conferenceName: any;
    conferenceType: conferenceType;
    conferenceData: ConferenceDataType;
} | undefined>;
export declare const createNewEvent: (startDate: string, endDate: string, userId: string, client: ApolloClient<NormalizedCacheObject>, selectedCalendarId?: string, categoryIds?: string[], title?: string, allDay?: boolean, recurringEndDate?: string, frequency?: RecurrenceFrequencyType, interval?: number, alarms?: string[] | number[], notes?: string, location?: LocationType, isFollowUp?: boolean, isPreEvent?: boolean, isPostEvent?: boolean, modifiable?: boolean, anyoneCanAddSelf?: boolean, guestsCanInviteOthers?: boolean, guestsCanSeeOtherGuests?: boolean, originalAllDay?: boolean, timezone?: string, taskId?: string, taskType?: string, followUpEventId?: string, preEventId?: string, postEventId?: string, forEventId?: string, zoomMeet?: boolean, googleMeet?: boolean, meetingTypeString?: meetingTypeStringType, zoomPassword?: string, zoomPrivateMeeting?: boolean, attendees?: Person[], conferenceId?: string, maxAttendees?: number, sendUpdates?: SendUpdatesType, status?: string, summary?: string, transparency?: TransparencyType, visibility?: VisibilityType, recurringEventId?: string, iCalUID?: string, htmlLink?: string, colorId?: string, originalTimezone?: string, backgroundColor?: string, foregroundColor?: string, useDefaultAlarms?: boolean, positiveImpactScore?: number, negativeImpactScore?: number, positiveImpactDayOfWeek?: number, positiveImpactTime?: Time, negativeImpactDayOfWeek?: number, negativeImpactTime?: Time, preferredDayOfWeek?: number, preferredTime?: Time, isExternalMeeting?: boolean, isExternalMeetingModifiable?: boolean, isMeetingModifiable?: boolean, isMeeting?: boolean, dailyTaskList?: boolean, weeklyTaskList?: boolean, isBreak?: boolean, preferredStartTimeRange?: Time, preferredEndTimeRange?: Time, copyAvailability?: boolean, copyTimeBlocking?: boolean, copyTimePreference?: boolean, copyReminders?: boolean, copyPriorityLevel?: boolean, copyModifiable?: boolean, copyCategories?: boolean, copyIsBreak?: boolean, timeBlocking?: BufferTimeType, userModifiedAvailability?: boolean, userModifiedTimeBlocking?: boolean, userModifiedTimePreference?: boolean, userModifiedReminders?: boolean, userModifiedPriorityLevel?: boolean, userModifiedCategories?: boolean, userModifiedModifiable?: boolean, userModifiedIsBreak?: boolean, hardDeadline?: string, softDeadline?: string, copyIsMeeting?: boolean, copyIsExternalMeeting?: boolean, userModifiedIsMeeting?: boolean, userModifiedIsExternalMeeting?: boolean, duration?: number, copyDuration?: boolean, userModifiedDuration?: boolean, method?: "create" | "update", unlink?: boolean, byWeekDay?: Day[], priority?: number) => Promise<any>;
export declare const deleteEventForTask: (eventId: string, client: ApolloClient<NormalizedCacheObject>) => Promise<any>;
/**
end
 */
