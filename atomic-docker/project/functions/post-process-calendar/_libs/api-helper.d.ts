import { BufferTimeNumberType, EventPlusType, EventType, MeetingAssistAttendeeType, MeetingAssistEventType, MeetingAssistPreferredTimeRangeType, MeetingAssistType, EventMeetingPlusType, PreferredTimeRangeType, RemindersForEventType, ValuesToReturnForBufferEventsType, UserPreferenceType, WorkTimeType, TimeSlotType, MonthType, DayType, MonthDayType, EventPartPlannerRequestBodyType, InitialEventPartType, InitialEventPartTypePlus, UserPlannerRequestBodyType, ReturnBodyForHostForOptaplannerPrepType, ReturnBodyForAttendeeForOptaplannerPrepType, ReturnBodyForExternalAttendeeForOptaplannerPrepType, esResponseBody, CategoryType, classificationResponseBody as ClassificationResponseBodyType, BufferTimeObjectType, ReminderType, CategoryEventType, EventPlannerResponseBodyType, ReminderTypeAdjusted, GoogleReminderType, GoogleSendUpdatesType, GoogleAttendeeType, GoogleConferenceDataType, GoogleExtendedPropertiesType, GoogleSourceType, GoogleTransparencyType, GoogleVisibilityType, GoogleAttachmentType, GoogleEventType1, ConferenceType, CreateGoogleEventResponseType, AttendeeType } from '@post_process_calendar/_libs/types';
import { Client } from '@opensearch-project/opensearch';
import { Readable } from 'stream';
export declare function streamToString(stream: Readable): Promise<string>;
export declare const getSearchClient: () => Promise<Client | undefined>;
export declare const searchData3: (userId: string, searchVector: number[]) => Promise<esResponseBody>;
export declare const convertEventToVectorSpace2: (event: EventType) => Promise<number[]>;
export declare const listMeetingAssistPreferredTimeRangesGivenMeetingId: (meetingId: string) => Promise<MeetingAssistPreferredTimeRangeType[] | undefined>;
export declare const listMeetingAssistAttendeesGivenMeetingId: (meetingId: string) => Promise<MeetingAssistAttendeeType[] | undefined>;
export declare const getMeetingAssistAttendee: (id: string) => Promise<any>;
export declare const getMeetingAssist: (id: string) => Promise<any>;
export declare const listMeetingAssistEventsForAttendeeGivenDates: (attendeeId: string, hostStartDate: string, hostEndDate: string, userTimezone: string, hostTimezone: string) => Promise<MeetingAssistEventType[] | undefined>;
export declare const listEventsForDate: (userId: string, startDate: string, endDate: string, timezone: string) => Promise<EventType[] | undefined>;
export declare const processMeetingAssistForOptaplanner: () => Promise<void>;
export declare const generateNewMeetingEventForAttendee: (attendee: MeetingAssistAttendeeType, meetingAssist: MeetingAssistType, windowStartDate: string, hostTimezone: string, preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType) => EventType;
export declare const generateNewMeetingEventForHost: (hostAttendee: MeetingAssistAttendeeType, meetingAssist: MeetingAssistType, windowStartDate: string, hostTimezone: string, preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType) => EventType;
export declare const listPreferredTimeRangesForEvent: (eventId: string) => Promise<PreferredTimeRangeType[] | undefined>;
export declare const createRemindersFromMinutesAndEvent: (eventId: string, minutes: number[], timezone: string, useDefault: boolean, userId: string) => RemindersForEventType;
export declare const createBufferTimeForNewMeetingEvent: (event: EventMeetingPlusType, bufferTime: BufferTimeNumberType) => ValuesToReturnForBufferEventsType;
export declare const getUserPreferences: (userId: string) => Promise<UserPreferenceType>;
export declare const getGlobalCalendar: (userId: string) => Promise<any>;
export declare const adjustStartDatesForBreakEventsForDay: (allEvents: EventPlusType[], breakEvents: EventPlusType[], userPreference: UserPreferenceType, timezone: string) => EventPlusType[];
export declare const convertToTotalWorkingHoursForInternalAttendee: (userPreference: UserPreferenceType, hostStartDate: string, hostTimezone: string) => number;
export declare const convertToTotalWorkingHoursForExternalAttendee: (attendeeEvents: EventPlusType[], hostStartDate: string, hostTimezone: string, userTimezone: string) => number;
export declare const generateBreaks: (userPreferences: UserPreferenceType, numberOfBreaksToGenerate: number, eventMirror: EventPlusType, globalCalendarId?: string) => EventPlusType[];
export declare const shouldGenerateBreakEventsForDay: (workingHours: number, userPreferences: UserPreferenceType, allEvents: EventPlusType[]) => boolean;
export declare const generateBreakEventsForDay: (userPreferences: UserPreferenceType, userId: string, hostStartDate: string, hostTimezone: string, globalCalendarId?: string, isFirstDay?: boolean) => Promise<EventPlusType[] | null | undefined>;
export declare const generateBreakEventsForDate: (userPreferences: UserPreferenceType, userId: string, hostStartDate: string, hostEndDate: string, hostTimezone: string, globalCalendarId?: string) => Promise<EventPlusType[] | []>;
export declare const generateWorkTimesForInternalAttendee: (hostId: string, userId: string, userPreference: UserPreferenceType, hostTimezone: string, userTimezone: string) => WorkTimeType[];
export declare const generateTimeSlotsForInternalAttendee: (hostStartDate: string, hostId: string, userPreference: UserPreferenceType, hostTimezone: string, userTimezone: string, isFirstDay?: boolean) => TimeSlotType[];
export declare const generateTimeSlotsLiteForInternalAttendee: (hostStartDate: string, hostId: string, userPreference: UserPreferenceType, hostTimezone: string, userTimezone: string, isFirstDay?: boolean) => TimeSlotType[];
export declare const validateEventDates: (event: EventPlusType, userPreferences: UserPreferenceType) => boolean;
export declare const validateEventDatesForExternalAttendee: (event: EventPlusType) => boolean;
export declare const generateEventParts: (event: EventPlusType, hostId: string) => InitialEventPartType[];
export declare const generateEventPartsLite: (event: EventPlusType, hostId: string) => InitialEventPartType[];
export declare const modifyEventPartsForSingularPreBufferTime: (eventParts: InitialEventPartType[], forEventId: string) => InitialEventPartType[];
export declare const modifyEventPartsForMultiplePreBufferTime: (eventParts: InitialEventPartType[]) => InitialEventPartType[];
export declare const modifyEventPartsForMultiplePostBufferTime: (eventParts: InitialEventPartType[]) => InitialEventPartType[];
export declare const modifyEventPartsForSingularPostBufferTime: (eventParts: InitialEventPartType[], forEventId: string) => InitialEventPartType[];
export declare const formatEventTypeToPlannerEvent: (event: InitialEventPartTypePlus, userPreference: UserPreferenceType, workTimes: WorkTimeType[], hostTimezone: string) => EventPartPlannerRequestBodyType;
export declare const formatEventTypeToPlannerEventForExternalAttendee: (event: InitialEventPartTypePlus, workTimes: WorkTimeType[], attendeeEvents: EventPlusType[], hostTimezone: string) => EventPartPlannerRequestBodyType;
export declare const convertMeetingPlusTypeToEventPlusType: (event: EventMeetingPlusType) => EventPlusType;
export declare const setPreferredTimeForUnModifiableEvent: (event: EventPartPlannerRequestBodyType, timezone: string) => EventPartPlannerRequestBodyType;
export declare const listEventsWithIds: (ids: string[]) => Promise<EventType[] | undefined>;
export declare const tagEventsForDailyOrWeeklyTask: (events: EventPartPlannerRequestBodyType[]) => Promise<EventPartPlannerRequestBodyType[] | null>;
export declare const tagEventForDailyOrWeeklyTask: (eventToSubmit: EventPartPlannerRequestBodyType, event: EventPlusType) => any;
export declare const generateUserPlannerRequestBody: (userPreference: UserPreferenceType, userId: string, workTimes: WorkTimeType[], hostId: string) => UserPlannerRequestBodyType;
export declare const generateUserPlannerRequestBodyForExternalAttendee: (userId: string, workTimes: WorkTimeType[], hostId: string) => UserPlannerRequestBodyType;
export declare const processEventsForOptaPlannerForMainHost: (mainHostId: string, allHostEvents: EventPlusType[], windowStartDate: string, windowEndDate: string, hostTimezone: string, oldHostEvents: EventPlusType[], newHostReminders?: RemindersForEventType[], newHostBufferTimes?: BufferTimeObjectType[]) => Promise<ReturnBodyForHostForOptaplannerPrepType>;
export declare const processEventsForOptaPlannerForInternalAttendees: (mainHostId: string, allEvents: EventPlusType[], windowStartDate: string, windowEndDate: string, hostTimezone: string, internalAttendees: MeetingAssistAttendeeType[], oldEvents: EventType[], oldMeetingEvents: EventMeetingPlusType[], newHostReminders?: RemindersForEventType[], newHostBufferTimes?: BufferTimeObjectType[]) => Promise<ReturnBodyForAttendeeForOptaplannerPrepType>;
export declare const convertMeetingAssistEventTypeToEventPlusType: (event: MeetingAssistEventType, userId: string) => EventPlusType;
export declare const generateWorkTimesForExternalAttendee: (hostId: string, userId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string) => WorkTimeType[];
export declare const generateTimeSlotsForExternalAttendee: (hostStartDate: string, hostId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string, isFirstDay?: boolean) => TimeSlotType[];
export declare const generateTimeSlotsLiteForExternalAttendee: (hostStartDate: string, hostId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string, isFirstDay?: boolean) => TimeSlotType[];
export declare const processEventsForOptaPlannerForExternalAttendees: (userIds: string[], mainHostId: string, allExternalEvents: MeetingAssistEventType[], windowStartDate: string, windowEndDate: string, hostTimezone: string, externalAttendees: MeetingAssistAttendeeType[], oldExternalMeetingEvents?: EventMeetingPlusType[]) => Promise<ReturnBodyForExternalAttendeeForOptaplannerPrepType>;
export declare const optaPlanWeekly: (timeslots: TimeSlotType[], userList: UserPlannerRequestBodyType[], eventParts: EventPartPlannerRequestBodyType[], singletonId: string, hostId: string, fileKey: string, delay: number, callBackUrl: string) => Promise<void>;
export declare const updateFreemiumById: (id: string, usage: number) => Promise<any>;
export declare const getFreemiumByUserId: (userId: string) => Promise<any>;
export declare const processEventsForOptaPlanner: (mainHostId: string, internalAttendees: MeetingAssistAttendeeType[], meetingEventPlus: EventMeetingPlusType[], allEvents: EventPlusType[], windowStartDate: string, windowEndDate: string, hostTimezone: string, oldEvents: EventType[], externalAttendees?: MeetingAssistAttendeeType[], meetingAssistEvents?: MeetingAssistEventType[], newHostReminders?: RemindersForEventType[], newHostBufferTimes?: BufferTimeObjectType[]) => Promise<void>;
export declare const getUserCategories: (userId: any) => Promise<CategoryType[] | undefined>;
export declare const findBestMatchCategory2: (event: EventPlusType, possibleLabels: CategoryType[]) => Promise<ClassificationResponseBodyType>;
export declare const processBestMatchCategories: (body: ClassificationResponseBodyType, newPossibleLabels: string[]) => string;
export declare const processEventForMeetingTypeCategories: (newEvent: EventPlusType, bestMatchCategory: CategoryType, newPossibleLabels: string[], scores: number[], categories: CategoryType[]) => CategoryType[] | [];
export declare const getUniqueLabels: (labels: CategoryType[]) => CategoryType[];
export declare const copyOverCategoryDefaults: (event: EventPlusType, category: CategoryType) => EventPlusType;
export declare const createRemindersAndTimeBlockingForBestMatchCategory: (id: string, userId: string, newEvent: EventPlusType, bestMatchCategory: CategoryType, newReminders1?: ReminderType[], newTimeBlocking1?: BufferTimeObjectType, previousEvent?: EventPlusType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: any;
} | undefined>;
export declare const createCategoryEvents: (categoryEvents: CategoryEventType[]) => Promise<void>;
export declare const listRemindersForEvent: (eventId: string, userId: string) => Promise<ReminderType[] | undefined>;
export declare const createRemindersUsingCategoryDefaultsForEvent: (event: EventPlusType, bestMatchCategory: CategoryType, oldReminders: ReminderType[], previousEvent: EventPlusType) => ReminderType[];
export declare const createPreAndPostEventsForCategoryDefaults: (bestMatchCategory: CategoryType, event: EventPlusType, previousEvent?: EventPlusType) => any;
export declare const updateValuesForMeetingTypeCategories: (event: any, newEvent1: EventPlusType, bestMatchCategories: CategoryType[], userId: string, newReminders1?: ReminderType[], newTimeBlocking1?: {
    beforeEvent?: EventPlusType;
    afterEvent?: EventPlusType;
}, previousEvent?: EventPlusType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: {
        beforeEvent?: EventPlusType;
        afterEvent?: EventPlusType;
    };
} | undefined>;
export declare const processUserEventForCategoryDefaults: (event: EventPlusType, vector: number[]) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
} | {
    newEvent: EventPlusType;
    newReminders?: undefined;
    newTimeBlocking?: undefined;
} | undefined>;
export declare const listCategoriesForEvent: (eventId: string) => Promise<CategoryType[] | undefined>;
export declare const processBestMatchCategoriesNoThreshold: (body: any, newPossibleLabels: any) => string;
export declare const processUserEventForCategoryDefaultsWithUserModifiedCategories: (event: EventPlusType, vector: number[]) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: any;
} | undefined>;
export declare const getEventFromPrimaryKey: (eventId: string) => Promise<EventPlusType>;
export declare const deleteDocInSearch3: (id: string) => Promise<void>;
export declare const copyOverPreviousEventDefaults: (event: EventPlusType, previousEvent: EventPlusType, category?: CategoryType, userPreferences?: UserPreferenceType) => EventPlusType;
export declare const createPreAndPostEventsFromPreviousEvent: (event: EventPlusType, previousEvent: EventPlusType) => any;
export declare const createRemindersFromPreviousEventForEvent: (event: EventPlusType, previousEvent: EventPlusType, userId: string) => Promise<ReminderType[]>;
export declare const copyOverCategoryMeetingAndExternalMeetingDefaultsWithFoundPreviousEvent: (event: EventPlusType, categories: CategoryType[], userPreferences: UserPreferenceType, previousEvent: EventPlusType) => {
    newEventMeeting: any;
    newEventExternal: any;
} | undefined;
export declare const createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences: (userId: string, newEvent: EventPlusType, newReminders1?: ReminderType[], newTimeBlocking1?: BufferTimeObjectType, previousEvent?: EventPlusType, userPreferences?: UserPreferenceType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: any;
} | undefined>;
export declare const updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting: (event: EventPlusType, newEvent1: EventPlusType, bestMatchCategories: CategoryType[], newReminders1: ReminderType[], newTimeBlocking1: BufferTimeObjectType, userId: string, userPreferences: UserPreferenceType, previousEvent: EventPlusType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: any;
} | undefined>;
export declare const createRemindersAndTimeBlockingFromPreviousEvent: (userId: string, newEvent: EventPlusType, newReminders1: ReminderType[], newTimeBlocking1: BufferTimeObjectType, previousEvent?: EventPlusType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: any;
} | undefined>;
export declare const processEventWithFoundPreviousEventAndCopyCategories: (id: string, previousEvent: EventPlusType, oldEvent: EventPlusType, userPreferences: UserPreferenceType, bestMatchCategory1: CategoryType, userId: string, bestMatchCategories1: CategoryType[], newModifiedEvent1: EventPlusType, newReminders1?: ReminderType[], newTimeBlocking1?: BufferTimeObjectType, previousCategories?: CategoryType[], previousMeetingCategoriesWithMeetingLabel?: CategoryType[], previousMeetingCategoriesWithExternalMeetingLabel?: CategoryType[]) => Promise<{
    newModifiedEvent: any;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
} | null | undefined>;
export declare const processEventWithFoundPreviousEventWithoutCategories: (previousEvent: EventPlusType, event: EventPlusType, userPreferences: UserPreferenceType, userId: string, newReminders?: ReminderType[], newTimeBlocking?: BufferTimeObjectType) => Promise<{
    newModifiedEvent: any;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
} | null | undefined>;
export declare const processUserEventWithFoundPreviousEvent: (event: EventPlusType, previousEventId: string) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
} | undefined>;
export declare const processUserEventWithFoundPreviousEventWithUserModifiedCategories: (event: EventPlusType, previousEventId: string) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
} | undefined>;
export declare const deleteOptaPlan: (userId: string) => Promise<void>;
export declare const validateEventsFromOptaplanner: (unsortedEvents: EventPlannerResponseBodyType[]) => void;
export declare const getMonthDayFromSlot: (monthDay: MonthDayType) => {
    month: MonthType;
    day: DayType;
};
export declare const formatPlannerEventsToEventAndAdjustTime: (events: EventPlannerResponseBodyType[], oldEvent: EventPlusType, hostTimezone: string) => EventPlusType;
export declare const putDataInSearch: (id: string, vector: number[], userId: string) => Promise<void>;
export declare const compareEventsToFilterUnequalEvents: (newEvent: EventPlusType, oldEvent?: EventPlusType) => boolean;
export declare const getCalendarWithId: (calendarId: string) => Promise<any>;
export declare const getCalendarIntegration: (userId: string, resource: string) => Promise<any>;
export declare const formatRemindersForGoogle: (reminders: ReminderType[]) => GoogleReminderType;
export declare const refreshZoomToken: (refreshToken: string) => Promise<{
    access_token: string;
    token_type: "bearer";
    refresh_token: string;
    expires_in: number;
    scope: string;
}>;
export declare const refreshGoogleToken: (refreshToken: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<{
    access_token: string;
    expires_in: number;
    scope: string;
    token_type: string;
}>;
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
export declare const getZoomAPIToken: (userId: string) => Promise<any>;
export declare const getGoogleAPIToken: (userId: string, resource: string, clientType: "ios" | "android" | "web" | "atomic-web") => Promise<any>;
export declare const patchGoogleEvent: (userId: string, calendarId: string, eventId: string, clientType: "ios" | "android" | "web" | "atomic-web", endDateTime?: string, startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: GoogleSendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: GoogleConferenceDataType, summary?: string, description?: string, timezone?: string, startDate?: string, endDate?: string, extendedProperties?: GoogleExtendedPropertiesType, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: GoogleSourceType, status?: string, transparency?: GoogleTransparencyType, visibility?: GoogleVisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: GoogleAttachmentType[], eventType?: GoogleEventType1, location?: string, colorId?: string) => Promise<void>;
export declare const createGoogleEventWithId: (userId: string, calendarId: string, clientType: "ios" | "android" | "web" | "atomic-web", eventId: string, endDateTime?: string, startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: GoogleSendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: GoogleConferenceDataType, summary?: string, description?: string, timezone?: string, startDate?: string, endDate?: string, extendedProperties?: GoogleExtendedPropertiesType, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: GoogleSourceType, status?: string, transparency?: GoogleTransparencyType, visibility?: GoogleVisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: GoogleAttachmentType[], eventType?: GoogleEventType1, location?: string, colorId?: string) => Promise<void>;
export declare const createGoogleEvent: (userId: string, calendarId: string, clientType: "ios" | "android" | "web" | "atomic-web", generatedId?: string, endDateTime?: string, startDateTime?: string, conferenceDataVersion?: 0 | 1, maxAttendees?: number, sendUpdates?: GoogleSendUpdatesType, anyoneCanAddSelf?: boolean, attendees?: GoogleAttendeeType[], conferenceData?: GoogleConferenceDataType, summary?: string, description?: string, timezone?: string, startDate?: string, endDate?: string, extendedProperties?: GoogleExtendedPropertiesType, guestsCanInviteOthers?: boolean, guestsCanModify?: boolean, guestsCanSeeOtherGuests?: boolean, originalStartDateTime?: string, originalStartDate?: string, recurrence?: string[], reminders?: GoogleReminderType, source?: GoogleSourceType, status?: string, transparency?: GoogleTransparencyType, visibility?: GoogleVisibilityType, iCalUID?: string, attendeesOmitted?: boolean, hangoutLink?: string, privateCopy?: boolean, locked?: boolean, attachments?: GoogleAttachmentType[], eventType?: GoogleEventType1, location?: string, colorId?: string) => Promise<{
    id: string;
    googleEventId: string | null | undefined;
    generatedId: string | undefined;
    calendarId: string;
    generatedEventId: string;
} | undefined>;
export declare const postPlannerModifyEventInCalendar: (newEvent: EventPlusType, userId: string, method: "update" | "create" | "createWithId", resource: string, isTimeBlocking: boolean, clientType: "ios" | "android" | "web" | "atomic-web", newReminders?: ReminderType[], attendees?: MeetingAssistAttendeeType[], conference?: ConferenceType) => Promise<string | CreateGoogleEventResponseType>;
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
export declare const insertAttendeesforEvent: (attendees: AttendeeType[]) => Promise<void>;
export declare const deleteAttendeesWithIds: (eventIds: string[], userId: string) => Promise<void>;
export declare const deleteRemindersWithIds: (eventIds: string[], userId: string) => Promise<void>;
export declare const insertReminders: (reminders: ReminderTypeAdjusted[]) => Promise<void>;
export declare const deletePreferredTimeRangesForEvents: (eventIds: string[]) => Promise<void>;
export declare const deletePreferredTimeRangesForEvent: (eventId: string) => Promise<void>;
export declare const insertPreferredTimeRanges: (preferredTimeRanges: PreferredTimeRangeType[]) => Promise<void>;
export declare const updateAllCalendarEventsPostPlanner: (plannerEvents: EventPlannerResponseBodyType[][], eventsToValidate: EventPlannerResponseBodyType[][], allEvents: EventPlusType[], oldEvents: EventPlusType[], hostTimezone: string, hostBufferTimes?: BufferTimeObjectType[], newHostReminders?: RemindersForEventType[], breaks?: EventPlusType[], oldAttendeeExternalEvents?: MeetingAssistEventType[], isReplan?: boolean, originalGoogleEventIdToUpdate?: string, originalCalendarIdToUpdate?: string) => Promise<void>;
export declare const deleteZoomMeeting: (zoomToken: string, meetingId: number) => Promise<void>;
export declare const getZoomMeeting: (zoomToken: string, meetingId: number) => Promise<any>;
export declare const updateZoomMeetingStartDate: (zoomToken: string, meetingId: number, startDate: string, timezone: string) => Promise<void>;
export declare const createZoomMeeting: (zoomToken: string, startDate: string, timezone: string, agenda: string, duration: number, contactName?: string, contactEmail?: string, meetingInvitees?: string[]) => Promise<any>;
export declare const insertConferences: (conferences: ConferenceType[]) => Promise<void>;
export declare const insertConference: (conference: ConferenceType) => Promise<any>;
export declare const listConferencesWithHosts: (ids: string[]) => Promise<ConferenceType[] | undefined>;
export declare const processEventsForUpdatingConferences: (finalEventsToUpsert: EventPlusType[]) => Promise<void>;
export declare const processEventsForCreatingConferences: (finalEventsToUpsert: EventPlusType[], createResults: {
    id: string;
    generatedId: string;
}[]) => Promise<any[] | undefined>;
export declare const listMeetingAssistsGivenMeetingIds: (meetingIds: string[]) => Promise<MeetingAssistType[] | undefined>;
