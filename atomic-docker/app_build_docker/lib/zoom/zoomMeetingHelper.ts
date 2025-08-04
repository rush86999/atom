import { Linking } from 'react-native';
import axios from 'axios';
import qs from 'qs';

import {
  zoomName,
  zoomResourceName,
  zoomCreateMeetingUrl,
  zoomUpdateMeetingUrl,
  zoomDeleteMeetingUrl,
  zoomOAuthStartUrl,
} from '@lib/zoom/constants';
import {
  CreateMeetingResponseType,
  CreateZoomMeetObjectType,
  UpdateZoomMeetObjectType,
  DeleteZoomMeetObjectType,
} from '@lib/zoom/types';

import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import getCalendarIntegrationByResource from '@lib/apollo/gql/getCalendarIntegrationByResourceAndName';
import { CalendarIntegrationType } from '@lib/dataTypes/Calendar_IntegrationType';
import Session from 'supertokens-web-js/recipe/session';

export const zoomAvailable = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const calIntObject = (
      await client.query<{ Calendar_Integration: CalendarIntegrationType[] }>({
        query: getCalendarIntegrationByResource,
        variables: {
          userId,
          name: zoomName,
          resource: zoomResourceName,
        },
      })
    ).data?.Calendar_Integration?.[0];
    if (calIntObject?.enabled) {
      return true;
    }
    return false;
  } catch (e) {
    console.log(e, ' unable to get zoom availability');
  }
};

export const createZoomMeeting = async (
  userId: string,
  startDate: string,
  timezone: string,
  agenda: string,
  duration: number,
  contactName?: string,
  contactEmail?: string,
  meetingInvitees?: string[],
  privateMeeting?: boolean
) => {
  try {
    if (startDate) {
      throw new Error('no startDate present inside createZoomMeeting');
    }

    if (!timezone) {
      throw new Error('no timezone inside createZoomMeeting');
    }

    if (!agenda) {
      throw new Error('no agenda inside createZoomMeeting');
    }

    if (!duration) {
      throw new Error('no duration inside createZoomMeeting');
    }

    if (!userId) {
      throw new Error('no userId inside createZoomMeeting');
    }

    const accessToken = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    };

    const data: CreateZoomMeetObjectType = {
      startDate,
      timezone,
      agenda,
      duration,
      userId,
      contactName,
      contactEmail,
      meetingInvitees,
      privateMeeting,
    };

    const url = zoomCreateMeetingUrl;

    const results = await axios.post<CreateMeetingResponseType>(
      url,
      data,
      config
    );

    const {
      data: { join_url, id, start_url, status },
    } = results;

    return { id, join_url, start_url, status };
  } catch (e) {
    console.log(e, ' unabel to create zoom meeting');
  }
};

export const deleteZoomMeeting = async (
  userId: string,
  meetingId: number,
  scheduleForReminder?: boolean,
  cancelMeetingReminder?: string
) => {
  try {
    if (typeof meetingId !== 'number') {
      console.log('id was not properly parsed to int ');
      return;
    }

    if (!userId) {
      throw new Error('no userId inside deleteZoomMeeting');
    }

    const url = zoomDeleteMeetingUrl;

    const accessToken = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    };

    const data: DeleteZoomMeetObjectType = {
      meetingId,
      userId,
      scheduleForReminder,
      cancelMeetingReminder,
    };

    const results = await axios.post(url, data, config);
    console.log(results, ' successfully deleted meeting');
  } catch (e) {
    console.log(e, '  unable to delete zoom meeting');
  }
};

export const updateZoomMeeting = async (
  userId: string,
  meetingId: number,
  startDate?: string,
  timezone?: string,
  agenda?: string,
  duration?: number,
  contactName?: string,
  contactEmail?: string,
  meetingInvitees?: string[],
  privateMeeting?: boolean
) => {
  try {
    if (!userId) {
      throw new Error('no userId inside updateZoomMeeting');
    }

    if (typeof meetingId !== 'number') {
      throw new Error(
        'id was not properly parsed to int  inside updateZoomMeeting'
      );
    }

    const url = zoomUpdateMeetingUrl;

    const data: UpdateZoomMeetObjectType = {
      userId,
      meetingId,
      startDate,
      timezone,
      agenda,
      duration,
      contactName,
      contactEmail,
      meetingInvitees,
      privateMeeting,
    };

    const accessToken = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    };

    const results = await axios.post<CreateMeetingResponseType>(
      url,
      data,
      config
    );

    const {
      data: { join_url, id, start_url, status },
    } = results;

    return { id, join_url, start_url, status };
  } catch (e) {
    console.log(e, ' unable to update zoom meeting');
  }
};
