import { searchWeb } from './webResearchSkills';
import { SearchResult } from '../types';
import got from 'got';
import * as constants from '../_libs/constants';

// Mocks
jest.mock('got');
const mockedGot = got as jest.Mocked<typeof got>;

// Mock constants for testing
jest.mock('../_libs/constants', () => ({
    ...jest.requireActual('../_libs/constants'), // Retain other constants
    ATOM_SERPAPI_API_KEY: 'test_serpapi_api_key',
    SERPAPI_BASE_URL: 'https://serpapi.com/search_mock',
}));

// Helper to override mocked constants for specific tests
const mockConstants = (apiKey?: string | null) => {
    Object.defineProperty(constants, 'ATOM_SERPAPI_API_KEY', {
        value: apiKey,
        configurable: true,
        writable: true,
    });
};

describe('Web Research Skills - searchWeb', () => {
    let consoleErrorSpy: jest.SpyInstance;
    let consoleLogSpy: jest.SpyInstance;
    const mockUserId = 'test-user-web-search';

    beforeEach(() => {
        jest.clearAllMocks();
        // Restore default mock API key before each test that might alter it
        mockConstants('test_serpapi_api_key');
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
    });

    afterEach(() => {
        consoleErrorSpy.mockRestore();
        consoleLogSpy.mockRestore();
    });

    it('should return empty array and log error if API key is missing', async () => {
        mockConstants(null); // Simulate missing API key
        const results = await searchWeb('test query', mockUserId);
        expect(results).toEqual([]);
        expect(consoleErrorSpy).toHaveBeenCalledWith("SerpApi API key is missing. Cannot perform web search.");
        expect(mockedGot.get).not.toHaveBeenCalled();
    });

    it('should return empty array for an empty query string', async () => {
        const results = await searchWeb('', mockUserId);
        expect(results).toEqual([]);
        expect(consoleLogSpy).toHaveBeenCalledWith("Search query is empty.");
        expect(mockedGot.get).not.toHaveBeenCalled();
    });

    it('should return empty array for a whitespace-only query string', async () => {
        const results = await searchWeb('   ', mockUserId);
        expect(results).toEqual([]);
        expect(consoleLogSpy).toHaveBeenCalledWith("Search query is empty.");
        expect(mockedGot.get).not.toHaveBeenCalled();
    });

    it('should call SerpApi and map organic results correctly', async () => {
        const mockSerpApiResponse = {
            organic_results: [
                { title: 'Result 1', link: 'http://link1.com', snippet: 'Snippet for 1' },
                { title: 'Result 2', link: 'http://link2.com', snippet: 'Snippet for 2' },
            ],
        };
        // Mock the behavior of .json() call as well
        mockedGot.get.mockReturnValue({ json: jest.fn().mockResolvedValue(mockSerpApiResponse) } as any);

        const results = await searchWeb('valid query', mockUserId);

        expect(mockedGot.get).toHaveBeenCalledTimes(1);
        expect(mockedGot.get).toHaveBeenCalledWith(
            expect.stringContaining(`${constants.SERPAPI_BASE_URL}?q=valid+query&api_key=${constants.ATOM_SERPAPI_API_KEY}&engine=google`),
            { responseType: 'json' }
        );
        expect(results.length).toBe(2);
        expect(results[0]).toEqual({ title: 'Result 1', link: 'http://link1.com', snippet: 'Snippet for 1' });
        expect(results[1]).toEqual({ title: 'Result 2', link: 'http://link2.com', snippet: 'Snippet for 2' });
    });

    it('should limit organic results to top 5', async () => {
        const manyResults = Array(10).fill(null).map((_, i) => ({
            title: `Title ${i+1}`, link: `http://link${i+1}.com`, snippet: `Snippet ${i+1}`
        }));
        mockedGot.get.mockReturnValue({ json: jest.fn().mockResolvedValue({ organic_results: manyResults }) } as any);

        const results = await searchWeb('query for many', mockUserId);
        expect(results.length).toBe(5);
    });

    it('should parse and return answer_box result if no organic_results', async () => {
        const mockSerpApiResponse = {
            answer_box: {
                title: 'Answer Title',
                link: 'http://answerlink.com',
                snippet: 'This is the answer snippet.',
            },
        };
        mockedGot.get.mockReturnValue({ json: jest.fn().mockResolvedValue(mockSerpApiResponse) } as any);

        const results = await searchWeb('query for answerbox', mockUserId);
        expect(results.length).toBe(1);
        expect(results[0]).toEqual({
            title: 'Answer Title',
            link: 'http://answerlink.com',
            snippet: 'This is the answer snippet.',
        });
    });

    it('should use answer_box.answer if snippet is not available', async () => {
        const mockSerpApiResponse = {
            answer_box: { title: 'Answer Title', answer: 'Direct answer content.' },
        };
        mockedGot.get.mockReturnValue({ json: jest.fn().mockResolvedValue(mockSerpApiResponse) } as any);
        const results = await searchWeb('query for answerbox answer', mockUserId);
        expect(results[0].snippet).toBe('Direct answer content.');
    });


    it('should return empty array if SerpApi returns no organic_results or answer_box', async () => {
        mockedGot.get.mockReturnValue({ json: jest.fn().mockResolvedValue({}) } as any); // Empty response
        const results = await searchWeb('empty response query', mockUserId);
        expect(results).toEqual([]);
        expect(consoleLogSpy).toHaveBeenCalledWith(expect.stringContaining('No organic results or answer box found'));
    });

    it('should return empty array and log error on SerpApi API error (e.g. JSON error in body)', async () => {
        // This test simulates when the .json() call itself might fail or the structure is unexpected before organic_results
        const serpApiErrorResponse = { error: "Your account is not active or you ran out of credits." };
        mockedGot.get.mockReturnValue({ json: jest.fn().mockResolvedValue(serpApiErrorResponse) } as any);

        const results = await searchWeb('query causing api error', mockUserId);
        expect(results).toEqual([]);
        expect(consoleLogSpy).toHaveBeenCalledWith(expect.stringContaining('No organic results or answer box found for query: "query causing api error"'));
    });

    it('should return empty array and log error on HTTP error from got', async () => {
        const httpError = new Error("Simulated HTTP 500 error");
        (httpError as any).response = { body: "Server Error Details From SerpApi" };
        mockedGot.get.mockRejectedValue(httpError);

        const results = await searchWeb('query causing http error', mockUserId);
        expect(results).toEqual([]);
        expect(consoleErrorSpy).toHaveBeenCalledWith(
            expect.stringContaining('Error performing web search with SerpApi:'),
            "Server Error Details From SerpApi"
        );
    });

    it('should log userId if provided', async () => {
        mockedGot.get.mockReturnValue({ json: jest.fn().mockResolvedValue({}) } as any);
        await searchWeb('logging query', mockUserId);
        expect(consoleLogSpy).toHaveBeenCalledWith(expect.stringContaining(`(userId: ${mockUserId})`));
    });
});
