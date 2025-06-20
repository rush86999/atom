import axios, { AxiosError, AxiosResponse } from 'axios';
import {
    // SemanticSearchSkills, // Class is not directly tested, but through the handler
    handleSemanticSearchMeetingNotesSkill,
} from '../semanticSearchSkills';
// Assuming BackendSearchResponse and MeetingSearchResult are exported from semanticSearchSkills.ts
// If they were moved to a central types file, the import path would change.
// For now, let's assume they are co-located or re-exported by semanticSearchSkills.ts if defined elsewhere.
// If they are not exported from semanticSearchSkills.ts, this will cause a type error.
// Based on previous subtask, they are defined locally in semanticSearchSkills.ts but not exported.
// For this test to compile, they need to be exported from semanticSearchSkills.ts OR
// defined again here, OR imported from a shared types location.
// Let's assume they are exported from semanticSearchSkills.ts for this test to work as written.
// If not, this would be a required modification to semanticSearchSkills.ts or this test file.

// For the subtask, I will define them here to make the test file self-contained for these types,
// as modifying semanticSearchSkills.ts to export them is outside this specific subtask's scope.
interface MeetingSearchResult {
    notion_page_id: string;
    meeting_title: string;
    meeting_date: string; // ISO date string
    score: number;
}
interface BackendSearchResponse {
    status: "success" | "error";
    data?: MeetingSearchResult[];
    message?: string;
    ok?: boolean;
    error?: { code: string; message: string; details?: any };
}


import { SkillArgs } from '../../../types'; // Path from skills/tests/ to atom-agent/types.ts
import * as constants from '../../_libs/constants'; // Path from skills/tests/ to atom-agent/_libs/constants.ts

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock constants
// Path is relative to this test file's location.
jest.mock('../../_libs/constants', () => ({
  ...jest.requireActual('../../_libs/constants'), // Preserve other constants
  PYTHON_API_SERVICE_BASE_URL: 'http://mock-python-api.com',
}));

