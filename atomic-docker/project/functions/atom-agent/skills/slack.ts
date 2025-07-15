import { sendSlackMessage as send } from './slackSkills';
import { listUpcomingEvents } from './calendarSkills';
import { CalendarEvent } from '../../types';
import { handleError } from '../../_utils/errorHandler';

export async function handleSendSlackMessage(userId: string, entities: any): Promise<string> {
    try {
        const { slack_channel, message_text } = entities;
        if (!slack_channel || typeof slack_channel !== 'string') {
            return "Slack channel/user ID is required to send a message via NLU.";
        } else if (!message_text || typeof message_text !== 'string') {
            return "Message text is required to send a Slack message via NLU.";
        } else {
            const slackResponse = await send(userId, slack_channel, message_text);
            if (slackResponse.ok) {
                return `Message sent to Slack channel/user ${slack_channel}.`;
            } else {
                return `Failed to send Slack message to ${slack_channel} via NLU. Error: ${slackResponse.error}`;
            }
        }
    } catch (error: any) {
        return handleError(error, "Sorry, there was an issue sending your Slack message.");
    }
}

export async function handleSlackMyAgenda(userId: string, entities: any): Promise<string> {
    try {
        const limit = entities?.limit && typeof entities.limit === 'number' ? entities.limit : 5;
        const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
        if (!events || events.length === 0) {
            const noEventsMessage = "You have no upcoming events on your calendar for the near future, or I couldn't access them (NLU path).";
            try {
                await send(userId, userId, noEventsMessage);
                return "I've checked your calendar; no upcoming events. Sent a note to your Slack DM (NLU path).";
            } catch (dmError:any) {
                return "No upcoming events found. Tried to DM you on Slack, but failed (NLU path).";
            }
        } else {
            let formattedAgenda = `🗓️ Your Upcoming Events (via NLU):\n`;
            for (const event of events) {
                const startTime = new Date(event.startTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                const endTime = new Date(event.endTime).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
                formattedAgenda += `- ${event.summary} (from ${startTime} to ${endTime})`;
                if (event.location) formattedAgenda += ` - Location: ${event.location}`;
                if (event.htmlLink) formattedAgenda += ` [View: ${event.htmlLink}]`;
                formattedAgenda += "\n";
            }
            const slackResponse = await send(userId, userId, formattedAgenda);
            if (slackResponse.ok) {
                return "I've sent your agenda to your Slack DM (NLU path)!";
            } else {
                return `Sorry, I couldn't send your agenda to Slack (NLU path). Error: ${slackResponse.error}`;
            }
        }
    } catch (error: any) {
        return handleError(error, "Sorry, an error occurred while processing your agenda for Slack (NLU path).");
    }
}
