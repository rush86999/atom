// Test file for llmUtilities.ts
import { analyzeTextForFollowUps } from '../llmUtilities';
import OpenAI from 'openai';
import { ExtractedFollowUpItems } from '../../../types';

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
const mockCreate = new OpenAI().chat.completions.create as jest.Mock;

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

  const sampleTextContent =
    'Meeting notes: Action Item: John to finalize report by Friday. Decision: We will proceed with Option A. Question: What is the budget for marketing?';
  const sampleContextDescription = 'Sample Meeting Notes';

  it('should return error if OPENAI_API_KEY is not set', async () => {
    delete process.env.OPENAI_API_KEY;
    // Need to re-import or re-initialize the module to pick up changed env var if it's read at module load time.
    // For simplicity in this conceptual test, we assume the check inside analyzeTextForFollowUps handles it.
    // If OpenAI client is initialized globally in llmUtilities.ts, this test would need adjustment or module reload.
    // The current llmUtilities.ts initializes OpenAI client conditionally and checks `openai` object.

    const result = await analyzeTextForFollowUps(
      sampleTextContent,
      sampleContextDescription
    );
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
    const result = await llmUtils.analyzeTextForFollowUps(
      shortText,
      'Short text context'
    );
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

    const mockLLMResponse: ExtractedFollowUpItems = {
      action_items: [
        { description: 'John to finalize report by Friday', assignee: 'John' },
      ],
      decisions: [{ description: 'Proceed with Option A' }],
      questions: [{ description: 'What is the budget for marketing?' }],
    };
    mockCreate.mockResolvedValue({
      choices: [{ message: { content: JSON.stringify(mockLLMResponse) } }],
    });

    const result = await llmUtils.analyzeTextForFollowUps(
      sampleTextContent,
      sampleContextDescription
    );

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        model: 'gpt-3.5-turbo-1106',
        response_format: { type: 'json_object' },
        messages: expect.arrayContaining([
          expect.objectContaining({ role: 'system' }),
          expect.objectContaining({
            role: 'user',
            content: expect.stringContaining(sampleTextContent),
          }),
        ]),
      })
    );
    expect(result.error).toBeUndefined();
    expect(result.extractedItems).toEqual(mockLLMResponse);
  });

  it('should return error if LLM response content is null', async () => {
    process.env.OPENAI_API_KEY = 'test-key';
    const llmUtils = await import('../llmUtilities');

    mockCreate.mockResolvedValue({
      choices: [{ message: { content: null } }],
    });
    const result = await llmUtils.analyzeTextForFollowUps(
      sampleTextContent,
      sampleContextDescription
    );
    expect(result.error).toContain(
      'LLM returned empty or null response content.'
    );
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
    const result = await llmUtils.analyzeTextForFollowUps(
      sampleTextContent,
      sampleContextDescription
    );
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
    const result = await llmUtils.analyzeTextForFollowUps(
      sampleTextContent,
      sampleContextDescription
    );
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
    (apiError as any).code = 'rate_limit_exceeded';
    mockCreate.mockRejectedValue(apiError);

    const result = await llmUtils.analyzeTextForFollowUps(
      sampleTextContent,
      sampleContextDescription
    );
    expect(result.error).toContain(
      'LLM interaction failed: OpenAI API Error: Rate limit exceeded (Code: rate_limit_exceeded)'
    );
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

    const result = await llmUtils.analyzeTextForFollowUps(
      sampleTextContent,
      sampleContextDescription
    );
    expect(result.error).toContain('LLM interaction failed: Network error');
    expect(result.extractedItems).toEqual({
      action_items: [],
      decisions: [],
      questions: [],
    });
  });
});
