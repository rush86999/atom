import axios from 'axios';
import Session from 'supertokens-web-js/recipe/session';

import { dayjs } from '@lib/date-utils';
import qs from 'qs';
import { v4 as uuid } from 'uuid';
import {
  googleAtomicWebAuthRefreshUrl,
  googleCalendarAndroidAuthRefreshUrl,
  googleCalendarIosAuthRefreshUrl,
} from '@lib/constants';
// dayjs.extend(utc)

import { googleConfig } from '@lib/dataTypes/configs';

import {
  googleURL,
  googleCalendarURL,
  googleCalendarName,
  googleResourceName,
  googleColorUrl,
  selfGoogleCalendarWatchUrl,
} from '@lib/calendarLib/constants';
import {
  calendarResponse,
  eventResponse,
  GoogleAttendeeType,
  ConferenceDataType,
  extendedProperties,
  GoogleReminderType,
  source,
  TransparencyType,
  VisibilityType,
  SendUpdatesType,
  allowedConferenceSolutionType,
  attachment,
  eventType1,
  // Collections,
  // Internals,
  // InstanceCreationOptions,
  DefaultReminderType,
  NotificationType,
  colorResponseType,
  RefreshTokenResponseBodyType,
} from '@lib/calendarLib/types';

import { updateCalendarIntegration } from '@lib/api-helper';

import { hasuraApiUrl } from '@lib/constants';
import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client';
import getCalendarIntegrationByResource from '@lib/apollo/gql/getCalendarIntegrationByResourceAndName';
import { CalendarIntegrationType } from '@lib/dataTypes/Calendar_IntegrationType';
import getCalendarPushNotificationByCalendarId from '@lib/apollo/gql/getCalendarPushNotificationByCalendarId';
import { CalendarWebhookType } from '@lib/dataTypes/CalendarWebhookType';
import listCalendarPushNotificationsByUserId from '@lib/apollo/gql/listCalendarPushNotificationsByUserId';
import deleteCalendarPushNotificationByCalendarId from '@lib/apollo/gql/deleteCalendarPushNotificationByCalendarId';

// type Collections = {
//     [key: string]: RxCollection;
// }
// type Internals = any
// type InstanceCreationOptions = any

// const result = await axios.post(url, data, config)

export const checkIfCalendarWebhookExpired = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const calendarWebhooks = (
      await client.query<{ Calendar_Push_Notification: CalendarWebhookType[] }>(
        {
          query: listCalendarPushNotificationsByUserId,
          variables: {
            userId,
          },
        }
      )
    )?.data?.Calendar_Push_Notification;

    // loop through each and refresh expired webhooks
    for (let i = 0; i < calendarWebhooks.length; i++) {
      if (dayjs().isAfter(dayjs(calendarWebhooks[i]?.expiration))) {
        await enableCalendarWebhook(calendarWebhooks[i]);
      }
    }
  } catch (e) {
    console.log(e, ' unable to check if calendar webhook expired');
  }
};

export const enableCalendarWebhook = async (webhook: CalendarWebhookType) => {
  try {
    const token = await Session.getAccessToken();
    const url = selfGoogleCalendarWatchUrl;
    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    };

    const data = {
      calendarId: webhook?.calendarId,
      userId: webhook?.userId,
      channelId: webhook?.id,
    };
    const results = await axios.post(url, data, config);
    console.log(results, ' results inside enableCalendarWebhook');
  } catch (e) {
    console.log(e, ' unable to enable calendar webhook');
  }
};

export const deleteCalendarWebhook = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendarId: string
) => {
  try {
    /**
     * const googleInteg = (await client.query<{ Calendar_Integration: CalendarIntegrationType[] }>({
      query: getCalendarIntegrationByResource,
      variables: {
        userId,
        name: googleCalendarName,
        resource: googleCalendarResource,
      }
    }))?.data?.Calendar_Integration?.[0]
     */
    const res = await client.mutate<{
      delete_Calendar_Push_Notification: { affected_rows: number };
    }>({
      mutation: deleteCalendarPushNotificationByCalendarId,
      variables: {
        calendarId,
      },
    });
    console.log(res, ' res inside deleteCalendarWebhookByCalendarId');
  } catch (e) {
    console.log(e, ' unable to delete calendar web hook');
  }
};

