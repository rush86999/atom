import { CustomAvailableTimeType, MeetingAssistAttendeeType, MeetingAssistCalendarType, MeetingAssistEventType, MeetingAssistPreferredTimeRangeType, ScheduleAssistWithMeetingQueueBodyType, MeetingAssistType, NotAvailableSlot, UserPreferenceType, RecurrenceFrequencyType } from '@lib/types';
export declare const getRruleFreq: (freq: RecurrenceFrequencyType) => any;
export declare const generateRecurringMeetingAssists: (originalMeetingAssist: MeetingAssistType) => MeetingAssistType[] | undefined;
export declare const generateDatesForFutureMeetingAssistsUsingRrule: (windowStartDate: string, windowEndDate: string, frequency: RecurrenceFrequencyType, interval: number, until: string) => any;
export declare const getUserPreferences: (userId: string) => Promise<UserPreferenceType | null>;
export declare const getUserGivenId: (userId: string) => Promise<any>;
export declare const insertMeetingAssists: (meetingAssists: MeetingAssistType[]) => Promise<number | undefined>;
export declare const upsertMeetingAssistCalendars: (calendarList: MeetingAssistCalendarType[]) => Promise<void>;
export declare const upsertMeetingAssistEvents: (events: MeetingAssistEventType[]) => Promise<void>;
export declare const googleCalendarSync: (token: string, // access_token returned by Google Auth
windowStartDate: string, windowEndDate: string, attendeeId: string, hostTimezone: string) => Promise<null | undefined>;
export declare const getCalendarIntegration: (userId: string, resource: string) => Promise<any>;
export declare const getMeetingAssist: (id: string) => Promise<any>;
export declare const listMeetingAssistAttendeesGivenMeetingId: (meetingId: string) => Promise<MeetingAssistAttendeeType[] | undefined>;
export declare const listMeetingAssistEventsForAttendeeGivenDates: (attendeeId: string, hostStartDate: string, hostEndDate: string, userTimezone: string, hostTimezone: string) => Promise<MeetingAssistEventType[] | undefined>;
export declare const updateMeetingAssistAttendee: (attendee: MeetingAssistAttendeeType) => Promise<void>;
export declare const generatePreferredTimesForRecurringMeetingAssist: (originalPreferredTimes: MeetingAssistPreferredTimeRangeType[], recurringMeetingAssist: MeetingAssistType, recurringAttendee: MeetingAssistAttendeeType) => MeetingAssistPreferredTimeRangeType[];
export declare const generateAttendeesAndPreferredTimesForRecurringMeetingAssist: (originalAttendees: MeetingAssistAttendeeType[], recurringMeetingAssist: MeetingAssistType, originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]) => {
    recurringAttendees: MeetingAssistAttendeeType[];
    recurringPreferredTimes: MeetingAssistPreferredTimeRangeType[];
};
export declare const generateAttendeesAndPreferredTimesForRecurringMeetingAssists: (originalAttendees: MeetingAssistAttendeeType[], recurringMeetingAssists: MeetingAssistType[], originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]) => {
    recurringAttendees: MeetingAssistAttendeeType[];
    recurringPreferredTimes: MeetingAssistPreferredTimeRangeType[];
};
export declare const insertMeetingAssistAttendees: (attendees: MeetingAssistAttendeeType[]) => Promise<number | undefined>;
export declare const upsertOneMeetingAssistAttendee: (attendee: MeetingAssistAttendeeType) => Promise<any>;
export declare const deleteMeetingAssistAttendee: (id: string) => Promise<any>;
export declare const getMeetingAssistAttendee: (id: string) => Promise<any>;
export declare const getMeetingAssistAttendeeByEmail: (primaryEmail: string, meetingId: string) => Promise<any>;
export declare const updateMeetingAssistAttendanceCount: (id: string, attendeeCount: number, attendeeRespondedCount: number) => Promise<any>;
export declare const getUserContactInfo: (id: string) => Promise<any>;
export declare const listEventsForUserGivenDates: (userId: string, hostStartDate: string, hostEndDate: string, userTimezone: string, hostTimezone: string) => Promise<EventType[] | undefined>;
export declare const findEventsForUserGivenMeetingId: (userId: string, hostStartDate: string, hostEndDate: string, userTimezone: string, hostTimezone: string, meetingId: string) => Promise<EventType[] | undefined>;
export declare const listMeetingAssistPreferredTimeRangesGivenMeetingId: (meetingId: string) => Promise<MeetingAssistPreferredTimeRangeType[] | undefined>;
export declare const generateAvailableSlotsforTimeWindow: (windowStartDate: string, windowEndDate: string, slotDuration: number, hostPreferences: UserPreferenceType, hostTimezone: string, userTimezone: string, notAvailableSlotsInUserTimezone?: NotAvailableSlot[]) => {
    availableSlots: AvailableSlot[];
    availableSlotsByDate: AvailableSlotsByDate;
};
/**
 * @params notAvailableSlotsInUserTimezone - events with transparency: 'opaque' as not available
 */
export declare const generateAvailableSlotsForDate: (slotDuration: number, userStartDateInHostTimezone: string, hostPreferences: UserPreferenceType, hostTimezone: string, userTimezone: string, notAvailableSlotsInUserTimezone?: NotAvailableSlot[], isFirstDay?: boolean, isLastDay?: boolean, userEndDateInHostTimezone?: string) => AvailableSlot[];
export declare const cancelMeetingAssist: (id: string) => Promise<any>;
export declare const deleteMeetingAssistPreferredTimesByIds: (ids: string[]) => Promise<number | undefined>;
export declare const upsertMeetingAssistPreferredTimes: (preferredTimes: MeetingAssistPreferredTimeRangeType[]) => Promise<number | undefined>;
export declare const BtoA: (str: string) => string;
export declare const AtoB: (str: string) => string;
export declare const startMeetingAssist: (body: ScheduleAssistWithMeetingQueueBodyType) => Promise<void>;
export declare const getCustomAvailableTimes: (slotDuration: number, hostStartDate: string, hostPreferences: UserPreferenceType, hostTimezone: string, userTimezone: string, isFirstDay?: boolean, isLastDay?: boolean) => CustomAvailableTimeType | null;
export declare const getMeetingAssistInviteGivenId: (id: string) => Promise<any>;
export declare const listMeetingAssistInvitesGivenMeetingId: (meetingId: string) => Promise<MeetingAssistInviteType[] | undefined>;
export declare const updateMeetingAssistInviteResponse: (id: string, response: string) => Promise<any>;
export declare const createRecurringMeetingAssists: (originalMeetingAssist: MeetingAssistType, originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]) => Promise<void>;
