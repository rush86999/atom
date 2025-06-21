import { Agenda as ActualAgenda, Job } from 'agenda'; // Import actual types for casting
import axios from 'axios';
// Import the service to be tested
import { agenda as agendaInstance, startAgenda, stopAgenda, ScheduledAgentTaskData, defineJob } from '../agendaService';

// Mock 'agenda' package
const mockAgendaDefine = jest.fn();
const mockAgendaStart = jest.fn().mockResolvedValue(undefined);
const mockAgendaStop = jest.fn().mockResolvedValue(undefined);
const mockAgendaOn = jest.fn();
const mockJobFail = jest.fn().mockResolvedValue(undefined);
const mockJobSave = jest.fn().mockResolvedValue(undefined);

// This will be the mock Agenda constructor
const mockAgendaConstructor = jest.fn().mockImplementation(() => ({
  define: mockAgendaDefine,
  start: mockAgendaStart,
  stop: mockAgendaStop,
  on: mockAgendaOn,
}));

jest.mock('agenda', () => ({
  __esModule: true,
  Agenda: mockAgendaConstructor,
}));

// Mock 'axios'
jest.mock('axios');
const mockedAxiosPost = axios.post as jest.Mock;

describe('agendaService', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules(); // Important to reset modules to re-evaluate agendaService with fresh mocks
    process.env = { ...originalEnv };

    // Reset all mocks
    mockAgendaConstructor.mockClear();
    mockAgendaDefine.mockClear();
    mockAgendaStart.mockClear();
    mockAgendaStop.mockClear();
    mockAgendaOn.mockClear();
    mockedAxiosPost.mockReset();
    mockJobFail.mockClear();
    mockJobSave.mockClear();

    // Setup default environment variables
    process.env.MONGODB_URI = 'mongodb://mock-db/test-agenda';
    process.env.AGENT_INTERNAL_INVOKE_URL = 'http://mock-agent.com/invoke';
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('Agenda instance should be initialized with correct db settings', () => {
    // agendaService is imported, which initializes agendaInstance on load.
    // We need to re-require or ensure the module is re-evaluated if we want to test constructor calls for each test.
    // For this setup, the constructor is called once when the test file loads agendaService.
    // If agendaService.ts was structured to export a factory function for agenda, testing constructor would be cleaner per call.
    // However, given its current structure (singleton export), we check the initial call.
    expect(mockAgendaConstructor).toHaveBeenCalledTimes(1); // Assuming it's called once per test file execution due to import
    expect(mockAgendaConstructor).toHaveBeenCalledWith({
      db: { address: process.env.MONGODB_URI, collection: 'agentScheduledTasks' },
      processEvery: '1 minute',
      maxConcurrency: 20,
    });
  });

  describe('startAgenda', () => {
    // Re-import or re-evaluate agendaService to get a fresh instance for these tests if needed
    // For now, assume agendaInstance is the one from initial load of the module.
    // To test `defineJob` inside `startAgenda` or the `EXECUTE_AGENT_ACTION` definition,
    // we need to ensure `startAgenda` is called AFTER the mocks are in place for `agenda.define`.

    let agendaServiceModule: typeof import('../agendaService');

    beforeEach(async () => {
        // Dynamically import the module to get a fresh instance with current mocks
        agendaServiceModule = await import('../agendaService');
    });


    it('should call agenda.start() and attach event listeners', async () => {
      await agendaServiceModule.startAgenda();
      expect(mockAgendaStart).toHaveBeenCalledTimes(1);
      expect(mockAgendaOn).toHaveBeenCalledWith('ready', expect.any(Function));
      expect(mockAgendaOn).toHaveBeenCalledWith('error', expect.any(Function));
      // Check for all event listeners defined in agendaService.ts
      expect(mockAgendaOn).toHaveBeenCalledWith('start', expect.any(Function));
      expect(mockAgendaOn).toHaveBeenCalledWith('complete', expect.any(Function));
      expect(mockAgendaOn).toHaveBeenCalledWith('success', expect.any(Function));
      expect(mockAgendaOn).toHaveBeenCalledWith('fail', expect.any(Function));
    });

    it('should define EXECUTE_AGENT_ACTION job processor', async () => {
      await agendaServiceModule.startAgenda(); // This is where EXECUTE_AGENT_ACTION is defined in the current structure
      expect(mockAgendaDefine).toHaveBeenCalledWith('EXECUTE_AGENT_ACTION', expect.any(Function));
    });

    describe('EXECUTE_AGENT_ACTION job processor', () => {
      let jobProcessor: (job: Job<ScheduledAgentTaskData>) => Promise<void>;
      const mockJob = {
        attrs: {
          _id: 'job-id-123',
          name: 'EXECUTE_AGENT_ACTION',
          data: {
            originalUserIntent: 'MOCK_INTENT',
            entities: { mockEntity: 'mockValue' },
            userId: 'mockUser',
          } as ScheduledAgentTaskData,
        },
        fail: mockJobFail,
        save: mockJobSave,
      } as unknown as Job<ScheduledAgentTaskData>; // Type assertion for mock

      beforeEach(async () => {
        // Capture the job processor function
        // Need to call startAgenda to ensure agenda.define is called
        await agendaServiceModule.startAgenda();
        // Find the call to define for 'EXECUTE_AGENT_ACTION' and get the handler
        const defineCall = mockAgendaDefine.mock.calls.find(call => call[0] === 'EXECUTE_AGENT_ACTION');
        if (defineCall && typeof defineCall[1] === 'function') {
          jobProcessor = defineCall[1];
        } else {
          throw new Error("EXECUTE_AGENT_ACTION job processor not defined or not a function");
        }
        mockedAxiosPost.mockReset();
        mockJobFail.mockClear();
        mockJobSave.mockClear();
      });

      it('should call axios.post with correct payload and handle successful response', async () => {
        mockedAxiosPost.mockResolvedValue({ status: 200, data: { success: true } });
        await jobProcessor(mockJob);

        expect(mockedAxiosPost).toHaveBeenCalledTimes(1);
        expect(mockedAxiosPost).toHaveBeenCalledWith(
          process.env.AGENT_INTERNAL_INVOKE_URL,
          {
            message: `Scheduled task: ${mockJob.attrs.data.originalUserIntent}`,
            intentName: mockJob.attrs.data.originalUserIntent,
            entities: mockJob.attrs.data.entities,
            userId: mockJob.attrs.data.userId,
            conversationId: mockJob.attrs.data.conversationId,
            requestSource: 'ScheduledJobExecutor',
          },
          { headers: { 'Content-Type': 'application/json' } }
        );
        expect(mockJobFail).not.toHaveBeenCalled();
      });

      it('should handle axios.post failure and call job.fail and job.save', async () => {
        const axiosError = {
            isAxiosError: true,
            response: { status: 500, data: { message: 'Agent internal error' } },
            message: 'Request failed with status code 500'
        };
        mockedAxiosPost.mockRejectedValue(axiosError);
        await jobProcessor(mockJob);

        expect(mockedAxiosPost).toHaveBeenCalledTimes(1);
        expect(mockJobFail).toHaveBeenCalledTimes(1);
        const expectedErrorMessage = `Agent endpoint error: 500 - ${JSON.stringify(axiosError.response.data)}`;
        expect(mockJobFail).toHaveBeenCalledWith(expectedErrorMessage);
        expect(mockJobSave).toHaveBeenCalledTimes(1);
      });

      it('should handle non-Axios error and call job.fail and job.save', async () => {
        const genericError = new Error('Some other error');
        mockedAxiosPost.mockRejectedValue(genericError);
        await jobProcessor(mockJob);

        expect(mockedAxiosPost).toHaveBeenCalledTimes(1);
        expect(mockJobFail).toHaveBeenCalledTimes(1);
        expect(mockJobFail).toHaveBeenCalledWith(genericError.message);
        expect(mockJobSave).toHaveBeenCalledTimes(1);
      });

      it('should handle missing job.attrs.data', async () => {
        const jobWithMissingData = {
          attrs: { _id: 'job-id-no-data', name: 'EXECUTE_AGENT_ACTION', data: null }, // data is null
          fail: mockJobFail,
          save: mockJobSave,
        } as unknown as Job<ScheduledAgentTaskData>;

        await jobProcessor(jobWithMissingData);

        expect(mockedAxiosPost).not.toHaveBeenCalled();
        expect(mockJobFail).toHaveBeenCalledTimes(1);
        expect(mockJobFail).toHaveBeenCalledWith('Job data is missing.');
        expect(mockJobSave).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('stopAgenda', () => {
    it('should call agenda.stop()', async () => {
      // Re-import or re-evaluate agendaService to get a fresh instance for these tests if needed
      const localAgendaServiceModule = await import('../agendaService');
      await localAgendaServiceModule.stopAgenda();
      expect(mockAgendaStop).toHaveBeenCalledTimes(1);
    });
  });

  describe('defineJob', () => {
    it('should call agenda.define with the given name and handler', () => {
      const jobName = 'test-job-definition';
      const handler = async (job: Job) => { console.log('test handler'); };
      // Re-import or re-evaluate agendaService to get a fresh instance for these tests if needed
      const localAgendaServiceModule = require('../agendaService'); // Use require for re-evaluation in CJS context if not using dynamic import
      localAgendaServiceModule.defineJob(jobName, handler);
      expect(mockAgendaDefine).toHaveBeenCalledWith(jobName, handler);
    });
  });
});
