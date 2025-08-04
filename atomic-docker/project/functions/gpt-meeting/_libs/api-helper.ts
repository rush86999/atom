import {
  ATOMIC_SUBDOMAIN_PATTERN,
  MAX_CHARACTER_LIMIT,
  NUMBER_TO_REMOVE_FOR_SUBDOMAIN_SLICE,
  defaultOpenAIAPIKey,
  googleCalendarResource,
  googleClientIdAndroid,
  googleClientIdAtomicWeb,
  googleClientIdIos,
  googleClientIdWeb,
  googleClientSecretAtomicWeb,
  googleClientSecretWeb,
  googleTokenUrl,
  hasuraAdminSecret,
  hasuraGraphUrl,
  openAIChatGPTModel,
  zoomBaseTokenUrl,
  zoomBaseUrl,
  zoomClientId,
  zoomClientSecret,
  zoomIVForPass,
  zoomPassKey,
  zoomResourceName,
  zoomSaltForPass,
} from './constants';
import qs from 'qs';
import {
  AttendeeType,
  CalendarIntegrationType,
  CalendarType,
  ConferenceType,
  CreateZoomMeetingRequestBodyType,
  EventType,
  ExtractDateTimeObjectType,
  GoogleAttachmentType,
  GoogleAttendeeType,
  GoogleConferenceDataType,
  GoogleEventType1,
  GoogleExtendedPropertiesType,
  GoogleReminderType,
  GoogleResType,
  GoogleSendUpdatesType,
  GoogleSourceType,
  GoogleTransparencyType,
  GoogleVisibilityType,
  MeetingUrlQueryParamsType,
  ReminderType,
  SummaryAndNotesObjectType,
  UserOpenAIType,
  UserPreferenceType,
  ZoomMeetingObjectType,
  isMeetingScheduledObjectType,
} from './types/genericTypes';
import crypto from 'crypto';
import got from 'got';
import { v4 as uuid } from 'uuid';
import OpenAI from 'openai';
import {
  extractDateTimeExampleInput,
  extractDateTimeExampleOutput,
  extractDateTimePrompt,
  generateMeetingSummaryInput,
  generateMeetingSummaryOutput,
  generateMeetingSummaryPrompt,
  isMeetingTimeScheduledExampleInput,
  isMeetingTimeScheduledExampleOutput,
  isMeetingTimeScheduledPrompt,
  summarizeAvailabilityExampleInput,
  summarizeAvailabilityExampleOutput,
  summarizeAvailabilityPrompt,
  summarizeAvailabilityResponsesPrompt,
  summarizeAvailabilityResponsesPromptExampleInput,
  summarizeAvailabilityResponsesPromptExampleOutput,
} from './prompts';
import { google } from 'googleapis';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import axios from 'axios';
import _ from 'lodash';
import * as cheerio from 'cheerio';
import quotedPrintable from 'quoted-printable';
import {
  AvailableSlotType,
  DayAvailabilityType,
  NotAvailableSlotType,
  SummarizeDayAvailabilityType,
} from './types/availabilityTypes';
import { getISODay } from 'date-fns';
import { ChatGPTRoleType } from './types/ChatGPTTypes';

dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);

