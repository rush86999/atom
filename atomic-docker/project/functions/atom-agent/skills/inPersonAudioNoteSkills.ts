// In: atomic-docker/project/functions/atom-agent/skills/inPersonAudioNoteSkills.ts

// --- Define Placeholder Types (replace with actual types from your project) ---
interface NluEntity {
  entity: string;
  value: any;
  // other properties like confidence, start, end
}

interface NluIntent {
  name: string;
  confidence: number;
}

interface NluIntentResult {
  intent: NluIntent;
  entities?: NluEntity[];
  raw_input?: string;
}

interface AgentContext {
  userId: string;
  // other contextual information like current session, device capabilities, etc.
  // Function to send command to client - this needs to be part of the context or globally available
  sendCommandToClient: (userId: string, command: AgentClientCommand) => Promise<void>;
}

// NEW/REVISED Placeholder Types for Agent-Client Communication
interface AgentClientCommand {
  command_id: string; // Unique ID for this command
  action: 'START_RECORDING_SESSION' | 'STOP_RECORDING_SESSION' | 'CANCEL_RECORDING_SESSION';
  payload?: {
    suggestedTitle?: string;
    linkedEventId?: string;
    // Other parameters like recording quality hints, max duration, etc.
  };
}

// ClientAckEvent is not directly used by agent skill sending commands, but good for context
// interface ClientAckEvent { // Client sends this back to agent
//   command_id: string; // Corresponds to the AgentClientCommand
//   status: 'ACKNOWLEDGED' | 'STARTED' | 'ERROR' | 'USER_DENIED_PERMISSION';
//   payload?: any; // e.g., error message
// }

interface AgentSkillResponse {
  success: boolean;
  message: string; // Text response for the user
  // No clientActionHint in the old sense, commands are direct
  sessionTrackingId?: string; // Optional: if agent needs to track this session via command_id
}
// --- End Placeholder Types ---


/**
 * Handles the START_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export async function handleStartInPersonAudioNoteDirect(
  nluResult: NluIntentResult,
  context: AgentContext
): Promise<AgentSkillResponse> {
  console.log(`Agent Skill (Direct): Handling START_IN_PERSON_AUDIO_NOTE for user ${context.userId}`);

  let suggestedTitle = "Audio Note " + new Date().toISOString(); // Default title
  let linkedEventId: string | undefined = undefined;

  const noteTitleEntity = nluResult.entities?.find(e => e.entity === 'NOTE_TITLE');
  if (noteTitleEntity && typeof noteTitleEntity.value === 'string') {
    suggestedTitle = noteTitleEntity.value;
  }

  const calendarEventEntity = nluResult.entities?.find(e => e.entity === 'CALENDAR_EVENT_CONTEXT');
  if (calendarEventEntity && typeof calendarEventEntity.value === 'string') {
    // TODO: Resolve calendarEventEntity.value to an eventId and potentially update suggestedTitle
    // linkedEventId = await context.agent.skills.calendar.resolveEventToId(calendarEventEntity.value, context.userId);
    // if (!noteTitleEntity && resolvedEventTitle) suggestedTitle = `Audio Note for ${resolvedEventTitle}`;
    console.log("Agent Skill (Direct): Calendar event context found (resolution not implemented):", calendarEventEntity.value);
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

    const userResponseMessage = `Okay, attempting to start an audio note titled "${suggestedTitle}". Please check the application window.`;

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
  nluResult: NluIntentResult,
  context: AgentContext
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
  nluResult: NluIntentResult,
  context: AgentContext
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
