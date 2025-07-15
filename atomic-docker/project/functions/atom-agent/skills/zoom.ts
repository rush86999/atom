import { ListZoomMeetingsResponse, GetZoomMeetingDetailsResponse } from '../../types';
import { listZoomMeetings as list, getZoomMeetingDetails as getDetails } from './zoomSkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleListZoomMeetings(userId: string, entities: any): Promise<string> {
    try {
        const userIdForZoom = "me";
        const type = (entities?.type && typeof entities.type === 'string' ? entities.type : 'upcoming') as 'live' | 'upcoming' | 'scheduled' | 'upcoming_meetings' | 'previous_meetings';
        const page_size = entities?.page_size && typeof entities.page_size === 'number' ? entities.page_size : 30;
        const next_page_token = entities?.next_page_token && typeof entities.next_page_token === 'string' ? entities.next_page_token : undefined;
        const options = { type, page_size, next_page_token };
        const response: ListZoomMeetingsResponse = await list(userIdForZoom, options);
        if (response.ok && response.meetings && response.meetings.length > 0) {
            let output = `Your Zoom Meetings (${type}, via NLU):\n`;
            for (const meeting of response.meetings) {
                output += `- ${meeting.topic} (ID: ${meeting.id}) - Start: ${meeting.start_time ? new Date(meeting.start_time).toLocaleString() : 'N/A'} - Join: ${meeting.join_url || 'N/A'}\n`;
            }
            if (response.next_page_token) {
                output += `More meetings available. For next page, use token: ${response.next_page_token}\n`;
            }
            return output;
        } else if (response.ok) {
            return "No Zoom meetings found matching your criteria (via NLU).";
        } else {
            return `Error fetching Zoom meetings (via NLU): ${response.error || 'Unknown error'}`;
        }
    } catch (error: any) {
        return handleError(error, "Sorry, an unexpected error occurred while fetching your Zoom meetings (NLU path).");
    }
}

export async function handleGetZoomMeetingDetails(userId: string, entities: any): Promise<string> {
    try {
        const { meeting_id } = entities;
        if (!meeting_id || typeof meeting_id !== 'string') {
            return "Zoom Meeting ID is required to get details via NLU.";
        } else {
            const response: GetZoomMeetingDetailsResponse = await getDetails(meeting_id);
            if (response.ok && response.meeting) {
                const m = response.meeting;
                return `Zoom Meeting Details (via NLU):\nTopic: ${m.topic}\nID: ${m.id}\nStart Time: ${m.start_time ? new Date(m.start_time).toLocaleString() : 'N/A'}\nDuration: ${m.duration || 'N/A'} mins\nJoin URL: ${m.join_url || 'N/A'}\nAgenda: ${m.agenda || 'N/A'}`;
            } else {
                return `Error fetching Zoom meeting details (via NLU): ${response.error || `Meeting with ID ${meeting_id} not found or an unknown error occurred.`}`;
            }
        }
    } catch (error: any) {
        return handleError(error, `Sorry, an unexpected error occurred while fetching details for Zoom meeting ${entities.meeting_id} (NLU path).`);
    }
}
