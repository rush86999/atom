import {
  activateConversation,
  deactivateConversation,
  recordUserInteraction,
  recordAgentResponse,
  isConversationActive,
  getConversationStateSnapshot,
  setAgentResponding,
  checkIfAgentIsResponding,
  getConversationHistory,
  _test_setConversationActive, // If testing this internal helper is desired
} from './conversationState'; // Adjust path as necessary
import { HandleMessageResponse } from './handler'; // Assuming this type is needed for history

const IDLE_TIMEOUT_MS = 30 * 1000; // Must match the value in conversationState.ts

describe('Conversation State Manager', () => {
  beforeEach(() => {
    // Reset state before each test by deactivating (which also resets timers and flags)
    // This ensures a clean slate for each test.
    // Directly manipulating globalConversationState is an alternative but less clean.
    deactivateConversation('test_setup_reset');
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers(); // Restore real timers
  });

  test('initial state', () => {
    const state = getConversationStateSnapshot();
    expect(state.isActive).toBe(false);
    expect(state.isAgentResponding).toBe(false);
    expect(state.lastInteractionTime).toBeNull();
    expect(state.conversationHistory).toEqual([]);
    expect(state.idleTimer).toBeNull(); // Assuming timer is null initially
  });

  describe('activateConversation', () => {
    test('should activate conversation and start idle timer', () => {
      const result = activateConversation();
      const state = getConversationStateSnapshot();

      expect(result.active).toBe(true);
      expect(state.isActive).toBe(true);
      expect(state.isAgentResponding).toBe(false); // Explicitly set to false on activation
      expect(state.lastInteractionTime).toBeGreaterThan(0);
      expect(state.idleTimer).not.toBeNull();

      // Check if timer is set for the correct duration
      const timerDetails = jest.getTimerSystem().findTimer(t => t.id === state.idleTimer);
      if(timerDetails) { // Timer ID might not be directly comparable if it's an object
          // This check is a bit fragile as it depends on Jest's internal timer representation
          // A more robust way is to check if deactivate is called after timeout.
      }
      expect(jest.getTimerCount()).toBe(1);
    });

    test('activating an already active conversation should reset timer and interaction time', () => {
      activateConversation(); // First activation
      const initialTime = getConversationStateSnapshot().lastInteractionTime;
      jest.advanceTimersByTime(1000); // Advance time a bit

      activateConversation(); // Second activation
      const state = getConversationStateSnapshot();
      expect(state.isActive).toBe(true);
      expect(state.isAgentResponding).toBe(false);
      expect(state.lastInteractionTime).toBeGreaterThan(initialTime!);
      expect(jest.getTimerCount()).toBe(1); // Should have cleared the old timer and started a new one
    });
  });

  describe('deactivateConversation', () => {
    test('should deactivate conversation and clear idle timer', () => {
      activateConversation();
      expect(getConversationStateSnapshot().isActive).toBe(true);
      expect(jest.getTimerCount()).toBe(1);

      deactivateConversation('test_deactivation');
      const state = getConversationStateSnapshot();
      expect(state.isActive).toBe(false);
      expect(state.isAgentResponding).toBe(false);
      expect(state.lastInteractionTime).toBeNull(); // Reset by deactivate
      expect(jest.getTimerCount()).toBe(0); // Timer cleared
    });
  });

  describe('recordUserInteraction', () => {
    test('should update lastInteractionTime and reset idle timer if active', () => {
      activateConversation();
      const initialTime = getConversationStateSnapshot().lastInteractionTime;
      jest.advanceTimersByTime(IDLE_TIMEOUT_MS / 2); // Advance timer part way

      recordUserInteraction("hello");
      const state = getConversationStateSnapshot();
      expect(state.lastInteractionTime).toBeGreaterThan(initialTime!);
      expect(jest.getTimerCount()).toBe(1); // Timer reset

      // Fast-forward to ensure the *new* timer would fire if not reset again
      jest.advanceTimersByTime(IDLE_TIMEOUT_MS + 100);
      expect(getConversationStateSnapshot().isActive).toBe(false); // Should have timed out by now
    });

    test('should not update interaction time or timer if conversation is inactive', () => {
        const initialTime = getConversationStateSnapshot().lastInteractionTime; // Should be null
        recordUserInteraction("hello");
        const state = getConversationStateSnapshot();
        expect(state.lastInteractionTime).toBe(initialTime); // Remains null
        expect(jest.getTimerCount()).toBe(0); // No timer started
    });
  });

  describe('recordAgentResponse', () => {
    test('should add agent response to conversation history', () => {
      activateConversation();
      const userMessage = "Hello Atom";
      const agentResponse: HandleMessageResponse = { text: "Hello user!" };
      recordUserInteraction(userMessage); // User speaks
      recordAgentResponse(userMessage, agentResponse); // Agent responds

      const history = getConversationHistory();
      expect(history.length).toBe(1);
      expect(history[0].user).toBe(userMessage);
      expect(history[0].agent.text).toBe("Hello user!");
      expect(history[0].timestamp).toBeDefined();
    });

     test('should limit conversation history size', () => {
      activateConversation();
      for (let i = 0; i < 25; i++) {
        recordAgentResponse(`User message ${i}`, { text: `Agent response ${i}` });
      }
      const history = getConversationHistory();
      expect(history.length).toBe(20); // Assuming limit is 20 as in implementation
      expect(history[0].agent.text).toBe('Agent response 5'); // Check first element after shift
    });
  });

  describe('Idle Timeout Logic', () => {
    test('should deactivate conversation after idle timeout', () => {
      activateConversation();
      expect(getConversationStateSnapshot().isActive).toBe(true);

      jest.advanceTimersByTime(IDLE_TIMEOUT_MS + 100); // Advance past timeout

      const state = getConversationStateSnapshot();
      expect(state.isActive).toBe(false);
      expect(state.isAgentResponding).toBe(false);
      expect(jest.getTimerCount()).toBe(0);
    });

    test('interaction before timeout should reset the timer', () => {
      activateConversation();
      jest.advanceTimersByTime(IDLE_TIMEOUT_MS / 2); // Almost timeout

      recordUserInteraction("still here"); // Interaction resets timer
      expect(getConversationStateSnapshot().isActive).toBe(true);

      jest.advanceTimersByTime(IDLE_TIMEOUT_MS / 2); // Advance again, but not enough for new timeout
      expect(getConversationStateSnapshot().isActive).toBe(true);

      jest.advanceTimersByTime(IDLE_TIMEOUT_MS / 2 + 100); // Now it should timeout
      expect(getConversationStateSnapshot().isActive).toBe(false);
    });

    test('idle timer should not deactivate if agent is responding', () => {
      activateConversation();
      setAgentResponding(true); // Agent starts its turn

      // Advance time past the normal idle timeout
      jest.advanceTimersByTime(IDLE_TIMEOUT_MS + 100);

      // Conversation should still be active because agent is responding
      expect(isConversationActive()).toBe(true);
      expect(checkIfAgentIsResponding()).toBe(true);

      setAgentResponding(false); // Agent finishes responding
      // Now the idle timer should effectively start or restart
      expect(jest.getTimerCount()).toBe(1); // A new timer should have been started by setAgentResponding(false)

      jest.advanceTimersByTime(IDLE_TIMEOUT_MS + 100);
      expect(isConversationActive()).toBe(false); // Should now timeout
    });
  });

  describe('setAgentResponding and checkIfAgentIsResponding', () => {
    test('should set and get isAgentResponding state', () => {
      expect(checkIfAgentIsResponding()).toBe(false);
      setAgentResponding(true);
      expect(checkIfAgentIsResponding()).toBe(true);
      setAgentResponding(false);
      expect(checkIfAgentIsResponding()).toBe(false);
    });

    test('setting agent responding to true should clear idle timer if active', () => {
        activateConversation(); // Starts an idle timer
        expect(jest.getTimerCount()).toBe(1);

        // As per current implementation of setAgentResponding -> startIdleTimer,
        // if agent is responding, timer is NOT started.
        // If agent stops responding AND conversation is active, timer IS started.
        setAgentResponding(true);
        // The log in startIdleTimer says "Idle timer not started because agent is currently responding."
        // This means any existing user idle timer should be cleared or effectively paused.
        // The current `startIdleTimer` clears existing timers. If `!isAgentResponding` is false, it won't start a new one.
        // So, if `setAgentResponding(true)` is called, and it calls `startIdleTimer`, the old timer is cleared,
        // and no new one is set.
        expect(jest.getTimerCount()).toBe(0);
    });

    test('setting agent responding to false should start idle timer if conversation is active', () => {
        activateConversation();
        setAgentResponding(true); // Timer count becomes 0
        expect(jest.getTimerCount()).toBe(0);

        setAgentResponding(false); // Should start the timer
        expect(jest.getTimerCount()).toBe(1);
        expect(isConversationActive()).toBe(true); // Still active
    });
  });

  describe('_test_setConversationActive (internal helper)', () => {
    test('should activate conversation using helper', () => {
      _test_setConversationActive(true);
      expect(isConversationActive()).toBe(true);
      expect(checkIfAgentIsResponding()).toBe(false);
      expect(jest.getTimerCount()).toBe(1);
    });

    test('should deactivate conversation using helper', () => {
      activateConversation(); // Ensure it's active first
      _test_setConversationActive(false);
      expect(isConversationActive()).toBe(false);
      expect(checkIfAgentIsResponding()).toBe(false);
      expect(jest.getTimerCount()).toBe(0);
    });
  });
});
