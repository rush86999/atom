import { AppType, MutatedCalendarExtractedJSONAttendeeType } from '@chat/_libs/types/UserInputToJSONType';
import { SendUpdatesType, TransparencyType, VisibilityType } from '@chat/_libs/types/EventType';
type MethodType = 'invite';
export type SendMeetingInviteType = {
    userId: string;
    timezone: string;
    title: string;
    attendees: MutatedCalendarExtractedJSONAttendeeType[];
    method: MethodType;
    duration?: number;
    description?: string;
    conferenceApp?: AppType;
    reminders?: number[];
    transparency?: TransparencyType;
    visibility?: VisibilityType;
    windowStartDate: string;
    windowEndDate: string;
    receiverTimezone: string;
};
export type ReceiverTimezoneFormDataResponseType = {
    type: 'select';
    value: string;
    name: string;
};
export type AttendeeDetailsType = {
    email: string;
    name: string;
    link: string;
};
export type MeetingUrlQueryParamsAttachmentType = {
    title: string;
    fileUrl: string;
};
export type MeetingUrlQueryParamsType = {
    userId: string;
    timezone: string;
    enableConference: 'true' | 'false';
    conferenceApp?: AppType;
    useDefaultAlarms?: 'true' | 'false';
    reminders?: string[];
    attendeeEmails: string[];
    duration: string;
    calendarId: string;
    startTime: string;
    name: string;
    primaryEmail: string;
    sendUpdates?: SendUpdatesType;
    anyoneCanAddSelf: 'true' | 'false';
    guestsCanInviteOthers: 'true' | 'false';
    guestsCanModify?: 'true' | 'false';
    guestsCanSeeOtherGuests: 'true' | 'false';
    transparency?: TransparencyType;
    visibility?: VisibilityType;
    attachments?: MeetingUrlQueryParamsAttachmentType[];
};
export type AttendeeDetailsForBulkMeetingInviteType = {
    email: string;
    name: string;
    link: string;
};
export type AttendeeDetailsForBulkMeetingCancelledType = {
    email: string;
    name: string;
};
export type RecurrenceFrequencyType = 'daily' | 'weekly' | 'monthly' | 'yearly';
export type MeetingInviteDetailsToHostType = {
    attendees: AttendeeDetailsType[];
    hostEmail: string;
    hostName: string;
    title: string;
    notes: string;
    windowStartDate: string;
    windowEndDate: string;
    timezone: string;
};
export {};
