import got from 'got';
import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import {
  hasuraAdminSecret,
  hasuraGraphUrl,
  zoomBaseTokenUrl,
  zoomBaseUrl,
  zoomClientId,
  zoomClientSecret,
  zoomIVForPass,
  zoomPassKey,
  zoomResourceName,
  zoomSaltForPass,
} from './constants';
import {
  CalendarIntegrationType,
  CreateMeetingResponseType,
  CreateZoomMeetingRequestBodyType,
  ZoomMeetingObjectType,
} from './types';
import qs from 'qs';
import axios from 'axios';
import crypto from 'crypto';

dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);

// update zoom meeting
export const updateZoomMeetingStartDate = async (
  zoomToken: string,
  meetingId: number,
  startDate: string,
  timezone: string
) => {
  try {
    const reqBody = {
      start_time: dayjs(startDate?.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss'),
      timezone,
    };

    await got
      .patch(`${zoomBaseUrl}/meetings/${meetingId}`, {
        json: reqBody,
        headers: {
          Authorization: `Bearer ${zoomToken}`,
          ContentType: 'application/json',
        },
      })
      .json();

    console.log(meetingId, 'successfully patched zoom meeting starting date');
  } catch (e) {
    console.log(e, ' unable to update zoom meeting');
  }
};

export const updateZoomMeeting = async (
  zoomToken: string,
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
    //valdiate
    if (startDate && dayjs().isAfter(dayjs(startDate))) {
      console.log(' starttime is in the past');
      throw new Error('starttime is in the past');
    }

    let settings: any = {};

    if (privateMeeting) {
      settings = { ...settings, private_meeting: privateMeeting };
    }

    if (contactName?.length > 0 && contactEmail?.length > 0) {
      settings = {
        contact_name: contactName,
        contact_email: contactEmail,
      };
    }

    if (meetingInvitees?.length > 0) {
      settings = { ...settings, meeting_invitees: meetingInvitees };
    }

    let reqBody: any = {};

    if (Object.keys(settings)?.length > 0) {
      reqBody.settings = settings;
    }

    if (startDate && timezone) {
      reqBody.start_time = dayjs(startDate?.slice(0, 19)).format(
        'YYYY-MM-DDTHH:mm:ss'
      );
      reqBody.timezone = timezone;
    }

    if (agenda) {
      reqBody.agenda = agenda;
    }

    if (duration) {
      reqBody.duration = duration;
    }

    await got
      .patch(`${zoomBaseUrl}/meetings/${meetingId}`, {
        json: reqBody,
        headers: {
          Authorization: `Bearer ${zoomToken}`,
          ContentType: 'application/json',
        },
      })
      .json();

    console.log(meetingId, 'successfully patched zoom meeting starting date');
  } catch (e) {
    console.log(e, ' unable to update zoom meeting');
  }
};

export const createZoomMeeting = async (
  zoomToken: string,
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
    //valdiate
    if (dayjs().isAfter(dayjs(startDate))) {
      console.log(' starttime is in the past');
      throw new Error('starttime is in the past');
    }

    console.log(
      dayjs(startDate?.slice(0, 19))
        .tz(timezone, true)
        .format('YYYY-MM-DDTHH:mm:ss'),
      timezone,
      agenda,
      duration,
      ` dayjs(startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DDTHH:mm:ss'),
            timezone,
            agenda,
            duration, createZoomMeeting called`
    );

    let settings: any = {};

    if (contactName?.length > 0 && contactEmail?.length > 0) {
      settings = {
        contact_name: contactName,
        contact_email: contactEmail,
      };
    }

    if (meetingInvitees?.length > 0) {
      settings = {
        ...settings,
        meeting_invitees: meetingInvitees?.map((m) => ({ email: m })),
      };
    }

    if (privateMeeting) {
      settings.private_meeting = true;
    }

    let reqBody: CreateZoomMeetingRequestBodyType = {};

    if (Object.keys(settings)?.length > 0) {
      reqBody.settings = settings;
    }

    reqBody = {
      ...reqBody,
      start_time: dayjs(startDate?.slice(0, 19))
        .tz(timezone, true)
        .utc()
        .format(),
      // timezone,
      agenda,
      duration,
    };

    console.log(reqBody, ' reqBody inside createZoomMeeting');

    const res: ZoomMeetingObjectType = await got
      .post(`${zoomBaseUrl}/users/me/meetings`, {
        json: reqBody,
        headers: {
          Authorization: `Bearer ${zoomToken}`,
          ContentType: 'application/json',
        },
      })
      .json();

    console.log(res, ' res inside createZoomMeeting');

    return res;
  } catch (e) {
    console.log(e, ' unable to create zoom meeting');
  }
};

