import { MeetingAssistAttendeeType, MeetingAssistPreferredTimeRangeType, MeetingAssistType, RecurrenceFrequencyType } from './types';
export declare const generatePreferredTimesForRecurringMeetingAssist: (originalPreferredTimes: MeetingAssistPreferredTimeRangeType[], recurringMeetingAssist: MeetingAssistType, recurringAttendee: MeetingAssistAttendeeType) => MeetingAssistPreferredTimeRangeType[];
export declare const generateAttendeesAndPreferredTimesForRecurringMeetingAssist: (originalAttendees: MeetingAssistAttendeeType[], recurringMeetingAssist: MeetingAssistType, originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]) => {
    recurringAttendees: MeetingAssistAttendeeType[];
    recurringPreferredTimes: MeetingAssistPreferredTimeRangeType[];
};
export declare const generateAttendeesAndPreferredTimesForRecurringMeetingAssists: (originalAttendees: MeetingAssistAttendeeType[], recurringMeetingAssists: MeetingAssistType[], originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]) => {
    recurringAttendees: MeetingAssistAttendeeType[];
    recurringPreferredTimes: MeetingAssistPreferredTimeRangeType[];
};
export declare const insertMeetingAssists: (meetingAssists: MeetingAssistType[]) => Promise<number | undefined>;
export declare const listMeetingAssistAttendeesGivenMeetingId: (meetingId: string) => Promise<MeetingAssistAttendeeType[] | undefined>;
export declare const getRruleFreq: (freq: RecurrenceFrequencyType) => any;
export declare const generateDatesForFutureMeetingAssistsUsingRrule: (windowStartDate: string, windowEndDate: string, frequency: RecurrenceFrequencyType, interval: number, until: string) => any;
export declare const generateRecurringMeetingAssists: (originalMeetingAssist: MeetingAssistType) => MeetingAssistType[] | undefined;
export declare const insertMeetingAssistAttendees: (attendees: MeetingAssistAttendeeType[]) => Promise<number | undefined>;
export declare const upsertMeetingAssistPreferredTimes: (preferredTimes: MeetingAssistPreferredTimeRangeType[]) => Promise<number | undefined>;
export declare const createRecurringMeetingAssists: (originalMeetingAssist: MeetingAssistType, originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]) => Promise<void>;
