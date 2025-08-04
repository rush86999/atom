import got from 'got';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import { google } from 'googleapis';
import { googlePeopleName, googlePeopleResource, hasuraGraphUrl, hasuraMetadataUrl, selfGooglePeopleAdminUrl, } from '@google_calendar_sync/_libs/constants';
import { deleteEventTriggerById, getEventTriggerByResourceId, getGoogleAPIToken, insertEventTriggers, } from '@google_calendar_sync/_libs/api-helper';
dayjs.extend(utc);
const adminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
// const hasuraGraphUrl = process.env.HASURA_GRAPH_URL
// const hasuraMetadataUrl = process.env.HASURA_METADATA_URL
// const selfGooglePeopleAdminUrl = process.env.SELF_GOOGLE_PEOPLE_ADMIN_UR
// const googlePeople = google.people('v1')
const deleteContacts = async (people) => {
    try {
        console.log(people, ' people inside deleteContacts');
        if (!(people?.[0]?.resourceName?.length > 0)) {
            console.log(' no people present to delete');
            return;
        }
        const ids = people?.map((p) => p?.resourceName.replace('people/', ''));
        if (!ids || !(ids?.length > 0)) {
            console.log(' no people present to delete');
            return;
        }
        const operationName = 'deleteContacts';
        const query = `
      mutation deleteContacts($ids: [String!]!) {
        delete_Contact(where: {id: {_in: $ids}}) {
          affected_rows
        }
      }
    `;
        const variables = {
            ids,
        };
        const response = await got
            .post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': adminSecret,
                'X-Hasura-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(response, ' this is response in deleteContacts');
    }
    catch (e) {
        console.log(e, ' unable to delete contacts');
    }
};
const upsertContacts2 = async (people, userId) => {
    try {
        console.log(people, ' people inside upsertContacts2');
        if (!(people?.[0]?.resourceName?.length > 0)) {
            console.log(' no people present to upsert');
            return;
        }
        const formattedPeople = people?.map((p) => ({
            id: p?.resourceName?.replace('people/', ''),
            name: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.displayName || p?.names?.[0]?.displayName,
            firstName: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.givenName || p?.names?.[0]?.givenName,
            middleName: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.middleName || p?.names?.[0]?.middleName,
            lastName: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.familyName || p?.names?.[0]?.familyName,
            namePrefix: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.honorificPrefix || p?.names?.[0]?.honorificPrefix,
            nameSuffix: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.honorificSuffix || p?.names?.[0]?.honorificSuffix,
            nickname: p?.nicknames?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.value || p?.nicknames?.[0]?.value,
            phoneticFirstName: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.phoneticGivenName || p?.names?.[0]?.phoneticGivenName,
            phoneticMiddleName: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.phoneticMiddleName || p?.names?.[0]?.phoneticMiddleName,
            phoneticLastName: p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.phoneticFamilyName || p?.names?.[0]?.phoneticFamilyName,
            company: p?.organizations?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.name || p?.organizations?.[0]?.name,
            jobTitle: p?.organizations?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.title || p?.organizations?.[0]?.title,
            department: p?.organizations?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.department || p?.organizations?.[0]?.department,
            notes: p?.biographies?.filter((n) => n?.metadata?.primary === true && n?.contentType === 'TEXT_HTML')?.[0]?.value || p?.biographies?.[0]?.value,
            imageAvailable: p?.coverPhotos?.filter((n) => n?.metadata?.primary === true)?.[0]?.url
                ?.length > 0,
            image: p?.coverPhotos?.filter((n) => n?.metadata?.primary === true)?.[0]
                ?.url || p?.coverPhotos?.[0]?.url,
            contactType: p?.metadata?.objectType,
            emails: p?.emailAddresses?.map((e) => ({
                primary: e?.metadata?.primary,
                value: e?.value,
                type: e?.type,
                displayName: e?.displayName,
            })),
            phoneNumbers: p?.phoneNumbers?.map((p) => ({
                primary: p?.metadata?.primary,
                value: p?.value,
                type: p?.type,
            })),
            imAddresses: p?.imClients?.map((i) => ({
                primary: i?.metadata?.primary,
                username: i?.username,
                service: i?.protocol,
                type: i?.type,
            })),
            linkAddresses: p?.urls?.map((u) => ({
                primary: u?.metadata?.primary,
                value: u?.value,
                type: u?.type,
            })),
            userId,
        }));
        if (!formattedPeople || !(formattedPeople?.length > 0)) {
            console.log('no formattedPeople to upsert');
            return;
        }
        const operationName = 'InsertContact';
        const query = `
      mutation InsertContact($contacts: [Contact_insert_input!]!) {
        insert_Contact(
          objects: $contacts,
          on_conflict: {
              constraint: Contact_pkey,
              update_columns: [
                name,
                firstName,
                middleName,
                lastName,
                namePrefix,
                nameSuffix,
                nickname,
                phoneticFirstName,
                phoneticMiddleName,
                phoneticLastName,
                company,
                jobTitle,
                department,
                notes,
                imageAvailable,
                image,
                contactType,
                emails,
                phoneNumbers,
                imAddresses,
                linkAddresses,
              ]
          }){
          returning {
            id
          }
        }
       }
    `;
        const variables = {
            contacts: formattedPeople,
        };
        const response = await got
            .post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': adminSecret,
                'X-Hasura-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(response, ' this is response in upsertContacts');
    }
    catch (e) {
        console.log(e, ' unable to upsertContacts');
    }
};
const incrementalGoogleContactsSync2 = async (calendarIntegrationId, userId, clientType, parentSyncToken, parentPageToken) => {
    try {
        let localConnections = {};
        let pageToken = parentPageToken;
        let syncToken = parentSyncToken;
        const token = await getGoogleAPIToken(userId, googlePeopleResource, clientType);
        const googlePeople = google.people({
            version: 'v1',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        const variables = {
            // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
            pageSize: 1000,
            // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
            personFields: 'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
            // Required. Comma-separated list of person fields to be included in the response. Each path should start with `person.`: for example, `person.names` or `person.photos`.
            // 'requestMask.includeField': 'person.names,person.nicknames,person.organizations,person.biographies,person.coverPhotos,person.metadata,person.emailAddresses,person.imClients,person.urls',
            // Optional. Whether the response should return `next_sync_token` on the last page of results. It can be used to get incremental changes since the last request by setting it on the request `sync_token`. More details about sync behavior at `people.connections.list`.
            requestSyncToken: true,
            // Required. The resource name to return connections for. Only `people/me` is valid.
            resourceName: 'people/me',
            // Optional. A sync token, received from a previous response `next_sync_token` Provide this to retrieve only the resources changed since the last request. When syncing, all other parameters provided to `people.connections.list` must match the first call that provided the sync token. More details about sync behavior at `people.connections.list`.
            syncToken: parentSyncToken,
        };
        if (parentPageToken) {
            variables.pageToken = parentPageToken;
        }
        const res = await googlePeople.people.connections.list(variables);
        console.log(res.data);
        const { connections, nextPageToken, nextSyncToken } = res.data;
        console.log(connections, nextPageToken, nextSyncToken, ' connections, nextPageToken, nextSyncToken inside incrementalGoogleContactsSync2');
        localConnections = connections;
        pageToken = nextPageToken;
        syncToken = nextSyncToken;
        await updateGoogleIntegration(calendarIntegrationId, nextSyncToken, nextPageToken);
        const deletedPeople = localConnections?.filter((e) => e?.metadata?.deleted === true);
        if (deletedPeople?.[0]?.names) {
            await deleteContacts(deletedPeople);
        }
        const peopleToUpsert = localConnections?.filter((e) => e?.metadata?.deleted !== true);
        // no events to upsert check next pagetoken
        if (!(peopleToUpsert?.[0]?.names?.length > 0)) {
            console.log('no events to upsert check next pagetoken');
            const variables = {
                // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
                pageSize: 1000,
                // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
                personFields: 'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
                // Required. Comma-separated list of person fields to be included in the response. Each path should start with `person.`: for example, `person.names` or `person.photos`.
                // 'requestMask.includeField': 'person.names,person.nicknames,person.organizations,person.biographies,person.coverPhotos,person.metadata,person.emailAddresses,person.imClients,person.urls',
                // Optional. Whether the response should return `next_sync_token` on the last page of results. It can be used to get incremental changes since the last request by setting it on the request `sync_token`. More details about sync behavior at `people.connections.list`.
                requestSyncToken: true,
                // Required. The resource name to return connections for. Only `people/me` is valid.
                resourceName: 'people/me',
                // Optional. A sync token, received from a previous response `next_sync_token` Provide this to retrieve only the resources changed since the last request. When syncing, all other parameters provided to `people.connections.list` must match the first call that provided the sync token. More details about sync behavior at `people.connections.list`.
                syncToken,
            };
            if (pageToken) {
                variables.pageToken = pageToken;
                const res = await googlePeople.people.connections.list(variables);
                const { connections, nextPageToken, nextSyncToken } = res.data;
                console.log(connections, nextPageToken, nextSyncToken, pageToken, ' connections, nextPageToken, nextSyncToken, pageToken inside incrementalGoogleContactsSync2');
                localConnections = connections;
                pageToken = nextPageToken;
                syncToken = nextSyncToken;
                // tokens in case something goes wrong
                // update pageToken and syncToken
                await updateGoogleIntegration(calendarIntegrationId, nextSyncToken, nextPageToken);
                const deletedPeople = localConnections?.filter((e) => e?.metadata?.deleted === true);
                if (deletedPeople?.[0]?.names) {
                    await deleteContacts(deletedPeople);
                }
                const peopleToUpsert2 = localConnections?.filter((e) => e?.metadata?.deleted !== true);
                if (peopleToUpsert2?.[0]?.names?.length > 0) {
                    await upsertContacts2(peopleToUpsert2, userId);
                }
            }
        }
        else {
            await upsertContacts2(peopleToUpsert, userId);
        }
        if (pageToken) {
            while (pageToken) {
                const variables = {
                    // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
                    pageSize: 1000,
                    // Optional. A page token, received from a previous response `next_page_token`. Provide this to retrieve the subsequent page. When paginating, all other parameters provided to `people.connections.list` must match the first call that provided the page token.
                    pageToken,
                    // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
                    personFields: 'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
                    // Required. Comma-separated list of person fields to be included in the response. Each path should start with `person.`: for example, `person.names` or `person.photos`.
                    // 'requestMask.includeField': 'person.names,person.nicknames,person.organizations,person.biographies,person.coverPhotos,person.metadata,person.emailAddresses,person.imClients,person.urls',
                    // Optional. Whether the response should return `next_sync_token` on the last page of results. It can be used to get incremental changes since the last request by setting it on the request `sync_token`. More details about sync behavior at `people.connections.list`.
                    requestSyncToken: true,
                    // Required. The resource name to return connections for. Only `people/me` is valid.
                    resourceName: 'people/me',
                };
                if (syncToken) {
                    variables.syncToken = syncToken;
                }
                const res = await googlePeople.people.connections.list(variables);
                console.log(res.data);
                const { connections, nextPageToken, nextSyncToken } = res.data;
                console.log(connections, nextPageToken, nextSyncToken, pageToken, ' connections, nextPageToken, nextSyncToken, pageToken inside incrementalGoogleContactsSync2 part of while loop');
                localConnections = connections;
                pageToken = nextPageToken;
                syncToken = nextSyncToken;
                // tokens in case something goes wrong
                // update pageToken and syncToken
                await updateGoogleIntegration(calendarIntegrationId, nextSyncToken, nextPageToken);
                const deletedPeople = localConnections?.filter((e) => e?.metadata?.deleted === true);
                if (deletedPeople?.[0]?.names) {
                    await deleteContacts(deletedPeople);
                }
                const peopleToUpsert = localConnections?.filter((e) => e?.metadata?.deleted !== true);
                // no events to upsert check next pagetoken
                if (!(peopleToUpsert?.[0]?.names?.length > 0)) {
                    console.log('no events to upsert check next pagetoken');
                    const variables = {
                        // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
                        pageSize: 1000,
                        // Optional. A page token, received from a previous response `next_page_token`. Provide this to retrieve the subsequent page. When paginating, all other parameters provided to `people.connections.list` must match the first call that provided the page token.
                        // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
                        personFields: 'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
                        // Required. Comma-separated list of person fields to be included in the response. Each path should start with `person.`: for example, `person.names` or `person.photos`.
                        // 'requestMask.includeField': 'person.names,person.nicknames,person.organizations,person.biographies,person.coverPhotos,person.metadata,person.emailAddresses,person.imClients,person.urls',
                        // Optional. Whether the response should return `next_sync_token` on the last page of results. It can be used to get incremental changes since the last request by setting it on the request `sync_token`. More details about sync behavior at `people.connections.list`.
                        requestSyncToken: true,
                        // Required. The resource name to return connections for. Only `people/me` is valid.
                        resourceName: 'people/me',
                    };
                    if (syncToken) {
                        variables.syncToken = syncToken;
                    }
                    if (pageToken) {
                        variables.pageToken = pageToken;
                        const res = await googlePeople.people.connections.list(variables);
                        const { connections, nextPageToken, nextSyncToken } = res.data;
                        localConnections = connections;
                        pageToken = nextPageToken;
                        syncToken = nextSyncToken;
                        // tokens in case something goes wrong
                        // update pageToken and syncToken
                        await updateGoogleIntegration(calendarIntegrationId, nextSyncToken, nextPageToken);
                        const deletedPeople = localConnections?.filter((e) => e?.metadata?.deleted === true);
                        if (deletedPeople?.[0]?.names?.[0]) {
                            await deleteContacts(deletedPeople);
                        }
                        const peopleToUpsert2 = localConnections?.filter((e) => e?.metadata?.deleted !== true);
                        if (peopleToUpsert2?.[0]?.names?.length > 0) {
                            await upsertContacts2(peopleToUpsert2, userId);
                        }
                    }
                    continue;
                }
                await upsertContacts2(peopleToUpsert, userId);
            }
        }
    }
    catch (e) {
        console.log(e, ' unable to incremental google sync');
        // reset sync
        if (e.code === 410) {
            await resetGoogleIntegrationSyncForContacts(calendarIntegrationId, userId);
            return true;
        }
        return false;
    }
};
const initialGoogleContactsSync2 = async (calendarIntegrationId, userId, clientType) => {
    try {
        let localConnections = {};
        let pageToken = '';
        const token = await getGoogleAPIToken(userId, googlePeopleResource, clientType);
        const googlePeople = google.people({
            version: 'v1',
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        const res = await googlePeople.people.connections.list({
            // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
            pageSize: 1000,
            // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
            personFields: 'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
            // Required. Comma-separated list of person fields to be included in the response. Each path should start with `person.`: for example, `person.names` or `person.photos`.
            // 'requestMask.includeField': 'person.names,person.nicknames,person.organizations,person.biographies,person.coverPhotos,person.metadata,person.emailAddresses,person.imClients,person.urls',
            // Optional. Whether the response should return `next_sync_token` on the last page of results. It can be used to get incremental changes since the last request by setting it on the request `sync_token`. More details about sync behavior at `people.connections.list`.
            requestSyncToken: true,
            // Required. The resource name to return connections for. Only `people/me` is valid.
            resourceName: 'people/me',
        });
        console.log(res.data);
        // Example response
        // {
        //   &quot;connections&quot;: [],
        //   &quot;nextPageToken&quot;: &quot;my_nextPageToken&quot;,
        //   &quot;nextSyncToken&quot;: &quot;my_nextSyncToken&quot;,
        //   &quot;totalItems&quot;: 0,
        //   &quot;totalPeople&quot;: 0
        // }
        const { connections, nextPageToken, nextSyncToken } = res.data;
        console.log(connections, nextPageToken, nextSyncToken, ' connections, nextPageToken, nextSyncToken inside initialGoogleContactsSync2');
        localConnections = connections;
        pageToken = nextPageToken;
        await updateGoogleIntegration(calendarIntegrationId, nextSyncToken, nextPageToken);
        const deletedPeople = localConnections?.filter((e) => e?.metadata?.deleted === true);
        if (deletedPeople?.[0]?.names) {
            await deleteContacts(deletedPeople);
        }
        const peopleToUpsert = localConnections?.filter((e) => e?.metadata?.deleted !== true);
        // no events to upsert check next pagetoken
        if (!(peopleToUpsert?.[0]?.names?.length > 0)) {
            console.log('no events to upsert check next pagetoken');
            const variables = {
                // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
                pageSize: 1000,
                // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
                personFields: 'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
                // Required. Comma-separated list of person fields to be included in the response. Each path should start with `person.`: for example, `person.names` or `person.photos`.
                // 'requestMask.includeField': 'person.names,person.nicknames,person.organizations,person.biographies,person.coverPhotos,person.metadata,person.emailAddresses,person.imClients,person.urls',
                // Required. The resource name to return connections for. Only `people/me` is valid.
                resourceName: 'people/me',
            };
            if (pageToken) {
                variables.pageToken = pageToken;
                const res = await googlePeople.people.connections.list(variables);
                console.log(res.data);
                // Example response
                // {
                //   &quot;connections&quot;: [],
                //   &quot;nextPageToken&quot;: &quot;my_nextPageToken&quot;,
                //   &quot;nextSyncToken&quot;: &quot;my_nextSyncToken&quot;,
                //   &quot;totalItems&quot;: 0,
                //   &quot;totalPeople&quot;: 0
                // }
                const { connections, nextPageToken, nextSyncToken } = res.data;
                console.log(connections, nextPageToken, nextSyncToken, pageToken, ' connections, nextPageToken, nextSyncToken, pageToken inside initialGoogleContactsSync2');
                localConnections = connections;
                pageToken = nextPageToken;
                // tokens in case something goes wrong
                // update pageToken and syncToken
                await updateGoogleIntegration(calendarIntegrationId, nextSyncToken, nextPageToken);
                const deletedPeople = localConnections?.filter((e) => e?.metadata?.deleted === true);
                if (deletedPeople?.[0]?.names?.[0]) {
                    await deleteContacts(deletedPeople);
                }
                const peopleToUpsert2 = localConnections?.filter((e) => e?.metadata?.deleted !== true);
                if (peopleToUpsert2?.[0]?.names?.[0]) {
                    await upsertContacts2(peopleToUpsert2, userId);
                }
            }
        }
        else {
            await upsertContacts2(peopleToUpsert, userId);
        }
        if (pageToken) {
            // fetch all pages
            while (pageToken) {
                const variables = {
                    // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
                    pageSize: 1000,
                    // Optional. A page token, received from a previous response `next_page_token`. Provide this to retrieve the subsequent page. When paginating, all other parameters provided to `people.connections.list` must match the first call that provided the page token.
                    pageToken,
                    // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
                    personFields: 'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
                    // Required. Comma-separated list of person fields to be included in the response. Each path should start with `person.`: for example, `person.names` or `person.photos`.
                    // // 'requestMask.includeField': 'person.names,person.nicknames,person.organizations,person.biographies,person.coverPhotos,person.metadata,person.emailAddresses,person.imClients,person.urls',
                    // Optional. Whether the response should return `next_sync_token` on the last page of results. It can be used to get incremental changes since the last request by setting it on the request `sync_token`. More details about sync behavior at `people.connections.list`.
                    requestSyncToken: true,
                    // Required. The resource name to return connections for. Only `people/me` is valid.
                    resourceName: 'people/me',
                };
                const res = await googlePeople.people.connections.list(variables);
                console.log(res.data);
                // Example response
                // {
                //   &quot;connections&quot;: [],
                //   &quot;nextPageToken&quot;: &quot;my_nextPageToken&quot;,
                //   &quot;nextSyncToken&quot;: &quot;my_nextSyncToken&quot;,
                //   &quot;totalItems&quot;: 0,
                //   &quot;totalPeople&quot;: 0
                // }
                const { connections, nextPageToken, nextSyncToken } = res.data;
                console.log(connections, nextPageToken, nextSyncToken, pageToken, ' connections, nextPageToken, nextSyncToken, pageToken inside initialGoogleContactsSync2 part of while loop');
                localConnections = connections;
                pageToken = nextPageToken;
                // tokens in case something goes wrong
                // update pageToken and syncToken
                await updateGoogleIntegration(calendarIntegrationId, nextSyncToken, nextPageToken);
                const deletedPeople = localConnections?.filter((e) => e?.metadata?.deleted === true);
                if (deletedPeople?.[0]?.names?.[0]) {
                    await deleteContacts(deletedPeople);
                }
                const peopleToUpsert = localConnections?.filter((e) => e?.metadata?.deleted !== true);
                // no events to upsert check next pagetoken
                if (!(peopleToUpsert?.[0]?.names?.length > 0)) {
                    console.log('no events to upsert check next pagetoken');
                    const variables = {
                        // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
                        pageSize: 1000,
                        // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
                        personFields: 'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
                        // Required. Comma-separated list of person fields to be included in the response. Each path should start with `person.`: for example, `person.names` or `person.photos`.
                        // 'requestMask.includeField': 'person.names,person.nicknames,person.organizations,person.biographies,person.coverPhotos,person.metadata,person.emailAddresses,person.imClients,person.urls',
                        // Required. The resource name to return connections for. Only `people/me` is valid.
                        resourceName: 'people/me',
                    };
                    if (pageToken) {
                        variables.pageToken = pageToken;
                        const res = await googlePeople.people.connections.list(variables);
                        console.log(res.data);
                        const { connections, nextPageToken, nextSyncToken } = res.data;
                        localConnections = connections;
                        pageToken = nextPageToken;
                        // tokens in case something goes wrong
                        // update pageToken and syncToken
                        await updateGoogleIntegration(calendarIntegrationId, nextSyncToken, nextPageToken);
                        const deletedPeople = localConnections?.filter((e) => e?.metadata?.deleted === true);
                        if (deletedPeople?.[0]?.names?.[0]) {
                            await deleteContacts(deletedPeople);
                        }
                        const peopleToUpsert2 = localConnections?.filter((e) => e?.metadata?.deleted !== true);
                        if (peopleToUpsert2?.[0]?.names?.[0]) {
                            await upsertContacts2(peopleToUpsert2, userId);
                        }
                    }
                    continue;
                }
                await upsertContacts2(peopleToUpsert, userId);
            }
        }
    }
    catch (e) {
        console.log(e, ' unable to do initial google sync');
        return false;
    }
};
const resetGoogleIntegrationSyncForContacts = async (calendarIntegrationId, userId) => {
    try {
        const operationName = 'updateCalendarIntegration';
        const query = `mutation updateCalendarIntegration($id: uuid!, $changes: Calendar_Integration_set_input) {
      update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: $changes) {
        pageToken
        syncToken
        clientType
      }
    }
    `;
        const variables = {
            id: calendarIntegrationId,
            changes: {
                pageToken: null,
                syncToken: null,
            },
        };
        const response = await got
            .post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': adminSecret,
                'X-Hasura-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(response, ' this is response in resetGoogleIntegrationSync');
        // const { token: authToken } = await getGoogleIntegration(calendarIntegrationId)
        return initialGoogleContactsSync2(calendarIntegrationId, userId, response?.data?.update_Calendar_Integration_by_pk?.clientType);
    }
    catch (e) {
        console.log(e, ' unable to reset google integration sync');
    }
};
const getGoogleIntegration = async (calendarIntegrationId) => {
    try {
        const operationName = 'getCalendarIntegration';
        const query = `query getCalendarIntegration($id: uuid!){
      Calendar_Integration_by_pk(id: $id) {
        id
        name
        token
        refreshToken
        pageToken
        syncToken
        enabled
        clientType
      }
    }`;
        const variables = { id: calendarIntegrationId };
        const response = await got
            .post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': adminSecret,
                'X-Hasura-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        // just to check
        console.log(response, ' this is response in getGoogleIntegration');
        if (response?.data?.Calendar_Integration_by_pk) {
            const { data: { Calendar_Integration_by_pk: { token, pageToken, syncToken, refreshToken, enabled, clientType, }, }, } = response;
            return { token, pageToken, syncToken, refreshToken, enabled, clientType };
        }
    }
    catch (e) {
        console.log(e, ' unable to get google token');
    }
};
const updateGoogleIntegration = async (calendarIntegrationId, syncToken, pageToken, syncEnabled) => {
    try {
        const operationName = 'updateCalendarIntegration';
        const query = `mutation updateCalendarIntegration($id: uuid!,${syncToken !== undefined ? ' $syncToken: String,' : ''}${pageToken !== undefined ? ' $pageToken: String,' : ''}${syncEnabled !== undefined ? ' $syncEnabled: Boolean,' : ''}) {
        update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {${pageToken !== undefined ? 'pageToken: $pageToken,' : ''} ${syncToken !== undefined ? 'syncToken: $syncToken,' : ''} ${syncEnabled !== undefined ? 'syncEnabled: $syncEnabled,' : ''}}) {
          id
          name
          pageToken
          refreshToken
          resource
          syncEnabled
          token
          syncToken
          updatedAt
          userId
          expiresAt
          enabled
          deleted
          createdDate
          clientType
        }
      }
    `;
        let variables = {
            id: calendarIntegrationId,
        };
        if (syncToken?.length > 0) {
            variables = { ...variables, syncToken };
        }
        if (pageToken?.length > 0) {
            variables = { ...variables, pageToken };
        }
        if (syncEnabled === false) {
            variables = { ...variables, syncEnabled };
        }
        const response = await got
            .post(hasuraGraphUrl, {
            headers: {
                'X-Hasura-Admin-Secret': adminSecret,
                'X-Hasura-Role': 'admin',
            },
            json: {
                operationName,
                query,
                variables,
            },
        })
            .json();
        console.log(response, ' this is response in updateGoogleIntegration');
    }
    catch (e) {
        console.log(e, ' unable to update google integration');
    }
};
const handler = async (req, res) => {
    try {
        /**
         * hasura trigger body:
         * {
            "scheduled_time": "2022-05-12T00:45:09.467Z",
            "payload": "{\"userId\": \"fc5df674-b4ee-43c7-ad9e-298ae0eb6208\", \"fileKey\": \"fc5df674-b4ee-43c7-ad9e-298ae0eb6208/65f1255e-01e4-405f-8a5c-ef422fb94c4b.json\"}", - stringified
            "created_at": "2022-05-12T00:46:10.890028Z",
            "id": "32778801-8f8d-43c2-a729-86633b3d701a",
            "comment": ""
          }
          VS
          axios post Body - stringified
          {
            calendarIntegrationId: string,
            userId: string,
            eventTriggerId: string,
            isInitialSync: boolean,
          }
         */
        console.log('googlePeopleSync called');
        let calendarIntegrationId = '';
        let userId = '';
        let isInitialSync = false;
        const bodyObj = req.body;
        if (typeof bodyObj?.scheduled_time === 'string') {
            console.log(bodyObj, ' scheduled trigger');
            const { payload } = bodyObj;
            const payloadObj = JSON.parse(payload);
            calendarIntegrationId = payloadObj.calendarIntegrationId;
            userId = payloadObj.userId;
            isInitialSync = payloadObj?.isInitialSync || false;
        }
        else {
            const body = req.body;
            calendarIntegrationId = body?.calendarIntegrationId;
            userId = body?.userId;
            isInitialSync = body?.isInitialSync;
        }
        // validate
        if (!calendarIntegrationId || !userId) {
            throw new Error(' calendar integration id or user id is empty');
        }
        const eventTrigger = await getEventTriggerByResourceId(googlePeopleResource);
        // validate
        if (!isInitialSync && !eventTrigger) {
            console.log('not initial and no eventTrigger so do nothing');
            return;
        }
        if (eventTrigger?.id) {
            await deleteEventTriggerById(eventTrigger?.id);
        }
        let syncEnabled = true;
        const { pageToken, syncToken, enabled, clientType } = await getGoogleIntegration(calendarIntegrationId);
        if (!enabled) {
            console.log('not enabled google people sync');
            return;
        }
        // if initial sync do 100 resuts else 10
        if (isInitialSync) {
            syncEnabled = await initialGoogleContactsSync2(calendarIntegrationId, userId, clientType);
        }
        else {
            syncEnabled = await incrementalGoogleContactsSync2(calendarIntegrationId, userId, clientType, syncToken, pageToken);
        }
        // if sync is not enabled let the user go through oauth again if needed
        if (syncEnabled === false) {
            await updateGoogleIntegration(calendarIntegrationId, undefined, undefined, syncEnabled);
            return res.status(200).json({
                message: `sync is disabled for googlePeopleSync`,
                event: bodyObj,
            });
        }
        // recreate scheduled event for next time
        const response = await got
            .post(hasuraMetadataUrl, {
            headers: {
                'X-Hasura-Admin-Secret': adminSecret,
                'X-Hasura-Role': 'admin',
                'Content-Type': 'application/json',
            },
            json: {
                type: 'create_scheduled_event',
                args: {
                    webhook: selfGooglePeopleAdminUrl,
                    schedule_at: dayjs().add(14, 'd').utc().format(),
                    payload: JSON.stringify({
                        calendarIntegrationId,
                        userId,
                    }),
                    headers: [
                        {
                            name: 'X-Hasura-Admin-Secret',
                            value: adminSecret,
                        },
                        {
                            name: 'X-Hasura-Role',
                            value: 'admin',
                        },
                        {
                            name: 'Content-Type',
                            value: 'application/json',
                        },
                    ],
                },
            },
        })
            .json();
        console.log(response, ' success response inside googlePeopleSync');
        await insertEventTriggers([
            {
                id: response?.event_id,
                userId,
                name: googlePeopleName,
                resource: googlePeopleResource,
                resourceId: calendarIntegrationId,
                updatedAt: dayjs().format(),
                createdAt: dayjs().format(),
            },
        ]);
        return res.status(200).json({
            message: `successfully taken care of googleCalendarySync!`,
            event: bodyObj,
        });
    }
    catch (e) {
        console.log(e, ' unable sync google calendar');
        return res.status(400).json({
            message: `error processing googlePeopleSync: message: ${e?.message}, code: ${e?.statusCode}`,
            event: e,
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ29vZ2xlLWNvbnRhY3Qtc3luYy1hZG1pbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImdvb2dsZS1jb250YWN0LXN5bmMtYWRtaW4udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQ0EsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBQ3RCLE9BQU8sS0FBSyxNQUFNLE9BQU8sQ0FBQztBQUMxQixPQUFPLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQztBQUNuQyxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0sWUFBWSxDQUFDO0FBSXBDLE9BQU8sRUFDTCxnQkFBZ0IsRUFDaEIsb0JBQW9CLEVBQ3BCLGNBQWMsRUFDZCxpQkFBaUIsRUFDakIsd0JBQXdCLEdBQ3pCLE1BQU0sdUNBQXVDLENBQUM7QUFFL0MsT0FBTyxFQUNMLHNCQUFzQixFQUN0QiwyQkFBMkIsRUFDM0IsaUJBQWlCLEVBQ2pCLG1CQUFtQixHQUNwQixNQUFNLHdDQUF3QyxDQUFDO0FBR2hELEtBQUssQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUM7QUFFbEIsTUFBTSxXQUFXLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQywyQkFBMkIsQ0FBQztBQUM1RCxzREFBc0Q7QUFDdEQsNERBQTREO0FBQzVELDJFQUEyRTtBQUUzRSwyQ0FBMkM7QUFDM0MsTUFBTSxjQUFjLEdBQUcsS0FBSyxFQUFFLE1BQW9CLEVBQUUsRUFBRTtJQUNwRCxJQUFJLENBQUM7UUFDSCxPQUFPLENBQUMsR0FBRyxDQUFDLE1BQU0sRUFBRSwrQkFBK0IsQ0FBQyxDQUFDO1FBQ3JELElBQUksQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLFlBQVksRUFBRSxNQUFNLEdBQUcsQ0FBQyxDQUFDLEVBQUUsQ0FBQztZQUM3QyxPQUFPLENBQUMsR0FBRyxDQUFDLDhCQUE4QixDQUFDLENBQUM7WUFDNUMsT0FBTztRQUNULENBQUM7UUFFRCxNQUFNLEdBQUcsR0FBRyxNQUFNLEVBQUUsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsWUFBWSxDQUFDLE9BQU8sQ0FBQyxTQUFTLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQztRQUV2RSxJQUFJLENBQUMsR0FBRyxJQUFJLENBQUMsQ0FBQyxHQUFHLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7WUFDL0IsT0FBTyxDQUFDLEdBQUcsQ0FBQyw4QkFBOEIsQ0FBQyxDQUFDO1lBQzVDLE9BQU87UUFDVCxDQUFDO1FBQ0QsTUFBTSxhQUFhLEdBQUcsZ0JBQWdCLENBQUM7UUFDdkMsTUFBTSxLQUFLLEdBQUc7Ozs7OztLQU1iLENBQUM7UUFDRixNQUFNLFNBQVMsR0FBRztZQUNoQixHQUFHO1NBQ0osQ0FBQztRQUVGLE1BQU0sUUFBUSxHQUFHLE1BQU0sR0FBRzthQUN2QixJQUFJLENBQUMsY0FBYyxFQUFFO1lBQ3BCLE9BQU8sRUFBRTtnQkFDUCx1QkFBdUIsRUFBRSxXQUFXO2dCQUNwQyxlQUFlLEVBQUUsT0FBTzthQUN6QjtZQUNELElBQUksRUFBRTtnQkFDSixhQUFhO2dCQUNiLEtBQUs7Z0JBQ0wsU0FBUzthQUNWO1NBQ0YsQ0FBQzthQUNELElBQUksRUFBRSxDQUFDO1FBQ1YsT0FBTyxDQUFDLEdBQUcsQ0FBQyxRQUFRLEVBQUUscUNBQXFDLENBQUMsQ0FBQztJQUMvRCxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDRCQUE0QixDQUFDLENBQUM7SUFDL0MsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLE1BQU0sZUFBZSxHQUFHLEtBQUssRUFBRSxNQUFvQixFQUFFLE1BQWMsRUFBRSxFQUFFO0lBQ3JFLElBQUksQ0FBQztRQUNILE9BQU8sQ0FBQyxHQUFHLENBQUMsTUFBTSxFQUFFLGdDQUFnQyxDQUFDLENBQUM7UUFDdEQsSUFBSSxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsWUFBWSxFQUFFLE1BQU0sR0FBRyxDQUFDLENBQUMsRUFBRSxDQUFDO1lBQzdDLE9BQU8sQ0FBQyxHQUFHLENBQUMsOEJBQThCLENBQUMsQ0FBQztZQUM1QyxPQUFPO1FBQ1QsQ0FBQztRQUNELE1BQU0sZUFBZSxHQUFHLE1BQU0sRUFBRSxHQUFHLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDMUMsRUFBRSxFQUFFLENBQUMsRUFBRSxZQUFZLEVBQUUsT0FBTyxDQUFDLFNBQVMsRUFBRSxFQUFFLENBQUM7WUFDM0MsSUFBSSxFQUNGLENBQUMsRUFBRSxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsUUFBUSxFQUFFLE9BQU8sS0FBSyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQztnQkFDekQsRUFBRSxXQUFXLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLFdBQVc7WUFDL0MsU0FBUyxFQUNQLENBQUMsRUFBRSxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsUUFBUSxFQUFFLE9BQU8sS0FBSyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQztnQkFDekQsRUFBRSxTQUFTLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLFNBQVM7WUFDM0MsVUFBVSxFQUNSLENBQUMsRUFBRSxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsUUFBUSxFQUFFLE9BQU8sS0FBSyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQztnQkFDekQsRUFBRSxVQUFVLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLFVBQVU7WUFDN0MsUUFBUSxFQUNOLENBQUMsRUFBRSxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsUUFBUSxFQUFFLE9BQU8sS0FBSyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQztnQkFDekQsRUFBRSxVQUFVLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLFVBQVU7WUFDN0MsVUFBVSxFQUNSLENBQUMsRUFBRSxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsUUFBUSxFQUFFLE9BQU8sS0FBSyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQztnQkFDekQsRUFBRSxlQUFlLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLGVBQWU7WUFDdkQsVUFBVSxFQUNSLENBQUMsRUFBRSxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsUUFBUSxFQUFFLE9BQU8sS0FBSyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQztnQkFDekQsRUFBRSxlQUFlLElBQUksQ0FBQyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLGVBQWU7WUFDdkQsUUFBUSxFQUNOLENBQUMsRUFBRSxTQUFTLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsUUFBUSxFQUFFLE9BQU8sS0FBSyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUMsQ0FBQztnQkFDN0QsRUFBRSxLQUFLLElBQUksQ0FBQyxFQUFFLFNBQVMsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLEtBQUs7WUFDdkMsaUJBQWlCLEVBQ2YsQ0FBQyxFQUFFLEtBQUssRUFBRSxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsRUFBRSxRQUFRLEVBQUUsT0FBTyxLQUFLLElBQUksQ0FBQyxFQUFFLENBQUMsQ0FBQyxDQUFDO2dCQUN6RCxFQUFFLGlCQUFpQixJQUFJLENBQUMsRUFBRSxLQUFLLEVBQUUsQ0FBQyxDQUFDLENB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QUFJLEVBQUUsQ0FBQztRQUVWLE9BQU8sQ0FBQyxHQUFHLENBQUMsUUFBUSxFQUFFLDJDQUEyQyxDQUFDLENBQUM7UUFFbkUsTUFBTSxtQkFBbUIsQ0FBQztZQUN4QjtnQkFDRSxFQUFFLEVBQUUsUUFBUSxFQUFFLFFBQVE7Z0JBQ3RCLE1BQU07Z0JBQ04sSUFBSSxFQUFFLGdCQUFnQjtnQkFDdEIsUUFBUSxFQUFFLG9CQUFvQjtnQkFDOUIsVUFBVSxFQUFFLHFCQUFxQjtnQkFDakMsU0FBUyxFQUFFLEtBQUssRUFBRSxDQUFDLE1BQU0sRUFBRTtnQkFDM0IsU0FBUyxFQUFFLEtBQUssRUFBRSxDQUFDLE1BQU0sRUFBRTthQUM1QjtTQUNGLENBQUMsQ0FBQztRQUVILE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDMUIsT0FBTyxFQUFFLGlEQUFpRDtZQUMxRCxLQUFLLEVBQUUsT0FBTztTQUNmLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsOEJBQThCLENBQUMsQ0FBQztRQUUvQyxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSwrQ0FBK0MsQ0FBQyxFQUFFLE9BQU8sV0FBVyxDQUFDLEVBQUUsVUFBVSxFQUFFO1lBQzVGLEtBQUssRUFBRSxDQUFDO1NBQ1QsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGVBQWUsT0FBTyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbmltcG9ydCBnb3QgZnJvbSAnZ290JztcbmltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG5pbXBvcnQgdXRjIGZyb20gJ2RheWpzL3BsdWdpbi91dGMnO1xuaW1wb3J0IHsgZ29vZ2xlIH0gZnJvbSAnZ29vZ2xlYXBpcyc7XG5cbmltcG9ydCB7IFBlcnNvblR5cGUgfSBmcm9tICcuLi9fbGlicy90eXBlcy9nb29nbGVQZW9wbGVTeW5jL3R5cGVzJztcblxuaW1wb3J0IHtcbiAgZ29vZ2xlUGVvcGxlTmFtZSxcbiAgZ29vZ2xlUGVvcGxlUmVzb3VyY2UsXG4gIGhhc3VyYUdyYXBoVXJsLFxuICBoYXN1cmFNZXRhZGF0YVVybCxcbiAgc2VsZkdvb2dsZVBlb3BsZUFkbWluVXJsLFxufSBmcm9tICdAZ29vZ2xlX2NhbGVuZGFyX3N5bmMvX2xpYnMvY29uc3RhbnRzJztcblxuaW1wb3J0IHtcbiAgZGVsZXRlRXZlbnRUcmlnZ2VyQnlJZCxcbiAgZ2V0RXZlbnRUcmlnZ2VyQnlSZXNvdXJjZUlkLFxuICBnZXRHb29nbGVBUElUb2tlbixcbiAgaW5zZXJ0RXZlbnRUcmlnZ2Vycyxcbn0gZnJvbSAnQGdvb2dsZV9jYWxlbmRhcl9zeW5jL19saWJzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGUgfSBmcm9tICdAZ29vZ2xlX2NhbGVuZGFyX3N5bmMvX2xpYnMvdHlwZXMvZ29vZ2xlQ2FsZW5kYXJTeW5jL3R5cGVzJztcblxuZGF5anMuZXh0ZW5kKHV0Yyk7XG5cbmNvbnN0IGFkbWluU2VjcmV0ID0gcHJvY2Vzcy5lbnYuSEFTVVJBX0dSQVBIUUxfQURNSU5fU0VDUkVUO1xuLy8gY29uc3QgaGFzdXJhR3JhcGhVcmwgPSBwcm9jZXNzLmVudi5IQVNVUkFfR1JBUEhfVVJMXG4vLyBjb25zdCBoYXN1cmFNZXRhZGF0YVVybCA9IHByb2Nlc3MuZW52LkhBU1VSQV9NRVRBREFUQV9VUkxcbi8vIGNvbnN0IHNlbGZHb29nbGVQZW9wbGVBZG1pblVybCA9IHByb2Nlc3MuZW52LlNFTEZfR09PR0xFX1BFT1BMRV9BRE1JTl9VUlxuXG4vLyBjb25zdCBnb29nbGVQZW9wbGUgPSBnb29nbGUucGVvcGxlKCd2MScpXG5jb25zdCBkZWxldGVDb250YWN0cyA9IGFzeW5jIChwZW9wbGU6IFBlcnNvblR5cGVbXSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKHBlb3BsZSwgJyBwZW9wbGUgaW5zaWRlIGRlbGV0ZUNvbnRhY3RzJyk7XG4gICAgaWYgKCEocGVvcGxlPy5bMF0/LnJlc291cmNlTmFtZT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgbm8gcGVvcGxlIHByZXNlbnQgdG8gZGVsZXRlJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3QgaWRzID0gcGVvcGxlPy5tYXAoKHApID0+IHA/LnJlc291cmNlTmFtZS5yZXBsYWNlKCdwZW9wbGUvJywgJycpKTtcblxuICAgIGlmICghaWRzIHx8ICEoaWRzPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coJyBubyBwZW9wbGUgcHJlc2VudCB0byBkZWxldGUnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdkZWxldGVDb250YWN0cyc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBtdXRhdGlvbiBkZWxldGVDb250YWN0cygkaWRzOiBbU3RyaW5nIV0hKSB7XG4gICAgICAgIGRlbGV0ZV9Db250YWN0KHdoZXJlOiB7aWQ6IHtfaW46ICRpZHN9fSkge1xuICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWRzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBhZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHRoaXMgaXMgcmVzcG9uc2UgaW4gZGVsZXRlQ29udGFjdHMnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBjb250YWN0cycpO1xuICB9XG59O1xuXG5jb25zdCB1cHNlcnRDb250YWN0czIgPSBhc3luYyAocGVvcGxlOiBQZXJzb25UeXBlW10sIHVzZXJJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2cocGVvcGxlLCAnIHBlb3BsZSBpbnNpZGUgdXBzZXJ0Q29udGFjdHMyJyk7XG4gICAgaWYgKCEocGVvcGxlPy5bMF0/LnJlc291cmNlTmFtZT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgbm8gcGVvcGxlIHByZXNlbnQgdG8gdXBzZXJ0Jyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuICAgIGNvbnN0IGZvcm1hdHRlZFBlb3BsZSA9IHBlb3BsZT8ubWFwKChwKSA9PiAoe1xuICAgICAgaWQ6IHA/LnJlc291cmNlTmFtZT8ucmVwbGFjZSgncGVvcGxlLycsICcnKSxcbiAgICAgIG5hbWU6XG4gICAgICAgIHA/Lm5hbWVzPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy5kaXNwbGF5TmFtZSB8fCBwPy5uYW1lcz8uWzBdPy5kaXNwbGF5TmFtZSxcbiAgICAgIGZpcnN0TmFtZTpcbiAgICAgICAgcD8ubmFtZXM/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF1cbiAgICAgICAgICA/LmdpdmVuTmFtZSB8fCBwPy5uYW1lcz8uWzBdPy5naXZlbk5hbWUsXG4gICAgICBtaWRkbGVOYW1lOlxuICAgICAgICBwPy5uYW1lcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8ubWlkZGxlTmFtZSB8fCBwPy5uYW1lcz8uWzBdPy5taWRkbGVOYW1lLFxuICAgICAgbGFzdE5hbWU6XG4gICAgICAgIHA/Lm5hbWVzPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy5mYW1pbHlOYW1lIHx8IHA/Lm5hbWVzPy5bMF0/LmZhbWlseU5hbWUsXG4gICAgICBuYW1lUHJlZml4OlxuICAgICAgICBwPy5uYW1lcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8uaG9ub3JpZmljUHJlZml4IHx8IHA/Lm5hbWVzPy5bMF0/Lmhvbm9yaWZpY1ByZWZpeCxcbiAgICAgIG5hbWVTdWZmaXg6XG4gICAgICAgIHA/Lm5hbWVzPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy5ob25vcmlmaWNTdWZmaXggfHwgcD8ubmFtZXM/LlswXT8uaG9ub3JpZmljU3VmZml4LFxuICAgICAgbmlja25hbWU6XG4gICAgICAgIHA/Lm5pY2tuYW1lcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8udmFsdWUgfHwgcD8ubmlja25hbWVzPy5bMF0/LnZhbHVlLFxuICAgICAgcGhvbmV0aWNGaXJzdE5hbWU6XG4gICAgICAgIHA/Lm5hbWVzPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy5waG9uZXRpY0dpdmVuTmFtZSB8fCBwPy5uYW1lcz8uWzBdPy5waG9uZXRpY0dpdmVuTmFtZSxcbiAgICAgIHBob25ldGljTWlkZGxlTmFtZTpcbiAgICAgICAgcD8ubmFtZXM/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF1cbiAgICAgICAgICA/LnBob25ldGljTWlkZGxlTmFtZSB8fCBwPy5uYW1lcz8uWzBdPy5waG9uZXRpY01pZGRsZU5hbWUsXG4gICAgICBwaG9uZXRpY0xhc3ROYW1lOlxuICAgICAgICBwPy5uYW1lcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8ucGhvbmV0aWNGYW1pbHlOYW1lIHx8IHA/Lm5hbWVzPy5bMF0/LnBob25ldGljRmFtaWx5TmFtZSxcbiAgICAgIGNvbXBhbnk6XG4gICAgICAgIHA/Lm9yZ2FuaXphdGlvbnM/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF1cbiAgICAgICAgICA/Lm5hbWUgfHwgcD8ub3JnYW5pemF0aW9ucz8uWzBdPy5uYW1lLFxuICAgICAgam9iVGl0bGU6XG4gICAgICAgIHA/Lm9yZ2FuaXphdGlvbnM/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF1cbiAgICAgICAgICA/LnRpdGxlIHx8IHA/Lm9yZ2FuaXphdGlvbnM/LlswXT8udGl0bGUsXG4gICAgICBkZXBhcnRtZW50OlxuICAgICAgICBwPy5vcmdhbml6YXRpb25zPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy5kZXBhcnRtZW50IHx8IHA/Lm9yZ2FuaXphdGlvbnM/LlswXT8uZGVwYXJ0bWVudCxcbiAgICAgIG5vdGVzOlxuICAgICAgICBwPy5iaW9ncmFwaGllcz8uZmlsdGVyKFxuICAgICAgICAgIChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSAmJiBuPy5jb250ZW50VHlwZSA9PT0gJ1RFWFRfSFRNTCdcbiAgICAgICAgKT8uWzBdPy52YWx1ZSB8fCBwPy5iaW9ncmFwaGllcz8uWzBdPy52YWx1ZSxcbiAgICAgIGltYWdlQXZhaWxhYmxlOlxuICAgICAgICBwPy5jb3ZlclBob3Rvcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXT8udXJsXG4gICAgICAgICAgPy5sZW5ndGggPiAwLFxuICAgICAgaW1hZ2U6XG4gICAgICAgIHA/LmNvdmVyUGhvdG9zPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy51cmwgfHwgcD8uY292ZXJQaG90b3M/LlswXT8udXJsLFxuICAgICAgY29udGFjdFR5cGU6IHA/Lm1ldGFkYXRhPy5vYmplY3RUeXBlLFxuICAgICAgZW1haWxzOiBwPy5lbWFpbEFkZHJlc3Nlcz8ubWFwKChlKSA9PiAoe1xuICAgICAgICBwcmltYXJ5OiBlPy5tZXRhZGF0YT8ucHJpbWFyeSxcbiAgICAgICAgdmFsdWU6IGU/LnZhbHVlLFxuICAgICAgICB0eXBlOiBlPy50eXBlLFxuICAgICAgICBkaXNwbGF5TmFtZTogZT8uZGlzcGxheU5hbWUsXG4gICAgICB9KSksXG4gICAgICBwaG9uZU51bWJlcnM6IHA/LnBob25lTnVtYmVycz8ubWFwKChwKSA9PiAoe1xuICAgICAgICBwcmltYXJ5OiBwPy5tZXRhZGF0YT8ucHJpbWFyeSxcbiAgICAgICAgdmFsdWU6IHA/LnZhbHVlLFxuICAgICAgICB0eXBlOiBwPy50eXBlLFxuICAgICAgfSkpLFxuICAgICAgaW1BZGRyZXNzZXM6IHA/LmltQ2xpZW50cz8ubWFwKChpKSA9PiAoe1xuICAgICAgICBwcmltYXJ5OiBpPy5tZXRhZGF0YT8ucHJpbWFyeSxcbiAgICAgICAgdXNlcm5hbWU6IGk/LnVzZXJuYW1lLFxuICAgICAgICBzZXJ2aWNlOiBpPy5wcm90b2NvbCxcbiAgICAgICAgdHlwZTogaT8udHlwZSxcbiAgICAgIH0pKSxcbiAgICAgIGxpbmtBZGRyZXNzZXM6IHA/LnVybHM/Lm1hcCgodSkgPT4gKHtcbiAgICAgICAgcHJpbWFyeTogdT8ubWV0YWRhdGE/LnByaW1hcnksXG4gICAgICAgIHZhbHVlOiB1Py52YWx1ZSxcbiAgICAgICAgdHlwZTogdT8udHlwZSxcbiAgICAgIH0pKSxcbiAgICAgIHVzZXJJZCxcbiAgICB9KSk7XG5cbiAgICBpZiAoIWZvcm1hdHRlZFBlb3BsZSB8fCAhKGZvcm1hdHRlZFBlb3BsZT8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyBmb3JtYXR0ZWRQZW9wbGUgdG8gdXBzZXJ0Jyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdJbnNlcnRDb250YWN0JztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIG11dGF0aW9uIEluc2VydENvbnRhY3QoJGNvbnRhY3RzOiBbQ29udGFjdF9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgaW5zZXJ0X0NvbnRhY3QoXG4gICAgICAgICAgb2JqZWN0czogJGNvbnRhY3RzLFxuICAgICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgICAgIGNvbnN0cmFpbnQ6IENvbnRhY3RfcGtleSxcbiAgICAgICAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICBuYW1lLFxuICAgICAgICAgICAgICAgIGZpcnN0TmFtZSxcbiAgICAgICAgICAgICAgICBtaWRkbGVOYW1lLFxuICAgICAgICAgICAgICAgIGxhc3ROYW1lLFxuICAgICAgICAgICAgICAgIG5hbWVQcmVmaXgsXG4gICAgICAgICAgICAgICAgbmFtZVN1ZmZpeCxcbiAgICAgICAgICAgICAgICBuaWNrbmFtZSxcbiAgICAgICAgICAgICAgICBwaG9uZXRpY0ZpcnN0TmFtZSxcbiAgICAgICAgICAgICAgICBwaG9uZXRpY01pZGRsZU5hbWUsXG4gICAgICAgICAgICAgICAgcGhvbmV0aWNMYXN0TmFtZSxcbiAgICAgICAgICAgICAgICBjb21wYW55LFxuICAgICAgICAgICAgICAgIGpvYlRpdGxlLFxuICAgICAgICAgICAgICAgIGRlcGFydG1lbnQsXG4gICAgICAgICAgICAgICAgbm90ZXMsXG4gICAgICAgICAgICAgICAgaW1hZ2VBdmFpbGFibGUsXG4gICAgICAgICAgICAgICAgaW1hZ2UsXG4gICAgICAgICAgICAgICAgY29udGFjdFR5cGUsXG4gICAgICAgICAgICAgICAgZW1haWxzLFxuICAgICAgICAgICAgICAgIHBob25lTnVtYmVycyxcbiAgICAgICAgICAgICAgICBpbUFkZHJlc3NlcyxcbiAgICAgICAgICAgICAgICBsaW5rQWRkcmVzc2VzLFxuICAgICAgICAgICAgICBdXG4gICAgICAgICAgfSl7XG4gICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgY29udGFjdHM6IGZvcm1hdHRlZFBlb3BsZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogYWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHRoaXMgaXMgcmVzcG9uc2UgaW4gdXBzZXJ0Q29udGFjdHMnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwc2VydENvbnRhY3RzJyk7XG4gIH1cbn07XG5cbmNvbnN0IGluY3JlbWVudGFsR29vZ2xlQ29udGFjdHNTeW5jMiA9IGFzeW5jIChcbiAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkOiBzdHJpbmcsXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjbGllbnRUeXBlOiAnaW9zJyB8ICdhbmRyb2lkJyB8ICd3ZWInIHwgJ2F0b21pYy13ZWInLFxuICBwYXJlbnRTeW5jVG9rZW46IHN0cmluZyxcbiAgcGFyZW50UGFnZVRva2VuPzogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgbG9jYWxDb25uZWN0aW9uczogUGVyc29uVHlwZVtdIHwgb2JqZWN0ID0ge307XG4gICAgbGV0IHBhZ2VUb2tlbiA9IHBhcmVudFBhZ2VUb2tlbjtcbiAgICBsZXQgc3luY1Rva2VuID0gcGFyZW50U3luY1Rva2VuO1xuXG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRHb29nbGVBUElUb2tlbihcbiAgICAgIHVzZXJJZCxcbiAgICAgIGdvb2dsZVBlb3BsZVJlc291cmNlLFxuICAgICAgY2xpZW50VHlwZVxuICAgICk7XG5cbiAgICBjb25zdCBnb29nbGVQZW9wbGUgPSBnb29nbGUucGVvcGxlKHtcbiAgICAgIHZlcnNpb246ICd2MScsXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnN0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgLy8gT3B0aW9uYWwuIFRoZSBudW1iZXIgb2YgY29ubmVjdGlvbnMgdG8gaW5jbHVkZSBpbiB0aGUgcmVzcG9uc2UuIFZhbGlkIHZhbHVlcyBhcmUgYmV0d2VlbiAxIGFuZCAxMDAwLCBpbmNsdXNpdmUuIERlZmF1bHRzIHRvIDEwMCBpZiBub3Qgc2V0IG9yIHNldCB0byAwLlxuICAgICAgcGFnZVNpemU6IDEwMDAsXG4gICAgICAvLyBSZXF1aXJlZC4gQSBmaWVsZCBtYXNrIHRvIHJlc3RyaWN0IHdoaWNoIGZpZWxkcyBvbiBlYWNoIHBlcnNvbiBhcmUgcmV0dXJuZWQuIE11bHRpcGxlIGZpZWxkcyBjYW4gYmUgc3BlY2lmaWVkIGJ5IHNlcGFyYXRpbmcgdGhlbSB3aXRoIGNvbW1hcy4gVmFsaWQgdmFsdWVzIGFyZTogKiBhZGRyZXNzZXMgKiBhZ2VSYW5nZXMgKiBiaW9ncmFwaGllcyAqIGJpcnRoZGF5cyAqIGNhbGVuZGFyVXJscyAqIGNsaWVudERhdGEgKiBjb3ZlclBob3RvcyAqIGVtYWlsQWRkcmVzc2VzICogZXZlbnRzICogZXh0ZXJuYWxJZHMgKiBnZW5kZXJzICogaW1DbGllbnRzICogaW50ZXJlc3RzICogbG9jYWxlcyAqIGxvY2F0aW9ucyAqIG1lbWJlcnNoaXBzICogbWV0YWRhdGEgKiBtaXNjS2V5d29yZHMgKiBuYW1lcyAqIG5pY2tuYW1lcyAqIG9jY3VwYXRpb25zICogb3JnYW5pemF0aW9ucyAqIHBob25lTnVtYmVycyAqIHBob3RvcyAqIHJlbGF0aW9ucyAqIHNpcEFkZHJlc3NlcyAqIHNraWxscyAqIHVybHMgKiB1c2VyRGVmaW5lZFxuICAgICAgcGVyc29uRmllbGRzOlxuICAgICAgICAnbmFtZXMsbmlja25hbWVzLG9yZ2FuaXphdGlvbnMsYmlvZ3JhcGhpZXMsY292ZXJQaG90b3MsbWV0YWRhdGEsZW1haWxBZGRyZXNzZXMsaW1DbGllbnRzLHVybHMnLFxuICAgICAgLy8gUmVxdWlyZWQuIENvbW1hLXNlcGFyYXRlZCBsaXN0IG9mIHBlcnNvbiBmaWVsZHMgdG8gYmUgaW5jbHVkZWQgaW4gdGhlIHJlc3BvbnNlLiBFYWNoIHBhdGggc2hvdWxkIHN0YXJ0IHdpdGggYHBlcnNvbi5gOiBmb3IgZXhhbXBsZSwgYHBlcnNvbi5uYW1lc2Agb3IgYHBlcnNvbi5waG90b3NgLlxuICAgICAgLy8gJ3JlcXVlc3RNYXNrLmluY2x1ZGVGaWVsZCc6ICdwZXJzb24ubmFtZXMscGVyc29uLm5pY2tuYW1lcyxwZXJzb24ub3JnYW5pemF0aW9ucyxwZXJzb24uYmlvZ3JhcGhpZXMscGVyc29uLmNvdmVyUGhvdG9zLHBlcnNvbi5tZXRhZGF0YSxwZXJzb24uZW1haWxBZGRyZXNzZXMscGVyc29uLmltQ2xpZW50cyxwZXJzb24udXJscycsXG4gICAgICAvLyBPcHRpb25hbC4gV2hldGhlciB0aGUgcmVzcG9uc2Ugc2hvdWxkIHJldHVybiBgbmV4dF9zeW5jX3Rva2VuYCBvbiB0aGUgbGFzdCBwYWdlIG9mIHJlc3VsdHMuIEl0IGNhbiBiZSB1c2VkIHRvIGdldCBpbmNyZW1lbnRhbCBjaGFuZ2VzIHNpbmNlIHRoZSBsYXN0IHJlcXVlc3QgYnkgc2V0dGluZyBpdCBvbiB0aGUgcmVxdWVzdCBgc3luY190b2tlbmAuIE1vcmUgZGV0YWlscyBhYm91dCBzeW5jIGJlaGF2aW9yIGF0IGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAuXG4gICAgICByZXF1ZXN0U3luY1Rva2VuOiB0cnVlLFxuICAgICAgLy8gUmVxdWlyZWQuIFRoZSByZXNvdXJjZSBuYW1lIHRvIHJldHVybiBjb25uZWN0aW9ucyBmb3IuIE9ubHkgYHBlb3BsZS9tZWAgaXMgdmFsaWQuXG4gICAgICByZXNvdXJjZU5hbWU6ICdwZW9wbGUvbWUnLFxuICAgICAgLy8gT3B0aW9uYWwuIEEgc3luYyB0b2tlbiwgcmVjZWl2ZWQgZnJvbSBhIHByZXZpb3VzIHJlc3BvbnNlIGBuZXh0X3N5bmNfdG9rZW5gIFByb3ZpZGUgdGhpcyB0byByZXRyaWV2ZSBvbmx5IHRoZSByZXNvdXJjZXMgY2hhbmdlZCBzaW5jZSB0aGUgbGFzdCByZXF1ZXN0LiBXaGVuIHN5bmNpbmcsIGFsbCBvdGhlciBwYXJhbWV0ZXJzIHByb3ZpZGVkIHRvIGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAgbXVzdCBtYXRjaCB0aGUgZmlyc3QgY2FsbCB0aGF0IHByb3ZpZGVkIHRoZSBzeW5jIHRva2VuLiBNb3JlIGRldGFpbHMgYWJvdXQgc3luYyBiZWhhdmlvciBhdCBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgLlxuICAgICAgc3luY1Rva2VuOiBwYXJlbnRTeW5jVG9rZW4sXG4gICAgfTtcblxuICAgIGlmIChwYXJlbnRQYWdlVG9rZW4pIHtcbiAgICAgIHZhcmlhYmxlcy5wYWdlVG9rZW4gPSBwYXJlbnRQYWdlVG9rZW47XG4gICAgfVxuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlUGVvcGxlLnBlb3BsZS5jb25uZWN0aW9ucy5saXN0KHZhcmlhYmxlcyk7XG4gICAgY29uc29sZS5sb2cocmVzLmRhdGEpO1xuXG4gICAgY29uc3QgeyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGNvbm5lY3Rpb25zLFxuICAgICAgbmV4dFBhZ2VUb2tlbixcbiAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAnIGNvbm5lY3Rpb25zLCBuZXh0UGFnZVRva2VuLCBuZXh0U3luY1Rva2VuIGluc2lkZSBpbmNyZW1lbnRhbEdvb2dsZUNvbnRhY3RzU3luYzInXG4gICAgKTtcblxuICAgIGxvY2FsQ29ubmVjdGlvbnMgPSBjb25uZWN0aW9ucztcbiAgICBwYWdlVG9rZW4gPSBuZXh0UGFnZVRva2VuO1xuICAgIHN5bmNUb2tlbiA9IG5leHRTeW5jVG9rZW47XG5cbiAgICBhd2FpdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbihcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICBuZXh0UGFnZVRva2VuXG4gICAgKTtcblxuICAgIGNvbnN0IGRlbGV0ZWRQZW9wbGUgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgPT09IHRydWVcbiAgICApO1xuXG4gICAgaWYgKGRlbGV0ZWRQZW9wbGU/LlswXT8ubmFtZXMpIHtcbiAgICAgIGF3YWl0IGRlbGV0ZUNvbnRhY3RzKGRlbGV0ZWRQZW9wbGUgYXMgUGVyc29uVHlwZVtdKTtcbiAgICB9XG5cbiAgICBjb25zdCBwZW9wbGVUb1Vwc2VydCA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCAhPT0gdHJ1ZVxuICAgICk7XG5cbiAgICAvLyBubyBldmVudHMgdG8gdXBzZXJ0IGNoZWNrIG5leHQgcGFnZXRva2VuXG4gICAgaWYgKCEocGVvcGxlVG9VcHNlcnQ/LlswXT8ubmFtZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlbicpO1xuICAgICAgY29uc3QgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICAgIC8vIE9wdGlvbmFsLiBUaGUgbnVtYmVyIG9mIGNvbm5lY3Rpb25zIHRvIGluY2x1ZGUgaW4gdGhlIHJlc3BvbnNlLiBWYWxpZCB2YWx1ZXMgYXJlIGJldHdlZW4gMSBhbmQgMTAwMCwgaW5jbHVzaXZlLiBEZWZhdWx0cyB0byAxMDAgaWYgbm90IHNldCBvciBzZXQgdG8gMC5cbiAgICAgICAgcGFnZVNpemU6IDEwMDAsXG4gICAgICAgIC8vIFJlcXVpcmVkLiBBIGZpZWxkIG1hc2sgdG8gcmVzdHJpY3Qgd2hpY2ggZmllbGRzIG9uIGVhY2ggcGVyc29uIGFyZSByZXR1cm5lZC4gTXVsdGlwbGUgZmllbGRzIGNhbiBiZSBzcGVjaWZpZWQgYnkgc2VwYXJhdGluZyB0aGVtIHdpdGggY29tbWFzLiBWYWxpZCB2YWx1ZXMgYXJlOiAqIGFkZHJlc3NlcyAqIGFnZVJhbmdlcyAqIGJpb2dyYXBoaWVzICogYmlydGhkYXlzICogY2FsZW5kYXJVcmxzICogY2xpZW50RGF0YSAqIGNvdmVyUGhvdG9zICogZW1haWxBZGRyZXNzZXMgKiBldmVudHMgKiBleHRlcm5hbElkcyAqIGdlbmRlcnMgKiBpbUNsaWVudHMgKiBpbnRlcmVzdHMgKiBsb2NhbGVzICogbG9jYXRpb25zICogbWVtYmVyc2hpcHMgKiBtZXRhZGF0YSAqIG1pc2NLZXl3b3JkcyAqIG5hbWVzICogbmlja25hbWVzICogb2NjdXBhdGlvbnMgKiBvcmdhbml6YXRpb25zICogcGhvbmVOdW1iZXJzICogcGhvdG9zICogcmVsYXRpb25zICogc2lwQWRkcmVzc2VzICogc2tpbGxzICogdXJscyAqIHVzZXJEZWZpbmVkXG4gICAgICAgIHBlcnNvbkZpZWxkczpcbiAgICAgICAgICAnbmFtZXMsbmlja25hbWVzLG9yZ2FuaXphdGlvbnMsYmlvZ3JhcGhpZXMsY292ZXJQaG90b3MsbWV0YWRhdGEsZW1haWxBZGRyZXNzZXMsaW1DbGllbnRzLHVybHMnLFxuICAgICAgICAvLyBSZXF1aXJlZC4gQ29tbWEtc2VwYXJhdGVkIGxpc3Qgb2YgcGVyc29uIGZpZWxkcyB0byBiZSBpbmNsdWRlZCBpbiB0aGUgcmVzcG9uc2UuIEVhY2ggcGF0aCBzaG91bGQgc3RhcnQgd2l0aCBgcGVyc29uLmA6IGZvciBleGFtcGxlLCBgcGVyc29uLm5hbWVzYCBvciBgcGVyc29uLnBob3Rvc2AuXG4gICAgICAgIC8vICdyZXF1ZXN0TWFzay5pbmNsdWRlRmllbGQnOiAncGVyc29uLm5hbWVzLHBlcnNvbi5uaWNrbmFtZXMscGVyc29uLm9yZ2FuaXphdGlvbnMscGVyc29uLmJpb2dyYXBoaWVzLHBlcnNvbi5jb3ZlclBob3RvcyxwZXJzb24ubWV0YWRhdGEscGVyc29uLmVtYWlsQWRkcmVzc2VzLHBlcnNvbi5pbUNsaWVudHMscGVyc29uLnVybHMnLFxuICAgICAgICAvLyBPcHRpb25hbC4gV2hldGhlciB0aGUgcmVzcG9uc2Ugc2hvdWxkIHJldHVybiBgbmV4dF9zeW5jX3Rva2VuYCBvbiB0aGUgbGFzdCBwYWdlIG9mIHJlc3VsdHMuIEl0IGNhbiBiZSB1c2VkIHRvIGdldCBpbmNyZW1lbnRhbCBjaGFuZ2VzIHNpbmNlIHRoZSBsYXN0IHJlcXVlc3QgYnkgc2V0dGluZyBpdCBvbiB0aGUgcmVxdWVzdCBgc3luY190b2tlbmAuIE1vcmUgZGV0YWlscyBhYm91dCBzeW5jIGJlaGF2aW9yIGF0IGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAuXG4gICAgICAgIHJlcXVlc3RTeW5jVG9rZW46IHRydWUsXG4gICAgICAgIC8vIFJlcXVpcmVkLiBUaGUgcmVzb3VyY2UgbmFtZSB0byByZXR1cm4gY29ubmVjdGlvbnMgZm9yLiBPbmx5IGBwZW9wbGUvbWVgIGlzIHZhbGlkLlxuICAgICAgICByZXNvdXJjZU5hbWU6ICdwZW9wbGUvbWUnLFxuICAgICAgICAvLyBPcHRpb25hbC4gQSBzeW5jIHRva2VuLCByZWNlaXZlZCBmcm9tIGEgcHJldmlvdXMgcmVzcG9uc2UgYG5leHRfc3luY190b2tlbmAgUHJvdmlkZSB0aGlzIHRvIHJldHJpZXZlIG9ubHkgdGhlIHJlc291cmNlcyBjaGFuZ2VkIHNpbmNlIHRoZSBsYXN0IHJlcXVlc3QuIFdoZW4gc3luY2luZywgYWxsIG90aGVyIHBhcmFtZXRlcnMgcHJvdmlkZWQgdG8gYHBlb3BsZS5jb25uZWN0aW9ucy5saXN0YCBtdXN0IG1hdGNoIHRoZSBmaXJzdCBjYWxsIHRoYXQgcHJvdmlkZWQgdGhlIHN5bmMgdG9rZW4uIE1vcmUgZGV0YWlscyBhYm91dCBzeW5jIGJlaGF2aW9yIGF0IGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAuXG4gICAgICAgIHN5bmNUb2tlbixcbiAgICAgIH07XG5cbiAgICAgIGlmIChwYWdlVG9rZW4pIHtcbiAgICAgICAgdmFyaWFibGVzLnBhZ2VUb2tlbiA9IHBhZ2VUb2tlbjtcbiAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlUGVvcGxlLnBlb3BsZS5jb25uZWN0aW9ucy5saXN0KHZhcmlhYmxlcyk7XG5cbiAgICAgICAgY29uc3QgeyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGNvbm5lY3Rpb25zLFxuICAgICAgICAgIG5leHRQYWdlVG9rZW4sXG4gICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICBwYWdlVG9rZW4sXG4gICAgICAgICAgJyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiwgcGFnZVRva2VuIGluc2lkZSBpbmNyZW1lbnRhbEdvb2dsZUNvbnRhY3RzU3luYzInXG4gICAgICAgICk7XG5cbiAgICAgICAgbG9jYWxDb25uZWN0aW9ucyA9IGNvbm5lY3Rpb25zO1xuICAgICAgICBwYWdlVG9rZW4gPSBuZXh0UGFnZVRva2VuO1xuICAgICAgICBzeW5jVG9rZW4gPSBuZXh0U3luY1Rva2VuO1xuICAgICAgICAvLyB0b2tlbnMgaW4gY2FzZSBzb21ldGhpbmcgZ29lcyB3cm9uZ1xuICAgICAgICAvLyB1cGRhdGUgcGFnZVRva2VuIGFuZCBzeW5jVG9rZW5cbiAgICAgICAgYXdhaXQgdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24oXG4gICAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgbmV4dFBhZ2VUb2tlblxuICAgICAgICApO1xuICAgICAgICBjb25zdCBkZWxldGVkUGVvcGxlID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCA9PT0gdHJ1ZVxuICAgICAgICApO1xuXG4gICAgICAgIGlmIChkZWxldGVkUGVvcGxlPy5bMF0/Lm5hbWVzKSB7XG4gICAgICAgICAgYXdhaXQgZGVsZXRlQ29udGFjdHMoZGVsZXRlZFBlb3BsZSBhcyBQZXJzb25UeXBlW10pO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcGVvcGxlVG9VcHNlcnQyID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCAhPT0gdHJ1ZVxuICAgICAgICApO1xuICAgICAgICBpZiAocGVvcGxlVG9VcHNlcnQyPy5bMF0/Lm5hbWVzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgYXdhaXQgdXBzZXJ0Q29udGFjdHMyKHBlb3BsZVRvVXBzZXJ0MiBhcyBQZXJzb25UeXBlW10sIHVzZXJJZCk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgYXdhaXQgdXBzZXJ0Q29udGFjdHMyKHBlb3BsZVRvVXBzZXJ0IGFzIFBlcnNvblR5cGVbXSwgdXNlcklkKTtcbiAgICB9XG5cbiAgICBpZiAocGFnZVRva2VuKSB7XG4gICAgICB3aGlsZSAocGFnZVRva2VuKSB7XG4gICAgICAgIGNvbnN0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgICAgIC8vIE9wdGlvbmFsLiBUaGUgbnVtYmVyIG9mIGNvbm5lY3Rpb25zIHRvIGluY2x1ZGUgaW4gdGhlIHJlc3BvbnNlLiBWYWxpZCB2YWx1ZXMgYXJlIGJldHdlZW4gMSBhbmQgMTAwMCwgaW5jbHVzaXZlLiBEZWZhdWx0cyB0byAxMDAgaWYgbm90IHNldCBvciBzZXQgdG8gMC5cbiAgICAgICAgICBwYWdlU2l6ZTogMTAwMCxcbiAgICAgICAgICAvLyBPcHRpb25hbC4gQSBwYWdlIHRva2VuLCByZWNlaXZlZCBmcm9tIGEgcHJldmlvdXMgcmVzcG9uc2UgYG5leHRfcGFnZV90b2tlbmAuIFByb3ZpZGUgdGhpcyB0byByZXRyaWV2ZSB0aGUgc3Vic2VxdWVudCBwYWdlLiBXaGVuIHBhZ2luYXRpbmcsIGFsbCBvdGhlciBwYXJhbWV0ZXJzIHByb3ZpZGVkIHRvIGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAgbXVzdCBtYXRjaCB0aGUgZmlyc3QgY2FsbCB0aGF0IHByb3ZpZGVkIHRoZSBwYWdlIHRva2VuLlxuICAgICAgICAgIHBhZ2VUb2tlbixcbiAgICAgICAgICAvLyBSZXF1aXJlZC4gQSBmaWVsZCBtYXNrIHRvIHJlc3RyaWN0IHdoaWNoIGZpZWxkcyBvbiBlYWNoIHBlcnNvbiBhcmUgcmV0dXJuZWQuIE11bHRpcGxlIGZpZWxkcyBjYW4gYmUgc3BlY2lmaWVkIGJ5IHNlcGFyYXRpbmcgdGhlbSB3aXRoIGNvbW1hcy4gVmFsaWQgdmFsdWVzIGFyZTogKiBhZGRyZXNzZXMgKiBhZ2VSYW5nZXMgKiBiaW9ncmFwaGllcyAqIGJpcnRoZGF5cyAqIGNhbGVuZGFyVXJscyAqIGNsaWVudERhdGEgKiBjb3ZlclBob3RvcyAqIGVtYWlsQWRkcmVzc2VzICogZXZlbnRzICogZXh0ZXJuYWxJZHMgKiBnZW5kZXJzICogaW1DbGllbnRzICogaW50ZXJlc3RzICogbG9jYWxlcyAqIGxvY2F0aW9ucyAqIG1lbWJlcnNoaXBzICogbWV0YWRhdGEgKiBtaXNjS2V5d29yZHMgKiBuYW1lcyAqIG5pY2tuYW1lcyAqIG9jY3VwYXRpb25zICogb3JnYW5pemF0aW9ucyAqIHBob25lTnVtYmVycyAqIHBob3RvcyAqIHJlbGF0aW9ucyAqIHNpcEFkZHJlc3NlcyAqIHNraWxscyAqIHVybHMgKiB1c2VyRGVmaW5lZFxuICAgICAgICAgIHBlcnNvbkZpZWxkczpcbiAgICAgICAgICAgICduYW1lcyxuaWNrbmFtZXMsb3JnYW5pemF0aW9ucyxiaW9ncmFwaGllcyxjb3ZlclBob3RvcyxtZXRhZGF0YSxlbWFpbEFkZHJlc3NlcyxpbUNsaWVudHMsdXJscycsXG4gICAgICAgICAgLy8gUmVxdWlyZWQuIENvbW1hLXNlcGFyYXRlZCBsaXN0IG9mIHBlcnNvbiBmaWVsZHMgdG8gYmUgaW5jbHVkZWQgaW4gdGhlIHJlc3BvbnNlLiBFYWNoIHBhdGggc2hvdWxkIHN0YXJ0IHdpdGggYHBlcnNvbi5gOiBmb3IgZXhhbXBsZSwgYHBlcnNvbi5uYW1lc2Agb3IgYHBlcnNvbi5waG90b3NgLlxuICAgICAgICAgIC8vICdyZXF1ZXN0TWFzay5pbmNsdWRlRmllbGQnOiAncGVyc29uLm5hbWVzLHBlcnNvbi5uaWNrbmFtZXMscGVyc29uLm9yZ2FuaXphdGlvbnMscGVyc29uLmJpb2dyYXBoaWVzLHBlcnNvbi5jb3ZlclBob3RvcyxwZXJzb24ubWV0YWRhdGEscGVyc29uLmVtYWlsQWRkcmVzc2VzLHBlcnNvbi5pbUNsaWVudHMscGVyc29uLnVybHMnLFxuICAgICAgICAgIC8vIE9wdGlvbmFsLiBXaGV0aGVyIHRoZSByZXNwb25zZSBzaG91bGQgcmV0dXJuIGBuZXh0X3N5bmNfdG9rZW5gIG9uIHRoZSBsYXN0IHBhZ2Ugb2YgcmVzdWx0cy4gSXQgY2FuIGJlIHVzZWQgdG8gZ2V0IGluY3JlbWVudGFsIGNoYW5nZXMgc2luY2UgdGhlIGxhc3QgcmVxdWVzdCBieSBzZXR0aW5nIGl0IG9uIHRoZSByZXF1ZXN0IGBzeW5jX3Rva2VuYC4gTW9yZSBkZXRhaWxzIGFib3V0IHN5bmMgYmVoYXZpb3IgYXQgYHBlb3BsZS5jb25uZWN0aW9ucy5saXN0YC5cbiAgICAgICAgICByZXF1ZXN0U3luY1Rva2VuOiB0cnVlLFxuICAgICAgICAgIC8vIFJlcXVpcmVkLiBUaGUgcmVzb3VyY2UgbmFtZSB0byByZXR1cm4gY29ubmVjdGlvbnMgZm9yLiBPbmx5IGBwZW9wbGUvbWVgIGlzIHZhbGlkLlxuICAgICAgICAgIHJlc291cmNlTmFtZTogJ3Blb3BsZS9tZScsXG4gICAgICAgIH07XG5cbiAgICAgICAgaWYgKHN5bmNUb2tlbikge1xuICAgICAgICAgIHZhcmlhYmxlcy5zeW5jVG9rZW4gPSBzeW5jVG9rZW47XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVQZW9wbGUucGVvcGxlLmNvbm5lY3Rpb25zLmxpc3QodmFyaWFibGVzKTtcbiAgICAgICAgY29uc29sZS5sb2cocmVzLmRhdGEpO1xuXG4gICAgICAgIGNvbnN0IHsgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuXG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGNvbm5lY3Rpb25zLFxuICAgICAgICAgIG5leHRQYWdlVG9rZW4sXG4gICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICBwYWdlVG9rZW4sXG4gICAgICAgICAgJyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiwgcGFnZVRva2VuIGluc2lkZSBpbmNyZW1lbnRhbEdvb2dsZUNvbnRhY3RzU3luYzIgcGFydCBvZiB3aGlsZSBsb29wJ1xuICAgICAgICApO1xuXG4gICAgICAgIGxvY2FsQ29ubmVjdGlvbnMgPSBjb25uZWN0aW9ucztcbiAgICAgICAgcGFnZVRva2VuID0gbmV4dFBhZ2VUb2tlbjtcbiAgICAgICAgc3luY1Rva2VuID0gbmV4dFN5bmNUb2tlbjtcbiAgICAgICAgLy8gdG9rZW5zIGluIGNhc2Ugc29tZXRoaW5nIGdvZXMgd3JvbmdcbiAgICAgICAgLy8gdXBkYXRlIHBhZ2VUb2tlbiBhbmQgc3luY1Rva2VuXG5cbiAgICAgICAgYXdhaXQgdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24oXG4gICAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgbmV4dFBhZ2VUb2tlblxuICAgICAgICApO1xuXG4gICAgICAgIGNvbnN0IGRlbGV0ZWRQZW9wbGUgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkID09PSB0cnVlXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKGRlbGV0ZWRQZW9wbGU/LlswXT8ubmFtZXMpIHtcbiAgICAgICAgICBhd2FpdCBkZWxldGVDb250YWN0cyhkZWxldGVkUGVvcGxlIGFzIFBlcnNvblR5cGVbXSk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBwZW9wbGVUb1Vwc2VydCA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgIT09IHRydWVcbiAgICAgICAgKTtcblxuICAgICAgICAvLyBubyBldmVudHMgdG8gdXBzZXJ0IGNoZWNrIG5leHQgcGFnZXRva2VuXG4gICAgICAgIGlmICghKHBlb3BsZVRvVXBzZXJ0Py5bMF0/Lm5hbWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKCdubyBldmVudHMgdG8gdXBzZXJ0IGNoZWNrIG5leHQgcGFnZXRva2VuJyk7XG4gICAgICAgICAgY29uc3QgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICAgICAgICAvLyBPcHRpb25hbC4gVGhlIG51bWJlciBvZiBjb25uZWN0aW9ucyB0byBpbmNsdWRlIGluIHRoZSByZXNwb25zZS4gVmFsaWQgdmFsdWVzIGFyZSBiZXR3ZWVuIDEgYW5kIDEwMDAsIGluY2x1c2l2ZS4gRGVmYXVsdHMgdG8gMTAwIGlmIG5vdCBzZXQgb3Igc2V0IHRvIDAuXG4gICAgICAgICAgICBwYWdlU2l6ZTogMTAwMCxcbiAgICAgICAgICAgIC8vIE9wdGlvbmFsLiBBIHBhZ2UgdG9rZW4sIHJlY2VpdmVkIGZyb20gYSBwcmV2aW91cyByZXNwb25zZSBgbmV4dF9wYWdlX3Rva2VuYC4gUHJvdmlkZSB0aGlzIHRvIHJldHJpZXZlIHRoZSBzdWJzZXF1ZW50IHBhZ2UuIFdoZW4gcGFnaW5hdGluZywgYWxsIG90aGVyIHBhcmFtZXRlcnMgcHJvdmlkZWQgdG8gYHBlb3BsZS5jb25uZWN0aW9ucy5saXN0YCBtdXN0IG1hdGNoIHRoZSBmaXJzdCBjYWxsIHRoYXQgcHJvdmlkZWQgdGhlIHBhZ2UgdG9rZW4uXG4gICAgICAgICAgICAvLyBSZXF1aXJlZC4gQSBmaWVsZCBtYXNrIHRvIHJlc3RyaWN0IHdoaWNoIGZpZWxkcyBvbiBlYWNoIHBlcnNvbiBhcmUgcmV0dXJuZWQuIE11bHRpcGxlIGZpZWxkcyBjYW4gYmUgc3BlY2lmaWVkIGJ5IHNlcGFyYXRpbmcgdGhlbSB3aXRoIGNvbW1hcy4gVmFsaWQgdmFsdWVzIGFyZTogKiBhZGRyZXNzZXMgKiBhZ2VSYW5nZXMgKiBiaW9ncmFwaGllcyAqIGJpcnRoZGF5cyAqIGNhbGVuZGFyVXJscyAqIGNsaWVudERhdGEgKiBjb3ZlclBob3RvcyAqIGVtYWlsQWRkcmVzc2VzICogZXZlbnRzICogZXh0ZXJuYWxJZHMgKiBnZW5kZXJzICogaW1DbGllbnRzICogaW50ZXJlc3RzICogbG9jYWxlcyAqIGxvY2F0aW9ucyAqIG1lbWJlcnNoaXBzICogbWV0YWRhdGEgKiBtaXNjS2V5d29yZHMgKiBuYW1lcyAqIG5pY2tuYW1lcyAqIG9jY3VwYXRpb25zICogb3JnYW5pemF0aW9ucyAqIHBob25lTnVtYmVycyAqIHBob3RvcyAqIHJlbGF0aW9ucyAqIHNpcEFkZHJlc3NlcyAqIHNraWxscyAqIHVybHMgKiB1c2VyRGVmaW5lZFxuICAgICAgICAgICAgcGVyc29uRmllbGRzOlxuICAgICAgICAgICAgICAnbmFtZXMsbmlja25hbWVzLG9yZ2FuaXphdGlvbnMsYmlvZ3JhcGhpZXMsY292ZXJQaG90b3MsbWV0YWRhdGEsZW1haWxBZGRyZXNzZXMsaW1DbGllbnRzLHVybHMnLFxuICAgICAgICAgICAgLy8gUmVxdWlyZWQuIENvbW1hLXNlcGFyYXRlZCBsaXN0IG9mIHBlcnNvbiBmaWVsZHMgdG8gYmUgaW5jbHVkZWQgaW4gdGhlIHJlc3BvbnNlLiBFYWNoIHBhdGggc2hvdWxkIHN0YXJ0IHdpdGggYHBlcnNvbi5gOiBmb3IgZXhhbXBsZSwgYHBlcnNvbi5uYW1lc2Agb3IgYHBlcnNvbi5waG90b3NgLlxuICAgICAgICAgICAgLy8gJ3JlcXVlc3RNYXNrLmluY2x1ZGVGaWVsZCc6ICdwZXJzb24ubmFtZXMscGVyc29uLm5pY2tuYW1lcyxwZXJzb24ub3JnYW5pemF0aW9ucyxwZXJzb24uYmlvZ3JhcGhpZXMscGVyc29uLmNvdmVyUGhvdG9zLHBlcnNvbi5tZXRhZGF0YSxwZXJzb24uZW1haWxBZGRyZXNzZXMscGVyc29uLmltQ2xpZW50cyxwZXJzb24udXJscycsXG4gICAgICAgICAgICAvLyBPcHRpb25hbC4gV2hldGhlciB0aGUgcmVzcG9uc2Ugc2hvdWxkIHJldHVybiBgbmV4dF9zeW5jX3Rva2VuYCBvbiB0aGUgbGFzdCBwYWdlIG9mIHJlc3VsdHMuIEl0IGNhbiBiZSB1c2VkIHRvIGdldCBpbmNyZW1lbnRhbCBjaGFuZ2VzIHNpbmNlIHRoZSBsYXN0IHJlcXVlc3QgYnkgc2V0dGluZyBpdCBvbiB0aGUgcmVxdWVzdCBgc3luY190b2tlbmAuIE1vcmUgZGV0YWlscyBhYm91dCBzeW5jIGJlaGF2aW9yIGF0IGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAuXG4gICAgICAgICAgICByZXF1ZXN0U3luY1Rva2VuOiB0cnVlLFxuICAgICAgICAgICAgLy8gUmVxdWlyZWQuIFRoZSByZXNvdXJjZSBuYW1lIHRvIHJldHVybiBjb25uZWN0aW9ucyBmb3IuIE9ubHkgYHBlb3BsZS9tZWAgaXMgdmFsaWQuXG4gICAgICAgICAgICByZXNvdXJjZU5hbWU6ICdwZW9wbGUvbWUnLFxuICAgICAgICAgIH07XG5cbiAgICAgICAgICBpZiAoc3luY1Rva2VuKSB7XG4gICAgICAgICAgICB2YXJpYWJsZXMuc3luY1Rva2VuID0gc3luY1Rva2VuO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChwYWdlVG9rZW4pIHtcbiAgICAgICAgICAgIHZhcmlhYmxlcy5wYWdlVG9rZW4gPSBwYWdlVG9rZW47XG4gICAgICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVQZW9wbGUucGVvcGxlLmNvbm5lY3Rpb25zLmxpc3QodmFyaWFibGVzKTtcblxuICAgICAgICAgICAgY29uc3QgeyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG5cbiAgICAgICAgICAgIGxvY2FsQ29ubmVjdGlvbnMgPSBjb25uZWN0aW9ucztcbiAgICAgICAgICAgIHBhZ2VUb2tlbiA9IG5leHRQYWdlVG9rZW47XG4gICAgICAgICAgICBzeW5jVG9rZW4gPSBuZXh0U3luY1Rva2VuO1xuICAgICAgICAgICAgLy8gdG9rZW5zIGluIGNhc2Ugc29tZXRoaW5nIGdvZXMgd3JvbmdcbiAgICAgICAgICAgIC8vIHVwZGF0ZSBwYWdlVG9rZW4gYW5kIHN5bmNUb2tlblxuICAgICAgICAgICAgYXdhaXQgdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24oXG4gICAgICAgICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICAgICAgbmV4dFBhZ2VUb2tlblxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGNvbnN0IGRlbGV0ZWRQZW9wbGUgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCA9PT0gdHJ1ZVxuICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgaWYgKGRlbGV0ZWRQZW9wbGU/LlswXT8ubmFtZXM/LlswXSkge1xuICAgICAgICAgICAgICBhd2FpdCBkZWxldGVDb250YWN0cyhkZWxldGVkUGVvcGxlIGFzIFBlcnNvblR5cGVbXSk7XG4gICAgICAgICAgICB9XG5cbiAgICAgICAgICAgIGNvbnN0IHBlb3BsZVRvVXBzZXJ0MiA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgICAgICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkICE9PSB0cnVlXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgaWYgKHBlb3BsZVRvVXBzZXJ0Mj8uWzBdPy5uYW1lcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICBhd2FpdCB1cHNlcnRDb250YWN0czIocGVvcGxlVG9VcHNlcnQyIGFzIFBlcnNvblR5cGVbXSwgdXNlcklkKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cbiAgICAgICAgYXdhaXQgdXBzZXJ0Q29udGFjdHMyKHBlb3BsZVRvVXBzZXJ0IGFzIFBlcnNvblR5cGVbXSwgdXNlcklkKTtcbiAgICAgIH1cbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBpbmNyZW1lbnRhbCBnb29nbGUgc3luYycpO1xuICAgIC8vIHJlc2V0IHN5bmNcbiAgICBpZiAoZS5jb2RlID09PSA0MTApIHtcbiAgICAgIGF3YWl0IHJlc2V0R29vZ2xlSW50ZWdyYXRpb25TeW5jRm9yQ29udGFjdHMoXG4gICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgdXNlcklkXG4gICAgICApO1xuICAgICAgcmV0dXJuIHRydWU7XG4gICAgfVxuICAgIHJldHVybiBmYWxzZTtcbiAgfVxufTtcblxuY29uc3QgaW5pdGlhbEdvb2dsZUNvbnRhY3RzU3luYzIgPSBhc3luYyAoXG4gIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY2xpZW50VHlwZTogJ2lvcycgfCAnYW5kcm9pZCcgfCAnd2ViJyB8ICdhdG9taWMtd2ViJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IGxvY2FsQ29ubmVjdGlvbnM6IFBlcnNvblR5cGVbXSB8IG9iamVjdCA9IHt9O1xuICAgIGxldCBwYWdlVG9rZW4gPSAnJztcbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IGdldEdvb2dsZUFQSVRva2VuKFxuICAgICAgdXNlcklkLFxuICAgICAgZ29vZ2xlUGVvcGxlUmVzb3VyY2UsXG4gICAgICBjbGllbnRUeXBlXG4gICAgKTtcblxuICAgIGNvbnN0IGdvb2dsZVBlb3BsZSA9IGdvb2dsZS5wZW9wbGUoe1xuICAgICAgdmVyc2lvbjogJ3YxJyxcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3Rva2VufWAsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlUGVvcGxlLnBlb3BsZS5jb25uZWN0aW9ucy5saXN0KHtcbiAgICAgIC8vIE9wdGlvbmFsLiBUaGUgbnVtYmVyIG9mIGNvbm5lY3Rpb25zIHRvIGluY2x1ZGUgaW4gdGhlIHJlc3BvbnNlLiBWYWxpZCB2YWx1ZXMgYXJlIGJldHdlZW4gMSBhbmQgMTAwMCwgaW5jbHVzaXZlLiBEZWZhdWx0cyB0byAxMDAgaWYgbm90IHNldCBvciBzZXQgdG8gMC5cbiAgICAgIHBhZ2VTaXplOiAxMDAwLFxuICAgICAgLy8gUmVxdWlyZWQuIEEgZmllbGQgbWFzayB0byByZXN0cmljdCB3aGljaCBmaWVsZHMgb24gZWFjaCBwZXJzb24gYXJlIHJldHVybmVkLiBNdWx0aXBsZSBmaWVsZHMgY2FuIGJlIHNwZWNpZmllZCBieSBzZXBhcmF0aW5nIHRoZW0gd2l0aCBjb21tYXMuIFZhbGlkIHZhbHVlcyBhcmU6ICogYWRkcmVzc2VzICogYWdlUmFuZ2VzICogYmlvZ3JhcGhpZXMgKiBiaXJ0aGRheXMgKiBjYWxlbmRhclVybHMgKiBjbGllbnREYXRhICogY292ZXJQaG90b3MgKiBlbWFpbEFkZHJlc3NlcyAqIGV2ZW50cyAqIGV4dGVybmFsSWRzICogZ2VuZGVycyAqIGltQ2xpZW50cyAqIGludGVyZXN0cyAqIGxvY2FsZXMgKiBsb2NhdGlvbnMgKiBtZW1iZXJzaGlwcyAqIG1ldGFkYXRhICogbWlzY0tleXdvcmRzICogbmFtZXMgKiBuaWNrbmFtZXMgKiBvY2N1cGF0aW9ucyAqIG9yZ2FuaXphdGlvbnMgKiBwaG9uZU51bWJlcnMgKiBwaG90b3MgKiByZWxhdGlvbnMgKiBzaXBBZGRyZXNzZXMgKiBza2lsbHMgKiB1cmxzICogdXNlckRlZmluZWRcbiAgICAgIHBlcnNvbkZpZWxkczpcbiAgICAgICAgJ25hbWVzLG5pY2tuYW1lcyxvcmdhbml6YXRpb25zLGJpb2dyYXBoaWVzLGNvdmVyUGhvdG9zLG1ldGFkYXRhLGVtYWlsQWRkcmVzc2VzLGltQ2xpZW50cyx1cmxzJyxcbiAgICAgIC8vIFJlcXVpcmVkLiBDb21tYS1zZXBhcmF0ZWQgbGlzdCBvZiBwZXJzb24gZmllbGRzIHRvIGJlIGluY2x1ZGVkIGluIHRoZSByZXNwb25zZS4gRWFjaCBwYXRoIHNob3VsZCBzdGFydCB3aXRoIGBwZXJzb24uYDogZm9yIGV4YW1wbGUsIGBwZXJzb24ubmFtZXNgIG9yIGBwZXJzb24ucGhvdG9zYC5cbiAgICAgIC8vICdyZXF1ZXN0TWFzay5pbmNsdWRlRmllbGQnOiAncGVyc29uLm5hbWVzLHBlcnNvbi5uaWNrbmFtZXMscGVyc29uLm9yZ2FuaXphdGlvbnMscGVyc29uLmJpb2dyYXBoaWVzLHBlcnNvbi5jb3ZlclBob3RvcyxwZXJzb24ubWV0YWRhdGEscGVyc29uLmVtYWlsQWRkcmVzc2VzLHBlcnNvbi5pbUNsaWVudHMscGVyc29uLnVybHMnLFxuICAgICAgLy8gT3B0aW9uYWwuIFdoZXRoZXIgdGhlIHJlc3BvbnNlIHNob3VsZCByZXR1cm4gYG5leHRfc3luY190b2tlbmAgb24gdGhlIGxhc3QgcGFnZSBvZiByZXN1bHRzLiBJdCBjYW4gYmUgdXNlZCB0byBnZXQgaW5jcmVtZW50YWwgY2hhbmdlcyBzaW5jZSB0aGUgbGFzdCByZXF1ZXN0IGJ5IHNldHRpbmcgaXQgb24gdGhlIHJlcXVlc3QgYHN5bmNfdG9rZW5gLiBNb3JlIGRldGFpbHMgYWJvdXQgc3luYyBiZWhhdmlvciBhdCBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgLlxuICAgICAgcmVxdWVzdFN5bmNUb2tlbjogdHJ1ZSxcbiAgICAgIC8vIFJlcXVpcmVkLiBUaGUgcmVzb3VyY2UgbmFtZSB0byByZXR1cm4gY29ubmVjdGlvbnMgZm9yLiBPbmx5IGBwZW9wbGUvbWVgIGlzIHZhbGlkLlxuICAgICAgcmVzb3VyY2VOYW1lOiAncGVvcGxlL21lJyxcbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhyZXMuZGF0YSk7XG4gICAgLy8gRXhhbXBsZSByZXNwb25zZVxuICAgIC8vIHtcbiAgICAvLyAgICZxdW90O2Nvbm5lY3Rpb25zJnF1b3Q7OiBbXSxcbiAgICAvLyAgICZxdW90O25leHRQYWdlVG9rZW4mcXVvdDs6ICZxdW90O215X25leHRQYWdlVG9rZW4mcXVvdDssXG4gICAgLy8gICAmcXVvdDtuZXh0U3luY1Rva2VuJnF1b3Q7OiAmcXVvdDtteV9uZXh0U3luY1Rva2VuJnF1b3Q7LFxuICAgIC8vICAgJnF1b3Q7dG90YWxJdGVtcyZxdW90OzogMCxcbiAgICAvLyAgICZxdW90O3RvdGFsUGVvcGxlJnF1b3Q7OiAwXG4gICAgLy8gfVxuXG4gICAgY29uc3QgeyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBjb25uZWN0aW9ucyxcbiAgICAgIG5leHRQYWdlVG9rZW4sXG4gICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgJyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiBpbnNpZGUgaW5pdGlhbEdvb2dsZUNvbnRhY3RzU3luYzInXG4gICAgKTtcbiAgICBsb2NhbENvbm5lY3Rpb25zID0gY29ubmVjdGlvbnM7XG4gICAgcGFnZVRva2VuID0gbmV4dFBhZ2VUb2tlbjtcblxuICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUludGVncmF0aW9uKFxuICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgIG5leHRQYWdlVG9rZW5cbiAgICApO1xuXG4gICAgY29uc3QgZGVsZXRlZFBlb3BsZSA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCA9PT0gdHJ1ZVxuICAgICk7XG5cbiAgICBpZiAoZGVsZXRlZFBlb3BsZT8uWzBdPy5uYW1lcykge1xuICAgICAgYXdhaXQgZGVsZXRlQ29udGFjdHMoZGVsZXRlZFBlb3BsZSBhcyBQZXJzb25UeXBlW10pO1xuICAgIH1cblxuICAgIGNvbnN0IHBlb3BsZVRvVXBzZXJ0ID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkICE9PSB0cnVlXG4gICAgKTtcblxuICAgIC8vIG5vIGV2ZW50cyB0byB1cHNlcnQgY2hlY2sgbmV4dCBwYWdldG9rZW5cbiAgICBpZiAoIShwZW9wbGVUb1Vwc2VydD8uWzBdPy5uYW1lcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyBldmVudHMgdG8gdXBzZXJ0IGNoZWNrIG5leHQgcGFnZXRva2VuJyk7XG4gICAgICBjb25zdCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgICAgLy8gT3B0aW9uYWwuIFRoZSBudW1iZXIgb2YgY29ubmVjdGlvbnMgdG8gaW5jbHVkZSBpbiB0aGUgcmVzcG9uc2UuIFZhbGlkIHZhbHVlcyBhcmUgYmV0d2VlbiAxIGFuZCAxMDAwLCBpbmNsdXNpdmUuIERlZmF1bHRzIHRvIDEwMCBpZiBub3Qgc2V0IG9yIHNldCB0byAwLlxuICAgICAgICBwYWdlU2l6ZTogMTAwMCxcbiAgICAgICAgLy8gUmVxdWlyZWQuIEEgZmllbGQgbWFzayB0byByZXN0cmljdCB3aGljaCBmaWVsZHMgb24gZWFjaCBwZXJzb24gYXJlIHJldHVybmVkLiBNdWx0aXBsZSBmaWVsZHMgY2FuIGJlIHNwZWNpZmllZCBieSBzZXBhcmF0aW5nIHRoZW0gd2l0aCBjb21tYXMuIFZhbGlkIHZhbHVlcyBhcmU6ICogYWRkcmVzc2VzICogYWdlUmFuZ2VzICogYmlvZ3JhcGhpZXMgKiBiaXJ0aGRheXMgKiBjYWxlbmRhclVybHMgKiBjbGllbnREYXRhICogY292ZXJQaG90b3MgKiBlbWFpbEFkZHJlc3NlcyAqIGV2ZW50cyAqIGV4dGVybmFsSWRzICogZ2VuZGVycyAqIGltQ2xpZW50cyAqIGludGVyZXN0cyAqIGxvY2FsZXMgKiBsb2NhdGlvbnMgKiBtZW1iZXJzaGlwcyAqIG1ldGFkYXRhICogbWlzY0tleXdvcmRzICogbmFtZXMgKiBuaWNrbmFtZXMgKiBvY2N1cGF0aW9ucyAqIG9yZ2FuaXphdGlvbnMgKiBwaG9uZU51bWJlcnMgKiBwaG90b3MgKiByZWxhdGlvbnMgKiBzaXBBZGRyZXNzZXMgKiBza2lsbHMgKiB1cmxzICogdXNlckRlZmluZWRcbiAgICAgICAgcGVyc29uRmllbGRzOlxuICAgICAgICAgICduYW1lcyxuaWNrbmFtZXMsb3JnYW5pemF0aW9ucyxiaW9ncmFwaGllcyxjb3ZlclBob3RvcyxtZXRhZGF0YSxlbWFpbEFkZHJlc3NlcyxpbUNsaWVudHMsdXJscycsXG4gICAgICAgIC8vIFJlcXVpcmVkLiBDb21tYS1zZXBhcmF0ZWQgbGlzdCBvZiBwZXJzb24gZmllbGRzIHRvIGJlIGluY2x1ZGVkIGluIHRoZSByZXNwb25zZS4gRWFjaCBwYXRoIHNob3VsZCBzdGFydCB3aXRoIGBwZXJzb24uYDogZm9yIGV4YW1wbGUsIGBwZXJzb24ubmFtZXNgIG9yIGBwZXJzb24ucGhvdG9zYC5cbiAgICAgICAgLy8gJ3JlcXVlc3RNYXNrLmluY2x1ZGVGaWVsZCc6ICdwZXJzb24ubmFtZXMscGVyc29uLm5pY2tuYW1lcyxwZXJzb24ub3JnYW5pemF0aW9ucyxwZXJzb24uYmlvZ3JhcGhpZXMscGVyc29uLmNvdmVyUGhvdG9zLHBlcnNvbi5tZXRhZGF0YSxwZXJzb24uZW1haWxBZGRyZXNzZXMscGVyc29uLmltQ2xpZW50cyxwZXJzb24udXJscycsXG4gICAgICAgIC8vIFJlcXVpcmVkLiBUaGUgcmVzb3VyY2UgbmFtZSB0byByZXR1cm4gY29ubmVjdGlvbnMgZm9yLiBPbmx5IGBwZW9wbGUvbWVgIGlzIHZhbGlkLlxuICAgICAgICByZXNvdXJjZU5hbWU6ICdwZW9wbGUvbWUnLFxuICAgICAgfTtcblxuICAgICAgaWYgKHBhZ2VUb2tlbikge1xuICAgICAgICB2YXJpYWJsZXMucGFnZVRva2VuID0gcGFnZVRva2VuO1xuICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVQZW9wbGUucGVvcGxlLmNvbm5lY3Rpb25zLmxpc3QodmFyaWFibGVzKTtcbiAgICAgICAgY29uc29sZS5sb2cocmVzLmRhdGEpO1xuICAgICAgICAvLyBFeGFtcGxlIHJlc3BvbnNlXG4gICAgICAgIC8vIHtcbiAgICAgICAgLy8gICAmcXVvdDtjb25uZWN0aW9ucyZxdW90OzogW10sXG4gICAgICAgIC8vICAgJnF1b3Q7bmV4dFBhZ2VUb2tlbiZxdW90OzogJnF1b3Q7bXlfbmV4dFBhZ2VUb2tlbiZxdW90OyxcbiAgICAgICAgLy8gICAmcXVvdDtuZXh0U3luY1Rva2VuJnF1b3Q7OiAmcXVvdDtteV9uZXh0U3luY1Rva2VuJnF1b3Q7LFxuICAgICAgICAvLyAgICZxdW90O3RvdGFsSXRlbXMmcXVvdDs6IDAsXG4gICAgICAgIC8vICAgJnF1b3Q7dG90YWxQZW9wbGUmcXVvdDs6IDBcbiAgICAgICAgLy8gfVxuXG4gICAgICAgIGNvbnN0IHsgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuXG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGNvbm5lY3Rpb25zLFxuICAgICAgICAgIG5leHRQYWdlVG9rZW4sXG4gICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICBwYWdlVG9rZW4sXG4gICAgICAgICAgJyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiwgcGFnZVRva2VuIGluc2lkZSBpbml0aWFsR29vZ2xlQ29udGFjdHNTeW5jMidcbiAgICAgICAgKTtcblxuICAgICAgICBsb2NhbENvbm5lY3Rpb25zID0gY29ubmVjdGlvbnM7XG4gICAgICAgIHBhZ2VUb2tlbiA9IG5leHRQYWdlVG9rZW47XG4gICAgICAgIC8vIHRva2VucyBpbiBjYXNlIHNvbWV0aGluZyBnb2VzIHdyb25nXG4gICAgICAgIC8vIHVwZGF0ZSBwYWdlVG9rZW4gYW5kIHN5bmNUb2tlblxuXG4gICAgICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUludGVncmF0aW9uKFxuICAgICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgICAgIG5leHRQYWdlVG9rZW5cbiAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBkZWxldGVkUGVvcGxlID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCA9PT0gdHJ1ZVxuICAgICAgICApO1xuXG4gICAgICAgIGlmIChkZWxldGVkUGVvcGxlPy5bMF0/Lm5hbWVzPy5bMF0pIHtcbiAgICAgICAgICBhd2FpdCBkZWxldGVDb250YWN0cyhkZWxldGVkUGVvcGxlIGFzIFBlcnNvblR5cGVbXSk7XG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBwZW9wbGVUb1Vwc2VydDIgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkICE9PSB0cnVlXG4gICAgICAgICk7XG4gICAgICAgIGlmIChwZW9wbGVUb1Vwc2VydDI/LlswXT8ubmFtZXM/LlswXSkge1xuICAgICAgICAgIGF3YWl0IHVwc2VydENvbnRhY3RzMihwZW9wbGVUb1Vwc2VydDIgYXMgUGVyc29uVHlwZVtdLCB1c2VySWQpO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGF3YWl0IHVwc2VydENvbnRhY3RzMihwZW9wbGVUb1Vwc2VydCBhcyBQZXJzb25UeXBlW10sIHVzZXJJZCk7XG4gICAgfVxuICAgIGlmIChwYWdlVG9rZW4pIHtcbiAgICAgIC8vIGZldGNoIGFsbCBwYWdlc1xuICAgICAgd2hpbGUgKHBhZ2VUb2tlbikge1xuICAgICAgICBjb25zdCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgICAgICAvLyBPcHRpb25hbC4gVGhlIG51bWJlciBvZiBjb25uZWN0aW9ucyB0byBpbmNsdWRlIGluIHRoZSByZXNwb25zZS4gVmFsaWQgdmFsdWVzIGFyZSBiZXR3ZWVuIDEgYW5kIDEwMDAsIGluY2x1c2l2ZS4gRGVmYXVsdHMgdG8gMTAwIGlmIG5vdCBzZXQgb3Igc2V0IHRvIDAuXG4gICAgICAgICAgcGFnZVNpemU6IDEwMDAsXG4gICAgICAgICAgLy8gT3B0aW9uYWwuIEEgcGFnZSB0b2tlbiwgcmVjZWl2ZWQgZnJvbSBhIHByZXZpb3VzIHJlc3BvbnNlIGBuZXh0X3BhZ2VfdG9rZW5gLiBQcm92aWRlIHRoaXMgdG8gcmV0cmlldmUgdGhlIHN1YnNlcXVlbnQgcGFnZS4gV2hlbiBwYWdpbmF0aW5nLCBhbGwgb3RoZXIgcGFyYW1ldGVycyBwcm92aWRlZCB0byBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgIG11c3QgbWF0Y2ggdGhlIGZpcnN0IGNhbGwgdGhhdCBwcm92aWRlZCB0aGUgcGFnZSB0b2tlbi5cbiAgICAgICAgICBwYWdlVG9rZW4sXG4gICAgICAgICAgLy8gUmVxdWlyZWQuIEEgZmllbGQgbWFzayB0byByZXN0cmljdCB3aGljaCBmaWVsZHMgb24gZWFjaCBwZXJzb24gYXJlIHJldHVybmVkLiBNdWx0aXBsZSBmaWVsZHMgY2FuIGJlIHNwZWNpZmllZCBieSBzZXBhcmF0aW5nIHRoZW0gd2l0aCBjb21tYXMuIFZhbGlkIHZhbHVlcyBhcmU6ICogYWRkcmVzc2VzICogYWdlUmFuZ2VzICogYmlvZ3JhcGhpZXMgKiBiaXJ0aGRheXMgKiBjYWxlbmRhclVybHMgKiBjbGllbnREYXRhICogY292ZXJQaG90b3MgKiBlbWFpbEFkZHJlc3NlcyAqIGV2ZW50cyAqIGV4dGVybmFsSWRzICogZ2VuZGVycyAqIGltQ2xpZW50cyAqIGludGVyZXN0cyAqIGxvY2FsZXMgKiBsb2NhdGlvbnMgKiBtZW1iZXJzaGlwcyAqIG1ldGFkYXRhICogbWlzY0tleXdvcmRzICogbmFtZXMgKiBuaWNrbmFtZXMgKiBvY2N1cGF0aW9ucyAqIG9yZ2FuaXphdGlvbnMgKiBwaG9uZU51bWJlcnMgKiBwaG90b3MgKiByZWxhdGlvbnMgKiBzaXBBZGRyZXNzZXMgKiBza2lsbHMgKiB1cmxzICogdXNlckRlZmluZWRcbiAgICAgICAgICBwZXJzb25GaWVsZHM6XG4gICAgICAgICAgICAnbmFtZXMsbmlja25hbWVzLG9yZ2FuaXphdGlvbnMsYmlvZ3JhcGhpZXMsY292ZXJQaG90b3MsbWV0YWRhdGEsZW1haWxBZGRyZXNzZXMsaW1DbGllbnRzLHVybHMnLFxuICAgICAgICAgIC8vIFJlcXVpcmVkLiBDb21tYS1zZXBhcmF0ZWQgbGlzdCBvZiBwZXJzb24gZmllbGRzIHRvIGJlIGluY2x1ZGVkIGluIHRoZSByZXNwb25zZS4gRWFjaCBwYXRoIHNob3VsZCBzdGFydCB3aXRoIGBwZXJzb24uYDogZm9yIGV4YW1wbGUsIGBwZXJzb24ubmFtZXNgIG9yIGBwZXJzb24ucGhvdG9zYC5cbiAgICAgICAgICAvLyAvLyAncmVxdWVzdE1hc2suaW5jbHVkZUZpZWxkJzogJ3BlcnNvbi5uYW1lcyxwZXJzb24ubmlja25hbWVzLHBlcnNvbi5vcmdhbml6YXRpb25zLHBlcnNvbi5iaW9ncmFwaGllcyxwZXJzb24uY292ZXJQaG90b3MscGVyc29uLm1ldGFkYXRhLHBlcnNvbi5lbWFpbEFkZHJlc3NlcyxwZXJzb24uaW1DbGllbnRzLHBlcnNvbi51cmxzJyxcbiAgICAgICAgICAvLyBPcHRpb25hbC4gV2hldGhlciB0aGUgcmVzcG9uc2Ugc2hvdWxkIHJldHVybiBgbmV4dF9zeW5jX3Rva2VuYCBvbiB0aGUgbGFzdCBwYWdlIG9mIHJlc3VsdHMuIEl0IGNhbiBiZSB1c2VkIHRvIGdldCBpbmNyZW1lbnRhbCBjaGFuZ2VzIHNpbmNlIHRoZSBsYXN0IHJlcXVlc3QgYnkgc2V0dGluZyBpdCBvbiB0aGUgcmVxdWVzdCBgc3luY190b2tlbmAuIE1vcmUgZGV0YWlscyBhYm91dCBzeW5jIGJlaGF2aW9yIGF0IGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAuXG4gICAgICAgICAgcmVxdWVzdFN5bmNUb2tlbjogdHJ1ZSxcbiAgICAgICAgICAvLyBSZXF1aXJlZC4gVGhlIHJlc291cmNlIG5hbWUgdG8gcmV0dXJuIGNvbm5lY3Rpb25zIGZvci4gT25seSBgcGVvcGxlL21lYCBpcyB2YWxpZC5cbiAgICAgICAgICByZXNvdXJjZU5hbWU6ICdwZW9wbGUvbWUnLFxuICAgICAgICB9O1xuICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVQZW9wbGUucGVvcGxlLmNvbm5lY3Rpb25zLmxpc3QodmFyaWFibGVzKTtcbiAgICAgICAgY29uc29sZS5sb2cocmVzLmRhdGEpO1xuICAgICAgICAvLyBFeGFtcGxlIHJlc3BvbnNlXG4gICAgICAgIC8vIHtcbiAgICAgICAgLy8gICAmcXVvdDtjb25uZWN0aW9ucyZxdW90OzogW10sXG4gICAgICAgIC8vICAgJnF1b3Q7bmV4dFBhZ2VUb2tlbiZxdW90OzogJnF1b3Q7bXlfbmV4dFBhZ2VUb2tlbiZxdW90OyxcbiAgICAgICAgLy8gICAmcXVvdDtuZXh0U3luY1Rva2VuJnF1b3Q7OiAmcXVvdDtteV9uZXh0U3luY1Rva2VuJnF1b3Q7LFxuICAgICAgICAvLyAgICZxdW90O3RvdGFsSXRlbXMmcXVvdDs6IDAsXG4gICAgICAgIC8vICAgJnF1b3Q7dG90YWxQZW9wbGUmcXVvdDs6IDBcbiAgICAgICAgLy8gfVxuXG4gICAgICAgIGNvbnN0IHsgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuXG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGNvbm5lY3Rpb25zLFxuICAgICAgICAgIG5leHRQYWdlVG9rZW4sXG4gICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICBwYWdlVG9rZW4sXG4gICAgICAgICAgJyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiwgcGFnZVRva2VuIGluc2lkZSBpbml0aWFsR29vZ2xlQ29udGFjdHNTeW5jMiBwYXJ0IG9mIHdoaWxlIGxvb3AnXG4gICAgICAgICk7XG5cbiAgICAgICAgbG9jYWxDb25uZWN0aW9ucyA9IGNvbm5lY3Rpb25zO1xuICAgICAgICBwYWdlVG9rZW4gPSBuZXh0UGFnZVRva2VuO1xuICAgICAgICAvLyB0b2tlbnMgaW4gY2FzZSBzb21ldGhpbmcgZ29lcyB3cm9uZ1xuICAgICAgICAvLyB1cGRhdGUgcGFnZVRva2VuIGFuZCBzeW5jVG9rZW5cblxuICAgICAgICBhd2FpdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbihcbiAgICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICBuZXh0UGFnZVRva2VuXG4gICAgICAgICk7XG5cbiAgICAgICAgY29uc3QgZGVsZXRlZFBlb3BsZSA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgPT09IHRydWVcbiAgICAgICAgKTtcblxuICAgICAgICBpZiAoZGVsZXRlZFBlb3BsZT8uWzBdPy5uYW1lcz8uWzBdKSB7XG4gICAgICAgICAgYXdhaXQgZGVsZXRlQ29udGFjdHMoZGVsZXRlZFBlb3BsZSBhcyBQZXJzb25UeXBlW10pO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcGVvcGxlVG9VcHNlcnQgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkICE9PSB0cnVlXG4gICAgICAgICk7XG5cbiAgICAgICAgLy8gbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlblxuICAgICAgICBpZiAoIShwZW9wbGVUb1Vwc2VydD8uWzBdPy5uYW1lcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlbicpO1xuICAgICAgICAgIGNvbnN0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgICAgICAgLy8gT3B0aW9uYWwuIFRoZSBudW1iZXIgb2YgY29ubmVjdGlvbnMgdG8gaW5jbHVkZSBpbiB0aGUgcmVzcG9uc2UuIFZhbGlkIHZhbHVlcyBhcmUgYmV0d2VlbiAxIGFuZCAxMDAwLCBpbmNsdXNpdmUuIERlZmF1bHRzIHRvIDEwMCBpZiBub3Qgc2V0IG9yIHNldCB0byAwLlxuICAgICAgICAgICAgcGFnZVNpemU6IDEwMDAsXG4gICAgICAgICAgICAvLyBSZXF1aXJlZC4gQSBmaWVsZCBtYXNrIHRvIHJlc3RyaWN0IHdoaWNoIGZpZWxkcyBvbiBlYWNoIHBlcnNvbiBhcmUgcmV0dXJuZWQuIE11bHRpcGxlIGZpZWxkcyBjYW4gYmUgc3BlY2lmaWVkIGJ5IHNlcGFyYXRpbmcgdGhlbSB3aXRoIGNvbW1hcy4gVmFsaWQgdmFsdWVzIGFyZTogKiBhZGRyZXNzZXMgKiBhZ2VSYW5nZXMgKiBiaW9ncmFwaGllcyAqIGJpcnRoZGF5cyAqIGNhbGVuZGFyVXJscyAqIGNsaWVudERhdGEgKiBjb3ZlclBob3RvcyAqIGVtYWlsQWRkcmVzc2VzICogZXZlbnRzICogZXh0ZXJuYWxJZHMgKiBnZW5kZXJzICogaW1DbGllbnRzICogaW50ZXJlc3RzICogbG9jYWxlcyAqIGxvY2F0aW9ucyAqIG1lbWJlcnNoaXBzICogbWV0YWRhdGEgKiBtaXNjS2V5d29yZHMgKiBuYW1lcyAqIG5pY2tuYW1lcyAqIG9jY3VwYXRpb25zICogb3JnYW5pemF0aW9ucyAqIHBob25lTnVtYmVycyAqIHBob3RvcyAqIHJlbGF0aW9ucyAqIHNpcEFkZHJlc3NlcyAqIHNraWxscyAqIHVybHMgKiB1c2VyRGVmaW5lZFxuICAgICAgICAgICAgcGVyc29uRmllbGRzOlxuICAgICAgICAgICAgICAnbmFtZXMsbmlja25hbWVzLG9yZ2FuaXphdGlvbnMsYmlvZ3JhcGhpZXMsY292ZXJQaG90b3MsbWV0YWRhdGEsZW1haWxBZGRyZXNzZXMsaW1DbGllbnRzLHVybHMnLFxuICAgICAgICAgICAgLy8gUmVxdWlyZWQuIENvbW1hLXNlcGFyYXRlZCBsaXN0IG9mIHBlcnNvbiBmaWVsZHMgdG8gYmUgaW5jbHVkZWQgaW4gdGhlIHJlc3BvbnNlLiBFYWNoIHBhdGggc2hvdWxkIHN0YXJ0IHdpdGggYHBlcnNvbi5gOiBmb3IgZXhhbXBsZSwgYHBlcnNvbi5uYW1lc2Agb3IgYHBlcnNvbi5waG90b3NgLlxuICAgICAgICAgICAgLy8gJ3JlcXVlc3RNYXNrLmluY2x1ZGVGaWVsZCc6ICdwZXJzb24ubmFtZXMscGVyc29uLm5pY2tuYW1lcyxwZXJzb24ub3JnYW5pemF0aW9ucyxwZXJzb24uYmlvZ3JhcGhpZXMscGVyc29uLmNvdmVyUGhvdG9zLHBlcnNvbi5tZXRhZGF0YSxwZXJzb24uZW1haWxBZGRyZXNzZXMscGVyc29uLmltQ2xpZW50cyxwZXJzb24udXJscycsXG4gICAgICAgICAgICAvLyBSZXF1aXJlZC4gVGhlIHJlc291cmNlIG5hbWUgdG8gcmV0dXJuIGNvbm5lY3Rpb25zIGZvci4gT25seSBgcGVvcGxlL21lYCBpcyB2YWxpZC5cbiAgICAgICAgICAgIHJlc291cmNlTmFtZTogJ3Blb3BsZS9tZScsXG4gICAgICAgICAgfTtcblxuICAgICAgICAgIGlmIChwYWdlVG9rZW4pIHtcbiAgICAgICAgICAgIHZhcmlhYmxlcy5wYWdlVG9rZW4gPSBwYWdlVG9rZW47XG4gICAgICAgICAgICBjb25zdCByZXMgPSBhd2FpdCBnb29nbGVQZW9wbGUucGVvcGxlLmNvbm5lY3Rpb25zLmxpc3QodmFyaWFibGVzKTtcbiAgICAgICAgICAgIGNvbnNvbGUubG9nKHJlcy5kYXRhKTtcblxuICAgICAgICAgICAgY29uc3QgeyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiB9ID0gcmVzLmRhdGE7XG5cbiAgICAgICAgICAgIGxvY2FsQ29ubmVjdGlvbnMgPSBjb25uZWN0aW9ucztcbiAgICAgICAgICAgIHBhZ2VUb2tlbiA9IG5leHRQYWdlVG9rZW47XG4gICAgICAgICAgICAvLyB0b2tlbnMgaW4gY2FzZSBzb21ldGhpbmcgZ29lcyB3cm9uZ1xuICAgICAgICAgICAgLy8gdXBkYXRlIHBhZ2VUb2tlbiBhbmQgc3luY1Rva2VuXG5cbiAgICAgICAgICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUludGVncmF0aW9uKFxuICAgICAgICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgICAgIG5leHRQYWdlVG9rZW5cbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBjb25zdCBkZWxldGVkUGVvcGxlID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgPT09IHRydWVcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgIGlmIChkZWxldGVkUGVvcGxlPy5bMF0/Lm5hbWVzPy5bMF0pIHtcbiAgICAgICAgICAgICAgYXdhaXQgZGVsZXRlQ29udGFjdHMoZGVsZXRlZFBlb3BsZSBhcyBQZXJzb25UeXBlW10pO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBjb25zdCBwZW9wbGVUb1Vwc2VydDIgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCAhPT0gdHJ1ZVxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGlmIChwZW9wbGVUb1Vwc2VydDI/LlswXT8ubmFtZXM/LlswXSkge1xuICAgICAgICAgICAgICBhd2FpdCB1cHNlcnRDb250YWN0czIocGVvcGxlVG9VcHNlcnQyIGFzIFBlcnNvblR5cGVbXSwgdXNlcklkKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBhd2FpdCB1cHNlcnRDb250YWN0czIocGVvcGxlVG9VcHNlcnQgYXMgUGVyc29uVHlwZVtdLCB1c2VySWQpO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRvIGluaXRpYWwgZ29vZ2xlIHN5bmMnKTtcbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cbn07XG5cbmNvbnN0IHJlc2V0R29vZ2xlSW50ZWdyYXRpb25TeW5jRm9yQ29udGFjdHMgPSBhc3luYyAoXG4gIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICd1cGRhdGVDYWxlbmRhckludGVncmF0aW9uJztcbiAgICBjb25zdCBxdWVyeSA9IGBtdXRhdGlvbiB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKCRpZDogdXVpZCEsICRjaGFuZ2VzOiBDYWxlbmRhcl9JbnRlZ3JhdGlvbl9zZXRfaW5wdXQpIHtcbiAgICAgIHVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wayhwa19jb2x1bW5zOiB7aWQ6ICRpZH0sIF9zZXQ6ICRjaGFuZ2VzKSB7XG4gICAgICAgIHBhZ2VUb2tlblxuICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgY2xpZW50VHlwZVxuICAgICAgfVxuICAgIH1cbiAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkOiBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICBjaGFuZ2VzOiB7XG4gICAgICAgIHBhZ2VUb2tlbjogbnVsbCxcbiAgICAgICAgc3luY1Rva2VuOiBudWxsLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IHtcbiAgICAgIGRhdGE6IHsgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogYWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIHJlc2V0R29vZ2xlSW50ZWdyYXRpb25TeW5jJyk7XG4gICAgLy8gY29uc3QgeyB0b2tlbjogYXV0aFRva2VuIH0gPSBhd2FpdCBnZXRHb29nbGVJbnRlZ3JhdGlvbihjYWxlbmRhckludGVncmF0aW9uSWQpXG4gICAgcmV0dXJuIGluaXRpYWxHb29nbGVDb250YWN0c1N5bmMyKFxuICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgdXNlcklkLFxuICAgICAgcmVzcG9uc2U/LmRhdGE/LnVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9waz8uY2xpZW50VHlwZVxuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZXNldCBnb29nbGUgaW50ZWdyYXRpb24gc3luYycpO1xuICB9XG59O1xuXG5jb25zdCBnZXRHb29nbGVJbnRlZ3JhdGlvbiA9IGFzeW5jIChjYWxlbmRhckludGVncmF0aW9uSWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbic7XG4gICAgY29uc3QgcXVlcnkgPSBgcXVlcnkgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbigkaWQ6IHV1aWQhKXtcbiAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrKGlkOiAkaWQpIHtcbiAgICAgICAgaWRcbiAgICAgICAgbmFtZVxuICAgICAgICB0b2tlblxuICAgICAgICByZWZyZXNoVG9rZW5cbiAgICAgICAgcGFnZVRva2VuXG4gICAgICAgIHN5bmNUb2tlblxuICAgICAgICBlbmFibGVkXG4gICAgICAgIGNsaWVudFR5cGVcbiAgICAgIH1cbiAgICB9YDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7IGlkOiBjYWxlbmRhckludGVncmF0aW9uSWQgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiB7XG4gICAgICBkYXRhOiB7IENhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogYWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICAvLyBqdXN0IHRvIGNoZWNrXG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgdGhpcyBpcyByZXNwb25zZSBpbiBnZXRHb29nbGVJbnRlZ3JhdGlvbicpO1xuICAgIGlmIChyZXNwb25zZT8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGspIHtcbiAgICAgIGNvbnN0IHtcbiAgICAgICAgZGF0YToge1xuICAgICAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrOiB7XG4gICAgICAgICAgICB0b2tlbixcbiAgICAgICAgICAgIHBhZ2VUb2tlbixcbiAgICAgICAgICAgIHN5bmNUb2tlbixcbiAgICAgICAgICAgIHJlZnJlc2hUb2tlbixcbiAgICAgICAgICAgIGVuYWJsZWQsXG4gICAgICAgICAgICBjbGllbnRUeXBlLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9ID0gcmVzcG9uc2U7XG5cbiAgICAgIHJldHVybiB7IHRva2VuLCBwYWdlVG9rZW4sIHN5bmNUb2tlbiwgcmVmcmVzaFRva2VuLCBlbmFibGVkLCBjbGllbnRUeXBlIH07XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGdvb2dsZSB0b2tlbicpO1xuICB9XG59O1xuXG5jb25zdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbiA9IGFzeW5jIChcbiAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkOiBzdHJpbmcsXG4gIHN5bmNUb2tlbj86IHN0cmluZyxcbiAgcGFnZVRva2VuPzogc3RyaW5nLFxuICBzeW5jRW5hYmxlZD86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAndXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbic7XG4gICAgY29uc3QgcXVlcnkgPSBgbXV0YXRpb24gdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbigkaWQ6IHV1aWQhLCR7c3luY1Rva2VuICE9PSB1bmRlZmluZWQgPyAnICRzeW5jVG9rZW46IFN0cmluZywnIDogJyd9JHtwYWdlVG9rZW4gIT09IHVuZGVmaW5lZCA/ICcgJHBhZ2VUb2tlbjogU3RyaW5nLCcgOiAnJ30ke3N5bmNFbmFibGVkICE9PSB1bmRlZmluZWQgPyAnICRzeW5jRW5hYmxlZDogQm9vbGVhbiwnIDogJyd9KSB7XG4gICAgICAgIHVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wayhwa19jb2x1bW5zOiB7aWQ6ICRpZH0sIF9zZXQ6IHske3BhZ2VUb2tlbiAhPT0gdW5kZWZpbmVkID8gJ3BhZ2VUb2tlbjogJHBhZ2VUb2tlbiwnIDogJyd9ICR7c3luY1Rva2VuICE9PSB1bmRlZmluZWQgPyAnc3luY1Rva2VuOiAkc3luY1Rva2VuLCcgOiAnJ30gJHtzeW5jRW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJ3N5bmNFbmFibGVkOiAkc3luY0VuYWJsZWQsJyA6ICcnfX0pIHtcbiAgICAgICAgICBpZFxuICAgICAgICAgIG5hbWVcbiAgICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgICByZWZyZXNoVG9rZW5cbiAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgIHN5bmNFbmFibGVkXG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICB1c2VySWRcbiAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICBlbmFibGVkXG4gICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgY2xpZW50VHlwZVxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBsZXQgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICBpZDogY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgIH07XG5cbiAgICBpZiAoc3luY1Rva2VuPy5sZW5ndGggPiAwKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7IC4uLnZhcmlhYmxlcywgc3luY1Rva2VuIH07XG4gICAgfVxuXG4gICAgaWYgKHBhZ2VUb2tlbj8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFyaWFibGVzID0geyAuLi52YXJpYWJsZXMsIHBhZ2VUb2tlbiB9O1xuICAgIH1cblxuICAgIGlmIChzeW5jRW5hYmxlZCA9PT0gZmFsc2UpIHtcbiAgICAgIHZhcmlhYmxlcyA9IHsgLi4udmFyaWFibGVzLCBzeW5jRW5hYmxlZCB9O1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIHVwZGF0ZUdvb2dsZUludGVncmF0aW9uJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgZ29vZ2xlIGludGVncmF0aW9uJyk7XG4gIH1cbn07XG5cbmNvbnN0IGhhbmRsZXIgPSBhc3luYyAocmVxOiBSZXF1ZXN0LCByZXM6IFJlc3BvbnNlKSA9PiB7XG4gIHRyeSB7XG4gICAgLyoqXG4gICAgICogaGFzdXJhIHRyaWdnZXIgYm9keTpcbiAgICAgKiB7XG4gICAgICAgIFwic2NoZWR1bGVkX3RpbWVcIjogXCIyMDIyLTA1LTEyVDAwOjQ1OjA5LjQ2N1pcIixcbiAgICAgICAgXCJwYXlsb2FkXCI6IFwie1xcXCJ1c2VySWRcXFwiOiBcXFwiZmM1ZGY2NzQtYjRlZS00M2M3LWFkOWUtMjk4YWUwZWI2MjA4XFxcIiwgXFxcImZpbGVLZXlcXFwiOiBcXFwiZmM1ZGY2NzQtYjRlZS00M2M3LWFkOWUtMjk4YWUwZWI2MjA4LzY1ZjEyNTVlLTAxZTQtNDA1Zi04YTVjLWVmNDIyZmI5NGM0Yi5qc29uXFxcIn1cIiwgLSBzdHJpbmdpZmllZFxuICAgICAgICBcImNyZWF0ZWRfYXRcIjogXCIyMDIyLTA1LTEyVDAwOjQ2OjEwLjg5MDAyOFpcIixcbiAgICAgICAgXCJpZFwiOiBcIjMyNzc4ODAxLThmOGQtNDNjMi1hNzI5LTg2NjMzYjNkNzAxYVwiLFxuICAgICAgICBcImNvbW1lbnRcIjogXCJcIlxuICAgICAgfVxuICAgICAgVlNcbiAgICAgIGF4aW9zIHBvc3QgQm9keSAtIHN0cmluZ2lmaWVkXG4gICAgICB7XG4gICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICAgICAgICB1c2VySWQ6IHN0cmluZyxcbiAgICAgICAgZXZlbnRUcmlnZ2VySWQ6IHN0cmluZyxcbiAgICAgICAgaXNJbml0aWFsU3luYzogYm9vbGVhbixcbiAgICAgIH1cbiAgICAgKi9cbiAgICBjb25zb2xlLmxvZygnZ29vZ2xlUGVvcGxlU3luYyBjYWxsZWQnKTtcbiAgICBsZXQgY2FsZW5kYXJJbnRlZ3JhdGlvbklkID0gJyc7XG4gICAgbGV0IHVzZXJJZCA9ICcnO1xuICAgIGxldCBpc0luaXRpYWxTeW5jID0gZmFsc2U7XG4gICAgY29uc3QgYm9keU9iaiA9IHJlcS5ib2R5O1xuICAgIGlmICh0eXBlb2YgYm9keU9iaj8uc2NoZWR1bGVkX3RpbWUgPT09ICdzdHJpbmcnKSB7XG4gICAgICBjb25zb2xlLmxvZyhib2R5T2JqLCAnIHNjaGVkdWxlZCB0cmlnZ2VyJyk7XG4gICAgICBjb25zdCB7IHBheWxvYWQgfSA9IGJvZHlPYmo7XG4gICAgICBjb25zdCBwYXlsb2FkT2JqID0gSlNPTi5wYXJzZShwYXlsb2FkKTtcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCA9IHBheWxvYWRPYmouY2FsZW5kYXJJbnRlZ3JhdGlvbklkO1xuICAgICAgdXNlcklkID0gcGF5bG9hZE9iai51c2VySWQ7XG4gICAgICBpc0luaXRpYWxTeW5jID0gcGF5bG9hZE9iaj8uaXNJbml0aWFsU3luYyB8fCBmYWxzZTtcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc3QgYm9keSA9IHJlcS5ib2R5O1xuICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkID0gYm9keT8uY2FsZW5kYXJJbnRlZ3JhdGlvbklkO1xuICAgICAgdXNlcklkID0gYm9keT8udXNlcklkO1xuICAgICAgaXNJbml0aWFsU3luYyA9IGJvZHk/LmlzSW5pdGlhbFN5bmM7XG4gICAgfVxuXG4gICAgLy8gdmFsaWRhdGVcbiAgICBpZiAoIWNhbGVuZGFySW50ZWdyYXRpb25JZCB8fCAhdXNlcklkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJyBjYWxlbmRhciBpbnRlZ3JhdGlvbiBpZCBvciB1c2VyIGlkIGlzIGVtcHR5Jyk7XG4gICAgfVxuXG4gICAgY29uc3QgZXZlbnRUcmlnZ2VyID1cbiAgICAgIGF3YWl0IGdldEV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZChnb29nbGVQZW9wbGVSZXNvdXJjZSk7XG5cbiAgICAvLyB2YWxpZGF0ZVxuICAgIGlmICghaXNJbml0aWFsU3luYyAmJiAhZXZlbnRUcmlnZ2VyKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm90IGluaXRpYWwgYW5kIG5vIGV2ZW50VHJpZ2dlciBzbyBkbyBub3RoaW5nJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKGV2ZW50VHJpZ2dlcj8uaWQpIHtcbiAgICAgIGF3YWl0IGRlbGV0ZUV2ZW50VHJpZ2dlckJ5SWQoZXZlbnRUcmlnZ2VyPy5pZCk7XG4gICAgfVxuXG4gICAgbGV0IHN5bmNFbmFibGVkID0gdHJ1ZTtcblxuICAgIGNvbnN0IHsgcGFnZVRva2VuLCBzeW5jVG9rZW4sIGVuYWJsZWQsIGNsaWVudFR5cGUgfSA9XG4gICAgICBhd2FpdCBnZXRHb29nbGVJbnRlZ3JhdGlvbihjYWxlbmRhckludGVncmF0aW9uSWQpO1xuXG4gICAgaWYgKCFlbmFibGVkKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm90IGVuYWJsZWQgZ29vZ2xlIHBlb3BsZSBzeW5jJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuICAgIC8vIGlmIGluaXRpYWwgc3luYyBkbyAxMDAgcmVzdXRzIGVsc2UgMTBcbiAgICBpZiAoaXNJbml0aWFsU3luYykge1xuICAgICAgc3luY0VuYWJsZWQgPSBhd2FpdCBpbml0aWFsR29vZ2xlQ29udGFjdHNTeW5jMihcbiAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNsaWVudFR5cGVcbiAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIHN5bmNFbmFibGVkID0gYXdhaXQgaW5jcmVtZW50YWxHb29nbGVDb250YWN0c1N5bmMyKFxuICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgY2xpZW50VHlwZSxcbiAgICAgICAgc3luY1Rva2VuLFxuICAgICAgICBwYWdlVG9rZW5cbiAgICAgICk7XG4gICAgfVxuXG4gICAgLy8gaWYgc3luYyBpcyBub3QgZW5hYmxlZCBsZXQgdGhlIHVzZXIgZ28gdGhyb3VnaCBvYXV0aCBhZ2FpbiBpZiBuZWVkZWRcbiAgICBpZiAoc3luY0VuYWJsZWQgPT09IGZhbHNlKSB7XG4gICAgICBhd2FpdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbihcbiAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgc3luY0VuYWJsZWRcbiAgICAgICk7XG4gICAgICByZXR1cm4gcmVzLnN0YXR1cygyMDApLmpzb24oe1xuICAgICAgICBtZXNzYWdlOiBgc3luYyBpcyBkaXNhYmxlZCBmb3IgZ29vZ2xlUGVvcGxlU3luY2AsXG4gICAgICAgIGV2ZW50OiBib2R5T2JqLFxuICAgICAgfSk7XG4gICAgfVxuICAgIC8vIHJlY3JlYXRlIHNjaGVkdWxlZCBldmVudCBmb3IgbmV4dCB0aW1lXG4gICAgY29uc3QgcmVzcG9uc2U6IHtcbiAgICAgIG1lc3NhZ2U6IHN0cmluZztcbiAgICAgIGV2ZW50X2lkOiBzdHJpbmc7XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhTWV0YWRhdGFVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBhZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIHR5cGU6ICdjcmVhdGVfc2NoZWR1bGVkX2V2ZW50JyxcbiAgICAgICAgICBhcmdzOiB7XG4gICAgICAgICAgICB3ZWJob29rOiBzZWxmR29vZ2xlUGVvcGxlQWRtaW5VcmwsXG4gICAgICAgICAgICBzY2hlZHVsZV9hdDogZGF5anMoKS5hZGQoMTQsICdkJykudXRjKCkuZm9ybWF0KCksXG4gICAgICAgICAgICBwYXlsb2FkOiBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgfSksXG4gICAgICAgICAgICBoZWFkZXJzOiBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBuYW1lOiAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JyxcbiAgICAgICAgICAgICAgICB2YWx1ZTogYWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBuYW1lOiAnWC1IYXN1cmEtUm9sZScsXG4gICAgICAgICAgICAgICAgdmFsdWU6ICdhZG1pbicsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBuYW1lOiAnQ29udGVudC1UeXBlJyxcbiAgICAgICAgICAgICAgICB2YWx1ZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyBzdWNjZXNzIHJlc3BvbnNlIGluc2lkZSBnb29nbGVQZW9wbGVTeW5jJyk7XG5cbiAgICBhd2FpdCBpbnNlcnRFdmVudFRyaWdnZXJzKFtcbiAgICAgIHtcbiAgICAgICAgaWQ6IHJlc3BvbnNlPy5ldmVudF9pZCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBuYW1lOiBnb29nbGVQZW9wbGVOYW1lLFxuICAgICAgICByZXNvdXJjZTogZ29vZ2xlUGVvcGxlUmVzb3VyY2UsXG4gICAgICAgIHJlc291cmNlSWQ6IGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICBjcmVhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICB9LFxuICAgIF0pO1xuXG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHtcbiAgICAgIG1lc3NhZ2U6IGBzdWNjZXNzZnVsbHkgdGFrZW4gY2FyZSBvZiBnb29nbGVDYWxlbmRhcnlTeW5jIWAsXG4gICAgICBldmVudDogYm9keU9iaixcbiAgICB9KTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHN5bmMgZ29vZ2xlIGNhbGVuZGFyJyk7XG5cbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDApLmpzb24oe1xuICAgICAgbWVzc2FnZTogYGVycm9yIHByb2Nlc3NpbmcgZ29vZ2xlUGVvcGxlU3luYzogbWVzc2FnZTogJHtlPy5tZXNzYWdlfSwgY29kZTogJHtlPy5zdGF0dXNDb2RlfWAsXG4gICAgICBldmVudDogZSxcbiAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==