export const getZoomMeeting = async (zoomToken: string, meetingId: number) => {
  try {
    const res: CreateMeetingResponseType = await got(
      `${zoomBaseUrl}/meetings/${meetingId}`,
      {
        headers: {
          Authorization: `Bearer ${zoomToken}`,
          ContentType: 'application/json',
        },
      }
    ).json();

    return res;
  } catch (e) {
    console.log(e, ' unable to get zoom meeting');
  }
};

export const deleteZoomMeeting = async (
  zoomToken: string,
  meetingId: number,
  scheduleForReminder?: boolean,
  cancelMeetingReminder?: boolean
) => {
  try {
    let params: any = {};
    if (cancelMeetingReminder || scheduleForReminder) {
      if (cancelMeetingReminder) {
        params = { cancel_meeting_reminder: cancelMeetingReminder };
      }

      if (scheduleForReminder) {
        params = { ...params, schedule_for_reminder: scheduleForReminder };
      }
    }

    const stringifiedObject =
      Object.keys(params)?.length > 0 ? qs.stringify(params) : '';

    if (stringifiedObject) {
      await got.delete(
        `${zoomBaseUrl}/meetings/` + meetingId + '?' + stringifiedObject,
        {
          headers: {
            Authorization: `Bearer ${zoomToken}`,
            ContentType: 'application/json',
          },
        }
      );
    } else {
      await got.delete(`${zoomBaseUrl}/meetings/` + meetingId, {
        headers: {
          Authorization: `Bearer ${zoomToken}`,
          ContentType: 'application/json',
        },
      });
    }

    console.log(meetingId, 'successfully deleted meeting');
  } catch (e) {
    console.log(e, ' unable to delete zoom meeting');
  }
};

export const refreshZoomToken = async (
  refreshToken: string
): Promise<{
  access_token: string;
  token_type: 'bearer';
  refresh_token: string;
  expires_in: number;
  scope: string;
}> => {
  try {
    const username = zoomClientId;
    const password = zoomClientSecret;

    return axios({
      data: new URLSearchParams({
        refresh_token: refreshToken,
        grant_type: 'refresh_token',
      }).toString(),
      baseURL: zoomBaseTokenUrl,
      url: '/oauth/token',
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      auth: {
        username,
        password,
      },
    }).then(({ data }) => Promise.resolve(data));
  } catch (e) {
    console.log(e, ' unable to refresh zoom token');
  }
};

export const getCalendarIntegration = async (
  userId: string,
  resource: string
) => {
  try {
    const operationName = 'getCalendarIntegration';
    const query = `
      query getCalendarIntegration($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
          token
          expiresAt
          id
          refreshToken
          resource
          name
          clientType
        }
      }
    `;
    const variables = {
      userId,
      resource,
    };

    const res: { data: { Calendar_Integration: CalendarIntegrationType[] } } =
      await got
        .post(hasuraGraphUrl, {
          json: {
            operationName,
            query,
            variables,
          },
          headers: {
            'X-Hasura-Admin-Secret': hasuraAdminSecret,
            'Content-Type': 'application/json',
            'X-Hasura-Role': 'admin',
          },
        })
        .json();

    console.log(res, ' res inside getCalendarIntegration');
    if (res?.data?.Calendar_Integration?.length > 0) {
      return res?.data?.Calendar_Integration?.[0];
    }
  } catch (e) {
    console.log(e, ' unable to get calendar integration');
  }
};

