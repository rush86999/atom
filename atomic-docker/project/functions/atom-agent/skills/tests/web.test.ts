import { handleSearchWeb } from '../web';
import * as webResearchSkills from '../webResearchSkills';

jest.mock('../webResearchSkills', () => ({
    searchWeb: jest.fn(),
}));

describe('web skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('handleSearchWeb', () => {
        it('should return a list of web search results', async () => {
            const mockResults = [
                {
                    title: 'Test Result 1',
                    link: 'https://example.com/1',
                    snippet: 'This is a test result.',
                },
                {
                    title: 'Test Result 2',
                    link: 'https://example.com/2',
                    snippet: 'This is another test result.',
                },
            ];
            (webResearchSkills.searchWeb as jest.Mock).mockResolvedValue(mockResults);

            const result = await handleSearchWeb({ query: 'test' });

            expect(result).toContain('Web search results for "test" (via NLU):');
            expect(result).toContain('Test Result 1');
            expect(result).toContain('Test Result 2');
        });

        it('should return a message when there are no web search results', async () => {
            (webResearchSkills.searchWeb as jest.Mock).mockResolvedValue([]);

            const result = await handleSearchWeb({ query: 'test' });

            expect(result).toBe('No web results found for "test" (via NLU).');
        });

        it('should return an error message when the query is missing', async () => {
            const result = await handleSearchWeb({});

            expect(result).toBe('A search query is required to search the web via NLU.');
        });

        it('should return an error message when an error occurs', async () => {
            (webResearchSkills.searchWeb as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleSearchWeb({ query: 'test' });

            expect(result).toBe("Sorry, I couldn't perform the web search due to an error (NLU path).");
        });
    });
});
