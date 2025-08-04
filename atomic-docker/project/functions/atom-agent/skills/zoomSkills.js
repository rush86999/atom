import axios from 'axios';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
const ZOOM_API_BASE_URL = 'https://api.zoom.us/v2';
const ZOOM_TOKEN_URL = 'https://zoom.us/oauth/token';
async function getZoomToken(userId) {
    const query = `
        query GetUserToken($userId: String!, $service: String!) {
            user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}) {
                access_token
                refresh_token
                expires_at
            }
        }
    `;
    const variables = {
        userId,
        service: 'zoom',
    };
    const response = await executeGraphQLQuery(query, variables, 'GetUserToken', userId);
    if (response.user_tokens && response.user_tokens.length > 0) {
        const token = response.user_tokens[0];
        const expiresAt = new Date(token.expires_at).getTime();
        if (Date.now() > expiresAt) {
            // Refresh the token
            const zoomClientId = process.env.ZOOM_CLIENT_ID;
            const zoomClientSecret = process.env.ZOOM_CLIENT_SECRET;
            if (!zoomClientId || !zoomClientSecret) {
                console.error('Zoom environment variables not configured for token refresh.');
                return null;
            }
            try {
                const refreshResponse = await axios.post(ZOOM_TOKEN_URL, new URLSearchParams({
                    grant_type: 'refresh_token',
                    refresh_token: token.refresh_token,
                }).toString(), {
                    headers: {
                        Authorization: `Basic ${Buffer.from(`${zoomClientId}:${zoomClientSecret}`).toString('base64')}`,
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                });
                if (refreshResponse.status === 200 &&
                    refreshResponse.data &&
                    refreshResponse.data.access_token) {
                    const newAccessToken = refreshResponse.data.access_token;
                    const newRefreshToken = refreshResponse.data.refresh_token;
                    const newExpiresIn = refreshResponse.data.expires_in;
                    const newExpiresAt = new Date(Date.now() + newExpiresIn * 1000).toISOString();
                    // Update the token in the database
                    const mutation = `
                        mutation UpdateUserToken($userId: String!, $service: String!, $accessToken: String!, $refreshToken: String, $expiresAt: timestamptz!) {
                            update_user_tokens(where: {user_id: {_eq: $userId}, service: {_eq: $service}}, _set: {access_token: $accessToken, refresh_token: $refreshToken, expires_at: $expiresAt}) {
                                returning {
                                    id
                                }
                            }
                        }
                    `;
                    const updateVariables = {
                        userId,
                        service: 'zoom',
                        accessToken: newAccessToken,
                        refreshToken: newRefreshToken,
                        expiresAt: newExpiresAt,
                    };
                    await executeGraphQLQuery(mutation, updateVariables, 'UpdateUserToken', userId);
                    return newAccessToken;
                }
            }
            catch (error) {
                console.error('Error refreshing Zoom token:', error);
                return null;
            }
        }
        return token.access_token;
    }
    return null;
}
export async function listZoomMeetings(userId, options) {
    console.log(`listZoomMeetings called for userId: ${userId} with options:`, options);
    const token = await getZoomToken(userId);
    if (!token) {
        return {
            ok: false,
            error: {
                code: 'ZOOM_AUTH_ERROR',
                message: 'Failed to obtain Zoom access token for listing meetings.',
            },
        };
    }
    const params = {
        type: options?.type || 'upcoming',
        page_size: options?.page_size || 30,
    };
    if (options?.next_page_token) {
        params.next_page_token = options.next_page_token;
    }
    try {
        const response = await axios.get(`${ZOOM_API_BASE_URL}/users/me/meetings`, {
            headers: { Authorization: `Bearer ${token}` },
            params: params,
        });
        return {
            ok: true,
            data: {
                meetings: response.data.meetings,
                page_count: response.data.page_count,
                page_number: response.data.page_number,
                page_size: response.data.page_size,
                total_records: response.data.total_records,
                next_page_token: response.data.next_page_token,
            },
        };
    }
    catch (error) {
        const axiosError = error;
        console.error(`Error listing Zoom meetings for userId ${userId}:`, axiosError.message);
        const errorData = axiosError.response?.data;
        return {
            ok: false,
            error: {
                code: errorData?.code ? `ZOOM_API_${errorData.code}` : 'ZOOM_API_ERROR',
                message: errorData?.message ||
                    axiosError.message ||
                    'Failed to list Zoom meetings',
                details: errorData,
            },
        };
    }
}
export async function getZoomMeetingDetails(userId, meetingId) {
    console.log(`getZoomMeetingDetails called for meetingId: ${meetingId}`);
    if (!meetingId || meetingId.trim() === '') {
        return {
            ok: false,
            error: { code: 'VALIDATION_ERROR', message: 'Meeting ID is required.' },
        };
    }
    const token = await getZoomToken(userId);
    if (!token) {
        return {
            ok: false,
            error: {
                code: 'ZOOM_AUTH_ERROR',
                message: 'Failed to obtain Zoom access token for getting meeting details.',
            },
        };
    }
    try {
        const response = await axios.get(`${ZOOM_API_BASE_URL}/meetings/${meetingId}`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        return { ok: true, data: response.data };
    }
    catch (error) {
        const axiosError = error;
        console.error(`Error getting Zoom meeting details for meetingId ${meetingId}:`, axiosError.message);
        const errorData = axiosError.response?.data;
        if (axiosError.response?.status === 404) {
            return {
                ok: false,
                error: {
                    code: 'MEETING_NOT_FOUND',
                    message: `Meeting not found (ID: ${meetingId}). ${errorData?.message || ''}`.trim(),
                    details: errorData,
                },
            };
        }
        return {
            ok: false,
            error: {
                code: errorData?.code ? `ZOOM_API_${errorData.code}` : 'ZOOM_API_ERROR',
                message: errorData?.message ||
                    axiosError.message ||
                    'Failed to get Zoom meeting details',
                details: errorData,
            },
        };
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiem9vbVNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInpvb21Ta2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxLQUFxQixNQUFNLE9BQU8sQ0FBQztBQUMxQyxPQUFPLEVBQUUsbUJBQW1CLEVBQUUsTUFBTSx3QkFBd0IsQ0FBQztBQVE3RCxNQUFNLGlCQUFpQixHQUFHLHdCQUF3QixDQUFDO0FBQ25ELE1BQU0sY0FBYyxHQUFHLDZCQUE2QixDQUFDO0FBRXJELEtBQUssVUFBVSxZQUFZLENBQUMsTUFBYztJQUN4QyxNQUFNLEtBQUssR0FBRzs7Ozs7Ozs7S0FRWCxDQUFDO0lBQ0osTUFBTSxTQUFTLEdBQUc7UUFDaEIsTUFBTTtRQUNOLE9BQU8sRUFBRSxNQUFNO0tBQ2hCLENBQUM7SUFDRixNQUFNLFFBQVEsR0FBRyxNQUFNLG1CQUFtQixDQU12QyxLQUFLLEVBQUUsU0FBUyxFQUFFLGNBQWMsRUFBRSxNQUFNLENBQUMsQ0FBQztJQUU3QyxJQUFJLFFBQVEsQ0FBQyxXQUFXLElBQUksUUFBUSxDQUFDLFdBQVcsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7UUFDNUQsTUFBTSxLQUFLLEdBQUcsUUFBUSxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUN0QyxNQUFNLFNBQVMsR0FBRyxJQUFJLElBQUksQ0FBQyxLQUFLLENBQUMsVUFBVSxDQUFDLENBQUMsT0FBTyxFQUFFLENBQUM7UUFFdkQsSUFBSSxJQUFJLENBQUMsR0FBRyxFQUFFLEdBQUcsU0FBUyxFQUFFLENBQUM7WUFDM0Isb0JBQW9CO1lBQ3BCLE1BQU0sWUFBWSxHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYyxDQUFDO1lBQ2hELE1BQU0sZ0JBQWdCLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxrQkFBa0IsQ0FBQztZQUV4RCxJQUFJLENBQUMsWUFBWSxJQUFJLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztnQkFDdkMsT0FBTyxD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QUFVLENBQUMsUUFBUSxFQUFFLElBQVcsQ0FBQztRQUVuRCxJQUFJLFVBQVUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxLQUFLLEdBQUcsRUFBRSxDQUFDO1lBQ3hDLE9BQU87Z0JBQ0wsRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSxtQkFBbUI7b0JBQ3pCLE9BQU8sRUFDTCwwQkFBMEIsU0FBUyxNQUFNLFNBQVMsRUFBRSxPQUFPLElBQUksRUFBRSxFQUFFLENBQUMsSUFBSSxFQUFFO29CQUM1RSxPQUFPLEVBQUUsU0FBUztpQkFDbkI7YUFDRixDQUFDO1FBQ0osQ0FBQztRQUNELE9BQU87WUFDTCxFQUFFLEVBQUUsS0FBSztZQUNULEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsU0FBUyxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsWUFBWSxTQUFTLENBQUMsSUFBSSxFQUFFLENBQUMsQ0FBQyxDQUFDLGdCQUFnQjtnQkFDdkUsT0FBTyxFQUNMLFNBQVMsRUFBRSxPQUFPO29CQUNsQixVQUFVLENBQUMsT0FBTztvQkFDbEIsb0NBQW9DO2dCQUN0QyxPQUFPLEVBQUUsU0FBUzthQUNuQjtTQUNGLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBheGlvcywgeyBBeGlvc0Vycm9yIH0gZnJvbSAnYXhpb3MnO1xuaW1wb3J0IHsgZXhlY3V0ZUdyYXBoUUxRdWVyeSB9IGZyb20gJy4uL19saWJzL2dyYXBocWxDbGllbnQnO1xuaW1wb3J0IHtcbiAgWm9vbU1lZXRpbmcsXG4gIFpvb21Ta2lsbFJlc3BvbnNlLFxuICBMaXN0Wm9vbU1lZXRpbmdzRGF0YSxcbiAgWm9vbVRva2VuUmVzcG9uc2UsXG59IGZyb20gJy4uL3R5cGVzJztcblxuY29uc3QgWk9PTV9BUElfQkFTRV9VUkwgPSAnaHR0cHM6Ly9hcGkuem9vbS51cy92Mic7XG5jb25zdCBaT09NX1RPS0VOX1VSTCA9ICdodHRwczovL3pvb20udXMvb2F1dGgvdG9rZW4nO1xuXG5hc3luYyBmdW5jdGlvbiBnZXRab29tVG9rZW4odXNlcklkOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZyB8IG51bGw+IHtcbiAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgIHF1ZXJ5IEdldFVzZXJUb2tlbigkdXNlcklkOiBTdHJpbmchLCAkc2VydmljZTogU3RyaW5nISkge1xuICAgICAgICAgICAgdXNlcl90b2tlbnMod2hlcmU6IHt1c2VyX2lkOiB7X2VxOiAkdXNlcklkfSwgc2VydmljZToge19lcTogJHNlcnZpY2V9fSkge1xuICAgICAgICAgICAgICAgIGFjY2Vzc190b2tlblxuICAgICAgICAgICAgICAgIHJlZnJlc2hfdG9rZW5cbiAgICAgICAgICAgICAgICBleHBpcmVzX2F0XG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICBgO1xuICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgdXNlcklkLFxuICAgIHNlcnZpY2U6ICd6b29tJyxcbiAgfTtcbiAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBleGVjdXRlR3JhcGhRTFF1ZXJ5PHtcbiAgICB1c2VyX3Rva2Vuczoge1xuICAgICAgYWNjZXNzX3Rva2VuOiBzdHJpbmc7XG4gICAgICByZWZyZXNoX3Rva2VuOiBzdHJpbmc7XG4gICAgICBleHBpcmVzX2F0OiBzdHJpbmc7XG4gICAgfVtdO1xuICB9PihxdWVyeSwgdmFyaWFibGVzLCAnR2V0VXNlclRva2VuJywgdXNlcklkKTtcblxuICBpZiAocmVzcG9uc2UudXNlcl90b2tlbnMgJiYgcmVzcG9uc2UudXNlcl90b2tlbnMubGVuZ3RoID4gMCkge1xuICAgIGNvbnN0IHRva2VuID0gcmVzcG9uc2UudXNlcl90b2tlbnNbMF07XG4gICAgY29uc3QgZXhwaXJlc0F0ID0gbmV3IERhdGUodG9rZW4uZXhwaXJlc19hdCkuZ2V0VGltZSgpO1xuXG4gICAgaWYgKERhdGUubm93KCkgPiBleHBpcmVzQXQpIHtcbiAgICAgIC8vIFJlZnJlc2ggdGhlIHRva2VuXG4gICAgICBjb25zdCB6b29tQ2xpZW50SWQgPSBwcm9jZXNzLmVudi5aT09NX0NMSUVOVF9JRDtcbiAgICAgIGNvbnN0IHpvb21DbGllbnRTZWNyZXQgPSBwcm9jZXNzLmVudi5aT09NX0NMSUVOVF9TRUNSRVQ7XG5cbiAgICAgIGlmICghem9vbUNsaWVudElkIHx8ICF6b29tQ2xpZW50U2VjcmV0KSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgJ1pvb20gZW52aXJvbm1lbnQgdmFyaWFibGVzIG5vdCBjb25maWd1cmVkIGZvciB0b2tlbiByZWZyZXNoLidcbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIG51bGw7XG4gICAgICB9XG5cbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IHJlZnJlc2hSZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3Q8Wm9vbVRva2VuUmVzcG9uc2U+KFxuICAgICAgICAgIFpPT01fVE9LRU5fVVJMLFxuICAgICAgICAgIG5ldyBVUkxTZWFyY2hQYXJhbXMoe1xuICAgICAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgICAgICAgcmVmcmVzaF90b2tlbjogdG9rZW4ucmVmcmVzaF90b2tlbixcbiAgICAgICAgICB9KS50b1N0cmluZygpLFxuICAgICAgICAgIHtcbiAgICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJhc2ljICR7QnVmZmVyLmZyb20oYCR7em9vbUNsaWVudElkfToke3pvb21DbGllbnRTZWNyZXR9YCkudG9TdHJpbmcoJ2Jhc2U2NCcpfWAsXG4gICAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24veC13d3ctZm9ybS11cmxlbmNvZGVkJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfVxuICAgICAgICApO1xuXG4gICAgICAgIGlmIChcbiAgICAgICAgICByZWZyZXNoUmVzcG9uc2Uuc3RhdHVzID09PSAyMDAgJiZcbiAgICAgICAgICByZWZyZXNoUmVzcG9uc2UuZGF0YSAmJlxuICAgICAgICAgIHJlZnJlc2hSZXNwb25zZS5kYXRhLmFjY2Vzc190b2tlblxuICAgICAgICApIHtcbiAgICAgICAgICBjb25zdCBuZXdBY2Nlc3NUb2tlbiA9IHJlZnJlc2hSZXNwb25zZS5kYXRhLmFjY2Vzc190b2tlbjtcbiAgICAgICAgICBjb25zdCBuZXdSZWZyZXNoVG9rZW4gPSByZWZyZXNoUmVzcG9uc2UuZGF0YS5yZWZyZXNoX3Rva2VuO1xuICAgICAgICAgIGNvbnN0IG5ld0V4cGlyZXNJbiA9IHJlZnJlc2hSZXNwb25zZS5kYXRhLmV4cGlyZXNfaW47XG4gICAgICAgICAgY29uc3QgbmV3RXhwaXJlc0F0ID0gbmV3IERhdGUoXG4gICAgICAgICAgICBEYXRlLm5vdygpICsgbmV3RXhwaXJlc0luICogMTAwMFxuICAgICAgICAgICkudG9JU09TdHJpbmcoKTtcblxuICAgICAgICAgIC8vIFVwZGF0ZSB0aGUgdG9rZW4gaW4gdGhlIGRhdGFiYXNlXG4gICAgICAgICAgY29uc3QgbXV0YXRpb24gPSBgXG4gICAgICAgICAgICAgICAgICAgICAgICBtdXRhdGlvbiBVcGRhdGVVc2VyVG9rZW4oJHVzZXJJZDogU3RyaW5nISwgJHNlcnZpY2U6IFN0cmluZyEsICRhY2Nlc3NUb2tlbjogU3RyaW5nISwgJHJlZnJlc2hUb2tlbjogU3RyaW5nLCAkZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiEpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVfdXNlcl90b2tlbnMod2hlcmU6IHt1c2VyX2lkOiB7X2VxOiAkdXNlcklkfSwgc2VydmljZToge19lcTogJHNlcnZpY2V9fSwgX3NldDoge2FjY2Vzc190b2tlbjogJGFjY2Vzc1Rva2VuLCByZWZyZXNoX3Rva2VuOiAkcmVmcmVzaFRva2VuLCBleHBpcmVzX2F0OiAkZXhwaXJlc0F0fSkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgYDtcbiAgICAgICAgICBjb25zdCB1cGRhdGVWYXJpYWJsZXMgPSB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICBzZXJ2aWNlOiAnem9vbScsXG4gICAgICAgICAgICBhY2Nlc3NUb2tlbjogbmV3QWNjZXNzVG9rZW4sXG4gICAgICAgICAgICByZWZyZXNoVG9rZW46IG5ld1JlZnJlc2hUb2tlbixcbiAgICAgICAgICAgIGV4cGlyZXNBdDogbmV3RXhwaXJlc0F0LFxuICAgICAgICAgIH07XG4gICAgICAgICAgYXdhaXQgZXhlY3V0ZUdyYXBoUUxRdWVyeShcbiAgICAgICAgICAgIG11dGF0aW9uLFxuICAgICAgICAgICAgdXBkYXRlVmFyaWFibGVzLFxuICAgICAgICAgICAgJ1VwZGF0ZVVzZXJUb2tlbicsXG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICApO1xuXG4gICAgICAgICAgcmV0dXJuIG5ld0FjY2Vzc1Rva2VuO1xuICAgICAgICB9XG4gICAgICB9IGNhdGNoIChlcnJvcikge1xuICAgICAgICBjb25zb2xlLmVycm9yKCdFcnJvciByZWZyZXNoaW5nIFpvb20gdG9rZW46JywgZXJyb3IpO1xuICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgIH1cbiAgICB9XG4gICAgcmV0dXJuIHRva2VuLmFjY2Vzc190b2tlbjtcbiAgfVxuICByZXR1cm4gbnVsbDtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGxpc3Rab29tTWVldGluZ3MoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBvcHRpb25zPzoge1xuICAgIHR5cGU/OlxuICAgICAgfCAnbGl2ZSdcbiAgICAgIHwgJ3VwY29taW5nJ1xuICAgICAgfCAnc2NoZWR1bGVkJ1xuICAgICAgfCAndXBjb21pbmdfbWVldGluZ3MnXG4gICAgICB8ICdwcmV2aW91c19tZWV0aW5ncyc7XG4gICAgcGFnZV9zaXplPzogbnVtYmVyO1xuICAgIG5leHRfcGFnZV90b2tlbj86IHN0cmluZztcbiAgfVxuKTogUHJvbWlzZTxab29tU2tpbGxSZXNwb25zZTxMaXN0Wm9vbU1lZXRpbmdzRGF0YT4+IHtcbiAgY29uc29sZS5sb2coXG4gICAgYGxpc3Rab29tTWVldGluZ3MgY2FsbGVkIGZvciB1c2VySWQ6ICR7dXNlcklkfSB3aXRoIG9wdGlvbnM6YCxcbiAgICBvcHRpb25zXG4gICk7XG5cbiAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRab29tVG9rZW4odXNlcklkKTtcbiAgaWYgKCF0b2tlbikge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnWk9PTV9BVVRIX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byBvYnRhaW4gWm9vbSBhY2Nlc3MgdG9rZW4gZm9yIGxpc3RpbmcgbWVldGluZ3MuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIGNvbnN0IHBhcmFtczogUmVjb3JkPHN0cmluZywgYW55PiA9IHtcbiAgICB0eXBlOiBvcHRpb25zPy50eXBlIHx8ICd1cGNvbWluZycsXG4gICAgcGFnZV9zaXplOiBvcHRpb25zPy5wYWdlX3NpemUgfHwgMzAsXG4gIH07XG4gIGlmIChvcHRpb25zPy5uZXh0X3BhZ2VfdG9rZW4pIHtcbiAgICBwYXJhbXMubmV4dF9wYWdlX3Rva2VuID0gb3B0aW9ucy5uZXh0X3BhZ2VfdG9rZW47XG4gIH1cblxuICB0cnkge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgYXhpb3MuZ2V0PFxuICAgICAgeyBtZWV0aW5nczogWm9vbU1lZXRpbmdbXSB9ICYgTGlzdFpvb21NZWV0aW5nc0RhdGFcbiAgICA+KGAke1pPT01fQVBJX0JBU0VfVVJMfS91c2Vycy9tZS9tZWV0aW5nc2AsIHtcbiAgICAgIGhlYWRlcnM6IHsgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAgfSxcbiAgICAgIHBhcmFtczogcGFyYW1zLFxuICAgIH0pO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIG9rOiB0cnVlLFxuICAgICAgZGF0YToge1xuICAgICAgICBtZWV0aW5nczogcmVzcG9uc2UuZGF0YS5tZWV0aW5ncyBhcyBab29tTWVldGluZ1tdLFxuICAgICAgICBwYWdlX2NvdW50OiByZXNwb25zZS5kYXRhLnBhZ2VfY291bnQsXG4gICAgICAgIHBhZ2VfbnVtYmVyOiByZXNwb25zZS5kYXRhLnBhZ2VfbnVtYmVyLFxuICAgICAgICBwYWdlX3NpemU6IHJlc3BvbnNlLmRhdGEucGFnZV9zaXplLFxuICAgICAgICB0b3RhbF9yZWNvcmRzOiByZXNwb25zZS5kYXRhLnRvdGFsX3JlY29yZHMsXG4gICAgICAgIG5leHRfcGFnZV90b2tlbjogcmVzcG9uc2UuZGF0YS5uZXh0X3BhZ2VfdG9rZW4sXG4gICAgICB9LFxuICAgIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zdCBheGlvc0Vycm9yID0gZXJyb3IgYXMgQXhpb3NFcnJvcjtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEVycm9yIGxpc3RpbmcgWm9vbSBtZWV0aW5ncyBmb3IgdXNlcklkICR7dXNlcklkfTpgLFxuICAgICAgYXhpb3NFcnJvci5tZXNzYWdlXG4gICAgKTtcbiAgICBjb25zdCBlcnJvckRhdGEgPSBheGlvc0Vycm9yLnJlc3BvbnNlPy5kYXRhIGFzIGFueTtcbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogZXJyb3JEYXRhPy5jb2RlID8gYFpPT01fQVBJXyR7ZXJyb3JEYXRhLmNvZGV9YCA6ICdaT09NX0FQSV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgZXJyb3JEYXRhPy5tZXNzYWdlIHx8XG4gICAgICAgICAgYXhpb3NFcnJvci5tZXNzYWdlIHx8XG4gICAgICAgICAgJ0ZhaWxlZCB0byBsaXN0IFpvb20gbWVldGluZ3MnLFxuICAgICAgICBkZXRhaWxzOiBlcnJvckRhdGEsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldFpvb21NZWV0aW5nRGV0YWlscyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG1lZXRpbmdJZDogc3RyaW5nXG4pOiBQcm9taXNlPFpvb21Ta2lsbFJlc3BvbnNlPFpvb21NZWV0aW5nPj4ge1xuICBjb25zb2xlLmxvZyhgZ2V0Wm9vbU1lZXRpbmdEZXRhaWxzIGNhbGxlZCBmb3IgbWVldGluZ0lkOiAke21lZXRpbmdJZH1gKTtcblxuICBpZiAoIW1lZXRpbmdJZCB8fCBtZWV0aW5nSWQudHJpbSgpID09PSAnJykge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjogeyBjb2RlOiAnVkFMSURBVElPTl9FUlJPUicsIG1lc3NhZ2U6ICdNZWV0aW5nIElEIGlzIHJlcXVpcmVkLicgfSxcbiAgICB9O1xuICB9XG5cbiAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRab29tVG9rZW4odXNlcklkKTtcbiAgaWYgKCF0b2tlbikge1xuICAgIHJldHVybiB7XG4gICAgICBvazogZmFsc2UsXG4gICAgICBlcnJvcjoge1xuICAgICAgICBjb2RlOiAnWk9PTV9BVVRIX0VSUk9SJyxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAnRmFpbGVkIHRvIG9idGFpbiBab29tIGFjY2VzcyB0b2tlbiBmb3IgZ2V0dGluZyBtZWV0aW5nIGRldGFpbHMuJyxcbiAgICAgIH0sXG4gICAgfTtcbiAgfVxuXG4gIHRyeSB7XG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5nZXQ8Wm9vbU1lZXRpbmc+KFxuICAgICAgYCR7Wk9PTV9BUElfQkFTRV9VUkx9L21lZXRpbmdzLyR7bWVldGluZ0lkfWAsXG4gICAgICB7XG4gICAgICAgIGhlYWRlcnM6IHsgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAgfSxcbiAgICAgIH1cbiAgICApO1xuICAgIHJldHVybiB7IG9rOiB0cnVlLCBkYXRhOiByZXNwb25zZS5kYXRhIH07XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBjb25zdCBheGlvc0Vycm9yID0gZXJyb3IgYXMgQXhpb3NFcnJvcjtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEVycm9yIGdldHRpbmcgWm9vbSBtZWV0aW5nIGRldGFpbHMgZm9yIG1lZXRpbmdJZCAke21lZXRpbmdJZH06YCxcbiAgICAgIGF4aW9zRXJyb3IubWVzc2FnZVxuICAgICk7XG4gICAgY29uc3QgZXJyb3JEYXRhID0gYXhpb3NFcnJvci5yZXNwb25zZT8uZGF0YSBhcyBhbnk7XG5cbiAgICBpZiAoYXhpb3NFcnJvci5yZXNwb25zZT8uc3RhdHVzID09PSA0MDQpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnTUVFVElOR19OT1RfRk9VTkQnLFxuICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICBgTWVldGluZyBub3QgZm91bmQgKElEOiAke21lZXRpbmdJZH0pLiAke2Vycm9yRGF0YT8ubWVzc2FnZSB8fCAnJ31gLnRyaW0oKSxcbiAgICAgICAgICBkZXRhaWxzOiBlcnJvckRhdGEsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cbiAgICByZXR1cm4ge1xuICAgICAgb2s6IGZhbHNlLFxuICAgICAgZXJyb3I6IHtcbiAgICAgICAgY29kZTogZXJyb3JEYXRhPy5jb2RlID8gYFpPT01fQVBJXyR7ZXJyb3JEYXRhLmNvZGV9YCA6ICdaT09NX0FQSV9FUlJPUicsXG4gICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgZXJyb3JEYXRhPy5tZXNzYWdlIHx8XG4gICAgICAgICAgYXhpb3NFcnJvci5tZXNzYWdlIHx8XG4gICAgICAgICAgJ0ZhaWxlZCB0byBnZXQgWm9vbSBtZWV0aW5nIGRldGFpbHMnLFxuICAgICAgICBkZXRhaWxzOiBlcnJvckRhdGEsXG4gICAgICB9LFxuICAgIH07XG4gIH1cbn1cbiJdfQ==