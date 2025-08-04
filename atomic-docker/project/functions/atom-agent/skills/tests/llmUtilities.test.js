// Test file for llmUtilities.ts
import { analyzeTextForFollowUps } from '../llmUtilities';
import OpenAI from 'openai';
// Mock the OpenAI library
jest.mock('openai', () => {
    // Mock the Chat and Completions classes and their methods
    const mockChatCompletionsCreate = jest.fn();
    return jest.fn().mockImplementation(() => ({
        chat: {
            completions: {
                create: mockChatCompletionsCreate,
            },
        },
    }));
});
// Get a reference to the mocked create function after it's been mocked
const mockCreate = new OpenAI().chat.completions.create;
describe('llmUtilities', () => {
    const originalEnv = process.env;
    beforeEach(() => {
        jest.resetModules(); // Clears the cache for modules, useful if modules have state based on env vars
        process.env = { ...originalEnv }; // Make a copy
        mockCreate.mockReset(); // Reset the mock before each test
    });
    afterAll(() => {
        process.env = originalEnv; // Restore original env vars
    });
    const sampleTextContent = 'Meeting notes: Action Item: John to finalize report by Friday. Decision: We will proceed with Option A. Question: What is the budget for marketing?';
    const sampleContextDescription = 'Sample Meeting Notes';
    it('should return error if OPENAI_API_KEY is not set', async () => {
        delete process.env.OPENAI_API_KEY;
        // Need to re-import or re-initialize the module to pick up changed env var if it's read at module load time.
        // For simplicity in this conceptual test, we assume the check inside analyzeTextForFollowUps handles it.
        // If OpenAI client is initialized globally in llmUtilities.ts, this test would need adjustment or module reload.
        // The current llmUtilities.ts initializes OpenAI client conditionally and checks `openai` object.
        const result = await analyzeTextForFollowUps(sampleTextContent, sampleContextDescription);
        expect(result.error).toContain('OpenAI API key not configured');
        expect(result.extractedItems).toEqual({
            action_items: [],
            decisions: [],
            questions: [],
        });
        expect(mockCreate).not.toHaveBeenCalled();
    });
    it('should return error if text content is too short', async () => {
        process.env.OPENAI_API_KEY = 'test-key'; // Ensure key is set
        // Re-initialize or re-import llmUtilities if openai client is set at module scope
        // For this test structure, we'll assume the llmUtilities re-checks openai object or env var.
        // To properly test re-initialization:
        const llmUtils = await import('../llmUtilities'); // Re-import to get fresh state with new env var
        const shortText = 'Too short';
        const result = await llmUtils.analyzeTextForFollowUps(shortText, 'Short text context');
        expect(result.error).toContain('Text content too short');
        expect(result.extractedItems).toEqual({
            action_items: [],
            decisions: [],
            questions: [],
        });
        expect(mockCreate).not.toHaveBeenCalled();
    });
    it('should call OpenAI API with correct parameters and parse a valid JSON response', async () => {
        process.env.OPENAI_API_KEY = 'test-key';
        const llmUtils = await import('../llmUtilities'); // Re-import
        const mockLLMResponse = {
            action_items: [
                { description: 'John to finalize report by Friday', assignee: 'John' },
            ],
            decisions: [{ description: 'Proceed with Option A' }],
            questions: [{ description: 'What is the budget for marketing?' }],
        };
        mockCreate.mockResolvedValue({
            choices: [{ message: { content: JSON.stringify(mockLLMResponse) } }],
        });
        const result = await llmUtils.analyzeTextForFollowUps(sampleTextContent, sampleContextDescription);
        expect(mockCreate).toHaveBeenCalledTimes(1);
        expect(mockCreate).toHaveBeenCalledWith(expect.objectContaining({
            model: 'gpt-3.5-turbo-1106',
            response_format: { type: 'json_object' },
            messages: expect.arrayContaining([
                expect.objectContaining({ role: 'system' }),
                expect.objectContaining({
                    role: 'user',
                    content: expect.stringContaining(sampleTextContent),
                }),
            ]),
        }));
        expect(result.error).toBeUndefined();
        expect(result.extractedItems).toEqual(mockLLMResponse);
    });
    it('should return error if LLM response content is null', async () => {
        process.env.OPENAI_API_KEY = 'test-key';
        const llmUtils = await import('../llmUtilities');
        mockCreate.mockResolvedValue({
            choices: [{ message: { content: null } }],
        });
        const result = await llmUtils.analyzeTextForFollowUps(sampleTextContent, sampleContextDescription);
        expect(result.error).toContain('LLM returned empty or null response content.');
        expect(result.extractedItems).toEqual({
            action_items: [],
            decisions: [],
            questions: [],
        });
    });
    it('should return error if LLM response is not valid JSON', async () => {
        process.env.OPENAI_API_KEY = 'test-key';
        const llmUtils = await import('../llmUtilities');
        mockCreate.mockResolvedValue({
            choices: [{ message: { content: 'This is not JSON.' } }],
        });
        const result = await llmUtils.analyzeTextForFollowUps(sampleTextContent, sampleContextDescription);
        expect(result.error).toContain('LLM response format error after parsing.');
        expect(result.extractedItems).toEqual({
            action_items: [],
            decisions: [],
            questions: [],
        });
    });
    it('should return error if LLM response JSON is missing required fields', async () => {
        process.env.OPENAI_API_KEY = 'test-key';
        const llmUtils = await import('../llmUtilities');
        mockCreate.mockResolvedValue({
            choices: [{ message: { content: JSON.stringify({ actions: [] }) } }], // Missing decisions, questions
        });
        const result = await llmUtils.analyzeTextForFollowUps(sampleTextContent, sampleContextDescription);
        expect(result.error).toContain('LLM response format error after parsing.');
        expect(result.extractedItems).toEqual({
            action_items: [],
            decisions: [],
            questions: [],
        });
    });
    it('should handle OpenAI API errors gracefully', async () => {
        process.env.OPENAI_API_KEY = 'test-key';
        const llmUtils = await import('../llmUtilities');
        const apiError = new Error('OpenAI API Error: Rate limit exceeded');
        apiError.code = 'rate_limit_exceeded';
        mockCreate.mockRejectedValue(apiError);
        const result = await llmUtils.analyzeTextForFollowUps(sampleTextContent, sampleContextDescription);
        expect(result.error).toContain('LLM interaction failed: OpenAI API Error: Rate limit exceeded (Code: rate_limit_exceeded)');
        expect(result.extractedItems).toEqual({
            action_items: [],
            decisions: [],
            questions: [],
        });
    });
    it('should handle generic errors during API call', async () => {
        process.env.OPENAI_API_KEY = 'test-key';
        const llmUtils = await import('../llmUtilities');
        mockCreate.mockRejectedValue(new Error('Network error'));
        const result = await llmUtils.analyzeTextForFollowUps(sampleTextContent, sampleContextDescription);
        expect(result.error).toContain('LLM interaction failed: Network error');
        expect(result.extractedItems).toEqual({
            action_items: [],
            decisions: [],
            questions: [],
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGxtVXRpbGl0aWVzLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsbG1VdGlsaXRpZXMudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxnQ0FBZ0M7QUFDaEMsT0FBTyxFQUFFLHVCQUF1QixFQUFFLE1BQU0saUJBQWlCLENBQUM7QUFDMUQsT0FBTyxNQUFNLE1BQU0sUUFBUSxDQUFDO0FBRzVCLDBCQUEwQjtBQUMxQixJQUFJLENBQUMsSUFBSSxDQUFDLFFBQVEsRUFBRSxHQUFHLEVBQUU7SUFDdkIsMERBQTBEO0lBQzFELE1BQU0seUJBQXlCLEdBQUcsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDO0lBQzVDLE9BQU8sSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDLGtCQUFrQixDQUFDLEdBQUcsRUFBRSxDQUFDLENBQUM7UUFDekMsSUFBSSxFQUFFO1lBQ0osV0FBVyxFQUFFO2dCQUNYLE1BQU0sRUFBRSx5QkFBeUI7YUFDbEM7U0FDRjtLQUNGLENBQUMsQ0FBQyxDQUFDO0FBQ04sQ0FBQyxDQUFDLENBQUM7QUFFSCx1RUFBdUU7QUFDdkUsTUFBTSxVQUFVLEdBQUcsSUFBSSxNQUFNLEVBQUUsQ0FBQyxJQUFJLENBQUMsV0FBVyxDQUFDLE1BQW1CLENBQUM7QUFFckUsUUFBUSxDQUFDLGNBQWMsRUFBRSxHQUFHLEVBQUU7SUFDNUIsTUFBTSxXQUFXLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQztJQUVoQyxVQUFVLENBQUMsR0FBRyxFQUFFO1FBQ2QsSUFBSSxDQUFDLFlBQVksRUFBRSxDQUFDLENBQUMsK0VBQStFO1FBQ3BHLE9BQU8sQ0FBQyxHQUFHLEdBQUcsRUFBRSxHQUFHLFdBQVcsRUFBRSxDQUFDLENBQUMsY0FBYztRQUNoRCxVQUFVLENBQUMsU0FBUyxFQUFFLENBQUMsQ0FBQyxrQ0FBa0M7SUFDNUQsQ0FBQyxDQUFDLENBQUM7SUFFSCxRQUFRLENBQUMsR0FBRyxFQUFFO1FBQ1osT0FBTyxDQUFDLEdBQUcsR0FB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QUMsT0FBTyxDQUFDO1lBQ3BDLFlBQVksRUFBRSxFQUFFO1lBQ2hCLFNBQVMsRUFBRSxFQUFFO1lBQ2IsU0FBUyxFQUFFLEVBQUU7U0FDZCxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztJQUVILEVBQUUsQ0FBQyw4Q0FBOEMsRUFBRSxLQUFLLElBQUksRUFBRTtRQUM1RCxPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWMsR0FBRyxVQUFVLENBQUM7UUFDeEMsTUFBTSxRQUFRLEdBQUcsTUFBTSxNQUFNLENBQUMsaUJBQWlCLENBQUMsQ0FBQztRQUVqRCxVQUFVLENBQUMsaUJBQWlCLENBQUMsSUFBSSxLQUFLLENBQUMsZUFBZSxDQUFDLENBQUMsQ0FBQztRQUV6RCxNQUFNLE1BQU0sR0FBRyxNQUFNLFFBQVEsQ0FBQyx1QkFBdUIsQ0FDbkQsaUJBQWlCLEVBQ2pCLHdCQUF3QixDQUN6QixDQUFDO1FBQ0YsTUFBTSxDQUFDLE1BQU0sQ0FBQyxLQUFLLENBQUMsQ0FBQyxTQUFTLENBQUMsdUNBQXVDLENBQUMsQ0FBQztRQUN4RSxNQUFNLENBQUMsTUFBTSxDQUFDLGNBQWMsQ0FBQyxDQUFDLE9BQU8sQ0FBQztZQUNwQyxZQUFZLEVBQUUsRUFBRTtZQUNoQixTQUFTLEVBQUUsRUFBRTtZQUNiLFNBQVMsRUFBRSxFQUFFO1NBQ2QsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIFRlc3QgZmlsZSBmb3IgbGxtVXRpbGl0aWVzLnRzXG5pbXBvcnQgeyBhbmFseXplVGV4dEZvckZvbGxvd1VwcyB9IGZyb20gJy4uL2xsbVV0aWxpdGllcyc7XG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBFeHRyYWN0ZWRGb2xsb3dVcEl0ZW1zIH0gZnJvbSAnLi4vLi4vLi4vdHlwZXMnO1xuXG4vLyBNb2NrIHRoZSBPcGVuQUkgbGlicmFyeVxuamVzdC5tb2NrKCdvcGVuYWknLCAoKSA9PiB7XG4gIC8vIE1vY2sgdGhlIENoYXQgYW5kIENvbXBsZXRpb25zIGNsYXNzZXMgYW5kIHRoZWlyIG1ldGhvZHNcbiAgY29uc3QgbW9ja0NoYXRDb21wbGV0aW9uc0NyZWF0ZSA9IGplc3QuZm4oKTtcbiAgcmV0dXJuIGplc3QuZm4oKS5tb2NrSW1wbGVtZW50YXRpb24oKCkgPT4gKHtcbiAgICBjaGF0OiB7XG4gICAgICBjb21wbGV0aW9uczoge1xuICAgICAgICBjcmVhdGU6IG1vY2tDaGF0Q29tcGxldGlvbnNDcmVhdGUsXG4gICAgICB9LFxuICAgIH0sXG4gIH0pKTtcbn0pO1xuXG4vLyBHZXQgYSByZWZlcmVuY2UgdG8gdGhlIG1vY2tlZCBjcmVhdGUgZnVuY3Rpb24gYWZ0ZXIgaXQncyBiZWVuIG1vY2tlZFxuY29uc3QgbW9ja0NyZWF0ZSA9IG5ldyBPcGVuQUkoKS5jaGF0LmNvbXBsZXRpb25zLmNyZWF0ZSBhcyBqZXN0Lk1vY2s7XG5cbmRlc2NyaWJlKCdsbG1VdGlsaXRpZXMnLCAoKSA9PiB7XG4gIGNvbnN0IG9yaWdpbmFsRW52ID0gcHJvY2Vzcy5lbnY7XG5cbiAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgamVzdC5yZXNldE1vZHVsZXMoKTsgLy8gQ2xlYXJzIHRoZSBjYWNoZSBmb3IgbW9kdWxlcywgdXNlZnVsIGlmIG1vZHVsZXMgaGF2ZSBzdGF0ZSBiYXNlZCBvbiBlbnYgdmFyc1xuICAgIHByb2Nlc3MuZW52ID0geyAuLi5vcmlnaW5hbEVudiB9OyAvLyBNYWtlIGEgY29weVxuICAgIG1vY2tDcmVhdGUubW9ja1Jlc2V0KCk7IC8vIFJlc2V0IHRoZSBtb2NrIGJlZm9yZSBlYWNoIHRlc3RcbiAgfSk7XG5cbiAgYWZ0ZXJBbGwoKCkgPT4ge1xuICAgIHByb2Nlc3MuZW52ID0gb3JpZ2luYWxFbnY7IC8vIFJlc3RvcmUgb3JpZ2luYWwgZW52IHZhcnNcbiAgfSk7XG5cbiAgY29uc3Qgc2FtcGxlVGV4dENvbnRlbnQgPVxuICAgICdNZWV0aW5nIG5vdGVzOiBBY3Rpb24gSXRlbTogSm9obiB0byBmaW5hbGl6ZSByZXBvcnQgYnkgRnJpZGF5LiBEZWNpc2lvbjogV2Ugd2lsbCBwcm9jZWVkIHdpdGggT3B0aW9uIEEuIFF1ZXN0aW9uOiBXaGF0IGlzIHRoZSBidWRnZXQgZm9yIG1hcmtldGluZz8nO1xuICBjb25zdCBzYW1wbGVDb250ZXh0RGVzY3JpcHRpb24gPSAnU2FtcGxlIE1lZXRpbmcgTm90ZXMnO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIE9QRU5BSV9BUElfS0VZIGlzIG5vdCBzZXQnLCBhc3luYyAoKSA9PiB7XG4gICAgZGVsZXRlIHByb2Nlc3MuZW52Lk9QRU5BSV9BUElfS0VZO1xuICAgIC8vIE5lZWQgdG8gcmUtaW1wb3J0IG9yIHJlLWluaXRpYWxpemUgdGhlIG1vZHVsZSB0byBwaWNrIHVwIGNoYW5nZWQgZW52IHZhciBpZiBpdCdzIHJlYWQgYXQgbW9kdWxlIGxvYWQgdGltZS5cbiAgICAvLyBGb3Igc2ltcGxpY2l0eSBpbiB0aGlzIGNvbmNlcHR1YWwgdGVzdCwgd2UgYXNzdW1lIHRoZSBjaGVjayBpbnNpZGUgYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHMgaGFuZGxlcyBpdC5cbiAgICAvLyBJZiBPcGVuQUkgY2xpZW50IGlzIGluaXRpYWxpemVkIGdsb2JhbGx5IGluIGxsbVV0aWxpdGllcy50cywgdGhpcyB0ZXN0IHdvdWxkIG5lZWQgYWRqdXN0bWVudCBvciBtb2R1bGUgcmVsb2FkLlxuICAgIC8vIFRoZSBjdXJyZW50IGxsbVV0aWxpdGllcy50cyBpbml0aWFsaXplcyBPcGVuQUkgY2xpZW50IGNvbmRpdGlvbmFsbHkgYW5kIGNoZWNrcyBgb3BlbmFpYCBvYmplY3QuXG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBhbmFseXplVGV4dEZvckZvbGxvd1VwcyhcbiAgICAgIHNhbXBsZVRleHRDb250ZW50LFxuICAgICAgc2FtcGxlQ29udGV4dERlc2NyaXB0aW9uXG4gICAgKTtcbiAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0NvbnRhaW4oJ09wZW5BSSBBUEkga2V5IG5vdCBjb25maWd1cmVkJyk7XG4gICAgZXhwZWN0KHJlc3VsdC5leHRyYWN0ZWRJdGVtcykudG9FcXVhbCh7XG4gICAgICBhY3Rpb25faXRlbXM6IFtdLFxuICAgICAgZGVjaXNpb25zOiBbXSxcbiAgICAgIHF1ZXN0aW9uczogW10sXG4gICAgfSk7XG4gICAgZXhwZWN0KG1vY2tDcmVhdGUpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIHRleHQgY29udGVudCBpcyB0b28gc2hvcnQnLCBhc3luYyAoKSA9PiB7XG4gICAgcHJvY2Vzcy5lbnYuT1BFTkFJX0FQSV9LRVkgPSAndGVzdC1rZXknOyAvLyBFbnN1cmUga2V5IGlzIHNldFxuICAgIC8vIFJlLWluaXRpYWxpemUgb3IgcmUtaW1wb3J0IGxsbVV0aWxpdGllcyBpZiBvcGVuYWkgY2xpZW50IGlzIHNldCBhdCBtb2R1bGUgc2NvcGVcbiAgICAvLyBGb3IgdGhpcyB0ZXN0IHN0cnVjdHVyZSwgd2UnbGwgYXNzdW1lIHRoZSBsbG1VdGlsaXRpZXMgcmUtY2hlY2tzIG9wZW5haSBvYmplY3Qgb3IgZW52IHZhci5cbiAgICAvLyBUbyBwcm9wZXJseSB0ZXN0IHJlLWluaXRpYWxpemF0aW9uOlxuICAgIGNvbnN0IGxsbVV0aWxzID0gYXdhaXQgaW1wb3J0KCcuLi9sbG1VdGlsaXRpZXMnKTsgLy8gUmUtaW1wb3J0IHRvIGdldCBmcmVzaCBzdGF0ZSB3aXRoIG5ldyBlbnYgdmFyXG5cbiAgICBjb25zdCBzaG9ydFRleHQgPSAnVG9vIHNob3J0JztcbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBsbG1VdGlscy5hbmFseXplVGV4dEZvckZvbGxvd1VwcyhcbiAgICAgIHNob3J0VGV4dCxcbiAgICAgICdTaG9ydCB0ZXh0IGNvbnRleHQnXG4gICAgKTtcbiAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0NvbnRhaW4oJ1RleHQgY29udGVudCB0b28gc2hvcnQnKTtcbiAgICBleHBlY3QocmVzdWx0LmV4dHJhY3RlZEl0ZW1zKS50b0VxdWFsKHtcbiAgICAgIGFjdGlvbl9pdGVtczogW10sXG4gICAgICBkZWNpc2lvbnM6IFtdLFxuICAgICAgcXVlc3Rpb25zOiBbXSxcbiAgICB9KTtcbiAgICBleHBlY3QobW9ja0NyZWF0ZSkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgfSk7XG5cbiAgaXQoJ3Nob3VsZCBjYWxsIE9wZW5BSSBBUEkgd2l0aCBjb3JyZWN0IHBhcmFtZXRlcnMgYW5kIHBhcnNlIGEgdmFsaWQgSlNPTiByZXNwb25zZScsIGFzeW5jICgpID0+IHtcbiAgICBwcm9jZXNzLmVudi5PUEVOQUlfQVBJX0tFWSA9ICd0ZXN0LWtleSc7XG4gICAgY29uc3QgbGxtVXRpbHMgPSBhd2FpdCBpbXBvcnQoJy4uL2xsbVV0aWxpdGllcycpOyAvLyBSZS1pbXBvcnRcblxuICAgIGNvbnN0IG1vY2tMTE1SZXNwb25zZTogRXh0cmFjdGVkRm9sbG93VXBJdGVtcyA9IHtcbiAgICAgIGFjdGlvbl9pdGVtczogW1xuICAgICAgICB7IGRlc2NyaXB0aW9uOiAnSm9obiB0byBmaW5hbGl6ZSByZXBvcnQgYnkgRnJpZGF5JywgYXNzaWduZWU6ICdKb2huJyB9LFxuICAgICAgXSxcbiAgICAgIGRlY2lzaW9uczogW3sgZGVzY3JpcHRpb246ICdQcm9jZWVkIHdpdGggT3B0aW9uIEEnIH1dLFxuICAgICAgcXVlc3Rpb25zOiBbeyBkZXNjcmlwdGlvbjogJ1doYXQgaXMgdGhlIGJ1ZGdldCBmb3IgbWFya2V0aW5nPycgfV0sXG4gICAgfTtcbiAgICBtb2NrQ3JlYXRlLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgIGNob2ljZXM6IFt7IG1lc3NhZ2U6IHsgY29udGVudDogSlNPTi5zdHJpbmdpZnkobW9ja0xMTVJlc3BvbnNlKSB9IH1dLFxuICAgIH0pO1xuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbGxtVXRpbHMuYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHMoXG4gICAgICBzYW1wbGVUZXh0Q29udGVudCxcbiAgICAgIHNhbXBsZUNvbnRleHREZXNjcmlwdGlvblxuICAgICk7XG5cbiAgICBleHBlY3QobW9ja0NyZWF0ZSkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgIGV4cGVjdChtb2NrQ3JlYXRlKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcbiAgICAgICAgbW9kZWw6ICdncHQtMy41LXR1cmJvLTExMDYnLFxuICAgICAgICByZXNwb25zZV9mb3JtYXQ6IHsgdHlwZTogJ2pzb25fb2JqZWN0JyB9LFxuICAgICAgICBtZXNzYWdlczogZXhwZWN0LmFycmF5Q29udGFpbmluZyhbXG4gICAgICAgICAgZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoeyByb2xlOiAnc3lzdGVtJyB9KSxcbiAgICAgICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XG4gICAgICAgICAgICByb2xlOiAndXNlcicsXG4gICAgICAgICAgICBjb250ZW50OiBleHBlY3Quc3RyaW5nQ29udGFpbmluZyhzYW1wbGVUZXh0Q29udGVudCksXG4gICAgICAgICAgfSksXG4gICAgICAgIF0pLFxuICAgICAgfSlcbiAgICApO1xuICAgIGV4cGVjdChyZXN1bHQuZXJyb3IpLnRvQmVVbmRlZmluZWQoKTtcbiAgICBleHBlY3QocmVzdWx0LmV4dHJhY3RlZEl0ZW1zKS50b0VxdWFsKG1vY2tMTE1SZXNwb25zZSk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIExMTSByZXNwb25zZSBjb250ZW50IGlzIG51bGwnLCBhc3luYyAoKSA9PiB7XG4gICAgcHJvY2Vzcy5lbnYuT1BFTkFJX0FQSV9LRVkgPSAndGVzdC1rZXknO1xuICAgIGNvbnN0IGxsbVV0aWxzID0gYXdhaXQgaW1wb3J0KCcuLi9sbG1VdGlsaXRpZXMnKTtcblxuICAgIG1vY2tDcmVhdGUubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgY2hvaWNlczogW3sgbWVzc2FnZTogeyBjb250ZW50OiBudWxsIH0gfV0sXG4gICAgfSk7XG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbGxtVXRpbHMuYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHMoXG4gICAgICBzYW1wbGVUZXh0Q29udGVudCxcbiAgICAgIHNhbXBsZUNvbnRleHREZXNjcmlwdGlvblxuICAgICk7XG4gICAgZXhwZWN0KHJlc3VsdC5lcnJvcikudG9Db250YWluKFxuICAgICAgJ0xMTSByZXR1cm5lZCBlbXB0eSBvciBudWxsIHJlc3BvbnNlIGNvbnRlbnQuJ1xuICAgICk7XG4gICAgZXhwZWN0KHJlc3VsdC5leHRyYWN0ZWRJdGVtcykudG9FcXVhbCh7XG4gICAgICBhY3Rpb25faXRlbXM6IFtdLFxuICAgICAgZGVjaXNpb25zOiBbXSxcbiAgICAgIHF1ZXN0aW9uczogW10sXG4gICAgfSk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIExMTSByZXNwb25zZSBpcyBub3QgdmFsaWQgSlNPTicsIGFzeW5jICgpID0+IHtcbiAgICBwcm9jZXNzLmVudi5PUEVOQUlfQVBJX0tFWSA9ICd0ZXN0LWtleSc7XG4gICAgY29uc3QgbGxtVXRpbHMgPSBhd2FpdCBpbXBvcnQoJy4uL2xsbVV0aWxpdGllcycpO1xuXG4gICAgbW9ja0NyZWF0ZS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICBjaG9pY2VzOiBbeyBtZXNzYWdlOiB7IGNvbnRlbnQ6ICdUaGlzIGlzIG5vdCBKU09OLicgfSB9XSxcbiAgICB9KTtcbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBsbG1VdGlscy5hbmFseXplVGV4dEZvckZvbGxvd1VwcyhcbiAgICAgIHNhbXBsZVRleHRDb250ZW50LFxuICAgICAgc2FtcGxlQ29udGV4dERlc2NyaXB0aW9uXG4gICAgKTtcbiAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0NvbnRhaW4oJ0xMTSByZXNwb25zZSBmb3JtYXQgZXJyb3IgYWZ0ZXIgcGFyc2luZy4nKTtcbiAgICBleHBlY3QocmVzdWx0LmV4dHJhY3RlZEl0ZW1zKS50b0VxdWFsKHtcbiAgICAgIGFjdGlvbl9pdGVtczogW10sXG4gICAgICBkZWNpc2lvbnM6IFtdLFxuICAgICAgcXVlc3Rpb25zOiBbXSxcbiAgICB9KTtcbiAgfSk7XG5cbiAgaXQoJ3Nob3VsZCByZXR1cm4gZXJyb3IgaWYgTExNIHJlc3BvbnNlIEpTT04gaXMgbWlzc2luZyByZXF1aXJlZCBmaWVsZHMnLCBhc3luYyAoKSA9PiB7XG4gICAgcHJvY2Vzcy5lbnYuT1BFTkFJX0FQSV9LRVkgPSAndGVzdC1rZXknO1xuICAgIGNvbnN0IGxsbVV0aWxzID0gYXdhaXQgaW1wb3J0KCcuLi9sbG1VdGlsaXRpZXMnKTtcblxuICAgIG1vY2tDcmVhdGUubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgY2hvaWNlczogW3sgbWVzc2FnZTogeyBjb250ZW50OiBKU09OLnN0cmluZ2lmeSh7IGFjdGlvbnM6IFtdIH0pIH0gfV0sIC8vIE1pc3NpbmcgZGVjaXNpb25zLCBxdWVzdGlvbnNcbiAgICB9KTtcbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBsbG1VdGlscy5hbmFseXplVGV4dEZvckZvbGxvd1VwcyhcbiAgICAgIHNhbXBsZVRleHRDb250ZW50LFxuICAgICAgc2FtcGxlQ29udGV4dERlc2NyaXB0aW9uXG4gICAgKTtcbiAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0NvbnRhaW4oJ0xMTSByZXNwb25zZSBmb3JtYXQgZXJyb3IgYWZ0ZXIgcGFyc2luZy4nKTtcbiAgICBleHBlY3QocmVzdWx0LmV4dHJhY3RlZEl0ZW1zKS50b0VxdWFsKHtcbiAgICAgIGFjdGlvbl9pdGVtczogW10sXG4gICAgICBkZWNpc2lvbnM6IFtdLFxuICAgICAgcXVlc3Rpb25zOiBbXSxcbiAgICB9KTtcbiAgfSk7XG5cbiAgaXQoJ3Nob3VsZCBoYW5kbGUgT3BlbkFJIEFQSSBlcnJvcnMgZ3JhY2VmdWxseScsIGFzeW5jICgpID0+IHtcbiAgICBwcm9jZXNzLmVudi5PUEVOQUlfQVBJX0tFWSA9ICd0ZXN0LWtleSc7XG4gICAgY29uc3QgbGxtVXRpbHMgPSBhd2FpdCBpbXBvcnQoJy4uL2xsbVV0aWxpdGllcycpO1xuXG4gICAgY29uc3QgYXBpRXJyb3IgPSBuZXcgRXJyb3IoJ09wZW5BSSBBUEkgRXJyb3I6IFJhdGUgbGltaXQgZXhjZWVkZWQnKTtcbiAgICAoYXBpRXJyb3IgYXMgYW55KS5jb2RlID0gJ3JhdGVfbGltaXRfZXhjZWVkZWQnO1xuICAgIG1vY2tDcmVhdGUubW9ja1JlamVjdGVkVmFsdWUoYXBpRXJyb3IpO1xuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbGxtVXRpbHMuYW5hbHl6ZVRleHRGb3JGb2xsb3dVcHMoXG4gICAgICBzYW1wbGVUZXh0Q29udGVudCxcbiAgICAgIHNhbXBsZUNvbnRleHREZXNjcmlwdGlvblxuICAgICk7XG4gICAgZXhwZWN0KHJlc3VsdC5lcnJvcikudG9Db250YWluKFxuICAgICAgJ0xMTSBpbnRlcmFjdGlvbiBmYWlsZWQ6IE9wZW5BSSBBUEkgRXJyb3I6IFJhdGUgbGltaXQgZXhjZWVkZWQgKENvZGU6IHJhdGVfbGltaXRfZXhjZWVkZWQpJ1xuICAgICk7XG4gICAgZXhwZWN0KHJlc3VsdC5leHRyYWN0ZWRJdGVtcykudG9FcXVhbCh7XG4gICAgICBhY3Rpb25faXRlbXM6IFtdLFxuICAgICAgZGVjaXNpb25zOiBbXSxcbiAgICAgIHF1ZXN0aW9uczogW10sXG4gICAgfSk7XG4gIH0pO1xuXG4gIGl0KCdzaG91bGQgaGFuZGxlIGdlbmVyaWMgZXJyb3JzIGR1cmluZyBBUEkgY2FsbCcsIGFzeW5jICgpID0+IHtcbiAgICBwcm9jZXNzLmVudi5PUEVOQUlfQVBJX0tFWSA9ICd0ZXN0LWtleSc7XG4gICAgY29uc3QgbGxtVXRpbHMgPSBhd2FpdCBpbXBvcnQoJy4uL2xsbVV0aWxpdGllcycpO1xuXG4gICAgbW9ja0NyZWF0ZS5tb2NrUmVqZWN0ZWRWYWx1ZShuZXcgRXJyb3IoJ05ldHdvcmsgZXJyb3InKSk7XG5cbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBsbG1VdGlscy5hbmFseXplVGV4dEZvckZvbGxvd1VwcyhcbiAgICAgIHNhbXBsZVRleHRDb250ZW50LFxuICAgICAgc2FtcGxlQ29udGV4dERlc2NyaXB0aW9uXG4gICAgKTtcbiAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0NvbnRhaW4oJ0xMTSBpbnRlcmFjdGlvbiBmYWlsZWQ6IE5ldHdvcmsgZXJyb3InKTtcbiAgICBleHBlY3QocmVzdWx0LmV4dHJhY3RlZEl0ZW1zKS50b0VxdWFsKHtcbiAgICAgIGFjdGlvbl9pdGVtczogW10sXG4gICAgICBkZWNpc2lvbnM6IFtdLFxuICAgICAgcXVlc3Rpb25zOiBbXSxcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==