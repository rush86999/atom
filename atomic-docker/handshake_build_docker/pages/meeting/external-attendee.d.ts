import type { NextPage } from 'next';
import { MeetingAssistAttendeeType } from "@lib/types";
type Props = {
    meetingAssistAttendee?: MeetingAssistAttendeeType;
    hostId: string;
    primaryEmail?: string;
    meetingId: string;
    attendeeId: string;
};
declare const MeetingAssistExternalAttendee: NextPage<Props>;
export default MeetingAssistExternalAttendee;
