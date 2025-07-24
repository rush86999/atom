import axios, { AxiosError } from 'axios';
import { executeGraphQLQuery } from '../_libs/graphqlClient';
import {
  ZoomMeeting,
  ZoomSkillResponse,
  ListZoomMeetingsData,
  ZoomTokenResponse,
} from '../types';

const ZOOM_API_BASE_URL = 'https://api.zoom.us/v2';
const ZOOM_TOKEN_URL = 'https://zoom.us/oauth/token';

async function getZoomToken(userId: string): Promise<string | null> {
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
    const response = await executeGraphQLQuery<{ user_tokens: { access_token: string, refresh_token: string, expires_at: string }[] }>(query, variables, 'GetUserToken', userId);

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
                const refreshResponse = await axios.post<ZoomTokenResponse>(
                    ZOOM_TOKEN_URL,
                    new URLSearchParams({
                        grant_type: 'refresh_token',
                        refresh_token: token.refresh_token,
                    }).toString(),
                    {
                        headers: {
                            'Authorization': `Basic ${Buffer.from(`${zoomClientId}:${zoomClientSecret}`).toString('base64')}`,
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                    }
                );

                if (refreshResponse.status === 200 && refreshResponse.data && refreshResponse.data.access_token) {
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
            } catch (error) {
                console.error('Error refreshing Zoom token:', error);
                return null;
            }
        }
        return token.access_token;
    }
    return null;
}

export async function listZoomMeetings(
  userId: string,
  options?: {
    type?: 'live' | 'upcoming' | 'scheduled' | 'upcoming_meetings' | 'previous_meetings';
    page_size?: number;
    next_page_token?: string;
  }
): Promise<ZoomSkillResponse<ListZoomMeetingsData>> {
  console.log(`listZoomMeetings called for userId: ${userId} with options:`, options);

  const token = await getZoomToken(userId);
  if (!token) {
    return { ok: false, error: { code: 'ZOOM_AUTH_ERROR', message: 'Failed to obtain Zoom access token for listing meetings.'} };
  }

  const params: Record<string, any> = {
    type: options?.type || 'upcoming',
    page_size: options?.page_size || 30,
  };
  if (options?.next_page_token) {
    params.next_page_token = options.next_page_token;
  }

  try {
    const response = await axios.get<{ meetings: ZoomMeeting[] } & ListZoomMeetingsData>(
        `${ZOOM_API_BASE_URL}/users/me/meetings`,
        {
            headers: { 'Authorization': `Bearer ${token}` },
            params: params,
        }
    );

    return {
      ok: true,
      data: {
        meetings: response.data.meetings as ZoomMeeting[],
        page_count: response.data.page_count,
        page_number: response.data.page_number,
        page_size: response.data.page_size,
        total_records: response.data.total_records,
        next_page_token: response.data.next_page_token,
      }
    };
  } catch (error: any) {
    const axiosError = error as AxiosError;
    console.error(`Error listing Zoom meetings for userId ${userId}:`, axiosError.message);
    const errorData = axiosError.response?.data as any;
    return {
        ok: false,
        error: {
            code: errorData?.code ? `ZOOM_API_${errorData.code}` : 'ZOOM_API_ERROR',
            message: errorData?.message || axiosError.message || 'Failed to list Zoom meetings',
            details: errorData
        }
    };
  }
}

export async function getZoomMeetingDetails(userId: string, meetingId: string): Promise<ZoomSkillResponse<ZoomMeeting>> {
  console.log(`getZoomMeetingDetails called for meetingId: ${meetingId}`);

  if (!meetingId || meetingId.trim() === '') {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Meeting ID is required.'}};
  }

  const token = await getZoomToken(userId);
  if (!token) {
     return { ok: false, error: { code: 'ZOOM_AUTH_ERROR', message: 'Failed to obtain Zoom access token for getting meeting details.'} };
  }

  try {
    const response = await axios.get<ZoomMeeting>(`${ZOOM_API_BASE_URL}/meetings/${meetingId}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    return { ok: true, data: response.data };
  } catch (error: any) {
    const axiosError = error as AxiosError;
    console.error(`Error getting Zoom meeting details for meetingId ${meetingId}:`, axiosError.message);
    const errorData = axiosError.response?.data as any;

    if (axiosError.response?.status === 404) {
        return {
            ok: false,
            error: {
                code: 'MEETING_NOT_FOUND',
                message: `Meeting not found (ID: ${meetingId}). ${errorData?.message || ''}`.trim(),
                details: errorData
            }
        };
    }
    return {
        ok: false,
        error: {
            code: errorData?.code ? `ZOOM_API_${errorData.code}` : 'ZOOM_API_ERROR',
            message: errorData?.message || axiosError.message || 'Failed to get Zoom meeting details',
            details: errorData
        }
    };
  }
}