export const getCalendarWebhook = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendarId: string
) => {
  try {
    const calendarWebhook = (
      await client.query<{ Calendar_Push_Notification: CalendarWebhookType[] }>(
        {
          query: getCalendarPushNotificationByCalendarId,
          variables: {
            calendarId,
          },
        }
      )
    )?.data?.Calendar_Push_Notification?.[0];

    console.log(calendarWebhook, ' calendarWebhook');
    return calendarWebhook;
  } catch (e) {
    console.log(e, ' unable to get calendar webhook');
  }
};

export const getGoogleCalendarSyncApiToken = async () => {
  try {
    const token = await Session.getAccessToken();
    const url = hasuraApiUrl;
    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };
    const operationName = 'GetGoogleCalendarSyncToken';
    const query = `
      query GetGoogleCalendarSyncToken($name: String!, $resource: String!) {
        Admin(where: {name: {_eq: $name}, resource: {_eq: $resource}}) {
          id
          name
          token
          resource
        }
      }
    `;
    const variables = {
      name: 'googleCalendarSync',
      resource: 'aws',
    };

    const data = {
      operationName,
      query,
      variables,
    };
    const results = await axios.post(url, data, config);

    if (results?.data?.Admin?.[0]?.id) {
      const token = results?.data?.Admin?.[0]?.token;
      return token;
    }
  } catch (e) {
    console.log(e, ' unable to get apiToken');
  }
};

export const houseKeepSyncEnabledGoogleCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    // get token and expiresAt
    const googleInteg = (
      await client.query<{ Calendar_Integration: CalendarIntegrationType[] }>({
        query: getCalendarIntegrationByResource,
        variables: {
          userId,
          name: googleCalendarName,
          resource: googleResourceName,
        },
      })
    )?.data?.Calendar_Integration?.[0];

    const oldEnabled = googleInteg?.enabled;
    const oldSyncEnabled = googleInteg?.syncEnabled;
    const updatedAt = dayjs().toISOString();

    const updateIntegration = gql`
      mutation UpdateCalendarIntegrationById(
        $id: uuid!
        $syncEnabled: Boolean
      ) {
        update_Calendar_Integration_by_pk(
          _set: { syncEnabled: $syncEnabled }
          pk_columns: { id: $id }
        ) {
          appAccountId
          appEmail
          appId
          colors
          contactEmail
          contactName
          createdDate
          deleted
          enabled
          expiresAt
          id
          name
          pageToken
          password
          refreshToken
          syncEnabled
          resource
          token
          syncToken
          updatedAt
          userId
          username
          clientType
        }
      }
    `;
    let variables: any = {
      id: googleInteg?.id,
    };

    if (oldEnabled && !oldSyncEnabled) {
      variables = {
        ...variables,
        syncEnabled: true,
        updatedAt,
      };
    } else if (!oldEnabled && oldSyncEnabled) {
      variables = {
        ...variables,
        syncEnabled: false,
        updatedAt,
      };
    }

    if (variables?.updatedAt) {
      await client.mutate({
        mutation: updateIntegration,
        variables,
      });
    }
    if (oldEnabled && !oldSyncEnabled) {
      await getGoogleToken(client, userId);
    }
  } catch (e) {
    console.log(
      e,
      ' unable to housekeep sync enabled for google calendar integration'
    );
  }
};

export const googleMeetAvailable = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const token = await getGoogleToken(client, userId);

    if (token && token?.length > 0) {
      return true;
    }
    return false;
  } catch (e) {
    console.log(e, ' google meet is not avilable');
  }
};

