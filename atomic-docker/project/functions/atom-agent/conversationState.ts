// Manages the state of the conversation with the Atom agent

import { HandleMessageResponse } from './handler'; // Assuming handler.ts exports this

const IDLE_TIMEOUT_MS = 30 * 1000; // 30 seconds
const MAX_TURN_HISTORY_LENGTH = 10; // Limit for STM turn history

export type InterfaceType = 'text' | 'voice';

interface ConversationState {
  isActive: boolean;
  isAgentResponding: boolean; // New state: true if agent is currently "speaking" or processing a response
  lastInteractionTime: number | null;
  conversationHistory: Array<{
    user: string;
    agent: HandleMessageResponse;
    timestamp: number;
  }>; // Retained for existing detailed history
  idleTimer: NodeJS.Timeout | null;

  // New STM fields
  currentIntent: string | null;
  identifiedEntities: Record<string, any> | null;
  userGoal: string | null;
  turnHistory: Array<{
    userInput: string;
    agentResponse: any; // Consider using a more specific type if available, like HandleMessageResponse
    intent?: string;
    entities?: Record<string, any>;
    timestamp: number;
  }>;
  ltmContext: any[] | null; // For storing results from LTM queries
}

// In-memory store for conversation states, keyed by InterfaceType.
const conversationStates = new Map<InterfaceType, ConversationState>();

function getOrCreateConversationState(
  interfaceType: InterfaceType
): ConversationState {
  if (!conversationStates.has(interfaceType)) {
    conversationStates.set(interfaceType, {
      isActive: false,
      isAgentResponding: false,
      lastInteractionTime: null,
      conversationHistory: [],
      idleTimer: null,
      currentIntent: null,
      identifiedEntities: null,
      userGoal: null,
      turnHistory: [],
      ltmContext: null,
    });
  }
  return conversationStates.get(interfaceType)!;
}

function log(interfaceType: InterfaceType, message: string) {
  console.log(
    `[ConversationState][${interfaceType}] ${new Date().toISOString()}: ${message}`
  );
}

export function getConversationStateSnapshot(
  interfaceType: InterfaceType
): Readonly<ConversationState> {
  const state = getOrCreateConversationState(interfaceType);
  // Return a copy to prevent direct modification of the state object
  return JSON.parse(JSON.stringify(state));
}

function clearIdleTimer(interfaceType: InterfaceType) {
  const state = getOrCreateConversationState(interfaceType);
  if (state.idleTimer) {
    clearTimeout(state.idleTimer);
    state.idleTimer = null;
  }
}

export function setAgentResponding(
  interfaceType: InterfaceType,
  isResponding: boolean
) {
  const state = getOrCreateConversationState(interfaceType);
  state.isAgentResponding = isResponding;
  log(interfaceType, `Agent responding state set to: ${isResponding}`);
  if (isResponding) {
    // If agent starts responding, we might want to temporarily pause the idle timer,
    // or handle it such that user can interrupt without idle timeout issues.
    // For now, an explicit interrupt signal will be the primary mechanism.
    // clearIdleTimer(interfaceType); // Option: clear idle timer when agent starts responding
  } else {
    // If agent finished responding and conversation is still active, restart idle timer
    if (state.isActive) {
      startIdleTimer(interfaceType);
    }
  }
}

export function checkIfAgentIsResponding(
  interfaceType: InterfaceType
): boolean {
  const state = getOrCreateConversationState(interfaceType);
  return state.isAgentResponding;
}

export function deactivateConversation(
  interfaceType: InterfaceType,
  reason: string = 'timeout'
) {
  clearIdleTimer(interfaceType);
  const state = getOrCreateConversationState(interfaceType);
  if (state.isActive || state.isAgentResponding) {
    state.isActive = false;
    state.isAgentResponding = false; // Ensure this is also reset
    state.lastInteractionTime = null;
    state.ltmContext = null; // Reset LTM context
    log(
      interfaceType,
      `Conversation deactivated due to ${reason}. LTM context cleared.`
    );
  }
}

function startIdleTimer(interfaceType: InterfaceType) {
  clearIdleTimer(interfaceType);
  const state = getOrCreateConversationState(interfaceType);
  // Only start idle timer if agent is NOT responding, and conversation IS active
  if (!state.isAgentResponding && state.isActive) {
    state.idleTimer = setTimeout(() => {
      const currentState = getOrCreateConversationState(interfaceType); // Re-fetch current state
      if (currentState.isActive && !currentState.isAgentResponding) {
        // Double check state
        deactivateConversation(interfaceType, 'idle_timeout');
      }
    }, IDLE_TIMEOUT_MS);
    log(
      interfaceType,
      `Idle timer started for ${IDLE_TIMEOUT_MS / 1000} seconds.`
    );
  } else if (state.isAgentResponding) {
    log(
      interfaceType,
      'Idle timer not started because agent is currently responding.'
    );
  } else if (!state.isActive) {
    log(
      interfaceType,
      'Idle timer not started because conversation is not active.'
    );
  }
}

