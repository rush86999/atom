// Manages the state of the conversation with the Atom agent

import { HandleMessageResponse } from './handler'; // Assuming handler.ts exports this

const IDLE_TIMEOUT_MS = 30 * 1000; // 30 seconds
const MAX_TURN_HISTORY_LENGTH = 10; // Limit for STM turn history

interface ConversationState {
  isActive: boolean;
  isAgentResponding: boolean; // New state: true if agent is currently "speaking" or processing a response
  lastInteractionTime: number | null;
  conversationHistory: Array<{ user: string; agent: HandleMessageResponse; timestamp: number }>; // Retained for existing detailed history
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

// In-memory store for conversation state.
const globalConversationState: ConversationState = {
  isActive: false,
  isAgentResponding: false,
  lastInteractionTime: null,
  conversationHistory: [], // Retained for existing detailed history
  idleTimer: null,

  // Initialize STM fields
  currentIntent: null,
  identifiedEntities: null,
  userGoal: null,
  turnHistory: [],
  ltmContext: null,
};

function log(message: string) {
  console.log(`[ConversationState] ${new Date().toISOString()}: ${message}`);
}

export function getConversationStateSnapshot(): Readonly<ConversationState> {
  // Return a copy to prevent direct modification of the state object
  return JSON.parse(JSON.stringify(globalConversationState));
}

function clearIdleTimer() {
  if (globalConversationState.idleTimer) {
    clearTimeout(globalConversationState.idleTimer);
    globalConversationState.idleTimer = null;
  }
}

export function setAgentResponding(isResponding: boolean) {
  globalConversationState.isAgentResponding = isResponding;
  log(`Agent responding state set to: ${isResponding}`);
  if (isResponding) {
    // If agent starts responding, we might want to temporarily pause the idle timer,
    // or handle it such that user can interrupt without idle timeout issues.
    // For now, an explicit interrupt signal will be the primary mechanism.
    // clearIdleTimer(); // Option: clear idle timer when agent starts responding
  } else {
    // If agent finished responding and conversation is still active, restart idle timer
    if (globalConversationState.isActive) {
      startIdleTimer();
    }
  }
}

export function checkIfAgentIsResponding(): boolean {
  return globalConversationState.isAgentResponding;
}

export function deactivateConversation(reason: string = "timeout") {
  clearIdleTimer();
  if (globalConversationState.isActive || globalConversationState.isAgentResponding) {
    globalConversationState.isActive = false;
    globalConversationState.isAgentResponding = false; // Ensure this is also reset
    globalConversationState.lastInteractionTime = null;
    globalConversationState.ltmContext = null; // Reset LTM context
    log(`Conversation deactivated due to ${reason}. LTM context cleared.`);
  }
}

function startIdleTimer() {
  clearIdleTimer();
  // Only start idle timer if agent is NOT responding, and conversation IS active
  if (!globalConversationState.isAgentResponding && globalConversationState.isActive) {
    globalConversationState.idleTimer = setTimeout(() => {
      if (globalConversationState.isActive && !globalConversationState.isAgentResponding) { // Double check state
        deactivateConversation("idle_timeout");
      }
    }, IDLE_TIMEOUT_MS);
    log(`Idle timer started for ${IDLE_TIMEOUT_MS / 1000} seconds.`);
  } else if (globalConversationState.isAgentResponding) {
    log("Idle timer not started because agent is currently responding.");
  } else if (!globalConversationState.isActive) {
    log("Idle timer not started because conversation is not active.");
  }
}

export function activateConversation(): { status: string; active: boolean } {
  const wasActive = globalConversationState.isActive;
  globalConversationState.isActive = true;
  globalConversationState.isAgentResponding = false; // Agent is not responding at point of activation
  globalConversationState.lastInteractionTime = Date.now();
  globalConversationState.ltmContext = null; // Reset LTM context on new activation
  startIdleTimer();

  if (!wasActive) {
    log("Conversation activated. LTM context cleared.");
    return { status: "Conversation activated.", active: true };
  } else {
    log("Conversation was already active. Interaction time and timer reset. Agent responding state ensured false. LTM context cleared.");
    return { status: "Conversation was already active. State reset for new interaction.", active: true };
  }
}

export function recordUserInteraction(text: string) {
  if (!globalConversationState.isActive) {
    log("Interaction recorded (text received) while conversation is inactive. This shouldn't lead to processing by agent logic.");
    return; // Don't update interaction time or restart timer if not active
  }
  // If user speaks, it implies they are interrupting or starting new turn.
  // Agent should no longer be considered "responding" from this point for this new input.
  // However, the /interrupt endpoint is the more explicit way to stop agent actions.
  // This function primarily resets the idle timer for the user's current speech.
  globalConversationState.lastInteractionTime = Date.now();
  startIdleTimer();
  log(`User interaction recorded. Time and timer reset. Text: "${text.substring(0, 50)}..."`);
}

export function recordAgentResponse(
  userText: string,
  agentResponse: HandleMessageResponse,
  intent?: string,
  entities?: Record<string, any>
) {
    // Record to existing conversationHistory
    globalConversationState.conversationHistory.push({
        user: userText,
        agent: agentResponse,
        timestamp: Date.now()
    });
    if (globalConversationState.conversationHistory.length > 20) { // Existing limit
        globalConversationState.conversationHistory.shift();
    }
    log("Agent response recorded in detailed history.");

    // Update new turnHistory for STM
    const turn = {
        userInput: userText,
        agentResponse: agentResponse, // Or a summary/specific part of it
        intent: intent,
        entities: entities,
        timestamp: Date.now()
    };
    globalConversationState.turnHistory.push(turn);
    if (globalConversationState.turnHistory.length > MAX_TURN_HISTORY_LENGTH) {
        globalConversationState.turnHistory.shift();
    }
    log(`Turn recorded in STM history. Current STM history length: ${globalConversationState.turnHistory.length}`);

    // Potentially update currentIntent and identifiedEntities from the latest turn
    if (intent) {
        globalConversationState.currentIntent = intent;
        log(`Current intent updated to: ${intent}`);
    }
    if (entities) {
        globalConversationState.identifiedEntities = entities;
        log(`Identified entities updated.`);
    }
}

export function updateIntentAndEntities(intent: string | null, entities: Record<string, any> | null) {
  globalConversationState.currentIntent = intent;
  globalConversationState.identifiedEntities = entities;
  log(`Intent and entities updated: Intent - ${intent}, Entities - ${JSON.stringify(entities)}`);
}

export function updateUserGoal(goal: string | null) {
  globalConversationState.userGoal = goal;
  log(`User goal updated to: ${goal}`);
}

export function updateLTMContext(context: any[] | null) {
  globalConversationState.ltmContext = context;
  if (context) {
    log(`LTM context updated with ${context.length} items.`);
  } else {
    log('LTM context cleared.');
  }
}

export function isConversationActive(): boolean {
  return globalConversationState.isActive;
}

export function getConversationHistory(): Readonly<Array<{ user: string; agent: HandleMessageResponse; timestamp: number }>> {
    return globalConversationState.conversationHistory;
}

// Example of how to expose a function to manually set state for testing (as requested)
// This would typically be part of a testing setup, not production code.
export function _test_setConversationActive(active: boolean) {
  if (active) {
    activateConversation();
  } else {
    deactivateConversation("manual test override");
  }
  log(`Conversation state manually set to active: ${active} for testing.`);
}

log("Conversation state manager initialized.");
