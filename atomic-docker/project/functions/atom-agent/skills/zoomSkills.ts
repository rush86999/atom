import axios, { AxiosError } from 'axios';
import {
  ATOM_ZOOM_ACCOUNT_ID,
  ATOM_ZOOM_CLIENT_ID,
  ATOM_ZOOM_CLIENT_SECRET,
} from '../_libs/constants';
import {
  ZoomMeeting,
  // ListZoomMeetingsResponse, // Superseded by ZoomSkillResponse<ListZoomMeetingsData>
  // GetZoomMeetingDetailsResponse, // Superseded by ZoomSkillResponse<ZoomMeeting>
  ZoomSkillResponse, // New generic response type
  ListZoomMeetingsData, // New data payload type
  ZoomTokenResponse,
  SkillError, // Standardized error type
} from '../types';

const ZOOM_API_BASE_URL = 'https://api.zoom.us/v2';
const ZOOM_TOKEN_URL = 'https://zoom.us/oauth/token';

// Export for testing token cache reset
export let zoomAccessToken: string | null = null;
export let tokenExpiryTime: number | null = null;

export const resetTokenCache = () => {
  zoomAccessToken = null;
  tokenExpiryTime = null;
};

async function getZoomAccessToken(): Promise<ZoomSkillResponse<string>> {
  if (zoomAccessToken && tokenExpiryTime && Date.now() < tokenExpiryTime) {
    console.log('Using cached Zoom access token.');
    return { ok: true, data: zoomAccessToken };
  }

  if (!ATOM_ZOOM_ACCOUNT_ID || !ATOM_ZOOM_CLIENT_ID || !ATOM_ZOOM_CLIENT_SECRET) {
    const errorMsg = 'Zoom API credentials (Account ID, Client ID, Client Secret) not configured.';
    console.error(errorMsg);
    return { ok: false, error: { code: 'ZOOM_CONFIG_ERROR', message: errorMsg } };
  }

  try {
    console.log('Requesting new Zoom access token...');
    const basicAuth = Buffer.from(`${ATOM_ZOOM_CLIENT_ID}:${ATOM_ZOOM_CLIENT_SECRET}`).toString('base64');
    const response = await axios.post<ZoomTokenResponse>(
      ZOOM_TOKEN_URL,
      new URLSearchParams({
        grant_type: 'account_credentials',
        account_id: ATOM_ZOOM_ACCOUNT_ID,
      }).toString(),
      {
        headers: {
          'Authorization': `Basic ${basicAuth}`,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    if (response.status === 200 && response.data && response.data.access_token) {
      const tokenData = response.data;
      zoomAccessToken = tokenData.access_token;
      tokenExpiryTime = Date.now() + (tokenData.expires_in - 300) * 1000; // 5-min buffer
      console.log('Successfully obtained new Zoom access token.');
      return { ok: true, data: zoomAccessToken };
    } else {
      console.error('Failed to obtain Zoom access token. Response Status:', response.status, 'Data:', response.data);
      resetTokenCache();
      return { ok: false, error: { code: 'ZOOM_AUTH_ERROR', message: 'Failed to obtain Zoom access token from API.', details: response.data } };
    }
  } catch (error) {
    const axiosError = error as AxiosError;
    console.error('Error obtaining Zoom access token:', axiosError.message);
    if (axiosError.response) {
      console.error('Zoom token API Error Response Data:', axiosError.response.data);
      console.error('Zoom token API Error Response Status:', axiosError.response.status);
    }
    resetTokenCache();
    return {
        ok: false,
        error: {
            code: 'ZOOM_AUTH_REQUEST_FAILED',
            message: `Error requesting Zoom access token: ${axiosError.message}`,
            details: axiosError.response?.data
        }
    };
  }
}

export async function listZoomMeetings(
  zoomUserId: string, // Typically "me" for Server-to-Server OAuth
  options?: {
    type?: 'live' | 'upcoming' | 'scheduled' | 'upcoming_meetings' | 'previous_meetings';
    page_size?: number;
    next_page_token?: string;
  }
): Promise<ZoomSkillResponse<ListZoomMeetingsData>> {
  console.log(`listZoomMeetings called for zoomUserId: ${zoomUserId} with options:`, options);

  const tokenResponse = await getZoomAccessToken();
  if (!tokenResponse.ok || !tokenResponse.data) {
    return { ok: false, error: tokenResponse.error || { code: 'ZOOM_AUTH_ERROR', message: 'Failed to obtain Zoom access token for listing meetings.'} };
  }
  const token = tokenResponse.data;

  const params: Record<string, any> = { // Use Record for better type safety on params
    type: options?.type || 'upcoming',
    page_size: options?.page_size || 30,
  };
  if (options?.next_page_token) {
    params.next_page_token = options.next_page_token;
  }

  try {
    const response = await axios.get<{ meetings: ZoomMeeting[] } & ListZoomMeetingsData>( // Type the expected axios response
        `${ZOOM_API_BASE_URL}/users/${zoomUserId}/meetings`,
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
    console.error(`Error listing Zoom meetings for userId ${zoomUserId}:`, axiosError.message);
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

export async function getZoomMeetingDetails(meetingId: string): Promise<ZoomSkillResponse<ZoomMeeting>> {
  console.log(`getZoomMeetingDetails called for meetingId: ${meetingId}`);

  if (!meetingId || meetingId.trim() === '') {
    return { ok: false, error: { code: 'VALIDATION_ERROR', message: 'Meeting ID is required.'}};
  }

  const tokenResponse = await getZoomAccessToken();
  if (!tokenResponse.ok || !tokenResponse.data) {
     return { ok: false, error: tokenResponse.error || { code: 'ZOOM_AUTH_ERROR', message: 'Failed to obtain Zoom access token for getting meeting details.'} };
  }
  const token = tokenResponse.data;

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
