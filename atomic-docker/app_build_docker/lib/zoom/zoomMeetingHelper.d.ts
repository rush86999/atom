import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
export declare const zoomAvailable: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<boolean | undefined>;
export declare const createZoomMeeting: (userId: string, startDate: string, timezone: string, agenda: string, duration: number, contactName?: string, contactEmail?: string, meetingInvitees?: string[], privateMeeting?: boolean) => Promise<{
    id: CreateMeetingResponseType;
    join_url: CreateMeetingResponseType;
    start_url: CreateMeetingResponseType;
    status: CreateMeetingResponseType;
} | undefined>;
export declare const deleteZoomMeeting: (userId: string, meetingId: number, scheduleForReminder?: boolean, cancelMeetingReminder?: string) => Promise<void>;
export declare const updateZoomMeeting: (userId: string, meetingId: number, startDate?: string, timezone?: string, agenda?: string, duration?: number, contactName?: string, contactEmail?: string, meetingInvitees?: string[], privateMeeting?: boolean) => Promise<{
    id: CreateMeetingResponseType;
    join_url: CreateMeetingResponseType;
    start_url: CreateMeetingResponseType;
    status: CreateMeetingResponseType;
} | undefined>;
