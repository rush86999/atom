export type AttendeeDetailsType = {
    email: string;
    name: string;
    link: string;
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
