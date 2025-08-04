import axios from 'axios';
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
const mockedAxiosPost = axios.post;
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
            db: {
                address: process.env.MONGODB_URI,
                collection: 'agentScheduledTasks',
            },
            processEvery: '1 minute',
            maxConcurrency: 20,
        });
    });
    describe('startAgenda', () => {
        // Re-import or re-evaluate agendaService to get a fresh instance for these tests if needed
        // For now, assume agendaInstance is the one from initial load of the module.
        // To test `defineJob` inside `startAgenda` or the `EXECUTE_AGENT_ACTION` definition,
        // we need to ensure `startAgenda` is called AFTER the mocks are in place for `agenda.define`.
        let agendaServiceModule;
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
            let jobProcessor;
            const mockJob = {
                attrs: {
                    _id: 'job-id-123',
                    name: 'EXECUTE_AGENT_ACTION',
                    data: {
                        originalUserIntent: 'MOCK_INTENT',
                        entities: { mockEntity: 'mockValue' },
                        userId: 'mockUser',
                    },
                },
                fail: mockJobFail,
                save: mockJobSave,
            }; // Type assertion for mock
            beforeEach(async () => {
                // Capture the job processor function
                // Need to call startAgenda to ensure agenda.define is called
                await agendaServiceModule.startAgenda();
                // Find the call to define for 'EXECUTE_AGENT_ACTION' and get the handler
                const defineCall = mockAgendaDefine.mock.calls.find((call) => call[0] === 'EXECUTE_AGENT_ACTION');
                if (defineCall && typeof defineCall[1] === 'function') {
                    jobProcessor = defineCall[1];
                }
                else {
                    throw new Error('EXECUTE_AGENT_ACTION job processor not defined or not a function');
                }
                mockedAxiosPost.mockReset();
                mockJobFail.mockClear();
                mockJobSave.mockClear();
            });
            it('should call axios.post with correct payload and handle successful response', async () => {
                mockedAxiosPost.mockResolvedValue({
                    status: 200,
                    data: { success: true },
                });
                await jobProcessor(mockJob);
                expect(mockedAxiosPost).toHaveBeenCalledTimes(1);
                expect(mockedAxiosPost).toHaveBeenCalledWith(process.env.AGENT_INTERNAL_INVOKE_URL, {
                    message: `Scheduled task: ${mockJob.attrs.data.originalUserIntent}`,
                    intentName: mockJob.attrs.data.originalUserIntent,
                    entities: mockJob.attrs.data.entities,
                    userId: mockJob.attrs.data.userId,
                    conversationId: mockJob.attrs.data.conversationId,
                    requestSource: 'ScheduledJobExecutor',
                }, { headers: { 'Content-Type': 'application/json' } });
                expect(mockJobFail).not.toHaveBeenCalled();
            });
            it('should handle axios.post failure and call job.fail and job.save', async () => {
                const axiosError = {
                    isAxiosError: true,
                    response: { status: 500, data: { message: 'Agent internal error' } },
                    message: 'Request failed with status code 500',
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
                    attrs: {
                        _id: 'job-id-no-data',
                        name: 'EXECUTE_AGENT_ACTION',
                        data: null,
                    }, // data is null
                    fail: mockJobFail,
                    save: mockJobSave,
                };
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
            const handler = async (job) => {
                console.log('test handler');
            };
            // Re-import or re-evaluate agendaService to get a fresh instance for these tests if needed
            const localAgendaServiceModule = require('../agendaService'); // Use require for re-evaluation in CJS context if not using dynamic import
            localAgendaServiceModule.defineJob(jobName, handler);
            expect(mockAgendaDefine).toHaveBeenCalledWith(jobName, handler);
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYWdlbmRhU2VydmljZS50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiYWdlbmRhU2VydmljZS50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sS0FBSyxNQUFNLE9BQU8sQ0FBQztBQVUxQix3QkFBd0I7QUFDeEIsTUFBTSxnQkFBZ0IsR0FBRyxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7QUFDbkMsTUFBTSxlQUFlLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLGlCQUFpQixDQUFDLFNBQVMsQ0FBQyxDQUFDO0FBQy9ELE1BQU0sY0FBYyxHQUFHLElBQUksQ0FBQyxFQUFFLEVBQUUsQ0FBQyxpQkFBaUIsQ0FBQyxTQUFTLENBQUMsQ0FBQztBQUM5RCxNQUFNLFlBQVksR0FBRyxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7QUFDL0IsTUFBTSxXQUFXLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLGlCQUFpQixDQUFDLFNBQVMsQ0FBQyxDQUFDO0FBQzNELE1BQU0sV0FBVyxHQUFHLElBQUksQ0FBQyxFQUFFLEVBQUUsQ0FBQyxpQkFBaUIsQ0FBQyxTQUFTLENBQUMsQ0FBQztBQUUzRCwyQ0FBMkM7QUFDM0MsTUFBTSxxQkFBcUIsR0FBRyxJQUFJLENBQUMsRUFBRSxFQUFFLENBQUMsa0JBQWtCLENBQUMsR0FBRyxFQUFFLENBQUMsQ0FBQztJQUNoRSxNQUFNLEVBQUUsZ0JBQWdCO0lBQ3hCLEtBQUssRUFBRSxlQUFlO0lBQ3RCLElBQUksRUFBRSxjQUFjO0lBQ3BCLEVBQUUsRUFBRSxZQUFZO0NBQ2pCLENBQUMsQ0FBQyxDQUFDO0FBRUosSUFBSSxDQUFDLElBQUksQ0FBQyxRQUFRLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQztJQUN6QixVQUFVLEVBQUUsSUFBSTtJQUNoQixNQUFNLEVBQUUscUJBQXFCO0NBQzlCLENBQUMsQ0FBQyxDQUFDO0FBRUosZUFBZTtBQUNmLElBQUksQ0FBQyxJQUFJLENB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QztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgQWdlbmRhIGFzIEFjdHVhbEFnZW5kYSwgSm9iIH0gZnJvbSAnYWdlbmRhJzsgLy8gSW1wb3J0IGFjdHVhbCB0eXBlcyBmb3IgY2FzdGluZ1xuaW1wb3J0IGF4aW9zIGZyb20gJ2F4aW9zJztcbi8vIEltcG9ydCB0aGUgc2VydmljZSB0byBiZSB0ZXN0ZWRcbmltcG9ydCB7XG4gIGFnZW5kYSBhcyBhZ2VuZGFJbnN0YW5jZSxcbiAgc3RhcnRBZ2VuZGEsXG4gIHN0b3BBZ2VuZGEsXG4gIFNjaGVkdWxlZEFnZW50VGFza0RhdGEsXG4gIGRlZmluZUpvYixcbn0gZnJvbSAnLi4vYWdlbmRhU2VydmljZSc7XG5cbi8vIE1vY2sgJ2FnZW5kYScgcGFja2FnZVxuY29uc3QgbW9ja0FnZW5kYURlZmluZSA9IGplc3QuZm4oKTtcbmNvbnN0IG1vY2tBZ2VuZGFTdGFydCA9IGplc3QuZm4oKS5tb2NrUmVzb2x2ZWRWYWx1ZSh1bmRlZmluZWQpO1xuY29uc3QgbW9ja0FnZW5kYVN0b3AgPSBqZXN0LmZuKCkubW9ja1Jlc29sdmVkVmFsdWUodW5kZWZpbmVkKTtcbmNvbnN0IG1vY2tBZ2VuZGFPbiA9IGplc3QuZm4oKTtcbmNvbnN0IG1vY2tKb2JGYWlsID0gamVzdC5mbigpLm1vY2tSZXNvbHZlZFZhbHVlKHVuZGVmaW5lZCk7XG5jb25zdCBtb2NrSm9iU2F2ZSA9IGplc3QuZm4oKS5tb2NrUmVzb2x2ZWRWYWx1ZSh1bmRlZmluZWQpO1xuXG4vLyBUaGlzIHdpbGwgYmUgdGhlIG1vY2sgQWdlbmRhIGNvbnN0cnVjdG9yXG5jb25zdCBtb2NrQWdlbmRhQ29uc3RydWN0b3IgPSBqZXN0LmZuKCkubW9ja0ltcGxlbWVudGF0aW9uKCgpID0+ICh7XG4gIGRlZmluZTogbW9ja0FnZW5kYURlZmluZSxcbiAgc3RhcnQ6IG1vY2tBZ2VuZGFTdGFydCxcbiAgc3RvcDogbW9ja0FnZW5kYVN0b3AsXG4gIG9uOiBtb2NrQWdlbmRhT24sXG59KSk7XG5cbmplc3QubW9jaygnYWdlbmRhJywgKCkgPT4gKHtcbiAgX19lc01vZHVsZTogdHJ1ZSxcbiAgQWdlbmRhOiBtb2NrQWdlbmRhQ29uc3RydWN0b3IsXG59KSk7XG5cbi8vIE1vY2sgJ2F4aW9zJ1xuamVzdC5tb2NrKCdheGlvcycpO1xuY29uc3QgbW9ja2VkQXhpb3NQb3N0ID0gYXhpb3MucG9zdCBhcyBqZXN0Lk1vY2s7XG5cbmRlc2NyaWJlKCdhZ2VuZGFTZXJ2aWNlJywgKCkgPT4ge1xuICBjb25zdCBvcmlnaW5hbEVudiA9IHByb2Nlc3MuZW52O1xuXG4gIGJlZm9yZUVhY2goKCkgPT4ge1xuICAgIGplc3QucmVzZXRNb2R1bGVzKCk7IC8vIEltcG9ydGFudCB0byByZXNldCBtb2R1bGVzIHRvIHJlLWV2YWx1YXRlIGFnZW5kYVNlcnZpY2Ugd2l0aCBmcmVzaCBtb2Nrc1xuICAgIHByb2Nlc3MuZW52ID0geyAuLi5vcmlnaW5hbEVudiB9O1xuXG4gICAgLy8gUmVzZXQgYWxsIG1vY2tzXG4gICAgbW9ja0FnZW5kYUNvbnN0cnVjdG9yLm1vY2tDbGVhcigpO1xuICAgIG1vY2tBZ2VuZGFEZWZpbmUubW9ja0NsZWFyKCk7XG4gICAgbW9ja0FnZW5kYVN0YXJ0Lm1vY2tDbGVhcigpO1xuICAgIG1vY2tBZ2VuZGFTdG9wLm1vY2tDbGVhcigpO1xuICAgIG1vY2tBZ2VuZGFPbi5tb2NrQ2xlYXIoKTtcbiAgICBtb2NrZWRBeGlvc1Bvc3QubW9ja1Jlc2V0KCk7XG4gICAgbW9ja0pvYkZhaWwubW9ja0NsZWFyKCk7XG4gICAgbW9ja0pvYlNhdmUubW9ja0NsZWFyKCk7XG5cbiAgICAvLyBTZXR1cCBkZWZhdWx0IGVudmlyb25tZW50IHZhcmlhYmxlc1xuICAgIHByb2Nlc3MuZW52Lk1PTkdPREJfVVJJID0gJ21vbmdvZGI6Ly9tb2NrLWRiL3Rlc3QtYWdlbmRhJztcbiAgICBwcm9jZXNzLmVudi5BR0VOVF9JTlRFUk5BTF9JTlZPS0VfVVJMID0gJ2h0dHA6Ly9tb2NrLWFnZW50LmNvbS9pbnZva2UnO1xuICB9KTtcblxuICBhZnRlckFsbCgoKSA9PiB7XG4gICAgcHJvY2Vzcy5lbnYgPSBvcmlnaW5hbEVudjtcbiAgfSk7XG5cbiAgaXQoJ0FnZW5kYSBpbnN0YW5jZSBzaG91bGQgYmUgaW5pdGlhbGl6ZWQgd2l0aCBjb3JyZWN0IGRiIHNldHRpbmdzJywgKCkgPT4ge1xuICAgIC8vIGFnZW5kYVNlcnZpY2UgaXMgaW1wb3J0ZWQsIHdoaWNoIGluaXRpYWxpemVzIGFnZW5kYUluc3RhbmNlIG9uIGxvYWQuXG4gICAgLy8gV2UgbmVlZCB0byByZS1yZXF1aXJlIG9yIGVuc3VyZSB0aGUgbW9kdWxlIGlzIHJlLWV2YWx1YXRlZCBpZiB3ZSB3YW50IHRvIHRlc3QgY29uc3RydWN0b3IgY2FsbHMgZm9yIGVhY2ggdGVzdC5cbiAgICAvLyBGb3IgdGhpcyBzZXR1cCwgdGhlIGNvbnN0cnVjdG9yIGlzIGNhbGxlZCBvbmNlIHdoZW4gdGhlIHRlc3QgZmlsZSBsb2FkcyBhZ2VuZGFTZXJ2aWNlLlxuICAgIC8vIElmIGFnZW5kYVNlcnZpY2UudHMgd2FzIHN0cnVjdHVyZWQgdG8gZXhwb3J0IGEgZmFjdG9yeSBmdW5jdGlvbiBmb3IgYWdlbmRhLCB0ZXN0aW5nIGNvbnN0cnVjdG9yIHdvdWxkIGJlIGNsZWFuZXIgcGVyIGNhbGwuXG4gICAgLy8gSG93ZXZlciwgZ2l2ZW4gaXRzIGN1cnJlbnQgc3RydWN0dXJlIChzaW5nbGV0b24gZXhwb3J0KSwgd2UgY2hlY2sgdGhlIGluaXRpYWwgY2FsbC5cbiAgICBleHBlY3QobW9ja0FnZW5kYUNvbnN0cnVjdG9yKS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7IC8vIEFzc3VtaW5nIGl0J3MgY2FsbGVkIG9uY2UgcGVyIHRlc3QgZmlsZSBleGVjdXRpb24gZHVlIHRvIGltcG9ydFxuICAgIGV4cGVjdChtb2NrQWdlbmRhQ29uc3RydWN0b3IpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKHtcbiAgICAgIGRiOiB7XG4gICAgICAgIGFkZHJlc3M6IHByb2Nlc3MuZW52Lk1PTkdPREJfVVJJLFxuICAgICAgICBjb2xsZWN0aW9uOiAnYWdlbnRTY2hlZHVsZWRUYXNrcycsXG4gICAgICB9LFxuICAgICAgcHJvY2Vzc0V2ZXJ5OiAnMSBtaW51dGUnLFxuICAgICAgbWF4Q29uY3VycmVuY3k6IDIwLFxuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnc3RhcnRBZ2VuZGEnLCAoKSA9PiB7XG4gICAgLy8gUmUtaW1wb3J0IG9yIHJlLWV2YWx1YXRlIGFnZW5kYVNlcnZpY2UgdG8gZ2V0IGEgZnJlc2ggaW5zdGFuY2UgZm9yIHRoZXNlIHRlc3RzIGlmIG5lZWRlZFxuICAgIC8vIEZvciBub3csIGFzc3VtZSBhZ2VuZGFJbnN0YW5jZSBpcyB0aGUgb25lIGZyb20gaW5pdGlhbCBsb2FkIG9mIHRoZSBtb2R1bGUuXG4gICAgLy8gVG8gdGVzdCBgZGVmaW5lSm9iYCBpbnNpZGUgYHN0YXJ0QWdlbmRhYCBvciB0aGUgYEVYRUNVVEVfQUdFTlRfQUNUSU9OYCBkZWZpbml0aW9uLFxuICAgIC8vIHdlIG5lZWQgdG8gZW5zdXJlIGBzdGFydEFnZW5kYWAgaXMgY2FsbGVkIEFGVEVSIHRoZSBtb2NrcyBhcmUgaW4gcGxhY2UgZm9yIGBhZ2VuZGEuZGVmaW5lYC5cblxuICAgIGxldCBhZ2VuZGFTZXJ2aWNlTW9kdWxlOiB0eXBlb2YgaW1wb3J0KCcuLi9hZ2VuZGFTZXJ2aWNlJyk7XG5cbiAgICBiZWZvcmVFYWNoKGFzeW5jICgpID0+IHtcbiAgICAgIC8vIER5bmFtaWNhbGx5IGltcG9ydCB0aGUgbW9kdWxlIHRvIGdldCBhIGZyZXNoIGluc3RhbmNlIHdpdGggY3VycmVudCBtb2Nrc1xuICAgICAgYWdlbmRhU2VydmljZU1vZHVsZSA9IGF3YWl0IGltcG9ydCgnLi4vYWdlbmRhU2VydmljZScpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBjYWxsIGFnZW5kYS5zdGFydCgpIGFuZCBhdHRhY2ggZXZlbnQgbGlzdGVuZXJzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgYXdhaXQgYWdlbmRhU2VydmljZU1vZHVsZS5zdGFydEFnZW5kYSgpO1xuICAgICAgZXhwZWN0KG1vY2tBZ2VuZGFTdGFydCkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgZXhwZWN0KG1vY2tBZ2VuZGFPbikudG9IYXZlQmVlbkNhbGxlZFdpdGgoJ3JlYWR5JywgZXhwZWN0LmFueShGdW5jdGlvbikpO1xuICAgICAgZXhwZWN0KG1vY2tBZ2VuZGFPbikudG9IYXZlQmVlbkNhbGxlZFdpdGgoJ2Vycm9yJywgZXhwZWN0LmFueShGdW5jdGlvbikpO1xuICAgICAgLy8gQ2hlY2sgZm9yIGFsbCBldmVudCBsaXN0ZW5lcnMgZGVmaW5lZCBpbiBhZ2VuZGFTZXJ2aWNlLnRzXG4gICAgICBleHBlY3QobW9ja0FnZW5kYU9uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aCgnc3RhcnQnLCBleHBlY3QuYW55KEZ1bmN0aW9uKSk7XG4gICAgICBleHBlY3QobW9ja0FnZW5kYU9uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgJ2NvbXBsZXRlJyxcbiAgICAgICAgZXhwZWN0LmFueShGdW5jdGlvbilcbiAgICAgICk7XG4gICAgICBleHBlY3QobW9ja0FnZW5kYU9uKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgJ3N1Y2Nlc3MnLFxuICAgICAgICBleHBlY3QuYW55KEZ1bmN0aW9uKVxuICAgICAgKTtcbiAgICAgIGV4cGVjdChtb2NrQWdlbmRhT24pLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKCdmYWlsJywgZXhwZWN0LmFueShGdW5jdGlvbikpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBkZWZpbmUgRVhFQ1VURV9BR0VOVF9BQ1RJT04gam9iIHByb2Nlc3NvcicsIGFzeW5jICgpID0+IHtcbiAgICAgIGF3YWl0IGFnZW5kYVNlcnZpY2VNb2R1bGUuc3RhcnRBZ2VuZGEoKTsgLy8gVGhpcyBpcyB3aGVyZSBFWEVDVVRFX0FHRU5UX0FDVElPTiBpcyBkZWZpbmVkIGluIHRoZSBjdXJyZW50IHN0cnVjdHVyZVxuICAgICAgZXhwZWN0KG1vY2tBZ2VuZGFEZWZpbmUpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICAnRVhFQ1VURV9BR0VOVF9BQ1RJT04nLFxuICAgICAgICBleHBlY3QuYW55KEZ1bmN0aW9uKVxuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGRlc2NyaWJlKCdFWEVDVVRFX0FHRU5UX0FDVElPTiBqb2IgcHJvY2Vzc29yJywgKCkgPT4ge1xuICAgICAgbGV0IGpvYlByb2Nlc3NvcjogKGpvYjogSm9iPFNjaGVkdWxlZEFnZW50VGFza0RhdGE+KSA9PiBQcm9taXNlPHZvaWQ+O1xuICAgICAgY29uc3QgbW9ja0pvYiA9IHtcbiAgICAgICAgYXR0cnM6IHtcbiAgICAgICAgICBfaWQ6ICdqb2ItaWQtMTIzJyxcbiAgICAgICAgICBuYW1lOiAnRVhFQ1VURV9BR0VOVF9BQ1RJT04nLFxuICAgICAgICAgIGRhdGE6IHtcbiAgICAgICAgICAgIG9yaWdpbmFsVXNlckludGVudDogJ01PQ0tfSU5URU5UJyxcbiAgICAgICAgICAgIGVudGl0aWVzOiB7IG1vY2tFbnRpdHk6ICdtb2NrVmFsdWUnIH0sXG4gICAgICAgICAgICB1c2VySWQ6ICdtb2NrVXNlcicsXG4gICAgICAgICAgfSBhcyBTY2hlZHVsZWRBZ2VudFRhc2tEYXRhLFxuICAgICAgICB9LFxuICAgICAgICBmYWlsOiBtb2NrSm9iRmFpbCxcbiAgICAgICAgc2F2ZTogbW9ja0pvYlNhdmUsXG4gICAgICB9IGFzIHVua25vd24gYXMgSm9iPFNjaGVkdWxlZEFnZW50VGFza0RhdGE+OyAvLyBUeXBlIGFzc2VydGlvbiBmb3IgbW9ja1xuXG4gICAgICBiZWZvcmVFYWNoKGFzeW5jICgpID0+IHtcbiAgICAgICAgLy8gQ2FwdHVyZSB0aGUgam9iIHByb2Nlc3NvciBmdW5jdGlvblxuICAgICAgICAvLyBOZWVkIHRvIGNhbGwgc3RhcnRBZ2VuZGEgdG8gZW5zdXJlIGFnZW5kYS5kZWZpbmUgaXMgY2FsbGVkXG4gICAgICAgIGF3YWl0IGFnZW5kYVNlcnZpY2VNb2R1bGUuc3RhcnRBZ2VuZGEoKTtcbiAgICAgICAgLy8gRmluZCB0aGUgY2FsbCB0byBkZWZpbmUgZm9yICdFWEVDVVRFX0FHRU5UX0FDVElPTicgYW5kIGdldCB0aGUgaGFuZGxlclxuICAgICAgICBjb25zdCBkZWZpbmVDYWxsID0gbW9ja0FnZW5kYURlZmluZS5tb2NrLmNhbGxzLmZpbmQoXG4gICAgICAgICAgKGNhbGwpID0+IGNhbGxbMF0gPT09ICdFWEVDVVRFX0FHRU5UX0FDVElPTidcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGRlZmluZUNhbGwgJiYgdHlwZW9mIGRlZmluZUNhbGxbMV0gPT09ICdmdW5jdGlvbicpIHtcbiAgICAgICAgICBqb2JQcm9jZXNzb3IgPSBkZWZpbmVDYWxsWzFdO1xuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgICAgICdFWEVDVVRFX0FHRU5UX0FDVElPTiBqb2IgcHJvY2Vzc29yIG5vdCBkZWZpbmVkIG9yIG5vdCBhIGZ1bmN0aW9uJ1xuICAgICAgICAgICk7XG4gICAgICAgIH1cbiAgICAgICAgbW9ja2VkQXhpb3NQb3N0Lm1vY2tSZXNldCgpO1xuICAgICAgICBtb2NrSm9iRmFpbC5tb2NrQ2xlYXIoKTtcbiAgICAgICAgbW9ja0pvYlNhdmUubW9ja0NsZWFyKCk7XG4gICAgICB9KTtcblxuICAgICAgaXQoJ3Nob3VsZCBjYWxsIGF4aW9zLnBvc3Qgd2l0aCBjb3JyZWN0IHBheWxvYWQgYW5kIGhhbmRsZSBzdWNjZXNzZnVsIHJlc3BvbnNlJywgYXN5bmMgKCkgPT4ge1xuICAgICAgICBtb2NrZWRBeGlvc1Bvc3QubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICAgIHN0YXR1czogMjAwLFxuICAgICAgICAgIGRhdGE6IHsgc3VjY2VzczogdHJ1ZSB9LFxuICAgICAgICB9KTtcbiAgICAgICAgYXdhaXQgam9iUHJvY2Vzc29yKG1vY2tKb2IpO1xuXG4gICAgICAgIGV4cGVjdChtb2NrZWRBeGlvc1Bvc3QpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTtcbiAgICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zUG9zdCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgICAgcHJvY2Vzcy5lbnYuQUdFTlRfSU5URVJOQUxfSU5WT0tFX1VSTCxcbiAgICAgICAgICB7XG4gICAgICAgICAgICBtZXNzYWdlOiBgU2NoZWR1bGVkIHRhc2s6ICR7bW9ja0pvYi5hdHRycy5kYXRhLm9yaWdpbmFsVXNlckludGVudH1gLFxuICAgICAgICAgICAgaW50ZW50TmFtZTogbW9ja0pvYi5hdHRycy5kYXRhLm9yaWdpbmFsVXNlckludGVudCxcbiAgICAgICAgICAgIGVudGl0aWVzOiBtb2NrSm9iLmF0dHJzLmRhdGEuZW50aXRpZXMsXG4gICAgICAgICAgICB1c2VySWQ6IG1vY2tKb2IuYXR0cnMuZGF0YS51c2VySWQsXG4gICAgICAgICAgICBjb252ZXJzYXRpb25JZDogbW9ja0pvYi5hdHRycy5kYXRhLmNvbnZlcnNhdGlvbklkLFxuICAgICAgICAgICAgcmVxdWVzdFNvdXJjZTogJ1NjaGVkdWxlZEpvYkV4ZWN1dG9yJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHsgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0gfVxuICAgICAgICApO1xuICAgICAgICBleHBlY3QobW9ja0pvYkZhaWwpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgICB9KTtcblxuICAgICAgaXQoJ3Nob3VsZCBoYW5kbGUgYXhpb3MucG9zdCBmYWlsdXJlIGFuZCBjYWxsIGpvYi5mYWlsIGFuZCBqb2Iuc2F2ZScsIGFzeW5jICgpID0+IHtcbiAgICAgICAgY29uc3QgYXhpb3NFcnJvciA9IHtcbiAgICAgICAgICBpc0F4aW9zRXJyb3I6IHRydWUsXG4gICAgICAgICAgcmVzcG9uc2U6IHsgc3RhdHVzOiA1MDAsIGRhdGE6IHsgbWVzc2FnZTogJ0FnZW50IGludGVybmFsIGVycm9yJyB9IH0sXG4gICAgICAgICAgbWVzc2FnZTogJ1JlcXVlc3QgZmFpbGVkIHdpdGggc3RhdHVzIGNvZGUgNTAwJyxcbiAgICAgICAgfTtcbiAgICAgICAgbW9ja2VkQXhpb3NQb3N0Lm1vY2tSZWplY3RlZFZhbHVlKGF4aW9zRXJyb3IpO1xuICAgICAgICBhd2FpdCBqb2JQcm9jZXNzb3IobW9ja0pvYik7XG5cbiAgICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zUG9zdCkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgICBleHBlY3QobW9ja0pvYkZhaWwpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTtcbiAgICAgICAgY29uc3QgZXhwZWN0ZWRFcnJvck1lc3NhZ2UgPSBgQWdlbnQgZW5kcG9pbnQgZXJyb3I6IDUwMCAtICR7SlNPTi5zdHJpbmdpZnkoYXhpb3NFcnJvci5yZXNwb25zZS5kYXRhKX1gO1xuICAgICAgICBleHBlY3QobW9ja0pvYkZhaWwpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKGV4cGVjdGVkRXJyb3JNZXNzYWdlKTtcbiAgICAgICAgZXhwZWN0KG1vY2tKb2JTYXZlKS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgICB9KTtcblxuICAgICAgaXQoJ3Nob3VsZCBoYW5kbGUgbm9uLUF4aW9zIGVycm9yIGFuZCBjYWxsIGpvYi5mYWlsIGFuZCBqb2Iuc2F2ZScsIGFzeW5jICgpID0+IHtcbiAgICAgICAgY29uc3QgZ2VuZXJpY0Vycm9yID0gbmV3IEVycm9yKCdTb21lIG90aGVyIGVycm9yJyk7XG4gICAgICAgIG1vY2tlZEF4aW9zUG9zdC5tb2NrUmVqZWN0ZWRWYWx1ZShnZW5lcmljRXJyb3IpO1xuICAgICAgICBhd2FpdCBqb2JQcm9jZXNzb3IobW9ja0pvYik7XG5cbiAgICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zUG9zdCkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgICBleHBlY3QobW9ja0pvYkZhaWwpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTtcbiAgICAgICAgZXhwZWN0KG1vY2tKb2JGYWlsKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChnZW5lcmljRXJyb3IubWVzc2FnZSk7XG4gICAgICAgIGV4cGVjdChtb2NrSm9iU2F2ZSkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgfSk7XG5cbiAgICAgIGl0KCdzaG91bGQgaGFuZGxlIG1pc3Npbmcgam9iLmF0dHJzLmRhdGEnLCBhc3luYyAoKSA9PiB7XG4gICAgICAgIGNvbnN0IGpvYldpdGhNaXNzaW5nRGF0YSA9IHtcbiAgICAgICAgICBhdHRyczoge1xuICAgICAgICAgICAgX2lkOiAnam9iLWlkLW5vLWRhdGEnLFxuICAgICAgICAgICAgbmFtZTogJ0VYRUNVVEVfQUdFTlRfQUNUSU9OJyxcbiAgICAgICAgICAgIGRhdGE6IG51bGwsXG4gICAgICAgICAgfSwgLy8gZGF0YSBpcyBudWxsXG4gICAgICAgICAgZmFpbDogbW9ja0pvYkZhaWwsXG4gICAgICAgICAgc2F2ZTogbW9ja0pvYlNhdmUsXG4gICAgICAgIH0gYXMgdW5rbm93biBhcyBKb2I8U2NoZWR1bGVkQWdlbnRUYXNrRGF0YT47XG5cbiAgICAgICAgYXdhaXQgam9iUHJvY2Vzc29yKGpvYldpdGhNaXNzaW5nRGF0YSk7XG5cbiAgICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zUG9zdCkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICAgICAgZXhwZWN0KG1vY2tKb2JGYWlsKS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgICAgIGV4cGVjdChtb2NrSm9iRmFpbCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoJ0pvYiBkYXRhIGlzIG1pc3NpbmcuJyk7XG4gICAgICAgIGV4cGVjdChtb2NrSm9iU2F2ZSkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgfSk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdzdG9wQWdlbmRhJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgY2FsbCBhZ2VuZGEuc3RvcCgpJywgYXN5bmMgKCkgPT4ge1xuICAgICAgLy8gUmUtaW1wb3J0IG9yIHJlLWV2YWx1YXRlIGFnZW5kYVNlcnZpY2UgdG8gZ2V0IGEgZnJlc2ggaW5zdGFuY2UgZm9yIHRoZXNlIHRlc3RzIGlmIG5lZWRlZFxuICAgICAgY29uc3QgbG9jYWxBZ2VuZGFTZXJ2aWNlTW9kdWxlID0gYXdhaXQgaW1wb3J0KCcuLi9hZ2VuZGFTZXJ2aWNlJyk7XG4gICAgICBhd2FpdCBsb2NhbEFnZW5kYVNlcnZpY2VNb2R1bGUuc3RvcEFnZW5kYSgpO1xuICAgICAgZXhwZWN0KG1vY2tBZ2VuZGFTdG9wKS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdkZWZpbmVKb2InLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCBjYWxsIGFnZW5kYS5kZWZpbmUgd2l0aCB0aGUgZ2l2ZW4gbmFtZSBhbmQgaGFuZGxlcicsICgpID0+IHtcbiAgICAgIGNvbnN0IGpvYk5hbWUgPSAndGVzdC1qb2ItZGVmaW5pdGlvbic7XG4gICAgICBjb25zdCBoYW5kbGVyID0gYXN5bmMgKGpvYjogSm9iKSA9PiB7XG4gICAgICAgIGNvbnNvbGUubG9nKCd0ZXN0IGhhbmRsZXInKTtcbiAgICAgIH07XG4gICAgICAvLyBSZS1pbXBvcnQgb3IgcmUtZXZhbHVhdGUgYWdlbmRhU2VydmljZSB0byBnZXQgYSBmcmVzaCBpbnN0YW5jZSBmb3IgdGhlc2UgdGVzdHMgaWYgbmVlZGVkXG4gICAgICBjb25zdCBsb2NhbEFnZW5kYVNlcnZpY2VNb2R1bGUgPSByZXF1aXJlKCcuLi9hZ2VuZGFTZXJ2aWNlJyk7IC8vIFVzZSByZXF1aXJlIGZvciByZS1ldmFsdWF0aW9uIGluIENKUyBjb250ZXh0IGlmIG5vdCB1c2luZyBkeW5hbWljIGltcG9ydFxuICAgICAgbG9jYWxBZ2VuZGFTZXJ2aWNlTW9kdWxlLmRlZmluZUpvYihqb2JOYW1lLCBoYW5kbGVyKTtcbiAgICAgIGV4cGVjdChtb2NrQWdlbmRhRGVmaW5lKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChqb2JOYW1lLCBoYW5kbGVyKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==