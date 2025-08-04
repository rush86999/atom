import { dayjs } from '@lib/date-utils';
// Unused import: hasuraApiUrl
// import {
//   hasuraApiUrl,
// } from '@lib/constants';
import { CalendarIntegrationType } from '@lib/dataTypes/Calendar_IntegrationType';
import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client';
import appServiceLogger from './logger'; // Import the shared logger

// dayjs.extend(utc)

export const updateCalendarIntegration = async (
  client: ApolloClient<NormalizedCacheObject>,
  calIntegId: string,
  enabled?: boolean,
  token?: string,
  refreshToken?: string,
  expiresAt?: string,
  clientType?: 'ios' | 'android' | 'web' | 'atomic-web'
) => {
  try {
    const updateCalendarIntegration = gql`
      mutation UpdateCalendarIntegrationById($id: uuid!, ${enabled !== undefined ? '$enabled: Boolean,' : ''} ${expiresAt ? '$expiresAt: timestamptz,' : ''} ${refreshToken ? '$refreshToken: String,' : ''} ${token ? '$token: String,' : ''} $updatedAt: timestamptz) {
        update_Calendar_Integration_by_pk(_set: {${enabled !== undefined ? 'enabled: $enabled,' : ''} ${expiresAt ? 'expiresAt: $expiresAt,' : ''} ${refreshToken ? 'refreshToken: $refreshToken,' : ''} ${token ? 'token: $token,' : ''} updatedAt: $updatedAt}, pk_columns: {id: $id}) {
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
      id: calIntegId,
      updatedAt: dayjs().toISOString(),
    };

    if (enabled !== undefined) {
      variables.enabled = enabled;
    }

    if (expiresAt) {
      variables.expiresAt = dayjs(expiresAt).toISOString();
    }

    if (refreshToken) {
      variables.refreshToken = refreshToken;
    }

    if (token) {
      variables.token = token;
    }

    if (clientType) {
      variables.clientType = clientType;
    }

    const results = (
      await client.mutate<{
        update_Calendar_Integration_by_pk: CalendarIntegrationType;
      }>({
        mutation: updateCalendarIntegration,
        variables,
      })
    )?.data?.update_Calendar_Integration_by_pk;

    return results;
  } catch (e: any) {
    // Added type annotation for e
    appServiceLogger.error({
      message: 'Unable to update calendar_integration in api-helper',
      calIntegId,
      error: e.message,
      stack: e.stack,
      details: e,
    });
    // Decide if to rethrow or return undefined/specific error structure
    // Original code implicitly returned undefined. Maintaining that for now.
  }
};

/**
end
 */
