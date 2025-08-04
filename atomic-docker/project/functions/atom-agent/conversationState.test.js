import { activateConversation, deactivateConversation, recordUserInteraction, recordAgentResponse, isConversationActive, getConversationStateSnapshot, setAgentResponding, checkIfAgentIsResponding, getConversationHistory, _test_setConversationActive, // If testing this internal helper is desired
 } from './conversationState'; // Adjust path as necessary
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
            const timerDetails = jest
                .getTimerSystem()
                .findTimer((t) => t.id === state.idleTimer);
            if (timerDetails) {
                // Timer ID might not be directly comparable if it's an object
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
            expect(state.lastInteractionTime).toBeGreaterThan(initialTime);
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
            recordUserInteraction('hello');
            const state = getConversationStateSnapshot();
            expect(state.lastInteractionTime).toBeGreaterThan(initialTime);
            expect(jest.getTimerCount()).toBe(1); // Timer reset
            // Fast-forward to ensure the *new* timer would fire if not reset again
            jest.advanceTimersByTime(IDLE_TIMEOUT_MS + 100);
            expect(getConversationStateSnapshot().isActive).toBe(false); // Should have timed out by now
        });
        test('should not update interaction time or timer if conversation is inactive', () => {
            const initialTime = getConversationStateSnapshot().lastInteractionTime; // Should be null
            recordUserInteraction('hello');
            const state = getConversationStateSnapshot();
            expect(state.lastInteractionTime).toBe(initialTime); // Remains null
            expect(jest.getTimerCount()).toBe(0); // No timer started
        });
    });
    describe('recordAgentResponse', () => {
        test('should add agent response to conversation history', () => {
            activateConversation();
            const userMessage = 'Hello Atom';
            const agentResponse = { text: 'Hello user!' };
            recordUserInteraction(userMessage); // User speaks
            recordAgentResponse(userMessage, agentResponse); // Agent responds
            const history = getConversationHistory();
            expect(history.length).toBe(1);
            expect(history[0].user).toBe(userMessage);
            expect(history[0].agent.text).toBe('Hello user!');
            expect(history[0].timestamp).toBeDefined();
        });
        test('should limit conversation history size', () => {
            activateConversation();
            for (let i = 0; i < 25; i++) {
                recordAgentResponse(`User message ${i}`, {
                    text: `Agent response ${i}`,
                });
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
            recordUserInteraction('still here'); // Interaction resets timer
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29udmVyc2F0aW9uU3RhdGUudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNvbnZlcnNhdGlvblN0YXRlLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLG9CQUFvQixFQUNwQixzQkFBc0IsRUFDdEIscUJBQXFCLEVBQ3JCLG1CQUFtQixFQUNuQixvQkFBb0IsRUFDcEIsNEJBQTRCLEVBQzVCLGtCQUFrQixFQUNsQix3QkFBd0IsRUFDeEIsc0JBQXNCLEVBQ3RCLDJCQUEyQixFQUFFLDZDQUE2QztFQUMzRSxNQUFNLHFCQUFxQixDQUFDLENBQUMsMkJBQTJCO0FBR3pELE1BQU0sZUFBZSxHQUFHLEVBQUUsR0FBRyxJQUFJLENBQUMsQ0FBQywrQ0FBK0M7QUFFbEYsUUFBUSxDQUFDLDRCQUE0QixFQUFFLEdBQUcsRUFBRTtJQUMxQyxVQUFVLENBQUMsR0FBRyxFQUFFO1FBQ2Qsb0ZBQW9GO1FBQ3BGLDRDQUE0QztRQUM1QyxrRkFBa0Y7UUFDbEYsc0JBQXNCLENBQUMsa0JBQWtCLENBQUMsQ0FBQztRQUMzQyxJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7SUFDdkIsQ0FBQyxDQUFDLENBQUM7SUFFSCxTQUFTLENBQUMsR0FBRyxFQUFFO1FBQ2IsSUFBSSxDQUFDLGNBQWMsRUFBRSxDQUFDO1FBQ3RCLElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQyxDQUFDLHNCQUFzQjtJQUM5QyxDQUFDLENBQUMsQ0FBQztJQUVILElBQUksQ0FBQyxlQUFlLEVBQUUsR0FBRyxFQUFFO1FBQ3pCLE1BQU0sS0FBSyxHQUFHLDRCQUE0QixFQUFFLENBQUM7UUFDN0MsTUFBTSxDQUFDLEtBQUssQ0FBQyxRQUFRLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDbkMsTUFBTSxDQUFDLEtBQUssQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQztRQUM1QyxNQUFNLENBQUMsS0FB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MkNBQTJDLEVBQUUsR0FBRyxFQUFFO1lBQ3JELDJCQUEyQixDQUFDLElBQUksQ0FBQyxDQUFDO1lBQ2xDLE1BQU0sQ0FBQyxvQkFBb0IsRUFBRSxDQUFDLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQyxDQUFDO1lBQzFDLE1BQU0sQ0FBQyx3QkFBd0IsRUFBRSxDQUFDLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDO1lBQy9DLE1BQU0sQ0FBQyxJQUFJLENBQUMsYUFBYSxFQUFFLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFDdkMsQ0FBQyxDQUFDLENBQUM7UUFFSCxJQUFJLENBQUMsNkNBQTZDLEVBQUUsR0FBRyxFQUFFO1lBQ3ZELG9CQUFvQixFQUFFLENBQUMsQ0FBQywyQkFBMkI7WUFDbkQsMkJBQTJCLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDbkMsTUFBTSxDQUFDLG9CQUFvQixFQUFFLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDM0MsTUFBTSxDQUFDLHdCQUF3QixFQUFFLENBQUMsQ0FBQyxJQUFJLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDL0MsTUFBTSxDQUFDLElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQyxDQUFDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUN2QyxDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBhY3RpdmF0ZUNvbnZlcnNhdGlvbixcbiAgZGVhY3RpdmF0ZUNvbnZlcnNhdGlvbixcbiAgcmVjb3JkVXNlckludGVyYWN0aW9uLFxuICByZWNvcmRBZ2VudFJlc3BvbnNlLFxuICBpc0NvbnZlcnNhdGlvbkFjdGl2ZSxcbiAgZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCxcbiAgc2V0QWdlbnRSZXNwb25kaW5nLFxuICBjaGVja0lmQWdlbnRJc1Jlc3BvbmRpbmcsXG4gIGdldENvbnZlcnNhdGlvbkhpc3RvcnksXG4gIF90ZXN0X3NldENvbnZlcnNhdGlvbkFjdGl2ZSwgLy8gSWYgdGVzdGluZyB0aGlzIGludGVybmFsIGhlbHBlciBpcyBkZXNpcmVkXG59IGZyb20gJy4vY29udmVyc2F0aW9uU3RhdGUnOyAvLyBBZGp1c3QgcGF0aCBhcyBuZWNlc3NhcnlcbmltcG9ydCB7IEhhbmRsZU1lc3NhZ2VSZXNwb25zZSB9IGZyb20gJy4vaGFuZGxlcic7IC8vIEFzc3VtaW5nIHRoaXMgdHlwZSBpcyBuZWVkZWQgZm9yIGhpc3RvcnlcblxuY29uc3QgSURMRV9USU1FT1VUX01TID0gMzAgKiAxMDAwOyAvLyBNdXN0IG1hdGNoIHRoZSB2YWx1ZSBpbiBjb252ZXJzYXRpb25TdGF0ZS50c1xuXG5kZXNjcmliZSgnQ29udmVyc2F0aW9uIFN0YXRlIE1hbmFnZXInLCAoKSA9PiB7XG4gIGJlZm9yZUVhY2goKCkgPT4ge1xuICAgIC8vIFJlc2V0IHN0YXRlIGJlZm9yZSBlYWNoIHRlc3QgYnkgZGVhY3RpdmF0aW5nICh3aGljaCBhbHNvIHJlc2V0cyB0aW1lcnMgYW5kIGZsYWdzKVxuICAgIC8vIFRoaXMgZW5zdXJlcyBhIGNsZWFuIHNsYXRlIGZvciBlYWNoIHRlc3QuXG4gICAgLy8gRGlyZWN0bHkgbWFuaXB1bGF0aW5nIGdsb2JhbENvbnZlcnNhdGlvblN0YXRlIGlzIGFuIGFsdGVybmF0aXZlIGJ1dCBsZXNzIGNsZWFuLlxuICAgIGRlYWN0aXZhdGVDb252ZXJzYXRpb24oJ3Rlc3Rfc2V0dXBfcmVzZXQnKTtcbiAgICBqZXN0LnVzZUZha2VUaW1lcnMoKTtcbiAgfSk7XG5cbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsVGltZXJzKCk7XG4gICAgamVzdC51c2VSZWFsVGltZXJzKCk7IC8vIFJlc3RvcmUgcmVhbCB0aW1lcnNcbiAgfSk7XG5cbiAgdGVzdCgnaW5pdGlhbCBzdGF0ZScsICgpID0+IHtcbiAgICBjb25zdCBzdGF0ZSA9IGdldENvbnZlcnNhdGlvblN0YXRlU25hcHNob3QoKTtcbiAgICBleHBlY3Qoc3RhdGUuaXNBY3RpdmUpLnRvQmUoZmFsc2UpO1xuICAgIGV4cGVjdChzdGF0ZS5pc0FnZW50UmVzcG9uZGluZykudG9CZShmYWxzZSk7XG4gICAgZXhwZWN0KHN0YXRlLmxhc3RJbnRlcmFjdGlvblRpbWUpLnRvQmVOdWxsKCk7XG4gICAgZXhwZWN0KHN0YXRlLmNvbnZlcnNhdGlvbkhpc3RvcnkpLnRvRXF1YWwoW10pO1xuICAgIGV4cGVjdChzdGF0ZS5pZGxlVGltZXIpLnRvQmVOdWxsKCk7IC8vIEFzc3VtaW5nIHRpbWVyIGlzIG51bGwgaW5pdGlhbGx5XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdhY3RpdmF0ZUNvbnZlcnNhdGlvbicsICgpID0+IHtcbiAgICB0ZXN0KCdzaG91bGQgYWN0aXZhdGUgY29udmVyc2F0aW9uIGFuZCBzdGFydCBpZGxlIHRpbWVyJywgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYWN0aXZhdGVDb252ZXJzYXRpb24oKTtcbiAgICAgIGNvbnN0IHN0YXRlID0gZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCgpO1xuXG4gICAgICBleHBlY3QocmVzdWx0LmFjdGl2ZSkudG9CZSh0cnVlKTtcbiAgICAgIGV4cGVjdChzdGF0ZS5pc0FjdGl2ZSkudG9CZSh0cnVlKTtcbiAgICAgIGV4cGVjdChzdGF0ZS5pc0FnZW50UmVzcG9uZGluZykudG9CZShmYWxzZSk7IC8vIEV4cGxpY2l0bHkgc2V0IHRvIGZhbHNlIG9uIGFjdGl2YXRpb25cbiAgICAgIGV4cGVjdChzdGF0ZS5sYXN0SW50ZXJhY3Rpb25UaW1lKS50b0JlR3JlYXRlclRoYW4oMCk7XG4gICAgICBleHBlY3Qoc3RhdGUuaWRsZVRpbWVyKS5ub3QudG9CZU51bGwoKTtcblxuICAgICAgLy8gQ2hlY2sgaWYgdGltZXIgaXMgc2V0IGZvciB0aGUgY29ycmVjdCBkdXJhdGlvblxuICAgICAgY29uc3QgdGltZXJEZXRhaWxzID0gamVzdFxuICAgICAgICAuZ2V0VGltZXJTeXN0ZW0oKVxuICAgICAgICAuZmluZFRpbWVyKCh0KSA9PiB0LmlkID09PSBzdGF0ZS5pZGxlVGltZXIpO1xuICAgICAgaWYgKHRpbWVyRGV0YWlscykge1xuICAgICAgICAvLyBUaW1lciBJRCBtaWdodCBub3QgYmUgZGlyZWN0bHkgY29tcGFyYWJsZSBpZiBpdCdzIGFuIG9iamVjdFxuICAgICAgICAvLyBUaGlzIGNoZWNrIGlzIGEgYml0IGZyYWdpbGUgYXMgaXQgZGVwZW5kcyBvbiBKZXN0J3MgaW50ZXJuYWwgdGltZXIgcmVwcmVzZW50YXRpb25cbiAgICAgICAgLy8gQSBtb3JlIHJvYnVzdCB3YXkgaXMgdG8gY2hlY2sgaWYgZGVhY3RpdmF0ZSBpcyBjYWxsZWQgYWZ0ZXIgdGltZW91dC5cbiAgICAgIH1cbiAgICAgIGV4cGVjdChqZXN0LmdldFRpbWVyQ291bnQoKSkudG9CZSgxKTtcbiAgICB9KTtcblxuICAgIHRlc3QoJ2FjdGl2YXRpbmcgYW4gYWxyZWFkeSBhY3RpdmUgY29udmVyc2F0aW9uIHNob3VsZCByZXNldCB0aW1lciBhbmQgaW50ZXJhY3Rpb24gdGltZScsICgpID0+IHtcbiAgICAgIGFjdGl2YXRlQ29udmVyc2F0aW9uKCk7IC8vIEZpcnN0IGFjdGl2YXRpb25cbiAgICAgIGNvbnN0IGluaXRpYWxUaW1lID0gZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCgpLmxhc3RJbnRlcmFjdGlvblRpbWU7XG4gICAgICBqZXN0LmFkdmFuY2VUaW1lcnNCeVRpbWUoMTAwMCk7IC8vIEFkdmFuY2UgdGltZSBhIGJpdFxuXG4gICAgICBhY3RpdmF0ZUNvbnZlcnNhdGlvbigpOyAvLyBTZWNvbmQgYWN0aXZhdGlvblxuICAgICAgY29uc3Qgc3RhdGUgPSBnZXRDb252ZXJzYXRpb25TdGF0ZVNuYXBzaG90KCk7XG4gICAgICBleHBlY3Qoc3RhdGUuaXNBY3RpdmUpLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3Qoc3RhdGUuaXNBZ2VudFJlc3BvbmRpbmcpLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHN0YXRlLmxhc3RJbnRlcmFjdGlvblRpbWUpLnRvQmVHcmVhdGVyVGhhbihpbml0aWFsVGltZSEpO1xuICAgICAgZXhwZWN0KGplc3QuZ2V0VGltZXJDb3VudCgpKS50b0JlKDEpOyAvLyBTaG91bGQgaGF2ZSBjbGVhcmVkIHRoZSBvbGQgdGltZXIgYW5kIHN0YXJ0ZWQgYSBuZXcgb25lXG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdkZWFjdGl2YXRlQ29udmVyc2F0aW9uJywgKCkgPT4ge1xuICAgIHRlc3QoJ3Nob3VsZCBkZWFjdGl2YXRlIGNvbnZlcnNhdGlvbiBhbmQgY2xlYXIgaWRsZSB0aW1lcicsICgpID0+IHtcbiAgICAgIGFjdGl2YXRlQ29udmVyc2F0aW9uKCk7XG4gICAgICBleHBlY3QoZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCgpLmlzQWN0aXZlKS50b0JlKHRydWUpO1xuICAgICAgZXhwZWN0KGplc3QuZ2V0VGltZXJDb3VudCgpKS50b0JlKDEpO1xuXG4gICAgICBkZWFjdGl2YXRlQ29udmVyc2F0aW9uKCd0ZXN0X2RlYWN0aXZhdGlvbicpO1xuICAgICAgY29uc3Qgc3RhdGUgPSBnZXRDb252ZXJzYXRpb25TdGF0ZVNuYXBzaG90KCk7XG4gICAgICBleHBlY3Qoc3RhdGUuaXNBY3RpdmUpLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHN0YXRlLmlzQWdlbnRSZXNwb25kaW5nKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChzdGF0ZS5sYXN0SW50ZXJhY3Rpb25UaW1lKS50b0JlTnVsbCgpOyAvLyBSZXNldCBieSBkZWFjdGl2YXRlXG4gICAgICBleHBlY3QoamVzdC5nZXRUaW1lckNvdW50KCkpLnRvQmUoMCk7IC8vIFRpbWVyIGNsZWFyZWRcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ3JlY29yZFVzZXJJbnRlcmFjdGlvbicsICgpID0+IHtcbiAgICB0ZXN0KCdzaG91bGQgdXBkYXRlIGxhc3RJbnRlcmFjdGlvblRpbWUgYW5kIHJlc2V0IGlkbGUgdGltZXIgaWYgYWN0aXZlJywgKCkgPT4ge1xuICAgICAgYWN0aXZhdGVDb252ZXJzYXRpb24oKTtcbiAgICAgIGNvbnN0IGluaXRpYWxUaW1lID0gZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCgpLmxhc3RJbnRlcmFjdGlvblRpbWU7XG4gICAgICBqZXN0LmFkdmFuY2VUaW1lcnNCeVRpbWUoSURMRV9USU1FT1VUX01TIC8gMik7IC8vIEFkdmFuY2UgdGltZXIgcGFydCB3YXlcblxuICAgICAgcmVjb3JkVXNlckludGVyYWN0aW9uKCdoZWxsbycpO1xuICAgICAgY29uc3Qgc3RhdGUgPSBnZXRDb252ZXJzYXRpb25TdGF0ZVNuYXBzaG90KCk7XG4gICAgICBleHBlY3Qoc3RhdGUubGFzdEludGVyYWN0aW9uVGltZSkudG9CZUdyZWF0ZXJUaGFuKGluaXRpYWxUaW1lISk7XG4gICAgICBleHBlY3QoamVzdC5nZXRUaW1lckNvdW50KCkpLnRvQmUoMSk7IC8vIFRpbWVyIHJlc2V0XG5cbiAgICAgIC8vIEZhc3QtZm9yd2FyZCB0byBlbnN1cmUgdGhlICpuZXcqIHRpbWVyIHdvdWxkIGZpcmUgaWYgbm90IHJlc2V0IGFnYWluXG4gICAgICBqZXN0LmFkdmFuY2VUaW1lcnNCeVRpbWUoSURMRV9USU1FT1VUX01TICsgMTAwKTtcbiAgICAgIGV4cGVjdChnZXRDb252ZXJzYXRpb25TdGF0ZVNuYXBzaG90KCkuaXNBY3RpdmUpLnRvQmUoZmFsc2UpOyAvLyBTaG91bGQgaGF2ZSB0aW1lZCBvdXQgYnkgbm93XG4gICAgfSk7XG5cbiAgICB0ZXN0KCdzaG91bGQgbm90IHVwZGF0ZSBpbnRlcmFjdGlvbiB0aW1lIG9yIHRpbWVyIGlmIGNvbnZlcnNhdGlvbiBpcyBpbmFjdGl2ZScsICgpID0+IHtcbiAgICAgIGNvbnN0IGluaXRpYWxUaW1lID0gZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCgpLmxhc3RJbnRlcmFjdGlvblRpbWU7IC8vIFNob3VsZCBiZSBudWxsXG4gICAgICByZWNvcmRVc2VySW50ZXJhY3Rpb24oJ2hlbGxvJyk7XG4gICAgICBjb25zdCBzdGF0ZSA9IGdldENvbnZlcnNhdGlvblN0YXRlU25hcHNob3QoKTtcbiAgICAgIGV4cGVjdChzdGF0ZS5sYXN0SW50ZXJhY3Rpb25UaW1lKS50b0JlKGluaXRpYWxUaW1lKTsgLy8gUmVtYWlucyBudWxsXG4gICAgICBleHBlY3QoamVzdC5nZXRUaW1lckNvdW50KCkpLnRvQmUoMCk7IC8vIE5vIHRpbWVyIHN0YXJ0ZWRcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ3JlY29yZEFnZW50UmVzcG9uc2UnLCAoKSA9PiB7XG4gICAgdGVzdCgnc2hvdWxkIGFkZCBhZ2VudCByZXNwb25zZSB0byBjb252ZXJzYXRpb24gaGlzdG9yeScsICgpID0+IHtcbiAgICAgIGFjdGl2YXRlQ29udmVyc2F0aW9uKCk7XG4gICAgICBjb25zdCB1c2VyTWVzc2FnZSA9ICdIZWxsbyBBdG9tJztcbiAgICAgIGNvbnN0IGFnZW50UmVzcG9uc2U6IEhhbmRsZU1lc3NhZ2VSZXNwb25zZSA9IHsgdGV4dDogJ0hlbGxvIHVzZXIhJyB9O1xuICAgICAgcmVjb3JkVXNlckludGVyYWN0aW9uKHVzZXJNZXNzYWdlKTsgLy8gVXNlciBzcGVha3NcbiAgICAgIHJlY29yZEFnZW50UmVzcG9uc2UodXNlck1lc3NhZ2UsIGFnZW50UmVzcG9uc2UpOyAvLyBBZ2VudCByZXNwb25kc1xuXG4gICAgICBjb25zdCBoaXN0b3J5ID0gZ2V0Q29udmVyc2F0aW9uSGlzdG9yeSgpO1xuICAgICAgZXhwZWN0KGhpc3RvcnkubGVuZ3RoKS50b0JlKDEpO1xuICAgICAgZXhwZWN0KGhpc3RvcnlbMF0udXNlcikudG9CZSh1c2VyTWVzc2FnZSk7XG4gICAgICBleHBlY3QoaGlzdG9yeVswXS5hZ2VudC50ZXh0KS50b0JlKCdIZWxsbyB1c2VyIScpO1xuICAgICAgZXhwZWN0KGhpc3RvcnlbMF0udGltZXN0YW1wKS50b0JlRGVmaW5lZCgpO1xuICAgIH0pO1xuXG4gICAgdGVzdCgnc2hvdWxkIGxpbWl0IGNvbnZlcnNhdGlvbiBoaXN0b3J5IHNpemUnLCAoKSA9PiB7XG4gICAgICBhY3RpdmF0ZUNvbnZlcnNhdGlvbigpO1xuICAgICAgZm9yIChsZXQgaSA9IDA7IGkgPCAyNTsgaSsrKSB7XG4gICAgICAgIHJlY29yZEFnZW50UmVzcG9uc2UoYFVzZXIgbWVzc2FnZSAke2l9YCwge1xuICAgICAgICAgIHRleHQ6IGBBZ2VudCByZXNwb25zZSAke2l9YCxcbiAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICBjb25zdCBoaXN0b3J5ID0gZ2V0Q29udmVyc2F0aW9uSGlzdG9yeSgpO1xuICAgICAgZXhwZWN0KGhpc3RvcnkubGVuZ3RoKS50b0JlKDIwKTsgLy8gQXNzdW1pbmcgbGltaXQgaXMgMjAgYXMgaW4gaW1wbGVtZW50YXRpb25cbiAgICAgIGV4cGVjdChoaXN0b3J5WzBdLmFnZW50LnRleHQpLnRvQmUoJ0FnZW50IHJlc3BvbnNlIDUnKTsgLy8gQ2hlY2sgZmlyc3QgZWxlbWVudCBhZnRlciBzaGlmdFxuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnSWRsZSBUaW1lb3V0IExvZ2ljJywgKCkgPT4ge1xuICAgIHRlc3QoJ3Nob3VsZCBkZWFjdGl2YXRlIGNvbnZlcnNhdGlvbiBhZnRlciBpZGxlIHRpbWVvdXQnLCAoKSA9PiB7XG4gICAgICBhY3RpdmF0ZUNvbnZlcnNhdGlvbigpO1xuICAgICAgZXhwZWN0KGdldENvbnZlcnNhdGlvblN0YXRlU25hcHNob3QoKS5pc0FjdGl2ZSkudG9CZSh0cnVlKTtcblxuICAgICAgamVzdC5hZHZhbmNlVGltZXJzQnlUaW1lKElETEVfVElNRU9VVF9NUyArIDEwMCk7IC8vIEFkdmFuY2UgcGFzdCB0aW1lb3V0XG5cbiAgICAgIGNvbnN0IHN0YXRlID0gZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCgpO1xuICAgICAgZXhwZWN0KHN0YXRlLmlzQWN0aXZlKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChzdGF0ZS5pc0FnZW50UmVzcG9uZGluZykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QoamVzdC5nZXRUaW1lckNvdW50KCkpLnRvQmUoMCk7XG4gICAgfSk7XG5cbiAgICB0ZXN0KCdpbnRlcmFjdGlvbiBiZWZvcmUgdGltZW91dCBzaG91bGQgcmVzZXQgdGhlIHRpbWVyJywgKCkgPT4ge1xuICAgICAgYWN0aXZhdGVDb252ZXJzYXRpb24oKTtcbiAgICAgIGplc3QuYWR2YW5jZVRpbWVyc0J5VGltZShJRExFX1RJTUVPVVRfTVMgLyAyKTsgLy8gQWxtb3N0IHRpbWVvdXRcblxuICAgICAgcmVjb3JkVXNlckludGVyYWN0aW9uKCdzdGlsbCBoZXJlJyk7IC8vIEludGVyYWN0aW9uIHJlc2V0cyB0aW1lclxuICAgICAgZXhwZWN0KGdldENvbnZlcnNhdGlvblN0YXRlU25hcHNob3QoKS5pc0FjdGl2ZSkudG9CZSh0cnVlKTtcblxuICAgICAgamVzdC5hZHZhbmNlVGltZXJzQnlUaW1lKElETEVfVElNRU9VVF9NUyAvIDIpOyAvLyBBZHZhbmNlIGFnYWluLCBidXQgbm90IGVub3VnaCBmb3IgbmV3IHRpbWVvdXRcbiAgICAgIGV4cGVjdChnZXRDb252ZXJzYXRpb25TdGF0ZVNuYXBzaG90KCkuaXNBY3RpdmUpLnRvQmUodHJ1ZSk7XG5cbiAgICAgIGplc3QuYWR2YW5jZVRpbWVyc0J5VGltZShJRExFX1RJTUVPVVRfTVMgLyAyICsgMTAwKTsgLy8gTm93IGl0IHNob3VsZCB0aW1lb3V0XG4gICAgICBleHBlY3QoZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCgpLmlzQWN0aXZlKS50b0JlKGZhbHNlKTtcbiAgICB9KTtcblxuICAgIHRlc3QoJ2lkbGUgdGltZXIgc2hvdWxkIG5vdCBkZWFjdGl2YXRlIGlmIGFnZW50IGlzIHJlc3BvbmRpbmcnLCAoKSA9PiB7XG4gICAgICBhY3RpdmF0ZUNvbnZlcnNhdGlvbigpO1xuICAgICAgc2V0QWdlbnRSZXNwb25kaW5nKHRydWUpOyAvLyBBZ2VudCBzdGFydHMgaXRzIHR1cm5cblxuICAgICAgLy8gQWR2YW5jZSB0aW1lIHBhc3QgdGhlIG5vcm1hbCBpZGxlIHRpbWVvdXRcbiAgICAgIGplc3QuYWR2YW5jZVRpbWVyc0J5VGltZShJRExFX1RJTUVPVVRfTVMgKyAxMDApO1xuXG4gICAgICAvLyBDb252ZXJzYXRpb24gc2hvdWxkIHN0aWxsIGJlIGFjdGl2ZSBiZWNhdXNlIGFnZW50IGlzIHJlc3BvbmRpbmdcbiAgICAgIGV4cGVjdChpc0NvbnZlcnNhdGlvbkFjdGl2ZSgpKS50b0JlKHRydWUpO1xuICAgICAgZXhwZWN0KGNoZWNrSWZBZ2VudElzUmVzcG9uZGluZygpKS50b0JlKHRydWUpO1xuXG4gICAgICBzZXRBZ2VudFJlc3BvbmRpbmcoZmFsc2UpOyAvLyBBZ2VudCBmaW5pc2hlcyByZXNwb25kaW5nXG4gICAgICAvLyBOb3cgdGhlIGlkbGUgdGltZXIgc2hvdWxkIGVmZmVjdGl2ZWx5IHN0YXJ0IG9yIHJlc3RhcnRcbiAgICAgIGV4cGVjdChqZXN0LmdldFRpbWVyQ291bnQoKSkudG9CZSgxKTsgLy8gQSBuZXcgdGltZXIgc2hvdWxkIGhhdmUgYmVlbiBzdGFydGVkIGJ5IHNldEFnZW50UmVzcG9uZGluZyhmYWxzZSlcblxuICAgICAgamVzdC5hZHZhbmNlVGltZXJzQnlUaW1lKElETEVfVElNRU9VVF9NUyArIDEwMCk7XG4gICAgICBleHBlY3QoaXNDb252ZXJzYXRpb25BY3RpdmUoKSkudG9CZShmYWxzZSk7IC8vIFNob3VsZCBub3cgdGltZW91dFxuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnc2V0QWdlbnRSZXNwb25kaW5nIGFuZCBjaGVja0lmQWdlbnRJc1Jlc3BvbmRpbmcnLCAoKSA9PiB7XG4gICAgdGVzdCgnc2hvdWxkIHNldCBhbmQgZ2V0IGlzQWdlbnRSZXNwb25kaW5nIHN0YXRlJywgKCkgPT4ge1xuICAgICAgZXhwZWN0KGNoZWNrSWZBZ2VudElzUmVzcG9uZGluZygpKS50b0JlKGZhbHNlKTtcbiAgICAgIHNldEFnZW50UmVzcG9uZGluZyh0cnVlKTtcbiAgICAgIGV4cGVjdChjaGVja0lmQWdlbnRJc1Jlc3BvbmRpbmcoKSkudG9CZSh0cnVlKTtcbiAgICAgIHNldEFnZW50UmVzcG9uZGluZyhmYWxzZSk7XG4gICAgICBleHBlY3QoY2hlY2tJZkFnZW50SXNSZXNwb25kaW5nKCkpLnRvQmUoZmFsc2UpO1xuICAgIH0pO1xuXG4gICAgdGVzdCgnc2V0dGluZyBhZ2VudCByZXNwb25kaW5nIHRvIHRydWUgc2hvdWxkIGNsZWFyIGlkbGUgdGltZXIgaWYgYWN0aXZlJywgKCkgPT4ge1xuICAgICAgYWN0aXZhdGVDb252ZXJzYXRpb24oKTsgLy8gU3RhcnRzIGFuIGlkbGUgdGltZXJcbiAgICAgIGV4cGVjdChqZXN0LmdldFRpbWVyQ291bnQoKSkudG9CZSgxKTtcblxuICAgICAgLy8gQXMgcGVyIGN1cnJlbnQgaW1wbGVtZW50YXRpb24gb2Ygc2V0QWdlbnRSZXNwb25kaW5nIC0+IHN0YXJ0SWRsZVRpbWVyLFxuICAgICAgLy8gaWYgYWdlbnQgaXMgcmVzcG9uZGluZywgdGltZXIgaXMgTk9UIHN0YXJ0ZWQuXG4gICAgICAvLyBJZiBhZ2VudCBzdG9wcyByZXNwb25kaW5nIEFORCBjb252ZXJzYXRpb24gaXMgYWN0aXZlLCB0aW1lciBJUyBzdGFydGVkLlxuICAgICAgc2V0QWdlbnRSZXNwb25kaW5nKHRydWUpO1xuICAgICAgLy8gVGhlIGxvZyBpbiBzdGFydElkbGVUaW1lciBzYXlzIFwiSWRsZSB0aW1lciBub3Qgc3RhcnRlZCBiZWNhdXNlIGFnZW50IGlzIGN1cnJlbnRseSByZXNwb25kaW5nLlwiXG4gICAgICAvLyBUaGlzIG1lYW5zIGFueSBleGlzdGluZyB1c2VyIGlkbGUgdGltZXIgc2hvdWxkIGJlIGNsZWFyZWQgb3IgZWZmZWN0aXZlbHkgcGF1c2VkLlxuICAgICAgLy8gVGhlIGN1cnJlbnQgYHN0YXJ0SWRsZVRpbWVyYCBjbGVhcnMgZXhpc3RpbmcgdGltZXJzLiBJZiBgIWlzQWdlbnRSZXNwb25kaW5nYCBpcyBmYWxzZSwgaXQgd29uJ3Qgc3RhcnQgYSBuZXcgb25lLlxuICAgICAgLy8gU28sIGlmIGBzZXRBZ2VudFJlc3BvbmRpbmcodHJ1ZSlgIGlzIGNhbGxlZCwgYW5kIGl0IGNhbGxzIGBzdGFydElkbGVUaW1lcmAsIHRoZSBvbGQgdGltZXIgaXMgY2xlYXJlZCxcbiAgICAgIC8vIGFuZCBubyBuZXcgb25lIGlzIHNldC5cbiAgICAgIGV4cGVjdChqZXN0LmdldFRpbWVyQ291bnQoKSkudG9CZSgwKTtcbiAgICB9KTtcblxuICAgIHRlc3QoJ3NldHRpbmcgYWdlbnQgcmVzcG9uZGluZyB0byBmYWxzZSBzaG91bGQgc3RhcnQgaWRsZSB0aW1lciBpZiBjb252ZXJzYXRpb24gaXMgYWN0aXZlJywgKCkgPT4ge1xuICAgICAgYWN0aXZhdGVDb252ZXJzYXRpb24oKTtcbiAgICAgIHNldEFnZW50UmVzcG9uZGluZyh0cnVlKTsgLy8gVGltZXIgY291bnQgYmVjb21lcyAwXG4gICAgICBleHBlY3QoamVzdC5nZXRUaW1lckNvdW50KCkpLnRvQmUoMCk7XG5cbiAgICAgIHNldEFnZW50UmVzcG9uZGluZyhmYWxzZSk7IC8vIFNob3VsZCBzdGFydCB0aGUgdGltZXJcbiAgICAgIGV4cGVjdChqZXN0LmdldFRpbWVyQ291bnQoKSkudG9CZSgxKTtcbiAgICAgIGV4cGVjdChpc0NvbnZlcnNhdGlvbkFjdGl2ZSgpKS50b0JlKHRydWUpOyAvLyBTdGlsbCBhY3RpdmVcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ190ZXN0X3NldENvbnZlcnNhdGlvbkFjdGl2ZSAoaW50ZXJuYWwgaGVscGVyKScsICgpID0+IHtcbiAgICB0ZXN0KCdzaG91bGQgYWN0aXZhdGUgY29udmVyc2F0aW9uIHVzaW5nIGhlbHBlcicsICgpID0+IHtcbiAgICAgIF90ZXN0X3NldENvbnZlcnNhdGlvbkFjdGl2ZSh0cnVlKTtcbiAgICAgIGV4cGVjdChpc0NvbnZlcnNhdGlvbkFjdGl2ZSgpKS50b0JlKHRydWUpO1xuICAgICAgZXhwZWN0KGNoZWNrSWZBZ2VudElzUmVzcG9uZGluZygpKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChqZXN0LmdldFRpbWVyQ291bnQoKSkudG9CZSgxKTtcbiAgICB9KTtcblxuICAgIHRlc3QoJ3Nob3VsZCBkZWFjdGl2YXRlIGNvbnZlcnNhdGlvbiB1c2luZyBoZWxwZXInLCAoKSA9PiB7XG4gICAgICBhY3RpdmF0ZUNvbnZlcnNhdGlvbigpOyAvLyBFbnN1cmUgaXQncyBhY3RpdmUgZmlyc3RcbiAgICAgIF90ZXN0X3NldENvbnZlcnNhdGlvbkFjdGl2ZShmYWxzZSk7XG4gICAgICBleHBlY3QoaXNDb252ZXJzYXRpb25BY3RpdmUoKSkudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QoY2hlY2tJZkFnZW50SXNSZXNwb25kaW5nKCkpLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KGplc3QuZ2V0VGltZXJDb3VudCgpKS50b0JlKDApO1xuICAgIH0pO1xuICB9KTtcbn0pO1xuIl19