export const updateCalendarIntegration = async (
  id: string,
  token?: string,
  expiresIn?: number,
  enabled?: boolean
) => {
  try {
    const operationName = 'updateCalendarIntegration';
    const query = `
      mutation updateCalendarIntegration($id: uuid!,${token !== undefined ? ' $token: String,' : ''}${expiresIn !== undefined ? ' $expiresAt: timestamptz,' : ''}${enabled !== undefined ? ' $enabled: Boolean,' : ''}) {
        update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {${token !== undefined ? 'token: $token,' : ''}${expiresIn !== undefined ? ' expiresAt: $expiresAt,' : ''}${enabled !== undefined ? ' enabled: $enabled,' : ''}}) {
          id
          name
          refreshToken
          token
          clientType
          userId
          updatedAt
        }
      }
    `;
    const variables = {
      id,
      token,
      expiresAt: dayjs().add(expiresIn, 'seconds').toISOString(),
      enabled,
    };

    const res = await got
      .post(hasuraGraphUrl, {
        json: {
          operationName,
          query,
          variables,
        },
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
      })
      .json();

    console.log(res, ' res inside updateCalendarIntegration');
  } catch (e) {
    console.log(e, ' unable to update calendar integration');
  }
};

export const decryptZoomTokens = (
  encryptedToken: string,
  encryptedRefreshToken?: string
) => {
  const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
  const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');

  const key = crypto.pbkdf2Sync(
    zoomPassKey as string,
    saltBuffer,
    10000,
    32,
    'sha256'
  );

  const decipherToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer);
  let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8');
  decryptedToken += decipherToken.final('utf8');

  if (encryptedRefreshToken) {
    const decipherRefreshToken = crypto.createDecipheriv(
      'aes-256-cbc',
      key,
      ivBuffer
    );
    let decryptedRefreshToken = decipherRefreshToken.update(
      encryptedRefreshToken,
      'base64',
      'utf8'
    );
    decryptedRefreshToken += decipherRefreshToken.final('utf8');

    return {
      token: decryptedToken,
      refreshToken: decryptedRefreshToken,
    };
  }

  return {
    token: decryptedToken,
  };
};

export const encryptZoomTokens = (token: string, refreshToken?: string) => {
  const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
  const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');

  const key = crypto.pbkdf2Sync(
    zoomPassKey as string,
    saltBuffer,
    10000,
    32,
    'sha256'
  );
  const cipherToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer);
  let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
  encryptedToken += cipherToken.final('base64');

  let encryptedRefreshToken = '';

  if (refreshToken) {
    const cipherRefreshToken = crypto.createCipheriv(
      'aes-256-cbc',
      key,
      ivBuffer
    );
    encryptedRefreshToken = cipherRefreshToken.update(
      refreshToken,
      'utf8',
      'base64'
    );
    encryptedRefreshToken += cipherRefreshToken.final('base64');
  }

  if (encryptedRefreshToken) {
    return {
      encryptedToken,
      encryptedRefreshToken,
    };
  } else {
    return { encryptedToken };
  }
};

export const getZoomIntegration = async (userId: string) => {
  try {
    const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(
      userId,
      zoomResourceName
    );

    const decryptedTokens = decryptZoomTokens(token, refreshToken);

    return {
      id,
      expiresAt,
      ...decryptedTokens,
    };
  } catch (e) {
    console.log(e, ' unable to get zoom integration');
  }
};

export const updateZoomIntegration = async (
  id: string,
  accessToken: string,
  expiresIn: number
) => {
  try {
    const { encryptedToken } = encryptZoomTokens(accessToken);
    await updateCalendarIntegration(id, encryptedToken, expiresIn);
  } catch (e) {
    console.log(e, ' unable to update zoom integration');
  }
};

export const getZoomAPIToken = async (userId: string) => {
  let integrationId = '';
  try {
    console.log('getZoomAPIToken called');
    const { id, token, expiresAt, refreshToken } =
      await getZoomIntegration(userId);
    integrationId = id;
    console.log(
      id,
      token,
      expiresAt,
      refreshToken,
      ' id, token, expiresAt, refreshToken'
    );
    if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
      const res = await refreshZoomToken(refreshToken);
      console.log(res, ' res from refreshZoomToken');
      await updateZoomIntegration(id, res.access_token, res.expires_in);
      return res.access_token;
    }

    return token;
  } catch (e) {
    console.log(e, ' unable to get zoom api token');
    await updateCalendarIntegration(integrationId, null, null, false);
  }
};
