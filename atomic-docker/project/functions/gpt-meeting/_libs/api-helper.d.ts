import { AttendeeType, ConferenceType, EventType, GoogleAttachmentType, GoogleAttendeeType, GoogleConferenceDataType, GoogleEventType1, GoogleExtendedPropertiesType, GoogleReminderType, GoogleResType, GoogleSendUpdatesType, GoogleSourceType, GoogleTransparencyType, GoogleVisibilityType, ReminderType, UserPreferenceType } from './types/genericTypes';
import OpenAI from 'openai';
import { DayAvailabilityType, NotAvailableSlotType, SummarizeDayAvailabilityType } from './types/availabilityTypes';
export declare const callOpenAI: (prompt: string, model: "gpt-3.5-turbo" | undefined, userData: string, openai: OpenAI, exampleInput?: string, exampleOutput?: string) => Promise<string | null | undefined>;
export declare const getCalendarIntegration: (userId: string, resource: string) => Promise<any>;
export declare const getGlobalCalendar: (userId: string) => Promise<any>;
export declare const updateCalendarIntegration: (id: string, token?: string, expiresIn?: number, enabled?: boolean) => Promise<void>;
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
export declare const refreshZoomToken: (refreshToken: string) => Promise<{
    access_token: string;
    token_type: "bearer";
    refresh_token: string;
    expires_in: number;
    scope: string;
}>;
export declare const getZoomAPIToken: (userId: string) => Promise<any>;
export declare const createZoomMeeting: (zoomToken: string, startDate: string, timezone: string, agenda: string, duration: number, contactName?: string, contactEmail?: string, meetingInvitees?: string[]) => Promise<any>;
export declare const refreshGoogleToken: (refreshToken: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<{
    access_token: string;
    expires_in: number;
    scope: string;
    token_type: string;
}>;
export declare const getGoogleAPIToken: (userId: string, resource: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<any>;
export declare const createGoogleEvent: (userId: string, calendarId: string, clientType: "ios" | "android" | "web" | "atomic-web", generatedId?: string, endDateTime?: string, // either endDateTime or endDate - all day vs specific period
startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: GoogleSendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: GoogleConferenceDataType, summary?: string, description?: string, timezone?: string, // required for recurrence
startDate?: string, // all day
endDate?: string, // all day
extendedProperties?: GoogleExtendedPropertiesType, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: GoogleSourceType, status?: string, transparency?: GoogleTransparencyType, visibility?: GoogleVisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: GoogleAttachmentType[], eventType?: GoogleEventType1, location?: string, colorId?: string) => Promise<GoogleResType>;
export declare const upsertEvents: (events: EventType[]) => Promise<{
    data: {
        insert_Event: {
            affected_rows: number;
            returning: {
                id: string;
            }[];
        };
    };
} | undefined>;
export declare const insertReminders: (reminders: ReminderType[]) => Promise<void>;
export declare const insertConference: (conference: ConferenceType) => Promise<any>;
export declare const processEmailContent: (content: string) => Promise<void>;
export declare const listEventsForUserGivenDates: (userId: string, senderStartDate: string, senderEndDate: string) => Promise<EventType[] | undefined>;
export declare const getUserPreferences: (userId: string) => Promise<UserPreferenceType | null>;
export declare const generateAvailableSlotsForDate: (slotDuration: number, senderStartDateInReceiverTimezone: string, senderPreferences: UserPreferenceType, receiverTimezone: string, senderTimezone: string, notAvailableSlotsInEventTimezone?: NotAvailableSlotType[], isFirstDay?: boolean, isLastDay?: boolean, senderEndDateInReceiverTimezone?: string) => AvailableSlotType[];
export declare const generateAvailableSlotsforTimeWindow: (windowStartDate: string, windowEndDate: string, slotDuration: number, senderPreferences: UserPreferenceType, receiverTimezone: string, senderTimezone: string, notAvailableSlotsInEventTimezone?: NotAvailableSlotType[]) => {
    availableSlots: AvailableSlotType[];
};
export declare const generateAvailability: (userId: string, windowStartDateInSenderTimezone: string, windowEndDateInSenderTimezone: string, senderTimezone: string, receiverTimezone: string, slotDuration: number) => Promise<AvailableSlotType[] | undefined>;
export declare const process_summarize_availability: (body: SummarizeDayAvailabilityType) => Promise<string | null | undefined>;
export declare const process_day_availibility: (body: DayAvailabilityType) => Promise<string | undefined>;
export declare const insertAttendeesforEvent: (attendees: AttendeeType[]) => Promise<void>;
export declare const deleteAttendeesWithIds: (eventIds: string[], userId: string) => Promise<void>;
