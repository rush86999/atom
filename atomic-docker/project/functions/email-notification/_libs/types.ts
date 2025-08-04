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

export type BulkMeetingInviteDetailsToAttendeeType = {
  attendees: AttendeeDetailsForBulkMeetingInviteType[];
  hostEmail: string;
  hostName: string;
};

export type AttendeeDetailsForBulkMeetingCancelledType = {
  email: string;
  name: string;
};

export type BulkMeetingCancelledDetailsToAttendeeType = {
  attendees: AttendeeDetailsForBulkMeetingCancelledType[];
  hostEmail: string;
  hostName: string;
};