export function activateConversation(interfaceType: InterfaceType): {
  status: string;
  active: boolean;
} {
  const state = getOrCreateConversationState(interfaceType);
  const wasActive = state.isActive;
  state.isActive = true;
  state.isAgentResponding = false; // Agent is not responding at point of activation
  state.lastInteractionTime = Date.now();
  state.ltmContext = null; // Reset LTM context on new activation
  startIdleTimer(interfaceType);

  if (!wasActive) {
    log(interfaceType, 'Conversation activated. LTM context cleared.');
    return { status: 'Conversation activated.', active: true };
  } else {
    log(
      interfaceType,
      'Conversation was already active. Interaction time and timer reset. Agent responding state ensured false. LTM context cleared.'
    );
    return {
      status:
        'Conversation was already active. State reset for new interaction.',
      active: true,
    };
  }
}

export function recordUserInteraction(
  interfaceType: InterfaceType,
  text: string
) {
  const state = getOrCreateConversationState(interfaceType);
  if (!state.isActive) {
    log(
      interfaceType,
      "Interaction recorded (text received) while conversation is inactive. This shouldn't lead to processing by agent logic."
    );
    return; // Don't update interaction time or restart timer if not active
  }
  // If user speaks, it implies they are interrupting or starting new turn.
  // Agent should no longer be considered "responding" from this point for this new input.
  // However, the /interrupt endpoint is the more explicit way to stop agent actions.
  // This function primarily resets the idle timer for the user's current speech.
  state.lastInteractionTime = Date.now();
  startIdleTimer(interfaceType);
  log(
    interfaceType,
    `User interaction recorded. Time and timer reset. Text: "${text.substring(0, 50)}..."`
  );
}

export function recordAgentResponse(
  interfaceType: InterfaceType,
  userText: string,
  agentResponse: HandleMessageResponse,
  intent?: string,
  entities?: Record<string, any>
) {
  const state = getOrCreateConversationState(interfaceType);
  // Record to existing conversationHistory
  state.conversationHistory.push({
    user: userText,
    agent: agentResponse,
    timestamp: Date.now(),
  });
  if (state.conversationHistory.length > 20) {
    // Existing limit
    state.conversationHistory.shift();
  }
  log(interfaceType, 'Agent response recorded in detailed history.');

  // Update new turnHistory for STM
  const turn = {
    userInput: userText,
    agentResponse: agentResponse, // Or a summary/specific part of it
    intent: intent,
    entities: entities,
    timestamp: Date.now(),
  };
  state.turnHistory.push(turn);
  if (state.turnHistory.length > MAX_TURN_HISTORY_LENGTH) {
    state.turnHistory.shift();
  }
  log(
    interfaceType,
    `Turn recorded in STM history. Current STM history length: ${state.turnHistory.length}`
  );

  // Potentially update currentIntent and identifiedEntities from the latest turn
  if (intent) {
    state.currentIntent = intent;
    log(interfaceType, `Current intent updated to: ${intent}`);
  }
  if (entities) {
    state.identifiedEntities = entities;
    log(interfaceType, `Identified entities updated.`);
  }
}

export function updateIntentAndEntities(
  interfaceType: InterfaceType,
  intent: string | null,
  entities: Record<string, any> | null
) {
  const state = getOrCreateConversationState(interfaceType);
  state.currentIntent = intent;
  state.identifiedEntities = entities;
  log(
    interfaceType,
    `Intent and entities updated: Intent - ${intent}, Entities - ${JSON.stringify(entities)}`
  );
}

export function updateUserGoal(
  interfaceType: InterfaceType,
  goal: string | null
) {
  const state = getOrCreateConversationState(interfaceType);
  state.userGoal = goal;
  log(interfaceType, `User goal updated to: ${goal}`);
}

export function updateLTMContext(
  interfaceType: InterfaceType,
  context: any[] | null
) {
  const state = getOrCreateConversationState(interfaceType);
  state.ltmContext = context;
  if (context) {
    log(interfaceType, `LTM context updated with ${context.length} items.`);
  } else {
    log(interfaceType, 'LTM context cleared.');
  }
}

export function isConversationActive(interfaceType: InterfaceType): boolean {
  const state = getOrCreateConversationState(interfaceType);
  return state.isActive;
}

export function getConversationHistory(
  interfaceType: InterfaceType
): Readonly<
  Array<{ user: string; agent: HandleMessageResponse; timestamp: number }>
> {
  const state = getOrCreateConversationState(interfaceType);
  return state.conversationHistory;
}

// Example of how to expose a function to manually set state for testing (as requested)
// This would typically be part of a testing setup, not production code.
export function _test_setConversationActive(
  interfaceType: InterfaceType,
  active: boolean
) {
  if (active) {
    activateConversation(interfaceType);
  } else {
    deactivateConversation(interfaceType, 'manual test override');
  }
  log(
    interfaceType,
    `Conversation state manually set to active: ${active} for testing.`
  );
}

log('text', 'Conversation state manager initialized for text interface.');
log('voice', 'Conversation state manager initialized for voice interface.');
