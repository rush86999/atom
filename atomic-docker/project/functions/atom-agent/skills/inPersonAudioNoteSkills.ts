// In: atomic-docker/project/functions/atom-agent/skills/inPersonAudioNoteSkills.ts

import { listUpcomingEvents } from './calendarSkills'; // Import the calendar skill
// Import central types including AgentSkillContext and AgentClientCommand
import { CalendarEvent, ProcessedNLUResponse, AgentSkillContext, AgentClientCommand } from '../types';

// Local/redefined types for AgentClientCommand and AgentSkillContext are removed.
// They are now imported from ../types


// This response type is specific to this skill's handlers
interface AgentSkillResponse {
  success: boolean;
  message: string;
  sessionTrackingId?: string;
}


/**
 * Handles the START_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export async function handleStartInPersonAudioNoteDirect(
  nluResult: ProcessedNLUResponse, // Use imported ProcessedNLUResponse
  context: AgentSkillContext       // Use redefined AgentSkillContext
): Promise<AgentSkillResponse> {
  console.log(`Agent Skill (Direct): Handling START_IN_PERSON_AUDIO_NOTE for user ${context.userId}`);

  let suggestedTitle = "Audio Note " + new Date().toISOString(); // Default title
  let linkedEventId: string | undefined = undefined;
  let resolvedEventSummary: string | undefined = undefined; // To store summary for title update
  let calendarFeedbackMessage = ""; // For user feedback regarding calendar linking

  // Access entities directly from nluResult.entities (which is Record<string, any>)
  const noteTitleFromEntities = nluResult.entities?.NOTE_TITLE as string | undefined;
  const originalNoteTitleProvided = noteTitleFromEntities && noteTitleFromEntities.trim() !== '';

  if (originalNoteTitleProvided) {
    suggestedTitle = noteTitleFromEntities!.trim();
  }

  const calendarEventContextFromEntities = nluResult.entities?.CALENDAR_EVENT_CONTEXT as string | undefined;
  if (calendarEventContextFromEntities && calendarEventContextFromEntities.trim() !== '') {
    const contextQuery = calendarEventContextFromEntities.trim().toLowerCase();
    console.log(`Agent Skill (Direct): Calendar event context found: "${contextQuery}". Attempting resolution.`);

    try {
      const now = new Date();
      const timeMin = new Date(now.getTime() - 12 * 60 * 60 * 1000).toISOString();
      const timeMax = new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString();

      const eventsResponse = await listUpcomingEvents(context.userId, 15, timeMin, timeMax);

      if (eventsResponse.ok && eventsResponse.data) {
        if (eventsResponse.data.length > 0) {
          const allFetchedEvents: CalendarEvent[] = eventsResponse.data;
          let matchedEvent: CalendarEvent | undefined = undefined;
          const currentTime = new Date().getTime();

          const matchingEvents = allFetchedEvents.filter(event =>
            (event.summary && event.summary.toLowerCase().includes(contextQuery)) ||
            (event.description && event.description.toLowerCase().includes(contextQuery))
          );

          if (matchingEvents.length > 0) {
            matchingEvents.sort((a, b) => {
              const aStart = new Date(a.startTime).getTime();
              const aEnd = new Date(a.endTime).getTime();
              const bStart = new Date(b.startTime).getTime();
              const bEnd = new Date(b.endTime).getTime();
              const aIsCurrent = aStart <= currentTime && aEnd >= currentTime;
              const bIsCurrent = bStart <= currentTime && bEnd >= currentTime;

              if (aIsCurrent && !bIsCurrent) return -1;
              if (!aIsCurrent && bIsCurrent) return 1;
              if (aIsCurrent && bIsCurrent) return bStart - aStart;
              if (aStart > currentTime && bStart > currentTime) return aStart - bStart;
              if (aStart < currentTime && bStart < currentTime) return bEnd - aEnd;
              if (aStart > currentTime) return -1;
              if (bStart > currentTime) return 1;
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
          } else {
            console.log(`Agent Skill (Direct): Could not resolve calendar context "${contextQuery}" to a specific event.`);
            calendarFeedbackMessage = ` (Note: I couldn't find a specific calendar event matching "${calendarEventContextFromEntities.trim()}" to link this note.)`;
          }
        } else { // eventsResponse.data.length === 0
            console.log("Agent Skill (Direct): No calendar events found in the time window for context resolution.");
            calendarFeedbackMessage = ` (Note: I couldn't find any calendar events around this time to link the note to "${calendarEventContextFromEntities.trim()}".)`;
        }
      } else if (!eventsResponse.ok) { // Error fetching events
        console.warn("Agent Skill (Direct): Failed to fetch calendar events for context resolution:", eventsResponse.error?.message);
        calendarFeedbackMessage = " (Note: I had trouble accessing your calendar to link this note.)";
      }
    } catch (error: any) {
      console.error("Agent Skill (Direct): Error during calendar event context resolution:", error.message, error.stack);
      calendarFeedbackMessage = " (Note: An error occurred while trying to check your calendar.)";
    }
  }

  const commandId = `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  const startCommand: AgentClientCommand = {
    command_id: commandId,
    action: 'START_RECORDING_SESSION',
    payload: {
      suggestedTitle: suggestedTitle,
      linkedEventId: linkedEventId,
    }
  };

  try {
    await context.sendCommandToClient(context.userId, startCommand);
    console.log("Agent Skill (Direct): Sent START_RECORDING_SESSION command to client:", startCommand);

    let userResponseMessage = `Okay, attempting to start an audio note titled "${suggestedTitle}". Please check the application window.`;
    if (calendarFeedbackMessage) {
      userResponseMessage += calendarFeedbackMessage;
    }

    return {
      success: true,
      message: userResponseMessage,
      sessionTrackingId: commandId
    };

  } catch (error: any) {
    console.error("Agent Skill (Direct): Error sending START_RECORDING_SESSION command to client:", error.message);
    return {
      success: false,
      message: "Sorry, I couldn't initiate the audio recording session due to an internal communication error.",
    };
  }
}

/**
 * Handles the STOP_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export async function handleStopInPersonAudioNoteDirect(
  nluResult: ProcessedNLUResponse, // Use imported ProcessedNLUResponse
  context: AgentSkillContext       // Use redefined AgentSkillContext
): Promise<AgentSkillResponse> {
  console.log(`Agent Skill (Direct): Handling STOP_IN_PERSON_AUDIO_NOTE for user ${context.userId}`);

  const commandId = `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  const stopCommand: AgentClientCommand = {
    command_id: commandId,
    action: 'STOP_RECORDING_SESSION',
  };

  try {
    await context.sendCommandToClient(context.userId, stopCommand);
    console.log("Agent Skill (Direct): Sent STOP_RECORDING_SESSION command to client:", stopCommand);

    return {
      success: true,
      message: "Okay, I've sent the command to stop the recording. The audio should be processed shortly if recording was active.",
    };
  } catch (error: any) {
    console.error("Agent Skill (Direct): Error sending STOP_RECORDING_SESSION command to client:", error.message);
    return {
      success: false,
      message: "Sorry, I couldn't send the stop command due to an internal communication error.",
    };
  }
}

/**
 * Handles the CANCEL_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export async function handleCancelInPersonAudioNoteDirect(
  nluResult: ProcessedNLUResponse, // Use imported ProcessedNLUResponse
  context: AgentSkillContext       // Use redefined AgentSkillContext
): Promise<AgentSkillResponse> {
  console.log(`Agent Skill (Direct): Handling CANCEL_IN_PERSON_AUDIO_NOTE for user ${context.userId}`);

  const commandId = `cmd_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  const cancelCommand: AgentClientCommand = {
    command_id: commandId,
    action: 'CANCEL_RECORDING_SESSION',
  };

  try {
    await context.sendCommandToClient(context.userId, cancelCommand);
    console.log("Agent Skill (Direct): Sent CANCEL_RECORDING_SESSION command to client:", cancelCommand);

    return {
      success: true,
      message: "Okay, I've cancelled the audio recording session attempt.",
    };
  } catch (error: any) {
    console.error("Agent Skill (Direct): Error sending CANCEL_RECORDING_SESSION command to client:", error.message);
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
    'START_IN_PERSON_AUDIO_NOTE': handleStartInPersonAudioNoteDirect,
    'STOP_IN_PERSON_AUDIO_NOTE': handleStopInPersonAudioNoteDirect,
    'CANCEL_IN_PERSON_AUDIO_NOTE': handleCancelInPersonAudioNoteDirect,
  },
  skillName: "InPersonAudioNoteDirect", // For logging or management
  description: "Handles voice commands to record in-person audio notes with direct client control."
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
