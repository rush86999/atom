import axios from 'axios';
import { GoogleAttendeeType, ConferenceDataType, extendedProperties, GoogleReminderType, source, TransparencyType, VisibilityType, SendUpdatesType, allowedConferenceSolutionType, attachment, eventType1, DefaultReminderType, NotificationType } from '@lib/calendarLib/types';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { CalendarWebhookType } from '@lib/dataTypes/CalendarWebhookType';
export declare const checkIfCalendarWebhookExpired: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<void>;
export declare const enableCalendarWebhook: (webhook: CalendarWebhookType) => Promise<void>;
export declare const deleteCalendarWebhook: (client: ApolloClient<NormalizedCacheObject>, calendarId: string) => Promise<void>;
export declare const getCalendarWebhook: (client: ApolloClient<NormalizedCacheObject>, calendarId: string) => Promise<any>;
export declare const getGoogleCalendarSyncApiToken: () => Promise<any>;
export declare const houseKeepSyncEnabledGoogleCalendar: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<void>;
export declare const googleMeetAvailable: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<boolean | undefined>;
export declare const getGoogleToken: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<any>;
export declare const patchGoogleCalendar: (client: ApolloClient<NormalizedCacheObject>, userId: string, calendarId: string, summary?: string, description?: string, location?: string, timeZone?: string, allowedConferenceSolutionTypes?: allowedConferenceSolutionType[]) => Promise<void>;
export declare const createGoogleCalendar: (client: ApolloClient<NormalizedCacheObject>, userId: string, id: string, summary: string, defaultReminders?: DefaultReminderType[], notifications?: NotificationType[]) => Promise<void>;
export declare const getGoogleCalendar: (client: ApolloClient<NormalizedCacheObject>, userId: string, calendarId: string) => Promise<axios.AxiosResponse<any, any> | undefined>;
export declare const deleteGoogleEvent: (client: ApolloClient<NormalizedCacheObject>, userId: string, calendarId: string, googleEventId: string, sendUpdates?: SendUpdatesType) => Promise<void>;
export declare const deleteGoogleCalendar: (client: ApolloClient<NormalizedCacheObject>, userId: string, calendarId: string) => Promise<void>;
export declare const getGoogleColors: (token: string) => Promise<any>;
export declare const clearGoogleCalendar: (client: ApolloClient<NormalizedCacheObject>, userId: string, calendarId: string) => Promise<void>;
export declare const patchGoogleEvent: (client: ApolloClient<NormalizedCacheObject>, userId: string, calendarId: string, eventId: string, endDateTime?: string, // either endDateTime or endDate - all day vs specific period
startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: SendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: ConferenceDataType, summary?: string, description?: string, timezone?: string, // required for recurrence
startDate?: string, endDate?: string, extendedProperties?: extendedProperties, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: source, status?: string, transparency?: TransparencyType, visibility?: VisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: attachment[], eventType?: eventType1, location?: string) => Promise<void>;
export declare const createGoogleEvent: (client: ApolloClient<NormalizedCacheObject>, userId: string, calendarId: string, endDateTime?: string, // either endDateTime or endDate - all day vs specific period
startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: SendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: ConferenceDataType, summary?: string, description?: string, timezone?: string, // required for recurrence
startDate?: string, endDate?: string, extendedProperties?: extendedProperties, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: source, status?: string, transparency?: TransparencyType, visibility?: VisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: attachment[], eventType?: eventType1, location?: string) => Promise<any>;
