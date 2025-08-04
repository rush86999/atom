// In: atomic-docker/project/functions/atom-agent/skills/inPersonAudioNoteSkills.ts
import { listUpcomingEvents } from './calendarSkills'; // Import the calendar skill
/**
 * Handles the START_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export async function handleStartInPersonAudioNoteDirect(nluResult, // Use imported ProcessedNLUResponse
context // Use redefined AgentSkillContext
) {
    console.log(`Agent Skill (Direct): Handling START_IN_PERSON_AUDIO_NOTE for user ${context.userId}`);
    let suggestedTitle = 'Audio Note ' + new Date().toISOString(); // Default title
    let linkedEventId = undefined;
    let resolvedEventSummary = undefined; // To store summary for title update
    let calendarFeedbackMessage = ''; // For user feedback regarding calendar linking
    // Access entities directly from nluResult.entities (which is Record<string, any>)
    const noteTitleFromEntities = nluResult.entities?.NOTE_TITLE;
    const originalNoteTitleProvided = noteTitleFromEntities && noteTitleFromEntities.trim() !== '';
    if (originalNoteTitleProvided) {
        suggestedTitle = noteTitleFromEntities.trim();
    }
    const calendarEventContextFromEntities = nluResult.entities
        ?.CALENDAR_EVENT_CONTEXT;
    if (calendarEventContextFromEntities &&
        calendarEventContextFromEntities.trim() !== '') {
        const contextQuery = calendarEventContextFromEntities.trim().toLowerCase();
        console.log(`Agent Skill (Direct): Calendar event context found: "${contextQuery}". Attempting resolution.`);
        try {
            const now = new Date();
            const timeMin = new Date(now.getTime() - 12 * 60 * 60 * 1000).toISOString();
            const timeMax = new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString();
            const eventsResponse = await listUpcomingEvents(context.userId, 15, timeMin, timeMax);
            if (eventsResponse.ok && eventsResponse.data) {
                if (eventsResponse.data.length > 0) {
                    const allFetchedEvents = eventsResponse.data;
                    let matchedEvent = undefined;
                    const currentTime = new Date().getTime();
                    const matchingEvents = allFetchedEvents.filter((event) => (event.summary &&
                        event.summary.toLowerCase().includes(contextQuery)) ||
                        (event.description &&
                            event.description.toLowerCase().includes(contextQuery)));
                    if (matchingEvents.length > 0) {
                        matchingEvents.sort((a, b) => {
                            const aStart = new Date(a.startTime).getTime();
                            const aEnd = new Date(a.endTime).getTime();
                            const bStart = new Date(b.startTime).getTime();
                            const bEnd = new Date(b.endTime).getTime();
                            const aIsCurrent = aStart <= currentTime && aEnd >= currentTime;
                            const bIsCurrent = bStart <= currentTime && bEnd >= currentTime;
                            if (aIsCurrent && !bIsCurrent)
                                return -1;
                            if (!aIsCurrent && bIsCurrent)
                                return 1;
                            if (aIsCurrent && bIsCurrent)
                                return bStart - aStart;
                            if (aStart > currentTime && bStart > currentTime)
                                return aStart - bStart;
                            if (aStart < currentTime && bStart < currentTime)
                                return bEnd - aEnd;
                            if (aStart > currentTime)
                                return -1;
                            if (bStart > currentTime)
                                return 1;
                            return bEnd - aEnd;
                        });
                        matchedEvent = matchingEvents[0];
                    }
                    if (matchedEvent) {
                        linkedEventId = matchedEvent.id;
                        resolvedEventSummary = matchedEvent.summary;
                        console.log(`Agent Skill (Direct): Resolved calendar context "${contextQuery}" to event: "${resolvedEventSummary}" (ID: ${linkedEventId})`);
                        if (!originalNoteTitleProvided && resolvedEventSummary) {
                            suggestedTitle = `Audio Note for '${resolvedEventSummary}'`;
                        }
                        // calendarFeedbackMessage = ` (Linked to: '${resolvedEventSummary}')`; // Optional: positive feedback
                    }
                    else {
                        console.log(`Agent Skill (Direct): Could not resolve calendar context "${contextQuery}" to a specific event.`);
                        calendarFeedbackMessage = ` (Note: I couldn't find a specific calendar event matching "${calendarEventContextFromEntities.trim()}" to link this note.)`;
                    }
                }
                else {
                    // eventsResponse.data.length === 0
                    console.log('Agent Skill (Direct): No calendar events found in the time window for context resolution.');
                    calendarFeedbackMessage = ` (Note: I couldn't find any calendar events around this time to link the note to "${calendarEventContextFromEntities.trim()}".)`;
                }
            }
            else if (!eventsResponse.ok) {
                // Error fetching events
                console.warn('Agent Skill (Direct): Failed to fetch calendar events for context resolution:', eventsResponse.error?.message);
                calendarFeedbackMessage =
                    ' (Note: I had trouble accessing your calendar to link this note.)';
            }
        }
        catch (error) {
            console.error('Agent Skill (Direct): Error during calendar event context resolution:', error.message, error.stack);
            calendarFeedbackMessage =
                ' (Note: An error occurred while trying to check your calendar.)';
        }
    }
    const commandId = `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const startCommand = {
        command_id: commandId,
        action: 'START_RECORDING_SESSION',
        payload: {
            suggestedTitle: suggestedTitle,
            linkedEventId: linkedEventId,
        },
    };
    try {
        await context.sendCommandToClient(context.userId, startCommand);
        console.log('Agent Skill (Direct): Sent START_RECORDING_SESSION command to client:', startCommand);
        let userResponseMessage = `Okay, attempting to start an audio note titled "${suggestedTitle}". Please check the application window.`;
        if (calendarFeedbackMessage) {
            userResponseMessage += calendarFeedbackMessage;
        }
        return {
            success: true,
            message: userResponseMessage,
            sessionTrackingId: commandId,
        };
    }
    catch (error) {
        console.error('Agent Skill (Direct): Error sending START_RECORDING_SESSION command to client:', error.message);
        return {
            success: false,
            message: "Sorry, I couldn't initiate the audio recording session due to an internal communication error.",
        };
    }
}
/**
 * Handles the STOP_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export async function handleStopInPersonAudioNoteDirect(nluResult, // Use imported ProcessedNLUResponse
context // Use redefined AgentSkillContext
) {
    console.log(`Agent Skill (Direct): Handling STOP_IN_PERSON_AUDIO_NOTE for user ${context.userId}`);
    const commandId = `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const stopCommand = {
        command_id: commandId,
        action: 'STOP_RECORDING_SESSION',
    };
    try {
        await context.sendCommandToClient(context.userId, stopCommand);
        console.log('Agent Skill (Direct): Sent STOP_RECORDING_SESSION command to client:', stopCommand);
        return {
            success: true,
            message: "Okay, I've sent the command to stop the recording. The audio should be processed shortly if recording was active.",
        };
    }
    catch (error) {
        console.error('Agent Skill (Direct): Error sending STOP_RECORDING_SESSION command to client:', error.message);
        return {
            success: false,
            message: "Sorry, I couldn't send the stop command due to an internal communication error.",
        };
    }
}
/**
 * Handles the CANCEL_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export async function handleCancelInPersonAudioNoteDirect(nluResult, // Use imported ProcessedNLUResponse
context // Use redefined AgentSkillContext
) {
    console.log(`Agent Skill (Direct): Handling CANCEL_IN_PERSON_AUDIO_NOTE for user ${context.userId}`);
    const commandId = `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const cancelCommand = {
        command_id: commandId,
        action: 'CANCEL_RECORDING_SESSION',
    };
    try {
        await context.sendCommandToClient(context.userId, cancelCommand);
        console.log('Agent Skill (Direct): Sent CANCEL_RECORDING_SESSION command to client:', cancelCommand);
        return {
            success: true,
            message: "Okay, I've cancelled the audio recording session attempt.",
        };
    }
    catch (error) {
        console.error('Agent Skill (Direct): Error sending CANCEL_RECORDING_SESSION command to client:', error.message);
        return {
            success: false,
            message: "Sorry, I couldn't send the cancel command due to an internal communication error.",
        };
    }
}
/**
 * Example of how these handlers might be registered or mapped in the agent's skill routing logic.
 * The actual mechanism will depend on the Atom agent's architecture.
 * This manifest should be imported and used by the agent's main router.
 */
