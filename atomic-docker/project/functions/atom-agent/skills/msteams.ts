import { ListMSTeamsMeetingsResponse, GetMSTeamsMeetingDetailsResponse } from '../../types';
import { listMicrosoftTeamsMeetings as listMeetings, getMicrosoftTeamsMeetingDetails as getDetails } from './msTeamsSkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleListMicrosoftTeamsMeetings(userId: string, entities: any): Promise<string> {
    try {
        const userPrincipalNameOrId = "me";
        const limit = entities?.limit && typeof entities.limit === 'number' ? entities.limit : 10;
        const next_link = entities?.next_link && typeof entities.next_link === 'string' ? entities.next_link : undefined;
        const options = { limit, nextLink: next_link, filterForTeams: true };
        const response: ListMSTeamsMeetingsResponse = await listMeetings(userPrincipalNameOrId, options);
        if (response.ok && response.events && response.events.length > 0) {
            let output = "Your Microsoft Teams Meetings (via NLU):\n";
            for (const event of response.events) {
                output += `- ${event.subject} (ID: ${event.id}) - Start: ${event.start?.dateTime ? new Date(event.start.dateTime).toLocaleString() : 'N/A'} - Join: ${event.onlineMeeting?.joinUrl || 'N/A'}\n`;
            }
            if (response.nextLink) {
                output += `More meetings available. Next page link (for API use): ${response.nextLink}\nTo get next page, you could say: list teams meetings with limit ${limit} and next_link ${response.nextLink}\n`;
            }
            return output;
        } else if (response.ok) {
            return "No Microsoft Teams meetings found matching your criteria (via NLU).";
        } else {
            return `Error fetching Microsoft Teams meetings (via NLU): ${response.error || 'Unknown error'}`;
        }
    } catch (error: any) {
        return handleError(error, "Sorry, an unexpected error occurred while fetching your Microsoft Teams meetings (NLU path).");
    }
}

export async function handleGetMicrosoftTeamsMeetingDetails(userId: string, entities: any): Promise<string> {
    try {
        const userPrincipalNameOrId = "me";
        const { event_id } = entities;
        if (!event_id || typeof event_id !== 'string') {
            return "Microsoft Graph Event ID is required to get Teams meeting details via NLU.";
        } else {
            const response: GetMSTeamsMeetingDetailsResponse = await getDetails(userPrincipalNameOrId, event_id);
            if (response.ok && response.event) {
                const ev = response.event;
                let output = `Teams Meeting (via NLU): ${ev.subject}\nID: ${ev.id}\nStart: ${ev.start?.dateTime ? new Date(ev.start.dateTime).toLocaleString() : 'N/A'}\nEnd: ${ev.end?.dateTime ? new Date(ev.end.dateTime).toLocaleString() : 'N/A'}`;
                if (ev.onlineMeeting?.joinUrl) output += `\nJoin URL: ${ev.onlineMeeting.joinUrl}`;
                if (ev.bodyPreview) output += `\nPreview: ${ev.bodyPreview}`;
                if (ev.webLink) output += `\nOutlook Link: ${ev.webLink}`;
                return output;
            } else {
                return `Error fetching Teams meeting details (via NLU): ${response.error || `Meeting with ID ${event_id} not found or an unknown error occurred.`}`;
            }
        }
    } catch (error: any) {
        return handleError(error, `Sorry, an unexpected error occurred while fetching details for Teams meeting ${entities.event_id} (NLU path).`);
    }
}
