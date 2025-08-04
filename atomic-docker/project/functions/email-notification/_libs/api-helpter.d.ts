import { BulkMeetingCancelledDetailsToAttendeeType, BulkMeetingInviteDetailsToAttendeeType, MeetingInviteDetailsToHostType } from '@email_notification/_libs/types';
export declare const sendMeetingInviteDetailsToHost: (meetingInvite: MeetingInviteDetailsToHostType) => Promise<void>;
export declare const sendBulkCancelToMeetingEmail: (meetingCancel: BulkMeetingCancelledDetailsToAttendeeType) => Promise<void>;
export declare const sendBulkInviteToMeetingEmail: (meetingInvite: BulkMeetingInviteDetailsToAttendeeType) => Promise<void>;
