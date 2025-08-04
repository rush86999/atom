import { ZoomMeeting, ZoomSkillResponse, ListZoomMeetingsData } from '../types';
export declare function listZoomMeetings(userId: string, options?: {
    type?: 'live' | 'upcoming' | 'scheduled' | 'upcoming_meetings' | 'previous_meetings';
    page_size?: number;
    next_page_token?: string;
}): Promise<ZoomSkillResponse<ListZoomMeetingsData>>;
export declare function getZoomMeetingDetails(userId: string, meetingId: string): Promise<ZoomSkillResponse<ZoomMeeting>>;
