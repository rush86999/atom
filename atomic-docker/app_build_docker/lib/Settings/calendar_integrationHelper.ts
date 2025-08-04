import { v4 as uuid } from 'uuid';
import { dayjs } from '@lib/date-utils';
import axios from 'axios';
import Session from 'supertokens-web-js/recipe/session';
import qs from 'qs';
import { retry } from '@lifeomic/attempt';

// dayjs.extend(utc)
// dayjs.extend(timezone)

import { ConfigType } from '@lib/dataTypes/ConfigType';
import { hasuraApiUrl } from '@lib/constants';

import {
  googleCalendarSyncUrl,
  googleCalendarURL,
  googleCalendarName,
  googleResourceName,
  localCalendarName,
  localCalendarResource,
} from '@lib/calendarLib/constants';

import {
  googlePeopleSyncUrl,
  googlePeopleName,
  googlePeopleResource,
  localContactsName,
  localContactsResource,
} from '@lib/contactLib/constants';

import { zoomName, zoomResourceName } from '@lib/zoom/constants';

import {
  CalendarListResponseType,
  CalendarListItemResponseType,
} from '@lib/calendarLib/types';

import {
  CalendarIntegrationType,
  colorType,
} from '@lib/dataTypes/Calendar_IntegrationType';
import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client';
import getCalendarIntegrationById from '@lib/apollo/gql/getCalendarIntegrationById';
import upsertCalendarIntegrations from '@lib/apollo/gql/upsertCalendarIntegrations';
import listCalendarIntegrations from '@lib/apollo/gql/listCalendarIntegrations';

const INTEGRATIONS = [
  {
    id: uuid(),
    resource: googleResourceName,
    name: googleCalendarName,
    enabled: false,
    syncEnabled: false,
    updatedAt: dayjs().format(),
    createdDate: dayjs().format(),
    deleted: false,
    clientType: 'atomic-web',
  },
  {
    id: uuid(),
    resource: zoomResourceName,
    name: zoomName,
    enabled: false,
    syncEnabled: false,
    updatedAt: dayjs().format(),
    createdDate: dayjs().toISOString(),
    deleted: false,
    clientType: 'web',
  },
  {
    id: uuid(),
    resource: googlePeopleResource,
    name: googlePeopleName,
    enabled: false,
    syncEnabled: false,
    updatedAt: dayjs().format(),
    createdDate: dayjs().toISOString(),
    deleted: false,
    clientType: 'atomic-web',
  },
  // {
  //   id: uuid(),
  //   resource: localContactsResource,
  //   name: localContactsName,
  //   enabled: false,
  //   syncEnabled: false,
  //   updatedAt: dayjs().format(),
  //   createdDate: dayjs().toISOString(),
  //   deleted: false,
  //   clientType: 'atomic-web',
  // },
  // {
  //   id: uuid(),
  //   resource: localCalendarResource,
  //   name: localCalendarName,
  //   enabled: false,
  //   syncEnabled: false,
  //   updatedAt: dayjs().format(),
  //   createdDate: dayjs().toISOString(),
  //   deleted: false,
  //   clientType: 'atomic-web',
  // },
];

export const deleteEventTriggerById = async (id: string) => {
  try {
    const token = await Session.getAccessToken();
    const operationName = 'deleteEventTriggerById';
    const query = `
      mutation deleteEventTriggerById($id: uuid!) {
        delete_Event_Trigger_by_pk(id: $id) {
          id
        }
      }
    `;
    const variables = { id };
    const config = {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    };

    const data = {
      operationName,
      query,
      variables,
    };

    const response = await axios.post(hasuraApiUrl, data, config);
    console.log(response?.data, ' deleteEventTriggerById');
  } catch (e) {
    console.log(e, ' deleteEventTriggerById');
  }
};

export const deleteEventTriggerByResourceId = async (resourceId: string) => {
  try {
    const token = await Session.getAccessToken();
    const operationName = 'deleteEventTriggerByResourceId';
    const query = `
      mutation deleteEventTriggerByResourceId($resourceId: String!) {
        delete_Event_Trigger(where: {resourceId: {_eq: $resourceId}}) {
          affected_rows
        }
      }
    `;
    const variables = { resourceId };
    const config = {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    };
    const data = {
      operationName,
      query,
      variables,
    };
    const response = await axios.post(hasuraApiUrl, data, config);
    console.log(response?.data, ' deleteEventTriggerByResourceId');
  } catch (e) {
    console.log(e, ' deleteEventTriggerByResourceId');
  }
};

