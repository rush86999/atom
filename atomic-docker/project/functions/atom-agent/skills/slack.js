import { sendSlackMessage as send } from './slackSkills';
import { listUpcomingEvents } from './calendarSkills';
import { handleError } from '../../_utils/errorHandler';
export async function handleSendSlackMessage(userId, entities) {
    try {
        const { slack_channel, message_text } = entities;
        if (!slack_channel || typeof slack_channel !== 'string') {
            return 'Slack channel/user ID is required to send a message via NLU.';
        }
        else if (!message_text || typeof message_text !== 'string') {
            return 'Message text is required to send a Slack message via NLU.';
        }
        else {
            const slackResponse = await send(userId, slack_channel, message_text);
            if (slackResponse.ok) {
                return `Message sent to Slack channel/user ${slack_channel}.`;
            }
            else {
                return `Failed to send Slack message to ${slack_channel} via NLU. Error: ${slackResponse.error}`;
            }
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, there was an issue sending your Slack message.');
    }
}
export async function handleSlackMyAgenda(userId, entities) {
    try {
        const limit = entities?.limit && typeof entities.limit === 'number'
            ? entities.limit
            : 5;
        const events = await listUpcomingEvents(userId, limit);
        if (!events || events.length === 0) {
            const noEventsMessage = "You have no upcoming events on your calendar for the near future, or I couldn't access them (NLU path).";
            try {
                await send(userId, userId, noEventsMessage);
                return "I've checked your calendar; no upcoming events. Sent a note to your Slack DM (NLU path).";
            }
            catch (dmError) {
                return 'No upcoming events found. Tried to DM you on Slack, but failed (NLU path).';
            }
        }
        else {
            let formattedAgenda = `🗓️ Your Upcoming Events (via NLU):\n`;
            for (const event of events) {
                const startTime = new Date(event.startTime).toLocaleString(undefined, {
                    dateStyle: 'short',
                    timeStyle: 'short',
                });
                const endTime = new Date(event.endTime).toLocaleString(undefined, {
                    dateStyle: 'short',
                    timeStyle: 'short',
                });
                formattedAgenda += `- ${event.summary} (from ${startTime} to ${endTime})`;
                if (event.location)
                    formattedAgenda += ` - Location: ${event.location}`;
                if (event.htmlLink)
                    formattedAgenda += ` [View: ${event.htmlLink}]`;
                formattedAgenda += '\n';
            }
            const slackResponse = await send(userId, userId, formattedAgenda);
            if (slackResponse.ok) {
                return "I've sent your agenda to your Slack DM (NLU path)!";
            }
            else {
                return `Sorry, I couldn't send your agenda to Slack (NLU path). Error: ${slackResponse.error}`;
            }
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, an error occurred while processing your agenda for Slack (NLU path).');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2xhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzbGFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsZ0JBQWdCLElBQUksSUFBSSxFQUFFLE1BQU0sZUFBZSxDQUFDO0FBQ3pELE9BQU8sRUFBRSxrQkFBa0IsRUFBRSxNQUFNLGtCQUFrQixDQUFDO0FBRXRELE9BQU8sRUFBRSxXQUFXLEVBQUUsTUFBTSwyQkFBMkIsQ0FBQztBQUV4RCxNQUFNLENBQUMsS0FBSyxVQUFVLHNCQUFzQixDQUMxQyxNQUFjLEVBQ2QsUUFBYTtJQUViLElBQUksQ0FBQztRQUNILE1BQU0sRUFBRSxhQUFhLEVBQUUsWUFBWSxFQUFFLEdBQUcsUUFBUSxDQUFDO1FBQ2pELElBQUksQ0FBQyxhQUFhLElBQUksT0FBTyxhQUFhLEtBQUssUUFBUSxFQUFFLENBQUM7WUFDeEQsT0FBTyw4REFBOEQsQ0FBQztRQUN4RSxDQUFDO2FBQU0sSUFBSSxDQUFDLFlBQVksSUFBSSxPQUFPLFlBQVksS0FBSyxRQUFRLEVBQUUsQ0FBQztZQUM3RCxPQUFPLDJEQUEyRCxDQUFDO1FBQ3JFLENBQUM7YUFBTSxDQUFDO1lBQ04sTUFBTSxhQUFhLEdBQUcsTUFBTSxJQUFJLENBQUMsTUFBTSxFQUFFLGFBQWEsRUFBRSxZQUFZLENBQUMsQ0FBQztZQUN0RSxJQUFJLGFBQWEsQ0FBQyxFQUFFLEVBQUUsQ0FBQztnQkFDckIsT0FBTyxzQ0FBc0MsYUFBYSxHQUFHLENBQUM7WUFDaEUsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLE9BQU8sbUNBQW1DLGFBQWEsb0JBQW9CLGFBQWEsQ0FBQyxLQUFLLEVBQUUsQ0FBQztZQUNuRyxDQUFDO1FBQ0gsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE9BQU8sV0FBVyxDQUNoQixLQUFLLEVBQ0wsdURBQXVELENBQ3hELENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUsbUJBQW1CLENBQ3ZDLE1BQWMsRUFDZCxRQUFhO0lBRWIsSUFBSSxDQUFDO1FBQ0gsTUFBTSxLQUFLLEdBQ1QsUUFBUSxFQUFFLEtBQUssSUFBSSxPQUFPLFFBQVEsQ0FBQyxLQUFLLEtBQUssUUFBUTtZQUNuRCxDQUFDLENBQUMsUUFBUSxDQUFDLEtBQUs7WUFDaEIsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUNSLE1BQU0sTUFBTSxHQUFvQixNQUFNLGtCQUFrQixDQUFDLE1BQU0sRUFBRSxLQUFLLENBQUMsQ0FBQztRQUN4RSxJQUFJLENBQUMsTUFBTSxJQUFJLE1BQU0sQ0FBQyxNQUFNLEtBQUssQ0FBQyxFQUFFLENBQUM7WUFDbkMsTUFBTSxlQUFlLEdBQ25CLHlHQUF5RyxDQUFDO1lBQzVHLElBQUksQ0FBQztnQkFDSCxNQUFNLElBQUksQ0FBQyxNQUFNLEVBQUUsTUFBTSxFQUFFLGVBQWUsQ0FBQyxDQUFDO2dCQUM1QyxPQUFPLDBGQUEwRixDQUFDO1lBQ3BHLENBQUM7WUFBQyxPQUFPLE9BQVksRUFBRSxDQUFDO2dCQUN0QixPQUFPLDRFQUE0RSxDQUFDO1lBQ3RGLENBQUM7UUFDSCxDQUFDO2FBQU0sQ0FBQztZQUNOLElBQUksZUFBZSxHQUFHLHVDQUF1QyxDQUFDO1lBQzlELEtBQUssTUFBTSxLQUFLLElBQUksTUFBTSxFQUFFLENBQUM7Z0JBQzNCLE1BQU0sU0FBUyxHQUFHLElBQUksSUFBSSxDQUFDLEtBQUssQ0FBQyxTQUFTLENBQUMsQ0FBQyxjQUFjLENBQUMsU0FBUyxFQUFFO29CQUNwRSxTQUFTLEVBQUUsT0FBTztvQkFDbEIsU0FBUyxFQUFFLE9BQU87aUJBQ25CLENBQUMsQ0FBQztnQkFDSCxNQUFNLE9BQU8sR0FBRyxJQUFJLElBQUksQ0FBQyxLQUFLLENBQUMsT0FBTyxDQUFDLENBQUMsY0FBYyxDQUFDLFNBQVMsRUFBRTtvQkFDaEUsU0FBUyxFQUFFLE9BQU87b0JBQ2xCLFNBQVMsRUFBRSxPQUFPO2lCQUNuQixDQUFDLENBQUM7Z0JBQ0gsZUFBZSxJQUFJLEtBQUssS0FBSyxDQUFDLE9BQU8sVUFBVSxTQUFTLE9BQU8sT0FBTyxHQUFHLENBQUM7Z0JBQzFFLElBQUksS0FBSyxDQUFDLFFBQVE7b0JBQUUsZUFBZSxJQUFJLGdCQUFnQixLQUFLLENBQUMsUUFBUSxFQUFFLENBQUM7Z0JBQ3hFLElBQUksS0FBSyxDQUFDLFFBQVE7b0JBQUUsZUFBZSxJQUFJLFdBQVcsS0FBSyxDQUFDLFFBQVEsR0FBRyxDQUFDO2dCQUNwRSxlQUFlLElBQUksSUFBSSxDQUFDO1lBQzFCLENBQUM7WUFDRCxNQUFNLGFBQWEsR0FBRyxNQUFNLElBQUksQ0FBQyxNQUFNLEVBQUUsTUFBTSxFQUFFLGVBQWUsQ0FBQyxDQUFDO1lBQ2xFLElBQUksYUFBYSxDQUFDLEVBQUUsRUFBRSxDQUFDO2dCQUNyQixPQUFPLG9EQUFvRCxDQUFDO1lBQzlELENBQUM7aUJBQU0sQ0FBQztnQkFDTixPQUFPLGtFQUFrRSxhQUFhLENBQUMsS0FBSyxFQUFFLENBQUM7WUFDakcsQ0FBQztRQUNILENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixPQUFPLFdBQVcsQ0FDaEIsS0FBSyxFQUNMLDZFQUE2RSxDQUM5RSxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBzZW5kU2xhY2tNZXNzYWdlIGFzIHNlbmQgfSBmcm9tICcuL3NsYWNrU2tpbGxzJztcbmltcG9ydCB7IGxpc3RVcGNvbWluZ0V2ZW50cyB9IGZyb20gJy4vY2FsZW5kYXJTa2lsbHMnO1xuaW1wb3J0IHsgQ2FsZW5kYXJFdmVudCB9IGZyb20gJy4uLy4uL3R5cGVzJztcbmltcG9ydCB7IGhhbmRsZUVycm9yIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2Vycm9ySGFuZGxlcic7XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVTZW5kU2xhY2tNZXNzYWdlKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW50aXRpZXM6IGFueVxuKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IHNsYWNrX2NoYW5uZWwsIG1lc3NhZ2VfdGV4dCB9ID0gZW50aXRpZXM7XG4gICAgaWYgKCFzbGFja19jaGFubmVsIHx8IHR5cGVvZiBzbGFja19jaGFubmVsICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdTbGFjayBjaGFubmVsL3VzZXIgSUQgaXMgcmVxdWlyZWQgdG8gc2VuZCBhIG1lc3NhZ2UgdmlhIE5MVS4nO1xuICAgIH0gZWxzZSBpZiAoIW1lc3NhZ2VfdGV4dCB8fCB0eXBlb2YgbWVzc2FnZV90ZXh0ICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdNZXNzYWdlIHRleHQgaXMgcmVxdWlyZWQgdG8gc2VuZCBhIFNsYWNrIG1lc3NhZ2UgdmlhIE5MVS4nO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBzbGFja1Jlc3BvbnNlID0gYXdhaXQgc2VuZCh1c2VySWQsIHNsYWNrX2NoYW5uZWwsIG1lc3NhZ2VfdGV4dCk7XG4gICAgICBpZiAoc2xhY2tSZXNwb25zZS5vaykge1xuICAgICAgICByZXR1cm4gYE1lc3NhZ2Ugc2VudCB0byBTbGFjayBjaGFubmVsL3VzZXIgJHtzbGFja19jaGFubmVsfS5gO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgcmV0dXJuIGBGYWlsZWQgdG8gc2VuZCBTbGFjayBtZXNzYWdlIHRvICR7c2xhY2tfY2hhbm5lbH0gdmlhIE5MVS4gRXJyb3I6ICR7c2xhY2tSZXNwb25zZS5lcnJvcn1gO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgJ1NvcnJ5LCB0aGVyZSB3YXMgYW4gaXNzdWUgc2VuZGluZyB5b3VyIFNsYWNrIG1lc3NhZ2UuJ1xuICAgICk7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVNsYWNrTXlBZ2VuZGEoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogYW55XG4pOiBQcm9taXNlPHN0cmluZz4ge1xuICB0cnkge1xuICAgIGNvbnN0IGxpbWl0ID1cbiAgICAgIGVudGl0aWVzPy5saW1pdCAmJiB0eXBlb2YgZW50aXRpZXMubGltaXQgPT09ICdudW1iZXInXG4gICAgICAgID8gZW50aXRpZXMubGltaXRcbiAgICAgICAgOiA1O1xuICAgIGNvbnN0IGV2ZW50czogQ2FsZW5kYXJFdmVudFtdID0gYXdhaXQgbGlzdFVwY29taW5nRXZlbnRzKHVzZXJJZCwgbGltaXQpO1xuICAgIGlmICghZXZlbnRzIHx8IGV2ZW50cy5sZW5ndGggPT09IDApIHtcbiAgICAgIGNvbnN0IG5vRXZlbnRzTWVzc2FnZSA9XG4gICAgICAgIFwiWW91IGhhdmUgbm8gdXBjb21pbmcgZXZlbnRzIG9uIHlvdXIgY2FsZW5kYXIgZm9yIHRoZSBuZWFyIGZ1dHVyZSwgb3IgSSBjb3VsZG4ndCBhY2Nlc3MgdGhlbSAoTkxVIHBhdGgpLlwiO1xuICAgICAgdHJ5IHtcbiAgICAgICAgYXdhaXQgc2VuZCh1c2VySWQsIHVzZXJJZCwgbm9FdmVudHNNZXNzYWdlKTtcbiAgICAgICAgcmV0dXJuIFwiSSd2ZSBjaGVja2VkIHlvdXIgY2FsZW5kYXI7IG5vIHVwY29taW5nIGV2ZW50cy4gU2VudCBhIG5vdGUgdG8geW91ciBTbGFjayBETSAoTkxVIHBhdGgpLlwiO1xuICAgICAgfSBjYXRjaCAoZG1FcnJvcjogYW55KSB7XG4gICAgICAgIHJldHVybiAnTm8gdXBjb21pbmcgZXZlbnRzIGZvdW5kLiBUcmllZCB0byBETSB5b3Ugb24gU2xhY2ssIGJ1dCBmYWlsZWQgKE5MVSBwYXRoKS4nO1xuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICBsZXQgZm9ybWF0dGVkQWdlbmRhID0gYPCfl5PvuI8gWW91ciBVcGNvbWluZyBFdmVudHMgKHZpYSBOTFUpOlxcbmA7XG4gICAgICBmb3IgKGNvbnN0IGV2ZW50IG9mIGV2ZW50cykge1xuICAgICAgICBjb25zdCBzdGFydFRpbWUgPSBuZXcgRGF0ZShldmVudC5zdGFydFRpbWUpLnRvTG9jYWxlU3RyaW5nKHVuZGVmaW5lZCwge1xuICAgICAgICAgIGRhdGVTdHlsZTogJ3Nob3J0JyxcbiAgICAgICAgICB0aW1lU3R5bGU6ICdzaG9ydCcsXG4gICAgICAgIH0pO1xuICAgICAgICBjb25zdCBlbmRUaW1lID0gbmV3IERhdGUoZXZlbnQuZW5kVGltZSkudG9Mb2NhbGVTdHJpbmcodW5kZWZpbmVkLCB7XG4gICAgICAgICAgZGF0ZVN0eWxlOiAnc2hvcnQnLFxuICAgICAgICAgIHRpbWVTdHlsZTogJ3Nob3J0JyxcbiAgICAgICAgfSk7XG4gICAgICAgIGZvcm1hdHRlZEFnZW5kYSArPSBgLSAke2V2ZW50LnN1bW1hcnl9IChmcm9tICR7c3RhcnRUaW1lfSB0byAke2VuZFRpbWV9KWA7XG4gICAgICAgIGlmIChldmVudC5sb2NhdGlvbikgZm9ybWF0dGVkQWdlbmRhICs9IGAgLSBMb2NhdGlvbjogJHtldmVudC5sb2NhdGlvbn1gO1xuICAgICAgICBpZiAoZXZlbnQuaHRtbExpbmspIGZvcm1hdHRlZEFnZW5kYSArPSBgIFtWaWV3OiAke2V2ZW50Lmh0bWxMaW5rfV1gO1xuICAgICAgICBmb3JtYXR0ZWRBZ2VuZGEgKz0gJ1xcbic7XG4gICAgICB9XG4gICAgICBjb25zdCBzbGFja1Jlc3BvbnNlID0gYXdhaXQgc2VuZCh1c2VySWQsIHVzZXJJZCwgZm9ybWF0dGVkQWdlbmRhKTtcbiAgICAgIGlmIChzbGFja1Jlc3BvbnNlLm9rKSB7XG4gICAgICAgIHJldHVybiBcIkkndmUgc2VudCB5b3VyIGFnZW5kYSB0byB5b3VyIFNsYWNrIERNIChOTFUgcGF0aCkhXCI7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICByZXR1cm4gYFNvcnJ5LCBJIGNvdWxkbid0IHNlbmQgeW91ciBhZ2VuZGEgdG8gU2xhY2sgKE5MVSBwYXRoKS4gRXJyb3I6ICR7c2xhY2tSZXNwb25zZS5lcnJvcn1gO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgJ1NvcnJ5LCBhbiBlcnJvciBvY2N1cnJlZCB3aGlsZSBwcm9jZXNzaW5nIHlvdXIgYWdlbmRhIGZvciBTbGFjayAoTkxVIHBhdGgpLidcbiAgICApO1xuICB9XG59XG4iXX0=