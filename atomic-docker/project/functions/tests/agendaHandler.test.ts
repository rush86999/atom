// @ts-nocheck
/**
 * Tests for Agenda scheduling within atom-agent/handler.ts (_internalHandleMessage)
 */
import { _internalHandleMessage } from '../atom-agent/handler';
import { agenda } from '../agendaService'; // Actual agenda instance
import * { conversationManager } from '../atom-agent/conversationState';

// Mock agenda methods
jest.mock('../agendaService', () => ({
  agenda: {
    schedule: jest.fn().mockResolvedValue({ attrs: { _id: 'mockJobIdScheduled' } }),
    every: jest.fn().mockResolvedValue({ attrs: { _id: 'mockJobIdRecurring' } }),
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
  understandMessage: jest.fn().mockImplementation(async (message, _, ltmContext) => {
    // Basic mock for NLU, specific to SCHEDULE_TASK entities
    if (message.includes("schedule send email tomorrow 10am")) {
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
    if (message.includes("schedule recurring report every monday 9am")) {
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
    return { intent: 'Unknown', entities: {}, user_id: 'test-user', original_query: message };
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
        conversationId: 'testConversationId123'
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
    conversationManager.getConversationStateSnapshot.mockReturnValueOnce({ conversationId: 'testConvIdOneTime' });


    const response = await _internalHandleMessage(interfaceType, message, userId, { conversationId: 'testConvIdOneTime' });

    expect(agenda.schedule).toHaveBeenCalledTimes(1);
    expect(agenda.schedule).toHaveBeenCalledWith(
      when,
      'EXECUTE_AGENT_ACTION',
      expect.objectContaining({
        originalUserIntent: taskIntent,
        entities: taskEntities,
        userId: userId,
        conversationId: 'testConvIdOneTime',
      })
    );
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
    conversationManager.getConversationStateSnapshot.mockReturnValueOnce({ conversationId: 'testConvIdRecurring' });


    const response = await _internalHandleMessage(interfaceType, message, userId, { conversationId: 'testConvIdRecurring' });

    expect(agenda.every).toHaveBeenCalledTimes(1);
    expect(agenda.every).toHaveBeenCalledWith(
      repeatInterval,
      'EXECUTE_AGENT_ACTION',
      expect.objectContaining({
        originalUserIntent: taskIntent,
        entities: taskEntities,
        userId: userId,
        conversationId: 'testConvIdRecurring',
      }),
      expect.objectContaining({
        timezone: repeatTimezone,
        // startDate might be undefined if not provided by NLU via when_value
      })
    );
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
        original_query: "schedule this task",
    };
    require('../atom-agent/skills/nluService').understandMessage.mockResolvedValueOnce(nluOutputForThisTest);

    const response = await _internalHandleMessage(interfaceType, "schedule this task", userId);

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
        original_query: "schedule with specific conv id",
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
     conversationManager.getConversationStateSnapshot.mockReturnValueOnce({ conversationId: 'someDefaultConvId' }); // To see which one is picked

    await _internalHandleMessage(interfaceType, "schedule with specific conv id", userId, { conversationId: specificConversationId });

    expect(agenda.schedule).toHaveBeenCalledWith(
      expect.any(Date),
      'EXECUTE_AGENT_ACTION',
      expect.objectContaining({
        conversationId: specificConversationId, // This is the key assertion
      })
    );
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