export const deleteEventTriggers = async (
  userId: string,
  resource: string,
  name: string
) => {
  try {
    const token = await Session.getAccessToken();
    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    };

    const operationName = 'deleteEventTriggers';
    const query = `
      mutation deleteEventTriggers($userId: uuid!, $resource: String!, $name: String!) {
        delete_Event_Trigger(where: {userId: {_eq: $userId}, resource: {_eq: $resource}, name: {_eq: $name}}) {
          affected_rows
        }
      }
    `;

    const variables = {
      userId,
      resource,
      name,
    };

    const data = {
      operationName,
      query,
      variables,
    };

    const results = await axios.post(hasuraApiUrl, data, config);

    console.log(results, ' able to successfully delete event triggers');
  } catch (e) {
    console.log(e, ' unable to call deleteEventTriggers');
  }
};

export const listGoogleCalendars = async (googleToken: string) => {
  try {
    let url = googleCalendarURL;
    const config = {
      headers: {
        Authorization: `Bearer ${googleToken}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    let isMore = true;

    const calendarList: CalendarListItemResponseType[] = [];

    while (isMore) {
      const results = await retry(
        async () => axios.get<CalendarListResponseType>(url, config),
        {
          delay: 200,
          factor: 2,
          maxAttempts: 5,
          maxDelay: 500,
        }
      );

      const items = results?.data?.items;
      calendarList.push(...items);
      console.log(items, ' items');
      // reset url
      url = googleCalendarURL;
      if (results?.data?.nextPageToken) {
        let params: any = {};
        if (results?.data?.nextPageToken) {
          params.pageToken = results?.data?.nextPageToken;
        }
        url = `${url}?${qs.stringify(params)}`;
      } else {
        isMore = false;
      }
    }

    return calendarList;
  } catch (e) {
    console.log(e, ' unable to list google calendars');
  }
};

export const triggerGoogleCalendarSync = async (
  calendarIntegrationId: string,
  calendarId: string,
  userId: string
) => {
  try {
    if (!calendarIntegrationId) {
      console.log(' no calendarINtegrationid');
      return;
    }

    if (!calendarId) {
      console.log('no calendarId');
      return;
    }

    if (!userId) {
      console.log('no userId');
      return;
    }
    const token = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    };

    const data = {
      calendarIntegrationId,
      calendarId,
      userId,
      isInitialSync: true,
      timezone: dayjs.tz.guess(),
    };

    const url = googleCalendarSyncUrl;

    const results = await axios.post(url, data, config);

    console.log(results, ' successfully triggered google calendar sync');
  } catch (e) {
    console.log(e, ' unable to trigger google calendar sync');
  }
};

export const triggerGooglePeopleSync = async (
  calendarIntegrationId: string,
  userId: string
) => {
  try {
    console.log('triggerGooglePeopleSyn called');
    if (!calendarIntegrationId) {
      console.log(' no calendarINtegrationid');
      return;
    }

    if (!userId) {
      console.log('no userId');
      return;
    }
    const token = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    };

    const data = {
      calendarIntegrationId,
      userId,
      isInitialSync: true,
    };

    const url = googlePeopleSyncUrl;

    const results = await axios.post(url, data, config);

    console.log(results, ' successfully triggered google people sync');
  } catch (e: any) {
    console.log(e, ' unable to trigger google people sync');
    console.log(e?.response?.data?.message, ' error message');
    console.log(e?.response?.data?.code, ' error code');
    console.log(e?.code, ' error code');
    console.log(e?.message, ' error message');
  }
};

export const updateIntegration = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string,
  enabled?: boolean,
  token?: string,
  refreshToken?: string,
  expiresAt?: string,
  syncEnabled?: boolean,
  colors?: colorType[],
  pageToken?: string,
  syncToken?: string,
  clientType?: 'ios' | 'android' | 'web' | 'atomic-web'
) => {
  try {
    const updateCalendarIntegration = gql`
      mutation UpdateCalendarIntegrationById($id: uuid!, 
        ${enabled !== undefined ? '$enabled: Boolean,' : ''} 
        ${expiresAt !== undefined ? '$expiresAt: timestamptz,' : ''} 
        ${refreshToken !== undefined ? '$refreshToken: String,' : ''} 
        ${token !== undefined ? '$token: String,' : ''}
        ${syncEnabled !== undefined ? '$syncEnabled: Boolean,' : ''}
        ${colors !== undefined ? '$colors: jsonb,' : ''}
        ${pageToken !== undefined ? '$pageToken: String,' : ''}
        ${syncToken !== undefined ? '$syncToken: String,' : ''}
        ${clientType !== undefined ? '$clientType: String,' : ''}
        $updatedAt: timestamptz) {
          update_Calendar_Integration_by_pk(_set: {
            ${enabled !== undefined ? 'enabled: $enabled,' : ''} 
            ${expiresAt !== undefined ? 'expiresAt: $expiresAt,' : ''} 
            ${refreshToken !== undefined ? 'refreshToken: $refreshToken,' : ''} 
            ${token !== undefined ? 'token: $token,' : ''}
            ${syncEnabled !== undefined ? 'syncEnabled: $syncEnabled,' : ''}
            ${colors !== undefined ? 'colors: $colors,' : ''}
            ${pageToken !== undefined ? 'pageToken: $pageToken,' : ''}
            ${syncToken !== undefined ? 'syncToken: $syncToken,' : ''}
            ${clientType !== undefined ? 'clientType: $clientType,' : ''}
            updatedAt: $updatedAt}, pk_columns: {id: $id}) {
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
          }
      }
    `;
    let variables: any = {
      id,
      updatedAt: dayjs().format(),
    };

    if (enabled !== undefined) {
      variables.enabled = enabled;
    }

    if (expiresAt !== undefined) {
      if (expiresAt === null) {
        variables.expiresAt = null;
      } else {
        variables.expiresAt = dayjs(expiresAt).format();
      }
    }

    if (refreshToken !== undefined) {
      variables.refreshToken = refreshToken;
    }

    if (token !== undefined) {
      variables.token = token;
    }

    if (syncEnabled !== undefined) {
      variables.syncEnabled = syncEnabled;
    }

    if (colors !== undefined) {
      variables.colors = colors;
    }

    if (pageToken !== undefined) {
      variables.pageToken = pageToken;
    }

    if (syncToken !== undefined) {
      variables.syncToken = syncToken;
    }

    if (clientType !== undefined) {
      variables.clientType = clientType;
    }

    const results = (
      await client.mutate<{
        update_Calendar_Integration_by_pk: CalendarIntegrationType;
      }>({
        mutation: updateCalendarIntegration,
        variables,
      })
    ).data.update_Calendar_Integration_by_pk;

    return results;
  } catch (e) {
    console.log(e, ' unable to update integration');
  }
};

export const getIntegrationById = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string
) => {
  try {
    const results = (
      await client.query<{
        Calendar_Integration_by_pk: CalendarIntegrationType;
      }>({
        query: getCalendarIntegrationById,
        variables: {
          id,
        },
      })
    ).data.Calendar_Integration_by_pk;

    return results;
  } catch (e) {
    console.log(e, ' unable to get integration');
  }
};

export const createInitialCalendarIntegrations = async (
  client: ApolloClient<NormalizedCacheObject>,
  sub: string
) => {
  try {
    const results = (
      await client.query<{
        Calendar_Integration: CalendarIntegrationType[];
      }>({
        query: listCalendarIntegrations,
        variables: { userId: sub },
      })
    ).data.Calendar_Integration;
    console.log(results, ' results inside createInitialCalendarIntegrations');
    if (!(results?.length > 0) || !results) {
      const calendar_integrations = INTEGRATIONS.map((i) => ({
        ...i,
        userId: sub,
      }));
      const { data } = await client.mutate<{
        insert_Calendar_Integration: { returning: CalendarIntegrationType[] };
      }>({
        mutation: upsertCalendarIntegrations,
        variables: { calendar_integrations },
      });
      console.log(
        data?.insert_Calendar_Integration?.returning,
        ' created initial calendar integrations'
      );
    }
  } catch (e) {
    console.log(e, ' unable to createIntialIntegration');
  }
};
