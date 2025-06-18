import axios, { AxiosError } from 'axios';
import {
  ATOM_ZOOM_ACCOUNT_ID,
  ATOM_ZOOM_CLIENT_ID,
  ATOM_ZOOM_CLIENT_SECRET,
} from '../_libs/constants';
import {
  ZoomMeeting,
  ListZoomMeetingsResponse,
  GetZoomMeetingDetailsResponse,
  ZoomTokenResponse,
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

async function getZoomAccessToken(): Promise<string | null> {
  if (zoomAccessToken && tokenExpiryTime && Date.now() < tokenExpiryTime) {
    return zoomAccessToken;
  }

  if (!ATOM_ZOOM_ACCOUNT_ID || !ATOM_ZOOM_CLIENT_ID || !ATOM_ZOOM_CLIENT_SECRET) {
    console.error('Zoom API credentials (Account ID, Client ID, Client Secret) not configured.');
    return null;
  }

  try {
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
      // Set expiry time with a 5-minute buffer (300 seconds) before actual expiry
      tokenExpiryTime = Date.now() + (tokenData.expires_in - 300) * 1000;
      console.log('Successfully obtained new Zoom access token.');
      return zoomAccessToken;
    } else {
      console.error('Failed to obtain Zoom access token. Response:', response.data);
      return null;
    }
  } catch (error) {
    const axiosError = error as AxiosError;
    console.error('Error obtaining Zoom access token:', axiosError.message);
    if (axiosError.response) {
      console.error('Zoom token API Error Response Data:', axiosError.response.data);
      console.error('Zoom token API Error Response Status:', axiosError.response.status);
    }
    // Ensure cache is cleared on failure to prevent using a stale/invalid token if one was partially set before error
    resetTokenCache();
    return null;
  }
}

export async function listZoomMeetings(
  zoomUserId: string, // Typically "me" for Server-to-Server OAuth, or a specific user ID.
  options?: {
    type?: 'live' | 'upcoming' | 'scheduled' | 'upcoming_meetings' | 'previous_meetings'; // Added more common types
    page_size?: number;
    next_page_token?: string;
  }
): Promise<ListZoomMeetingsResponse> {
  console.log(`listZoomMeetings called for zoomUserId: ${zoomUserId} with options:`, options);
  const token = await getZoomAccessToken();
  if (!token) {
    return { ok: false, error: 'Failed to obtain Zoom access token.' };
  }

  const params: any = {
    type: options?.type || 'upcoming',
    page_size: options?.page_size || 30,
  };
  if (options?.next_page_token) {
    params.next_page_token = options.next_page_token;
  }

  try {
    const response = await axios.get(`${ZOOM_API_BASE_URL}/users/${zoomUserId}/meetings`, {
      headers: { 'Authorization': `Bearer ${token}` },
      params: params,
    });

    // The Zoom API response for list meetings includes pagination fields at the root level
    // and the actual meetings in a 'meetings' array.
    return {
      ok: true,
      meetings: response.data.meetings as ZoomMeeting[],
      page_count: response.data.page_count,
      page_number: response.data.page_number,
      page_size: response.data.page_size,
      total_records: response.data.total_records,
      next_page_token: response.data.next_page_token,
    };
  } catch (error) {
    const axiosError = error as AxiosError;
    console.error(`Error listing Zoom meetings for userId ${zoomUserId}:`, axiosError.message);
    const errorResponse = axiosError.response?.data as any;
    return {
        ok: false,
        error: errorResponse?.message || axiosError.message || 'Failed to list Zoom meetings'
    };
  }
}

export async function getZoomMeetingDetails(meetingId: string): Promise<GetZoomMeetingDetailsResponse> {
  console.log(`getZoomMeetingDetails called for meetingId: ${meetingId}`);
  const token = await getZoomAccessToken();
  if (!token) {
    return { ok: false, error: 'Failed to obtain Zoom access token.' };
  }

  try {
    const response = await axios.get(`${ZOOM_API_BASE_URL}/meetings/${meetingId}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    return { ok: true, meeting: response.data as ZoomMeeting };
  } catch (error) {
    const axiosError = error as AxiosError;
    console.error(`Error getting Zoom meeting details for meetingId ${meetingId}:`, axiosError.message);
    const errorResponse = axiosError.response?.data as any;

    if (axiosError.response?.status === 404) {
        return { ok: false, error: `Meeting not found (ID: ${meetingId}). ${errorResponse?.message || ''}`.trim() };
    }
    return {
        ok: false,
        error: errorResponse?.message || axiosError.message || 'Failed to get Zoom meeting details'
    };
  }
}