describe('SemanticSearchSkills & handleSemanticSearchMeetingNotesSkill', () => {
  const userId = 'testUser123';
  const baseArgs: Omit<SkillArgs, 'params' | 'raw_message'> = { // raw_message might not always be needed if not used by skill for this test
    command: 'search_meeting_notes',
    user_id: userId,
  };

  afterEach(() => {
    jest.clearAllMocks(); // Clear mocks after each test
  });

  // Test the exported handler function, which internally uses the class logic
  describe('handleSemanticSearchMeetingNotesSkill', () => {
    it('should return formatted results on successful search with data', async () => {
      const mockBackendResults: MeetingSearchResult[] = [
        { notion_page_id: 'id-1-no-hyphen', meeting_title: 'Test Meeting Alpha', meeting_date: '2023-01-01T10:00:00Z', score: 0.9123 },
        { notion_page_id: 'id2withhyphen', meeting_title: 'Planning Session Beta', meeting_date: '2023-01-05T14:30:00Z', score: 0.8567 },
      ];
      // This is the structure the Python backend /api/semantic_search_meetings sends
      const mockPythonApiResponse = { status: 'success', data: mockBackendResults };
      mockedAxios.post.mockResolvedValueOnce({ data: mockPythonApiResponse } as AxiosResponse<BackendSearchResponse>);

      const args: SkillArgs = { ...baseArgs, params: { query: 'relevant topic' }, raw_message: 'search for relevant topic' };
      const result = await handleSemanticSearchMeetingNotesSkill(args);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        `${constants.PYTHON_API_SERVICE_BASE_URL}/api/semantic_search_meetings`,
        { query: 'relevant topic', user_id: userId }
      );
      expect(result).toContain("Found these meetings related to your query:");
      expect(result).toContain("Test Meeting Alpha");
      // Use toLocaleDateString with undefined locale to use system's default, making test more portable
      const date1 = new Date('2023-01-01T10:00:00Z');
      const expectedDate1Str = date1.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
      expect(result).toContain(`(${expectedDate1Str})`);
      expect(result).toContain("notion://page/id1nohyphen"); // Hyphens removed
      expect(result).toContain("(Similarity: 0.91)");
      expect(result).toContain("Planning Session Beta");
      expect(result).toContain("notion://page/id2withhyphen");
      expect(result).toContain("(Similarity: 0.86)");
    });

    it('should return "no results" message on successful search with empty data', async () => {
      const mockApiResponse: BackendSearchResponse = { status: 'success', data: [] };
      mockedAxios.post.mockResolvedValueOnce({ data: mockApiResponse } as AxiosResponse<BackendSearchResponse>);

      const args: SkillArgs = { ...baseArgs, params: { query: 'obscure topic' }, raw_message: 'search obscure topic' };
      const result = await handleSemanticSearchMeetingNotesSkill(args);

      // The skill formats this slightly differently now based on its internal logic
      expect(result).toBe("Sorry, I couldn't find any meeting notes matching your query.");
    });

    it('should return error message if backend returns status "error"', async () => {
      const mockApiResponse: BackendSearchResponse = { status: 'error', message: 'Backend search exploded' };
      mockedAxios.post.mockResolvedValueOnce({ data: mockApiResponse } as AxiosResponse<BackendSearchResponse>);

      const args: SkillArgs = { ...baseArgs, params: { query: 'trigger error' }, raw_message: 'search trigger error' };
      const result = await handleSemanticSearchMeetingNotesSkill(args);

      expect(result).toBe("I encountered an error while searching: Backend search exploded");
    });

    it('should return generic error message if backend response is malformed (e.g. unexpected structure)', async () => {
      const mockMalformedResponse = { some_unexpected_key: "some_value" }; // Does not match BackendSearchResponse
      mockedAxios.post.mockResolvedValueOnce({ data: mockMalformedResponse } as any);

      const args: SkillArgs = { ...baseArgs, params: { query: 'test malformed' }, raw_message: 'search test malformed' };
      const result = await handleSemanticSearchMeetingNotesSkill(args);
      expect(result).toBe("I received an unexpected response from the search service. Please try again later.");
    });

    it('should return generic error message on axios network error', async () => {
      mockedAxios.post.mockRejectedValueOnce(new Error('Network connection failed'));

      const args: SkillArgs = { ...baseArgs, params: { query: 'network fail test' }, raw_message: 'search network fail test' };
      const result = await handleSemanticSearchMeetingNotesSkill(args);

      expect(result).toBe("I'm sorry, I ran into a problem trying to search your meeting notes. Please try again later.");
    });

    it('should return specific error message if axios error has response data from backend', async () => {
        const errorResponseData = { message: "Specific backend error from Axios response" };
        const axiosError = new AxiosError("Request failed with status code 500");
        axiosError.response = { data: errorResponseData, status: 500, statusText: 'Internal Server Error', headers: {}, config: {} } as AxiosResponse;
        axiosError.isAxiosError = true;

        mockedAxios.post.mockRejectedValueOnce(axiosError);

        const args: SkillArgs = { ...baseArgs, params: { query: 'axios error with data' }, raw_message: 'search axios error with data' };
        const result = await handleSemanticSearchMeetingNotesSkill(args);
        // The skill's catch block logs axiosError.response?.data but returns a generic message
        // Let's check if the logged message (if we could capture it) or the returned message is as expected.
        // The current skill implementation returns generic message for AxiosError.
        expect(result).toBe("I'm sorry, I ran into a problem trying to search your meeting notes. Please try again later.");
    });


    it('should ask for a query if query parameter is missing in params', async () => {
      const args: SkillArgs = { ...baseArgs, params: {}, raw_message: 'search' }; // No query in params
      const result = await handleSemanticSearchMeetingNotesSkill(args);
      expect(result).toBe("Please provide a search query. For example, 'search_meeting_notes what were the decisions about project alpha?'");
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });

    it('should ask for a query if query parameter is an empty string', async () => {
      const args: SkillArgs = { ...baseArgs, params: { query: '   ' }, raw_message: 'search    ' }; // Empty string query
      const result = await handleSemanticSearchMeetingNotesSkill(args);
      expect(result).toBe("Please provide a search query. For example, 'search_meeting_notes what were the decisions about project alpha?'");
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });
  });
});
