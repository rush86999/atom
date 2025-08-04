import { listZoomMeetings, getZoomMeetingDetails, resetTokenCache, } from './zoomSkills';
import axios from 'axios';
import * as constants from '../_libs/constants';
// Mock external dependencies
jest.mock('axios');
const mockedAxios = axios;
jest.mock('../_libs/constants', () => ({
    ATOM_ZOOM_ACCOUNT_ID: 'test_account_id',
    ATOM_ZOOM_CLIENT_ID: 'test_client_id',
    ATOM_ZOOM_CLIENT_SECRET: 'test_client_secret',
}));
// Spy on console.error and console.log
let consoleErrorSpy;
let consoleLogSpy;
describe('zoomSkills', () => {
    beforeEach(() => {
        mockedAxios.post.mockReset();
        mockedAxios.get.mockReset();
        resetTokenCache(); // Reset the in-memory token cache before each test
        // Set default mock values for constants for each test, can be overridden by spyOn
        jest
            .spyOn(constants, 'ATOM_ZOOM_ACCOUNT_ID', 'get')
            .mockReturnValue('test_account_id');
        jest
            .spyOn(constants, 'ATOM_ZOOM_CLIENT_ID', 'get')
            .mockReturnValue('test_client_id');
        jest
            .spyOn(constants, 'ATOM_ZOOM_CLIENT_SECRET', 'get')
            .mockReturnValue('test_client_secret');
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => { });
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => { });
    });
    afterEach(() => {
        jest.clearAllMocks(); // Clears all mocks, including spies
        consoleErrorSpy.mockRestore();
        consoleLogSpy.mockRestore();
    });
    describe('getZoomAccessToken (tested implicitly via skill functions)', () => {
        const mockZoomUserId = 'user123';
        it('should fetch and cache a new token successfully', async () => {
            mockedAxios.post.mockResolvedValueOnce({
                data: {
                    access_token: 'new_token_123',
                    expires_in: 3600,
                    token_type: 'Bearer',
                },
                status: 200,
            });
            mockedAxios.get.mockResolvedValueOnce({ data: { meetings: [] } }); // For listZoomMeetings call
            await listZoomMeetings(mockZoomUserId); // First call, fetches and caches token
            expect(mockedAxios.post).toHaveBeenCalledTimes(1);
            expect(mockedAxios.post).toHaveBeenCalledWith('https://zoom.us/oauth/token', expect.stringContaining('grant_type=account_credentials'), expect.objectContaining({
                headers: expect.objectContaining({
                    Authorization: expect.stringContaining('Basic '),
                }),
            }));
            mockedAxios.get.mockClear(); // Clear get mock before next call
            mockedAxios.get.mockResolvedValueOnce({ data: { meetings: [] } }); // Mock for second listZoomMeetings
            await listZoomMeetings(mockZoomUserId); // Second call, should use cached token
            expect(mockedAxios.post).toHaveBeenCalledTimes(1); // Still 1, token was cached
            expect(mockedAxios.get).toHaveBeenCalledTimes(1); // listZoomMeetings' GET was called
        });
        it('should refresh token if expired', async () => {
            mockedAxios.post.mockResolvedValueOnce({
                // Initial token, expires quickly
                data: { access_token: 'token_initial', expires_in: 1 },
                status: 200,
            });
            mockedAxios.post.mockResolvedValueOnce({
                // Refreshed token
                data: { access_token: 'token_refreshed', expires_in: 3600 },
                status: 200,
            });
            mockedAxios.get.mockResolvedValue({ data: { meetings: [] } }); // For listZoomMeetings
            await listZoomMeetings(mockZoomUserId); // Initial call
            expect(mockedAxios.post).toHaveBeenCalledTimes(1);
            jest.useFakeTimers();
            jest.advanceTimersByTime(2000); // Advance time by 2 seconds, enough for token to expire
            jest.useRealTimers();
            await listZoomMeetings(mockZoomUserId); // Second call, should trigger refresh
            expect(mockedAxios.post).toHaveBeenCalledTimes(2); // Token refreshed
            // Check if the GET call for the second listZoomMeetings used the refreshed token
            // This requires inspecting the actual call arguments if the mock setup allows.
            // The current mock setup for axios.get might not easily allow direct inspection of headers for the *second* call if not reset.
            // However, the fact that POST was called twice is the primary indicator of refresh.
            // To verify the header, we'd need a more granular mock or capture arguments.
            // For now, we assume the new token from the second POST would be used.
            // A more robust test might involve capturing the token in getZoomAccessToken if it were directly testable
            // or ensuring the Authorization header in the second GET call is 'Bearer token_refreshed'.
            // Let's check the last call to GET (which is the second one here)
            const lastGetCall = mockedAxios.get.mock.calls[mockedAxios.get.mock.calls.length - 1];
            expect(lastGetCall[1]?.headers?.Authorization).toBe('Bearer token_refreshed');
        });
        it('should return error if Zoom auth API fails', async () => {
            mockedAxios.post.mockRejectedValueOnce(new Error('Zoom Auth Failed'));
            const result = await listZoomMeetings(mockZoomUserId);
            expect(result.ok).toBe(false);
            expect(result.error).toContain('Failed to obtain Zoom access token.');
            expect(consoleErrorSpy).toHaveBeenCalledWith('Error obtaining Zoom access token:', 'Zoom Auth Failed');
        });
        it('should return error if Zoom auth constants are missing', async () => {
            jest.spyOn(constants, 'ATOM_ZOOM_CLIENT_ID', 'get').mockReturnValue(''); // Simulate missing client ID
            const result = await listZoomMeetings(mockZoomUserId);
            expect(result.ok).toBe(false);
            expect(result.error).toContain('Failed to obtain Zoom access token.'); // The getZoomAccessToken returns null
            expect(consoleErrorSpy).toHaveBeenCalledWith('Zoom API credentials (Account ID, Client ID, Client Secret) not configured.');
        });
    });
    describe('listZoomMeetings', () => {
        const mockZoomUserId = 'user456';
        beforeEach(() => {
            // Ensure a valid token is mocked for these tests, as token logic is tested separately
            mockedAxios.post.mockResolvedValue({
                data: { access_token: 'valid_token_for_list', expires_in: 3600 },
                status: 200,
            });
        });
        it('should list meetings successfully', async () => {
            const mockMeetingsData = [
                { id: 'm1', topic: 'Meeting 1' },
            ];
            mockedAxios.get.mockResolvedValueOnce({
                data: {
                    meetings: mockMeetingsData,
                    next_page_token: 'next_token_here',
                },
                status: 200,
            });
            const result = await listZoomMeetings(mockZoomUserId, {
                type: 'upcoming',
                page_size: 10,
            });
            expect(result.ok).toBe(true);
            expect(result.meetings).toEqual(mockMeetingsData);
            expect(result.next_page_token).toBe('next_token_here');
            expect(mockedAxios.get).toHaveBeenCalledWith(`${ZOOM_API_BASE_URL}/users/${mockZoomUserId}/meetings`, expect.objectContaining({
                headers: { Authorization: 'Bearer valid_token_for_list' },
                params: { type: 'upcoming', page_size: 10 },
            }));
        });
        it('should handle API error when listing meetings', async () => {
            const apiError = {
                isAxiosError: true,
                response: { data: { message: 'Error from Zoom API' } },
                message: 'Request failed',
            };
            mockedAxios.get.mockRejectedValueOnce(apiError);
            const result = await listZoomMeetings(mockZoomUserId);
            expect(result.ok).toBe(false);
            expect(result.error).toBe('Error from Zoom API');
            expect(consoleErrorSpy).toHaveBeenCalledWith(`Error listing Zoom meetings for userId ${mockZoomUserId}:`, 'Request failed');
        });
    });
    describe('getZoomMeetingDetails', () => {
        const mockMeetingId = 'meeting789';
        beforeEach(() => {
            mockedAxios.post.mockResolvedValue({
                data: { access_token: 'valid_token_for_details', expires_in: 3600 },
                status: 200,
            });
        });
        it('should get meeting details successfully', async () => {
            const mockMeetingDetailData = {
                id: mockMeetingId,
                topic: 'Detailed Meeting Topic',
            };
            mockedAxios.get.mockResolvedValueOnce({
                data: mockMeetingDetailData,
                status: 200,
            });
            const result = await getZoomMeetingDetails(mockMeetingId);
            expect(result.ok).toBe(true);
            expect(result.meeting).toEqual(mockMeetingDetailData);
            expect(mockedAxios.get).toHaveBeenCalledWith(`${ZOOM_API_BASE_URL}/meetings/${mockMeetingId}`, expect.objectContaining({
                headers: { Authorization: 'Bearer valid_token_for_details' },
            }));
        });
        it('should handle meeting not found (404 error)', async () => {
            const axiosError = {
                isAxiosError: true,
                response: { status: 404, data: { message: 'Meeting does not exist.' } },
                message: 'Request failed with status code 404',
            };
            mockedAxios.get.mockRejectedValueOnce(axiosError);
            const result = await getZoomMeetingDetails('non_existent_id');
            expect(result.ok).toBe(false);
            expect(result.error).toContain('Meeting not found (ID: non_existent_id). Meeting does not exist.');
            expect(consoleErrorSpy).toHaveBeenCalledWith(`Error getting Zoom meeting details for meetingId non_existent_id:`, 'Request failed with status code 404');
        });
        it('should handle other API errors when getting details', async () => {
            const apiError = {
                isAxiosError: true,
                response: { data: { message: 'Some other API error' } },
                message: 'Request failed',
            };
            mockedAxios.get.mockRejectedValueOnce(apiError);
            const result = await getZoomMeetingDetails(mockMeetingId);
            expect(result.ok).toBe(false);
            expect(result.error).toBe('Some other API error');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiem9vbVNraWxscy50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiem9vbVNraWxscy50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFDTCxnQkFBZ0IsRUFDaEIscUJBQXFCLEVBQ3JCLGVBQWUsR0FDaEIsTUFBTSxjQUFjLENBQUM7QUFDdEIsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBQzFCLE9BQU8sS0FBSyxTQUFTLE1BQU0sb0JBQW9CLENBQUM7QUFHaEQsNkJBQTZCO0FBQzdCLElBQUksQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLENBQUM7QUFDbkIsTUFBTSxXQUFXLEdBQUcsS0FBa0MsQ0FBQztBQUV2RCxJQUFJLENBQUMsSUFBSSxDQUFDLG9CQUFvQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDckMsb0JBQW9CLEVBQUUsaUJBQWlCO0lBQ3ZDLG1CQUFtQixFQUFFLGdCQUFnQjtJQUNyQyx1QkFBdUIsRUFBRSxvQkFBb0I7Q0FDOUMsQ0FBQyxDQUFDLENBQUM7QUFFSix1Q0FBdUM7QUFDdkMsSUFBSSxlQUFpQyxDQUFDO0FBQ3RDLElBQUksYUFBK0IsQ0FBQztBQUVwQyxRQUFRLENBQUMsWUFBWSxFQUFFLEdBQUcsRUFBRTtJQUMxQixVQUFVLENBQUMsR0FBRyxFQUFFO1FBQ2QsV0FBVyxDQUFDLElBQUksQ0FBQyxTQUFTLEVBQUUsQ0FBQztRQUM3QixXQUFXLENBQUMsR0FBRyxDQUFDLFNBQVMsRUFBRSxDQUFDO1FBQzVCLGVBQWUsRUFBRSxDQUFDLENBQUMsbURBQW1EO1FBRXRFLGtGQUFrRjtRQUNsRixJQUFJO2FBQ0QsS0FBSyxDQUFDLFNBQVMsRUFBRSxzQkFBc0IsRUFBRSxLQUFLLENBQUM7YUFDL0MsZUFBZSxDQUFDLGlCQUFpQixDQUFDLENBQUM7UUFDdEMsSUFBSTthQUNELEtBQUssQ0FBQyxTQUFTLEVBQUUscUJBQXFCLEVBQUUsS0FBSyxDQUFDO2FBQzlDLGVBQWUsQ0FBQyxn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bmdzLFxuICBnZXRab29tTWVldGluZ0RldGFpbHMsXG4gIHJlc2V0VG9rZW5DYWNoZSxcbn0gZnJvbSAnLi96b29tU2tpbGxzJztcbmltcG9ydCBheGlvcyBmcm9tICdheGlvcyc7XG5pbXBvcnQgKiBhcyBjb25zdGFudHMgZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IFpvb21NZWV0aW5nLCBab29tVG9rZW5SZXNwb25zZSB9IGZyb20gJy4uL3R5cGVzJzsgLy8gQXNzdW1pbmcgdHlwZXMgYXJlIGNvcnJlY3RseSBkZWZpbmVkXG5cbi8vIE1vY2sgZXh0ZXJuYWwgZGVwZW5kZW5jaWVzXG5qZXN0Lm1vY2soJ2F4aW9zJyk7XG5jb25zdCBtb2NrZWRBeGlvcyA9IGF4aW9zIGFzIGplc3QuTW9ja2VkPHR5cGVvZiBheGlvcz47XG5cbmplc3QubW9jaygnLi4vX2xpYnMvY29uc3RhbnRzJywgKCkgPT4gKHtcbiAgQVRPTV9aT09NX0FDQ09VTlRfSUQ6ICd0ZXN0X2FjY291bnRfaWQnLFxuICBBVE9NX1pPT01fQ0xJRU5UX0lEOiAndGVzdF9jbGllbnRfaWQnLFxuICBBVE9NX1pPT01fQ0xJRU5UX1NFQ1JFVDogJ3Rlc3RfY2xpZW50X3NlY3JldCcsXG59KSk7XG5cbi8vIFNweSBvbiBjb25zb2xlLmVycm9yIGFuZCBjb25zb2xlLmxvZ1xubGV0IGNvbnNvbGVFcnJvclNweTogamVzdC5TcHlJbnN0YW5jZTtcbmxldCBjb25zb2xlTG9nU3B5OiBqZXN0LlNweUluc3RhbmNlO1xuXG5kZXNjcmliZSgnem9vbVNraWxscycsICgpID0+IHtcbiAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgbW9ja2VkQXhpb3MucG9zdC5tb2NrUmVzZXQoKTtcbiAgICBtb2NrZWRBeGlvcy5nZXQubW9ja1Jlc2V0KCk7XG4gICAgcmVzZXRUb2tlbkNhY2hlKCk7IC8vIFJlc2V0IHRoZSBpbi1tZW1vcnkgdG9rZW4gY2FjaGUgYmVmb3JlIGVhY2ggdGVzdFxuXG4gICAgLy8gU2V0IGRlZmF1bHQgbW9jayB2YWx1ZXMgZm9yIGNvbnN0YW50cyBmb3IgZWFjaCB0ZXN0LCBjYW4gYmUgb3ZlcnJpZGRlbiBieSBzcHlPblxuICAgIGplc3RcbiAgICAgIC5zcHlPbihjb25zdGFudHMsICdBVE9NX1pPT01fQUNDT1VOVF9JRCcsICdnZXQnKVxuICAgICAgLm1vY2tSZXR1cm5WYWx1ZSgndGVzdF9hY2NvdW50X2lkJyk7XG4gICAgamVzdFxuICAgICAgLnNweU9uKGNvbnN0YW50cywgJ0FUT01fWk9PTV9DTElFTlRfSUQnLCAnZ2V0JylcbiAgICAgIC5tb2NrUmV0dXJuVmFsdWUoJ3Rlc3RfY2xpZW50X2lkJyk7XG4gICAgamVzdFxuICAgICAgLnNweU9uKGNvbnN0YW50cywgJ0FUT01fWk9PTV9DTElFTlRfU0VDUkVUJywgJ2dldCcpXG4gICAgICAubW9ja1JldHVyblZhbHVlKCd0ZXN0X2NsaWVudF9zZWNyZXQnKTtcblxuICAgIGNvbnNvbGVFcnJvclNweSA9IGplc3Quc3B5T24oY29uc29sZSwgJ2Vycm9yJykubW9ja0ltcGxlbWVudGF0aW9uKCgpID0+IHt9KTtcbiAgICBjb25zb2xlTG9nU3B5ID0gamVzdC5zcHlPbihjb25zb2xlLCAnbG9nJykubW9ja0ltcGxlbWVudGF0aW9uKCgpID0+IHt9KTtcbiAgfSk7XG5cbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTsgLy8gQ2xlYXJzIGFsbCBtb2NrcywgaW5jbHVkaW5nIHNwaWVzXG4gICAgY29uc29sZUVycm9yU3B5Lm1vY2tSZXN0b3JlKCk7XG4gICAgY29uc29sZUxvZ1NweS5tb2NrUmVzdG9yZSgpO1xuICB9KTtcblxuICBkZXNjcmliZSgnZ2V0Wm9vbUFjY2Vzc1Rva2VuICh0ZXN0ZWQgaW1wbGljaXRseSB2aWEgc2tpbGwgZnVuY3Rpb25zKScsICgpID0+IHtcbiAgICBjb25zdCBtb2NrWm9vbVVzZXJJZCA9ICd1c2VyMTIzJztcblxuICAgIGl0KCdzaG91bGQgZmV0Y2ggYW5kIGNhY2hlIGEgbmV3IHRva2VuIHN1Y2Nlc3NmdWxseScsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tlZEF4aW9zLnBvc3QubW9ja1Jlc29sdmVkVmFsdWVPbmNlKHtcbiAgICAgICAgZGF0YToge1xuICAgICAgICAgIGFjY2Vzc190b2tlbjogJ25ld190b2tlbl8xMjMnLFxuICAgICAgICAgIGV4cGlyZXNfaW46IDM2MDAsXG4gICAgICAgICAgdG9rZW5fdHlwZTogJ0JlYXJlcicsXG4gICAgICAgIH0gYXMgWm9vbVRva2VuUmVzcG9uc2UsXG4gICAgICAgIHN0YXR1czogMjAwLFxuICAgICAgfSk7XG4gICAgICBtb2NrZWRBeGlvcy5nZXQubW9ja1Jlc29sdmVkVmFsdWVPbmNlKHsgZGF0YTogeyBtZWV0aW5nczogW10gfSB9KTsgLy8gRm9yIGxpc3Rab29tTWVldGluZ3MgY2FsbFxuXG4gICAgICBhd2FpdCBsaXN0Wm9vbU1lZXRpbmdzKG1vY2tab29tVXNlcklkKTsgLy8gRmlyc3QgY2FsbCwgZmV0Y2hlcyBhbmQgY2FjaGVzIHRva2VuXG4gICAgICBleHBlY3QobW9ja2VkQXhpb3MucG9zdCkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpO1xuICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zLnBvc3QpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICAnaHR0cHM6Ly96b29tLnVzL29hdXRoL3Rva2VuJyxcbiAgICAgICAgZXhwZWN0LnN0cmluZ0NvbnRhaW5pbmcoJ2dyYW50X3R5cGU9YWNjb3VudF9jcmVkZW50aWFscycpLFxuICAgICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XG4gICAgICAgICAgaGVhZGVyczogZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xuICAgICAgICAgICAgQXV0aG9yaXphdGlvbjogZXhwZWN0LnN0cmluZ0NvbnRhaW5pbmcoJ0Jhc2ljICcpLFxuICAgICAgICAgIH0pLFxuICAgICAgICB9KVxuICAgICAgKTtcblxuICAgICAgbW9ja2VkQXhpb3MuZ2V0Lm1vY2tDbGVhcigpOyAvLyBDbGVhciBnZXQgbW9jayBiZWZvcmUgbmV4dCBjYWxsXG4gICAgICBtb2NrZWRBeGlvcy5nZXQubW9ja1Jlc29sdmVkVmFsdWVPbmNlKHsgZGF0YTogeyBtZWV0aW5nczogW10gfSB9KTsgLy8gTW9jayBmb3Igc2Vjb25kIGxpc3Rab29tTWVldGluZ3NcblxuICAgICAgYXdhaXQgbGlzdFpvb21NZWV0aW5ncyhtb2NrWm9vbVVzZXJJZCk7IC8vIFNlY29uZCBjYWxsLCBzaG91bGQgdXNlIGNhY2hlZCB0b2tlblxuICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zLnBvc3QpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygxKTsgLy8gU3RpbGwgMSwgdG9rZW4gd2FzIGNhY2hlZFxuICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zLmdldCkudG9IYXZlQmVlbkNhbGxlZFRpbWVzKDEpOyAvLyBsaXN0Wm9vbU1lZXRpbmdzJyBHRVQgd2FzIGNhbGxlZFxuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZWZyZXNoIHRva2VuIGlmIGV4cGlyZWQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrZWRBeGlvcy5wb3N0Lm1vY2tSZXNvbHZlZFZhbHVlT25jZSh7XG4gICAgICAgIC8vIEluaXRpYWwgdG9rZW4sIGV4cGlyZXMgcXVpY2tseVxuICAgICAgICBkYXRhOiB7IGFjY2Vzc190b2tlbjogJ3Rva2VuX2luaXRpYWwnLCBleHBpcmVzX2luOiAxIH0sXG4gICAgICAgIHN0YXR1czogMjAwLFxuICAgICAgfSk7XG4gICAgICBtb2NrZWRBeGlvcy5wb3N0Lm1vY2tSZXNvbHZlZFZhbHVlT25jZSh7XG4gICAgICAgIC8vIFJlZnJlc2hlZCB0b2tlblxuICAgICAgICBkYXRhOiB7IGFjY2Vzc190b2tlbjogJ3Rva2VuX3JlZnJlc2hlZCcsIGV4cGlyZXNfaW46IDM2MDAgfSxcbiAgICAgICAgc3RhdHVzOiAyMDAsXG4gICAgICB9KTtcbiAgICAgIG1vY2tlZEF4aW9zLmdldC5tb2NrUmVzb2x2ZWRWYWx1ZSh7IGRhdGE6IHsgbWVldGluZ3M6IFtdIH0gfSk7IC8vIEZvciBsaXN0Wm9vbU1lZXRpbmdzXG5cbiAgICAgIGF3YWl0IGxpc3Rab29tTWVldGluZ3MobW9ja1pvb21Vc2VySWQpOyAvLyBJbml0aWFsIGNhbGxcbiAgICAgIGV4cGVjdChtb2NrZWRBeGlvcy5wb3N0KS50b0hhdmVCZWVuQ2FsbGVkVGltZXMoMSk7XG5cbiAgICAgIGplc3QudXNlRmFrZVRpbWVycygpO1xuICAgICAgamVzdC5hZHZhbmNlVGltZXJzQnlUaW1lKDIwMDApOyAvLyBBZHZhbmNlIHRpbWUgYnkgMiBzZWNvbmRzLCBlbm91Z2ggZm9yIHRva2VuIHRvIGV4cGlyZVxuICAgICAgamVzdC51c2VSZWFsVGltZXJzKCk7XG5cbiAgICAgIGF3YWl0IGxpc3Rab29tTWVldGluZ3MobW9ja1pvb21Vc2VySWQpOyAvLyBTZWNvbmQgY2FsbCwgc2hvdWxkIHRyaWdnZXIgcmVmcmVzaFxuICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zLnBvc3QpLnRvSGF2ZUJlZW5DYWxsZWRUaW1lcygyKTsgLy8gVG9rZW4gcmVmcmVzaGVkXG4gICAgICAvLyBDaGVjayBpZiB0aGUgR0VUIGNhbGwgZm9yIHRoZSBzZWNvbmQgbGlzdFpvb21NZWV0aW5ncyB1c2VkIHRoZSByZWZyZXNoZWQgdG9rZW5cbiAgICAgIC8vIFRoaXMgcmVxdWlyZXMgaW5zcGVjdGluZyB0aGUgYWN0dWFsIGNhbGwgYXJndW1lbnRzIGlmIHRoZSBtb2NrIHNldHVwIGFsbG93cy5cbiAgICAgIC8vIFRoZSBjdXJyZW50IG1vY2sgc2V0dXAgZm9yIGF4aW9zLmdldCBtaWdodCBub3QgZWFzaWx5IGFsbG93IGRpcmVjdCBpbnNwZWN0aW9uIG9mIGhlYWRlcnMgZm9yIHRoZSAqc2Vjb25kKiBjYWxsIGlmIG5vdCByZXNldC5cbiAgICAgIC8vIEhvd2V2ZXIsIHRoZSBmYWN0IHRoYXQgUE9TVCB3YXMgY2FsbGVkIHR3aWNlIGlzIHRoZSBwcmltYXJ5IGluZGljYXRvciBvZiByZWZyZXNoLlxuICAgICAgLy8gVG8gdmVyaWZ5IHRoZSBoZWFkZXIsIHdlJ2QgbmVlZCBhIG1vcmUgZ3JhbnVsYXIgbW9jayBvciBjYXB0dXJlIGFyZ3VtZW50cy5cbiAgICAgIC8vIEZvciBub3csIHdlIGFzc3VtZSB0aGUgbmV3IHRva2VuIGZyb20gdGhlIHNlY29uZCBQT1NUIHdvdWxkIGJlIHVzZWQuXG4gICAgICAvLyBBIG1vcmUgcm9idXN0IHRlc3QgbWlnaHQgaW52b2x2ZSBjYXB0dXJpbmcgdGhlIHRva2VuIGluIGdldFpvb21BY2Nlc3NUb2tlbiBpZiBpdCB3ZXJlIGRpcmVjdGx5IHRlc3RhYmxlXG4gICAgICAvLyBvciBlbnN1cmluZyB0aGUgQXV0aG9yaXphdGlvbiBoZWFkZXIgaW4gdGhlIHNlY29uZCBHRVQgY2FsbCBpcyAnQmVhcmVyIHRva2VuX3JlZnJlc2hlZCcuXG4gICAgICAvLyBMZXQncyBjaGVjayB0aGUgbGFzdCBjYWxsIHRvIEdFVCAod2hpY2ggaXMgdGhlIHNlY29uZCBvbmUgaGVyZSlcbiAgICAgIGNvbnN0IGxhc3RHZXRDYWxsID1cbiAgICAgICAgbW9ja2VkQXhpb3MuZ2V0Lm1vY2suY2FsbHNbbW9ja2VkQXhpb3MuZ2V0Lm1vY2suY2FsbHMubGVuZ3RoIC0gMV07XG4gICAgICBleHBlY3QobGFzdEdldENhbGxbMV0/LmhlYWRlcnM/LkF1dGhvcml6YXRpb24pLnRvQmUoXG4gICAgICAgICdCZWFyZXIgdG9rZW5fcmVmcmVzaGVkJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIFpvb20gYXV0aCBBUEkgZmFpbHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrZWRBeGlvcy5wb3N0Lm1vY2tSZWplY3RlZFZhbHVlT25jZShuZXcgRXJyb3IoJ1pvb20gQXV0aCBGYWlsZWQnKSk7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBsaXN0Wm9vbU1lZXRpbmdzKG1vY2tab29tVXNlcklkKTtcbiAgICAgIGV4cGVjdChyZXN1bHQub2spLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcikudG9Db250YWluKCdGYWlsZWQgdG8gb2J0YWluIFpvb20gYWNjZXNzIHRva2VuLicpO1xuICAgICAgZXhwZWN0KGNvbnNvbGVFcnJvclNweSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgICdFcnJvciBvYnRhaW5pbmcgWm9vbSBhY2Nlc3MgdG9rZW46JyxcbiAgICAgICAgJ1pvb20gQXV0aCBGYWlsZWQnXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gZXJyb3IgaWYgWm9vbSBhdXRoIGNvbnN0YW50cyBhcmUgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGplc3Quc3B5T24oY29uc3RhbnRzLCAnQVRPTV9aT09NX0NMSUVOVF9JRCcsICdnZXQnKS5tb2NrUmV0dXJuVmFsdWUoJycpOyAvLyBTaW11bGF0ZSBtaXNzaW5nIGNsaWVudCBJRFxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbGlzdFpvb21NZWV0aW5ncyhtb2NrWm9vbVVzZXJJZCk7XG4gICAgICBleHBlY3QocmVzdWx0Lm9rKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChyZXN1bHQuZXJyb3IpLnRvQ29udGFpbignRmFpbGVkIHRvIG9idGFpbiBab29tIGFjY2VzcyB0b2tlbi4nKTsgLy8gVGhlIGdldFpvb21BY2Nlc3NUb2tlbiByZXR1cm5zIG51bGxcbiAgICAgIGV4cGVjdChjb25zb2xlRXJyb3JTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICAnWm9vbSBBUEkgY3JlZGVudGlhbHMgKEFjY291bnQgSUQsIENsaWVudCBJRCwgQ2xpZW50IFNlY3JldCkgbm90IGNvbmZpZ3VyZWQuJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2xpc3Rab29tTWVldGluZ3MnLCAoKSA9PiB7XG4gICAgY29uc3QgbW9ja1pvb21Vc2VySWQgPSAndXNlcjQ1Nic7XG4gICAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgICAvLyBFbnN1cmUgYSB2YWxpZCB0b2tlbiBpcyBtb2NrZWQgZm9yIHRoZXNlIHRlc3RzLCBhcyB0b2tlbiBsb2dpYyBpcyB0ZXN0ZWQgc2VwYXJhdGVseVxuICAgICAgbW9ja2VkQXhpb3MucG9zdC5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIGRhdGE6IHsgYWNjZXNzX3Rva2VuOiAndmFsaWRfdG9rZW5fZm9yX2xpc3QnLCBleHBpcmVzX2luOiAzNjAwIH0sXG4gICAgICAgIHN0YXR1czogMjAwLFxuICAgICAgfSk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIGxpc3QgbWVldGluZ3Mgc3VjY2Vzc2Z1bGx5JywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja01lZXRpbmdzRGF0YTogUGFydGlhbDxab29tTWVldGluZz5bXSA9IFtcbiAgICAgICAgeyBpZDogJ20xJywgdG9waWM6ICdNZWV0aW5nIDEnIH0sXG4gICAgICBdO1xuICAgICAgbW9ja2VkQXhpb3MuZ2V0Lm1vY2tSZXNvbHZlZFZhbHVlT25jZSh7XG4gICAgICAgIGRhdGE6IHtcbiAgICAgICAgICBtZWV0aW5nczogbW9ja01lZXRpbmdzRGF0YSxcbiAgICAgICAgICBuZXh0X3BhZ2VfdG9rZW46ICduZXh0X3Rva2VuX2hlcmUnLFxuICAgICAgICB9LFxuICAgICAgICBzdGF0dXM6IDIwMCxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBsaXN0Wm9vbU1lZXRpbmdzKG1vY2tab29tVXNlcklkLCB7XG4gICAgICAgIHR5cGU6ICd1cGNvbWluZycsXG4gICAgICAgIHBhZ2Vfc2l6ZTogMTAsXG4gICAgICB9KTtcbiAgICAgIGV4cGVjdChyZXN1bHQub2spLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QocmVzdWx0Lm1lZXRpbmdzKS50b0VxdWFsKG1vY2tNZWV0aW5nc0RhdGEpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5uZXh0X3BhZ2VfdG9rZW4pLnRvQmUoJ25leHRfdG9rZW5faGVyZScpO1xuICAgICAgZXhwZWN0KG1vY2tlZEF4aW9zLmdldCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgIGAke1pPT01fQVBJX0JBU0VfVVJMfS91c2Vycy8ke21vY2tab29tVXNlcklkfS9tZWV0aW5nc2AsXG4gICAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcbiAgICAgICAgICBoZWFkZXJzOiB7IEF1dGhvcml6YXRpb246ICdCZWFyZXIgdmFsaWRfdG9rZW5fZm9yX2xpc3QnIH0sXG4gICAgICAgICAgcGFyYW1zOiB7IHR5cGU6ICd1cGNvbWluZycsIHBhZ2Vfc2l6ZTogMTAgfSxcbiAgICAgICAgfSlcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIGhhbmRsZSBBUEkgZXJyb3Igd2hlbiBsaXN0aW5nIG1lZXRpbmdzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgYXBpRXJyb3IgPSB7XG4gICAgICAgIGlzQXhpb3NFcnJvcjogdHJ1ZSxcbiAgICAgICAgcmVzcG9uc2U6IHsgZGF0YTogeyBtZXNzYWdlOiAnRXJyb3IgZnJvbSBab29tIEFQSScgfSB9LFxuICAgICAgICBtZXNzYWdlOiAnUmVxdWVzdCBmYWlsZWQnLFxuICAgICAgfSBhcyBBeGlvc0Vycm9yO1xuICAgICAgbW9ja2VkQXhpb3MuZ2V0Lm1vY2tSZWplY3RlZFZhbHVlT25jZShhcGlFcnJvcik7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGxpc3Rab29tTWVldGluZ3MobW9ja1pvb21Vc2VySWQpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5vaykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmVycm9yKS50b0JlKCdFcnJvciBmcm9tIFpvb20gQVBJJyk7XG4gICAgICBleHBlY3QoY29uc29sZUVycm9yU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgYEVycm9yIGxpc3RpbmcgWm9vbSBtZWV0aW5ncyBmb3IgdXNlcklkICR7bW9ja1pvb21Vc2VySWR9OmAsXG4gICAgICAgICdSZXF1ZXN0IGZhaWxlZCdcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdnZXRab29tTWVldGluZ0RldGFpbHMnLCAoKSA9PiB7XG4gICAgY29uc3QgbW9ja01lZXRpbmdJZCA9ICdtZWV0aW5nNzg5JztcbiAgICBiZWZvcmVFYWNoKCgpID0+IHtcbiAgICAgIG1vY2tlZEF4aW9zLnBvc3QubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBkYXRhOiB7IGFjY2Vzc190b2tlbjogJ3ZhbGlkX3Rva2VuX2Zvcl9kZXRhaWxzJywgZXhwaXJlc19pbjogMzYwMCB9LFxuICAgICAgICBzdGF0dXM6IDIwMCxcbiAgICAgIH0pO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBnZXQgbWVldGluZyBkZXRhaWxzIHN1Y2Nlc3NmdWxseScsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tNZWV0aW5nRGV0YWlsRGF0YTogUGFydGlhbDxab29tTWVldGluZz4gPSB7XG4gICAgICAgIGlkOiBtb2NrTWVldGluZ0lkLFxuICAgICAgICB0b3BpYzogJ0RldGFpbGVkIE1lZXRpbmcgVG9waWMnLFxuICAgICAgfTtcbiAgICAgIG1vY2tlZEF4aW9zLmdldC5tb2NrUmVzb2x2ZWRWYWx1ZU9uY2Uoe1xuICAgICAgICBkYXRhOiBtb2NrTWVldGluZ0RldGFpbERhdGEsXG4gICAgICAgIHN0YXR1czogMjAwLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldFpvb21NZWV0aW5nRGV0YWlscyhtb2NrTWVldGluZ0lkKTtcbiAgICAgIGV4cGVjdChyZXN1bHQub2spLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QocmVzdWx0Lm1lZXRpbmcpLnRvRXF1YWwobW9ja01lZXRpbmdEZXRhaWxEYXRhKTtcbiAgICAgIGV4cGVjdChtb2NrZWRBeGlvcy5nZXQpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBgJHtaT09NX0FQSV9CQVNFX1VSTH0vbWVldGluZ3MvJHttb2NrTWVldGluZ0lkfWAsXG4gICAgICAgIGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcbiAgICAgICAgICBoZWFkZXJzOiB7IEF1dGhvcml6YXRpb246ICdCZWFyZXIgdmFsaWRfdG9rZW5fZm9yX2RldGFpbHMnIH0sXG4gICAgICAgIH0pXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCBoYW5kbGUgbWVldGluZyBub3QgZm91bmQgKDQwNCBlcnJvciknLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBheGlvc0Vycm9yID0ge1xuICAgICAgICBpc0F4aW9zRXJyb3I6IHRydWUsXG4gICAgICAgIHJlc3BvbnNlOiB7IHN0YXR1czogNDA0LCBkYXRhOiB7IG1lc3NhZ2U6ICdNZWV0aW5nIGRvZXMgbm90IGV4aXN0LicgfSB9LFxuICAgICAgICBtZXNzYWdlOiAnUmVxdWVzdCBmYWlsZWQgd2l0aCBzdGF0dXMgY29kZSA0MDQnLFxuICAgICAgfSBhcyBBeGlvc0Vycm9yO1xuICAgICAgbW9ja2VkQXhpb3MuZ2V0Lm1vY2tSZWplY3RlZFZhbHVlT25jZShheGlvc0Vycm9yKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgZ2V0Wm9vbU1lZXRpbmdEZXRhaWxzKCdub25fZXhpc3RlbnRfaWQnKTtcbiAgICAgIGV4cGVjdChyZXN1bHQub2spLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcikudG9Db250YWluKFxuICAgICAgICAnTWVldGluZyBub3QgZm91bmQgKElEOiBub25fZXhpc3RlbnRfaWQpLiBNZWV0aW5nIGRvZXMgbm90IGV4aXN0LidcbiAgICAgICk7XG4gICAgICBleHBlY3QoY29uc29sZUVycm9yU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgYEVycm9yIGdldHRpbmcgWm9vbSBtZWV0aW5nIGRldGFpbHMgZm9yIG1lZXRpbmdJZCBub25fZXhpc3RlbnRfaWQ6YCxcbiAgICAgICAgJ1JlcXVlc3QgZmFpbGVkIHdpdGggc3RhdHVzIGNvZGUgNDA0J1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgaGFuZGxlIG90aGVyIEFQSSBlcnJvcnMgd2hlbiBnZXR0aW5nIGRldGFpbHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBhcGlFcnJvciA9IHtcbiAgICAgICAgaXNBeGlvc0Vycm9yOiB0cnVlLFxuICAgICAgICByZXNwb25zZTogeyBkYXRhOiB7IG1lc3NhZ2U6ICdTb21lIG90aGVyIEFQSSBlcnJvcicgfSB9LFxuICAgICAgICBtZXNzYWdlOiAnUmVxdWVzdCBmYWlsZWQnLFxuICAgICAgfSBhcyBBeGlvc0Vycm9yO1xuICAgICAgbW9ja2VkQXhpb3MuZ2V0Lm1vY2tSZWplY3RlZFZhbHVlT25jZShhcGlFcnJvcik7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldFpvb21NZWV0aW5nRGV0YWlscyhtb2NrTWVldGluZ0lkKTtcbiAgICAgIGV4cGVjdChyZXN1bHQub2spLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5lcnJvcikudG9CZSgnU29tZSBvdGhlciBBUEkgZXJyb3InKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==