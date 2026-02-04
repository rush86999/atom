import { AdvancedResearchSkill } from './advancedResearchSkill';
import { executeGraphQLQuery } from '../../atomic-docker/project/functions/atom-agent/_libs/graphqlClient';
import { OpenAI } from 'openai';

// Mock dependencies
jest.mock('../../atomic-docker/project/functions/atom-agent/_libs/graphqlClient');
jest.mock('openai');

const mockedExecuteGraphQLQuery = executeGraphQLQuery as jest.MockedFunction<typeof executeGraphQLQuery>;
const mockedOpenAI = OpenAI as jest.MockedClass<typeof OpenAI>;

// Mock the OpenAI implementation
mockedOpenAI.mockImplementation(() => ({
  chat: {
    completions: {
      create: jest.fn()
    }
  }
} as any));

describe('AdvancedResearchSkill', () => {
  let researchSkill: AdvancedResearchSkill;
  const mockOpenAIInstance = new OpenAI();

  beforeEach(() => {
    jest.clearAllMocks();
    researchSkill = new AdvancedResearchSkill('test-openai-key');

    // Reset OpenAI mock
    (mockOpenAIInstance.chat.completions.create as jest.Mock).mockReset();
  });

  describe('Initialization', () => {
    it('should initialize with provided API key', () => {
      expect(researchSkill).toBeDefined();
      expect(() => new AdvancedResearchSkill('')).toThrow('API key is required');
    });
  });

  describe('summarizeDocuments', () => {
    it('should summarize multiple documents successfully', async () => {
      const mockResponse = {
        success: true,
        data: {
          summary: 'This is a comprehensive summary of all documents',
          keyPoints: ['Point 1', 'Point 2', 'Point 3'],
          confidence: 0.95
        }
      };

      (mockOpenAIInstance.chat.completions.create as jest.Mock).mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify(mockResponse.data)
          }
        }]
      });

      const documents = [
        { id: 'doc1', content: 'Document 1 content', title: 'Test Doc 1' },
        { id: 'doc2', content: 'Document 2 content', title: 'Test Doc 2' }
      ];

      const result = await researchSkill.summarizeDocuments(documents);

      expect(result).toEqual(mockResponse);
      expect(mockOpenAIInstance.chat.completions.create).toHaveBeenCalledTimes(1);
    });

    it('should handle empty documents array', async () => {
      const result = await researchSkill.summarizeDocuments([]);

      expect(result.success).toBe(false);
      expect(result.error).toContain('No documents provided');
    });

    it('should handle OpenAI API errors', async () => {
      (mockOpenAIInstance.chat.completions.create as jest.Mock).mockRejectedValueOnce(new Error('API Error'));

      const documents = [{ id: 'doc1', content: 'test', title: 'Test' }];
      const result = await researchSkill.summarizeDocuments(documents);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Error summarizing documents');
    });
  });

  describe('askQuestion', () => {
    it('should answer questions about provided documents', async () => {
      const mockResponse = {
        success: true,
        data: {
          answer: 'Based on the documents, the answer is comprehensive and accurate',
          sources: ['doc1', 'doc3'],
          confidence: 0.88
        }
      };

      (mockOpenAIInstance.chat.completions.create as jest.Mock).mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify(mockResponse.data)
          }
        }]
      });

      const documents = [
        { id: 'doc1', content: 'Document contains key information', title: 'Info Doc' }
      ];

      const result = await researchSkill.askQuestion(
        documents,
        'What is the main topic of these documents?'
      );

      expect(result).toEqual(mockResponse);
    });

    it('should handle empty question', async () => {
      const documents = [{ id: 'doc1', content: 'test', title: 'Test' }];

      const result = await researchSkill.askQuestion(documents, '');

      expect(result.success).toBe(false);
      expect(result.error).toContain('Question is required');
    });
  });

  describe('extractKeyTerms', () => {
    it('should extract key terms and entities', async () => {
      const mockResponse = {
        success: true,
        data: {
          keyTerms: ['React', 'Node.js', 'TypeScript'],
          entities: [
            { name: 'John Doe', type: 'person' },
            { name: 'Google', type: 'organization' }
          ],
          topics: ['web development', 'programming']
        }