export const getGoogleToken = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    // get token and expiresAt
    const googleInteg = (
      await client.query<{ Calendar_Integration: CalendarIntegrationType[] }>({
        query: getCalendarIntegrationByResource,
        variables: {
          userId,
          name: googleCalendarName,
          resource: googleResourceName,
        },
      })
    )?.data?.Calendar_Integration?.[0];

    const token = googleInteg?.token;
    const expiresAt = googleInteg?.expiresAt;
    const oldRefreshToken = googleInteg?.refreshToken;

    if (dayjs().isAfter(dayjs(expiresAt))) {
      let newAccessToken = '';
      let newRefreshToken = '';
      let newExpiresAt = '';

      if (googleInteg?.clientType === 'ios' && oldRefreshToken) {
        const url = googleCalendarIosAuthRefreshUrl;
        const token = await Session.getAccessToken();
        const config = {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        };

        const data = {
          refreshToken: oldRefreshToken,
        };

        const results: {
          data: {
            message: string;
            event: RefreshTokenResponseBodyType;
          };
        } = await axios.post(url, data, config);
        console.log(results, ' results inside enableGoogleCalendarSync');

        newAccessToken = results?.data?.event?.access_token;
        newRefreshToken = oldRefreshToken;
        newExpiresAt = dayjs()
          .add(results?.data?.event?.expires_in, 'seconds')
          .toISOString();
      } else if (
        (googleInteg?.clientType === 'web' ||
          googleInteg?.clientType === 'android') &&
        oldRefreshToken
      ) {
        const url = googleCalendarAndroidAuthRefreshUrl;
        const token = await Session.getAccessToken();
        const config = {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        };

        const data = {
          refreshToken: oldRefreshToken,
        };

        const results: {
          data: {
            message: string;
            event: RefreshTokenResponseBodyType;
          };
        } = await axios.post(url, data, config);
        console.log(results, ' results inside enableGoogleCalendarSync');

        newAccessToken = results?.data?.event?.access_token;
        newRefreshToken = oldRefreshToken;
        newExpiresAt = dayjs()
          .add(results?.data?.event?.expires_in, 'seconds')
          .toISOString();
      } else if (googleInteg?.clientType === 'atomic-web' && oldRefreshToken) {
        const url = googleAtomicWebAuthRefreshUrl;
        const token = await Session.getAccessToken();
        const config = {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        };

        const data = {
          refreshToken: oldRefreshToken,
        };

        const results: {
          data: {
            message: string;
            event: RefreshTokenResponseBodyType;
          };
        } = await axios.post(url, data, config);
        console.log(results, ' results inside enableGoogleCalendarSync');

        newAccessToken = results?.data?.event?.access_token;
        newRefreshToken = oldRefreshToken;
        newExpiresAt = dayjs()
          .add(results?.data?.event?.expires_in, 'seconds')
          .toISOString();
      }

      //googleAtomicWebAuthRefreshUrl

      await updateCalendarIntegration(
        client,
        googleInteg?.id,
        undefined,
        newAccessToken,
        newRefreshToken,
        newExpiresAt,
        googleInteg?.clientType === 'android' ? 'web' : googleInteg?.clientType
      );

      return newAccessToken;
    }

    return token;
  } catch (e) {
    console.log(e, ' unable to getGoogleToken');
  }
};

export const patchGoogleCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  calendarId: string,
  summary?: string,
  description?: string,
  location?: string,
  timeZone?: string,
  allowedConferenceSolutionTypes?: allowedConferenceSolutionType[]
) => {
  try {
    // get token =
    const token = await getGoogleToken(client, userId);
    let url = `${googleCalendarURL}/${encodeURI(calendarId)}`;

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    let data: any = {};

    if (summary && summary?.length > 0) {
      data = { ...data, summary };
    }

    if (description && description?.length > 0) {
      data = { ...data, description };
    }

    if (location && location?.length > 0) {
      data = { ...data, location };
    }

    if (timeZone && timeZone?.length > 0) {
      data = { ...data, timeZone };
    }

    if (
      allowedConferenceSolutionTypes &&
      allowedConferenceSolutionTypes?.[0]?.length > 0
    ) {
      data = {
        ...data,
        conferenceProperties: {
          allowedConferenceSolutionTypes,
        },
      };
    }

    const results = await axios.patch<calendarResponse>(url, data, config);

    console.log(results, ' results after patching calendar');
  } catch (e) {
    console.log(e, ' unable to patch google calendar');
  }
};