export const callOpenAI = async (
  prompt: string,
  model: 'gpt-3.5-turbo' = 'gpt-3.5-turbo',
  userData: string,
  openai: OpenAI,
  exampleInput?: string,
  exampleOutput?: string
) => {
  try {
    // assistant
    const completion = await openai.chat.completions.create({
      model,
      messages: [
        { role: 'system' as ChatGPTRoleType, content: prompt },
        exampleInput && {
          role: 'user' as ChatGPTRoleType,
          content: exampleInput,
        },
        exampleOutput && {
          role: 'assistant' as ChatGPTRoleType,
          content: exampleOutput,
        },
        { role: 'user' as ChatGPTRoleType, content: userData },
      ]?.filter((m) => !!m),
    });
    console.log(
      completion.choices[0]?.message?.content,
      ' response from openaiapi'
    );

    return completion?.choices?.[0]?.message?.content;
  } catch (error) {
    if (error.response) {
      console.log(error.response.status, ' openai error status');
      console.log(error.response.data, ' openai error data');
    } else {
      console.log(error.message, ' openai error message');
    }
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

export const getGlobalCalendar = async (userId: string) => {
  try {
    const operationName = 'getGlobalCalendar';
    const query = `
        query getGlobalCalendar($userId: uuid!) {
          Calendar(where: {globalPrimary: {_eq: true}, userId: {_eq: $userId}}) {
            colorId
            backgroundColor
            accessLevel
            account
            createdDate
            defaultReminders
            foregroundColor
            globalPrimary
            id
            modifiable
            primary
            resource
            title
            updatedAt
            userId
          }
        }
    `;

    const res: { data: { Calendar: CalendarType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            userId,
          },
        },
      })
      .json();

    return res.data.Calendar?.[0];
  } catch (e) {
    console.log(e, ' unable to get global calendar');
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
export const getZoomAPIToken = async (userId: string) => {
  let integrationId = '';
  try {
    console.log('getZoomAPIToken called');
    const { id, token, expiresAt, refreshToken } =
      await getZoomIntegration(userId);
    if (!refreshToken) {
      console.log('zoom not active, no refresh token');
      return;
    }

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

export const createZoomMeeting = async (
  zoomToken: string,
  startDate: string,
  timezone: string,
  agenda: string,
  duration: number,
  contactName?: string,
  contactEmail?: string,
  meetingInvitees?: string[]
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
export const refreshGoogleToken = async (
  refreshToken: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web'
): Promise<{
  access_token: string;
  expires_in: number; // add seconds to now
  scope: string;
  token_type: string;
}> => {
  try {
    console.log('refreshGoogleToken called', refreshToken);
    console.log('clientType', clientType);
    console.log('googleClientIdIos', googleClientIdIos);
    switch (clientType) {
      case 'ios':
        return got
          .post(googleTokenUrl, {
            form: {
              grant_type: 'refresh_token',
              refresh_token: refreshToken,
              client_id: googleClientIdIos,
            },
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          })
          .json();
      case 'android':
        return got
          .post(googleTokenUrl, {
            form: {
              grant_type: 'refresh_token',
              refresh_token: refreshToken,
              client_id: googleClientIdAndroid,
            },
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          })
          .json();
      case 'web':
        return got
          .post(googleTokenUrl, {
            form: {
              grant_type: 'refresh_token',
              refresh_token: refreshToken,
              client_id: googleClientIdWeb,
              client_secret: googleClientSecretWeb,
            },
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          })
          .json();
      case 'atomic-web':
        return got
          .post(googleTokenUrl, {
            form: {
              grant_type: 'refresh_token',
              refresh_token: refreshToken,
              client_id: googleClientIdAtomicWeb,
              client_secret: googleClientSecretAtomicWeb,
            },
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          })
          .json();
    }

    /*  
        {
          "access_token": "1/fFAGRNJru1FTz70BzhT3Zg",
          "expires_in": 3920, // add seconds to now
          "scope": "https://www.googleapis.com/auth/drive.metadata.readonly",
          "token_type": "Bearer"
        }
        */
  } catch (e) {
    console.log(e, ' unable to refresh google token');
  }
};

export const getGoogleAPIToken = async (
  userId: string,
  resource: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web'
) => {
  let integrationId = '';
  try {
    const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(
      userId,
      resource
    );
    integrationId = id;
    console.log(
      id,
      token,
      expiresAt,
      refreshToken,
      ' id, token, expiresAt, refreshToken'
    );
    if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
      const res = await refreshGoogleToken(refreshToken, clientType);
      console.log(res, ' res from refreshGoogleToken');
      await updateCalendarIntegration(id, res.access_token, res.expires_in);
      return res.access_token;
    }
    return token;
  } catch (e) {
    console.log(e, ' unable to get api token');
    await updateCalendarIntegration(integrationId, null, null, false);
  }
};

export const createGoogleEvent = async (
  userId: string,
  calendarId: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web',
  generatedId?: string,
  endDateTime?: string, // either endDateTime or endDate - all day vs specific period
  startDateTime?: string,
  conferenceDataVersion?: 0 | 1,
  maxAttendees?: number,
  sendUpdates?: GoogleSendUpdatesType,
  anyoneCanAddSelf?: boolean,
  attendees?: GoogleAttendeeType[],
  conferenceData?: GoogleConferenceDataType,
  summary?: string,
  description?: string,
  timezone?: string, // required for recurrence
  startDate?: string, // all day
  endDate?: string, // all day
  extendedProperties?: GoogleExtendedPropertiesType,
  guestsCanInviteOthers?: boolean,
  guestsCanModify?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalStartDateTime?: string,
  originalStartDate?: string,
  recurrence?: string[],
  reminders?: GoogleReminderType,
  source?: GoogleSourceType,
  status?: string,
  transparency?: GoogleTransparencyType,
  visibility?: GoogleVisibilityType,
  iCalUID?: string,
  attendeesOmitted?: boolean,
  hangoutLink?: string,
  privateCopy?: boolean,
  locked?: boolean,
  attachments?: GoogleAttachmentType[],
  eventType?: GoogleEventType1,
  location?: string,
  colorId?: string
): Promise<GoogleResType> => {
  try {
    console.log(
      generatedId,
      conferenceDataVersion,
      conferenceData,
      ' generatedId, conferenceDataVersion, conferenceData inside createGoogleEvent'
    );
    // get token =
    const token = await getGoogleAPIToken(
      userId,
      googleCalendarResource,
      clientType
    );

    const googleCalendar = google.calendar({
      version: 'v3',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    // create request body
    let data: any = {};

    if (endDateTime && timezone && !endDate) {
      const end = {
        dateTime: endDateTime,
        timeZone: timezone,
      };

      data.end = end;
    }

    if (endDate && timezone && !endDateTime) {
      const end = {
        date: dayjs(endDate.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };

      data.end = end;
    }

    if (startDate && timezone && !startDateTime) {
      const start = {
        date: dayjs(startDate.slice(0, 19))
          .tz(timezone, true)
          .format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      data.start = start;
    }

    if (startDateTime && timezone && !startDate) {
      const start = {
        dateTime: startDateTime,
        timeZone: timezone,
      };
      data.start = start;
    }

    if (originalStartDate && timezone && !originalStartDateTime) {
      const originalStartTime = {
        date: originalStartDate,
        timeZone: timezone,
      };
      data.originalStartTime = originalStartTime;
    }

    if (originalStartDateTime && timezone && !originalStartDate) {
      const originalStartTime = {
        dateTime: dayjs(originalStartDateTime).tz(timezone, true).format(),
        timeZone: timezone,
      };
      data.originalStartTime = originalStartTime;
    }

    if (anyoneCanAddSelf) {
      data = { ...data, anyoneCanAddSelf };
    }

    if (attendees?.[0]?.email) {
      data = { ...data, attendees };
    }

    if (conferenceData?.createRequest) {
      data = {
        ...data,
        conferenceData: {
          createRequest: {
            conferenceSolutionKey: {
              type: conferenceData.type,
            },
            requestId: conferenceData?.requestId || uuid(),
          },
        },
      };
    } else if (conferenceData?.entryPoints?.[0]) {
      data = {
        ...data,
        conferenceData: {
          conferenceSolution: {
            iconUri: conferenceData?.iconUri,
            key: {
              type: conferenceData?.type,
            },
            name: conferenceData?.name,
          },
          entryPoints: conferenceData?.entryPoints,
        },
      };
    }

    if (description?.length > 0) {
      data = { ...data, description };
    }

    if (extendedProperties?.private || extendedProperties?.shared) {
      data = { ...data, extendedProperties };
    }

    if (guestsCanInviteOthers) {
      data = { ...data, guestsCanInviteOthers };
    }

    if (guestsCanModify) {
      data = { ...data, guestsCanModify };
    }

    if (guestsCanSeeOtherGuests) {
      data = { ...data, guestsCanSeeOtherGuests };
    }

    if (locked) {
      data = { ...data, locked };
    }

    if (privateCopy) {
      data = { ...data, privateCopy };
    }

    if (recurrence?.[0]) {
      data = { ...data, recurrence };
    }

    if (reminders?.overrides?.length > 0 || reminders?.useDefault) {
      data = { ...data, reminders };
    }

    if (source?.title || source?.url) {
      data = { ...data, source };
    }

    if (attachments?.[0]?.fileId) {
      data = { ...data, attachments };
    }

    if (eventType?.length > 0) {
      data = { ...data, eventType };
    }

    if (status) {
      data = { ...data, status };
    }

    if (transparency) {
      data = { ...data, transparency };
    }

    if (visibility) {
      data = { ...data, visibility };
    }

    if (iCalUID?.length > 0) {
      data = { ...data, iCalUID };
    }

    if (attendeesOmitted) {
      data = { ...data, attendeesOmitted };
    }

    if (hangoutLink?.length > 0) {
      data = { ...data, hangoutLink };
    }

    if (summary?.length > 0) {
      data = { ...data, summary };
    }

    if (location?.length > 0) {
      data = { ...data, location };
    }

    if (colorId) {
      data.colorId = colorId;
    }

    const res = await googleCalendar.events.insert({
      // Calendar identifier. To retrieve calendar IDs call the calendarList.list method. If you want to access the primary calendar of the currently logged in user, use the "primary" keyword.
      calendarId,
      // Version number of conference data supported by the API client. Version 0 assumes no conference data support and ignores conference data in the event's body. Version 1 enables support for copying of ConferenceData as well as for creating new conferences using the createRequest field of conferenceData. The default is 0.
      conferenceDataVersion,
      // The maximum number of attendees to include in the response. If there are more than the specified number of attendees, only the participant is returned. Optional.
      maxAttendees,
      // Whether to send notifications about the creation of the new event. Note that some emails might still be sent. The default is false.
      sendUpdates,

      // Request body metadata
      requestBody: data,
    });

    console.log(res.data);

    console.log(res?.data, ' res?.data from googleCreateEvent');
    return {
      id: `${res?.data?.id}#${calendarId}`,
      googleEventId: res?.data?.id,
      generatedId,
      calendarId,
      generatedEventId: generatedId?.split('#')[0],
    };
  } catch (e) {
    console.log(e, ' createGoogleEvent');
  }
};

export const upsertEvents = async (events: EventType[]) => {
  try {
    const operationName = 'InsertEvent';
    const query = `
            mutation InsertEvent($events: [Event_insert_input!]!) {
                insert_Event(
                    objects: $events,
                    on_conflict: {
                        constraint: Event_pkey,
                        update_columns: [
                            userId,
                            title,
                            startDate,
                            endDate,
                            allDay,
                            recurrenceRule,
                            location,
                            notes,
                            attachments,
                            links,
                            timezone,
                            createdDate,
                            deleted,
                            taskId,
                            taskType,
                            priority,
                            followUpEventId,
                            isFollowUp,
                            isPreEvent,
                            isPostEvent,
                            preEventId,
                            postEventId,
                            modifiable,
                            forEventId,
                            conferenceId,
                            maxAttendees,
                            sendUpdates,
                            anyoneCanAddSelf,
                            guestsCanInviteOthers,
                            guestsCanSeeOtherGuests,
                            originalStartDate,
                            originalAllDay,
                            status,
                            summary,
                            transparency,
                            visibility,
                            recurringEventId,
                            updatedAt,
                            iCalUID,
                            htmlLink,
                            colorId,
                            creator,
                            organizer,
                            endTimeUnspecified,
                            recurrence,
                            originalTimezone,
                            attendeesOmitted,
                            extendedProperties,
                            hangoutLink,
                            guestsCanModify,
                            locked,
                            source,
                            eventType,
                            privateCopy,
                            calendarId,
                            backgroundColor,
                            foregroundColor,
                            useDefaultAlarms,
                            positiveImpactScore,
                            negativeImpactScore,
                            positiveImpactDayOfWeek,
                            positiveImpactTime,
                            negativeImpactDayOfWeek,
                            negativeImpactTime,
                            preferredDayOfWeek,
                            preferredTime,
                            isExternalMeeting,
                            isExternalMeetingModifiable,
                            isMeetingModifiable,
                            isMeeting,
                            dailyTaskList,
                            weeklyTaskList,
                            isBreak,
                            preferredStartTimeRange,
                            preferredEndTimeRange,
                            copyAvailability,
                            copyTimeBlocking,
                            copyTimePreference,
                            copyReminders,
                            copyPriorityLevel,
                            copyModifiable,
                            copyCategories,
                            copyIsBreak,
                            timeBlocking,
                            userModifiedAvailability,
                            userModifiedTimeBlocking,
                            userModifiedTimePreference,
                            userModifiedReminders,
                            userModifiedPriorityLevel,
                            userModifiedCategories,
                            userModifiedModifiable,
                            userModifiedIsBreak,
                            hardDeadline,
                            softDeadline,
                            copyIsMeeting,
                            copyIsExternalMeeting,
                            userModifiedIsMeeting,
                            userModifiedIsExternalMeeting,
                            duration,
                            copyDuration,
                            userModifiedDuration,
                            unlink,
                            copyColor,
                            userModifiedColor,
                            byWeekDay,
                            localSynced,
                            meetingId,
                            eventId,
                        ]
                    }){
                    returning {
                        id
                    }
                    affected_rows
                }
            }
        `;
    _.uniqBy(events, 'id').forEach((e) =>
      console.log(e?.id, e, 'id, e inside upsertEventsPostPlanner ')
    );
    const variables = {
      events: _.uniqBy(events, 'id'),
    };

    const response: {
      data: {
        insert_Event: { affected_rows: number; returning: { id: string }[] };
      };
    } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();
    console.log(
      response,
      response?.data?.insert_Event?.affected_rows,
      ' response after upserting events'
    );
    response?.data?.insert_Event?.returning?.forEach((e) =>
      console.log(e, ' returning  response after upserting events')
    );
    return response;
  } catch (e) {
    console.log(e, ' unable to update event');
  }
};

export const insertReminders = async (reminders: ReminderType[]) => {
  try {
    // validate
    if (!(reminders?.filter((e) => !!e?.eventId)?.length > 0)) {
      return;
    }

    reminders.forEach((r) =>
      console.log(r, ' reminder inside insertReminders')
    );

    const operationName = 'InsertReminder';
    const query = `
            mutation InsertReminder($reminders: [Reminder_insert_input!]!) {
                insert_Reminder(objects: $reminders) {
                    affected_rows
                    returning {
                        id
                        createdDate
                        deleted
                        eventId
                        method
                        minutes
                        reminderDate
                        timezone
                        updatedAt
                        useDefault
                        userId
                    }
                }
            }
        `;
    const variables = {
      reminders,
    };

    const response: {
      data: { insert_Reminder: { returning: ReminderType[] } };
    } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(
      response?.data?.insert_Reminder?.returning,
      ' this is response in insertReminders'
    );
    response?.data?.insert_Reminder?.returning.forEach((r) =>
      console.log(r, ' response in insertReminder')
    );
  } catch (e) {
    console.log(e, ' unable to insertReminders');
  }
};

export const insertConference = async (conference: ConferenceType) => {
  try {
    const operationName = 'InsertConference';
    const query = `
            mutation InsertConference($conference: Conference_insert_input!) {
                insert_Conference_one(object: $conference) {
                    app
                    calendarId
                    createdDate
                    deleted
                    entryPoints
                    hangoutLink
                    iconUri
                    id
                    isHost
                    joinUrl
                    key
                    name
                    notes
                    parameters
                    requestId
                    startUrl
                    status
                    type
                    updatedAt
                    userId
                    zoomPrivateMeeting
                }
            }
        `;

    const variables = {
      conference,
    };

    const res: { data: { insert_Conference_one: ConferenceType } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(res, ' successfully inserted one conference');

    return res?.data?.insert_Conference_one;
  } catch (e) {
    console.log(e, ' unable to insert conference');
  }
};

export const processEmailContent = async (content: string) => {
  try {
    const rawContent = content;

    console.log(rawContent, ' raw content');
    let html = '';

    // const html_regex = HTML_REGEX_PATTERN
    // const htmls = html_regex.exec(rawContent)
    // console.log(htmls, ' htmls')
    // html = htmls?.[0]
    // validate by matching

    // use cheerio to get content
    const decodedRawContent = decodeURIComponent(
      quotedPrintable.decode(rawContent)
    );
    const $ = cheerio.load(decodedRawContent);

    $('div').each((_, element) => {
      console.log($(element).text(), ' $(element).text()');
      html += $(element).text();
    });

    console.log(html, ' html');

    if (!html) {
      console.log('html is not present');
      return;
    }

    const short_html =
      html?.length > MAX_CHARACTER_LIMIT
        ? html.slice(0, MAX_CHARACTER_LIMIT)
        : html;

    console.log(short_html, ' short_html');
    console.log(short_html.length, ' short_html.length');

    const url_regex = ATOMIC_SUBDOMAIN_PATTERN;

    const urls = url_regex.exec(decodedRawContent);

    console.log(urls, ' urls');

    let url = urls?.[0];

    console.log(url, ' url');

    if (!url) {
      console.log('no url present');
      return;
    }

    const urlObject = new URL(
      url.slice(0, url.length - NUMBER_TO_REMOVE_FOR_SUBDOMAIN_SLICE)
    );

    // const searchParams = new URLSearchParams(urlObject.search)

    console.log(urlObject.href, ' urlObject.href');
    // console.log(searchParams, ' searchParams')
    url = url.slice(0, url.length - NUMBER_TO_REMOVE_FOR_SUBDOMAIN_SLICE);

    const urlQIndex = url.indexOf('?');
    const urlShort = url.slice(urlQIndex + 1);
    const atomicQSParamsString = urlShort;

    const rawQueryParamsObject = qs.parse(atomicQSParamsString);

    console.log(rawQueryParamsObject, ' rawQueryParamsObject');

    const newQueryParamsObject: MeetingUrlQueryParamsType | {} = {};

    for (const key in rawQueryParamsObject) {
      const newKey = key.replace('amp;', '');

      if (typeof rawQueryParamsObject[key] === 'string') {
        const oldValue: string = rawQueryParamsObject[key] || '';
        const newValue = oldValue?.replace(
          '" target="_blank">Atomic</a> :)</pr',
          ''
        );
        newQueryParamsObject[newKey] = newValue;
      } else {
        newQueryParamsObject[newKey] = rawQueryParamsObject[key];
      }
    }

    console.log(newQueryParamsObject, ' newQueryParamsObject');

    if (!(newQueryParamsObject as MeetingUrlQueryParamsType)?.userId) {
      console.log(' newQueryParamsObject not parsed properly');
      return;
    }

    const queryParamsObject: MeetingUrlQueryParamsType =
      newQueryParamsObject as MeetingUrlQueryParamsType;

    const userId = queryParamsObject?.userId;
    const timezone = queryParamsObject?.timezone;
    const attendeeEmails = queryParamsObject?.attendeeEmails;
    const duration = queryParamsObject?.duration;
    const calendarId = queryParamsObject?.calendarId;
    const startTime = queryParamsObject?.startTime;
    const name = queryParamsObject?.name;
    const primaryEmail = queryParamsObject?.primaryEmail;
    // const attachments = queryParamsObject?.attachments

    // validate
    if (!userId) {
      throw new Error('no userId present inside query params');
    }

    if (!timezone) {
      throw new Error('no timezone provided');
    }

    if (!(attendeeEmails?.length > 0)) {
      throw new Error('no attendee emails');
    }

    if (!duration) {
      throw new Error('no duration provided');
    }

    if (!name) {
      throw new Error('no name provided');
    }

    if (!calendarId) {
      throw new Error('no calendarId provided');
    }

    if (!primaryEmail) {
      throw new Error('no new primaryEmail');
    }

    // get openai key

    const openai = new OpenAI({
      apiKey: defaultOpenAIAPIKey,
    });

    // check for whether a meeting time is scheduled or not
    const isMeetingPrompt = isMeetingTimeScheduledPrompt;

    const isMeetingUserData = `email body: ${short_html}`;

    const openAIResForMeetingTimeScheduled = await callOpenAI(
      isMeetingPrompt,
      openAIChatGPTModel,
      isMeetingUserData,
      openai,
      isMeetingTimeScheduledExampleInput,
      isMeetingTimeScheduledExampleOutput
    );

    // parse JSON
    console.log(
      openAIResForMeetingTimeScheduled,
      ' openAIResForMeetingTimeScheduled'
    );
    // ChatGPT response
    // { "time_provided": true }

    const startIndex = openAIResForMeetingTimeScheduled?.indexOf('{');
    const endIndex = openAIResForMeetingTimeScheduled?.indexOf('}');

    const isMeetingTimeScheduledString = openAIResForMeetingTimeScheduled.slice(
      startIndex,
      endIndex + 1
    );

    const isMeetingScheduledObject: isMeetingScheduledObjectType = JSON.parse(
      isMeetingTimeScheduledString
    );

    // stop if meeting time is not scheduled
    if (!isMeetingScheduledObject?.time_provided) {
      console.log('no meeting time provided');
      return;
    }

    // extract data and time
    const extractDateAndTimePrompt = extractDateTimePrompt;
    const extractDateTimeUserData = `start time: ${startTime} \n timezone: ${timezone} \n email History: ${short_html}`;

    const openAIResForExtractDateTime = await callOpenAI(
      extractDateAndTimePrompt,
      openAIChatGPTModel,
      extractDateTimeUserData,
      openai,
      extractDateTimeExampleInput,
      extractDateTimeExampleOutput
    );

    const startIndex2 = openAIResForExtractDateTime?.indexOf('{');
    const endIndex2 = openAIResForExtractDateTime?.indexOf('}');

    const extractDateTimeString = openAIResForExtractDateTime.slice(
      startIndex2,
      endIndex2 + 1
    );
    const extractDateTimeObject: ExtractDateTimeObjectType = JSON.parse(
      extractDateTimeString
    );

    // ISO 8601 format time
    const meetingTime = extractDateTimeObject?.meeting_time;

    // validate meetingTime
    if (!meetingTime) {
      throw new Error('unable to extract date and time');
    }

    // schedule meeting

    // generate meeting summary and notes
    const generateSummaryAndNotesPrompt = generateMeetingSummaryPrompt;
    const generateSummaryAndNotesUserData = `start time: ${startTime} \n timezone: ${timezone} \n email History: ${short_html}`;
    const openAIResForSummaryAndNotes = await callOpenAI(
      generateSummaryAndNotesPrompt,
      openAIChatGPTModel,
      generateSummaryAndNotesUserData,
      openai,
      generateMeetingSummaryInput,
      generateMeetingSummaryOutput
    );

    const startIndex3 = openAIResForSummaryAndNotes?.indexOf('{');
    const endIndex3 = openAIResForSummaryAndNotes?.indexOf('}');

    const summaryAndNotesString = openAIResForSummaryAndNotes.slice(
      startIndex3,
      endIndex3 + 1
    );
    const summaryAndNotesObject: SummaryAndNotesObjectType = JSON.parse(
      summaryAndNotesString
    );

    // get primary calendar
    const primaryCalendar = await getGlobalCalendar(userId);

    // validate
    if (!primaryCalendar?.id) {
      throw new Error('no primary calendar found inside createAgenda');
    }

    // get client type
    const calIntegration = await getCalendarIntegration(
      userId,
      googleCalendarResource
    );

    // validate
    if (!calIntegration?.clientType) {
      throw new Error(
        'no client type inside calendar integration inside create agenda'
      );
    }

    const eventId = uuid();

    const remindersString = queryParamsObject?.reminders;

    const remindersToUpdateEventId: ReminderType[] = [];

    if (remindersString) {
      const newReminders: ReminderType[] = remindersString.map((r) => ({
        id: uuid(),
        userId,
        eventId, // generatedId
        timezone,
        minutes: parseInt(r, 10),
        useDefault: false,
        updatedAt: dayjs().format(),
        createdDate: dayjs().format(),
        deleted: false,
      }));

      remindersToUpdateEventId.push(...newReminders);
    }

    const googleReminder: GoogleReminderType = {
      overrides: remindersToUpdateEventId?.map((r) => ({
        method: 'email',
        minutes: r?.minutes,
      })),
      useDefault: false,
    };

    // create attendees to create if any
    const attendees: AttendeeType[] = [];
    if (attendeeEmails?.length > 0) {
      for (const aEmail of attendeeEmails) {
        const attendee: AttendeeType = {
          id: uuid(),
          userId,
          name: primaryEmail === aEmail ? name : undefined,
          emails: [{ primary: true, value: aEmail }],
          eventId, // generatedId
          updatedAt: dayjs().format(),
          createdDate: dayjs().format(),
          deleted: false,
        };
        attendees.push(attendee);
      }
    }

    if (queryParamsObject?.enableConference) {
      let conference: ConferenceType | {} = {};
      // create conference object
      const zoomToken = await getZoomAPIToken(userId);
      conference = zoomToken
        ? {}
        : {
            id: uuid(),
            userId,
            calendarId: calendarId || primaryCalendar?.id,
            app: 'google',
            name,
            notes: summaryAndNotesObject?.notes,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            deleted: false,
            isHost: true,
          };

      if (queryParamsObject?.conferenceApp === 'zoom' && zoomToken) {
        if (zoomToken) {
          console.log(zoomToken, ' zoomToken inside if (zoomToken)');

          const zoomObject = await createZoomMeeting(
            zoomToken,
            meetingTime,
            timezone,
            summaryAndNotesObject?.summary,
            parseInt(duration, 10),
            name,
            primaryEmail,
            attendeeEmails
          );

          console.log(zoomObject, ' zoomObject after createZoomMeeting');

          if (zoomObject) {
            conference = {
              id: `${zoomObject?.id}`,
              userId: userId,
              calendarId,
              app: 'zoom',
              name: zoomObject?.agenda,
              notes: zoomObject?.agenda,
              joinUrl: zoomObject?.join_url,
              startUrl: zoomObject?.start_url,
              isHost: true,
              updatedAt: dayjs().format(),
              createdDate: dayjs().format(),
              deleted: false,
              entryPoints: [
                {
                  entryPointType: 'video',
                  label: zoomObject?.join_url,
                  password: zoomObject?.password,
                  uri: zoomObject?.join_url,
                },
              ],
            } as ConferenceType;
          }
        }
      }

      const eventToUpsertLocal: EventType = {
        id: eventId,
        userId,
        title: summaryAndNotesObject?.summary,
        startDate: dayjs(meetingTime).tz(timezone).format(),
        endDate: dayjs(meetingTime)
          .tz(timezone)
          .add(parseInt(duration, 10), 'm')
          .format(),
        allDay: false,
        notes: summaryAndNotesObject?.notes,
        timezone,
        createdDate: dayjs().format(),
        deleted: false,
        priority: 1,
        isFollowUp: false,
        isPreEvent: false,
        isPostEvent: false,
        modifiable: false,
        anyoneCanAddSelf:
          queryParamsObject?.anyoneCanAddSelf === 'true' ? true : false,
        guestsCanInviteOthers:
          queryParamsObject?.guestsCanInviteOthers === 'true' ? true : false,
        guestsCanSeeOtherGuests:
          queryParamsObject?.guestsCanSeeOtherGuests === 'true' ? true : false,
        transparency: queryParamsObject?.transparency,
        visibility: queryParamsObject?.visibility,
        originalStartDate: undefined,
        originalAllDay: false,
        summary: summaryAndNotesObject?.summary,
        updatedAt: dayjs().format(),
        calendarId: calendarId || primaryCalendar?.id,
        eventId: undefined,
        conferenceId: (conference as ConferenceType)?.id,
        attachments: queryParamsObject?.attachments,
        sendUpdates: queryParamsObject?.sendUpdates,
        duration: parseInt(queryParamsObject?.duration, 10),
      };

      const googleResValue: GoogleResType = await createGoogleEvent(
        userId,
        calendarId,
        calIntegration?.clientType,
        eventToUpsertLocal?.id,
        eventToUpsertLocal?.endDate,
        eventToUpsertLocal?.startDate,
        (conference as ConferenceType)?.id ? 1 : 0,
        2,
        eventToUpsertLocal?.sendUpdates,
        eventToUpsertLocal?.anyoneCanAddSelf,
        attendeeEmails?.map((a) => ({ email: a })),
        (conference as ConferenceType)?.id
          ? {
              type:
                (conference as ConferenceType)?.app === 'zoom'
                  ? 'addOn'
                  : 'hangoutsMeet',
              name: (conference as ConferenceType)?.name,
              conferenceId: (conference as ConferenceType)?.id,
              entryPoints: (conference as ConferenceType)?.entryPoints,
              createRequest:
                (conference as ConferenceType)?.app === 'google'
                  ? {
                      requestId: (conference as ConferenceType)?.requestId,
                      conferenceSolutionKey: {
                        type: 'hangoutsMeet',
                      },
                    }
                  : undefined,
            }
          : undefined,
        summaryAndNotesObject?.summary,
        summaryAndNotesObject?.notes,
        timezone,
        undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.guestsCanInviteOthers,
        eventToUpsertLocal?.guestsCanModify,
        eventToUpsertLocal?.guestsCanSeeOtherGuests,
        eventToUpsertLocal?.originalStartDate,
        undefined,
        undefined,
        remindersToUpdateEventId?.length > 0 ? googleReminder : undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.transparency,
        eventToUpsertLocal?.visibility,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.attachments,
        'default',
        undefined,
        undefined
      );

      eventToUpsertLocal.id = googleResValue.id;
      eventToUpsertLocal.eventId = googleResValue.googleEventId;

      // update reminders for event Id
      remindersToUpdateEventId?.map((r) => ({
        ...r,
        eventId: eventToUpsertLocal.id,
      }));

      // update attendees for eventId
      attendees?.map((a) => ({ ...a, eventId: eventToUpsertLocal.id }));

      // insert conference
      await insertConference(conference as ConferenceType);

      // insert events
      await upsertEvents([eventToUpsertLocal]);

      // insert reminders
      if (remindersToUpdateEventId?.length > 0) {
        await insertReminders(remindersToUpdateEventId);
      }

      if (attendees?.length > 0) {
        await insertAttendeesforEvent(attendees);
      }
    } else {
      const eventToUpsertLocal: EventType = {
        id: eventId,
        userId,
        title: summaryAndNotesObject?.summary,
        startDate: dayjs(meetingTime).tz(timezone).format(),
        endDate: dayjs(meetingTime)
          .tz(timezone)
          .add(parseInt(duration, 10), 'm')
          .format(),
        allDay: false,
        notes: summaryAndNotesObject?.notes,
        timezone,
        createdDate: dayjs().format(),
        deleted: false,
        priority: 1,
        isFollowUp: false,
        isPreEvent: false,
        isPostEvent: false,
        modifiable: false,
        anyoneCanAddSelf:
          queryParamsObject?.anyoneCanAddSelf === 'true' ? true : false,
        guestsCanInviteOthers:
          queryParamsObject?.guestsCanInviteOthers === 'true' ? true : false,
        guestsCanSeeOtherGuests:
          queryParamsObject?.guestsCanSeeOtherGuests === 'true' ? true : false,
        transparency: queryParamsObject?.transparency,
        visibility: queryParamsObject?.visibility,
        originalStartDate: undefined,
        originalAllDay: false,
        summary: summaryAndNotesObject?.summary,
        updatedAt: dayjs().format(),
        calendarId: calendarId || primaryCalendar?.id,
        eventId: undefined,
        attachments: queryParamsObject?.attachments,
        sendUpdates: queryParamsObject?.sendUpdates,
        duration: parseInt(queryParamsObject?.duration, 10),
      };

      const googleResValue: GoogleResType = await createGoogleEvent(
        userId,
        calendarId,
        calIntegration?.clientType,
        eventToUpsertLocal?.id,
        eventToUpsertLocal?.endDate,
        eventToUpsertLocal?.startDate,
        0,
        2,
        eventToUpsertLocal?.sendUpdates,
        eventToUpsertLocal?.anyoneCanAddSelf,
        attendeeEmails?.map((a) => ({ email: a })),
        undefined,
        summaryAndNotesObject?.summary,
        summaryAndNotesObject?.notes,
        timezone,
        undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.guestsCanInviteOthers,
        eventToUpsertLocal?.guestsCanModify,
        eventToUpsertLocal?.guestsCanSeeOtherGuests,
        eventToUpsertLocal?.originalStartDate,
        undefined,
        undefined,
        remindersToUpdateEventId?.length > 0 ? googleReminder : undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.transparency,
        eventToUpsertLocal?.visibility,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.attachments,
        'default',
        undefined,
        undefined
      );

      eventToUpsertLocal.id = googleResValue.id;
      eventToUpsertLocal.eventId = googleResValue.googleEventId;

      // update reminders for event Id
      remindersToUpdateEventId?.map((r) => ({
        ...r,
        eventId: eventToUpsertLocal.id,
      }));

      // update attendees for eventId
      attendees?.map((a) => ({ ...a, eventId: eventToUpsertLocal.id }));

      // insert events
      await upsertEvents([eventToUpsertLocal]);

      // insert reminders
      if (remindersToUpdateEventId?.length > 0) {
        await insertReminders(remindersToUpdateEventId);
      }

      if (attendees?.length > 0) {
        await insertAttendeesforEvent(attendees);
      }
    }
  } catch (e) {
    console.log(e, ' unable to process email content');
  }
};

export const listEventsForUserGivenDates = async (
  userId: string,
  senderStartDate: string,
  senderEndDate: string
  // senderTimezone: string,
  // receiverTimezone: string,
) => {
  try {
    const operationName = 'listEventsForUser';
    const query = `
            query listEventsForUser($userId: uuid!, $startDate: timestamp!, $endDate: timestamp!) {
                Event(where: {userId: {_eq: $userId}, endDate: {_gte: $startDate}, startDate: {_lte: $endDate}, deleted: {_neq: true}, allDay: {_neq: true}}) {
                    allDay
                    anyoneCanAddSelf
                    attachments
                    attendeesOmitted
                    backgroundColor
                    calendarId
                    colorId
                    conferenceId
                    copyAvailability
                    copyCategories
                    copyDuration
                    copyIsBreak
                    copyIsExternalMeeting
                    copyIsMeeting
                    copyModifiable
                    copyPriorityLevel
                    copyReminders
                    copyTimeBlocking
                    copyTimePreference
                    createdDate
                    creator
                    dailyTaskList
                    deleted
                    duration
                    endDate
                    endTimeUnspecified
                    eventId
                    eventType
                    extendedProperties
                    followUpEventId
                    forEventId
                    foregroundColor
                    guestsCanInviteOthers
                    guestsCanModify
                    guestsCanSeeOtherGuests
                    hangoutLink
                    hardDeadline
                    htmlLink
                    iCalUID
                    id
                    isBreak
                    isExternalMeeting
                    isExternalMeetingModifiable
                    isFollowUp
                    isMeeting
                    isMeetingModifiable
                    isPostEvent
                    isPreEvent
                    links
                    location
                    locked
                    maxAttendees
                    meetingId
                    method
                    modifiable
                    negativeImpactDayOfWeek
                    negativeImpactScore
                    negativeImpactTime
                    notes
                    organizer
                    originalAllDay
                    originalStartDate
                    originalTimezone
                    positiveImpactDayOfWeek
                    positiveImpactScore
                    positiveImpactTime
                    postEventId
                    preEventId
                    preferredDayOfWeek
                    preferredEndTimeRange
                    preferredStartTimeRange
                    preferredTime
                    priority
                    privateCopy
                    recurrence
                    recurrenceRule
                    recurringEventId
                    sendUpdates
                    softDeadline
                    source
                    startDate
                    status
                    summary
                    taskId
                    taskType
                    timeBlocking
                    timezone
                    title
                    transparency
                    unlink
                    updatedAt
                    useDefaultAlarms
                    userId
                    userModifiedAvailability
                    userModifiedCategories
                    userModifiedDuration
                    userModifiedIsBreak
                    userModifiedIsExternalMeeting
                    userModifiedIsMeeting
                    userModifiedModifiable
                    userModifiedPriorityLevel
                    userModifiedReminders
                    userModifiedTimeBlocking
                    userModifiedTimePreference
                    visibility
                    weeklyTaskList
                    byWeekDay
                    localSynced
                    userModifiedColor
                    copyColor
                    copyExternalMeetingModifiable
                    userModifiedExternalMeetingModifiable
                    userModifiedMeetingModifiable
                }
            }
        `;
    // get events
    // local date
    // const startDateInReceiverTimezone = dayjs(senderStartDate.slice(0, 19)).tz(receiverTimezone, true)
    // const endDateInReceiverTimezone = dayjs((senderEndDate.slice(0, 19))).tz(receiverTimezone, true)
    // const startDateInSenderTimezone = dayjs(startDateInReceiverTimezone).format().slice(0, 19)
    // const endDateInSenderTimezone = dayjs(endDateInReceiverTimezone).format().slice(0, 19)

    const res: { data: { Event: EventType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            userId,
            startDate: senderStartDate,
            endDate: senderEndDate,
          },
        },
      })
      .json();

    console.log(res, ' res from listEventsforUser');
    return res?.data?.Event;
  } catch (e) {
    console.log(e, ' listEventsForUser');
  }
};

export const getUserPreferences = async (
  userId: string
): Promise<UserPreferenceType | null> => {
  try {
    if (!userId) {
      console.log('userId is null');
      return null;
    }
    const operationName = 'getUserPreferences';
    const query = `
    query getUserPreferences($userId: uuid!) {
      User_Preference(where: {userId: {_eq: $userId}}) {
        startTimes
        endTimes
        backToBackMeetings
        copyAvailability
        copyCategories
        copyIsBreak
        copyModifiable
        copyPriorityLevel
        copyReminders
        copyTimeBlocking
        copyTimePreference
        createdDate
        deleted
        followUp
        id
        isPublicCalendar
        maxNumberOfMeetings
        maxWorkLoadPercent
        publicCalendarCategories
        reminders
        updatedAt
        userId
        minNumberOfBreaks
        breakColor
        breakLength
        copyColor
        copyIsExternalMeeting
        copyIsMeeting
        onBoarded
      }
    }    
  `;
    const res: { data: { User_Preference: UserPreferenceType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            userId,
          },
        },
      })
      .json();
    return res?.data?.User_Preference?.[0];
  } catch (e) {
    console.log(e, ' getUserPreferences');
    return null;
  }
};
export const generateAvailableSlotsForDate = (
  slotDuration: number,
  senderStartDateInReceiverTimezone: string,
  senderPreferences: UserPreferenceType,
  receiverTimezone: string,
  senderTimezone: string,
  notAvailableSlotsInEventTimezone?: NotAvailableSlotType[],
  isFirstDay?: boolean,
  isLastDay?: boolean,
  senderEndDateInReceiverTimezone?: string
) => {
  console.log(senderTimezone, ' senderTimezone');
  console.log(receiverTimezone, ' receiverTimezone');

  if (isFirstDay && isLastDay && senderEndDateInReceiverTimezone) {
    const endTimesBySender = senderPreferences.endTimes;
    const dayOfWeekIntAsReceiver = getISODay(
      dayjs(senderStartDateInReceiverTimezone?.slice(0, 19))
        .tz(receiverTimezone, true)
        .toDate()
    );

    const dayOfMonthAsReceiver = dayjs(
      senderStartDateInReceiverTimezone?.slice(0, 19)
    )
      .tz(receiverTimezone, true)
      .date();
    let startHourAsReceiver = dayjs(
      senderStartDateInReceiverTimezone?.slice(0, 19)
    )
      .tz(receiverTimezone, true)
      .hour();

    const flooredValue = Math.floor(60 / slotDuration);

    let minuteValueAsReceiver = 0;
    if (
      dayjs(senderStartDateInReceiverTimezone).tz(receiverTimezone).minute() !==
      0
    ) {
      for (let i = 0; i < flooredValue; i++) {
        const endMinutes = (i + 1) * slotDuration;
        const startMinutes = i * slotDuration;
        if (
          dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .isBetween(
              dayjs(senderStartDateInReceiverTimezone)
                .tz(receiverTimezone)
                .minute(startMinutes),
              dayjs(senderStartDateInReceiverTimezone)
                .tz(receiverTimezone)
                .minute(endMinutes),
              'minute',
              '[)'
            )
        ) {
          minuteValueAsReceiver = endMinutes;
        }
      }
    }

    if (
      dayjs(senderStartDateInReceiverTimezone)
        .tz(receiverTimezone)
        .isBetween(
          dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute(flooredValue * slotDuration),
          dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute(59),
          'minute',
          '[)'
        )
    ) {
      startHourAsReceiver += 1;
      minuteValueAsReceiver = 0;
    }

    const startMinuteAsReceiver = minuteValueAsReceiver;

    const endHourWorkBySender =
      endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour ??
      20;
    const endMinuteWorkBySender =
      endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)
        ?.minutes ?? 0;
    const endHourAsReceiver = dayjs(senderEndDateInReceiverTimezone)
      .tz(receiverTimezone)
      .hour();
    const endMinuteAsReceiver = dayjs(senderEndDateInReceiverTimezone)
      .tz(receiverTimezone)
      .minute();

    // validate values before calculating
    const startTimes = senderPreferences.startTimes;
    const workStartHourBySender =
      startTimes?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour || 8;
    const workStartMinuteBySender =
      startTimes?.find((i) => i.day === dayOfWeekIntAsReceiver)?.minutes || 0;

    if (
      dayjs(senderStartDateInReceiverTimezone)
        .tz(senderTimezone)
        .isAfter(
          dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(endHourWorkBySender)
            .minute(endMinuteWorkBySender)
        )
    ) {
      // return empty as outside of work time
      return [];
    }

    // change to work start time as sender start time before work start time
    if (
      dayjs(senderStartDateInReceiverTimezone)
        .tz(senderTimezone)
        .isBefore(
          dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(workStartHourBySender)
            .minute(workStartMinuteBySender)
        )
    ) {
      const startDuration = dayjs.duration({
        hours: workStartHourBySender,
        minutes: workStartMinuteBySender,
      });
      const endDuration = dayjs.duration({
        hours: endHourAsReceiver,
        minutes: endMinuteAsReceiver,
      });
      const totalDuration = endDuration.subtract(startDuration);
      const totalMinutes = totalDuration.asMinutes();

      const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
      console.log(
        senderStartDateInReceiverTimezone,
        endTimesBySender,
        dayOfWeekIntAsReceiver,
        dayOfMonthAsReceiver,
        startHourAsReceiver,
        startMinuteAsReceiver,
        endHourAsReceiver,
        endMinuteAsReceiver,
        timezone,
        `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
      );
      for (let i = 0; i < totalMinutes; i += slotDuration) {
        if (i > totalMinutes) {
          continue;
        }

        availableSlotsInReceiverTimezone.push({
          id: uuid(),
          startDate: dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(workStartHourBySender)
            .minute(workStartMinuteBySender)
            .tz(receiverTimezone)
            .add(i, 'minute')
            .second(0)
            .format(),
          endDate: dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(workStartHourBySender)
            .minute(workStartMinuteBySender)
            .tz(receiverTimezone)
            .add(i + slotDuration, 'minute')
            .second(0)
            .format(),
        });
      }
      console.log(
        availableSlotsInReceiverTimezone,
        ' timeSlots inside generateTimeSlots for first day where startDate is before work start time'
      );

      // filter out unavailable times
      const filteredAvailableSlotsInReceiverTimezone =
        availableSlotsInReceiverTimezone.filter((a) => {
          const foundIndex = notAvailableSlotsInEventTimezone?.findIndex(
            (na) => {
              const partA = dayjs(a.endDate)
                .tz(receiverTimezone)
                .second(0)
                .isBetween(
                  dayjs(na.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .add(1, 'm'),
                  dayjs(na.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .subtract(1, 'm'),
                  'm',
                  '[]'
                );

              const partB = dayjs(a.startDate)
                .tz(receiverTimezone)
                .second(0)
                .isBetween(
                  dayjs(na.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .add(1, 'm'),
                  dayjs(na.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .subtract(1, 'm'),
                  'm',
                  '[]'
                );

              const partC =
                dayjs(na.startDate)
                  .tz(receiverTimezone)
                  .second(0)
                  .format('YYYY-MM-DDTHH:mm') ===
                  dayjs(a.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') &&
                dayjs(na.endDate)
                  .tz(receiverTimezone)
                  .second(0)
                  .format('YYYY-MM-DDTHH:mm') ===
                  dayjs(a.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm');

              const isNotAvailable = partA || partB || partC;

              // console.log(a, na, ' a, na')
              return isNotAvailable;
            }
          );

          console.log(foundIndex, ' foundIndex');

          if (foundIndex !== undefined && foundIndex > -1) {
            return false;
          }

          return true;
        });

      console.log(
        filteredAvailableSlotsInReceiverTimezone,
        ' filteredAvailableSlots'
      );

      return filteredAvailableSlotsInReceiverTimezone;
    }

    const startDuration = dayjs.duration({
      hours: startHourAsReceiver,
      minutes: startMinuteAsReceiver,
    });
    const endDuration = dayjs.duration({
      hours: endHourAsReceiver,
      minutes: endMinuteAsReceiver,
    });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    console.log(totalMinutes, ' totalMinutes inside first and last same day');
    const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
    console.log(
      senderStartDateInReceiverTimezone,
      endTimesBySender,
      dayOfWeekIntAsReceiver,
      endHourWorkBySender,
      endMinuteWorkBySender,
      receiverTimezone,
      `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside first & last Day inside generateTimeslots`
    );
    for (let i = 0; i < totalMinutes; i += slotDuration) {
      if (i > totalMinutes) {
        continue;
      }
      availableSlotsInReceiverTimezone.push({
        id: uuid(),
        startDate: dayjs(senderStartDateInReceiverTimezone)
          .tz(receiverTimezone)
          .hour(startHourAsReceiver)
          .minute(startMinuteAsReceiver)
          .add(i, 'minute')
          .second(0)
          .format(),
        endDate: dayjs(senderStartDateInReceiverTimezone)
          .tz(receiverTimezone)
          .hour(startHourAsReceiver)
          .minute(startMinuteAsReceiver)
          .add(i + slotDuration, 'minute')
          .second(0)
          .format(),
      });
    }

    console.log(
      availableSlotsInReceiverTimezone,
      ' availableSlots inside first & last same day'
    );
    const filteredAvailableSlotsInReceiverTimezone =
      availableSlotsInReceiverTimezone.filter((a) => {
        const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
          const partA = dayjs(a.endDate)
            .tz(receiverTimezone)
            .second(0)
            .isBetween(
              dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'),
              dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'),
              'm',
              '[]'
            );

          const partB = dayjs(a.startDate)
            .tz(receiverTimezone)
            .second(0)
            .isBetween(
              dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'),
              dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'),
              'm',
              '[]'
            );

          const partC =
            dayjs(na.startDate)
              .tz(receiverTimezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') ===
              dayjs(a.startDate)
                .tz(receiverTimezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm') &&
            dayjs(na.endDate)
              .tz(receiverTimezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') ===
              dayjs(a.endDate)
                .tz(receiverTimezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm');

          const isNotAvailable = partA || partB || partC;

          // console.log(a, na, ' a, na')

          return isNotAvailable;
        });

        console.log(foundIndex, ' foundIndex');

        if (foundIndex !== undefined && foundIndex > -1) {
          return false;
        }

        return true;
      });

    console.log(
      filteredAvailableSlotsInReceiverTimezone,
      ' filteredAvailableSlots'
    );
    return filteredAvailableSlotsInReceiverTimezone;
  }

  if (isFirstDay) {
    // firstday can be started outside of work time
    // if firstDay start is after end time -- return []
    const endTimesBySender = senderPreferences.endTimes;
    const dayOfWeekIntAsReceiver = getISODay(
      dayjs(senderStartDateInReceiverTimezone).tz(receiverTimezone).toDate()
    );

    // month is zero-indexed
    // const month = dayjs(hostStartDate.slice(0, 19)).tz(hostTimezone, true).tz(userTimezone).month()
    const dayOfMonthAsReceiver = dayjs(senderStartDateInReceiverTimezone)
      .tz(receiverTimezone)
      .date();
    let startHourAsReceiver = dayjs(senderStartDateInReceiverTimezone)
      .tz(receiverTimezone)
      .hour();
    const startHourBySender = dayjs(senderStartDateInReceiverTimezone)
      .tz(senderTimezone)
      .hour();
    const startMinuteBySender = dayjs(senderStartDateInReceiverTimezone)
      .tz(senderTimezone)
      .minute();
    // create slot sizes
    const flooredValue = Math.floor(60 / slotDuration);

    let minuteValueAsReceiver = 0;
    if (
      dayjs(senderStartDateInReceiverTimezone).tz(receiverTimezone).minute() !==
      0
    ) {
      for (let i = 0; i < flooredValue; i++) {
        const endMinutes = (i + 1) * slotDuration;
        const startMinutes = i * slotDuration;
        if (
          dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .isBetween(
              dayjs(senderStartDateInReceiverTimezone)
                .tz(receiverTimezone)
                .minute(startMinutes),
              dayjs(senderStartDateInReceiverTimezone)
                .tz(receiverTimezone)
                .minute(endMinutes),
              'minute',
              '[)'
            )
        ) {
          minuteValueAsReceiver = endMinutes;
        }
      }
    }

    if (
      dayjs(senderStartDateInReceiverTimezone)
        .tz(receiverTimezone)
        .isBetween(
          dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute(flooredValue * slotDuration),
          dayjs(senderStartDateInReceiverTimezone)
            .tz(receiverTimezone)
            .minute(59),
          'minute',
          '[)'
        )
    ) {
      startHourAsReceiver += 1;
      minuteValueAsReceiver = 0;
    }

    const startMinuteAsReceiver = minuteValueAsReceiver;

    // convert to user timezone so everything is linked to user timezone

    const endHourBySender =
      endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour ??
      20;
    const endMinuteBySender =
      endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)
        ?.minutes ?? 0;

    // validate values before calculating
    const startTimes = senderPreferences.startTimes;
    const workStartHourBySender =
      startTimes?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour || 8;
    const workStartMinuteBySender =
      startTimes?.find((i) => i.day === dayOfWeekIntAsReceiver)?.minutes || 0;

    if (
      dayjs(senderStartDateInReceiverTimezone)
        .tz(senderTimezone)
        .isAfter(
          dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(endHourBySender)
            .minute(endMinuteBySender)
        )
    ) {
      // return empty as outside of work time
      return [];
    }

    // change to work start time as host start time before work start time
    if (
      dayjs(senderStartDateInReceiverTimezone)
        .tz(senderTimezone)
        .isBefore(
          dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(workStartHourBySender)
            .minute(workStartMinuteBySender)
        )
    ) {
      const startDuration = dayjs.duration({
        hours: workStartHourBySender,
        minutes: workStartMinuteBySender,
      });
      const endDuration = dayjs.duration({
        hours: endHourBySender,
        minutes: endMinuteBySender,
      });
      const totalDuration = endDuration.subtract(startDuration);
      const totalMinutes = totalDuration.asMinutes();

      const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
      console.log(
        senderStartDateInReceiverTimezone,
        endTimesBySender,
        dayOfWeekIntAsReceiver,
        dayOfMonthAsReceiver,
        startHourAsReceiver,
        startMinuteAsReceiver,
        endHourBySender,
        endMinuteBySender,
        timezone,
        `startDate, endTimes, dayOfWeekIntByUser, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
      );
      for (let i = 0; i < totalMinutes; i += slotDuration) {
        if (i > totalMinutes) {
          continue;
        }

        availableSlotsInReceiverTimezone.push({
          id: uuid(),
          startDate: dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(workStartHourBySender)
            .minute(workStartMinuteBySender)
            .tz(receiverTimezone)
            .add(i, 'minute')
            .second(0)
            .format(),
          endDate: dayjs(senderStartDateInReceiverTimezone)
            .tz(senderTimezone)
            .hour(workStartHourBySender)
            .minute(workStartMinuteBySender)
            .tz(receiverTimezone)
            .add(i + slotDuration, 'minute')
            .second(0)
            .format(),
        });
      }
      console.log(
        availableSlotsInReceiverTimezone,
        ' timeSlots inside generateTimeSlots for first day where startDate is before work start time'
      );

      // filter out unavailable times
      const filteredAvailableSlotsInReceiverTimezone =
        availableSlotsInReceiverTimezone.filter((a) => {
          const foundIndex = notAvailableSlotsInEventTimezone?.findIndex(
            (na) => {
              const partA = dayjs(a.endDate)
                .tz(receiverTimezone)
                .second(0)
                .isBetween(
                  dayjs(na.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .add(1, 'm'),
                  dayjs(na.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .subtract(1, 'm'),
                  'm',
                  '[]'
                );

              const partB = dayjs(a.startDate)
                .tz(receiverTimezone)
                .second(0)
                .isBetween(
                  dayjs(na.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .add(1, 'm'),
                  dayjs(na.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .subtract(1, 'm'),
                  'm',
                  '[]'
                );

              const partC =
                dayjs(na.startDate)
                  .tz(receiverTimezone)
                  .second(0)
                  .format('YYYY-MM-DDTHH:mm') ===
                  dayjs(a.startDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm') &&
                dayjs(na.endDate)
                  .tz(receiverTimezone)
                  .second(0)
                  .format('YYYY-MM-DDTHH:mm') ===
                  dayjs(a.endDate)
                    .tz(receiverTimezone)
                    .second(0)
                    .format('YYYY-MM-DDTHH:mm');

              const isNotAvailable = partA || partB || partC;

              // console.log(a, na, ' a, na')
              return isNotAvailable;
            }
          );

          console.log(foundIndex, ' foundIndex');

          if (foundIndex !== undefined && foundIndex > -1) {
            return false;
          }

          return true;
        });

      console.log(
        filteredAvailableSlotsInReceiverTimezone,
        ' filteredAvailableSlots'
      );

      return filteredAvailableSlotsInReceiverTimezone;
    }

    const startDuration = dayjs.duration({
      hours: startHourBySender,
      minutes: startMinuteBySender,
    });
    const endDuration = dayjs.duration({
      hours: endHourBySender,
      minutes: endMinuteBySender,
    });
    const totalDuration = endDuration.subtract(startDuration);
    const totalMinutes = totalDuration.asMinutes();
    const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
    console.log(
      senderStartDateInReceiverTimezone,
      endTimesBySender,
      dayOfWeekIntAsReceiver,
      endHourBySender,
      endMinuteBySender,
      receiverTimezone,
      `startDate, endTimes, dayOfWeekInt, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateTimeslots`
    );
    for (let i = 0; i < totalMinutes; i += slotDuration) {
      if (i > totalMinutes) {
        continue;
      }
      availableSlotsInReceiverTimezone.push({
        id: uuid(),
        startDate: dayjs(senderStartDateInReceiverTimezone)
          .tz(receiverTimezone)
          .hour(startHourAsReceiver)
          .minute(startMinuteAsReceiver)
          .add(i, 'minute')
          .second(0)
          .format(),
        endDate: dayjs(senderStartDateInReceiverTimezone)
          .tz(receiverTimezone)
          .hour(startHourAsReceiver)
          .minute(startMinuteAsReceiver)
          .add(i + slotDuration, 'minute')
          .second(0)
          .format(),
      });
    }
    const filteredAvailableSlotsInReceiverTimezone =
      availableSlotsInReceiverTimezone.filter((a) => {
        const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
          const partA = dayjs(a.endDate)
            .tz(receiverTimezone)
            .second(0)
            .isBetween(
              dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'),
              dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'),
              'm',
              '[]'
            );

          const partB = dayjs(a.startDate)
            .tz(receiverTimezone)
            .second(0)
            .isBetween(
              dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'),
              dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'),
              'm',
              '[]'
            );

          const partC =
            dayjs(na.startDate)
              .tz(receiverTimezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') ===
              dayjs(a.startDate)
                .tz(receiverTimezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm') &&
            dayjs(na.endDate)
              .tz(receiverTimezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') ===
              dayjs(a.endDate)
                .tz(receiverTimezone)
                .second(0)
                .format('YYYY-MM-DDTHH:mm');

          const isNotAvailable = partA || partB || partC;

          // console.log(a, na, ' a, na')

          return isNotAvailable;
        });

        console.log(foundIndex, ' foundIndex');

        if (foundIndex !== undefined && foundIndex > -1) {
          return false;
        }

        return true;
      });

    console.log(
      filteredAvailableSlotsInReceiverTimezone,
      ' filteredAvailableSlots server timezone'
    );
    return filteredAvailableSlotsInReceiverTimezone;
  }

  // not first day start from work start time schedule

  const startTimesBySender = senderPreferences.startTimes;

  const endTimesBySender = senderPreferences.endTimes;

  const dayOfWeekIntAsReceiver = getISODay(
    dayjs(senderStartDateInReceiverTimezone?.slice(0, 19))
      .tz(receiverTimezone, true)
      .toDate()
  );
  const dayOfMonthAsReceiver = dayjs(
    senderStartDateInReceiverTimezone?.slice(0, 19)
  )
    .tz(receiverTimezone, true)
    .date();

  // convert to user timezone so everything is linked to user timezone
  let endHourBySender =
    endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)?.hour ?? 20;
  let endMinuteBySender =
    endTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)?.minutes ??
    0;

  // if last day change end time to hostStartDate provided
  if (isLastDay && senderEndDateInReceiverTimezone) {
    endHourBySender = dayjs(senderEndDateInReceiverTimezone)
      .tz(senderTimezone)
      .hour();
    // create slot sizes
    const flooredValue = Math.floor(60 / slotDuration);

    let minuteValueBySender = 0;
    for (let i = 0; i < flooredValue; i++) {
      const endMinutes = (i + 1) * slotDuration;
      const startMinutes = i * slotDuration;
      if (
        dayjs(senderEndDateInReceiverTimezone)
          .tz(senderTimezone)
          .isBetween(
            dayjs(senderEndDateInReceiverTimezone)
              .tz(senderTimezone)
              .minute(startMinutes),
            dayjs(senderEndDateInReceiverTimezone)
              .tz(senderTimezone)
              .minute(endMinutes),
            'minute',
            '[)'
          )
      ) {
        minuteValueBySender = startMinutes;
      }
    }

    endMinuteBySender = minuteValueBySender;
  }

  const startHourBySender =
    (startTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)
      ?.hour as number) || 8;
  const startMinuteBySender =
    (startTimesBySender?.find((i) => i.day === dayOfWeekIntAsReceiver)
      ?.minutes as number) || 0;

  const startDuration = dayjs.duration({
    hours: startHourBySender,
    minutes: startMinuteBySender,
  });
  const endDuration = dayjs.duration({
    hours: endHourBySender,
    minutes: endMinuteBySender,
  });
  const totalDuration = endDuration.subtract(startDuration);
  const totalMinutes = totalDuration.asMinutes();

  const availableSlotsInReceiverTimezone: AvailableSlotType[] = [];
  console.log(
    senderStartDateInReceiverTimezone,
    endTimesBySender,
    dayOfWeekIntAsReceiver,
    dayOfMonthAsReceiver,
    startHourBySender,
    startMinuteBySender,
    endHourBySender,
    endMinuteBySender,
    timezone,
    `startDate, endTimes, dayOfWeekIntByHost, dayOfMonth, startHour, startMinute, endHour, endMinute totalMinutes, timezone, inside firstDay inside generateAvailableslots`
  );
  for (let i = 0; i < totalMinutes; i += slotDuration) {
    if (i > totalMinutes) {
      continue;
    }

    availableSlotsInReceiverTimezone.push({
      id: uuid(),
      startDate: dayjs(senderStartDateInReceiverTimezone)
        .tz(senderTimezone)
        .hour(startHourBySender)
        .minute(startMinuteBySender)
        .tz(receiverTimezone)
        .add(i, 'minute')
        .second(0)
        .format(),
      endDate: dayjs(senderStartDateInReceiverTimezone)
        .tz(senderTimezone)
        .hour(startHourBySender)
        .minute(startMinuteBySender)
        .tz(receiverTimezone)
        .add(i + slotDuration, 'minute')
        .second(0)
        .format(),
    });
  }

  console.log(
    availableSlotsInReceiverTimezone,
    ' timeSlots inside generateTimeSlots not first day'
  );
  console.log(
    notAvailableSlotsInEventTimezone,
    ' notAvailableSlotsInEventTimezone not first day'
  );

  // filter out unavailable times
  const filteredAvailableSlotsInReceiverTimezone =
    availableSlotsInReceiverTimezone.filter((a) => {
      const foundIndex = notAvailableSlotsInEventTimezone?.findIndex((na) => {
        const partA = dayjs(a.endDate)
          .tz(receiverTimezone)
          .second(0)
          .isBetween(
            dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'),
            dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'),
            'm',
            '[]'
          );

        const partB = dayjs(a.startDate)
          .tz(receiverTimezone)
          .second(0)
          .isBetween(
            dayjs(na.startDate).tz(receiverTimezone).second(0).add(1, 'm'),
            dayjs(na.endDate).tz(receiverTimezone).second(0).subtract(1, 'm'),
            'm',
            '[]'
          );

        const partC =
          dayjs(na.startDate)
            .tz(receiverTimezone)
            .second(0)
            .format('YYYY-MM-DDTHH:mm') ===
            dayjs(a.startDate)
              .tz(receiverTimezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm') &&
          dayjs(na.endDate)
            .tz(receiverTimezone)
            .second(0)
            .format('YYYY-MM-DDTHH:mm') ===
            dayjs(a.endDate)
              .tz(receiverTimezone)
              .second(0)
              .format('YYYY-MM-DDTHH:mm');

        const isNotAvailable = partA || partB || partC;

        // console.log(a, na, ' a, na')

        return isNotAvailable;
      });

      console.log(foundIndex, ' foundIndex');

      if (foundIndex !== undefined && foundIndex > -1) {
        return false;
      }

      return true;
    });

  console.log(
    filteredAvailableSlotsInReceiverTimezone,
    ' filteredAvailableSlots in receiverTimezone'
  );
  // convert to receiverTimezone before returning values
  return filteredAvailableSlotsInReceiverTimezone;
};

export const generateAvailableSlotsforTimeWindow = (
  windowStartDate: string,
  windowEndDate: string,
  slotDuration: number,
  senderPreferences: UserPreferenceType,
  receiverTimezone: string,
  senderTimezone: string,
  notAvailableSlotsInEventTimezone?: NotAvailableSlotType[]
) => {
  const diffDays = dayjs(windowEndDate).diff(dayjs(windowStartDate), 'd');

  const startDatesForEachDay = [];
  const availableSlots: AvailableSlotType[] = [];

  for (let i = 0; i <= diffDays; i++) {
    startDatesForEachDay.push(
      dayjs(windowStartDate.slice(0, 19))
        .tz(receiverTimezone, true)
        .add(i, 'day')
        .format()
    );
  }

  if (diffDays < 1) {
    const generatedSlots = generateAvailableSlotsForDate(
      slotDuration,
      dayjs(windowStartDate.slice(0, 19)).tz(receiverTimezone, true).format(),
      senderPreferences,
      receiverTimezone,
      senderTimezone,
      notAvailableSlotsInEventTimezone,
      true,
      true,
      dayjs(windowEndDate.slice(0, 19)).tz(receiverTimezone, true).format()
    );
    //  0123456789
    //  2020-04-02T08:02:17-05:00
    availableSlots.push(...generatedSlots);
  } else {
    for (let i = 0; i < startDatesForEachDay.length; i++) {
      const filteredNotAvailableSlotsInEventTimezone =
        notAvailableSlotsInEventTimezone?.filter(
          (na) =>
            dayjs(na?.startDate).tz(receiverTimezone).format('YYYY-MM-DD') ===
            dayjs(startDatesForEachDay?.[i])
              .tz(receiverTimezone)
              .format('YYYY-MM-DD')
        );
      if (i === 0) {
        const generatedSlots = generateAvailableSlotsForDate(
          slotDuration,
          startDatesForEachDay?.[i],
          senderPreferences,
          receiverTimezone,
          senderTimezone,
          filteredNotAvailableSlotsInEventTimezone,
          true,
          false,
          dayjs(windowEndDate.slice(0, 19)).tz(receiverTimezone, true).format()
        );
        //  0123456789
        //  2020-04-02T08:02:17-05:00
        availableSlots.push(...generatedSlots);

        continue;
      }

      if (i === startDatesForEachDay.length - 1) {
        const generatedSlots = generateAvailableSlotsForDate(
          slotDuration,
          startDatesForEachDay?.[i],
          senderPreferences,
          receiverTimezone,
          senderTimezone,
          filteredNotAvailableSlotsInEventTimezone,
          false,
          true,
          dayjs(windowEndDate.slice(0, 19)).tz(receiverTimezone, true).format()
        );

        availableSlots.push(...generatedSlots);

        continue;
      }

      const generatedSlots = generateAvailableSlotsForDate(
        slotDuration,
        startDatesForEachDay?.[i],
        senderPreferences,
        receiverTimezone,
        senderTimezone,
        filteredNotAvailableSlotsInEventTimezone
      );

      availableSlots.push(...generatedSlots);
    }
  }

  return { availableSlots };
};

export const generateAvailability = async (
  userId: string,
  windowStartDateInSenderTimezone: string,
  windowEndDateInSenderTimezone: string,
  senderTimezone: string,
  receiverTimezone: string,
  slotDuration: number
) => {
  try {
    const oldEventsInEventTimezone = await listEventsForUserGivenDates(
      userId,
      windowStartDateInSenderTimezone,
      windowEndDateInSenderTimezone
    );

    console.log(oldEventsInEventTimezone, ' oldEventsInEventTimezone');

    if (!oldEventsInEventTimezone || !(oldEventsInEventTimezone?.length > 0)) {
      console.log('no old events in generateAvailability');
    }

    const oldEventsInEventTimezoneFormatted = oldEventsInEventTimezone?.map(
      (e) => ({
        ...e,
        startDate: dayjs(e?.startDate.slice(0, 19))
          .tz(e?.timezone, true)
          .format(),
        endDate: dayjs(e?.endDate.slice(0, 19)).tz(e?.timezone, true).format(),
        timezone: e?.timezone,
      })
    );

    const notAvailableFromEvents: NotAvailableSlotType[] =
      oldEventsInEventTimezoneFormatted?.map((e) => ({
        startDate: e?.startDate,
        endDate: e?.endDate,
      }));

    const userPreferences = await getUserPreferences(userId);

    const { availableSlots: availableSlotsInReceiverTimezone } =
      await generateAvailableSlotsforTimeWindow(
        windowStartDateInSenderTimezone,
        windowEndDateInSenderTimezone,
        slotDuration,
        userPreferences,
        receiverTimezone,
        senderTimezone,
        notAvailableFromEvents?.length > 0 ? notAvailableFromEvents : undefined
      );

    return availableSlotsInReceiverTimezone;
  } catch (e) {
    console.log(e, ' unable to generate availability');
  }
};

export const process_summarize_availability = async (
  body: SummarizeDayAvailabilityType
) => {
  try {
    const userId = body?.userId;
    const dayAvailabilityList = body?.dayAvailabilityList;

    const openai = new OpenAI({
      apiKey: defaultOpenAIAPIKey,
    });

    const summarizedRes = await callOpenAI(
      summarizeAvailabilityResponsesPrompt,
      openAIChatGPTModel,
      dayAvailabilityList,
      openai,
      summarizeAvailabilityResponsesPromptExampleInput,
      summarizeAvailabilityResponsesPromptExampleOutput
    );

    return summarizedRes;
  } catch (e) {
    console.log(e, ' unable to process summarize availability');
  }
};

export const process_day_availibility = async (body: DayAvailabilityType) => {
  try {
    const userId = body?.userId;
    const windowStartDate = body?.windowStartDate;
    const windowEndDate = body?.windowEndDate;
    const senderTimezone = body?.senderTimezone;
    const receiverTimezone = body?.receiverTimezone;
    const slotDuration = body?.slotDuration;

    const openai = new OpenAI({
      apiKey: defaultOpenAIAPIKey,
    });

    // get availability
    const availability = await generateAvailability(
      userId,
      windowStartDate,
      windowEndDate,
      senderTimezone,
      receiverTimezone,
      parseInt(slotDuration, 10)
    );

    if (!(availability?.length > 0)) {
      throw new Error('no availability present');
    }

    const uniqDates = _.uniqBy(availability, (curr) =>
      dayjs(curr?.startDate).tz(receiverTimezone).format('YYYY-MM-DD')
    );

    let availabilityText = '';

    const prompt1 = summarizeAvailabilityPrompt;

    const exampleInput1 = summarizeAvailabilityExampleInput;

    const exampleOutput1 = summarizeAvailabilityExampleOutput;

    let openAIAvailabilityRes = '';

    for (const uniqDate of uniqDates) {
      const filteredAvailability = availability?.filter(
        (a) =>
          dayjs(a?.startDate).tz(receiverTimezone).format('YYYY-MM-DD') ===
          dayjs(uniqDate?.startDate).tz(receiverTimezone).format('YYYY-MM-DD')
      );

      if (filteredAvailability?.length > 0) {
        availabilityText +=
          `${dayjs(uniqDate?.startDate).tz(receiverTimezone).format('L')} - ${filteredAvailability?.map((curr) => `${dayjs(curr?.startDate).tz(receiverTimezone).format('LT')} - ${dayjs(curr?.endDate).tz(receiverTimezone).format('LT')},`)?.reduce((prev, curr) => `${prev} ${curr}`, '')}` +
          '\n\n';

        const miniAvailabilityText =
          `${dayjs(uniqDate?.startDate).tz(receiverTimezone).format('L')} - ${filteredAvailability?.map((curr) => `${dayjs(curr?.startDate).tz(receiverTimezone).format('LT')} - ${dayjs(curr?.endDate).tz(receiverTimezone).format('LT')},`)?.reduce((prev, curr) => `${prev} ${curr}`, '')}` +
          '\n\n';

        const miniUserData = `My availability: ` + miniAvailabilityText;

        console.log(miniUserData, ' newAvailabilityPrompt');

        const miniOpenAIAvailabilityRes = await callOpenAI(
          prompt1,
          openAIChatGPTModel,
          miniUserData,
          openai,
          exampleInput1,
          exampleOutput1
        );

        // validate openai res
        if (!miniOpenAIAvailabilityRes) {
          throw new Error(
            'no openAIAvailabilityRes present inside appointmentRequest'
          );
        }

        openAIAvailabilityRes += '\n' + miniOpenAIAvailabilityRes;
      }
    }

    console.log(openAIAvailabilityRes, ' openAIAvailabilityRes');

    return openAIAvailabilityRes;
  } catch (e) {
    console.log(e, ' unable to process day availability');
  }
};

export const insertAttendeesforEvent = async (attendees: AttendeeType[]) => {
  try {
    // validate
    if (!(attendees?.filter((a) => !!a?.eventId)?.length > 0)) {
      return;
    }

    const operationName = 'InsertAttendeesForEvent';
    const query = `
            mutation InsertAttendeesForEvent($attendees: [Attendee_insert_input!]!) {
                insert_Attendee(objects: $attendees) {
                    affected_rows
                    returning {
                        additionalGuests
                        comment
                        contactId
                        createdDate
                        deleted
                        emails
                        eventId
                        id
                        imAddresses
                        name
                        optional
                        phoneNumbers
                        resource
                        responseStatus
                        updatedAt
                        userId
                    }
                }
            }
        `;
    const variables = {
      attendees,
    };

    const response: {
      data: {
        insert_Attendee: { affected_rows: number; returning: AttendeeType[] };
      };
    } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(
      response?.data?.insert_Attendee?.returning,
      ' this is response in insertAttendees'
    );
    response?.data?.insert_Attendee?.returning.forEach((r) =>
      console.log(r, ' response in insertAttendees')
    );
  } catch (e) {
    console.log(e, ' unable to insert Attendees for new event');
  }
};

export const deleteAttendeesWithIds = async (
  eventIds: string[],
  userId: string
) => {
  try {
    // validate
    if (!(eventIds?.filter((e) => !!e)?.length > 0)) {
      return;
    }
    eventIds.forEach((e) =>
      console.log(e, ' eventIds inside deleteRemindersWithIds')
    );
    const operationName = 'DeleteAttendeesWithEventIds';
    const query = `
            mutation DeleteAttendeesWithEventIds($userId: uuid!, $eventIds: [String!]!) {
                delete_Attendee(where: {userId: {_eq: $userId}, eventId: {_in: $eventIds}}) {
                    affected_rows
                    returning {
                        additionalGuests
                        comment
                        contactId
                        createdDate
                        deleted
                        emails
                        eventId
                        id
                        imAddresses
                        name
                        optional
                        phoneNumbers
                        resource
                        responseStatus
                        updatedAt
                        userId
                    }
                }
            }

    `;

    const variables = {
      userId,
      eventIds,
    };

    const response = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();
    console.log(response, ' this is response in deleteAttendeesWithIds');
  } catch (e) {
    console.log(e, ' deleteAttendeesWithIds');
  }
};
