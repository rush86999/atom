// @ts-nocheck
/**
 * Tests for Agenda scheduling within atom-agent/handler.ts (_internalHandleMessage)
 */
import { _internalHandleMessage } from '../atom-agent/handler';
import { agenda } from '../agendaService'; // Actual agenda instance
import * as conversationManager from '../atom-agent/conversationState';
// Mock agenda methods
jest.mock('../agendaService', () => ({
    agenda: {
        schedule: jest
            .fn()
            .mockResolvedValue({ attrs: { _id: 'mockJobIdScheduled' } }),
        every: jest
            .fn()
            .mockResolvedValue({ attrs: { _id: 'mockJobIdRecurring' } }),
        // We might need to mock start/stop if they are called during test setup/teardown
        // For now, focusing on schedule/every.
        start: jest.fn().mockResolvedValue(undefined),
        stop: jest.fn().mockResolvedValue(undefined),
        define: jest.fn(), // Define is called in agendaService.startAgenda
    },
    // Export other things from agendaService if needed by handler.ts, or adjust mock.
    // For now, assuming only `agenda` instance is directly used by SCHEDULE_TASK.
    startAgenda: jest.fn().mockResolvedValue(undefined),
    stopAgenda: jest.fn().mockResolvedValue(undefined),
    ScheduledAgentTaskData: jest.fn(), // Mock the interface if it's used as a value
}));
// Mock conversationManager if its state is read/written in ways that affect tests
jest.mock('../atom-agent/conversationState', () => ({
    activateConversation: jest.fn(),
    deactivateConversation: jest.fn(),
    recordUserInteraction: jest.fn(),
    recordAgentResponse: jest.fn(),
    getConversationStateSnapshot: jest.fn().mockReturnValue({
        // Provide a mock state if needed by the parts of _internalHandleMessage being tested
        ltmContext: null,
        conversationId: 'mockConversationIdFromState',
    }),
    updateLTMContext: jest.fn(),
    updateUserGoal: jest.fn(),
    updateIntentAndEntities: jest.fn(),
    isConversationActive: jest.fn().mockReturnValue(true), // Assume active for tests
}));
// Mock NLU service if it's indirectly called, though SCHEDULE_TASK should use direct parameters
jest.mock('../atom-agent/skills/nluService', () => ({
    understandMessage: jest
        .fn()
        .mockImplementation(async (message, _, ltmContext) => {
        // Basic mock for NLU, specific to SCHEDULE_TASK entities
        if (message.includes('schedule send email tomorrow 10am')) {
            return {
                intent: 'SCHEDULE_TASK',
                entities: {
                    when_value: 'tomorrow at 10am', // NLU would resolve this to a date/time string
                    task_intent: 'SEND_EMAIL',
                    task_entities: { to: 'test@example.com', subject: 'Hello' },
                    task_description: 'Send a test email',
                },
                user_id: 'test-user',
                original_query: message,
            };
        }
        if (message.includes('schedule recurring report every monday 9am')) {
            return {
                intent: 'SCHEDULE_TASK',
                entities: {
                    when_value: 'every monday 9am', // NLU would resolve this
                    is_recurring: true,
                    repeat_interval: 'every Monday at 9am', // Or cron: "0 9 * * 1"
                    task_intent: 'GENERATE_REPORT',
                    task_entities: { type: 'sales' },
                    task_description: 'Generate weekly sales report',
                },
                user_id: 'test-user',
                original_query: message,
            };
        }
        // Default fallback if NLU is unexpectedly hit
        return {
            intent: 'Unknown',
            entities: {},
            user_id: 'test-user',
            original_query: message,
        };
    }),
}));
// Mock LTM/STM functions if they are called and might interfere
jest.mock('../atom-agent/memoryManager', () => ({
    retrieveRelevantLTM: jest.fn().mockResolvedValue([]),
    loadLTMToSTM: jest.fn().mockResolvedValue(undefined),
    processSTMToLTM: jest.fn().mockResolvedValue(undefined),
}));
// Mock lancedb if it's initialized or used
jest.mock('../lanceDBManager', () => ({
    initializeDB: jest.fn().mockResolvedValue(null), // Mock connection object or null
}));
describe('_internalHandleMessage - SCHEDULE_TASK intent', () => {
    const userId = 'test-user-schedule';
    const interfaceType = 'text';
    beforeEach(() => {
        // Clear all mock implementations and calls before each test
        jest.clearAllMocks();
        // conversationManager.getConversationStateSnapshot.mockReturnValue({ conversationId: 'mockConvId' });
    });
    it('should schedule a one-time task using agenda.schedule', async () => {
        const message = 'schedule send email tomorrow 10am'; // This will be processed by the mocked NLU
        // NLU mock will provide these:
        const taskIntent = 'SEND_EMAIL';
        const taskEntities = { to: 'test@example.com', subject: 'Hello' };
        const taskDescription = 'Send a test email';
        const when = new Date('2024-03-15T10:00:00.000Z'); // Example resolved date/time for "tomorrow at 10am"
        // Simulate NLU resolving "tomorrow at 10am" to a specific date object for the test
        // We'll pass this directly via options for a more direct test of the scheduling logic
        const directOptions = {
            requestSource: 'TestDirect', // Not ScheduledJobExecutor to allow NLU mock to run for SCHEDULE_TASK intent extraction
            intentName: 'SCHEDULE_TASK',
            entities: {
                when_value: when, // Pass resolved Date object
                task_intent: taskIntent,
                task_entities: taskEntities,
                task_description: taskDescription,
                is_recurring: false,
            },
            conversationId: 'testConversationId123',
        };
        // To test the SCHEDULE_TASK block directly, we need _internalHandleMessage to receive these options.
        // The current _internalHandleMessage structure bypasses NLU if requestSource is ScheduledJobExecutor.
        // For this test, we want NLU to be "bypassed" by providing the intent and entities directly to the SCHEDULE_TASK case.
        // This means the `message` parameter to _internalHandleMessage is less important if we ensure SCHEDULE_TASK uses direct entities.
        // We need to ensure the mocked NLU (understandMessage) is what provides the intent and entities
        // to the switch case.
        // The `directOptions` above is how we would pass if we were the Agenda callback.
        // For testing the NLU path to SCHEDULE_TASK, we rely on understandMessage mock.
        // Let's refine the test to directly call with SCHEDULE_TASK intent and resolved entities
        // as if NLU has already processed them.
        // This means we'll call _internalHandleMessage with a message that the NLU mock can parse,
        // or we can structure the test to assume NLU parsing and focus on the skill execution part.
        // Re-mock understandMessage for this specific test case for clarity if needed, or rely on global one.
        // For this path, we are testing the *scheduling* part.
        const nluOutputForThisTest = {
            intent: 'SCHEDULE_TASK',
            entities: {
                when_value: when, // NLU has resolved this to a Date
                task_intent: taskIntent,
                task_entities: taskEntities,
                task_description: taskDescription,
                is_recurring: false,
                // conversationId can also be an entity if passed by NLU
            },
            user_id: userId,
            original_query: message,
        };
        // Temporarily override the global mock for this specific test if it helps clarity
        require('../atom-agent/skills/nluService').understandMessage.mockResolvedValueOnce(nluOutputForThisTest);
        conversationManager.getConversationStateSnapshot.mockReturnValueOnce({
            conversationId: 'testConvIdOneTime',
        });
        const response = await _internalHandleMessage(interfaceType, message, userId, { conversationId: 'testConvIdOneTime' });
        expect(agenda.schedule).toHaveBeenCalledTimes(1);
        expect(agenda.schedule).toHaveBeenCalledWith(when, 'EXECUTE_AGENT_ACTION', expect.objectContaining({
            originalUserIntent: taskIntent,
            entities: taskEntities,
            userId: userId,
            conversationId: 'testConvIdOneTime',
        }));
        expect(response.text).toContain(`Task "${taskDescription}" scheduled for ${when.toLocaleString()}`);
        expect(agenda.every).not.toHaveBeenCalled();
    });
    it('should schedule a recurring task using agenda.every', async () => {
        const message = 'schedule recurring report every monday 9am';
        const taskIntent = 'GENERATE_REPORT';
        const taskEntities = { type: 'sales' };
        const taskDescription = 'Generate weekly sales report';
        const repeatInterval = 'every Monday at 9am'; // Or a cron string "0 9 * * 1"
        const repeatTimezone = 'America/New_York'; // Example timezone
        const nluOutputForThisTest = {
            intent: 'SCHEDULE_TASK',
            entities: {
                // when_value: undefined, // For a pure recurring, 'when' might be start date or undefined
                is_recurring: true,
                repeat_interval: repeatInterval,
                repeat_timezone: repeatTimezone,
                task_intent: taskIntent,
                task_entities: taskEntities,
                task_description: taskDescription,
            },
            user_id: userId,
            original_query: message,
        };
        require('../atom-agent/skills/nluService').understandMessage.mockResolvedValueOnce(nluOutputForThisTest);
        conversationManager.getConversationStateSnapshot.mockReturnValueOnce({
            conversationId: 'testConvIdRecurring',
        });
        const response = await _internalHandleMessage(interfaceType, message, userId, { conversationId: 'testConvIdRecurring' });
        expect(agenda.every).toHaveBeenCalledTimes(1);
        expect(agenda.every).toHaveBeenCalledWith(repeatInterval, 'EXECUTE_AGENT_ACTION', expect.objectContaining({
            originalUserIntent: taskIntent,
            entities: taskEntities,
            userId: userId,
            conversationId: 'testConvIdRecurring',
        }), expect.objectContaining({
            timezone: repeatTimezone,
            // startDate might be undefined if not provided by NLU via when_value
        }));
        expect(response.text).toContain(`Recurring task "${taskDescription}" scheduled to run ${repeatInterval}`);
        expect(agenda.schedule).not.toHaveBeenCalled();
    });
    it('should return an error message if essential scheduling parameters are missing', async () => {
        const nluOutputForThisTest = {
            intent: 'SCHEDULE_TASK',
            entities: {
                // Missing when_value for one-time, and repeat_interval for recurring
                task_intent: 'SOME_ACTION',
                task_entities: { foo: 'bar' },
            },
            user_id: userId,
            original_query: 'schedule this task',
        };
        require('../atom-agent/skills/nluService').understandMessage.mockResolvedValueOnce(nluOutputForThisTest);
        const response = await _internalHandleMessage(interfaceType, 'schedule this task', userId);
        expect(response.text).toContain("Cannot schedule task: 'when' must be provided for one-time tasks, or 'repeatInterval' for recurring tasks.");
        expect(agenda.schedule).not.toHaveBeenCalled();
        expect(agenda.every).not.toHaveBeenCalled();
    });
    it('should correctly pass conversationId from options to Agenda job data', async () => {
        const when = new Date('2024-03-16T12:00:00.000Z');
        const specificConversationId = 'specificConvIdForTest';
        const nluOutputForThisTest = {
            intent: 'SCHEDULE_TASK',
            entities: {
                when_value: when,
                task_intent: 'TEST_CONV_ID',
                task_entities: { detail: 'testing conv id' },
                is_recurring: false,
            },
            user_id: userId,
            original_query: 'schedule with specific conv id',
        };
        require('../atom-agent/skills/nluService').understandMessage.mockResolvedValueOnce(nluOutputForThisTest);
        // Ensure getConversationStateSnapshot returns the specific ID if _internalHandleMessage tries to get it from there
        // However, the current implementation of SCHEDULE_TASK in handler.ts directly uses scheduleParams.conversationId,
        // which should come from the `options` passed to _internalHandleMessage if available.
        // If `options.conversationId` is undefined, then it tries to get from `conversationManager.getConversationStateSnapshot(interfaceType)?.conversationId;`
        // Let's test the path where options.conversationId is provided.
        // For this test, we simulate that `_internalHandleMessage` is called with `options` containing `conversationId`.
        // The current `_internalHandleMessage` only takes `conversationId` from its `options` parameter if `requestSource` is `ScheduledJobExecutor`.
        // The `SCHEDULE_TASK` block, however, directly uses `scheduleParams.conversationId`.
        // `scheduleParams.conversationId` is derived from `nluResponse.entities.conversationId` or `currentConversationState.conversationId`.
        // So, we need to ensure NLU entities OR conversationManager snapshot provides it.
        // Let's ensure NLU provides it for this test.
        nluOutputForThisTest.entities.conversationId = specificConversationId;
        conversationManager.getConversationStateSnapshot.mockReturnValueOnce({
            conversationId: 'someDefaultConvId',
        }); // To see which one is picked
        await _internalHandleMessage(interfaceType, 'schedule with specific conv id', userId, { conversationId: specificConversationId });
        expect(agenda.schedule).toHaveBeenCalledWith(expect.any(Date), 'EXECUTE_AGENT_ACTION', expect.objectContaining({
            conversationId: specificConversationId, // This is the key assertion
        }));
    });
});
// Note: To run these tests, you'd need Jest installed and configured.
// The paths in `jest.mock` calls might need adjustment based on your project structure.
// Also, `_internalHandleMessage` and other imported functions need to be properly exported.
// The mock for `nluService` is very basic and would need to be more robust for comprehensive testing.
// The `handler.ts` file itself has other dependencies (like LTM/STM, LanceDB) that are
// superficially mocked here; deeper testing would require more involved mocks or test doubles for those.
// The `conversationId` handling in `SCHEDULE_TASK` needs to be consistent:
// - If NLU provides it as an entity, use that.
// - Else, if `options.conversationId` (from Agenda callback) is available, use that. (This path is for EXECUTE_AGENT_ACTION)
// - Else, use `conversationManager.getConversationStateSnapshot().conversationId`.
// The current code for SCHEDULE_TASK: `conversationId: scheduleParams.conversationId,`
// where `scheduleParams` gets `conversationId` from `entities.conversationId` or `currentConversationState.conversationId`.
// The test "should correctly pass conversationId from options to Agenda job data" might be misnamed,
// as it tests `conversationId` coming from NLU entities into the `scheduleParams` for a *newly scheduled task*.
// The `options.conversationId` to `_internalHandleMessage` is more relevant when an *existing* Agenda job *executes* and calls back.
// The test `should schedule a one-time task using agenda.schedule` already covers conversationId from `getConversationStateSnapshot`
// if not provided by NLU.
// To truly test `options.conversationId` propagation for a *new* schedule, NLU would have to provide it OR
// the wrapper calling `_internalHandleMessage` for a user command would need to pass it in options.
// The current structure seems to prioritize NLU-provided `conversationId` or active conversation's ID for new schedules.
// The `conversationId` in `ScheduledAgentTaskData` is correctly populated from `scheduleParams.conversationId`.
// And when the job runs, this `conversationId` from `jobData` is passed to `_internalHandleMessage` via its `options`.
// So the chain looks correct.
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYWdlbmRhSGFuZGxlci50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYWdlbmRhSGFuZGxlci50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLGNBQWM7QUFDZDs7R0FFRztBQUNILE9BQU8sRUFBRSxzQkFBc0IsRUFBRSxNQUFNLHVCQUF1QixDQUFDO0FBQy9ELE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxrQkFBa0IsQ0FBQyxDQUFDLHlCQUF5QjtBQUNwRSxPQUFPLEtBQUssbUJBQW1CLE1BQU0saUNBQWlDLENBQUM7QUFFdkUsc0JBQXNCO0FBQ3RCLElBQUksQ0FBQyxJQUFJLENBQUMsa0JBQWtCLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQztJQUNuQyxNQUFNLEVBQUU7UUFDTixRQUFRLEVBQUUsSUFBSTthQUNYLEVBQUUsRUFBRTthQUNKLGlCQUFpQixDQUFDLEVBQUUsS0FBSyxFQUFFLEVBQUUsR0FBRyxFQUFFLG9CQUFvQixFQUFFLEVBQUUsQ0FBQztRQUM5RCxLQUFLLEVBQUUsSUFBSTthQUNSLEVBQUUsRUFBRTthQUNKLGlCQUFpQixDQUFDLEVBQUUsS0FBSyxFQUFFLEVBQUUsR0FBRyxFQUFFLG9CQUFvQixFQUFFLEVBQUUsQ0FBQztRQUM5RCxpRkFBaUY7UUFDakYsdUNBQXVDO1FBQ3ZDLEtBQUssRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUMsaUJBQWlCLENBQUMsU0FBUyxDQUFDO1FBQzdDLElBQUksRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUMsaUJBQWlCLENBQUMsU0FBUyxDQUFDO1FBQzVDLE1BQU0sRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFLEVBQUUsZ0RBQWdEO0tBQ3BFO0lBQ0Qsa0ZBQWtGO0lBQ2xGLDhFQUE4RTtJQUM5RSxXQUFXLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLGlCQUFpQixDQUFDLFNBQVMsQ0FBQztJQUNuRCxVQUFVLEVBQUUsSUFBSSxDQUFDLEVBQUUs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NEhBQTRIO0FBQzVILHFHQUFxRztBQUNyRyxnSEFBZ0g7QUFDaEgscUlBQXFJO0FBQ3JJLHFJQUFxSTtBQUNySSwwQkFBMEI7QUFDMUIsMkdBQTJHO0FBQzNHLG9HQUFvRztBQUNwRyx5SEFBeUg7QUFDekgsZ0hBQWdIO0FBQ2hILHVIQUF1SDtBQUN2SCw4QkFBOEIiLCJzb3VyY2VzQ29udGVudCI6WyIvLyBAdHMtbm9jaGVja1xuLyoqXG4gKiBUZXN0cyBmb3IgQWdlbmRhIHNjaGVkdWxpbmcgd2l0aGluIGF0b20tYWdlbnQvaGFuZGxlci50cyAoX2ludGVybmFsSGFuZGxlTWVzc2FnZSlcbiAqL1xuaW1wb3J0IHsgX2ludGVybmFsSGFuZGxlTWVzc2FnZSB9IGZyb20gJy4uL2F0b20tYWdlbnQvaGFuZGxlcic7XG5pbXBvcnQgeyBhZ2VuZGEgfSBmcm9tICcuLi9hZ2VuZGFTZXJ2aWNlJzsgLy8gQWN0dWFsIGFnZW5kYSBpbnN0YW5jZVxuaW1wb3J0ICogYXMgY29udmVyc2F0aW9uTWFuYWdlciBmcm9tICcuLi9hdG9tLWFnZW50L2NvbnZlcnNhdGlvblN0YXRlJztcblxuLy8gTW9jayBhZ2VuZGEgbWV0aG9kc1xuamVzdC5tb2NrKCcuLi9hZ2VuZGFTZXJ2aWNlJywgKCkgPT4gKHtcbiAgYWdlbmRhOiB7XG4gICAgc2NoZWR1bGU6IGplc3RcbiAgICAgIC5mbigpXG4gICAgICAubW9ja1Jlc29sdmVkVmFsdWUoeyBhdHRyczogeyBfaWQ6ICdtb2NrSm9iSWRTY2hlZHVsZWQnIH0gfSksXG4gICAgZXZlcnk6IGplc3RcbiAgICAgIC5mbigpXG4gICAgICAubW9ja1Jlc29sdmVkVmFsdWUoeyBhdHRyczogeyBfaWQ6ICdtb2NrSm9iSWRSZWN1cnJpbmcnIH0gfSksXG4gICAgLy8gV2UgbWlnaHQgbmVlZCB0byBtb2NrIHN0YXJ0L3N0b3AgaWYgdGhleSBhcmUgY2FsbGVkIGR1cmluZyB0ZXN0IHNldHVwL3RlYXJkb3duXG4gICAgLy8gRm9yIG5vdywgZm9jdXNpbmcgb24gc2NoZWR1bGUvZXZlcnkuXG4gICAgc3RhcnQ6IGplc3QuZm4oKS5tb2NrUmVzb2x2ZWRWYWx1ZSh1bmRlZmluZWQpLFxuICAgIHN0b3A6IGplc3QuZm4oKS5tb2NrUmVzb2x2ZWRWYWx1ZSh1bmRlZmluZWQpLFxuICAgIGRlZmluZTogamVzdC5mbigpLCAvLyBEZWZpbmUgaXMgY2FsbGVkIGluIGFnZW5kYVNlcnZpY2Uuc3RhcnRBZ2VuZGFcbiAgfSxcbiAgLy8gRXhwb3J0IG90aGVyIHRoaW5ncyBmcm9tIGFnZW5kYVNlcnZpY2UgaWYgbmVlZGVkIGJ5IGhhbmRsZXIudHMsIG9yIGFkanVzdCBtb2NrLlxuICAvLyBGb3Igbm93LCBhc3N1bWluZyBvbmx5IGBhZ2VuZGFgIGluc3RhbmNlIGlzIGRpcmVjdGx5IHVzZWQgYnkgU0NIRURVTEVfVEFTSy5cbiAgc3RhcnRBZ2VuZGE6IGplc3QuZm4oKS5tb2NrUmVzb2x2ZWRWYWx1ZSh1bmRlZmluZWQpLFxuICBzdG9wQWdlbmRhOiBqZXN0LmZuKCkubW9ja1Jlc29sdmVkVmFsdWUodW5kZWZpbmVkKSxcbiAgU2NoZWR1bGVkQWdlbnRUYXNrRGF0YTogamVzdC5mbigpLCAvLyBNb2NrIHRoZSBpbnRlcmZhY2UgaWYgaXQncyB1c2VkIGFzIGEgdmFsdWVcbn0pKTtcblxuLy8gTW9jayBjb252ZXJzYXRpb25NYW5hZ2VyIGlmIGl0cyBzdGF0ZSBpcyByZWFkL3dyaXR0ZW4gaW4gd2F5cyB0aGF0IGFmZmVjdCB0ZXN0c1xuamVzdC5tb2NrKCcuLi9hdG9tLWFnZW50L2NvbnZlcnNhdGlvblN0YXRlJywgKCkgPT4gKHtcbiAgYWN0aXZhdGVDb252ZXJzYXRpb246IGplc3QuZm4oKSxcbiAgZGVhY3RpdmF0ZUNvbnZlcnNhdGlvbjogamVzdC5mbigpLFxuICByZWNvcmRVc2VySW50ZXJhY3Rpb246IGplc3QuZm4oKSxcbiAgcmVjb3JkQWdlbnRSZXNwb25zZTogamVzdC5mbigpLFxuICBnZXRDb252ZXJzYXRpb25TdGF0ZVNuYXBzaG90OiBqZXN0LmZuKCkubW9ja1JldHVyblZhbHVlKHtcbiAgICAvLyBQcm92aWRlIGEgbW9jayBzdGF0ZSBpZiBuZWVkZWQgYnkgdGhlIHBhcnRzIG9mIF9pbnRlcm5hbEhhbmRsZU1lc3NhZ2UgYmVpbmcgdGVzdGVkXG4gICAgbHRtQ29udGV4dDogbnVsbCxcbiAgICBjb252ZXJzYXRpb25JZDogJ21vY2tDb252ZXJzYXRpb25JZEZyb21TdGF0ZScsXG4gIH0pLFxuICB1cGRhdGVMVE1Db250ZXh0OiBqZXN0LmZuKCksXG4gIHVwZGF0ZVVzZXJHb2FsOiBqZXN0LmZuKCksXG4gIHVwZGF0ZUludGVudEFuZEVudGl0aWVzOiBqZXN0LmZuKCksXG4gIGlzQ29udmVyc2F0aW9uQWN0aXZlOiBqZXN0LmZuKCkubW9ja1JldHVyblZhbHVlKHRydWUpLCAvLyBBc3N1bWUgYWN0aXZlIGZvciB0ZXN0c1xufSkpO1xuXG4vLyBNb2NrIE5MVSBzZXJ2aWNlIGlmIGl0J3MgaW5kaXJlY3RseSBjYWxsZWQsIHRob3VnaCBTQ0hFRFVMRV9UQVNLIHNob3VsZCB1c2UgZGlyZWN0IHBhcmFtZXRlcnNcbmplc3QubW9jaygnLi4vYXRvbS1hZ2VudC9za2lsbHMvbmx1U2VydmljZScsICgpID0+ICh7XG4gIHVuZGVyc3RhbmRNZXNzYWdlOiBqZXN0XG4gICAgLmZuKClcbiAgICAubW9ja0ltcGxlbWVudGF0aW9uKGFzeW5jIChtZXNzYWdlLCBfLCBsdG1Db250ZXh0KSA9PiB7XG4gICAgICAvLyBCYXNpYyBtb2NrIGZvciBOTFUsIHNwZWNpZmljIHRvIFNDSEVEVUxFX1RBU0sgZW50aXRpZXNcbiAgICAgIGlmIChtZXNzYWdlLmluY2x1ZGVzKCdzY2hlZHVsZSBzZW5kIGVtYWlsIHRvbW9ycm93IDEwYW0nKSkge1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIGludGVudDogJ1NDSEVEVUxFX1RBU0snLFxuICAgICAgICAgIGVudGl0aWVzOiB7XG4gICAgICAgICAgICB3aGVuX3ZhbHVlOiAndG9tb3Jyb3cgYXQgMTBhbScsIC8vIE5MVSB3b3VsZCByZXNvbHZlIHRoaXMgdG8gYSBkYXRlL3RpbWUgc3RyaW5nXG4gICAgICAgICAgICB0YXNrX2ludGVudDogJ1NFTkRfRU1BSUwnLFxuICAgICAgICAgICAgdGFza19lbnRpdGllczogeyB0bzogJ3Rlc3RAZXhhbXBsZS5jb20nLCBzdWJqZWN0OiAnSGVsbG8nIH0sXG4gICAgICAgICAgICB0YXNrX2Rlc2NyaXB0aW9uOiAnU2VuZCBhIHRlc3QgZW1haWwnLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgdXNlcl9pZDogJ3Rlc3QtdXNlcicsXG4gICAgICAgICAgb3JpZ2luYWxfcXVlcnk6IG1lc3NhZ2UsXG4gICAgICAgIH07XG4gICAgICB9XG4gICAgICBpZiAobWVzc2FnZS5pbmNsdWRlcygnc2NoZWR1bGUgcmVjdXJyaW5nIHJlcG9ydCBldmVyeSBtb25kYXkgOWFtJykpIHtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICBpbnRlbnQ6ICdTQ0hFRFVMRV9UQVNLJyxcbiAgICAgICAgICBlbnRpdGllczoge1xuICAgICAgICAgICAgd2hlbl92YWx1ZTogJ2V2ZXJ5IG1vbmRheSA5YW0nLCAvLyBOTFUgd291bGQgcmVzb2x2ZSB0aGlzXG4gICAgICAgICAgICBpc19yZWN1cnJpbmc6IHRydWUsXG4gICAgICAgICAgICByZXBlYXRfaW50ZXJ2YWw6ICdldmVyeSBNb25kYXkgYXQgOWFtJywgLy8gT3IgY3JvbjogXCIwIDkgKiAqIDFcIlxuICAgICAgICAgICAgdGFza19pbnRlbnQ6ICdHRU5FUkFURV9SRVBPUlQnLFxuICAgICAgICAgICAgdGFza19lbnRpdGllczogeyB0eXBlOiAnc2FsZXMnIH0sXG4gICAgICAgICAgICB0YXNrX2Rlc2NyaXB0aW9uOiAnR2VuZXJhdGUgd2Vla2x5IHNhbGVzIHJlcG9ydCcsXG4gICAgICAgICAgfSxcbiAgICAgICAgICB1c2VyX2lkOiAndGVzdC11c2VyJyxcbiAgICAgICAgICBvcmlnaW5hbF9xdWVyeTogbWVzc2FnZSxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICAgIC8vIERlZmF1bHQgZmFsbGJhY2sgaWYgTkxVIGlzIHVuZXhwZWN0ZWRseSBoaXRcbiAgICAgIHJldHVybiB7XG4gICAgICAgIGludGVudDogJ1Vua25vd24nLFxuICAgICAgICBlbnRpdGllczoge30sXG4gICAgICAgIHVzZXJfaWQ6ICd0ZXN0LXVzZXInLFxuICAgICAgICBvcmlnaW5hbF9xdWVyeTogbWVzc2FnZSxcbiAgICAgIH07XG4gICAgfSksXG59KSk7XG5cbi8vIE1vY2sgTFRNL1NUTSBmdW5jdGlvbnMgaWYgdGhleSBhcmUgY2FsbGVkIGFuZCBtaWdodCBpbnRlcmZlcmVcbmplc3QubW9jaygnLi4vYXRvbS1hZ2VudC9tZW1vcnlNYW5hZ2VyJywgKCkgPT4gKHtcbiAgcmV0cmlldmVSZWxldmFudExUTTogamVzdC5mbigpLm1vY2tSZXNvbHZlZFZhbHVlKFtdKSxcbiAgbG9hZExUTVRvU1RNOiBqZXN0LmZuKCkubW9ja1Jlc29sdmVkVmFsdWUodW5kZWZpbmVkKSxcbiAgcHJvY2Vzc1NUTVRvTFRNOiBqZXN0LmZuKCkubW9ja1Jlc29sdmVkVmFsdWUodW5kZWZpbmVkKSxcbn0pKTtcblxuLy8gTW9jayBsYW5jZWRiIGlmIGl0J3MgaW5pdGlhbGl6ZWQgb3IgdXNlZFxuamVzdC5tb2NrKCcuLi9sYW5jZURCTWFuYWdlcicsICgpID0+ICh7XG4gIGluaXRpYWxpemVEQjogamVzdC5mbigpLm1vY2tSZXNvbHZlZFZhbHVlKG51bGwpLCAvLyBNb2NrIGNvbm5lY3Rpb24gb2JqZWN0IG9yIG51bGxcbn0pKTtcblxuZGVzY3JpYmUoJ19pbnRlcm5hbEhhbmRsZU1lc3NhZ2UgLSBTQ0hFRFVMRV9UQVNLIGludGVudCcsICgpID0+IHtcbiAgY29uc3QgdXNlcklkID0gJ3Rlc3QtdXNlci1zY2hlZHVsZSc7XG4gIGNvbnN0IGludGVyZmFjZVR5cGUgPSAndGV4dCc7XG5cbiAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgLy8gQ2xlYXIgYWxsIG1vY2sgaW1wbGVtZW50YXRpb25zIGFuZCBjYWxscyBiZWZvcmUgZWFjaCB0ZXN0XG4gICAgamVzdC5jbGVhckFsbE1vY2tzKCk7XG4gICAgLy8gY29udmVyc2F0aW9uTWFuYWdlci5nZXRDb252ZXJzYXRpb25TdGF0ZVNuYXBzaG90Lm1vY2tSZXR1cm5WYWx1ZSh7IGNvbnZlcnNhdGlvbklkOiAnbW9ja0NvbnZJZCcgfSk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgc2NoZWR1bGUgYSBvbmUtdGltZSB0YXNrIHVzaW5nIGFnZW5kYS5zY2hlZHVsZScsIGFzeW5jICgpID0+IHtcbiAgICBjb25zdCBtZXNzYWdlID0gJ3NjaGVkdWxlIHNlbmQgZW1haWwgdG9tb3Jyb3cgMTBhbSc7IC8vIFRoaXMgd2lsbCBiZSBwcm9jZXNzZWQgYnkgdGhlIG1vY2tlZCBOTFVcblxuICAgIC8vIE5MVSBtb2NrIHdpbGwgcHJvdmlkZSB0aGVzZTpcbiAgICBjb25zdCB0YXNrSW50ZW50ID0gJ1NFTkRfRU1BSUwnO1xuICAgIGNvbnN0IHRhc2tFbnRpdGllcyA9IHsgdG86ICd0ZXN0QGV4YW1wbGUuY29tJywgc3ViamVjdDogJ0hlbGxvJyB9O1xuICAgIGNvbnN0IHRhc2tEZXNjcmlwdGlvbiA9ICdTZW5kIGEgdGVzdCBlbWFpbCc7XG4gICAgY29uc3Qgd2hlbiA9IG5ldyBEYXRlKCcyMDI0LTAzLTE1VDEwOjAwOjAwLjAwMFonKTsgLy8gRXhhbXBsZSByZXNvbHZlZCBkYXRlL3RpbWUgZm9yIFwidG9tb3Jyb3cgYXQgMTBhbVwiXG5cbiAgICAvLyBTaW11bGF0ZSBOTFUgcmVzb2x2aW5nIFwidG9tb3Jyb3cgYXQgMTBhbVwiIHRvIGEgc3BlY2lmaWMgZGF0ZSBvYmplY3QgZm9yIHRoZSB0ZXN0XG4gICAgLy8gV2UnbGwgcGFzcyB0aGlzIGRpcmVjdGx5IHZpYSBvcHRpb25zIGZvciBhIG1vcmUgZGlyZWN0IHRlc3Qgb2YgdGhlIHNjaGVkdWxpbmcgbG9naWNcbiAgICBjb25zdCBkaXJlY3RPcHRpb25zID0ge1xuICAgICAgcmVxdWVzdFNvdXJjZTogJ1Rlc3REaXJlY3QnLCAvLyBOb3QgU2NoZWR1bGVkSm9iRXhlY3V0b3IgdG8gYWxsb3cgTkxVIG1vY2sgdG8gcnVuIGZvciBTQ0hFRFVMRV9UQVNLIGludGVudCBleHRyYWN0aW9uXG4gICAgICBpbnRlbnROYW1lOiAnU0NIRURVTEVfVEFTSycsXG4gICAgICBlbnRpdGllczoge1xuICAgICAgICB3aGVuX3ZhbHVlOiB3aGVuLCAvLyBQYXNzIHJlc29sdmVkIERhdGUgb2JqZWN0XG4gICAgICAgIHRhc2tfaW50ZW50OiB0YXNrSW50ZW50LFxuICAgICAgICB0YXNrX2VudGl0aWVzOiB0YXNrRW50aXRpZXMsXG4gICAgICAgIHRhc2tfZGVzY3JpcHRpb246IHRhc2tEZXNjcmlwdGlvbixcbiAgICAgICAgaXNfcmVjdXJyaW5nOiBmYWxzZSxcbiAgICAgIH0sXG4gICAgICBjb252ZXJzYXRpb25JZDogJ3Rlc3RDb252ZXJzYXRpb25JZDEyMycsXG4gICAgfTtcblxuICAgIC8vIFRvIHRlc3QgdGhlIFNDSEVEVUxFX1RBU0sgYmxvY2sgZGlyZWN0bHksIHdlIG5lZWQgX2ludGVybmFsSGFuZGxlTWVzc2FnZSB0byByZWNlaXZlIHRoZXNlIG9wdGlvbnMuXG4gICAgLy8gVGhlIGN1cnJlbnQgX2ludGVybmFsSGFuZGxlTWVzc2FnZSBzdHJ1Y3R1cmUgYnlwYXNzZXMgTkxVIGlmIHJlcXVlc3RTb3VyY2UgaXMgU2NoZWR1bGVkSm9iRXhlY3V0b3IuXG4gICAgLy8gRm9yIHRoaXMgdGVzdCwgd2Ugd2FudCBOTFUgdG8gYmUgXCJieXBhc3NlZFwiIGJ5IHByb3ZpZGluZyB0aGUgaW50ZW50IGFuZCBlbnRpdGllcyBkaXJlY3RseSB0byB0aGUgU0NIRURVTEVfVEFTSyBjYXNlLlxuICAgIC8vIFRoaXMgbWVhbnMgdGhlIGBtZXNzYWdlYCBwYXJhbWV0ZXIgdG8gX2ludGVybmFsSGFuZGxlTWVzc2FnZSBpcyBsZXNzIGltcG9ydGFudCBpZiB3ZSBlbnN1cmUgU0NIRURVTEVfVEFTSyB1c2VzIGRpcmVjdCBlbnRpdGllcy5cblxuICAgIC8vIFdlIG5lZWQgdG8gZW5zdXJlIHRoZSBtb2NrZWQgTkxVICh1bmRlcnN0YW5kTWVzc2FnZSkgaXMgd2hhdCBwcm92aWRlcyB0aGUgaW50ZW50IGFuZCBlbnRpdGllc1xuICAgIC8vIHRvIHRoZSBzd2l0Y2ggY2FzZS5cbiAgICAvLyBUaGUgYGRpcmVjdE9wdGlvbnNgIGFib3ZlIGlzIGhvdyB3ZSB3b3VsZCBwYXNzIGlmIHdlIHdlcmUgdGhlIEFnZW5kYSBjYWxsYmFjay5cbiAgICAvLyBGb3IgdGVzdGluZyB0aGUgTkxVIHBhdGggdG8gU0NIRURVTEVfVEFTSywgd2UgcmVseSBvbiB1bmRlcnN0YW5kTWVzc2FnZSBtb2NrLlxuXG4gICAgLy8gTGV0J3MgcmVmaW5lIHRoZSB0ZXN0IHRvIGRpcmVjdGx5IGNhbGwgd2l0aCBTQ0hFRFVMRV9UQVNLIGludGVudCBhbmQgcmVzb2x2ZWQgZW50aXRpZXNcbiAgICAvLyBhcyBpZiBOTFUgaGFzIGFscmVhZHkgcHJvY2Vzc2VkIHRoZW0uXG4gICAgLy8gVGhpcyBtZWFucyB3ZSdsbCBjYWxsIF9pbnRlcm5hbEhhbmRsZU1lc3NhZ2Ugd2l0aCBhIG1lc3NhZ2UgdGhhdCB0aGUgTkxVIG1vY2sgY2FuIHBhcnNlLFxuICAgIC8vIG9yIHdlIGNhbiBzdHJ1Y3R1cmUgdGhlIHRlc3QgdG8gYXNzdW1lIE5MVSBwYXJzaW5nIGFuZCBmb2N1cyBvbiB0aGUgc2tpbGwgZXhlY3V0aW9uIHBhcnQuXG5cbiAgICAvLyBSZS1tb2NrIHVuZGVyc3RhbmRNZXNzYWdlIGZvciB0aGlzIHNwZWNpZmljIHRlc3QgY2FzZSBmb3IgY2xhcml0eSBpZiBuZWVkZWQsIG9yIHJlbHkgb24gZ2xvYmFsIG9uZS5cbiAgICAvLyBGb3IgdGhpcyBwYXRoLCB3ZSBhcmUgdGVzdGluZyB0aGUgKnNjaGVkdWxpbmcqIHBhcnQuXG4gICAgY29uc3Qgbmx1T3V0cHV0Rm9yVGhpc1Rlc3QgPSB7XG4gICAgICBpbnRlbnQ6ICdTQ0hFRFVMRV9UQVNLJyxcbiAgICAgIGVudGl0aWVzOiB7XG4gICAgICAgIHdoZW5fdmFsdWU6IHdoZW4sIC8vIE5MVSBoYXMgcmVzb2x2ZWQgdGhpcyB0byBhIERhdGVcbiAgICAgICAgdGFza19pbnRlbnQ6IHRhc2tJbnRlbnQsXG4gICAgICAgIHRhc2tfZW50aXRpZXM6IHRhc2tFbnRpdGllcyxcbiAgICAgICAgdGFza19kZXNjcmlwdGlvbjogdGFza0Rlc2NyaXB0aW9uLFxuICAgICAgICBpc19yZWN1cnJpbmc6IGZhbHNlLFxuICAgICAgICAvLyBjb252ZXJzYXRpb25JZCBjYW4gYWxzbyBiZSBhbiBlbnRpdHkgaWYgcGFzc2VkIGJ5IE5MVVxuICAgICAgfSxcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIG9yaWdpbmFsX3F1ZXJ5OiBtZXNzYWdlLFxuICAgIH07XG5cbiAgICAvLyBUZW1wb3JhcmlseSBvdmVycmlkZSB0aGUgZ2xvYmFsIG1vY2sgZm9yIHRoaXMgc3BlY2lmaWMgdGVzdCBpZiBpdCBoZWxwcyBjbGFyaXR5XG4gICAgcmVxdWlyZSgnLi4vYXRvbS1hZ2VudC9za2lsbHMvbmx1U2VydmljZScpLnVuZGVyc3RhbmRNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlT25jZShcbiAgICAgIG5sdU91dHB1dEZvclRoaXNUZXN0XG4gICAgKTtcbiAgICBjb252ZXJzYXRpb25NYW5hZ2VyLmdldENvbnZlcnNhdGlvblN0YXRlU25hcHNob3QubW9ja1JldHVyblZhbHVlT25jZSh7XG4gICAgICBjb252ZXJzYXRpb25JZDogJ3Rlc3RDb252SWRPbmVUaW1lJyxcbiAgICB9KTtcblxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgX2ludGVybmFsSGFuZGxlTWVzc2FnZShcbiAgICAgIGludGVyZmFjZVR5cGUsXG4gICAgICBtZXNzYWdlLFxuICAgICAgdXNlcklkLFxuICAgICAgeyBjb252ZXJzYXRpb25JZDogJ3Rlc3RDb252SWRPbmVUaW1lJyB9XG4gICAgKTtcblxuICAgIGV4cGVjdChhZ2VuZGEuc2NoZWR1bGUpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTtcbiAgICBleHBlY3QoYWdlbmRhLnNjaGVkdWxlKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIHdoZW4sXG4gICAgICAnRVhFQ1VURV9BR0VOVF9BQ1RJT04nLFxuICAgICAgZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xuICAgICAgICBvcmlnaW5hbFVzZXJJbnRlbnQ6IHRhc2tJbnRlbnQsXG4gICAgICAgIGVudGl0aWVzOiB0YXNrRW50aXRpZXMsXG4gICAgICAgIHVzZXJJZDogdXNlcklkLFxuICAgICAgICBjb252ZXJzYXRpb25JZDogJ3Rlc3RDb252SWRPbmVUaW1lJyxcbiAgICAgIH0pXG4gICAgKTtcbiAgICBleHBlY3QocmVzcG9uc2UudGV4dCkudG9Db250YWluKFxuICAgICAgYFRhc2sgXCIke3Rhc2tEZXNjcmlwdGlvbn1cIiBzY2hlZHVsZWQgZm9yICR7d2hlbi50b0xvY2FsZVN0cmluZygpfWBcbiAgICApO1xuICAgIGV4cGVjdChhZ2VuZGEuZXZlcnkpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgc2NoZWR1bGUgYSByZWN1cnJpbmcgdGFzayB1c2luZyBhZ2VuZGEuZXZlcnknLCBhc3luYyAoKSA9PiB7XG4gICAgY29uc3QgbWVzc2FnZSA9ICdzY2hlZHVsZSByZWN1cnJpbmcgcmVwb3J0IGV2ZXJ5IG1vbmRheSA5YW0nO1xuICAgIGNvbnN0IHRhc2tJbnRlbnQgPSAnR0VORVJBVEVfUkVQT1JUJztcbiAgICBjb25zdCB0YXNrRW50aXRpZXMgPSB7IHR5cGU6ICdzYWxlcycgfTtcbiAgICBjb25zdCB0YXNrRGVzY3JpcHRpb24gPSAnR2VuZXJhdGUgd2Vla2x5IHNhbGVzIHJlcG9ydCc7XG4gICAgY29uc3QgcmVwZWF0SW50ZXJ2YWwgPSAnZXZlcnkgTW9uZGF5IGF0IDlhbSc7IC8vIE9yIGEgY3JvbiBzdHJpbmcgXCIwIDkgKiAqIDFcIlxuICAgIGNvbnN0IHJlcGVhdFRpbWV6b25lID0gJ0FtZXJpY2EvTmV3X1lvcmsnOyAvLyBFeGFtcGxlIHRpbWV6b25lXG5cbiAgICBjb25zdCBubHVPdXRwdXRGb3JUaGlzVGVzdCA9IHtcbiAgICAgIGludGVudDogJ1NDSEVEVUxFX1RBU0snLFxuICAgICAgZW50aXRpZXM6IHtcbiAgICAgICAgLy8gd2hlbl92YWx1ZTogdW5kZWZpbmVkLCAvLyBGb3IgYSBwdXJlIHJlY3VycmluZywgJ3doZW4nIG1pZ2h0IGJlIHN0YXJ0IGRhdGUgb3IgdW5kZWZpbmVkXG4gICAgICAgIGlzX3JlY3VycmluZzogdHJ1ZSxcbiAgICAgICAgcmVwZWF0X2ludGVydmFsOiByZXBlYXRJbnRlcnZhbCxcbiAgICAgICAgcmVwZWF0X3RpbWV6b25lOiByZXBlYXRUaW1lem9uZSxcbiAgICAgICAgdGFza19pbnRlbnQ6IHRhc2tJbnRlbnQsXG4gICAgICAgIHRhc2tfZW50aXRpZXM6IHRhc2tFbnRpdGllcyxcbiAgICAgICAgdGFza19kZXNjcmlwdGlvbjogdGFza0Rlc2NyaXB0aW9uLFxuICAgICAgfSxcbiAgICAgIHVzZXJfaWQ6IHVzZXJJZCxcbiAgICAgIG9yaWdpbmFsX3F1ZXJ5OiBtZXNzYWdlLFxuICAgIH07XG4gICAgcmVxdWlyZSgnLi4vYXRvbS1hZ2VudC9za2lsbHMvbmx1U2VydmljZScpLnVuZGVyc3RhbmRNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlT25jZShcbiAgICAgIG5sdU91dHB1dEZvclRoaXNUZXN0XG4gICAgKTtcbiAgICBjb252ZXJzYXRpb25NYW5hZ2VyLmdldENvbnZlcnNhdGlvblN0YXRlU25hcHNob3QubW9ja1JldHVyblZhbHVlT25jZSh7XG4gICAgICBjb252ZXJzYXRpb25JZDogJ3Rlc3RDb252SWRSZWN1cnJpbmcnLFxuICAgIH0pO1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlKFxuICAgICAgaW50ZXJmYWNlVHlwZSxcbiAgICAgIG1lc3NhZ2UsXG4gICAgICB1c2VySWQsXG4gICAgICB7IGNvbnZlcnNhdGlvbklkOiAndGVzdENvbnZJZFJlY3VycmluZycgfVxuICAgICk7XG5cbiAgICBleHBlY3QoYWdlbmRhLmV2ZXJ5KS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgZXhwZWN0KGFnZW5kYS5ldmVyeSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICByZXBlYXRJbnRlcnZhbCxcbiAgICAgICdFWEVDVVRFX0FHRU5UX0FDVElPTicsXG4gICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XG4gICAgICAgIG9yaWdpbmFsVXNlckludGVudDogdGFza0ludGVudCxcbiAgICAgICAgZW50aXRpZXM6IHRhc2tFbnRpdGllcyxcbiAgICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgICAgIGNvbnZlcnNhdGlvbklkOiAndGVzdENvbnZJZFJlY3VycmluZycsXG4gICAgICB9KSxcbiAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcbiAgICAgICAgdGltZXpvbmU6IHJlcGVhdFRpbWV6b25lLFxuICAgICAgICAvLyBzdGFydERhdGUgbWlnaHQgYmUgdW5kZWZpbmVkIGlmIG5vdCBwcm92aWRlZCBieSBOTFUgdmlhIHdoZW5fdmFsdWVcbiAgICAgIH0pXG4gICAgKTtcbiAgICBleHBlY3QocmVzcG9uc2UudGV4dCkudG9Db250YWluKFxuICAgICAgYFJlY3VycmluZyB0YXNrIFwiJHt0YXNrRGVzY3JpcHRpb259XCIgc2NoZWR1bGVkIHRvIHJ1biAke3JlcGVhdEludGVydmFsfWBcbiAgICApO1xuICAgIGV4cGVjdChhZ2VuZGEuc2NoZWR1bGUpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2UgaWYgZXNzZW50aWFsIHNjaGVkdWxpbmcgcGFyYW1ldGVycyBhcmUgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICBjb25zdCBubHVPdXRwdXRGb3JUaGlzVGVzdCA9IHtcbiAgICAgIGludGVudDogJ1NDSEVEVUxFX1RBU0snLFxuICAgICAgZW50aXRpZXM6IHtcbiAgICAgICAgLy8gTWlzc2luZyB3aGVuX3ZhbHVlIGZvciBvbmUtdGltZSwgYW5kIHJlcGVhdF9pbnRlcnZhbCBmb3IgcmVjdXJyaW5nXG4gICAgICAgIHRhc2tfaW50ZW50OiAnU09NRV9BQ1RJT04nLFxuICAgICAgICB0YXNrX2VudGl0aWVzOiB7IGZvbzogJ2JhcicgfSxcbiAgICAgIH0sXG4gICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICBvcmlnaW5hbF9xdWVyeTogJ3NjaGVkdWxlIHRoaXMgdGFzaycsXG4gICAgfTtcbiAgICByZXF1aXJlKCcuLi9hdG9tLWFnZW50L3NraWxscy9ubHVTZXJ2aWNlJykudW5kZXJzdGFuZE1lc3NhZ2UubW9ja1Jlc29sdmVkVmFsdWVPbmNlKFxuICAgICAgbmx1T3V0cHV0Rm9yVGhpc1Rlc3RcbiAgICApO1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlKFxuICAgICAgaW50ZXJmYWNlVHlwZSxcbiAgICAgICdzY2hlZHVsZSB0aGlzIHRhc2snLFxuICAgICAgdXNlcklkXG4gICAgKTtcblxuICAgIGV4cGVjdChyZXNwb25zZS50ZXh0KS50b0NvbnRhaW4oXG4gICAgICBcIkNhbm5vdCBzY2hlZHVsZSB0YXNrOiAnd2hlbicgbXVzdCBiZSBwcm92aWRlZCBmb3Igb25lLXRpbWUgdGFza3MsIG9yICdyZXBlYXRJbnRlcnZhbCcgZm9yIHJlY3VycmluZyB0YXNrcy5cIlxuICAgICk7XG4gICAgZXhwZWN0KGFnZW5kYS5zY2hlZHVsZSkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICBleHBlY3QoYWdlbmRhLmV2ZXJ5KS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICB9KTtcblxuICBpdCgnc2hvdWxkIGNvcnJlY3RseSBwYXNzIGNvbnZlcnNhdGlvbklkIGZyb20gb3B0aW9ucyB0byBBZ2VuZGEgam9iIGRhdGEnLCBhc3luYyAoKSA9PiB7XG4gICAgY29uc3Qgd2hlbiA9IG5ldyBEYXRlKCcyMDI0LTAzLTE2VDEyOjAwOjAwLjAwMFonKTtcbiAgICBjb25zdCBzcGVjaWZpY0NvbnZlcnNhdGlvbklkID0gJ3NwZWNpZmljQ29udklkRm9yVGVzdCc7XG4gICAgY29uc3Qgbmx1T3V0cHV0Rm9yVGhpc1Rlc3QgPSB7XG4gICAgICBpbnRlbnQ6ICdTQ0hFRFVMRV9UQVNLJyxcbiAgICAgIGVudGl0aWVzOiB7XG4gICAgICAgIHdoZW5fdmFsdWU6IHdoZW4sXG4gICAgICAgIHRhc2tfaW50ZW50OiAnVEVTVF9DT05WX0lEJyxcbiAgICAgICAgdGFza19lbnRpdGllczogeyBkZXRhaWw6ICd0ZXN0aW5nIGNvbnYgaWQnIH0sXG4gICAgICAgIGlzX3JlY3VycmluZzogZmFsc2UsXG4gICAgICB9LFxuICAgICAgdXNlcl9pZDogdXNlcklkLFxuICAgICAgb3JpZ2luYWxfcXVlcnk6ICdzY2hlZHVsZSB3aXRoIHNwZWNpZmljIGNvbnYgaWQnLFxuICAgIH07XG4gICAgcmVxdWlyZSgnLi4vYXRvbS1hZ2VudC9za2lsbHMvbmx1U2VydmljZScpLnVuZGVyc3RhbmRNZXNzYWdlLm1vY2tSZXNvbHZlZFZhbHVlT25jZShcbiAgICAgIG5sdU91dHB1dEZvclRoaXNUZXN0XG4gICAgKTtcbiAgICAvLyBFbnN1cmUgZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdCByZXR1cm5zIHRoZSBzcGVjaWZpYyBJRCBpZiBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlIHRyaWVzIHRvIGdldCBpdCBmcm9tIHRoZXJlXG4gICAgLy8gSG93ZXZlciwgdGhlIGN1cnJlbnQgaW1wbGVtZW50YXRpb24gb2YgU0NIRURVTEVfVEFTSyBpbiBoYW5kbGVyLnRzIGRpcmVjdGx5IHVzZXMgc2NoZWR1bGVQYXJhbXMuY29udmVyc2F0aW9uSWQsXG4gICAgLy8gd2hpY2ggc2hvdWxkIGNvbWUgZnJvbSB0aGUgYG9wdGlvbnNgIHBhc3NlZCB0byBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlIGlmIGF2YWlsYWJsZS5cbiAgICAvLyBJZiBgb3B0aW9ucy5jb252ZXJzYXRpb25JZGAgaXMgdW5kZWZpbmVkLCB0aGVuIGl0IHRyaWVzIHRvIGdldCBmcm9tIGBjb252ZXJzYXRpb25NYW5hZ2VyLmdldENvbnZlcnNhdGlvblN0YXRlU25hcHNob3QoaW50ZXJmYWNlVHlwZSk/LmNvbnZlcnNhdGlvbklkO2BcbiAgICAvLyBMZXQncyB0ZXN0IHRoZSBwYXRoIHdoZXJlIG9wdGlvbnMuY29udmVyc2F0aW9uSWQgaXMgcHJvdmlkZWQuXG5cbiAgICAvLyBGb3IgdGhpcyB0ZXN0LCB3ZSBzaW11bGF0ZSB0aGF0IGBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlYCBpcyBjYWxsZWQgd2l0aCBgb3B0aW9uc2AgY29udGFpbmluZyBgY29udmVyc2F0aW9uSWRgLlxuICAgIC8vIFRoZSBjdXJyZW50IGBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlYCBvbmx5IHRha2VzIGBjb252ZXJzYXRpb25JZGAgZnJvbSBpdHMgYG9wdGlvbnNgIHBhcmFtZXRlciBpZiBgcmVxdWVzdFNvdXJjZWAgaXMgYFNjaGVkdWxlZEpvYkV4ZWN1dG9yYC5cbiAgICAvLyBUaGUgYFNDSEVEVUxFX1RBU0tgIGJsb2NrLCBob3dldmVyLCBkaXJlY3RseSB1c2VzIGBzY2hlZHVsZVBhcmFtcy5jb252ZXJzYXRpb25JZGAuXG4gICAgLy8gYHNjaGVkdWxlUGFyYW1zLmNvbnZlcnNhdGlvbklkYCBpcyBkZXJpdmVkIGZyb20gYG5sdVJlc3BvbnNlLmVudGl0aWVzLmNvbnZlcnNhdGlvbklkYCBvciBgY3VycmVudENvbnZlcnNhdGlvblN0YXRlLmNvbnZlcnNhdGlvbklkYC5cbiAgICAvLyBTbywgd2UgbmVlZCB0byBlbnN1cmUgTkxVIGVudGl0aWVzIE9SIGNvbnZlcnNhdGlvbk1hbmFnZXIgc25hcHNob3QgcHJvdmlkZXMgaXQuXG5cbiAgICAvLyBMZXQncyBlbnN1cmUgTkxVIHByb3ZpZGVzIGl0IGZvciB0aGlzIHRlc3QuXG4gICAgbmx1T3V0cHV0Rm9yVGhpc1Rlc3QuZW50aXRpZXMuY29udmVyc2F0aW9uSWQgPSBzcGVjaWZpY0NvbnZlcnNhdGlvbklkO1xuICAgIGNvbnZlcnNhdGlvbk1hbmFnZXIuZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdC5tb2NrUmV0dXJuVmFsdWVPbmNlKHtcbiAgICAgIGNvbnZlcnNhdGlvbklkOiAnc29tZURlZmF1bHRDb252SWQnLFxuICAgIH0pOyAvLyBUbyBzZWUgd2hpY2ggb25lIGlzIHBpY2tlZFxuXG4gICAgYXdhaXQgX2ludGVybmFsSGFuZGxlTWVzc2FnZShcbiAgICAgIGludGVyZmFjZVR5cGUsXG4gICAgICAnc2NoZWR1bGUgd2l0aCBzcGVjaWZpYyBjb252IGlkJyxcbiAgICAgIHVzZXJJZCxcbiAgICAgIHsgY29udmVyc2F0aW9uSWQ6IHNwZWNpZmljQ29udmVyc2F0aW9uSWQgfVxuICAgICk7XG5cbiAgICBleHBlY3QoYWdlbmRhLnNjaGVkdWxlKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5hbnkoRGF0ZSksXG4gICAgICAnRVhFQ1VURV9BR0VOVF9BQ1RJT04nLFxuICAgICAgZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xuICAgICAgICBjb252ZXJzYXRpb25JZDogc3BlY2lmaWNDb252ZXJzYXRpb25JZCwgLy8gVGhpcyBpcyB0aGUga2V5IGFzc2VydGlvblxuICAgICAgfSlcbiAgICApO1xuICB9KTtcbn0pO1xuXG4vLyBOb3RlOiBUbyBydW4gdGhlc2UgdGVzdHMsIHlvdSdkIG5lZWQgSmVzdCBpbnN0YWxsZWQgYW5kIGNvbmZpZ3VyZWQuXG4vLyBUaGUgcGF0aHMgaW4gYGplc3QubW9ja2AgY2FsbHMgbWlnaHQgbmVlZCBhZGp1c3RtZW50IGJhc2VkIG9uIHlvdXIgcHJvamVjdCBzdHJ1Y3R1cmUuXG4vLyBBbHNvLCBgX2ludGVybmFsSGFuZGxlTWVzc2FnZWAgYW5kIG90aGVyIGltcG9ydGVkIGZ1bmN0aW9ucyBuZWVkIHRvIGJlIHByb3Blcmx5IGV4cG9ydGVkLlxuLy8gVGhlIG1vY2sgZm9yIGBubHVTZXJ2aWNlYCBpcyB2ZXJ5IGJhc2ljIGFuZCB3b3VsZCBuZWVkIHRvIGJlIG1vcmUgcm9idXN0IGZvciBjb21wcmVoZW5zaXZlIHRlc3RpbmcuXG4vLyBUaGUgYGhhbmRsZXIudHNgIGZpbGUgaXRzZWxmIGhhcyBvdGhlciBkZXBlbmRlbmNpZXMgKGxpa2UgTFRNL1NUTSwgTGFuY2VEQikgdGhhdCBhcmVcbi8vIHN1cGVyZmljaWFsbHkgbW9ja2VkIGhlcmU7IGRlZXBlciB0ZXN0aW5nIHdvdWxkIHJlcXVpcmUgbW9yZSBpbnZvbHZlZCBtb2NrcyBvciB0ZXN0IGRvdWJsZXMgZm9yIHRob3NlLlxuLy8gVGhlIGBjb252ZXJzYXRpb25JZGAgaGFuZGxpbmcgaW4gYFNDSEVEVUxFX1RBU0tgIG5lZWRzIHRvIGJlIGNvbnNpc3RlbnQ6XG4vLyAtIElmIE5MVSBwcm92aWRlcyBpdCBhcyBhbiBlbnRpdHksIHVzZSB0aGF0LlxuLy8gLSBFbHNlLCBpZiBgb3B0aW9ucy5jb252ZXJzYXRpb25JZGAgKGZyb20gQWdlbmRhIGNhbGxiYWNrKSBpcyBhdmFpbGFibGUsIHVzZSB0aGF0LiAoVGhpcyBwYXRoIGlzIGZvciBFWEVDVVRFX0FHRU5UX0FDVElPTilcbi8vIC0gRWxzZSwgdXNlIGBjb252ZXJzYXRpb25NYW5hZ2VyLmdldENvbnZlcnNhdGlvblN0YXRlU25hcHNob3QoKS5jb252ZXJzYXRpb25JZGAuXG4vLyBUaGUgY3VycmVudCBjb2RlIGZvciBTQ0hFRFVMRV9UQVNLOiBgY29udmVyc2F0aW9uSWQ6IHNjaGVkdWxlUGFyYW1zLmNvbnZlcnNhdGlvbklkLGBcbi8vIHdoZXJlIGBzY2hlZHVsZVBhcmFtc2AgZ2V0cyBgY29udmVyc2F0aW9uSWRgIGZyb20gYGVudGl0aWVzLmNvbnZlcnNhdGlvbklkYCBvciBgY3VycmVudENvbnZlcnNhdGlvblN0YXRlLmNvbnZlcnNhdGlvbklkYC5cbi8vIFRoZSB0ZXN0IFwic2hvdWxkIGNvcnJlY3RseSBwYXNzIGNvbnZlcnNhdGlvbklkIGZyb20gb3B0aW9ucyB0byBBZ2VuZGEgam9iIGRhdGFcIiBtaWdodCBiZSBtaXNuYW1lZCxcbi8vIGFzIGl0IHRlc3RzIGBjb252ZXJzYXRpb25JZGAgY29taW5nIGZyb20gTkxVIGVudGl0aWVzIGludG8gdGhlIGBzY2hlZHVsZVBhcmFtc2AgZm9yIGEgKm5ld2x5IHNjaGVkdWxlZCB0YXNrKi5cbi8vIFRoZSBgb3B0aW9ucy5jb252ZXJzYXRpb25JZGAgdG8gYF9pbnRlcm5hbEhhbmRsZU1lc3NhZ2VgIGlzIG1vcmUgcmVsZXZhbnQgd2hlbiBhbiAqZXhpc3RpbmcqIEFnZW5kYSBqb2IgKmV4ZWN1dGVzKiBhbmQgY2FsbHMgYmFjay5cbi8vIFRoZSB0ZXN0IGBzaG91bGQgc2NoZWR1bGUgYSBvbmUtdGltZSB0YXNrIHVzaW5nIGFnZW5kYS5zY2hlZHVsZWAgYWxyZWFkeSBjb3ZlcnMgY29udmVyc2F0aW9uSWQgZnJvbSBgZ2V0Q29udmVyc2F0aW9uU3RhdGVTbmFwc2hvdGBcbi8vIGlmIG5vdCBwcm92aWRlZCBieSBOTFUuXG4vLyBUbyB0cnVseSB0ZXN0IGBvcHRpb25zLmNvbnZlcnNhdGlvbklkYCBwcm9wYWdhdGlvbiBmb3IgYSAqbmV3KiBzY2hlZHVsZSwgTkxVIHdvdWxkIGhhdmUgdG8gcHJvdmlkZSBpdCBPUlxuLy8gdGhlIHdyYXBwZXIgY2FsbGluZyBgX2ludGVybmFsSGFuZGxlTWVzc2FnZWAgZm9yIGEgdXNlciBjb21tYW5kIHdvdWxkIG5lZWQgdG8gcGFzcyBpdCBpbiBvcHRpb25zLlxuLy8gVGhlIGN1cnJlbnQgc3RydWN0dXJlIHNlZW1zIHRvIHByaW9yaXRpemUgTkxVLXByb3ZpZGVkIGBjb252ZXJzYXRpb25JZGAgb3IgYWN0aXZlIGNvbnZlcnNhdGlvbidzIElEIGZvciBuZXcgc2NoZWR1bGVzLlxuLy8gVGhlIGBjb252ZXJzYXRpb25JZGAgaW4gYFNjaGVkdWxlZEFnZW50VGFza0RhdGFgIGlzIGNvcnJlY3RseSBwb3B1bGF0ZWQgZnJvbSBgc2NoZWR1bGVQYXJhbXMuY29udmVyc2F0aW9uSWRgLlxuLy8gQW5kIHdoZW4gdGhlIGpvYiBydW5zLCB0aGlzIGBjb252ZXJzYXRpb25JZGAgZnJvbSBgam9iRGF0YWAgaXMgcGFzc2VkIHRvIGBfaW50ZXJuYWxIYW5kbGVNZXNzYWdlYCB2aWEgaXRzIGBvcHRpb25zYC5cbi8vIFNvIHRoZSBjaGFpbiBsb29rcyBjb3JyZWN0LlxuIl19