// create calendar
export const createGoogleCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  id: string,
  summary: string,
  defaultReminders?: DefaultReminderType[],
  notifications?: NotificationType[]
) => {
  try {
    // get token =
    const token = await getGoogleToken(client, userId);
    let url = googleCalendarURL;

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    let data: any = { id, summaryOverride: summary, selected: true };

    if (defaultReminders && defaultReminders?.[0]?.method?.length > 0) {
      data = { ...data, defaultReminders };
    }

    if (notifications && notifications?.[0]?.method?.length > 0) {
      data = {
        ...data,
        notificationSettings: {
          notifications,
        },
      };
    }

    const result = await axios.post(url, data, config);
    console.log(result, ' successfully created secondary google calendar');
  } catch (e) {
    console.log(e, ' unable to create google calendar');
  }
};

// get calendar info
export const getGoogleCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  calendarId: string
) => {
  try {
    // get token =
    const token = await getGoogleToken(client, userId);
    let url = `${googleCalendarURL}/${encodeURI(calendarId)}`;

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    const results = await axios.get(url, config);
    console.log(results, ' results for get calendar');
    return results;
  } catch (e) {
    console.log(e, ' unable to get calendar');
  }
};

export const deleteGoogleEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  calendarId: string,
  googleEventId: string,
  sendUpdates: SendUpdatesType = 'all'
) => {
  try {
    // get token =
    const token = await getGoogleToken(client, userId);
    let url = `${googleURL}/${encodeURI(calendarId)}/events/${encodeURI(googleEventId)}`;

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };
    // path params
    if (sendUpdates) {
      url = `${url}?`;
      let params = { sendUpdates };

      url = `${url}${qs.stringify(params)}`;
    }

    const result = await axios.delete(url, config);
    console.log(result, ' result after delete event');
  } catch (e) {
    console.log(e, ' unable to delete google event');
  }
};

// delete secondary calendar
export const deleteGoogleCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  calendarId: string
) => {
  try {
    // get token =
    const token = await getGoogleToken(client, userId);
    let url = `${googleCalendarURL}/${encodeURI(calendarId)}`;

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    const results = await axios.delete(url, config);
    console.log(results, ' successfully deleted secondary calendar');
  } catch (e) {
    console.log(e, ' unable to catch google calendar');
  }
};

export const getGoogleColors = async (token: string) => {
  try {
    const url = googleColorUrl;
    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    const { data } = await axios.get<colorResponseType>(url, config);
    console.log(data, ' data for get colors');
    return data;
  } catch (e) {
    console.log(e, ' unable to get google colors');
  }
};

export const clearGoogleCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  calendarId: string
) => {
  try {
    // get token =
    const token = await getGoogleToken(client, userId);
    let url = `${googleURL}/${encodeURI(calendarId)}/clear`;

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    const results = await axios.post(url, undefined, config);
    console.log(results, ' results from post');
  } catch (e) {
    console.log(e, ' unable to delete google event');
  }
};

