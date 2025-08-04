"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createInitialCalendarIntegrations = exports.getIntegrationById = exports.updateIntegration = exports.triggerGooglePeopleSync = exports.triggerGoogleCalendarSync = exports.listGoogleCalendars = exports.deleteEventTriggers = exports.deleteEventTriggerByResourceId = exports.deleteEventTriggerById = void 0;
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
const axios_1 = __importDefault(require("axios"));
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
const qs_1 = __importDefault(require("qs"));
const attempt_1 = require("@lifeomic/attempt");
const constants_1 = require("@lib/constants");
const constants_2 = require("@lib/calendarLib/constants");
const constants_3 = require("@lib/contactLib/constants");
const constants_4 = require("@lib/zoom/constants");
const client_1 = require("@apollo/client");
const getCalendarIntegrationById_1 = __importDefault(require("@lib/apollo/gql/getCalendarIntegrationById"));
const upsertCalendarIntegrations_1 = __importDefault(require("@lib/apollo/gql/upsertCalendarIntegrations"));
const listCalendarIntegrations_1 = __importDefault(require("@lib/apollo/gql/listCalendarIntegrations"));
const INTEGRATIONS = [
    {
        id: (0, uuid_1.v4)(),
        resource: constants_2.googleResourceName,
        name: constants_2.googleCalendarName,
        enabled: false,
        syncEnabled: false,
        updatedAt: (0, date_utils_1.dayjs)().format(),
        createdDate: (0, date_utils_1.dayjs)().format(),
        deleted: false,
        clientType: 'atomic-web',
    },
    {
        id: (0, uuid_1.v4)(),
        resource: constants_4.zoomResourceName,
        name: constants_4.zoomName,
        enabled: false,
        syncEnabled: false,
        updatedAt: (0, date_utils_1.dayjs)().format(),
        createdDate: (0, date_utils_1.dayjs)().toISOString(),
        deleted: false,
        clientType: 'web',
    },
    {
        id: (0, uuid_1.v4)(),
        resource: constants_3.googlePeopleResource,
        name: constants_3.googlePeopleName,
        enabled: false,
        syncEnabled: false,
        updatedAt: (0, date_utils_1.dayjs)().format(),
        createdDate: (0, date_utils_1.dayjs)().toISOString(),
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
const deleteEventTriggerById = async (id) => {
    try {
        const token = await session_1.default.getAccessToken();
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
        const response = await axios_1.default.post(constants_1.hasuraApiUrl, data, config);
        console.log(response?.data, ' deleteEventTriggerById');
    }
    catch (e) {
        console.log(e, ' deleteEventTriggerById');
    }
};
exports.deleteEventTriggerById = deleteEventTriggerById;
const deleteEventTriggerByResourceId = async (resourceId) => {
    try {
        const token = await session_1.default.getAccessToken();
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
        const response = await axios_1.default.post(constants_1.hasuraApiUrl, data, config);
        console.log(response?.data, ' deleteEventTriggerByResourceId');
    }
    catch (e) {
        console.log(e, ' deleteEventTriggerByResourceId');
    }
};
exports.deleteEventTriggerByResourceId = deleteEventTriggerByResourceId;
const deleteEventTriggers = async (userId, resource, name) => {
    try {
        const token = await session_1.default.getAccessToken();
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
        const results = await axios_1.default.post(constants_1.hasuraApiUrl, data, config);
        console.log(results, ' able to successfully delete event triggers');
    }
    catch (e) {
        console.log(e, ' unable to call deleteEventTriggers');
    }
};
exports.deleteEventTriggers = deleteEventTriggers;
const listGoogleCalendars = async (googleToken) => {
    try {
        let url = constants_2.googleCalendarURL;
        const config = {
            headers: {
                Authorization: `Bearer ${googleToken}`,
                'Content-Type': 'application/json',
                Accept: 'application/json',
            },
        };
        let isMore = true;
        const calendarList = [];
        while (isMore) {
            const results = await (0, attempt_1.retry)(async () => axios_1.default.get(url, config), {
                delay: 200,
                factor: 2,
                maxAttempts: 5,
                maxDelay: 500,
            });
            const items = results?.data?.items;
            calendarList.push(...items);
            console.log(items, ' items');
            // reset url
            url = constants_2.googleCalendarURL;
            if (results?.data?.nextPageToken) {
                let params = {};
                if (results?.data?.nextPageToken) {
                    params.pageToken = results?.data?.nextPageToken;
                }
                url = `${url}?${qs_1.default.stringify(params)}`;
            }
            else {
                isMore = false;
            }
        }
        return calendarList;
    }
    catch (e) {
        console.log(e, ' unable to list google calendars');
    }
};
exports.listGoogleCalendars = listGoogleCalendars;
const triggerGoogleCalendarSync = async (calendarIntegrationId, calendarId, userId) => {
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
        const token = await session_1.default.getAccessToken();
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
            timezone: date_utils_1.dayjs.tz.guess(),
        };
        const url = constants_2.googleCalendarSyncUrl;
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' successfully triggered google calendar sync');
    }
    catch (e) {
        console.log(e, ' unable to trigger google calendar sync');
    }
};
exports.triggerGoogleCalendarSync = triggerGoogleCalendarSync;
const triggerGooglePeopleSync = async (calendarIntegrationId, userId) => {
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
        const token = await session_1.default.getAccessToken();
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
        const url = constants_3.googlePeopleSyncUrl;
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' successfully triggered google people sync');
    }
    catch (e) {
        console.log(e, ' unable to trigger google people sync');
        console.log(e?.response?.data?.message, ' error message');
        console.log(e?.response?.data?.code, ' error code');
        console.log(e?.code, ' error code');
        console.log(e?.message, ' error message');
    }
};
exports.triggerGooglePeopleSync = triggerGooglePeopleSync;
const updateIntegration = async (client, id, enabled, token, refreshToken, expiresAt, syncEnabled, colors, pageToken, syncToken, clientType) => {
    try {
        const updateCalendarIntegration = (0, client_1.gql) `
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
        let variables = {
            id,
            updatedAt: (0, date_utils_1.dayjs)().format(),
        };
        if (enabled !== undefined) {
            variables.enabled = enabled;
        }
        if (expiresAt !== undefined) {
            if (expiresAt === null) {
                variables.expiresAt = null;
            }
            else {
                variables.expiresAt = (0, date_utils_1.dayjs)(expiresAt).format();
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
        const results = (await client.mutate({
            mutation: updateCalendarIntegration,
            variables,
        })).data.update_Calendar_Integration_by_pk;
        return results;
    }
    catch (e) {
        console.log(e, ' unable to update integration');
    }
};
exports.updateIntegration = updateIntegration;
const getIntegrationById = async (client, id) => {
    try {
        const results = (await client.query({
            query: getCalendarIntegrationById_1.default,
            variables: {
                id,
            },
        })).data.Calendar_Integration_by_pk;
        return results;
    }
    catch (e) {
        console.log(e, ' unable to get integration');
    }
};
exports.getIntegrationById = getIntegrationById;
const createInitialCalendarIntegrations = async (client, sub) => {
    try {
        const results = (await client.query({
            query: listCalendarIntegrations_1.default,
            variables: { userId: sub },
        })).data.Calendar_Integration;
        console.log(results, ' results inside createInitialCalendarIntegrations');
        if (!(results?.length > 0) || !results) {
            const calendar_integrations = INTEGRATIONS.map((i) => ({
                ...i,
                userId: sub,
            }));
            const { data } = await client.mutate({
                mutation: upsertCalendarIntegrations_1.default,
                variables: { calendar_integrations },
            });
            console.log(data?.insert_Calendar_Integration?.returning, ' created initial calendar integrations');
        }
    }
    catch (e) {
        console.log(e, ' unable to createIntialIntegration');
    }
};
exports.createInitialCalendarIntegrations = createInitialCalendarIntegrations;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsZW5kYXJfaW50ZWdyYXRpb25IZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxlbmRhcl9pbnRlZ3JhdGlvbkhlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSwrQkFBa0M7QUFDbEMsZ0RBQXdDO0FBQ3hDLGtEQUEwQjtBQUMxQixnRkFBd0Q7QUFDeEQsNENBQW9CO0FBQ3BCLCtDQUEwQztBQU0xQyw4Q0FBOEM7QUFFOUMsMERBT29DO0FBRXBDLHlEQU1tQztBQUVuQyxtREFBaUU7QUFXakUsMkNBQTBFO0FBQzFFLDRHQUFvRjtBQUNwRiw0R0FBb0Y7QUFDcEYsd0dBQWdGO0FBRWhGLE1BQU0sWUFBWSxHQUFHO0lBQ25CO1FBQ0UsRUFBRSxFQUFFLElBQUEsU0FBSSxHQUFFO1FBQ1YsUUFBUSxFQUFFLDhCQUFrQjtRQUM1QixJQUFJLEVBQUUsOEJBQWtCO1FBQ3hCLE9BQU8sRUFBRSxLQUFLO1FBQ2QsV0FBVyxFQUFFLEtBQUs7UUFDbEIsU0FBUyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLE1BQU0sRUFBRTtRQUMzQixXQUFXLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsTUFBTSxFQUFFO1FBQzdCLE9BQU8sRUFBRSxLQUFLO1FBQ2QsVUFBVSxFQUFFLFlBQVk7S0FDekI7SUFDRDtRQUNFLEVBQUUsRUFBRSxJQUFBLFNBQUksR0FBRTtRQUNWLFFBQVEsRUFBRSw0QkFBZ0I7UUFDMUIsSUFBSSxFQUFFLG9CQUFRO1FBQ2QsT0FBTyxFQUFFLEtBQUs7UUFDZCxXQUFXLEVBQUUsS0FBSztRQUNsQixTQUFTLEVBQUUsSUFBQSxrQkFBSyxHQUFFLENBQUMsTUFBTSxFQUFFO1FBQzNCLFdBQVcsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUU7UUFDbEMsT0FBTyxFQUFFLEtBQUs7UUFDZCxVQUFVLEVBQUUsS0FBSztLQUNsQjtJQUNEO1FBQ0UsRUFBRSxFQUFFLElBQUEsU0FBSSxHQUFF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SyxFQUFFLGtDQUF3QjtZQUMvQixTQUFTLEVBQUUsRUFBRSxNQUFNLEVBQUUsR0FBRyxFQUFFO1NBQzNCLENBQUMsQ0FDSCxDQUFDLElBQUksQ0FBQyxvQkFBb0IsQ0FBQztRQUM1QixPQUFPLENBQUMsR0FBRyxDQUFDLE9BQU8sRUFBRSxtREFBbUQsQ0FBQyxDQUFDO1FBQzFFLElBQUksQ0FBQyxDQUFDLE9BQU8sRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUN2QyxNQUFNLHFCQUFxQixHQUFHLFlBQVksQ0FBQyxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7Z0JBQ3JELEdBQUcsQ0FBQztnQkFDSixNQUFNLEVBQUUsR0FBRzthQUNaLENBQUMsQ0FBQyxDQUFDO1lBQ0osTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FFakM7Z0JBQ0QsUUFBUSxFQUFFLG9DQUEwQjtnQkFDcEMsU0FBUyxFQUFFLEVBQUUscUJBQXFCLEVBQUU7YUFDckMsQ0FBQyxDQUFDO1lBQ0gsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLEVBQUUsMkJBQTJCLEVBQUUsU0FBUyxFQUM1Qyx3Q0FBd0MsQ0FDekMsQ0FBQztRQUNKLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLG9DQUFvQyxDQUFDLENBQUM7SUFDdkQsQ0FBQztBQUNILENBQUMsQ0FBQztBQWpDVyxRQUFBLGlDQUFpQyxxQ0FpQzVDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdjQgYXMgdXVpZCB9IGZyb20gJ3V1aWQnO1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAbGliL2RhdGUtdXRpbHMnO1xuaW1wb3J0IGF4aW9zIGZyb20gJ2F4aW9zJztcbmltcG9ydCBTZXNzaW9uIGZyb20gJ3N1cGVydG9rZW5zLXdlYi1qcy9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQgcXMgZnJvbSAncXMnO1xuaW1wb3J0IHsgcmV0cnkgfSBmcm9tICdAbGlmZW9taWMvYXR0ZW1wdCc7XG5cbi8vIGRheWpzLmV4dGVuZCh1dGMpXG4vLyBkYXlqcy5leHRlbmQodGltZXpvbmUpXG5cbmltcG9ydCB7IENvbmZpZ1R5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9Db25maWdUeXBlJztcbmltcG9ydCB7IGhhc3VyYUFwaVVybCB9IGZyb20gJ0BsaWIvY29uc3RhbnRzJztcblxuaW1wb3J0IHtcbiAgZ29vZ2xlQ2FsZW5kYXJTeW5jVXJsLFxuICBnb29nbGVDYWxlbmRhclVSTCxcbiAgZ29vZ2xlQ2FsZW5kYXJOYW1lLFxuICBnb29nbGVSZXNvdXJjZU5hbWUsXG4gIGxvY2FsQ2FsZW5kYXJOYW1lLFxuICBsb2NhbENhbGVuZGFyUmVzb3VyY2UsXG59IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvY29uc3RhbnRzJztcblxuaW1wb3J0IHtcbiAgZ29vZ2xlUGVvcGxlU3luY1VybCxcbiAgZ29vZ2xlUGVvcGxlTmFtZSxcbiAgZ29vZ2xlUGVvcGxlUmVzb3VyY2UsXG4gIGxvY2FsQ29udGFjdHNOYW1lLFxuICBsb2NhbENvbnRhY3RzUmVzb3VyY2UsXG59IGZyb20gJ0BsaWIvY29udGFjdExpYi9jb25zdGFudHMnO1xuXG5pbXBvcnQgeyB6b29tTmFtZSwgem9vbVJlc291cmNlTmFtZSB9IGZyb20gJ0BsaWIvem9vbS9jb25zdGFudHMnO1xuXG5pbXBvcnQge1xuICBDYWxlbmRhckxpc3RSZXNwb25zZVR5cGUsXG4gIENhbGVuZGFyTGlzdEl0ZW1SZXNwb25zZVR5cGUsXG59IGZyb20gJ0BsaWIvY2FsZW5kYXJMaWIvdHlwZXMnO1xuXG5pbXBvcnQge1xuICBDYWxlbmRhckludGVncmF0aW9uVHlwZSxcbiAgY29sb3JUeXBlLFxufSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYWxlbmRhcl9JbnRlZ3JhdGlvblR5cGUnO1xuaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBncWwsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5SWQnO1xuaW1wb3J0IHVwc2VydENhbGVuZGFySW50ZWdyYXRpb25zIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC91cHNlcnRDYWxlbmRhckludGVncmF0aW9ucyc7XG5pbXBvcnQgbGlzdENhbGVuZGFySW50ZWdyYXRpb25zIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0Q2FsZW5kYXJJbnRlZ3JhdGlvbnMnO1xuXG5jb25zdCBJTlRFR1JBVElPTlMgPSBbXG4gIHtcbiAgICBpZDogdXVpZCgpLFxuICAgIHJlc291cmNlOiBnb29nbGVSZXNvdXJjZU5hbWUsXG4gICAgbmFtZTogZ29vZ2xlQ2FsZW5kYXJOYW1lLFxuICAgIGVuYWJsZWQ6IGZhbHNlLFxuICAgIHN5bmNFbmFibGVkOiBmYWxzZSxcbiAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgY2xpZW50VHlwZTogJ2F0b21pYy13ZWInLFxuICB9LFxuICB7XG4gICAgaWQ6IHV1aWQoKSxcbiAgICByZXNvdXJjZTogem9vbVJlc291cmNlTmFtZSxcbiAgICBuYW1lOiB6b29tTmFtZSxcbiAgICBlbmFibGVkOiBmYWxzZSxcbiAgICBzeW5jRW5hYmxlZDogZmFsc2UsXG4gICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgZGVsZXRlZDogZmFsc2UsXG4gICAgY2xpZW50VHlwZTogJ3dlYicsXG4gIH0sXG4gIHtcbiAgICBpZDogdXVpZCgpLFxuICAgIHJlc291cmNlOiBnb29nbGVQZW9wbGVSZXNvdXJjZSxcbiAgICBuYW1lOiBnb29nbGVQZW9wbGVOYW1lLFxuICAgIGVuYWJsZWQ6IGZhbHNlLFxuICAgIHN5bmNFbmFibGVkOiBmYWxzZSxcbiAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgY3JlYXRlZERhdGU6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICBkZWxldGVkOiBmYWxzZSxcbiAgICBjbGllbnRUeXBlOiAnYXRvbWljLXdlYicsXG4gIH0sXG4gIC8vIHtcbiAgLy8gICBpZDogdXVpZCgpLFxuICAvLyAgIHJlc291cmNlOiBsb2NhbENvbnRhY3RzUmVzb3VyY2UsXG4gIC8vICAgbmFtZTogbG9jYWxDb250YWN0c05hbWUsXG4gIC8vICAgZW5hYmxlZDogZmFsc2UsXG4gIC8vICAgc3luY0VuYWJsZWQ6IGZhbHNlLFxuICAvLyAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgLy8gICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAvLyAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAvLyAgIGNsaWVudFR5cGU6ICdhdG9taWMtd2ViJyxcbiAgLy8gfSxcbiAgLy8ge1xuICAvLyAgIGlkOiB1dWlkKCksXG4gIC8vICAgcmVzb3VyY2U6IGxvY2FsQ2FsZW5kYXJSZXNvdXJjZSxcbiAgLy8gICBuYW1lOiBsb2NhbENhbGVuZGFyTmFtZSxcbiAgLy8gICBlbmFibGVkOiBmYWxzZSxcbiAgLy8gICBzeW5jRW5hYmxlZDogZmFsc2UsXG4gIC8vICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAvLyAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gIC8vICAgZGVsZXRlZDogZmFsc2UsXG4gIC8vICAgY2xpZW50VHlwZTogJ2F0b21pYy13ZWInLFxuICAvLyB9LFxuXTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUV2ZW50VHJpZ2dlckJ5SWQgPSBhc3luYyAoaWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRva2VuID0gYXdhaXQgU2Vzc2lvbi5nZXRBY2Nlc3NUb2tlbigpO1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZGVsZXRlRXZlbnRUcmlnZ2VyQnlJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBtdXRhdGlvbiBkZWxldGVFdmVudFRyaWdnZXJCeUlkKCRpZDogdXVpZCEpIHtcbiAgICAgICAgZGVsZXRlX0V2ZW50X1RyaWdnZXJfYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgICAgIGlkXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHsgaWQgfTtcbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgY29uc3QgZGF0YSA9IHtcbiAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICBxdWVyeSxcbiAgICAgIHZhcmlhYmxlcyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBheGlvcy5wb3N0KGhhc3VyYUFwaVVybCwgZGF0YSwgY29uZmlnKTtcbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZT8uZGF0YSwgJyBkZWxldGVFdmVudFRyaWdnZXJCeUlkJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGRlbGV0ZUV2ZW50VHJpZ2dlckJ5SWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZCA9IGFzeW5jIChyZXNvdXJjZUlkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2RlbGV0ZUV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBtdXRhdGlvbiBkZWxldGVFdmVudFRyaWdnZXJCeVJlc291cmNlSWQoJHJlc291cmNlSWQ6IFN0cmluZyEpIHtcbiAgICAgICAgZGVsZXRlX0V2ZW50X1RyaWdnZXIod2hlcmU6IHtyZXNvdXJjZUlkOiB7X2VxOiAkcmVzb3VyY2VJZH19KSB7XG4gICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7IHJlc291cmNlSWQgfTtcbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgfSxcbiAgICB9O1xuICAgIGNvbnN0IGRhdGEgPSB7XG4gICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgcXVlcnksXG4gICAgICB2YXJpYWJsZXMsXG4gICAgfTtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QoaGFzdXJhQXBpVXJsLCBkYXRhLCBjb25maWcpO1xuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlPy5kYXRhLCAnIGRlbGV0ZUV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZCcpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBkZWxldGVFdmVudFRyaWdnZXJCeVJlc291cmNlSWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZUV2ZW50VHJpZ2dlcnMgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICByZXNvdXJjZTogc3RyaW5nLFxuICBuYW1lOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRva2VuID0gYXdhaXQgU2Vzc2lvbi5nZXRBY2Nlc3NUb2tlbigpO1xuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2RlbGV0ZUV2ZW50VHJpZ2dlcnMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgbXV0YXRpb24gZGVsZXRlRXZlbnRUcmlnZ2VycygkdXNlcklkOiB1dWlkISwgJHJlc291cmNlOiBTdHJpbmchLCAkbmFtZTogU3RyaW5nISkge1xuICAgICAgICBkZWxldGVfRXZlbnRfVHJpZ2dlcih3aGVyZToge3VzZXJJZDoge19lcTogJHVzZXJJZH0sIHJlc291cmNlOiB7X2VxOiAkcmVzb3VyY2V9LCBuYW1lOiB7X2VxOiAkbmFtZX19KSB7XG4gICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHJlc291cmNlLFxuICAgICAgbmFtZSxcbiAgICB9O1xuXG4gICAgY29uc3QgZGF0YSA9IHtcbiAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICBxdWVyeSxcbiAgICAgIHZhcmlhYmxlcyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGF4aW9zLnBvc3QoaGFzdXJhQXBpVXJsLCBkYXRhLCBjb25maWcpO1xuXG4gICAgY29uc29sZS5sb2cocmVzdWx0cywgJyBhYmxlIHRvIHN1Y2Nlc3NmdWxseSBkZWxldGUgZXZlbnQgdHJpZ2dlcnMnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNhbGwgZGVsZXRlRXZlbnRUcmlnZ2VycycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdEdvb2dsZUNhbGVuZGFycyA9IGFzeW5jIChnb29nbGVUb2tlbjogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IHVybCA9IGdvb2dsZUNhbGVuZGFyVVJMO1xuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke2dvb2dsZVRva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIEFjY2VwdDogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgbGV0IGlzTW9yZSA9IHRydWU7XG5cbiAgICBjb25zdCBjYWxlbmRhckxpc3Q6IENhbGVuZGFyTGlzdEl0ZW1SZXNwb25zZVR5cGVbXSA9IFtdO1xuXG4gICAgd2hpbGUgKGlzTW9yZSkge1xuICAgICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IHJldHJ5KFxuICAgICAgICBhc3luYyAoKSA9PiBheGlvcy5nZXQ8Q2FsZW5kYXJMaXN0UmVzcG9uc2VUeXBlPih1cmwsIGNvbmZpZyksXG4gICAgICAgIHtcbiAgICAgICAgICBkZWxheTogMjAwLFxuICAgICAgICAgIGZhY3RvcjogMixcbiAgICAgICAgICBtYXhBdHRlbXB0czogNSxcbiAgICAgICAgICBtYXhEZWxheTogNTAwLFxuICAgICAgICB9XG4gICAgICApO1xuXG4gICAgICBjb25zdCBpdGVtcyA9IHJlc3VsdHM/LmRhdGE/Lml0ZW1zO1xuICAgICAgY2FsZW5kYXJMaXN0LnB1c2goLi4uaXRlbXMpO1xuICAgICAgY29uc29sZS5sb2coaXRlbXMsICcgaXRlbXMnKTtcbiAgICAgIC8vIHJlc2V0IHVybFxuICAgICAgdXJsID0gZ29vZ2xlQ2FsZW5kYXJVUkw7XG4gICAgICBpZiAocmVzdWx0cz8uZGF0YT8ubmV4dFBhZ2VUb2tlbikge1xuICAgICAgICBsZXQgcGFyYW1zOiBhbnkgPSB7fTtcbiAgICAgICAgaWYgKHJlc3VsdHM/LmRhdGE/Lm5leHRQYWdlVG9rZW4pIHtcbiAgICAgICAgICBwYXJhbXMucGFnZVRva2VuID0gcmVzdWx0cz8uZGF0YT8ubmV4dFBhZ2VUb2tlbjtcbiAgICAgICAgfVxuICAgICAgICB1cmwgPSBgJHt1cmx9PyR7cXMuc3RyaW5naWZ5KHBhcmFtcyl9YDtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGlzTW9yZSA9IGZhbHNlO1xuICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiBjYWxlbmRhckxpc3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IGdvb2dsZSBjYWxlbmRhcnMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHRyaWdnZXJHb29nbGVDYWxlbmRhclN5bmMgPSBhc3luYyAoXG4gIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICBjYWxlbmRhcklkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIWNhbGVuZGFySW50ZWdyYXRpb25JZCkge1xuICAgICAgY29uc29sZS5sb2coJyBubyBjYWxlbmRhcklOdGVncmF0aW9uaWQnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBpZiAoIWNhbGVuZGFySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyBjYWxlbmRhcklkJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyB1c2VySWQnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBTZXNzaW9uLmdldEFjY2Vzc1Rva2VuKCk7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgY29uc3QgZGF0YSA9IHtcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgIGNhbGVuZGFySWQsXG4gICAgICB1c2VySWQsXG4gICAgICBpc0luaXRpYWxTeW5jOiB0cnVlLFxuICAgICAgdGltZXpvbmU6IGRheWpzLnR6Lmd1ZXNzKCksXG4gICAgfTtcblxuICAgIGNvbnN0IHVybCA9IGdvb2dsZUNhbGVuZGFyU3luY1VybDtcblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBheGlvcy5wb3N0KHVybCwgZGF0YSwgY29uZmlnKTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgc3VjY2Vzc2Z1bGx5IHRyaWdnZXJlZCBnb29nbGUgY2FsZW5kYXIgc3luYycpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdHJpZ2dlciBnb29nbGUgY2FsZW5kYXIgc3luYycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdHJpZ2dlckdvb2dsZVBlb3BsZVN5bmMgPSBhc3luYyAoXG4gIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coJ3RyaWdnZXJHb29nbGVQZW9wbGVTeW4gY2FsbGVkJyk7XG4gICAgaWYgKCFjYWxlbmRhckludGVncmF0aW9uSWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgbm8gY2FsZW5kYXJJTnRlZ3JhdGlvbmlkJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyB1c2VySWQnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBTZXNzaW9uLmdldEFjY2Vzc1Rva2VuKCk7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgY29uc3QgZGF0YSA9IHtcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIGlzSW5pdGlhbFN5bmM6IHRydWUsXG4gICAgfTtcblxuICAgIGNvbnN0IHVybCA9IGdvb2dsZVBlb3BsZVN5bmNVcmw7XG5cbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgYXhpb3MucG9zdCh1cmwsIGRhdGEsIGNvbmZpZyk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXN1bHRzLCAnIHN1Y2Nlc3NmdWxseSB0cmlnZ2VyZWQgZ29vZ2xlIHBlb3BsZSBzeW5jJyk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHRyaWdnZXIgZ29vZ2xlIHBlb3BsZSBzeW5jJyk7XG4gICAgY29uc29sZS5sb2coZT8ucmVzcG9uc2U/LmRhdGE/Lm1lc3NhZ2UsICcgZXJyb3IgbWVzc2FnZScpO1xuICAgIGNvbnNvbGUubG9nKGU/LnJlc3BvbnNlPy5kYXRhPy5jb2RlLCAnIGVycm9yIGNvZGUnKTtcbiAgICBjb25zb2xlLmxvZyhlPy5jb2RlLCAnIGVycm9yIGNvZGUnKTtcbiAgICBjb25zb2xlLmxvZyhlPy5tZXNzYWdlLCAnIGVycm9yIG1lc3NhZ2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUludGVncmF0aW9uID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBpZDogc3RyaW5nLFxuICBlbmFibGVkPzogYm9vbGVhbixcbiAgdG9rZW4/OiBzdHJpbmcsXG4gIHJlZnJlc2hUb2tlbj86IHN0cmluZyxcbiAgZXhwaXJlc0F0Pzogc3RyaW5nLFxuICBzeW5jRW5hYmxlZD86IGJvb2xlYW4sXG4gIGNvbG9ycz86IGNvbG9yVHlwZVtdLFxuICBwYWdlVG9rZW4/OiBzdHJpbmcsXG4gIHN5bmNUb2tlbj86IHN0cmluZyxcbiAgY2xpZW50VHlwZT86ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYidcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24gPSBncWxgXG4gICAgICBtdXRhdGlvbiBVcGRhdGVDYWxlbmRhckludGVncmF0aW9uQnlJZCgkaWQ6IHV1aWQhLCBcbiAgICAgICAgJHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnJGVuYWJsZWQ6IEJvb2xlYW4sJyA6ICcnfSBcbiAgICAgICAgJHtleHBpcmVzQXQgIT09IHVuZGVmaW5lZCA/ICckZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiwnIDogJyd9IFxuICAgICAgICAke3JlZnJlc2hUb2tlbiAhPT0gdW5kZWZpbmVkID8gJyRyZWZyZXNoVG9rZW46IFN0cmluZywnIDogJyd9IFxuICAgICAgICAke3Rva2VuICE9PSB1bmRlZmluZWQgPyAnJHRva2VuOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAke3N5bmNFbmFibGVkICE9PSB1bmRlZmluZWQgPyAnJHN5bmNFbmFibGVkOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgJHtjb2xvcnMgIT09IHVuZGVmaW5lZCA/ICckY29sb3JzOiBqc29uYiwnIDogJyd9XG4gICAgICAgICR7cGFnZVRva2VuICE9PSB1bmRlZmluZWQgPyAnJHBhZ2VUb2tlbjogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgJHtzeW5jVG9rZW4gIT09IHVuZGVmaW5lZCA/ICckc3luY1Rva2VuOiBTdHJpbmcsJyA6ICcnfVxuICAgICAgICAke2NsaWVudFR5cGUgIT09IHVuZGVmaW5lZCA/ICckY2xpZW50VHlwZTogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgJHVwZGF0ZWRBdDogdGltZXN0YW1wdHopIHtcbiAgICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsoX3NldDoge1xuICAgICAgICAgICAgJHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnZW5hYmxlZDogJGVuYWJsZWQsJyA6ICcnfSBcbiAgICAgICAgICAgICR7ZXhwaXJlc0F0ICE9PSB1bmRlZmluZWQgPyAnZXhwaXJlc0F0OiAkZXhwaXJlc0F0LCcgOiAnJ30gXG4gICAgICAgICAgICAke3JlZnJlc2hUb2tlbiAhPT0gdW5kZWZpbmVkID8gJ3JlZnJlc2hUb2tlbjogJHJlZnJlc2hUb2tlbiwnIDogJyd9IFxuICAgICAgICAgICAgJHt0b2tlbiAhPT0gdW5kZWZpbmVkID8gJ3Rva2VuOiAkdG9rZW4sJyA6ICcnfVxuICAgICAgICAgICAgJHtzeW5jRW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJ3N5bmNFbmFibGVkOiAkc3luY0VuYWJsZWQsJyA6ICcnfVxuICAgICAgICAgICAgJHtjb2xvcnMgIT09IHVuZGVmaW5lZCA/ICdjb2xvcnM6ICRjb2xvcnMsJyA6ICcnfVxuICAgICAgICAgICAgJHtwYWdlVG9rZW4gIT09IHVuZGVmaW5lZCA/ICdwYWdlVG9rZW46ICRwYWdlVG9rZW4sJyA6ICcnfVxuICAgICAgICAgICAgJHtzeW5jVG9rZW4gIT09IHVuZGVmaW5lZCA/ICdzeW5jVG9rZW46ICRzeW5jVG9rZW4sJyA6ICcnfVxuICAgICAgICAgICAgJHtjbGllbnRUeXBlICE9PSB1bmRlZmluZWQgPyAnY2xpZW50VHlwZTogJGNsaWVudFR5cGUsJyA6ICcnfVxuICAgICAgICAgICAgdXBkYXRlZEF0OiAkdXBkYXRlZEF0fSwgcGtfY29sdW1uczoge2lkOiAkaWR9KSB7XG4gICAgICAgICAgICAgIGFwcEFjY291bnRJZFxuICAgICAgICAgICAgICBhcHBFbWFpbFxuICAgICAgICAgICAgICBhcHBJZFxuICAgICAgICAgICAgICBjb2xvcnNcbiAgICAgICAgICAgICAgY29udGFjdEVtYWlsXG4gICAgICAgICAgICAgIGNvbnRhY3ROYW1lXG4gICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgZW5hYmxlZFxuICAgICAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgICAgICAgcGFzc3dvcmRcbiAgICAgICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgICAgIHRva2VuXG4gICAgICAgICAgICAgIHN5bmNUb2tlblxuICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgIHVzZXJuYW1lXG4gICAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgbGV0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgaWQsXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgfTtcblxuICAgIGlmIChlbmFibGVkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5lbmFibGVkID0gZW5hYmxlZDtcbiAgICB9XG5cbiAgICBpZiAoZXhwaXJlc0F0ICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIGlmIChleHBpcmVzQXQgPT09IG51bGwpIHtcbiAgICAgICAgdmFyaWFibGVzLmV4cGlyZXNBdCA9IG51bGw7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB2YXJpYWJsZXMuZXhwaXJlc0F0ID0gZGF5anMoZXhwaXJlc0F0KS5mb3JtYXQoKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAocmVmcmVzaFRva2VuICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5yZWZyZXNoVG9rZW4gPSByZWZyZXNoVG9rZW47XG4gICAgfVxuXG4gICAgaWYgKHRva2VuICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy50b2tlbiA9IHRva2VuO1xuICAgIH1cblxuICAgIGlmIChzeW5jRW5hYmxlZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuc3luY0VuYWJsZWQgPSBzeW5jRW5hYmxlZDtcbiAgICB9XG5cbiAgICBpZiAoY29sb3JzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5jb2xvcnMgPSBjb2xvcnM7XG4gICAgfVxuXG4gICAgaWYgKHBhZ2VUb2tlbiAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMucGFnZVRva2VuID0gcGFnZVRva2VuO1xuICAgIH1cblxuICAgIGlmIChzeW5jVG9rZW4gIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLnN5bmNUb2tlbiA9IHN5bmNUb2tlbjtcbiAgICB9XG5cbiAgICBpZiAoY2xpZW50VHlwZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuY2xpZW50VHlwZSA9IGNsaWVudFR5cGU7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzdWx0cyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGs6IENhbGVuZGFySW50ZWdyYXRpb25UeXBlO1xuICAgICAgfT4oe1xuICAgICAgICBtdXRhdGlvbjogdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbixcbiAgICAgICAgdmFyaWFibGVzLFxuICAgICAgfSlcbiAgICApLmRhdGEudXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrO1xuXG4gICAgcmV0dXJuIHJlc3VsdHM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgaW50ZWdyYXRpb24nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEludGVncmF0aW9uQnlJZCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgaWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzdWx0cyA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7XG4gICAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiBDYWxlbmRhckludGVncmF0aW9uVHlwZTtcbiAgICAgIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldENhbGVuZGFySW50ZWdyYXRpb25CeUlkLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICBpZCxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKS5kYXRhLkNhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrO1xuXG4gICAgcmV0dXJuIHJlc3VsdHM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgaW50ZWdyYXRpb24nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZUluaXRpYWxDYWxlbmRhckludGVncmF0aW9ucyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgc3ViOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHJlc3VsdHMgPSAoXG4gICAgICBhd2FpdCBjbGllbnQucXVlcnk8e1xuICAgICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbjogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGVbXTtcbiAgICAgIH0+KHtcbiAgICAgICAgcXVlcnk6IGxpc3RDYWxlbmRhckludGVncmF0aW9ucyxcbiAgICAgICAgdmFyaWFibGVzOiB7IHVzZXJJZDogc3ViIH0sXG4gICAgICB9KVxuICAgICkuZGF0YS5DYWxlbmRhcl9JbnRlZ3JhdGlvbjtcbiAgICBjb25zb2xlLmxvZyhyZXN1bHRzLCAnIHJlc3VsdHMgaW5zaWRlIGNyZWF0ZUluaXRpYWxDYWxlbmRhckludGVncmF0aW9ucycpO1xuICAgIGlmICghKHJlc3VsdHM/Lmxlbmd0aCA+IDApIHx8ICFyZXN1bHRzKSB7XG4gICAgICBjb25zdCBjYWxlbmRhcl9pbnRlZ3JhdGlvbnMgPSBJTlRFR1JBVElPTlMubWFwKChpKSA9PiAoe1xuICAgICAgICAuLi5pLFxuICAgICAgICB1c2VySWQ6IHN1YixcbiAgICAgIH0pKTtcbiAgICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICAgIGluc2VydF9DYWxlbmRhcl9JbnRlZ3JhdGlvbjogeyByZXR1cm5pbmc6IENhbGVuZGFySW50ZWdyYXRpb25UeXBlW10gfTtcbiAgICAgIH0+KHtcbiAgICAgICAgbXV0YXRpb246IHVwc2VydENhbGVuZGFySW50ZWdyYXRpb25zLFxuICAgICAgICB2YXJpYWJsZXM6IHsgY2FsZW5kYXJfaW50ZWdyYXRpb25zIH0sXG4gICAgICB9KTtcbiAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICBkYXRhPy5pbnNlcnRfQ2FsZW5kYXJfSW50ZWdyYXRpb24/LnJldHVybmluZyxcbiAgICAgICAgJyBjcmVhdGVkIGluaXRpYWwgY2FsZW5kYXIgaW50ZWdyYXRpb25zJ1xuICAgICAgKTtcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjcmVhdGVJbnRpYWxJbnRlZ3JhdGlvbicpO1xuICB9XG59O1xuIl19