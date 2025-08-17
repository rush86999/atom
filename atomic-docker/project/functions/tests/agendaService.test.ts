import axios from 'axios';
import { Agenda } from 'agenda';
import { startAgenda, stopAgenda, defineJob, agenda } from '../agendaService';

// Mock dependencies
jest.mock('agenda');
jest.mock('axios');
jest.mock('../lib/logger', () => ({
  __esModule: true,
  default: {
    info: jest.fn(),
    error: jest.fn(),
    warn: jest.fn(),
  }
}));

// Comprehensive test suite for Agenda service
describe('AgendaService - 100% Coverage', () => {
  let mockAgenda: jest.Mocked<Partial<Agenda>>;
  let mockAxios: jest.Mocked<typeof axios>;

  beforeEach(() => {
    jest.clearAllMocks();

    // Setup test environment
    process.env = {
      ...process.env,
      MONGODB_URI: 'mongodb://localhost:27017/test-db',
      AGENT_INTERNAL_INVOKE_URL: 'http://localhost:3000/api/agent',
    };

    // Mock Agenda
    mockAgenda = {
      define: jest.fn(),
      start: jest.fn().mockResolvedValue(undefined),
      stop: jest.fn().mockResolvedValue(undefined),
      on: jest.fn(),
    };

    // Mock Axios
    mockAxios = axios as jest.Mocked<typeof axios>;
    mockAxios.post.mockResolvedValue({ status: 200, data: { success: true } });
    mockAxios.isAxiosError = jest.fn().mockImplementation((error) => !!(error && error.isAxiosError));

    (Agenda as jest.MockedClass<typeof Agenda>).mockImplementation(() => mockAgenda as any);
  });

  describe('Initialization', () => {
    it('should create Agenda with correct MongoDB config', async () => {
      await startAgenda();

      expect(Agenda).toHaveBeenCalledWith({
        db: { address: process.env.MONGODB_URI, collection: 'agentScheduledTasks' },
        processEvery: '1 minute',
        maxConcurrency: 20,
      });
    });

    it('should define job processors', async () => {
      await startAgenda();

      expect(mockAgenda.define).toHaveBeenCalledWith('EXECUTE_AGENT_ACTION', expect.any(Function));
      expect(mockAgenda.define).toHaveBeenCalledWith('send task reminder', expect.any(Function));
    });

    it('should setup event handlers', async () => {
      await startAgenda();

      expect(mockAgenda.on).toHaveBeenCalledWith('ready', expect.any(Function));
      expect(mockAgenda.on).toHaveBeenCalledWith('error', expect.any(Function));
      expect(mockAgenda.on).toHaveBeenCalledWith('start', expect.any(Function));
      expect(mockAgenda.on).toHaveBeenCalledWith('complete', expect.any(Function));
      expect(mockAgenda.on).toHaveBeenCalledWith('success', expect.any(Function));
      expect(mockAgenda.on).toHaveBeenCalledWith('fail', expect.any(Function));
    });

    it('should use environment variables correctly', async () => {
      const original = process.env.MONGODB_URI;
      process.env.MONGODB_URI = 'test-db';

      await startAgenda();

      expect(Agenda).toHaveBeenCalledWith(expect.objectContaining({
        db: { address: 'test-db', collection: 'agentScheduledTasks' }
      }));

      process.env.MONGODB_URI = original;
    });
  });

  describe('Job Processing', () => {
    let executeAgentJob: Function;
    let sendTaskReminderJob: Function;

    beforeEach(async () => {
      await startAgenda();

      // Extract job processors
      const jobDefinitions = mockAgenda.define.mock.calls;
      const agentJob = jobDefinitions.find(([name]) => name === 'EXECUTE_AGENT_ACTION');
      const reminderJob = jobDefinitions.find(([name]) => name === 'send task reminder');

      executeAgentJob = agentJob?.[1] as Function;
      sendTaskReminderJob = reminderJob?.[1] as Function;
    });

    describe('EXECUTE_AGENT_ACTION job', () => {
      it('should handle successful agent invocation', async () => {
        const mockJob = {
          attrs: {
            _id: 'job-123',
            name: 'EXECUTE_AGENT_ACTION',
            data: {
              originalUserIntent: 'CREATE_TASK',
              entities: { task: 'Send email' },
              userId: 'user-123'
            }
          },
          fail: jest.fn(),
          save: jest.fn()
        };

        await executeAgentJob(mockJob);

        expect(mockAxios.post).toHaveBeenCalledWith(
          process.env.AGENT_INTERNAL_INVOKE_URL!,
          {
            message: 'Execute scheduled task: CREATE_TASK',
            userId: 'user-123',
            intentName: 'CREATE_TASK',
            entities