export const patchGoogleEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  calendarId: string,
  eventId: string,
  endDateTime?: string, // either endDateTime or endDate - all day vs specific period
  startDateTime?: string,
  conferenceDataVersion?: 0 | 1,
  maxAttendees?: number,
  sendUpdates?: SendUpdatesType,
  anyoneCanAddSelf?: boolean,
  attendees?: GoogleAttendeeType[],
  conferenceData?: ConferenceDataType,
  summary?: string,
  description?: string,
  timezone?: string, // required for recurrence
  startDate?: string,
  endDate?: string,
  extendedProperties?: extendedProperties,
  guestsCanInviteOthers?: boolean,
  guestsCanModify?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalStartDateTime?: string,
  originalStartDate?: string,
  recurrence?: string[],
  reminders?: GoogleReminderType,
  source?: source,
  status?: string,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  iCalUID?: string,
  attendeesOmitted?: boolean,
  hangoutLink?: string,
  privateCopy?: boolean,
  locked?: boolean,
  attachments?: attachment[],
  eventType?: eventType1,
  location?: string
) => {
  try {
    // get token =
    const token = await getGoogleToken(client, userId);
    let url = `${googleURL}/${encodeURI(calendarId)}/events/${encodeURI(eventId)}`;

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    // if any query parameters build them
    if (
      maxAttendees ||
      sendUpdates ||
      (typeof conferenceDataVersion === 'number' && conferenceDataVersion > -1)
    ) {
      url = `${url}?`;
      let params: any = {};

      if (maxAttendees) {
        params.maxAttendees = maxAttendees;
      }

      if (sendUpdates) {
        params.sendUpdates = sendUpdates;
      }

      if (
        typeof conferenceDataVersion === 'number' &&
        conferenceDataVersion > -1
      ) {
        params.conferenceDataVersion = conferenceDataVersion;
      }

      if (
        params?.maxAttendees ||
        params?.sendUpdates ||
        params?.conferenceDataVersion > -1
      ) {
        url = `${url}${qs.stringify(params)}`;
      }
    }

    // create request body
    let data: any = {};

    if (endDate && timezone && !endDateTime) {
      const end = {
        date: dayjs(endDate).format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      data.end = end;
    }

    if (endDateTime && timezone && !endDate) {
      const end = {
        dateTime: dayjs(endDateTime).format(),
        timeZone: timezone,
      };
      data.end = end;
    }

    if (startDate && timezone && !startDateTime) {
      const start = {
        date: dayjs(startDate).format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      data.start = start;
    }

    if (startDateTime && timezone && !startDate) {
      const start = {
        dateTime: dayjs(startDateTime).format(),
        timeZone: timezone,
      };
      data.start = start;
    }

    if (originalStartDate && timezone && !originalStartDateTime) {
      const originalStartTime = {
        date: dayjs(originalStartDate).format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      data.originalStartTime = originalStartTime;
    }

    if (originalStartDateTime && timezone && !originalStartDate) {
      const originalStartTime = {
        dateTime: dayjs(originalStartDateTime).format(),
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

    if (description && description?.length > 0) {
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

    if (reminders) {
      data = { ...data, reminders };
    }

    if (source?.title || source?.url) {
      data = { ...data, source };
    }

    if (attachments?.[0]?.fileId) {
      data = { ...data, attachments };
    }

    if (eventType && eventType?.length > 0) {
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

    if (iCalUID && iCalUID?.length > 0) {
      data = { ...data, iCalUID };
    }

    if (attendeesOmitted) {
      data = { ...data, attendeesOmitted };
    }

    if (hangoutLink && hangoutLink?.length > 0) {
      data = { ...data, hangoutLink };
    }

    if (summary && summary?.length > 0) {
      data = { ...data, summary };
    }

    if (location && location?.length > 0) {
      data = { ...data, location };
    }
    console.log(url, data, ' url, data inside google patch');
    const results = await axios.patch(url, data, config);
    console.log(results, ' results from patch google event');
  } catch (e) {
    console.log(e, ' unable to patch google event');
  }
};

export const createGoogleEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  calendarId: string,
  endDateTime?: string, // either endDateTime or endDate - all day vs specific period
  startDateTime?: string,
  conferenceDataVersion?: 0 | 1,
  maxAttendees?: number,
  sendUpdates?: SendUpdatesType,
  anyoneCanAddSelf?: boolean,
  attendees?: GoogleAttendeeType[],
  conferenceData?: ConferenceDataType,
  summary?: string,
  description?: string,
  timezone?: string, // required for recurrence
  startDate?: string,
  endDate?: string,
  extendedProperties?: extendedProperties,
  guestsCanInviteOthers?: boolean,
  guestsCanModify?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalStartDateTime?: string,
  originalStartDate?: string,
  recurrence?: string[],
  reminders?: GoogleReminderType,
  source?: source,
  status?: string,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  iCalUID?: string,
  attendeesOmitted?: boolean,
  hangoutLink?: string,
  privateCopy?: boolean,
  locked?: boolean,
  attachments?: attachment[],
  eventType?: eventType1,
  location?: string
) => {
  try {
    // get token =
    const token = await getGoogleToken(client, userId);
    let url = `${googleURL}/${encodeURI(calendarId)}/events`;

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    // if any query parameters build them
    // first
    if (
      maxAttendees ||
      sendUpdates ||
      (typeof conferenceDataVersion === 'number' && conferenceDataVersion > 0)
    ) {
      url = `${url}?`;
      let params: any = {};

      if (maxAttendees) {
        params = { ...params, maxAttendees };
      }

      if (sendUpdates) {
        params = { ...params, sendUpdates };
      }

      if (
        typeof conferenceDataVersion === 'number' &&
        conferenceDataVersion > -1
      ) {
        params = { ...params, conferenceDataVersion };
      }

      if (
        params?.maxAttendees ||
        params?.sendUpdates ||
        params?.conferenceDataVersion > -1
      ) {
        url = `${url}${qs.stringify(params)}`;
      }
    }

    // create request body
    let data: any = {};

    if (endDateTime && timezone && !endDate) {
      const end = {
        dateTime: dayjs(endDateTime).format(),
        timeZone: timezone,
      };

      data.end = end;
    }

    if (endDate && timezone && !endDateTime) {
      const end = {
        date: dayjs(endDate).format('YYYY-MM-DD'),
        timeZone: timezone,
      };

      data.end = end;
    }

    if (startDate && timezone && !startDateTime) {
      const start = {
        date: dayjs(startDate).format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      data.start = start;
    }

    if (startDateTime && timezone && !startDate) {
      const start = {
        dateTime: dayjs(startDateTime).format(),
        timeZone: timezone,
      };
      data.start = start;
    }

    if (originalStartDate && timezone && !originalStartDateTime) {
      const originalStartTime = {
        date: dayjs(originalStartDate).format('YYYY-MM-DD'),
        timeZone: timezone,
      };
      data.originalStartTime = originalStartTime;
    }

    if (originalStartDateTime && timezone && !originalStartDate) {
      const originalStartTime = {
        dateTime: dayjs(originalStartDateTime).format(),
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

    if (description && description?.length > 0) {
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

    if (reminders) {
      data = { ...data, reminders };
    }

    if (source?.title || source?.url) {
      data = { ...data, source };
    }

    if (attachments?.[0]?.fileId) {
      data = { ...data, attachments };
    }

    if (eventType && eventType?.length > 0) {
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

    if (iCalUID && iCalUID?.length > 0) {
      data = { ...data, iCalUID };
    }

    if (attendeesOmitted) {
      data = { ...data, attendeesOmitted };
    }

    if (hangoutLink && hangoutLink?.length > 0) {
      data = { ...data, hangoutLink };
    }

    if (summary && summary?.length > 0) {
      data = { ...data, summary };
    }

    if (location && location?.length > 0) {
      data = { ...data, location };
    }

    const results = await axios.post<eventResponse>(url, data, config);

    console.log(results, ' results from googleCreateEvent');
    return results?.data?.id;
  } catch (e: any) {
    console.log(e, ' createGoogleEvent');
    console.log(
      e?.response?.data?.error?.message,
      ' error from googleCreateEvent'
    );
    console.log(e?.toJSON(), ' error from googleCreateEvent');
  }
};