export const InPersonAudioNoteDirectSkillManifest = {
    intentHandlers: {
        START_IN_PERSON_AUDIO_NOTE: handleStartInPersonAudioNoteDirect,
        STOP_IN_PERSON_AUDIO_NOTE: handleStopInPersonAudioNoteDirect,
        CANCEL_IN_PERSON_AUDIO_NOTE: handleCancelInPersonAudioNoteDirect,
    },
    skillName: 'InPersonAudioNoteDirect', // For logging or management
    description: 'Handles voice commands to record in-person audio notes with direct client control.',
};
// It's assumed that the `AgentContext` will be populated with a `sendCommandToClient` method
// by the core agent framework, specific to the active user's connection (e.g., WebSocket).
// Example:
// class AgentFramework {
//   clientConnections: Map<string, WebSocketLikeInterface>;
//
//   async sendCommandToClientImpl(userId: string, command: AgentClientCommand): Promise<void> {
//     const clientConnection = this.clientConnections.get(userId);
//     if (clientConnection) {
//       clientConnection.send(JSON.stringify(command)); // Or however commands are serialized
//     } else {
//       throw new Error(`No active client connection found for user ${userId}`);
//     }
//   }
//
//   getContextForUser(userId: string): AgentContext {
//     return {
//       userId: userId,
//       sendCommandToClient: this.sendCommandToClientImpl.bind(this)
//       // ... other context items
//     };
//   }
// }
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5QZXJzb25BdWRpb05vdGVTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpblBlcnNvbkF1ZGlvTm90ZVNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxtRkFBbUY7QUFFbkYsT0FBTyxFQUFFLGtCQUFrQixFQUFFLE1BQU0sa0JBQWtCLENBQUMsQ0FBQyw0QkFBNEI7QUFtQm5GOztHQUVHO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSxrQ0FBa0MsQ0FDdEQsU0FBK0IsRUFBRSxvQ0FBb0M7QUFDckUsT0FBMEIsQ0FBQyxrQ0FBa0M7O0lBRTdELE9BQU8sQ0FBQyxHQUFHLENBQ1Qsc0VBQXNFLE9BQU8sQ0FBQyxNQUFNLEVBQUUsQ0FDdkYsQ0FBQztJQUVGLElBQUksY0FBYyxHQUFHLGFBQWEsR0FBRyxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRSxDQUFDLENBQUMsZ0JBQWdCO0lBQy9FLElBQUksYUFBYSxHQUF1QixTQUFTLENBQUM7SUFDbEQsSUFBSSxvQkFBb0IsR0FBdUIsU0FBUyxDQUFDLENBQUMsb0NBQW9DO0lBQzlGLElBQUksdUJBQXVCLEdBQUcsRUFBRSxDQUFDLENBQUMsK0NBQStDO0lBRWpGLGtGQUFrRjtJQUNsRixNQUFNLHFCQUFxQixHQUFHLFNBQVMsQ0FBQyxRQUFRLEVBQUUsVUFFckMsQ0FBQztJQUNkLE1BQU0seUJBQXlCLEdBQzdCLHFCQUFxQixJQUFJLHFCQUFxQixDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsQ0FBQztJQUUvRCxJQUFJLHlCQUF5QixFQUFFLENBQUM7UUFDOUIsY0FBYyxHQUFHLHFCQUFzQixDQUFDLElBQUksRUFBRSxDQUFDO0lBQ2pELENBQUM7SUFFRCxNQUFNLGdDQUFnQyxHQUFHLFNBQVMsQ0FBQyxRQUFRO1FBQ3pELEVBQUUsc0JBQTRDLENBQUM7SUFDakQsSUFDRSxnQ0FBZ0M7UUFDaEMsZ0NBQWdDLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxFQUM5QyxD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QWMsRUFBRTtRQUNkLDBCQUEwQixFQUFFLGtDQUFrQztRQUM5RCx5QkFBeUIsRUFBRSxpQ0FBaUM7UUFDNUQsMkJBQTJCLEVBQUUsbUNBQW1DO0tBQ2pFO0lBQ0QsU0FBUyxFQUFFLHlCQUF5QixFQUFFLDRCQUE0QjtJQUNsRSxXQUFXLEVBQ1Qsb0ZBQW9GO0NBQ3ZGLENBQUM7QUFFRiw2RkFBNkY7QUFDN0YsMkZBQTJGO0FBQzNGLFdBQVc7QUFDWCx5QkFBeUI7QUFDekIsNERBQTREO0FBQzVELEVBQUU7QUFDRixnR0FBZ0c7QUFDaEcsbUVBQW1FO0FBQ25FLDhCQUE4QjtBQUM5Qiw4RkFBOEY7QUFDOUYsZUFBZTtBQUNmLGlGQUFpRjtBQUNqRixRQUFRO0FBQ1IsTUFBTTtBQUNOLEVBQUU7QUFDRixzREFBc0Q7QUFDdEQsZUFBZTtBQUNmLHdCQUF3QjtBQUN4QixxRUFBcUU7QUFDckUsbUNBQW1DO0FBQ25DLFNBQVM7QUFDVCxNQUFNO0FBQ04sSUFBSSIsInNvdXJjZXNDb250ZW50IjpbIi8vIEluOiBhdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL2F0b20tYWdlbnQvc2tpbGxzL2luUGVyc29uQXVkaW9Ob3RlU2tpbGxzLnRzXG5cbmltcG9ydCB7IGxpc3RVcGNvbWluZ0V2ZW50cyB9IGZyb20gJy4vY2FsZW5kYXJTa2lsbHMnOyAvLyBJbXBvcnQgdGhlIGNhbGVuZGFyIHNraWxsXG4vLyBJbXBvcnQgY2VudHJhbCB0eXBlcyBpbmNsdWRpbmcgQWdlbnRTa2lsbENvbnRleHQgYW5kIEFnZW50Q2xpZW50Q29tbWFuZFxuaW1wb3J0IHtcbiAgQ2FsZW5kYXJFdmVudCxcbiAgUHJvY2Vzc2VkTkxVUmVzcG9uc2UsXG4gIEFnZW50U2tpbGxDb250ZXh0LFxuICBBZ2VudENsaWVudENvbW1hbmQsXG59IGZyb20gJy4uL3R5cGVzJztcblxuLy8gTG9jYWwvcmVkZWZpbmVkIHR5cGVzIGZvciBBZ2VudENsaWVudENvbW1hbmQgYW5kIEFnZW50U2tpbGxDb250ZXh0IGFyZSByZW1vdmVkLlxuLy8gVGhleSBhcmUgbm93IGltcG9ydGVkIGZyb20gLi4vdHlwZXNcblxuLy8gVGhpcyByZXNwb25zZSB0eXBlIGlzIHNwZWNpZmljIHRvIHRoaXMgc2tpbGwncyBoYW5kbGVyc1xuaW50ZXJmYWNlIEFnZW50U2tpbGxSZXNwb25zZSB7XG4gIHN1Y2Nlc3M6IGJvb2xlYW47XG4gIG1lc3NhZ2U6IHN0cmluZztcbiAgc2Vzc2lvblRyYWNraW5nSWQ/OiBzdHJpbmc7XG59XG5cbi8qKlxuICogSGFuZGxlcyB0aGUgU1RBUlRfSU5fUEVSU09OX0FVRElPX05PVEUgaW50ZW50IHdpdGggZGlyZWN0IGNsaWVudCBjb250cm9sLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlU3RhcnRJblBlcnNvbkF1ZGlvTm90ZURpcmVjdChcbiAgbmx1UmVzdWx0OiBQcm9jZXNzZWROTFVSZXNwb25zZSwgLy8gVXNlIGltcG9ydGVkIFByb2Nlc3NlZE5MVVJlc3BvbnNlXG4gIGNvbnRleHQ6IEFnZW50U2tpbGxDb250ZXh0IC8vIFVzZSByZWRlZmluZWQgQWdlbnRTa2lsbENvbnRleHRcbik6IFByb21pc2U8QWdlbnRTa2lsbFJlc3BvbnNlPiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBBZ2VudCBTa2lsbCAoRGlyZWN0KTogSGFuZGxpbmcgU1RBUlRfSU5fUEVSU09OX0FVRElPX05PVEUgZm9yIHVzZXIgJHtjb250ZXh0LnVzZXJJZH1gXG4gICk7XG5cbiAgbGV0IHN1Z2dlc3RlZFRpdGxlID0gJ0F1ZGlvIE5vdGUgJyArIG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKTsgLy8gRGVmYXVsdCB0aXRsZVxuICBsZXQgbGlua2VkRXZlbnRJZDogc3RyaW5nIHwgdW5kZWZpbmVkID0gdW5kZWZpbmVkO1xuICBsZXQgcmVzb2x2ZWRFdmVudFN1bW1hcnk6IHN0cmluZyB8IHVuZGVmaW5lZCA9IHVuZGVmaW5lZDsgLy8gVG8gc3RvcmUgc3VtbWFyeSBmb3IgdGl0bGUgdXBkYXRlXG4gIGxldCBjYWxlbmRhckZlZWRiYWNrTWVzc2FnZSA9ICcnOyAvLyBGb3IgdXNlciBmZWVkYmFjayByZWdhcmRpbmcgY2FsZW5kYXIgbGlua2luZ1xuXG4gIC8vIEFjY2VzcyBlbnRpdGllcyBkaXJlY3RseSBmcm9tIG5sdVJlc3VsdC5lbnRpdGllcyAod2hpY2ggaXMgUmVjb3JkPHN0cmluZywgYW55PilcbiAgY29uc3Qgbm90ZVRpdGxlRnJvbUVudGl0aWVzID0gbmx1UmVzdWx0LmVudGl0aWVzPy5OT1RFX1RJVExFIGFzXG4gICAgfCBzdHJpbmdcbiAgICB8IHVuZGVmaW5lZDtcbiAgY29uc3Qgb3JpZ2luYWxOb3RlVGl0bGVQcm92aWRlZCA9XG4gICAgbm90ZVRpdGxlRnJvbUVudGl0aWVzICYmIG5vdGVUaXRsZUZyb21FbnRpdGllcy50cmltKCkgIT09ICcnO1xuXG4gIGlmIChvcmlnaW5hbE5vdGVUaXRsZVByb3ZpZGVkKSB7XG4gICAgc3VnZ2VzdGVkVGl0bGUgPSBub3RlVGl0bGVGcm9tRW50aXRpZXMhLnRyaW0oKTtcbiAgfVxuXG4gIGNvbnN0IGNhbGVuZGFyRXZlbnRDb250ZXh0RnJvbUVudGl0aWVzID0gbmx1UmVzdWx0LmVudGl0aWVzXG4gICAgPy5DQUxFTkRBUl9FVkVOVF9DT05URVhUIGFzIHN0cmluZyB8IHVuZGVmaW5lZDtcbiAgaWYgKFxuICAgIGNhbGVuZGFyRXZlbnRDb250ZXh0RnJvbUVudGl0aWVzICYmXG4gICAgY2FsZW5kYXJFdmVudENvbnRleHRGcm9tRW50aXRpZXMudHJpbSgpICE9PSAnJ1xuICApIHtcbiAgICBjb25zdCBjb250ZXh0UXVlcnkgPSBjYWxlbmRhckV2ZW50Q29udGV4dEZyb21FbnRpdGllcy50cmltKCkudG9Mb3dlckNhc2UoKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBBZ2VudCBTa2lsbCAoRGlyZWN0KTogQ2FsZW5kYXIgZXZlbnQgY29udGV4dCBmb3VuZDogXCIke2NvbnRleHRRdWVyeX1cIi4gQXR0ZW1wdGluZyByZXNvbHV0aW9uLmBcbiAgICApO1xuXG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IG5vdyA9IG5ldyBEYXRlKCk7XG4gICAgICBjb25zdCB0aW1lTWluID0gbmV3IERhdGUoXG4gICAgICAgIG5vdy5nZXRUaW1lKCkgLSAxMiAqIDYwICogNjAgKiAxMDAwXG4gICAgICApLnRvSVNPU3RyaW5nKCk7XG4gICAgICBjb25zdCB0aW1lTWF4ID0gbmV3IERhdGUoXG4gICAgICAgIG5vdy5nZXRUaW1lKCkgKyAyNCAqIDYwICogNjAgKiAxMDAwXG4gICAgICApLnRvSVNPU3RyaW5nKCk7XG5cbiAgICAgIGNvbnN0IGV2ZW50c1Jlc3BvbnNlID0gYXdhaXQgbGlzdFVwY29taW5nRXZlbnRzKFxuICAgICAgICBjb250ZXh0LnVzZXJJZCxcbiAgICAgICAgMTUsXG4gICAgICAgIHRpbWVNaW4sXG4gICAgICAgIHRpbWVNYXhcbiAgICAgICk7XG5cbiAgICAgIGlmIChldmVudHNSZXNwb25zZS5vayAmJiBldmVudHNSZXNwb25zZS5kYXRhKSB7XG4gICAgICAgIGlmIChldmVudHNSZXNwb25zZS5kYXRhLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICBjb25zdCBhbGxGZXRjaGVkRXZlbnRzOiBDYWxlbmRhckV2ZW50W10gPSBldmVudHNSZXNwb25zZS5kYXRhO1xuICAgICAgICAgIGxldCBtYXRjaGVkRXZlbnQ6IENhbGVuZGFyRXZlbnQgfCB1bmRlZmluZWQgPSB1bmRlZmluZWQ7XG4gICAgICAgICAgY29uc3QgY3VycmVudFRpbWUgPSBuZXcgRGF0ZSgpLmdldFRpbWUoKTtcblxuICAgICAgICAgIGNvbnN0IG1hdGNoaW5nRXZlbnRzID0gYWxsRmV0Y2hlZEV2ZW50cy5maWx0ZXIoXG4gICAgICAgICAgICAoZXZlbnQpID0+XG4gICAgICAgICAgICAgIChldmVudC5zdW1tYXJ5ICYmXG4gICAgICAgICAgICAgICAgZXZlbnQuc3VtbWFyeS50b0xvd2VyQ2FzZSgpLmluY2x1ZGVzKGNvbnRleHRRdWVyeSkpIHx8XG4gICAgICAgICAgICAgIChldmVudC5kZXNjcmlwdGlvbiAmJlxuICAgICAgICAgICAgICAgIGV2ZW50LmRlc2NyaXB0aW9uLnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMoY29udGV4dFF1ZXJ5KSlcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgaWYgKG1hdGNoaW5nRXZlbnRzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgIG1hdGNoaW5nRXZlbnRzLnNvcnQoKGEsIGIpID0+IHtcbiAgICAgICAgICAgICAgY29uc3QgYVN0YXJ0ID0gbmV3IERhdGUoYS5zdGFydFRpbWUpLmdldFRpbWUoKTtcbiAgICAgICAgICAgICAgY29uc3QgYUVuZCA9IG5ldyBEYXRlKGEuZW5kVGltZSkuZ2V0VGltZSgpO1xuICAgICAgICAgICAgICBjb25zdCBiU3RhcnQgPSBuZXcgRGF0ZShiLnN0YXJ0VGltZSkuZ2V0VGltZSgpO1xuICAgICAgICAgICAgICBjb25zdCBiRW5kID0gbmV3IERhdGUoYi5lbmRUaW1lKS5nZXRUaW1lKCk7XG4gICAgICAgICAgICAgIGNvbnN0IGFJc0N1cnJlbnQgPSBhU3RhcnQgPD0gY3VycmVudFRpbWUgJiYgYUVuZCA+PSBjdXJyZW50VGltZTtcbiAgICAgICAgICAgICAgY29uc3QgYklzQ3VycmVudCA9IGJTdGFydCA8PSBjdXJyZW50VGltZSAmJiBiRW5kID49IGN1cnJlbnRUaW1lO1xuXG4gICAgICAgICAgICAgIGlmIChhSXNDdXJyZW50ICYmICFiSXNDdXJyZW50KSByZXR1cm4gLTE7XG4gICAgICAgICAgICAgIGlmICghYUlzQ3VycmVudCAmJiBiSXNDdXJyZW50KSByZXR1cm4gMTtcbiAgICAgICAgICAgICAgaWYgKGFJc0N1cnJlbnQgJiYgYklzQ3VycmVudCkgcmV0dXJuIGJTdGFydCAtIGFTdGFydDtcbiAgICAgICAgICAgICAgaWYgKGFTdGFydCA+IGN1cnJlbnRUaW1lICYmIGJTdGFydCA+IGN1cnJlbnRUaW1lKVxuICAgICAgICAgICAgICAgIHJldHVybiBhU3RhcnQgLSBiU3RhcnQ7XG4gICAgICAgICAgICAgIGlmIChhU3RhcnQgPCBjdXJyZW50VGltZSAmJiBiU3RhcnQgPCBjdXJyZW50VGltZSlcbiAgICAgICAgICAgICAgICByZXR1cm4gYkVuZCAtIGFFbmQ7XG4gICAgICAgICAgICAgIGlmIChhU3RhcnQgPiBjdXJyZW50VGltZSkgcmV0dXJuIC0xO1xuICAgICAgICAgICAgICBpZiAoYlN0YXJ0ID4gY3VycmVudFRpbWUpIHJldHVybiAxO1xuICAgICAgICAgICAgICByZXR1cm4gYkVuZCAtIGFFbmQ7XG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIG1hdGNoZWRFdmVudCA9IG1hdGNoaW5nRXZlbnRzWzBdO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChtYXRjaGVkRXZlbnQpIHtcbiAgICAgICAgICAgIGxpbmtlZEV2ZW50SWQgPSBtYXRjaGVkRXZlbnQuaWQ7XG4gICAgICAgICAgICByZXNvbHZlZEV2ZW50U3VtbWFyeSA9IG1hdGNoZWRFdmVudC5zdW1tYXJ5O1xuICAgICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICAgIGBBZ2VudCBTa2lsbCAoRGlyZWN0KTogUmVzb2x2ZWQgY2FsZW5kYXIgY29udGV4dCBcIiR7Y29udGV4dFF1ZXJ5fVwiIHRvIGV2ZW50OiBcIiR7cmVzb2x2ZWRFdmVudFN1bW1hcnl9XCIgKElEOiAke2xpbmtlZEV2ZW50SWR9KWBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBpZiAoIW9yaWdpbmFsTm90ZVRpdGxlUHJvdmlkZWQgJiYgcmVzb2x2ZWRFdmVudFN1bW1hcnkpIHtcbiAgICAgICAgICAgICAgc3VnZ2VzdGVkVGl0bGUgPSBgQXVkaW8gTm90ZSBmb3IgJyR7cmVzb2x2ZWRFdmVudFN1bW1hcnl9J2A7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICAvLyBjYWxlbmRhckZlZWRiYWNrTWVzc2FnZSA9IGAgKExpbmtlZCB0bzogJyR7cmVzb2x2ZWRFdmVudFN1bW1hcnl9JylgOyAvLyBPcHRpb25hbDogcG9zaXRpdmUgZmVlZGJhY2tcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICAgIGBBZ2VudCBTa2lsbCAoRGlyZWN0KTogQ291bGQgbm90IHJlc29sdmUgY2FsZW5kYXIgY29udGV4dCBcIiR7Y29udGV4dFF1ZXJ5fVwiIHRvIGEgc3BlY2lmaWMgZXZlbnQuYFxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGNhbGVuZGFyRmVlZGJhY2tNZXNzYWdlID0gYCAoTm90ZTogSSBjb3VsZG4ndCBmaW5kIGEgc3BlY2lmaWMgY2FsZW5kYXIgZXZlbnQgbWF0Y2hpbmcgXCIke2NhbGVuZGFyRXZlbnRDb250ZXh0RnJvbUVudGl0aWVzLnRyaW0oKX1cIiB0byBsaW5rIHRoaXMgbm90ZS4pYDtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgLy8gZXZlbnRzUmVzcG9uc2UuZGF0YS5sZW5ndGggPT09IDBcbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgICdBZ2VudCBTa2lsbCAoRGlyZWN0KTogTm8gY2FsZW5kYXIgZXZlbnRzIGZvdW5kIGluIHRoZSB0aW1lIHdpbmRvdyBmb3IgY29udGV4dCByZXNvbHV0aW9uLidcbiAgICAgICAgICApO1xuICAgICAgICAgIGNhbGVuZGFyRmVlZGJhY2tNZXNzYWdlID0gYCAoTm90ZTogSSBjb3VsZG4ndCBmaW5kIGFueSBjYWxlbmRhciBldmVudHMgYXJvdW5kIHRoaXMgdGltZSB0byBsaW5rIHRoZSBub3RlIHRvIFwiJHtjYWxlbmRhckV2ZW50Q29udGV4dEZyb21FbnRpdGllcy50cmltKCl9XCIuKWA7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSBpZiAoIWV2ZW50c1Jlc3BvbnNlLm9rKSB7XG4gICAgICAgIC8vIEVycm9yIGZldGNoaW5nIGV2ZW50c1xuICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgJ0FnZW50IFNraWxsIChEaXJlY3QpOiBGYWlsZWQgdG8gZmV0Y2ggY2FsZW5kYXIgZXZlbnRzIGZvciBjb250ZXh0IHJlc29sdXRpb246JyxcbiAgICAgICAgICBldmVudHNSZXNwb25zZS5lcnJvcj8ubWVzc2FnZVxuICAgICAgICApO1xuICAgICAgICBjYWxlbmRhckZlZWRiYWNrTWVzc2FnZSA9XG4gICAgICAgICAgJyAoTm90ZTogSSBoYWQgdHJvdWJsZSBhY2Nlc3NpbmcgeW91ciBjYWxlbmRhciB0byBsaW5rIHRoaXMgbm90ZS4pJztcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnQWdlbnQgU2tpbGwgKERpcmVjdCk6IEVycm9yIGR1cmluZyBjYWxlbmRhciBldmVudCBjb250ZXh0IHJlc29sdXRpb246JyxcbiAgICAgICAgZXJyb3IubWVzc2FnZSxcbiAgICAgICAgZXJyb3Iuc3RhY2tcbiAgICAgICk7XG4gICAgICBjYWxlbmRhckZlZWRiYWNrTWVzc2FnZSA9XG4gICAgICAgICcgKE5vdGU6IEFuIGVycm9yIG9jY3VycmVkIHdoaWxlIHRyeWluZyB0byBjaGVjayB5b3VyIGNhbGVuZGFyLiknO1xuICAgIH1cbiAgfVxuXG4gIGNvbnN0IGNvbW1hbmRJZCA9IGBjbWRfJHtEYXRlLm5vdygpfV8ke01hdGgucmFuZG9tKCkudG9TdHJpbmcoMzYpLnN1YnN0cmluZygyLCA3KX1gO1xuICBjb25zdCBzdGFydENvbW1hbmQ6IEFnZW50Q2xpZW50Q29tbWFuZCA9IHtcbiAgICBjb21tYW5kX2lkOiBjb21tYW5kSWQsXG4gICAgYWN0aW9uOiAnU1RBUlRfUkVDT1JESU5HX1NFU1NJT04nLFxuICAgIHBheWxvYWQ6IHtcbiAgICAgIHN1Z2dlc3RlZFRpdGxlOiBzdWdnZXN0ZWRUaXRsZSxcbiAgICAgIGxpbmtlZEV2ZW50SWQ6IGxpbmtlZEV2ZW50SWQsXG4gICAgfSxcbiAgfTtcblxuICB0cnkge1xuICAgIGF3YWl0IGNvbnRleHQuc2VuZENvbW1hbmRUb0NsaWVudChjb250ZXh0LnVzZXJJZCwgc3RhcnRDb21tYW5kKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgICdBZ2VudCBTa2lsbCAoRGlyZWN0KTogU2VudCBTVEFSVF9SRUNPUkRJTkdfU0VTU0lPTiBjb21tYW5kIHRvIGNsaWVudDonLFxuICAgICAgc3RhcnRDb21tYW5kXG4gICAgKTtcblxuICAgIGxldCB1c2VyUmVzcG9uc2VNZXNzYWdlID0gYE9rYXksIGF0dGVtcHRpbmcgdG8gc3RhcnQgYW4gYXVkaW8gbm90ZSB0aXRsZWQgXCIke3N1Z2dlc3RlZFRpdGxlfVwiLiBQbGVhc2UgY2hlY2sgdGhlIGFwcGxpY2F0aW9uIHdpbmRvdy5gO1xuICAgIGlmIChjYWxlbmRhckZlZWRiYWNrTWVzc2FnZSkge1xuICAgICAgdXNlclJlc3BvbnNlTWVzc2FnZSArPSBjYWxlbmRhckZlZWRiYWNrTWVzc2FnZTtcbiAgICB9XG5cbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIG1lc3NhZ2U6IHVzZXJSZXNwb25zZU1lc3NhZ2UsXG4gICAgICBzZXNzaW9uVHJhY2tpbmdJZDogY29tbWFuZElkLFxuICAgIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgJ0FnZW50IFNraWxsIChEaXJlY3QpOiBFcnJvciBzZW5kaW5nIFNUQVJUX1JFQ09SRElOR19TRVNTSU9OIGNvbW1hbmQgdG8gY2xpZW50OicsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOlxuICAgICAgICBcIlNvcnJ5LCBJIGNvdWxkbid0IGluaXRpYXRlIHRoZSBhdWRpbyByZWNvcmRpbmcgc2Vzc2lvbiBkdWUgdG8gYW4gaW50ZXJuYWwgY29tbXVuaWNhdGlvbiBlcnJvci5cIixcbiAgICB9O1xuICB9XG59XG5cbi8qKlxuICogSGFuZGxlcyB0aGUgU1RPUF9JTl9QRVJTT05fQVVESU9fTk9URSBpbnRlbnQgd2l0aCBkaXJlY3QgY2xpZW50IGNvbnRyb2wuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVTdG9wSW5QZXJzb25BdWRpb05vdGVEaXJlY3QoXG4gIG5sdVJlc3VsdDogUHJvY2Vzc2VkTkxVUmVzcG9uc2UsIC8vIFVzZSBpbXBvcnRlZCBQcm9jZXNzZWROTFVSZXNwb25zZVxuICBjb250ZXh0OiBBZ2VudFNraWxsQ29udGV4dCAvLyBVc2UgcmVkZWZpbmVkIEFnZW50U2tpbGxDb250ZXh0XG4pOiBQcm9taXNlPEFnZW50U2tpbGxSZXNwb25zZT4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBgQWdlbnQgU2tpbGwgKERpcmVjdCk6IEhhbmRsaW5nIFNUT1BfSU5fUEVSU09OX0FVRElPX05PVEUgZm9yIHVzZXIgJHtjb250ZXh0LnVzZXJJZH1gXG4gICk7XG5cbiAgY29uc3QgY29tbWFuZElkID0gYGNtZF8ke0RhdGUubm93KCl9XyR7TWF0aC5yYW5kb20oKS50b1N0cmluZygzNikuc3Vic3RyaW5nKDIsIDcpfWA7XG4gIGNvbnN0IHN0b3BDb21tYW5kOiBBZ2VudENsaWVudENvbW1hbmQgPSB7XG4gICAgY29tbWFuZF9pZDogY29tbWFuZElkLFxuICAgIGFjdGlvbjogJ1NUT1BfUkVDT1JESU5HX1NFU1NJT04nLFxuICB9O1xuXG4gIHRyeSB7XG4gICAgYXdhaXQgY29udGV4dC5zZW5kQ29tbWFuZFRvQ2xpZW50KGNvbnRleHQudXNlcklkLCBzdG9wQ29tbWFuZCk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICAnQWdlbnQgU2tpbGwgKERpcmVjdCk6IFNlbnQgU1RPUF9SRUNPUkRJTkdfU0VTU0lPTiBjb21tYW5kIHRvIGNsaWVudDonLFxuICAgICAgc3RvcENvbW1hbmRcbiAgICApO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICBtZXNzYWdlOlxuICAgICAgICBcIk9rYXksIEkndmUgc2VudCB0aGUgY29tbWFuZCB0byBzdG9wIHRoZSByZWNvcmRpbmcuIFRoZSBhdWRpbyBzaG91bGQgYmUgcHJvY2Vzc2VkIHNob3J0bHkgaWYgcmVjb3JkaW5nIHdhcyBhY3RpdmUuXCIsXG4gICAgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnQWdlbnQgU2tpbGwgKERpcmVjdCk6IEVycm9yIHNlbmRpbmcgU1RPUF9SRUNPUkRJTkdfU0VTU0lPTiBjb21tYW5kIHRvIGNsaWVudDonLFxuICAgICAgZXJyb3IubWVzc2FnZVxuICAgICk7XG4gICAgcmV0dXJuIHtcbiAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgbWVzc2FnZTpcbiAgICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBzZW5kIHRoZSBzdG9wIGNvbW1hbmQgZHVlIHRvIGFuIGludGVybmFsIGNvbW11bmljYXRpb24gZXJyb3IuXCIsXG4gICAgfTtcbiAgfVxufVxuXG4vKipcbiAqIEhhbmRsZXMgdGhlIENBTkNFTF9JTl9QRVJTT05fQVVESU9fTk9URSBpbnRlbnQgd2l0aCBkaXJlY3QgY2xpZW50IGNvbnRyb2wuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVDYW5jZWxJblBlcnNvbkF1ZGlvTm90ZURpcmVjdChcbiAgbmx1UmVzdWx0OiBQcm9jZXNzZWROTFVSZXNwb25zZSwgLy8gVXNlIGltcG9ydGVkIFByb2Nlc3NlZE5MVVJlc3BvbnNlXG4gIGNvbnRleHQ6IEFnZW50U2tpbGxDb250ZXh0IC8vIFVzZSByZWRlZmluZWQgQWdlbnRTa2lsbENvbnRleHRcbik6IFByb21pc2U8QWdlbnRTa2lsbFJlc3BvbnNlPiB7XG4gIGNvbnNvbGUubG9nKFxuICAgIGBBZ2VudCBTa2lsbCAoRGlyZWN0KTogSGFuZGxpbmcgQ0FOQ0VMX0lOX1BFUlNPTl9BVURJT19OT1RFIGZvciB1c2VyICR7Y29udGV4dC51c2VySWR9YFxuICApO1xuXG4gIGNvbnN0IGNvbW1hbmRJZCA9IGBjbWRfJHtEYXRlLm5vdygpfV8ke01hdGgucmFuZG9tKCkudG9TdHJpbmcoMzYpLnN1YnN0cmluZygyLCA3KX1gO1xuICBjb25zdCBjYW5jZWxDb21tYW5kOiBBZ2VudENsaWVudENvbW1hbmQgPSB7XG4gICAgY29tbWFuZF9pZDogY29tbWFuZElkLFxuICAgIGFjdGlvbjogJ0NBTkNFTF9SRUNPUkRJTkdfU0VTU0lPTicsXG4gIH07XG5cbiAgdHJ5IHtcbiAgICBhd2FpdCBjb250ZXh0LnNlbmRDb21tYW5kVG9DbGllbnQoY29udGV4dC51c2VySWQsIGNhbmNlbENvbW1hbmQpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ0FnZW50IFNraWxsIChEaXJlY3QpOiBTZW50IENBTkNFTF9SRUNPUkRJTkdfU0VTU0lPTiBjb21tYW5kIHRvIGNsaWVudDonLFxuICAgICAgY2FuY2VsQ29tbWFuZFxuICAgICk7XG5cbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIG1lc3NhZ2U6IFwiT2theSwgSSd2ZSBjYW5jZWxsZWQgdGhlIGF1ZGlvIHJlY29yZGluZyBzZXNzaW9uIGF0dGVtcHQuXCIsXG4gICAgfTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnQWdlbnQgU2tpbGwgKERpcmVjdCk6IEVycm9yIHNlbmRpbmcgQ0FOQ0VMX1JFQ09SRElOR19TRVNTSU9OIGNvbW1hbmQgdG8gY2xpZW50OicsXG4gICAgICBlcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOlxuICAgICAgICBcIlNvcnJ5LCBJIGNvdWxkbid0IHNlbmQgdGhlIGNhbmNlbCBjb21tYW5kIGR1ZSB0byBhbiBpbnRlcm5hbCBjb21tdW5pY2F0aW9uIGVycm9yLlwiLFxuICAgIH07XG4gIH1cbn1cblxuLyoqXG4gKiBFeGFtcGxlIG9mIGhvdyB0aGVzZSBoYW5kbGVycyBtaWdodCBiZSByZWdpc3RlcmVkIG9yIG1hcHBlZCBpbiB0aGUgYWdlbnQncyBza2lsbCByb3V0aW5nIGxvZ2ljLlxuICogVGhlIGFjdHVhbCBtZWNoYW5pc20gd2lsbCBkZXBlbmQgb24gdGhlIEF0b20gYWdlbnQncyBhcmNoaXRlY3R1cmUuXG4gKiBUaGlzIG1hbmlmZXN0IHNob3VsZCBiZSBpbXBvcnRlZCBhbmQgdXNlZCBieSB0aGUgYWdlbnQncyBtYWluIHJvdXRlci5cbiAqL1xuZXhwb3J0IGNvbnN0IEluUGVyc29uQXVkaW9Ob3RlRGlyZWN0U2tpbGxNYW5pZmVzdCA9IHtcbiAgaW50ZW50SGFuZGxlcnM6IHtcbiAgICBTVEFSVF9JTl9QRVJTT05fQVVESU9fTk9URTogaGFuZGxlU3RhcnRJblBlcnNvbkF1ZGlvTm90ZURpcmVjdCxcbiAgICBTVE9QX0lOX1BFUlNPTl9BVURJT19OT1RFOiBoYW5kbGVTdG9wSW5QZXJzb25BdWRpb05vdGVEaXJlY3QsXG4gICAgQ0FOQ0VMX0lOX1BFUlNPTl9BVURJT19OT1RFOiBoYW5kbGVDYW5jZWxJblBlcnNvbkF1ZGlvTm90ZURpcmVjdCxcbiAgfSxcbiAgc2tpbGxOYW1lOiAnSW5QZXJzb25BdWRpb05vdGVEaXJlY3QnLCAvLyBGb3IgbG9nZ2luZyBvciBtYW5hZ2VtZW50XG4gIGRlc2NyaXB0aW9uOlxuICAgICdIYW5kbGVzIHZvaWNlIGNvbW1hbmRzIHRvIHJlY29yZCBpbi1wZXJzb24gYXVkaW8gbm90ZXMgd2l0aCBkaXJlY3QgY2xpZW50IGNvbnRyb2wuJyxcbn07XG5cbi8vIEl0J3MgYXNzdW1lZCB0aGF0IHRoZSBgQWdlbnRDb250ZXh0YCB3aWxsIGJlIHBvcHVsYXRlZCB3aXRoIGEgYHNlbmRDb21tYW5kVG9DbGllbnRgIG1ldGhvZFxuLy8gYnkgdGhlIGNvcmUgYWdlbnQgZnJhbWV3b3JrLCBzcGVjaWZpYyB0byB0aGUgYWN0aXZlIHVzZXIncyBjb25uZWN0aW9uIChlLmcuLCBXZWJTb2NrZXQpLlxuLy8gRXhhbXBsZTpcbi8vIGNsYXNzIEFnZW50RnJhbWV3b3JrIHtcbi8vICAgY2xpZW50Q29ubmVjdGlvbnM6IE1hcDxzdHJpbmcsIFdlYlNvY2tldExpa2VJbnRlcmZhY2U+O1xuLy9cbi8vICAgYXN5bmMgc2VuZENvbW1hbmRUb0NsaWVudEltcGwodXNlcklkOiBzdHJpbmcsIGNvbW1hbmQ6IEFnZW50Q2xpZW50Q29tbWFuZCk6IFByb21pc2U8dm9pZD4ge1xuLy8gICAgIGNvbnN0IGNsaWVudENvbm5lY3Rpb24gPSB0aGlzLmNsaWVudENvbm5lY3Rpb25zLmdldCh1c2VySWQpO1xuLy8gICAgIGlmIChjbGllbnRDb25uZWN0aW9uKSB7XG4vLyAgICAgICBjbGllbnRDb25uZWN0aW9uLnNlbmQoSlNPTi5zdHJpbmdpZnkoY29tbWFuZCkpOyAvLyBPciBob3dldmVyIGNvbW1hbmRzIGFyZSBzZXJpYWxpemVkXG4vLyAgICAgfSBlbHNlIHtcbi8vICAgICAgIHRocm93IG5ldyBFcnJvcihgTm8gYWN0aXZlIGNsaWVudCBjb25uZWN0aW9uIGZvdW5kIGZvciB1c2VyICR7dXNlcklkfWApO1xuLy8gICAgIH1cbi8vICAgfVxuLy9cbi8vICAgZ2V0Q29udGV4dEZvclVzZXIodXNlcklkOiBzdHJpbmcpOiBBZ2VudENvbnRleHQge1xuLy8gICAgIHJldHVybiB7XG4vLyAgICAgICB1c2VySWQ6IHVzZXJJZCxcbi8vICAgICAgIHNlbmRDb21tYW5kVG9DbGllbnQ6IHRoaXMuc2VuZENvbW1hbmRUb0NsaWVudEltcGwuYmluZCh0aGlzKVxuLy8gICAgICAgLy8gLi4uIG90aGVyIGNvbnRleHQgaXRlbXNcbi8vICAgICB9O1xuLy8gICB9XG4vLyB9XG4iXX0=