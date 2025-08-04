import { CalendarWebhookType, esResponseBody, EventPlusType, EventResourceType, EventType, GoogleAttachmentType, GoogleAttendeeType, GoogleConferenceDataType, GoogleEventType1, GoogleExtendedPropertiesType, GoogleReminderType, GoogleSendUpdatesType, GoogleSourceType, GoogleTransparencyType, GoogleVisibilityType, MeetingAssistAttendeeType, ReminderType, UserPreferenceType } from './types';
import { colorTypeResponse, ConferenceType } from '@/google-calendar-sync/_libs/types/googleCalendarSync/types';
import { EventTriggerType } from '@/google-calendar-sync/_libs/types/googlePeopleSync/types';
import { Readable } from 'stream';
import { EventObjectForVectorType } from '@/google-calendar-sync/_libs/types/event2Vectors/types';
export declare const insertEventTriggers: (objects: EventTriggerType[]) => Promise<void>;
export declare const getEventTriggerByResourceId: (resourceId: string) => Promise<any>;
export declare const deleteEventTriggerById: (id: string) => Promise<void>;
export declare const resetGoogleSyncForCalendar: (calendarId: string, userId: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<any>;
export declare const deleteMeetingAssistsGivenIds: (ids: string[]) => Promise<void>;
export declare const addlocalItemsToEvent2VectorObjects: (localItems: EventResourceType[], event2VectorObjects: EventObjectForVectorType[], calendarId: string) => void;
export declare const incrementalGoogleCalendarSync2: (calendarId: string, userId: string, clientType: "ios" | "android" | "web" | "atomic-web", parentSyncToken: string, parentPageToken?: string, colorItem?: colorTypeResponse) => Promise<boolean>;
export declare const getCalendarWebhookById: (channelId: string) => Promise<any>;
export declare const convertTextToVectorSpace2: (text: string) => Promise<number[]>;
export declare const deleteDocInSearch3: (id: string) => Promise<void>;
export declare const getSearchClient: () => Promise<any>;
export declare const searchData3: (userId: string, searchVector: number[]) => Promise<esResponseBody>;
export declare const deleteCalendarWebhookById: (channelId: string) => Promise<void>;
export declare const stopCalendarWatch: (id: string, resourceId: string) => Promise<void>;
export declare const getCalendarWebhookByCalendarId: (calendarId: string) => Promise<any>;
export declare const upsertEvents2: (events: EventResourceType[], userId: string, calendarId: string, colorItem?: colorTypeResponse) => Promise<null | undefined>;
export declare const upsertConference2: (events: EventResourceType[], userId: string, calendarId: string) => Promise<void>;
export declare const insertCalendarWebhook: (webhook: CalendarWebhookType) => Promise<any>;
export declare const upsertAttendees2: (events: EventResourceType[], userId: string, calendarId: string) => Promise<void>;
export declare const updateGoogleIntegration: (calendarIntegrationId: string, syncEnabled?: boolean) => Promise<void>;
export declare const updateGoogleCalendarTokensInDb: (calendarId: string, syncToken?: string, pageToken?: string) => Promise<void>;
export declare const getCalendarWithId: (calendarId: string) => Promise<any>;
export declare const requestCalendarWatch: (calendarId: string, channelId: string, token: string, userId: string) => Promise<any>;
export declare const listCalendarsForUser: (userId: string) => Promise<CalendarType[] | undefined>;
export declare const insertRemindersGivenEventResource: (events: EventResourceType[], userId: string, calendarId: string) => Promise<void>;
export declare const getGoogleIntegration: (calendarIntegrationId: string) => Promise<{
    token: any;
    refreshToken: any;
    clientType: any;
} | undefined>;
export declare const getGoogleColor: (token: string) => Promise<any>;
export declare const getGoogleCalendarInDb: (calendarId: string) => Promise<{
    pageToken: any;
    syncToken: any;
    id: any;
} | undefined>;
export declare const deleteAttendees: (events: EventResourceType[], calendarId: string) => Promise<void>;
export declare const refreshZoomToken: (refreshToken: string) => Promise<{
    access_token: string;
    token_type: "bearer";
    refresh_token: string;
    expires_in: number;
    scope: string;
}>;
export declare const decryptZoomTokens: (encryptedToken: string, encryptedRefreshToken?: string) => {
    token: string;
    refreshToken: string;
} | {
    token: string;
    refreshToken?: undefined;
};
export declare const encryptZoomTokens: (token: string, refreshToken?: string) => {
    encryptedToken: string;
    encryptedRefreshToken: string;
} | {
    encryptedToken: string;
    encryptedRefreshToken?: undefined;
};
export declare const getZoomIntegration: (userId: string) => Promise<{
    token: string;
    refreshToken: string;
    id: any;
    expiresAt: any;
} | {
    token: string;
    refreshToken?: undefined;
    id: any;
    expiresAt: any;
} | undefined>;
export declare const updateZoomIntegration: (id: string, accessToken: string, expiresIn: number) => Promise<void>;
export declare const getZoomAPIToken: (userId: string) => Promise<any>;
export declare const deleteZoomMeeting: (zoomToken: string, conferenceId: number, scheduleForReminder?: boolean, cancelMeetingReminder?: boolean) => Promise<void>;
export declare const listConferencesWithHosts: (ids: string[]) => Promise<ConferenceType[] | undefined>;
export declare const deleteConferencesInDb: (conferenceIds: string[]) => Promise<void>;
export declare const deleteConferences: (events: {
    eventId: string;
    id: string;
    calendarId: string;
    meetingId: string;
    conferenceId?: string;
}[]) => Promise<void>;
export declare const deleteEvents: (events: EventResourceType[], calendarId: string) => Promise<{
    eventId: string;
    id: string;
    calendarId: string;
    meetingId: string;
    conferenceId?: string;
}[] | undefined>;
export declare const deleteReminders: (events: EventResourceType[], userId: string, calendarId: string) => Promise<void>;
export declare const getUserPreferences: (userId: string) => Promise<UserPreferenceType>;
export declare const convertToTotalWorkingHours: (userPreference: UserPreferenceType, startDate: string, timezone: string) => number;
export declare const listEventsWithIds: (ids: string[]) => Promise<EventType[] | undefined>;
export declare const listEventsForDate: (userId: string, startDate: string, endDate: string, timezone: string) => Promise<EventType[] | undefined>;
export declare const shouldGenerateBreakEventsForDay: (workingHours: number, userPreferences: UserPreferenceType, allEvents: EventPlusType[]) => boolean;
export declare const generateBreaks: (userPreferences: UserPreferenceType, numberOfBreaksToGenerate: number, eventMirror: EventPlusType, globalCalendarId?: string) => EventPlusType[];
export declare const generateBreakEventsForDay: (userPreferences: UserPreferenceType, userId: string, startDate: string, timezone: string, eventsToBeBreaks?: EventPlusType[], globalCalendarId?: string, isFirstDay?: boolean) => Promise<EventPlusType[] | null | undefined>;
export declare const adjustStartDatesForBreakEventsForDay: (allEvents: EventPlusType[], breakEvents: EventPlusType[], userPreference: UserPreferenceType, timezone: string) => EventPlusType[];
export declare const generateBreakEventsForDate: (userPreferences: UserPreferenceType, userId: string, startDate: string, endDate: string, timezone: string, eventsToBeBreaks?: EventPlusType[], globalCalendarId?: string) => Promise<EventPlusType[] | []>;
export declare const upsertEventsPostPlanner: (events: EventType[]) => Promise<{
    data: {
        insert_Event: {
            affected_rows: number;
            returning: {
                id: string;
            }[];
        };
    };
} | undefined>;
export declare const formatRemindersForGoogle: (reminders: ReminderType[]) => GoogleReminderType;
export declare const refreshGoogleToken: (refreshToken: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<{
    access_token: string;
    expires_in: number;
    scope: string;
    token_type: string;
}>;
export declare const updateCalendarIntegration: (id: string, token?: string, expiresIn?: number, enabled?: boolean) => Promise<void>;
export declare const getCalendarIntegration: (userId: string, resource: string) => Promise<any>;
export declare const getGoogleAPIToken: (userId: string, resource: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<any>;
export declare const patchGoogleEvent: (userId: string, calendarId: string, eventId: string, clientType: "ios" | "android" | "web" | "atomic-web", endDateTime?: string, // either endDateTime or endDate - all day vs specific period
startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: GoogleSendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: GoogleConferenceDataType, summary?: string, description?: string, timezone?: string, // required for recurrence
startDate?: string, endDate?: string, extendedProperties?: GoogleExtendedPropertiesType, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: GoogleSourceType, status?: string, transparency?: GoogleTransparencyType, visibility?: GoogleVisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: GoogleAttachmentType[], eventType?: GoogleEventType1, location?: string, colorId?: string) => Promise<void>;
export declare const createGoogleEvent: (userId: string, calendarId: string, clientType: "ios" | "android" | "web" | "atomic-web", generatedId?: string, endDateTime?: string, // either endDateTime or endDate - all day vs specific period
startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: GoogleSendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: GoogleConferenceDataType, summary?: string, description?: string, timezone?: string, // required for recurrence
startDate?: string, // all day
endDate?: string, // all day
extendedProperties?: GoogleExtendedPropertiesType, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: GoogleSourceType, status?: string, transparency?: GoogleTransparencyType, visibility?: GoogleVisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: GoogleAttachmentType[], eventType?: GoogleEventType1, location?: string, colorId?: string) => Promise<{
    id: any;
    generatedId: string | undefined;
} | undefined>;
export declare const postPlannerModifyEventInCalendar: (newEvent: EventPlusType, userId: string, method: "update" | "create", resource: string, isTimeBlocking: boolean, clientType: "ios" | "android" | "web" | "atomic-web", newReminders?: ReminderType[], attendees?: MeetingAssistAttendeeType[], conference?: ConferenceType) => Promise<string | {
    id: string;
    generatedId: string;
}>;
export declare const generateBreakEventsForCalendarSync: (userId: string, timezone: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<void>;
interface GoogleEventPatchAttributes {
    summary?: string;
    description?: string;
    location?: string;
    status?: 'confirmed' | 'tentative' | 'cancelled';
    transparency?: 'opaque' | 'transparent';
    visibility?: 'default' | 'public' | 'private' | 'confidential';
    colorId?: string;
    conferenceData?: Record<string, any> | null;
}
export declare function directUpdateGoogleEventAndHasura(userId: string, calendarId: string, eventId: string, // This is Google's event ID
clientType: 'ios' | 'android' | 'web' | 'atomic-web', updates: Partial<GoogleEventPatchAttributes>): Promise<boolean>;
export declare function streamToString(stream: Readable): Promise<string>;
export declare const addToQueueForVectorSearch: (userId: string, events: EventObjectForVectorType[]) => Promise<void>;
export {};
