import { BufferTimeNumberType, EventPlusType, EventType, MeetingAssistAttendeeType, MeetingAssistEventType, MeetingAssistPreferredTimeRangeType, MeetingAssistType, EventMeetingPlusType, PreferredTimeRangeType, RemindersForEventType, ValuesToReturnForBufferEventsType, UserPreferenceType, WorkTimeType, TimeSlotType, EventPartPlannerRequestBodyType, InitialEventPartType, InitialEventPartTypePlus, UserPlannerRequestBodyType, ReturnBodyForExternalAttendeeForOptaplannerPrepType, CategoryType, classificationResponseBody as ClassificationResponseBodyType, BufferTimeObjectType, ReminderType, CategoryEventType } from '@features_apply/_libs/types';
import { TrainingEventSchema } from '@functions/_utils/lancedb_service';
import { FeaturesApplyResponse } from './types';
export declare const getEventVectorById: (id: string) => Promise<FeaturesApplyResponse<number[] | null>>;
export declare const deleteTrainingDataById: (id: string) => Promise<FeaturesApplyResponse<void>>;
export declare const searchTrainingDataByVector: (userId: string, searchVector: number[]) => Promise<FeaturesApplyResponse<TrainingEventSchema | null>>;
export declare const addTrainingData: (trainingEntry: TrainingEventSchema) => Promise<FeaturesApplyResponse<void>>;
export declare const convertEventTitleToOpenAIVector: (title: string) => Promise<FeaturesApplyResponse<number[] | undefined>>;
export declare const listMeetingAssistPreferredTimeRangesGivenMeetingId: (meetingId: string) => Promise<FeaturesApplyResponse<MeetingAssistPreferredTimeRangeType[] | null>>;
export declare const listMeetingAssistAttendeesGivenMeetingId: (meetingId: string) => Promise<FeaturesApplyResponse<MeetingAssistAttendeeType[] | null>>;
export declare const getMeetingAssistAttendee: (id: string) => Promise<FeaturesApplyResponse<MeetingAssistAttendeeType | null>>;
export declare const getMeetingAssist: (id: string) => Promise<FeaturesApplyResponse<MeetingAssistType | null>>;
export declare const listMeetingAssistEventsForAttendeeGivenDates: (attendeeId: string, hostStartDate: string, hostEndDate: string, userTimezone: string, hostTimezone: string) => Promise<FeaturesApplyResponse<MeetingAssistEventType[] | null>>;
export declare const listEventsForDate: (userId: string, startDate: string, endDate: string, timezone: string) => Promise<FeaturesApplyResponse<EventType[] | null>>;
export declare const listEventsForUserGivenDates: (userId: string, hostStartDate: string, hostEndDate: string, userTimezone: string, hostTimezone: string) => Promise<FeaturesApplyResponse<EventType[] | null>>;
export declare const processMeetingAssistForOptaplanner: () => Promise<FeaturesApplyResponse<{
    message: string;
}>>;
export declare const generateNewMeetingEventForAttendee: (attendee: MeetingAssistAttendeeType, meetingAssist: MeetingAssistType, windowStartDate: string, windowEndDate: string, hostTimezone: string, calendarId?: string, preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType) => EventType;
export declare const generateNewMeetingEventForHost: (hostAttendee: MeetingAssistAttendeeType, meetingAssist: MeetingAssistType, windowStartDate: string, windowEndDate: string, hostTimezone: string, preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType) => EventType;
export declare const listPreferredTimeRangesForEvent: (eventId: string) => Promise<FeaturesApplyResponse<PreferredTimeRangeType[] | null>>;
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
export declare const convertMeetingAssistEventTypeToEventPlusType: (event: MeetingAssistEventType, userId: string) => EventPlusType;
export declare const generateWorkTimesForExternalAttendee: (hostId: string, userId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string) => WorkTimeType[];
export declare const generateTimeSlotsForExternalAttendee: (hostStartDate: string, hostId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string, isFirstDay?: boolean) => TimeSlotType[];
export declare const generateTimeSlotsLiteForExternalAttendee: (hostStartDate: string, hostId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string, isFirstDay?: boolean) => TimeSlotType[];
export declare const processEventsForOptaPlannerForExternalAttendees: (userIds: string[], mainHostId: string, allExternalEvents: MeetingAssistEventType[], windowStartDate: string, windowEndDate: string, hostTimezone: string, externalAttendees: MeetingAssistAttendeeType[], oldExternalMeetingEvents?: EventMeetingPlusType[], newMeetingEvents?: EventMeetingPlusType[]) => Promise<ReturnBodyForExternalAttendeeForOptaplannerPrepType>;
export declare const optaPlanWeekly: (timeslots: TimeSlotType[], userList: UserPlannerRequestBodyType[], eventParts: EventPartPlannerRequestBodyType[], singletonId: string, hostId: string, fileKey: string, delay: number, callBackUrl: string) => Promise<void>;
export declare const updateFreemiumById: (id: string, usage: number) => Promise<any>;
export declare const getFreemiumByUserId: (userId: string) => Promise<any>;
export declare const getUserCategories: (userId: any) => Promise<CategoryType[] | undefined>;
export declare const findBestMatchCategory2: (event: EventPlusType, possibleLabels: CategoryType[]) => Promise<ClassificationResponseBodyType>;
export declare const processBestMatchCategories: (body: ClassificationResponseBodyType, newPossibleLabels: string[]) => string;
export declare const processEventForMeetingTypeCategories: (newEvent: EventPlusType, bestMatchCategory: CategoryType, newPossibleLabels: string[], scores: number[], categories: CategoryType[]) => CategoryType[] | [];
export declare const getUniqueLabels: (labels: CategoryType[]) => CategoryType[];
export declare const copyOverCategoryDefaults: (event: EventPlusType, category: CategoryType) => EventPlusType;
export declare const createRemindersAndBufferTimesForBestMatchCategory: (id: string, userId: string, newEvent: EventPlusType, bestMatchCategory: CategoryType, newReminders1?: ReminderType[], newBufferTimes1?: BufferTimeObjectType, previousEvent?: EventPlusType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newBufferTimes: any;
} | undefined>;
export declare const createCategoryEvents: (categoryEvents: CategoryEventType[]) => Promise<FeaturesApplyResponse<void>>;
export declare const listRemindersForEvent: (eventId: string, userId: string) => Promise<FeaturesApplyResponse<ReminderType[] | null>>;
export declare const createRemindersUsingCategoryDefaultsForEvent: (event: EventPlusType, bestMatchCategory: CategoryType, oldReminders: ReminderType[], previousEvent: EventPlusType) => ReminderType[];
export declare const createPreAndPostEventsForCategoryDefaults: (bestMatchCategory: CategoryType, event: EventPlusType, previousEvent?: EventPlusType) => any;
export declare const updateValuesForMeetingTypeCategories: (event: any, newEvent1: EventPlusType, bestMatchCategories: CategoryType[], userId: string, newReminders1?: ReminderType[], newTimeBlocking1?: BufferTimeObjectType, // Updated type
previousEvent?: EventPlusType) => Promise<FeaturesApplyResponse<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newBufferTimes: BufferTimeObjectType;
}>>;
export declare const processUserEventForCategoryDefaults: (event: EventPlusType, vector: number[]) => Promise<FeaturesApplyResponse<{
    newEvent: EventPlusType;
    newReminders?: ReminderType[];
    newBufferTimes?: BufferTimeObjectType;
} | null>>;
export declare const listCategoriesForEvent: (eventId: string) => Promise<FeaturesApplyResponse<CategoryType[] | null>>;
export declare const processBestMatchCategoriesNoThreshold: (body: any, newPossibleLabels: any) => string;
export declare const processUserEventForCategoryDefaultsWithUserModifiedCategories: (event: EventPlusType, vector: number[]) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newBufferTimes: any;
} | undefined>;
export declare const getEventFromPrimaryKey: (id: string) => Promise<FeaturesApplyResponse<EventPlusType | null>>;
export declare const copyOverPreviousEventDefaults: (event: EventPlusType, previousEvent: EventPlusType, category?: CategoryType, userPreferences?: UserPreferenceType) => EventPlusType;
export declare const listFutureMeetingAssists: (userId: string, windowStartDate: string, windowEndDate: string, ids?: string[]) => Promise<MeetingAssistType[] | undefined>;
export declare const meetingAttendeeCountGivenMeetingId: (meetingId: string) => Promise<number | undefined>;
export declare const createPreAndPostEventsFromPreviousEvent: (event: EventPlusType, previousEvent: EventPlusType) => any;
export declare const createRemindersFromPreviousEventForEvent: (event: EventPlusType, previousEvent: EventPlusType, userId: string) => Promise<ReminderType[]>;
export declare const copyOverCategoryMeetingAndExternalMeetingDefaultsWithFoundPreviousEvent: (event: EventPlusType, categories: CategoryType[], userPreferences: UserPreferenceType, previousEvent: EventPlusType) => {
    newEventMeeting: any;
    newEventExternal: any;
} | undefined;
export declare const createRemindersAndTimeBlockingFromPreviousEventGivenUserPreferences: (userId: string, newEvent: EventPlusType, newReminders1?: ReminderType[], newBufferTimes1?: BufferTimeObjectType, previousEvent?: EventPlusType, userPreferences?: UserPreferenceType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newBufferTimes: any;
} | undefined>;
export declare const updateValuesForEventWithPreviousEventPlusMeetingAndExternalMeeting: (event: EventPlusType, newEvent1: EventPlusType, bestMatchCategories: CategoryType[], newReminders1: ReminderType[], newTimeBlocking1: BufferTimeObjectType, userId: string, userPreferences: UserPreferenceType, previousEvent: EventPlusType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newBufferTimes: any;
} | undefined>;
export declare const createRemindersAndTimeBlockingFromPreviousEvent: (userId: string, newEvent: EventPlusType, newReminders1: ReminderType[], newBufferTimes1: BufferTimeObjectType, previousEvent?: EventPlusType) => Promise<{
    newEvent: EventPlusType;
    newReminders: ReminderType[];
    newBufferTimes: any;
} | undefined>;
export declare const processEventWithFoundPreviousEventAndCopyCategories: (id: string, previousEvent: EventPlusType, oldEvent: EventPlusType, userPreferences: UserPreferenceType, bestMatchCategory1: CategoryType, userId: string, bestMatchCategories1: CategoryType[], newModifiedEvent1: EventPlusType, newReminders1?: ReminderType[], newTimeBlocking1?: BufferTimeObjectType, previousCategories?: CategoryType[], previousMeetingCategoriesWithMeetingLabel?: CategoryType[], previousMeetingCategoriesWithExternalMeetingLabel?: CategoryType[]) => Promise<FeaturesApplyResponse<{
    newModifiedEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
} | null>>;
export declare const processEventWithFoundPreviousEventWithoutCategories: (previousEvent: EventPlusType, event: EventPlusType, userPreferences: UserPreferenceType, userId: string, newReminders?: ReminderType[], newTimeBlocking?: BufferTimeObjectType) => Promise<FeaturesApplyResponse<{
    newModifiedEvent: EventPlusType;
    newReminders: ReminderType[];
    newTimeBlocking: BufferTimeObjectType;
} | null>>;
export declare const processUserEventWithFoundPreviousEvent: (event: EventPlusType, previousEventId: string) => Promise<FeaturesApplyResponse<{
    newEvent: EventPlusType;
    newReminders?: ReminderType[];
    newBufferTimes?: BufferTimeObjectType;
} | null>>;
export declare const processUserEventWithFoundPreviousEventWithUserModifiedCategories: (event: EventPlusType, previousEventId: string) => Promise<FeaturesApplyResponse<{
    newEvent: EventPlusType;
    newReminders?: ReminderType[];
    newBufferTimes?: BufferTimeObjectType;
} | null>>;
