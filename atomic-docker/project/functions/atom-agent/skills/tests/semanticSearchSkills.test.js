import axios, { AxiosError } from 'axios';
import { 
// SemanticSearchSkills, // Class is not directly tested, but through the handler
handleSemanticSearchMeetingNotesSkill, } from '../semanticSearchSkills';
import * as constants from '../../_libs/constants'; // Path from skills/tests/ to atom-agent/_libs/constants.ts
// Mock axios
jest.mock('axios');
const mockedAxios = axios;
// Mock constants
// Path is relative to this test file's location.
jest.mock('../../_libs/constants', () => ({
    ...jest.requireActual('../../_libs/constants'), // Preserve other constants
    PYTHON_API_SERVICE_BASE_URL: 'http://mock-python-api.com',
}));
describe('SemanticSearchSkills & handleSemanticSearchMeetingNotesSkill', () => {
    const userId = 'testUser123';
    const baseArgs = {
        // raw_message might not always be needed if not used by skill for this test
        command: 'search_meeting_notes',
        user_id: userId,
    };
    afterEach(() => {
        jest.clearAllMocks(); // Clear mocks after each test
    });
    // Test the exported handler function, which internally uses the class logic
    describe('handleSemanticSearchMeetingNotesSkill', () => {
        it('should return formatted results on successful search with data', async () => {
            const mockBackendResults = [
                {
                    notion_page_id: 'id-1-no-hyphen',
                    meeting_title: 'Test Meeting Alpha',
                    meeting_date: '2023-01-01T10:00:00Z',
                    score: 0.9123,
                },
                {
                    notion_page_id: 'id2withhyphen',
                    meeting_title: 'Planning Session Beta',
                    meeting_date: '2023-01-05T14:30:00Z',
                    score: 0.8567,
                },
            ];
            // This is the structure the Python backend /api/semantic_search_meetings sends
            const mockPythonApiResponse = {
                status: 'success',
                data: mockBackendResults,
            };
            mockedAxios.post.mockResolvedValueOnce({
                data: mockPythonApiResponse,
            });
            const args = {
                ...baseArgs,
                params: { query: 'relevant topic' },
                raw_message: 'search for relevant topic',
            };
            const result = await handleSemanticSearchMeetingNotesSkill(args);
            expect(mockedAxios.post).toHaveBeenCalledWith(`${constants.PYTHON_API_SERVICE_BASE_URL}/api/semantic_search_meetings`, { query: 'relevant topic', user_id: userId });
            expect(result).toContain('Found these meetings related to your query:');
            expect(result).toContain('Test Meeting Alpha');
            // Use toLocaleDateString with undefined locale to use system's default, making test more portable
            const date1 = new Date('2023-01-01T10:00:00Z');
            const expectedDate1Str = date1.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
            });
            expect(result).toContain(`(${expectedDate1Str})`);
            expect(result).toContain('notion://page/id1nohyphen'); // Hyphens removed
            expect(result).toContain('(Similarity: 0.91)');
            expect(result).toContain('Planning Session Beta');
            expect(result).toContain('notion://page/id2withhyphen');
            expect(result).toContain('(Similarity: 0.86)');
        });
        it('should return "no results" message on successful search with empty data', async () => {
            const mockApiResponse = {
                status: 'success',
                data: [],
            };
            mockedAxios.post.mockResolvedValueOnce({
                data: mockApiResponse,
            });
            const args = {
                ...baseArgs,
                params: { query: 'obscure topic' },
                raw_message: 'search obscure topic',
            };
            const result = await handleSemanticSearchMeetingNotesSkill(args);
            // The skill formats this slightly differently now based on its internal logic
            expect(result).toBe("Sorry, I couldn't find any meeting notes matching your query.");
        });
        it('should return error message if backend returns status "error"', async () => {
            const mockApiResponse = {
                status: 'error',
                message: 'Backend search exploded',
            };
            mockedAxios.post.mockResolvedValueOnce({
                data: mockApiResponse,
            });
            const args = {
                ...baseArgs,
                params: { query: 'trigger error' },
                raw_message: 'search trigger error',
            };
            const result = await handleSemanticSearchMeetingNotesSkill(args);
            expect(result).toBe('I encountered an error while searching: Backend search exploded');
        });
        it('should return generic error message if backend response is malformed (e.g. unexpected structure)', async () => {
            const mockMalformedResponse = { some_unexpected_key: 'some_value' }; // Does not match BackendSearchResponse
            mockedAxios.post.mockResolvedValueOnce({
                data: mockMalformedResponse,
            });
            const args = {
                ...baseArgs,
                params: { query: 'test malformed' },
                raw_message: 'search test malformed',
            };
            const result = await handleSemanticSearchMeetingNotesSkill(args);
            expect(result).toBe('I received an unexpected response from the search service. Please try again later.');
        });
        it('should return generic error message on axios network error', async () => {
            mockedAxios.post.mockRejectedValueOnce(new Error('Network connection failed'));
            const args = {
                ...baseArgs,
                params: { query: 'network fail test' },
                raw_message: 'search network fail test',
            };
            const result = await handleSemanticSearchMeetingNotesSkill(args);
            expect(result).toBe("I'm sorry, I ran into a problem trying to search your meeting notes. Please try again later.");
        });
        it('should return specific error message if axios error has response data from backend', async () => {
            const errorResponseData = {
                message: 'Specific backend error from Axios response',
            };
            const axiosError = new AxiosError('Request failed with status code 500');
            axiosError.response = {
                data: errorResponseData,
                status: 500,
                statusText: 'Internal Server Error',
                headers: {},
                config: {},
            };
            axiosError.isAxiosError = true;
            mockedAxios.post.mockRejectedValueOnce(axiosError);
            const args = {
                ...baseArgs,
                params: { query: 'axios error with data' },
                raw_message: 'search axios error with data',
            };
            const result = await handleSemanticSearchMeetingNotesSkill(args);
            // The skill's catch block logs axiosError.response?.data but returns a generic message
            // Let's check if the logged message (if we could capture it) or the returned message is as expected.
            // The current skill implementation returns generic message for AxiosError.
            expect(result).toBe("I'm sorry, I ran into a problem trying to search your meeting notes. Please try again later.");
        });
        it('should ask for a query if query parameter is missing in params', async () => {
            const args = {
                ...baseArgs,
                params: {},
                raw_message: 'search',
            }; // No query in params
            const result = await handleSemanticSearchMeetingNotesSkill(args);
            expect(result).toBe("Please provide a search query. For example, 'search_meeting_notes what were the decisions about project alpha?'");
            expect(mockedAxios.post).not.toHaveBeenCalled();
        });
        it('should ask for a query if query parameter is an empty string', async () => {
            const args = {
                ...baseArgs,
                params: { query: '   ' },
                raw_message: 'search    ',
            }; // Empty string query
            const result = await handleSemanticSearchMeetingNotesSkill(args);
            expect(result).toBe("Please provide a search query. For example, 'search_meeting_notes what were the decisions about project alpha?'");
            expect(mockedAxios.post).not.toHaveBeenCalled();
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VtYW50aWNTZWFyY2hTa2lsbHMudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNlbWFudGljU2VhcmNoU2tpbGxzLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxLQUFLLEVBQUUsRUFBRSxVQUFVLEVBQWlCLE1BQU0sT0FBTyxDQUFDO0FBQ3pELE9BQU87QUFDTCxpRkFBaUY7QUFDakYscUNBQXFDLEdBQ3RDLE1BQU0seUJBQXlCLENBQUM7QUE0QmpDLE9BQU8sS0FBSyxTQUFTLE1BQU0sdUJBQXVCLENBQUMsQ0FBQywyREFBMkQ7QUFFL0csYUFBYTtBQUNiLElBQUksQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLENBQUM7QUFDbkIsTUFBTSxXQUFXLEdBQUcsS0FBa0MsQ0FBQztBQUV2RCxpQkFBaUI7QUFDakIsaURBQWlEO0FBQ2pELElBQUksQ0FBQyxJQUFJLENBQUMsdUJBQXVCLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQztJQUN4QyxHQUFHLElBQUksQ0FBQyxhQUFhLENBQUMsdUJBQXVCLENBQUMsRUFBRSwyQkFBMkI7SUFDM0UsMkJBQTJCLEVBQUUsNEJBQTRCO0NBQzFELENBQUMsQ0FBQyxDQUFDO0FBRUosUUFBUSxDQUFDLDhEQUE4RCxFQUFFLEdBQUcsRUFBRTtJQUM1RSxNQUFNLE1BQU0sR0FBRyxhQUFhLENBQUM7SUFDN0IsTUFBTSxRQUFRLEdBQThDO1FBQzFELDRFQUE0RTtRQUM1RSxPQUFPLEVBQUUsc0JBQXNCO1FBQy9CLE9BQU8sRUFBRSxNQUFNO0tBQ2hCLENBQUM7SUFFRixTQUFTLENBQUMsR0FBRyxFQUFFO1FBQ2IsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDLENBQUMsOEJBQThCO0lBQ3RELENBQUMsQ0FBQyxDQUFDO0lBRUgsNEVBQTRFO0lBQzVFLFFBQVEsQ0FBQyx1Q0FBdUMsRUFBRSxHQUFHLEVBQUU7UUFDckQsRUFBRSxDQUFDLGdFQUFnRSxFQUFFLEtBQUssSUFBSSxFQUFF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QUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgYXhpb3MsIHsgQXhpb3NFcnJvciwgQXhpb3NSZXNwb25zZSB9IGZyb20gJ2F4aW9zJztcbmltcG9ydCB7XG4gIC8vIFNlbWFudGljU2VhcmNoU2tpbGxzLCAvLyBDbGFzcyBpcyBub3QgZGlyZWN0bHkgdGVzdGVkLCBidXQgdGhyb3VnaCB0aGUgaGFuZGxlclxuICBoYW5kbGVTZW1hbnRpY1NlYXJjaE1lZXRpbmdOb3Rlc1NraWxsLFxufSBmcm9tICcuLi9zZW1hbnRpY1NlYXJjaFNraWxscyc7XG4vLyBBc3N1bWluZyBCYWNrZW5kU2VhcmNoUmVzcG9uc2UgYW5kIE1lZXRpbmdTZWFyY2hSZXN1bHQgYXJlIGV4cG9ydGVkIGZyb20gc2VtYW50aWNTZWFyY2hTa2lsbHMudHNcbi8vIElmIHRoZXkgd2VyZSBtb3ZlZCB0byBhIGNlbnRyYWwgdHlwZXMgZmlsZSwgdGhlIGltcG9ydCBwYXRoIHdvdWxkIGNoYW5nZS5cbi8vIEZvciBub3csIGxldCdzIGFzc3VtZSB0aGV5IGFyZSBjby1sb2NhdGVkIG9yIHJlLWV4cG9ydGVkIGJ5IHNlbWFudGljU2VhcmNoU2tpbGxzLnRzIGlmIGRlZmluZWQgZWxzZXdoZXJlLlxuLy8gSWYgdGhleSBhcmUgbm90IGV4cG9ydGVkIGZyb20gc2VtYW50aWNTZWFyY2hTa2lsbHMudHMsIHRoaXMgd2lsbCBjYXVzZSBhIHR5cGUgZXJyb3IuXG4vLyBCYXNlZCBvbiBwcmV2aW91cyBzdWJ0YXNrLCB0aGV5IGFyZSBkZWZpbmVkIGxvY2FsbHkgaW4gc2VtYW50aWNTZWFyY2hTa2lsbHMudHMgYnV0IG5vdCBleHBvcnRlZC5cbi8vIEZvciB0aGlzIHRlc3QgdG8gY29tcGlsZSwgdGhleSBuZWVkIHRvIGJlIGV4cG9ydGVkIGZyb20gc2VtYW50aWNTZWFyY2hTa2lsbHMudHMgT1Jcbi8vIGRlZmluZWQgYWdhaW4gaGVyZSwgT1IgaW1wb3J0ZWQgZnJvbSBhIHNoYXJlZCB0eXBlcyBsb2NhdGlvbi5cbi8vIExldCdzIGFzc3VtZSB0aGV5IGFyZSBleHBvcnRlZCBmcm9tIHNlbWFudGljU2VhcmNoU2tpbGxzLnRzIGZvciB0aGlzIHRlc3QgdG8gd29yayBhcyB3cml0dGVuLlxuLy8gSWYgbm90LCB0aGlzIHdvdWxkIGJlIGEgcmVxdWlyZWQgbW9kaWZpY2F0aW9uIHRvIHNlbWFudGljU2VhcmNoU2tpbGxzLnRzIG9yIHRoaXMgdGVzdCBmaWxlLlxuXG4vLyBGb3IgdGhlIHN1YnRhc2ssIEkgd2lsbCBkZWZpbmUgdGhlbSBoZXJlIHRvIG1ha2UgdGhlIHRlc3QgZmlsZSBzZWxmLWNvbnRhaW5lZCBmb3IgdGhlc2UgdHlwZXMsXG4vLyBhcyBtb2RpZnlpbmcgc2VtYW50aWNTZWFyY2hTa2lsbHMudHMgdG8gZXhwb3J0IHRoZW0gaXMgb3V0c2lkZSB0aGlzIHNwZWNpZmljIHN1YnRhc2sncyBzY29wZS5cbmludGVyZmFjZSBNZWV0aW5nU2VhcmNoUmVzdWx0IHtcbiAgbm90aW9uX3BhZ2VfaWQ6IHN0cmluZztcbiAgbWVldGluZ190aXRsZTogc3RyaW5nO1xuICBtZWV0aW5nX2RhdGU6IHN0cmluZzsgLy8gSVNPIGRhdGUgc3RyaW5nXG4gIHNjb3JlOiBudW1iZXI7XG59XG5pbnRlcmZhY2UgQmFja2VuZFNlYXJjaFJlc3BvbnNlIHtcbiAgc3RhdHVzOiAnc3VjY2VzcycgfCAnZXJyb3InO1xuICBkYXRhPzogTWVldGluZ1NlYXJjaFJlc3VsdFtdO1xuICBtZXNzYWdlPzogc3RyaW5nO1xuICBvaz86IGJvb2xlYW47XG4gIGVycm9yPzogeyBjb2RlOiBzdHJpbmc7IG1lc3NhZ2U6IHN0cmluZzsgZGV0YWlscz86IGFueSB9O1xufVxuXG5pbXBvcnQgeyBTa2lsbEFyZ3MgfSBmcm9tICcuLi8uLi8uLi90eXBlcyc7IC8vIFBhdGggZnJvbSBza2lsbHMvdGVzdHMvIHRvIGF0b20tYWdlbnQvdHlwZXMudHNcbmltcG9ydCAqIGFzIGNvbnN0YW50cyBmcm9tICcuLi8uLi9fbGlicy9jb25zdGFudHMnOyAvLyBQYXRoIGZyb20gc2tpbGxzL3Rlc3RzLyB0byBhdG9tLWFnZW50L19saWJzL2NvbnN0YW50cy50c1xuXG4vLyBNb2NrIGF4aW9zXG5qZXN0Lm1vY2soJ2F4aW9zJyk7XG5jb25zdCBtb2NrZWRBeGlvcyA9IGF4aW9zIGFzIGplc3QuTW9ja2VkPHR5cGVvZiBheGlvcz47XG5cbi8vIE1vY2sgY29uc3RhbnRzXG4vLyBQYXRoIGlzIHJlbGF0aXZlIHRvIHRoaXMgdGVzdCBmaWxlJ3MgbG9jYXRpb24uXG5qZXN0Lm1vY2soJy4uLy4uL19saWJzL2NvbnN0YW50cycsICgpID0+ICh7XG4gIC4uLmplc3QucmVxdWlyZUFjdHVhbCgnLi4vLi4vX2xpYnMvY29uc3RhbnRzJyksIC8vIFByZXNlcnZlIG90aGVyIGNvbnN0YW50c1xuICBQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkw6ICdodHRwOi8vbW9jay1weXRob24tYXBpLmNvbScsXG59KSk7XG5cbmRlc2NyaWJlKCdTZW1hbnRpY1NlYXJjaFNraWxscyAmIGhhbmRsZVNlbWFudGljU2VhcmNoTWVldGluZ05vdGVzU2tpbGwnLCAoKSA9PiB7XG4gIGNvbnN0IHVzZXJJZCA9ICd0ZXN0VXNlcjEyMyc7XG4gIGNvbnN0IGJhc2VBcmdzOiBPbWl0PFNraWxsQXJncywgJ3BhcmFtcycgfCAncmF3X21lc3NhZ2UnPiA9IHtcbiAgICAvLyByYXdfbWVzc2FnZSBtaWdodCBub3QgYWx3YXlzIGJlIG5lZWRlZCBpZiBub3QgdXNlZCBieSBza2lsbCBmb3IgdGhpcyB0ZXN0XG4gICAgY29tbWFuZDogJ3NlYXJjaF9tZWV0aW5nX25vdGVzJyxcbiAgICB1c2VyX2lkOiB1c2VySWQsXG4gIH07XG5cbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTsgLy8gQ2xlYXIgbW9ja3MgYWZ0ZXIgZWFjaCB0ZXN0XG4gIH0pO1xuXG4gIC8vIFRlc3QgdGhlIGV4cG9ydGVkIGhhbmRsZXIgZnVuY3Rpb24sIHdoaWNoIGludGVybmFsbHkgdXNlcyB0aGUgY2xhc3MgbG9naWNcbiAgZGVzY3JpYmUoJ2hhbmRsZVNlbWFudGljU2VhcmNoTWVldGluZ05vdGVzU2tpbGwnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gZm9ybWF0dGVkIHJlc3VsdHMgb24gc3VjY2Vzc2Z1bCBzZWFyY2ggd2l0aCBkYXRhJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja0JhY2tlbmRSZXN1bHRzOiBNZWV0aW5nU2VhcmNoUmVzdWx0W10gPSBbXG4gICAgICAgIHtcbiAgICAgICAgICBub3Rpb25fcGFnZV9pZDogJ2lkLTEtbm8taHlwaGVuJyxcbiAgICAgICAgICBtZWV0aW5nX3RpdGxlOiAnVGVzdCBNZWV0aW5nIEFscGhhJyxcbiAgICAgICAgICBtZWV0aW5nX2RhdGU6ICcyMDIzLTAxLTAxVDEwOjAwOjAwWicsXG4gICAgICAgICAgc2NvcmU6IDAuOTEyMyxcbiAgICAgICAgfSxcbiAgICAgICAge1xuICAgICAgICAgIG5vdGlvbl9wYWdlX2lkOiAnaWQyd2l0aGh5cGhlbicsXG4gICAgICAgICAgbWVldGluZ190aXRsZTogJ1BsYW5uaW5nIFNlc3Npb24gQmV0YScsXG4gICAgICAgICAgbWVldGluZ19kYXRlOiAnMjAyMy0wMS0wNVQxNDozMDowMFonLFxuICAgICAgICAgIHNjb3JlOiAwLjg1NjcsXG4gICAgICAgIH0sXG4gICAgICBdO1xuICAgICAgLy8gVGhpcyBpcyB0aGUgc3RydWN0dXJlIHRoZSBQeXRob24gYmFja2VuZCAvYXBpL3NlbWFudGljX3NlYXJjaF9tZWV0aW5ncyBzZW5kc1xuICAgICAgY29uc3QgbW9ja1B5dGhvbkFwaVJlc3BvbnNlID0ge1xuICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgZGF0YTogbW9ja0JhY2tlbmRSZXN1bHRzLFxuICAgICAgfTtcbiAgICAgIG1vY2tlZEF4aW9zLnBvc3QubW9ja1Jlc29sdmVkVmFsdWVPbmNlKHtcbiAgICAgICAgZGF0YTogbW9ja1B5dGhvbkFwaVJlc3BvbnNlLFxuICAgICAgfSBhcyBBeGlvc1Jlc3BvbnNlPEJhY2tlbmRTZWFyY2hSZXNwb25zZT4pO1xuXG4gICAgICBjb25zdCBhcmdzOiBTa2lsbEFyZ3MgPSB7XG4gICAgICAgIC4uLmJhc2VBcmdzLFxuICAgICAgICBwYXJhbXM6IHsgcXVlcnk6ICdyZWxldmFudCB0b3BpYycgfSxcbiAgICAgICAgcmF3X21lc3NhZ2U6ICdzZWFyY2ggZm9yIHJlbGV2YW50IHRvcGljJyxcbiAgICAgIH07XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVTZW1hbnRpY1NlYXJjaE1lZXRpbmdOb3Rlc1NraWxsKGFyZ3MpO1xuXG4gICAgICBleHBlY3QobW9ja2VkQXhpb3MucG9zdCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgIGAke2NvbnN0YW50cy5QWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9zZW1hbnRpY19zZWFyY2hfbWVldGluZ3NgLFxuICAgICAgICB7IHF1ZXJ5OiAncmVsZXZhbnQgdG9waWMnLCB1c2VyX2lkOiB1c2VySWQgfVxuICAgICAgKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignRm91bmQgdGhlc2UgbWVldGluZ3MgcmVsYXRlZCB0byB5b3VyIHF1ZXJ5OicpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdUZXN0IE1lZXRpbmcgQWxwaGEnKTtcbiAgICAgIC8vIFVzZSB0b0xvY2FsZURhdGVTdHJpbmcgd2l0aCB1bmRlZmluZWQgbG9jYWxlIHRvIHVzZSBzeXN0ZW0ncyBkZWZhdWx0LCBtYWtpbmcgdGVzdCBtb3JlIHBvcnRhYmxlXG4gICAgICBjb25zdCBkYXRlMSA9IG5ldyBEYXRlKCcyMDIzLTAxLTAxVDEwOjAwOjAwWicpO1xuICAgICAgY29uc3QgZXhwZWN0ZWREYXRlMVN0ciA9IGRhdGUxLnRvTG9jYWxlRGF0ZVN0cmluZyh1bmRlZmluZWQsIHtcbiAgICAgICAgeWVhcjogJ251bWVyaWMnLFxuICAgICAgICBtb250aDogJ2xvbmcnLFxuICAgICAgICBkYXk6ICdudW1lcmljJyxcbiAgICAgIH0pO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKGAoJHtleHBlY3RlZERhdGUxU3RyfSlgKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignbm90aW9uOi8vcGFnZS9pZDFub2h5cGhlbicpOyAvLyBIeXBoZW5zIHJlbW92ZWRcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignKFNpbWlsYXJpdHk6IDAuOTEpJyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ1BsYW5uaW5nIFNlc3Npb24gQmV0YScpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdub3Rpb246Ly9wYWdlL2lkMndpdGhoeXBoZW4nKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignKFNpbWlsYXJpdHk6IDAuODYpJyk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBcIm5vIHJlc3VsdHNcIiBtZXNzYWdlIG9uIHN1Y2Nlc3NmdWwgc2VhcmNoIHdpdGggZW1wdHkgZGF0YScsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tBcGlSZXNwb25zZTogQmFja2VuZFNlYXJjaFJlc3BvbnNlID0ge1xuICAgICAgICBzdGF0dXM6ICdzdWNjZXNzJyxcbiAgICAgICAgZGF0YTogW10sXG4gICAgICB9O1xuICAgICAgbW9ja2VkQXhpb3MucG9zdC5tb2NrUmVzb2x2ZWRWYWx1ZU9uY2Uoe1xuICAgICAgICBkYXRhOiBtb2NrQXBpUmVzcG9uc2UsXG4gICAgICB9IGFzIEF4aW9zUmVzcG9uc2U8QmFja2VuZFNlYXJjaFJlc3BvbnNlPik7XG5cbiAgICAgIGNvbnN0IGFyZ3M6IFNraWxsQXJncyA9IHtcbiAgICAgICAgLi4uYmFzZUFyZ3MsXG4gICAgICAgIHBhcmFtczogeyBxdWVyeTogJ29ic2N1cmUgdG9waWMnIH0sXG4gICAgICAgIHJhd19tZXNzYWdlOiAnc2VhcmNoIG9ic2N1cmUgdG9waWMnLFxuICAgICAgfTtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNlbWFudGljU2VhcmNoTWVldGluZ05vdGVzU2tpbGwoYXJncyk7XG5cbiAgICAgIC8vIFRoZSBza2lsbCBmb3JtYXRzIHRoaXMgc2xpZ2h0bHkgZGlmZmVyZW50bHkgbm93IGJhc2VkIG9uIGl0cyBpbnRlcm5hbCBsb2dpY1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBmaW5kIGFueSBtZWV0aW5nIG5vdGVzIG1hdGNoaW5nIHlvdXIgcXVlcnkuXCJcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBlcnJvciBtZXNzYWdlIGlmIGJhY2tlbmQgcmV0dXJucyBzdGF0dXMgXCJlcnJvclwiJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja0FwaVJlc3BvbnNlOiBCYWNrZW5kU2VhcmNoUmVzcG9uc2UgPSB7XG4gICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgbWVzc2FnZTogJ0JhY2tlbmQgc2VhcmNoIGV4cGxvZGVkJyxcbiAgICAgIH07XG4gICAgICBtb2NrZWRBeGlvcy5wb3N0Lm1vY2tSZXNvbHZlZFZhbHVlT25jZSh7XG4gICAgICAgIGRhdGE6IG1vY2tBcGlSZXNwb25zZSxcbiAgICAgIH0gYXMgQXhpb3NSZXNwb25zZTxCYWNrZW5kU2VhcmNoUmVzcG9uc2U+KTtcblxuICAgICAgY29uc3QgYXJnczogU2tpbGxBcmdzID0ge1xuICAgICAgICAuLi5iYXNlQXJncyxcbiAgICAgICAgcGFyYW1zOiB7IHF1ZXJ5OiAndHJpZ2dlciBlcnJvcicgfSxcbiAgICAgICAgcmF3X21lc3NhZ2U6ICdzZWFyY2ggdHJpZ2dlciBlcnJvcicsXG4gICAgICB9O1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VtYW50aWNTZWFyY2hNZWV0aW5nTm90ZXNTa2lsbChhcmdzKTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ0kgZW5jb3VudGVyZWQgYW4gZXJyb3Igd2hpbGUgc2VhcmNoaW5nOiBCYWNrZW5kIHNlYXJjaCBleHBsb2RlZCdcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBnZW5lcmljIGVycm9yIG1lc3NhZ2UgaWYgYmFja2VuZCByZXNwb25zZSBpcyBtYWxmb3JtZWQgKGUuZy4gdW5leHBlY3RlZCBzdHJ1Y3R1cmUpJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja01hbGZvcm1lZFJlc3BvbnNlID0geyBzb21lX3VuZXhwZWN0ZWRfa2V5OiAnc29tZV92YWx1ZScgfTsgLy8gRG9lcyBub3QgbWF0Y2ggQmFja2VuZFNlYXJjaFJlc3BvbnNlXG4gICAgICBtb2NrZWRBeGlvcy5wb3N0Lm1vY2tSZXNvbHZlZFZhbHVlT25jZSh7XG4gICAgICAgIGRhdGE6IG1vY2tNYWxmb3JtZWRSZXNwb25zZSxcbiAgICAgIH0gYXMgYW55KTtcblxuICAgICAgY29uc3QgYXJnczogU2tpbGxBcmdzID0ge1xuICAgICAgICAuLi5iYXNlQXJncyxcbiAgICAgICAgcGFyYW1zOiB7IHF1ZXJ5OiAndGVzdCBtYWxmb3JtZWQnIH0sXG4gICAgICAgIHJhd19tZXNzYWdlOiAnc2VhcmNoIHRlc3QgbWFsZm9ybWVkJyxcbiAgICAgIH07XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVTZW1hbnRpY1NlYXJjaE1lZXRpbmdOb3Rlc1NraWxsKGFyZ3MpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ0kgcmVjZWl2ZWQgYW4gdW5leHBlY3RlZCByZXNwb25zZSBmcm9tIHRoZSBzZWFyY2ggc2VydmljZS4gUGxlYXNlIHRyeSBhZ2FpbiBsYXRlci4nXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gZ2VuZXJpYyBlcnJvciBtZXNzYWdlIG9uIGF4aW9zIG5ldHdvcmsgZXJyb3InLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrZWRBeGlvcy5wb3N0Lm1vY2tSZWplY3RlZFZhbHVlT25jZShcbiAgICAgICAgbmV3IEVycm9yKCdOZXR3b3JrIGNvbm5lY3Rpb24gZmFpbGVkJylcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IGFyZ3M6IFNraWxsQXJncyA9IHtcbiAgICAgICAgLi4uYmFzZUFyZ3MsXG4gICAgICAgIHBhcmFtczogeyBxdWVyeTogJ25ldHdvcmsgZmFpbCB0ZXN0JyB9LFxuICAgICAgICByYXdfbWVzc2FnZTogJ3NlYXJjaCBuZXR3b3JrIGZhaWwgdGVzdCcsXG4gICAgICB9O1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VtYW50aWNTZWFyY2hNZWV0aW5nTm90ZXNTa2lsbChhcmdzKTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgXCJJJ20gc29ycnksIEkgcmFuIGludG8gYSBwcm9ibGVtIHRyeWluZyB0byBzZWFyY2ggeW91ciBtZWV0aW5nIG5vdGVzLiBQbGVhc2UgdHJ5IGFnYWluIGxhdGVyLlwiXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gc3BlY2lmaWMgZXJyb3IgbWVzc2FnZSBpZiBheGlvcyBlcnJvciBoYXMgcmVzcG9uc2UgZGF0YSBmcm9tIGJhY2tlbmQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBlcnJvclJlc3BvbnNlRGF0YSA9IHtcbiAgICAgICAgbWVzc2FnZTogJ1NwZWNpZmljIGJhY2tlbmQgZXJyb3IgZnJvbSBBeGlvcyByZXNwb25zZScsXG4gICAgICB9O1xuICAgICAgY29uc3QgYXhpb3NFcnJvciA9IG5ldyBBeGlvc0Vycm9yKCdSZXF1ZXN0IGZhaWxlZCB3aXRoIHN0YXR1cyBjb2RlIDUwMCcpO1xuICAgICAgYXhpb3NFcnJvci5yZXNwb25zZSA9IHtcbiAgICAgICAgZGF0YTogZXJyb3JSZXNwb25zZURhdGEsXG4gICAgICAgIHN0YXR1czogNTAwLFxuICAgICAgICBzdGF0dXNUZXh0OiAnSW50ZXJuYWwgU2VydmVyIEVycm9yJyxcbiAgICAgICAgaGVhZGVyczoge30sXG4gICAgICAgIGNvbmZpZzoge30sXG4gICAgICB9IGFzIEF4aW9zUmVzcG9uc2U7XG4gICAgICBheGlvc0Vycm9yLmlzQXhpb3NFcnJvciA9IHRydWU7XG5cbiAgICAgIG1vY2tlZEF4aW9zLnBvc3QubW9ja1JlamVjdGVkVmFsdWVPbmNlKGF4aW9zRXJyb3IpO1xuXG4gICAgICBjb25zdCBhcmdzOiBTa2lsbEFyZ3MgPSB7XG4gICAgICAgIC4uLmJhc2VBcmdzLFxuICAgICAgICBwYXJhbXM6IHsgcXVlcnk6ICdheGlvcyBlcnJvciB3aXRoIGRhdGEnIH0sXG4gICAgICAgIHJhd19tZXNzYWdlOiAnc2VhcmNoIGF4aW9zIGVycm9yIHdpdGggZGF0YScsXG4gICAgICB9O1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VtYW50aWNTZWFyY2hNZWV0aW5nTm90ZXNTa2lsbChhcmdzKTtcbiAgICAgIC8vIFRoZSBza2lsbCdzIGNhdGNoIGJsb2NrIGxvZ3MgYXhpb3NFcnJvci5yZXNwb25zZT8uZGF0YSBidXQgcmV0dXJucyBhIGdlbmVyaWMgbWVzc2FnZVxuICAgICAgLy8gTGV0J3MgY2hlY2sgaWYgdGhlIGxvZ2dlZCBtZXNzYWdlIChpZiB3ZSBjb3VsZCBjYXB0dXJlIGl0KSBvciB0aGUgcmV0dXJuZWQgbWVzc2FnZSBpcyBhcyBleHBlY3RlZC5cbiAgICAgIC8vIFRoZSBjdXJyZW50IHNraWxsIGltcGxlbWVudGF0aW9uIHJldHVybnMgZ2VuZXJpYyBtZXNzYWdlIGZvciBBeGlvc0Vycm9yLlxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgXCJJJ20gc29ycnksIEkgcmFuIGludG8gYSBwcm9ibGVtIHRyeWluZyB0byBzZWFyY2ggeW91ciBtZWV0aW5nIG5vdGVzLiBQbGVhc2UgdHJ5IGFnYWluIGxhdGVyLlwiXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBhc2sgZm9yIGEgcXVlcnkgaWYgcXVlcnkgcGFyYW1ldGVyIGlzIG1pc3NpbmcgaW4gcGFyYW1zJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgYXJnczogU2tpbGxBcmdzID0ge1xuICAgICAgICAuLi5iYXNlQXJncyxcbiAgICAgICAgcGFyYW1zOiB7fSxcbiAgICAgICAgcmF3X21lc3NhZ2U6ICdzZWFyY2gnLFxuICAgICAgfTsgLy8gTm8gcXVlcnkgaW4gcGFyYW1zXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVTZW1hbnRpY1NlYXJjaE1lZXRpbmdOb3Rlc1NraWxsKGFyZ3MpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgXCJQbGVhc2UgcHJvdmlkZSBhIHNlYXJjaCBxdWVyeS4gRm9yIGV4YW1wbGUsICdzZWFyY2hfbWVldGluZ19ub3RlcyB3aGF0IHdlcmUgdGhlIGRlY2lzaW9ucyBhYm91dCBwcm9qZWN0IGFscGhhPydcIlxuICAgICAgKTtcbiAgICAgIGV4cGVjdChtb2NrZWRBeGlvcy5wb3N0KS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBhc2sgZm9yIGEgcXVlcnkgaWYgcXVlcnkgcGFyYW1ldGVyIGlzIGFuIGVtcHR5IHN0cmluZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGFyZ3M6IFNraWxsQXJncyA9IHtcbiAgICAgICAgLi4uYmFzZUFyZ3MsXG4gICAgICAgIHBhcmFtczogeyBxdWVyeTogJyAgICcgfSxcbiAgICAgICAgcmF3X21lc3NhZ2U6ICdzZWFyY2ggICAgJyxcbiAgICAgIH07IC8vIEVtcHR5IHN0cmluZyBxdWVyeVxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VtYW50aWNTZWFyY2hNZWV0aW5nTm90ZXNTa2lsbChhcmdzKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgIFwiUGxlYXNlIHByb3ZpZGUgYSBzZWFyY2ggcXVlcnkuIEZvciBleGFtcGxlLCAnc2VhcmNoX21lZXRpbmdfbm90ZXMgd2hhdCB3ZXJlIHRoZSBkZWNpc2lvbnMgYWJvdXQgcHJvamVjdCBhbHBoYT8nXCJcbiAgICAgICk7XG4gICAgICBleHBlY3QobW9ja2VkQXhpb3MucG9zdCkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==