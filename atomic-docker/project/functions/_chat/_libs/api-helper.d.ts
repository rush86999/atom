import { Day } from "./constants";
import { EventSchema as LanceDbEventSchema, TrainingEventSchema as LanceDbTrainingEventSchema } from '../../_utils/lancedb_service';
import DateTimeJSONType, { RelativeTimeChangeFromNowType, RelativeTimeFromNowType } from "./datetime/DateTimeJSONJSONType";
import { BufferTimeType, RecurrenceFrequencyType, RecurrenceRuleType, Time } from "./types/EventType";
import { GoogleReminderType } from "./types/GoogleReminderType";
import { GoogleResType } from "./types/GoogleResType";
import { GoogleSendUpdatesType, GoogleAttendeeType, GoogleConferenceDataType, GoogleExtendedPropertiesType, GoogleTransparencyType, GoogleVisibilityType, GoogleSourceType, GoogleAttachmentType, GoogleEventType1, ReminderType } from "./types/GoogleTypes";
import { ConferenceType } from "./types/ConferenceType";
import { EventType } from '@chat/_libs/types/EventType';
import { PreAndPostEventReturnType } from "./types/PreAndPostEventReturnType";
import { AttendeeType } from "./types/AttendeeType";
import DayOfWeekType from "./types/DayOfWeekType";
import ByMonthDayType from "./types/ByMonthDayType";
import { MeetingAssistType } from "./types/MeetingAssistType";
import { TaskType } from "./types/TaskType";
export declare const openTrainEventIndex = "knn-open-train-event-index";
export declare const openTrainEventVectorName = "embeddings";
export declare const searchSingleEventByVectorLanceDb: (userId: string, searchVector: number[]) => Promise<LanceDbEventSchema | null>;
export declare const searchSingleEventByVectorWithDatesLanceDb: (userId: string, qVector: number[], startDate: string, endDate: string) => Promise<LanceDbEventSchema | null>;
export declare const searchMultipleEventsByVectorWithDatesLanceDb: (userId: string, qVector: number[], startDate: string, endDate: string, limit?: number) => Promise<LanceDbEventSchema[]>;
export declare const upsertConference: (conference: ConferenceType) => Promise<ConferenceType>;
export declare const insertReminders: (reminders: ReminderType[]) => Promise<void>;
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
export declare const putDataInTrainEventIndexInOpenSearch: (id: string, vector: number[], userId: string) => Promise<void>;
export declare const getEventVectorFromLanceDb: (id: string) => Promise<number[] | null>;
export declare const upsertEventToLanceDb: (id: string, vector: number[], userId: string, start_date: string, end_date: string, title: string) => Promise<void>;
export declare const deleteEventFromLanceDb: (id: string) => Promise<void>;
export declare const deleteTrainingDataFromLanceDb: (id: string) => Promise<void>;
export declare const updateTrainingDataInLanceDb: (id: string, vector: number[], userId: string, source_event_text: string) => Promise<void>;
export declare const searchTrainingDataFromLanceDb: (userId: string, searchVector: number[]) => Promise<LanceDbTrainingEventSchema | null>;
export declare const convertEventTitleToOpenAIVector: (title: string) => Promise<number[] | undefined>;
export declare const eventSearchBoundary: (timezone: string, dateJSONBody: DateTimeJSONType, currentTime: string) => {
    startDate: string;
    endDate: string;
};
export declare const extrapolateDateFromJSONData: (currentTime: string, timezone: string, year: string | null | undefined, month: string | null | undefined, day: string | null | undefined, isoWeekday: number | null | undefined, hour: number | null | undefined, minute: number | null | undefined, time: Time | null | undefined, relativeTimeChangeFromNow: RelativeTimeChangeFromNowType | null | undefined, relativeTimeFromNow: RelativeTimeFromNowType[] | null | undefined) => string;
export declare const extrapolateStartDateFromJSONData: (currentTime: string, timezone: string, year: string | null | undefined, month: string | null | undefined, day: string | null | undefined, isoWeekday: number | null | undefined, hour: number | null | undefined, minute: number | null | undefined, time: Time | null | undefined, relativeTimeChangeFromNow: RelativeTimeChangeFromNowType | null | undefined, relativeTimeFromNow: RelativeTimeFromNowType[] | null | undefined) => string;
export declare const extrapolateEndDateFromJSONData: (currentTime: string, timezone: string, year: string | null | undefined, month: string | null | undefined, day: string | null | undefined, isoWeekday: number | null | undefined, hour: number | null | undefined, minute: number | null | undefined, time: Time | null | undefined, relativeTimeChangeFromNow: RelativeTimeChangeFromNowType | null | undefined, relativeTimeFromNow: RelativeTimeFromNowType[] | null | undefined) => string;
export declare const getGlobalCalendar: (userId: string) => Promise<any>;
export declare const getCalendarIntegrationByResource: (userId: string, resource: string) => Promise<CalendarIntegrationType>;
export declare const getCalendarIntegrationByName: (userId: string, name: string) => Promise<CalendarIntegrationType>;
export declare const getZoomIntegration: (userId: string) => Promise<{
    token: string;
    refreshToken: string;
    id: CalendarIntegrationType;
    expiresAt: CalendarIntegrationType;
} | {
    token: string;
    refreshToken?: undefined;
    id: CalendarIntegrationType;
    expiresAt: CalendarIntegrationType;
} | undefined>;
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
export declare const updateCalendarIntegration: (id: string, token?: string, expiresIn?: number, enabled?: boolean) => Promise<void>;
export declare const updateZoomIntegration: (id: string, accessToken: string, expiresIn: number) => Promise<void>;
export declare const refreshZoomToken: (refreshToken: string) => Promise<{
    access_token: string;
    token_type: "bearer";
    refresh_token: string;
    expires_in: number;
    scope: string;
}>;
export declare const getZoomAPIToken: (userId: string) => Promise<string | undefined>;
export declare const deleteRemindersWithIds: (eventIds: string[], userId: string) => Promise<void>;
export declare const updateZoomMeeting: any;
export declare const updateZoomMeeting: (zoomToken: string, meetingId: number, startDate?: string, timezone?: string, agenda?: string, duration?: number, contactName?: string, contactEmail?: string, meetingInvitees?: string[], privateMeeting?: boolean, recur?: RecurrenceRuleType) => Promise<void>;
export declare const getNumberForWeekDay: (day: DayOfWeekType) => "1" | "4" | "6" | "2" | "3" | "5" | "7" | undefined;
export declare const getNumberInString: (byWeekDays: DayOfWeekType[]) => string;
export declare const createZoomMeeting: (zoomToken: string, startDate: string, timezone: string, agenda: string, duration: number, contactName?: string, contactEmail?: string, meetingInvitees?: string[], recur?: RecurrenceRuleType) => Promise<ZoomMeetingObjectType>;
export declare const getGoogleAPIToken: (userId: string, name: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<any>;
export declare const createGoogleEvent: (userId: string, calendarId: string, clientType: "ios" | "android" | "web" | "atomic-web", generatedId?: string, endDateTime?: string, // either endDateTime or endDate - all day vs specific period
startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: GoogleSendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: GoogleConferenceDataType, summary?: string, description?: string, timezone?: string, // required for recurrence
startDate?: string, // all day
endDate?: string, // all day
extendedProperties?: GoogleExtendedPropertiesType, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: GoogleSourceType, status?: string, transparency?: GoogleTransparencyType, visibility?: GoogleVisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: GoogleAttachmentType[], eventType?: GoogleEventType1, location?: string, colorId?: string) => Promise<GoogleResType>;
export declare const patchGoogleEvent: (userId: string, calendarId: string, eventId: string, clientType: "ios" | "android" | "web" | "atomic-web", endDateTime?: string, // either endDateTime or endDate - all day vs specific period
startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: GoogleSendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: GoogleConferenceDataType, summary?: string, description?: string, timezone?: string, // required for recurrence
startDate?: string, endDate?: string, extendedProperties?: GoogleExtendedPropertiesType, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: GoogleSourceType, status?: string, transparency?: GoogleTransparencyType, visibility?: GoogleVisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: GoogleAttachmentType[], eventType?: GoogleEventType1, location?: string, colorId?: string) => Promise<void>;
export declare const insertAttendeesforEvent: (retries: 3, factor: 2, minTimeout: 1000, maxTimeout: 10000, onRetry: (error: any, attemptNumber: any) => {}, chatApiHelperLogger: any, warn: any) => any;
export declare const getEventFromPrimaryKey: (eventId: string) => Promise<EventType>;
export declare const getTaskGivenId: (id: string) => Promise<TaskType>;
export declare const createPreAndPostEventsFromEvent: (event: EventType, bufferTime: BufferTimeType) => PreAndPostEventReturnType;
export declare const upsertAttendeesforEvent: (attendees: AttendeeType[]) => Promise<void>;
export declare const getRRuleDay: (value: Day | undefined) => any;
export declare const getRRuleByWeekDay: (value: DayOfWeekType | undefined) => any;
export declare const createRRuleString: (frequency: RecurrenceFrequencyType, interval: number, byWeekDay?: DayOfWeekType[] | null, count?: number | null, recurringEndDate?: string, byMonthDay?: ByMonthDayType[]) => any[] | undefined;
export declare const upsertMeetingAssistOne: (meetingAssist: MeetingAssistType) => Promise<void>;
