interface SuccessResponseType<T> {
    success: true;
    data: T;
}
interface GenericSuccessResponse {
    success: true;
}
interface FailureResponseType {
    success: false;
    error: {
        message: string;
        details?: any;
        rawResponse?: string;
        parsedResponse?: any;
    };
}
interface OpenAIErrorResponse {
    type: 'OPENAI_API_ERROR';
    status: number;
    data: any;
    message: string;
}
interface OpenAIRequestErrorResponse {
    type: 'OPENAI_REQUEST_ERROR';
    message: string;
}
interface OpenAISuccessResponse {
    success: true;
    content: string | null | undefined;
}
interface OpenAIFailureResponse {
    success: false;
    error: OpenAIErrorResponse | OpenAIRequestErrorResponse;
}
type CallOpenAIResponse = OpenAISuccessResponse | OpenAIFailureResponse;
export interface CalendarIntegrationType {
    id: string;
    userId: string;
    clientType: 'ios' | 'android' | 'web' | 'atomic-web';
    token: string | null;
    refreshToken: string | null;
    expiresAt: string | null;
    resource: string;
    syncEnabled?: boolean;
    primaryCalendarId?: string;
}
export interface GoogleTokenResponseType {
    access_token: string;
    expires_in: number;
    scope?: string;
    token_type?: string;
    id_token?: string;
}
interface CreateGoogleEventSuccessData {
    id: string;
    googleEventId: string;
    generatedId: string;
    calendarId: string;
    generatedEventId?: string;
}
type CreateGoogleEventResponse = {
    success: true;
    data: CreateGoogleEventSuccessData;
} | FailureResponseType;
export interface EventType {
    id: string;
    userId: string;
    calendarId: string;
    gEventId?: string | null;
    provider?: string | null;
    summary?: string | null;
    description?: string | null;
    startDateTime?: string | null;
    endDateTime?: string | null;
    timezone?: string | null;
    status?: string | null;
    isDeleted?: boolean | null;
    parentEventId?: string | null;
    taskId?: string | null;
    projectId?: string | null;
    createdAt?: string;
    updatedAt?: string;
}
export interface GlobalCalendarType extends CalendarIntegrationType {
}
export interface UserPreferenceType {
    id: string;
    userId: string;
    somePreference?: string;
    workHoursStartTime?: string;
    workHoursEndTime?: string;
    workDays?: number[];
    slotDuration?: number;
    timezone?: string;
    bufferBetweenMeetings?: number;
}
type EmailResponse = GenericSuccessResponse | FailureResponseType;
interface AvailabilitySlot {
    startDate: string;
    endDate: string;
}
export declare const callOpenAI: (systemMessage: string, userMessage: string, exampleInput?: string, exampleOutput?: string, model?: string) => Promise<CallOpenAIResponse>;
export declare const getCalendarIntegration: (userId: string, resource: string) => Promise<SuccessResponseType<CalendarIntegrationType | undefined> | FailureResponseType>;
export declare const refreshGoogleToken: (refreshTokenVal: string, clientType: CalendarIntegrationType["clientType"]) => Promise<SuccessResponseType<GoogleTokenResponseType> | FailureResponseType>;
export declare const updateCalendarIntegration: (id: string, token: string | null, expiresAt: string | null, refreshTokenVal?: string | null, syncEnabled?: boolean) => Promise<GenericSuccessResponse | FailureResponseType>;
export declare const getGoogleAPIToken: (userId: string, resource: string) => Promise<{
    success: true;
    token: string;
} | FailureResponseType>;
export declare const createGoogleEvent: (userId: string, calendarIdVal: string, clientTypeVal: CalendarIntegrationType["clientType"], summaryVal: string, startDateTimeVal: string, endDateTimeVal: string, timezoneVal: string, descriptionVal?: string, attendeesVal?: {
    email: string;
}[], conferenceSolutionVal?: "eventHangout" | "hangoutsMeet" | null) => Promise<CreateGoogleEventResponse>;
export declare const getGlobalCalendar: (userId: string) => Promise<SuccessResponseType<GlobalCalendarType | undefined> | FailureResponseType>;
export declare const listEventsForDate: (userId: string, startDate: string, endDate: string, timezoneParam: string) => Promise<SuccessResponseType<EventType[]> | FailureResponseType>;
export declare const listEventsForUserGivenDates: (userId: string, senderStartDate: string, senderEndDate: string) => Promise<SuccessResponseType<EventType[]> | FailureResponseType>;
export declare const getUserPreferences: (userId: string) => Promise<SuccessResponseType<UserPreferenceType | undefined> | FailureResponseType>;
export declare const sendAgendaEmail: (to: string, name: string, title: string, body: string) => Promise<EmailResponse>;
export declare const sendSummaryEmail: (to: string, name: string, title: string, summary: string) => Promise<EmailResponse>;
export declare const emailTaskBreakDown: (to: string, name: string, title: string, tasks: string) => Promise<EmailResponse>;
export declare const sendGenericTaskEmail: (to: string, name: string, title: string, body: string) => Promise<EmailResponse>;
export declare const sendMeetingRequestTemplate: (to: string, name: string, title: string, body: string, yesLink: string, noLink: string) => Promise<EmailResponse>;
export declare const createAgenda: (userId: string, clientType: CalendarIntegrationType["clientType"], userTimezone: string, userDate: string, promptVal: string, email?: string, nameVal?: string) => Promise<GenericSuccessResponse | FailureResponseType>;
export declare const createSummaryOfTimePeriod: (userId: string, startDate: string, endDate: string, timezone: string, email?: string, name?: string) => Promise<SuccessResponseType<string> | FailureResponseType>;
export declare const breakDownTask: (userId: string, clientType: CalendarIntegrationType["clientType"], userTimezone: string, taskTitle: string, taskDescription: string, isAllDay: boolean, startDate: string, endDate: string, email?: string, name?: string) => Promise<GenericSuccessResponse | FailureResponseType>;
export declare const howToTask: (userId: string, clientType: CalendarIntegrationType["clientType"], userTimezone: string, taskTitle: string, isAllDay: boolean, startDate: string, endDate: string, email?: string, name?: string) => Promise<GenericSuccessResponse | FailureResponseType>;
export declare const meetingRequest: (userId: string, clientType: CalendarIntegrationType["clientType"], userTimezone: string, userDateContext: string, attendees: string, subject: string, promptVal: string, durationMinutes: number, shareAvailability: boolean, availabilityUserDateStart?: string, availabilityUserDateEnd?: string, emailTo?: string, emailName?: string, yesLink?: string, noLink?: string) => Promise<GenericSuccessResponse | FailureResponseType>;
export declare const createDaySchedule: (userId: string, clientType: CalendarIntegrationType["clientType"], userDate: string, userTimezone: string, prompt: string, isAllDay: boolean, email?: string, name?: string) => Promise<GenericSuccessResponse | FailureResponseType>;
export declare const generateAvailableSlotsForDate: (date: string, // YYYY-MM-DD format for the target day
senderPreferences: UserPreferenceType, // Contains work hours, slot duration, timezone
notAvailableSlotsInEventTimezone: AvailabilitySlot[], // Existing busy slots for the user, in event's target timezone
receiverTimezone: string, // Timezone for which the slots should be presented
isFirstDay: boolean, // Is this the first day of the overall window?
isLastDay: boolean, // Is this the last day of the overall window?
windowStartTimeInReceiverTimezone?: string, // HH:mm, only if isFirstDay is true
windowEndTimeInReceiverTimezone?: string) => AvailabilitySlot[];
export declare const generateAvailableSlotsforTimeWindow: (startDate: string, // YYYY-MM-DD
endDate: string, // YYYY-MM-DD
senderPreferences: UserPreferenceType, notAvailableFromEvents: EventType[], // All events for the user within a broader range
receiverTimezone: string, windowStartTimeInReceiverTimezone?: string, // HH:mm for the first day
windowEndTimeInReceiverTimezone?: string) => {
    availableSlots: AvailabilitySlot[];
};
export declare const generateAvailability: (userId: string, availabilityScanStartDate: string, // YYYY-MM-DD
availabilityScanEndDate: string, // YYYY-MM-DD
receiverGeneratedTimezone: string) => Promise<SuccessResponseType<AvailabilitySlot[]> | FailureResponseType>;
export {};
