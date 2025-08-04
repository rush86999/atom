import { BufferTimeNumberType, EventPlusType, EventType, MeetingAssistAttendeeType, MeetingAssistEventType, MeetingAssistPreferredTimeRangeType, MeetingAssistType, EventMeetingPlusType, RemindersForEventType, ValuesToReturnForBufferEventsType, UserPreferenceType, WorkTimeType, TimeSlotType, EventPartPlannerRequestBodyType, InitialEventPartType, InitialEventPartTypePlus, UserPlannerRequestBodyType, ReturnBodyForHostForOptaplannerPrepType, ReturnBodyForAttendeeForOptaplannerPrepType, ReturnBodyForExternalAttendeeForOptaplannerPrepType, PlannerRequestBodyType, BufferTimeObjectType, FetchedExternalPreference, NewConstraints } from '@schedule_assist/_libs/types';
export declare const listFutureMeetingAssists: (userId: string, windowStartDate: string, windowEndDate: string, ids?: string[]) => Promise<MeetingAssistType[] | undefined>;
export declare const listMeetingAssistPreferredTimeRangesGivenMeetingId: (meetingId: string) => Promise<MeetingAssistPreferredTimeRangeType[] | undefined>;
export declare const meetingAttendeeCountGivenMeetingId: (meetingId: string) => Promise<number | undefined>;
export declare const listMeetingAssistAttendeesGivenMeetingId: (meetingId: string) => Promise<MeetingAssistAttendeeType[] | undefined>;
export declare const getMeetingAssistAttendee: (id: string) => Promise<any>;
export declare const getMeetingAssist: (id: string) => Promise<any>;
export declare const listMeetingAssistEventsForAttendeeGivenDates: (attendeeId: string, hostStartDate: string, hostEndDate: string, userTimezone: string, hostTimezone: string) => Promise<MeetingAssistEventType[] | undefined>;
export declare const listEventsForDate: (userId: string, startDate: string, endDate: string, timezone: string) => Promise<EventType[] | undefined>;
export declare const listEventsForUserGivenDates: (userId: string, hostStartDate: string, hostEndDate: string, userTimezone: string, hostTimezone: string) => Promise<EventType[] | undefined>;
export declare const processMeetingAssistForOptaplanner: () => Promise<void>;
export declare const generateNewMeetingEventForAttendee: (attendee: MeetingAssistAttendeeType, meetingAssist: MeetingAssistType, windowStartDate: string, windowEndDate: string, hostTimezone: string, calendarId?: string, preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType) => EventType;
export declare const generateNewMeetingEventForHost: (hostAttendee: MeetingAssistAttendeeType, meetingAssist: MeetingAssistType, windowStartDate: string, windowEndDate: string, hostTimezone: string, preferredStartTimeRange?: MeetingAssistPreferredTimeRangeType) => EventType;
export declare const listPreferredTimeRangesForEvent: (eventId: string) => Promise<PreferredTimeRangeType[] | undefined>;
export declare const createRemindersFromMinutesAndEvent: (eventId: string, minutes: number[], timezone: string, useDefault: boolean, userId: string) => RemindersForEventType;
export declare const createBufferTimeForNewMeetingEvent: (event: EventMeetingPlusType, bufferTime: BufferTimeNumberType) => ValuesToReturnForBufferEventsType;
export declare const getUserPreferences: (userId: string) => Promise<UserPreferenceType>;
export declare const getGlobalCalendar: (userId: string) => Promise<any>;
export declare const adjustStartDatesForBreakEventsForDay: (allEvents: EventPlusType[], breakEvents: EventPlusType[], userPreferences: UserPreferenceType, timezone: string) => EventPlusType[];
export declare const convertToTotalWorkingHoursForInternalAttendee: (userPreference: UserPreferenceType, hostStartDate: string, hostTimezone: string) => number;
export declare const convertToTotalWorkingHoursForExternalAttendee: (attendeeEvents: EventPlusType[], hostStartDate: string, hostTimezone: string, userTimezone: string) => number;
export declare const getEventDetailsForModification: (hasuraEventId: string) => Promise<(EventType & {
    attendees?: MeetingAssistAttendeeType[];
}) | null>;
export declare function generateEventPartsForReplan(allUserEvents: EventPlusType[], // All events for all relevant users
eventToReplanHasuraId: string, // e.g., "googleEventId#calendarId"
replanConstraints: NewConstraints, hostId: string, // Typically originalEventDetails.userId
hostTimezone: string): InitialEventPartTypePlus[];
export declare function generateTimeSlotsForReplan(users: MeetingAssistAttendeeType[], // Final list of users for the replanned event
replanConstraints: NewConstraints, hostTimezone: string, globalDefaultWindowStart: string, // Fallback window start (ISO string)
globalDefaultWindowEnd: string, // Fallback window end (ISO string)
mainHostId: string, // Needed by generateTimeSlotsLiteForInternalAttendee
userPreferencesCache: Map<string, UserPreferenceType>): Promise<TimeSlotType[]>;
export declare function orchestrateReplanOptaPlannerInput(userId: string, // User initiating the replan (usually the host)
hostTimezone: string, originalEventDetails: EventType & {
    attendees?: MeetingAssistAttendeeType[];
    meetingId?: string;
}, newConstraints: NewConstraints, allUsersFromOriginalEventAndAdded: MeetingAssistAttendeeType[], // Combined list of original and newly added attendees
allExistingEventsForUsers: EventPlusType[]): Promise<PlannerRequestBodyType | null>;
export declare const listExternalAttendeePreferences: (meetingAssistId: string, meetingAssistAttendeeId: string) => Promise<FetchedExternalPreference[]>;
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
export declare const processEventsForOptaPlannerForMainHost: (mainHostId: string, allHostEvents: EventPlusType[], windowStartDate: string, windowEndDate: string, hostTimezone: string, oldHostEvents: EventPlusType[], newHostBufferTimes?: BufferTimeObjectType[]) => Promise<ReturnBodyForHostForOptaplannerPrepType>;
export declare const processEventsForOptaPlannerForInternalAttendees: (mainHostId: string, allEvents: EventPlusType[], windowStartDate: string, windowEndDate: string, hostTimezone: string, internalAttendees: MeetingAssistAttendeeType[], oldEvents: EventPlusType[], oldMeetingEvents?: EventMeetingPlusType[], newMeetingEvents?: EventMeetingPlusType[], newHostBufferTimes?: BufferTimeObjectType[]) => Promise<ReturnBodyForAttendeeForOptaplannerPrepType>;
export declare const convertMeetingAssistEventTypeToEventPlusType: (event: MeetingAssistEventType, userId: string) => EventPlusType;
export declare const generateWorkTimesForExternalAttendee: (hostId: string, userId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string) => WorkTimeType[];
export declare const generateTimeSlotsForExternalAttendee: (hostStartDate: string, hostId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string, isFirstDay?: boolean) => TimeSlotType[];
export declare const generateTimeSlotsLiteForExternalAttendee: (hostStartDate: string, hostId: string, attendeeEvents: EventPlusType[], hostTimezone: string, userTimezone: string, isFirstDay?: boolean) => TimeSlotType[];
export declare const processEventsForOptaPlannerForExternalAttendees: (userIds: string[], mainHostId: string, allExternalEvents: MeetingAssistEventType[], // These are MeetingAssistEvents from the user's calendar connection
windowStartDate: string, windowEndDate: string, hostTimezone: string, externalAttendees: MeetingAssistAttendeeType[], oldExternalMeetingEvents?: EventMeetingPlusType[], newMeetingEvents?: EventMeetingPlusType[], meetingAssistId?: string) => Promise<ReturnBodyForExternalAttendeeForOptaplannerPrepType>;
export declare const optaPlanWeekly: (timeslots: TimeSlotType[], userList: UserPlannerRequestBodyType[], eventParts: EventPartPlannerRequestBodyType[], singletonId: string, hostId: string, fileKey: string, delay: number, callBackUrl: string) => Promise<void>;
export declare const updateFreemiumById: (id: string, usage: number) => Promise<any>;
export declare const getFreemiumByUserId: (userId: string) => Promise<any>;
export declare const processEventsForOptaPlanner: (mainHostId: string, internalAttendees: MeetingAssistAttendeeType[], meetingEventPlus: EventMeetingPlusType[], newMeetingEventPlus: EventMeetingPlusType[], allEvents: EventPlusType[], windowStartDate: string, windowEndDate: string, hostTimezone: string, oldEvents: EventPlusType[], externalAttendees?: MeetingAssistAttendeeType[], meetingAssistEvents?: MeetingAssistEventType[], newHostReminders?: RemindersForEventType[], newHostBufferTimes?: BufferTimeObjectType[], isReplan?: boolean, eventBeingReplanned?: {
    originalEventId: string;
    googleEventId: string;
    calendarId: string;
    newConstraints: NewConstraints;
    originalAttendees: MeetingAssistAttendeeType[];
}) => Promise<void>;
