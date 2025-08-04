import {
  scheduleTask,
  cancelTask,
  ScheduleTaskParams,
  CancelTaskParams,
} from '../schedulingSkills';
import { agenda, ScheduledAgentTaskData } from '../../../agendaService'; // Actual import for type, mock handles implementation

// Mock the agendaService
const mockAgendaSchedule = jest.fn();
const mockAgendaEvery = jest.fn();
const mockAgendaCancel = jest.fn();

jest.mock('../../../agendaService', () => ({
  __esModule: true, // Needed for ES module imports
  agenda: {
    schedule: mockAgendaSchedule,
    every: mockAgendaEvery,
    cancel: mockAgendaCancel,
  },
  // We don't need to mock ScheduledAgentTaskData as it's an interface
}));

describe('schedulingSkills (Agenda-based)', () => {
  beforeEach(() => {
    // Reset mocks before each test
    mockAgendaSchedule.mockReset().mockResolvedValue({}); // Default to resolve successfully
    mockAgendaEvery.mockReset().mockResolvedValue({}); // Default to resolve successfully
    mockAgendaCancel.mockReset().mockResolvedValue(1); // Default to 1 job cancelled
  });

  describe('scheduleTask', () => {
    const baseJobData: ScheduledAgentTaskData = {
      originalUserIntent: 'TEST_INTENT',
      entities: { data: 'sample' },
      userId: 'user-123',
      conversationId: 'conv-456',
    };

    const baseParams: ScheduleTaskParams = {
      when: '2024-09-01T10:00:00Z',
      originalUserIntent: baseJobData.originalUserIntent,
      entities: baseJobData.entities,
      userId: baseJobData.userId,
      conversationId: baseJobData.conversationId,
      taskDescription: 'Test task scheduling',
    };

    it('should schedule a one-time task using agenda.schedule', async () => {
      const params: ScheduleTaskParams = { ...baseParams, isRecurring: false };
      const result = await scheduleTask(params);

      expect(result).toBe(
        `Task "${params.taskDescription}" has been scheduled for ${params.when}.`
      );
      expect(mockAgendaSchedule).toHaveBeenCalledTimes(1);
      expect(mockAgendaSchedule).toHaveBeenCalledWith(
        params.when,
        'EXECUTE_AGENT_ACTION',
        baseJobData
      );
      expect(mockAgendaEvery).not.toHaveBeenCalled();
    });

    it('should schedule a recurring task using agenda.every', async () => {
      const params: ScheduleTaskParams = {
        ...baseParams,
        isRecurring: true,
        repeatInterval: 'every day at 10am',
        repeatTimezone: 'America/New_York',
      };
      const result = await scheduleTask(params);

      expect(result).toBe(
        `Recurring task "${params.taskDescription}" scheduled to run based on interval: ${params.repeatInterval}.`
      );
      expect(mockAgendaEvery).toHaveBeenCalledTimes(1);
      expect(mockAgendaEvery).toHaveBeenCalledWith(
        params.repeatInterval,
        'EXECUTE_AGENT_ACTION',
        baseJobData,
        { timezone: params.repeatTimezone }
      );
      expect(mockAgendaSchedule).not.toHaveBeenCalled();
    });

    it('should schedule a recurring task without timezone if not provided', async () => {
      const params: ScheduleTaskParams = {
        ...baseParams,
        isRecurring: true,
        repeatInterval: '0 0 * * *', // every day at midnight
      };
      await scheduleTask(params);

      expect(mockAgendaEvery).toHaveBeenCalledTimes(1);
      expect(mockAgendaEvery).toHaveBeenCalledWith(
        params.repeatInterval,
        'EXECUTE_AGENT_ACTION',
        baseJobData,
        {} // Empty options because timezone is undefined
      );
    });

    it('should return an error message if agenda.schedule fails', async () => {
      const error = new Error('Agenda schedule failed');
      mockAgendaSchedule.mockRejectedValue(error);
      const result = await scheduleTask(baseParams);

      expect(result).toBe(`Failed to schedule task: ${error.message}`);
      expect(mockAgendaSchedule).toHaveBeenCalledTimes(1);
    });

    it('should return an error message if agenda.every fails', async () => {
      const error = new Error('Agenda every failed');
      mockAgendaEvery.mockRejectedValue(error);
      const params: ScheduleTaskParams = {
        ...baseParams,
        isRecurring: true,
        repeatInterval: '1 day',
      };
      const result = await scheduleTask(params);

      expect(result).toBe(`Failed to schedule task: ${error.message}`);
      expect(mockAgendaEvery).toHaveBeenCalledTimes(1);
    });

    it('should validate required parameters: when (for one-time)', async () => {
      const params: any = { ...baseParams, when: undefined };
      const result = await scheduleTask(params);
      expect(result).toBe("Scheduling time ('when') must be provided.");
      expect(mockAgendaSchedule).not.toHaveBeenCalled();
    });

    it('should validate required parameters: originalUserIntent', async () => {
      const params: any = { ...baseParams, originalUserIntent: undefined };
      const result = await scheduleTask(params);
      expect(result).toBe(
        'The original user intent to be scheduled must be provided.'
      );
      expect(mockAgendaSchedule).not.toHaveBeenCalled();
    });
  });

  describe('cancelTask', () => {
    it('should cancel tasks based on provided criteria', async () => {
      const params: CancelTaskParams = {
        jobName: 'EXECUTE_AGENT_ACTION',
        userId: 'user-123',
        originalUserIntent: 'TEST_INTENT',
      };
      const query = {
        name: params.jobName,
        'data.userId': params.userId,
        'data.originalUserIntent': params.originalUserIntent,
      };

      mockAgendaCancel.mockResolvedValue(2); // Simulate 2 jobs cancelled
      const result = await cancelTask(params);

      expect(result).toBe(
        'Successfully cancelled 2 task(s) matching criteria.'
      );
      expect(mockAgendaCancel).toHaveBeenCalledTimes(1);
      expect(mockAgendaCancel).toHaveBeenCalledWith(query);
    });

    it('should return a message if no tasks were cancelled', async () => {
      mockAgendaCancel.mockResolvedValue(0); // Simulate 0 jobs cancelled
      const params: CancelTaskParams = { userId: 'user-nonexistent' };
      const result = await cancelTask(params);

      expect(result).toBe('No tasks found matching the criteria to cancel.');
      expect(mockAgendaCancel).toHaveBeenCalledWith({
        'data.userId': 'user-nonexistent',
      });
    });

    it('should return an error if no criteria provided for cancellation', async () => {
      const result = await cancelTask({});
      expect(result).toBe(
        'No criteria provided to cancel tasks. Please specify jobName, userId, or originalUserIntent.'
      );
      expect(mockAgendaCancel).not.toHaveBeenCalled();
    });

    it('should return an error message if agenda.cancel fails', async () => {
      const error = new Error('Agenda cancel failed');
      mockAgendaCancel.mockRejectedValue(error);
      const params: CancelTaskParams = { userId: 'user-123' };
      const result = await cancelTask(params);

      expect(result).toBe(`Failed to cancel task(s): ${error.message}`);
    });
  });
});
