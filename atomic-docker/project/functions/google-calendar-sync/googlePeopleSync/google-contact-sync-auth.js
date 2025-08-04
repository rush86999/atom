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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ29vZ2xlLWNvbnRhY3Qtc3luYy1hdXRoLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ29vZ2xlLWNvbnRhY3Qtc3luYy1hdXRoLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sR0FBRyxNQUFNLEtBQUssQ0FBQztBQUN0QixPQUFPLEtBQUssTUFBTSxPQUFPLENBQUM7QUFDMUIsT0FBTyxHQUFHLE1BQU0sa0JBQWtCLENBQUM7QUFDbkMsT0FBTyxFQUFFLE1BQU0sRUFBRSxNQUFNLFlBQVksQ0FBQztBQUlwQyxPQUFPLEVBQ0wsZ0JBQWdCLEVBQ2hCLG9CQUFvQixFQUNwQixjQUFjLEVBQ2QsaUJBQWlCLEVBQ2pCLHdCQUF3QixHQUN6QixNQUFNLHVDQUF1QyxDQUFDO0FBRS9DLE9BQU8sRUFDTCxzQkFBc0IsRUFDdEIsMkJBQTJCLEVBQzNCLGlCQUFpQixFQUNqQixtQkFBbUIsR0FDcEIsTUFBTSx3Q0FBd0MsQ0FBQztBQUdoRCxLQUFLLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDO0FBRWxCLE1BQU0sV0FBVyxHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsMkJBQTJCLENBQUM7QUFDNUQsc0RBQXNEO0FBQ3RELDREQUE0RDtBQUM1RCwyRUFBMkU7QUFFM0UsMkNBQTJDO0FBQzNDLE1BQU0sY0FBYyxHQUFHLEtBQUssRUFBRSxNQUFvQixFQUFFLEVBQUU7SUFDcEQsSUFBSSxDQUFDO1FBQ0gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxNQUFNLEVBQUUsK0JBQStCLENBQUMsQ0FBQztRQUNyRCxJQUFJLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxZQUFZLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7WUFDN0MsT0FBTyxDQUFDLEdBQUcsQ0FBQyw4QkFBOEIsQ0FBQyxDQUFDO1lBQzVDLE9BQU87UUFDVCxDQUFDO1FBRUQsTUFBTSxHQUFHLEdBQUcsTUFBTSxFQUFFLEdBQUcsQ0FB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SSxFQUFFLENBQUM7UUFFVixPQUFPLENBQUMsR0FBRyxDQUFDLFFBQVEsRUFBRSwyQ0FBMkMsQ0FBQyxDQUFDO1FBRW5FLE1BQU0sbUJBQW1CLENBQUM7WUFDeEI7Z0JBQ0UsRUFBRSxFQUFFLFFBQVEsRUFBRSxRQUFRO2dCQUN0QixNQUFNO2dCQUNOLElBQUksRUFBRSxnQkFBZ0I7Z0JBQ3RCLFFBQVEsRUFBRSxvQkFBb0I7Z0JBQzlCLFVBQVUsRUFBRSxxQkFBcUI7Z0JBQ2pDLFNBQVMsRUFBRSxLQUFLLEVBQUUsQ0FBQyxNQUFNLEVBQUU7Z0JBQzNCLFNBQVMsRUFBRSxLQUFLLEVBQUUsQ0FBQyxNQUFNLEVBQUU7YUFDNUI7U0FDRixDQUFDLENBQUM7UUFFSCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSxpREFBaUQ7WUFDMUQsS0FBSyxFQUFFLE9BQU87U0FDZixDQUFDLENBQUM7SUFDTCxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDhCQUE4QixDQUFDLENBQUM7UUFFL0MsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixPQUFPLEVBQUUsK0NBQStDLENBQUMsRUFBRSxPQUFPLFdBQVcsQ0FBQyxFQUFFLFVBQVUsRUFBRTtZQUM1RixLQUFLLEVBQUUsQ0FBQztTQUNULENBQUMsQ0FBQztJQUNMLENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixlQUFlLE9BQU8sQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFJlcXVlc3QsIFJlc3BvbnNlIH0gZnJvbSAnZXhwcmVzcyc7XG5pbXBvcnQgZ290IGZyb20gJ2dvdCc7XG5pbXBvcnQgZGF5anMgZnJvbSAnZGF5anMnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcbmltcG9ydCB7IGdvb2dsZSB9IGZyb20gJ2dvb2dsZWFwaXMnO1xuXG5pbXBvcnQgeyBQZXJzb25UeXBlIH0gZnJvbSAnLi4vX2xpYnMvdHlwZXMvZ29vZ2xlUGVvcGxlU3luYy90eXBlcyc7XG5cbmltcG9ydCB7XG4gIGdvb2dsZVBlb3BsZU5hbWUsXG4gIGdvb2dsZVBlb3BsZVJlc291cmNlLFxuICBoYXN1cmFHcmFwaFVybCxcbiAgaGFzdXJhTWV0YWRhdGFVcmwsXG4gIHNlbGZHb29nbGVQZW9wbGVBZG1pblVybCxcbn0gZnJvbSAnQGdvb2dsZV9jYWxlbmRhcl9zeW5jL19saWJzL2NvbnN0YW50cyc7XG5cbmltcG9ydCB7XG4gIGRlbGV0ZUV2ZW50VHJpZ2dlckJ5SWQsXG4gIGdldEV2ZW50VHJpZ2dlckJ5UmVzb3VyY2VJZCxcbiAgZ2V0R29vZ2xlQVBJVG9rZW4sXG4gIGluc2VydEV2ZW50VHJpZ2dlcnMsXG59IGZyb20gJ0Bnb29nbGVfY2FsZW5kYXJfc3luYy9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCB7IENhbGVuZGFySW50ZWdyYXRpb25UeXBlIH0gZnJvbSAnQGdvb2dsZV9jYWxlbmRhcl9zeW5jL19saWJzL3R5cGVzL2dvb2dsZUNhbGVuZGFyU3luYy90eXBlcyc7XG5cbmRheWpzLmV4dGVuZCh1dGMpO1xuXG5jb25zdCBhZG1pblNlY3JldCA9IHByb2Nlc3MuZW52LkhBU1VSQV9HUkFQSFFMX0FETUlOX1NFQ1JFVDtcbi8vIGNvbnN0IGhhc3VyYUdyYXBoVXJsID0gcHJvY2Vzcy5lbnYuSEFTVVJBX0dSQVBIX1VSTFxuLy8gY29uc3QgaGFzdXJhTWV0YWRhdGFVcmwgPSBwcm9jZXNzLmVudi5IQVNVUkFfTUVUQURBVEFfVVJMXG4vLyBjb25zdCBzZWxmR29vZ2xlUGVvcGxlQWRtaW5VcmwgPSBwcm9jZXNzLmVudi5TRUxGX0dPT0dMRV9QRU9QTEVfQURNSU5fVVJcblxuLy8gY29uc3QgZ29vZ2xlUGVvcGxlID0gZ29vZ2xlLnBlb3BsZSgndjEnKVxuY29uc3QgZGVsZXRlQ29udGFjdHMgPSBhc3luYyAocGVvcGxlOiBQZXJzb25UeXBlW10pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhwZW9wbGUsICcgcGVvcGxlIGluc2lkZSBkZWxldGVDb250YWN0cycpO1xuICAgIGlmICghKHBlb3BsZT8uWzBdPy5yZXNvdXJjZU5hbWU/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBjb25zb2xlLmxvZygnIG5vIHBlb3BsZSBwcmVzZW50IHRvIGRlbGV0ZScpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGNvbnN0IGlkcyA9IHBlb3BsZT8ubWFwKChwKSA9PiBwPy5yZXNvdXJjZU5hbWUucmVwbGFjZSgncGVvcGxlLycsICcnKSk7XG5cbiAgICBpZiAoIWlkcyB8fCAhKGlkcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgbm8gcGVvcGxlIHByZXNlbnQgdG8gZGVsZXRlJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnZGVsZXRlQ29udGFjdHMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgbXV0YXRpb24gZGVsZXRlQ29udGFjdHMoJGlkczogW1N0cmluZyFdISkge1xuICAgICAgICBkZWxldGVfQ29udGFjdCh3aGVyZToge2lkOiB7X2luOiAkaWRzfX0pIHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkcyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogYWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIGRlbGV0ZUNvbnRhY3RzJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkZWxldGUgY29udGFjdHMnKTtcbiAgfVxufTtcblxuY29uc3QgdXBzZXJ0Q29udGFjdHMyID0gYXN5bmMgKHBlb3BsZTogUGVyc29uVHlwZVtdLCB1c2VySWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKHBlb3BsZSwgJyBwZW9wbGUgaW5zaWRlIHVwc2VydENvbnRhY3RzMicpO1xuICAgIGlmICghKHBlb3BsZT8uWzBdPy5yZXNvdXJjZU5hbWU/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBjb25zb2xlLmxvZygnIG5vIHBlb3BsZSBwcmVzZW50IHRvIHVwc2VydCcpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cbiAgICBjb25zdCBmb3JtYXR0ZWRQZW9wbGUgPSBwZW9wbGU/Lm1hcCgocCkgPT4gKHtcbiAgICAgIGlkOiBwPy5yZXNvdXJjZU5hbWU/LnJlcGxhY2UoJ3Blb3BsZS8nLCAnJyksXG4gICAgICBuYW1lOlxuICAgICAgICBwPy5uYW1lcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8uZGlzcGxheU5hbWUgfHwgcD8ubmFtZXM/LlswXT8uZGlzcGxheU5hbWUsXG4gICAgICBmaXJzdE5hbWU6XG4gICAgICAgIHA/Lm5hbWVzPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy5naXZlbk5hbWUgfHwgcD8ubmFtZXM/LlswXT8uZ2l2ZW5OYW1lLFxuICAgICAgbWlkZGxlTmFtZTpcbiAgICAgICAgcD8ubmFtZXM/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF1cbiAgICAgICAgICA/Lm1pZGRsZU5hbWUgfHwgcD8ubmFtZXM/LlswXT8ubWlkZGxlTmFtZSxcbiAgICAgIGxhc3ROYW1lOlxuICAgICAgICBwPy5uYW1lcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8uZmFtaWx5TmFtZSB8fCBwPy5uYW1lcz8uWzBdPy5mYW1pbHlOYW1lLFxuICAgICAgbmFtZVByZWZpeDpcbiAgICAgICAgcD8ubmFtZXM/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF1cbiAgICAgICAgICA/Lmhvbm9yaWZpY1ByZWZpeCB8fCBwPy5uYW1lcz8uWzBdPy5ob25vcmlmaWNQcmVmaXgsXG4gICAgICBuYW1lU3VmZml4OlxuICAgICAgICBwPy5uYW1lcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8uaG9ub3JpZmljU3VmZml4IHx8IHA/Lm5hbWVzPy5bMF0/Lmhvbm9yaWZpY1N1ZmZpeCxcbiAgICAgIG5pY2tuYW1lOlxuICAgICAgICBwPy5uaWNrbmFtZXM/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF1cbiAgICAgICAgICA/LnZhbHVlIHx8IHA/Lm5pY2tuYW1lcz8uWzBdPy52YWx1ZSxcbiAgICAgIHBob25ldGljRmlyc3ROYW1lOlxuICAgICAgICBwPy5uYW1lcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8ucGhvbmV0aWNHaXZlbk5hbWUgfHwgcD8ubmFtZXM/LlswXT8ucGhvbmV0aWNHaXZlbk5hbWUsXG4gICAgICBwaG9uZXRpY01pZGRsZU5hbWU6XG4gICAgICAgIHA/Lm5hbWVzPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy5waG9uZXRpY01pZGRsZU5hbWUgfHwgcD8ubmFtZXM/LlswXT8ucGhvbmV0aWNNaWRkbGVOYW1lLFxuICAgICAgcGhvbmV0aWNMYXN0TmFtZTpcbiAgICAgICAgcD8ubmFtZXM/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF1cbiAgICAgICAgICA/LnBob25ldGljRmFtaWx5TmFtZSB8fCBwPy5uYW1lcz8uWzBdPy5waG9uZXRpY0ZhbWlseU5hbWUsXG4gICAgICBjb21wYW55OlxuICAgICAgICBwPy5vcmdhbml6YXRpb25zPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy5uYW1lIHx8IHA/Lm9yZ2FuaXphdGlvbnM/LlswXT8ubmFtZSxcbiAgICAgIGpvYlRpdGxlOlxuICAgICAgICBwPy5vcmdhbml6YXRpb25zPy5maWx0ZXIoKG4pID0+IG4/Lm1ldGFkYXRhPy5wcmltYXJ5ID09PSB0cnVlKT8uWzBdXG4gICAgICAgICAgPy50aXRsZSB8fCBwPy5vcmdhbml6YXRpb25zPy5bMF0/LnRpdGxlLFxuICAgICAgZGVwYXJ0bWVudDpcbiAgICAgICAgcD8ub3JnYW5pemF0aW9ucz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8uZGVwYXJ0bWVudCB8fCBwPy5vcmdhbml6YXRpb25zPy5bMF0/LmRlcGFydG1lbnQsXG4gICAgICBub3RlczpcbiAgICAgICAgcD8uYmlvZ3JhcGhpZXM/LmZpbHRlcihcbiAgICAgICAgICAobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUgJiYgbj8uY29udGVudFR5cGUgPT09ICdURVhUX0hUTUwnXG4gICAgICAgICk/LlswXT8udmFsdWUgfHwgcD8uYmlvZ3JhcGhpZXM/LlswXT8udmFsdWUsXG4gICAgICBpbWFnZUF2YWlsYWJsZTpcbiAgICAgICAgcD8uY292ZXJQaG90b3M/LmZpbHRlcigobikgPT4gbj8ubWV0YWRhdGE/LnByaW1hcnkgPT09IHRydWUpPy5bMF0/LnVybFxuICAgICAgICAgID8ubGVuZ3RoID4gMCxcbiAgICAgIGltYWdlOlxuICAgICAgICBwPy5jb3ZlclBob3Rvcz8uZmlsdGVyKChuKSA9PiBuPy5tZXRhZGF0YT8ucHJpbWFyeSA9PT0gdHJ1ZSk/LlswXVxuICAgICAgICAgID8udXJsIHx8IHA/LmNvdmVyUGhvdG9zPy5bMF0/LnVybCxcbiAgICAgIGNvbnRhY3RUeXBlOiBwPy5tZXRhZGF0YT8ub2JqZWN0VHlwZSxcbiAgICAgIGVtYWlsczogcD8uZW1haWxBZGRyZXNzZXM/Lm1hcCgoZSkgPT4gKHtcbiAgICAgICAgcHJpbWFyeTogZT8ubWV0YWRhdGE/LnByaW1hcnksXG4gICAgICAgIHZhbHVlOiBlPy52YWx1ZSxcbiAgICAgICAgdHlwZTogZT8udHlwZSxcbiAgICAgICAgZGlzcGxheU5hbWU6IGU/LmRpc3BsYXlOYW1lLFxuICAgICAgfSkpLFxuICAgICAgcGhvbmVOdW1iZXJzOiBwPy5waG9uZU51bWJlcnM/Lm1hcCgocCkgPT4gKHtcbiAgICAgICAgcHJpbWFyeTogcD8ubWV0YWRhdGE/LnByaW1hcnksXG4gICAgICAgIHZhbHVlOiBwPy52YWx1ZSxcbiAgICAgICAgdHlwZTogcD8udHlwZSxcbiAgICAgIH0pKSxcbiAgICAgIGltQWRkcmVzc2VzOiBwPy5pbUNsaWVudHM/Lm1hcCgoaSkgPT4gKHtcbiAgICAgICAgcHJpbWFyeTogaT8ubWV0YWRhdGE/LnByaW1hcnksXG4gICAgICAgIHVzZXJuYW1lOiBpPy51c2VybmFtZSxcbiAgICAgICAgc2VydmljZTogaT8ucHJvdG9jb2wsXG4gICAgICAgIHR5cGU6IGk/LnR5cGUsXG4gICAgICB9KSksXG4gICAgICBsaW5rQWRkcmVzc2VzOiBwPy51cmxzPy5tYXAoKHUpID0+ICh7XG4gICAgICAgIHByaW1hcnk6IHU/Lm1ldGFkYXRhPy5wcmltYXJ5LFxuICAgICAgICB2YWx1ZTogdT8udmFsdWUsXG4gICAgICAgIHR5cGU6IHU/LnR5cGUsXG4gICAgICB9KSksXG4gICAgICB1c2VySWQsXG4gICAgfSkpO1xuXG4gICAgaWYgKCFmb3JtYXR0ZWRQZW9wbGUgfHwgIShmb3JtYXR0ZWRQZW9wbGU/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gZm9ybWF0dGVkUGVvcGxlIHRvIHVwc2VydCcpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0Q29udGFjdCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICBtdXRhdGlvbiBJbnNlcnRDb250YWN0KCRjb250YWN0czogW0NvbnRhY3RfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgIGluc2VydF9Db250YWN0KFxuICAgICAgICAgIG9iamVjdHM6ICRjb250YWN0cyxcbiAgICAgICAgICBvbl9jb25mbGljdDoge1xuICAgICAgICAgICAgICBjb25zdHJhaW50OiBDb250YWN0X3BrZXksXG4gICAgICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgICAgICAgbmFtZSxcbiAgICAgICAgICAgICAgICBmaXJzdE5hbWUsXG4gICAgICAgICAgICAgICAgbWlkZGxlTmFtZSxcbiAgICAgICAgICAgICAgICBsYXN0TmFtZSxcbiAgICAgICAgICAgICAgICBuYW1lUHJlZml4LFxuICAgICAgICAgICAgICAgIG5hbWVTdWZmaXgsXG4gICAgICAgICAgICAgICAgbmlja25hbWUsXG4gICAgICAgICAgICAgICAgcGhvbmV0aWNGaXJzdE5hbWUsXG4gICAgICAgICAgICAgICAgcGhvbmV0aWNNaWRkbGVOYW1lLFxuICAgICAgICAgICAgICAgIHBob25ldGljTGFzdE5hbWUsXG4gICAgICAgICAgICAgICAgY29tcGFueSxcbiAgICAgICAgICAgICAgICBqb2JUaXRsZSxcbiAgICAgICAgICAgICAgICBkZXBhcnRtZW50LFxuICAgICAgICAgICAgICAgIG5vdGVzLFxuICAgICAgICAgICAgICAgIGltYWdlQXZhaWxhYmxlLFxuICAgICAgICAgICAgICAgIGltYWdlLFxuICAgICAgICAgICAgICAgIGNvbnRhY3RUeXBlLFxuICAgICAgICAgICAgICAgIGVtYWlscyxcbiAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnMsXG4gICAgICAgICAgICAgICAgaW1BZGRyZXNzZXMsXG4gICAgICAgICAgICAgICAgbGlua0FkZHJlc3NlcyxcbiAgICAgICAgICAgICAgXVxuICAgICAgICAgIH0pe1xuICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICBpZFxuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgIH1cbiAgICBgO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGNvbnRhY3RzOiBmb3JtYXR0ZWRQZW9wbGUsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXNwb25zZSwgJyB0aGlzIGlzIHJlc3BvbnNlIGluIHVwc2VydENvbnRhY3RzJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cHNlcnRDb250YWN0cycpO1xuICB9XG59O1xuXG5jb25zdCBpbmNyZW1lbnRhbEdvb2dsZUNvbnRhY3RzU3luYzIgPSBhc3luYyAoXG4gIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgY2xpZW50VHlwZTogJ2lvcycgfCAnYW5kcm9pZCcgfCAnd2ViJyB8ICdhdG9taWMtd2ViJyxcbiAgcGFyZW50U3luY1Rva2VuOiBzdHJpbmcsXG4gIHBhcmVudFBhZ2VUb2tlbj86IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IGxvY2FsQ29ubmVjdGlvbnM6IFBlcnNvblR5cGVbXSB8IG9iamVjdCA9IHt9O1xuICAgIGxldCBwYWdlVG9rZW4gPSBwYXJlbnRQYWdlVG9rZW47XG4gICAgbGV0IHN5bmNUb2tlbiA9IHBhcmVudFN5bmNUb2tlbjtcblxuICAgIGNvbnN0IHRva2VuID0gYXdhaXQgZ2V0R29vZ2xlQVBJVG9rZW4oXG4gICAgICB1c2VySWQsXG4gICAgICBnb29nbGVQZW9wbGVSZXNvdXJjZSxcbiAgICAgIGNsaWVudFR5cGVcbiAgICApO1xuXG4gICAgY29uc3QgZ29vZ2xlUGVvcGxlID0gZ29vZ2xlLnBlb3BsZSh7XG4gICAgICB2ZXJzaW9uOiAndjEnLFxuICAgICAgaGVhZGVyczoge1xuICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7dG9rZW59YCxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zdCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgIC8vIE9wdGlvbmFsLiBUaGUgbnVtYmVyIG9mIGNvbm5lY3Rpb25zIHRvIGluY2x1ZGUgaW4gdGhlIHJlc3BvbnNlLiBWYWxpZCB2YWx1ZXMgYXJlIGJldHdlZW4gMSBhbmQgMTAwMCwgaW5jbHVzaXZlLiBEZWZhdWx0cyB0byAxMDAgaWYgbm90IHNldCBvciBzZXQgdG8gMC5cbiAgICAgIHBhZ2VTaXplOiAxMDAwLFxuICAgICAgLy8gUmVxdWlyZWQuIEEgZmllbGQgbWFzayB0byByZXN0cmljdCB3aGljaCBmaWVsZHMgb24gZWFjaCBwZXJzb24gYXJlIHJldHVybmVkLiBNdWx0aXBsZSBmaWVsZHMgY2FuIGJlIHNwZWNpZmllZCBieSBzZXBhcmF0aW5nIHRoZW0gd2l0aCBjb21tYXMuIFZhbGlkIHZhbHVlcyBhcmU6ICogYWRkcmVzc2VzICogYWdlUmFuZ2VzICogYmlvZ3JhcGhpZXMgKiBiaXJ0aGRheXMgKiBjYWxlbmRhclVybHMgKiBjbGllbnREYXRhICogY292ZXJQaG90b3MgKiBlbWFpbEFkZHJlc3NlcyAqIGV2ZW50cyAqIGV4dGVybmFsSWRzICogZ2VuZGVycyAqIGltQ2xpZW50cyAqIGludGVyZXN0cyAqIGxvY2FsZXMgKiBsb2NhdGlvbnMgKiBtZW1iZXJzaGlwcyAqIG1ldGFkYXRhICogbWlzY0tleXdvcmRzICogbmFtZXMgKiBuaWNrbmFtZXMgKiBvY2N1cGF0aW9ucyAqIG9yZ2FuaXphdGlvbnMgKiBwaG9uZU51bWJlcnMgKiBwaG90b3MgKiByZWxhdGlvbnMgKiBzaXBBZGRyZXNzZXMgKiBza2lsbHMgKiB1cmxzICogdXNlckRlZmluZWRcbiAgICAgIHBlcnNvbkZpZWxkczpcbiAgICAgICAgJ25hbWVzLG5pY2tuYW1lcyxvcmdhbml6YXRpb25zLGJpb2dyYXBoaWVzLGNvdmVyUGhvdG9zLG1ldGFkYXRhLGVtYWlsQWRkcmVzc2VzLGltQ2xpZW50cyx1cmxzJyxcbiAgICAgIC8vIFJlcXVpcmVkLiBDb21tYS1zZXBhcmF0ZWQgbGlzdCBvZiBwZXJzb24gZmllbGRzIHRvIGJlIGluY2x1ZGVkIGluIHRoZSByZXNwb25zZS4gRWFjaCBwYXRoIHNob3VsZCBzdGFydCB3aXRoIGBwZXJzb24uYDogZm9yIGV4YW1wbGUsIGBwZXJzb24ubmFtZXNgIG9yIGBwZXJzb24ucGhvdG9zYC5cbiAgICAgIC8vICdyZXF1ZXN0TWFzay5pbmNsdWRlRmllbGQnOiAncGVyc29uLm5hbWVzLHBlcnNvbi5uaWNrbmFtZXMscGVyc29uLm9yZ2FuaXphdGlvbnMscGVyc29uLmJpb2dyYXBoaWVzLHBlcnNvbi5jb3ZlclBob3RvcyxwZXJzb24ubWV0YWRhdGEscGVyc29uLmVtYWlsQWRkcmVzc2VzLHBlcnNvbi5pbUNsaWVudHMscGVyc29uLnVybHMnLFxuICAgICAgLy8gT3B0aW9uYWwuIFdoZXRoZXIgdGhlIHJlc3BvbnNlIHNob3VsZCByZXR1cm4gYG5leHRfc3luY190b2tlbmAgb24gdGhlIGxhc3QgcGFnZSBvZiByZXN1bHRzLiBJdCBjYW4gYmUgdXNlZCB0byBnZXQgaW5jcmVtZW50YWwgY2hhbmdlcyBzaW5jZSB0aGUgbGFzdCByZXF1ZXN0IGJ5IHNldHRpbmcgaXQgb24gdGhlIHJlcXVlc3QgYHN5bmNfdG9rZW5gLiBNb3JlIGRldGFpbHMgYWJvdXQgc3luYyBiZWhhdmlvciBhdCBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgLlxuICAgICAgcmVxdWVzdFN5bmNUb2tlbjogdHJ1ZSxcbiAgICAgIC8vIFJlcXVpcmVkLiBUaGUgcmVzb3VyY2UgbmFtZSB0byByZXR1cm4gY29ubmVjdGlvbnMgZm9yLiBPbmx5IGBwZW9wbGUvbWVgIGlzIHZhbGlkLlxuICAgICAgcmVzb3VyY2VOYW1lOiAncGVvcGxlL21lJyxcbiAgICAgIC8vIE9wdGlvbmFsLiBBIHN5bmMgdG9rZW4sIHJlY2VpdmVkIGZyb20gYSBwcmV2aW91cyByZXNwb25zZSBgbmV4dF9zeW5jX3Rva2VuYCBQcm92aWRlIHRoaXMgdG8gcmV0cmlldmUgb25seSB0aGUgcmVzb3VyY2VzIGNoYW5nZWQgc2luY2UgdGhlIGxhc3QgcmVxdWVzdC4gV2hlbiBzeW5jaW5nLCBhbGwgb3RoZXIgcGFyYW1ldGVycyBwcm92aWRlZCB0byBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgIG11c3QgbWF0Y2ggdGhlIGZpcnN0IGNhbGwgdGhhdCBwcm92aWRlZCB0aGUgc3luYyB0b2tlbi4gTW9yZSBkZXRhaWxzIGFib3V0IHN5bmMgYmVoYXZpb3IgYXQgYHBlb3BsZS5jb25uZWN0aW9ucy5saXN0YC5cbiAgICAgIHN5bmNUb2tlbjogcGFyZW50U3luY1Rva2VuLFxuICAgIH07XG5cbiAgICBpZiAocGFyZW50UGFnZVRva2VuKSB7XG4gICAgICB2YXJpYWJsZXMucGFnZVRva2VuID0gcGFyZW50UGFnZVRva2VuO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvb2dsZVBlb3BsZS5wZW9wbGUuY29ubmVjdGlvbnMubGlzdCh2YXJpYWJsZXMpO1xuICAgIGNvbnNvbGUubG9nKHJlcy5kYXRhKTtcblxuICAgIGNvbnN0IHsgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBjb25uZWN0aW9ucyxcbiAgICAgIG5leHRQYWdlVG9rZW4sXG4gICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgJyBjb25uZWN0aW9ucywgbmV4dFBhZ2VUb2tlbiwgbmV4dFN5bmNUb2tlbiBpbnNpZGUgaW5jcmVtZW50YWxHb29nbGVDb250YWN0c1N5bmMyJ1xuICAgICk7XG5cbiAgICBsb2NhbENvbm5lY3Rpb25zID0gY29ubmVjdGlvbnM7XG4gICAgcGFnZVRva2VuID0gbmV4dFBhZ2VUb2tlbjtcbiAgICBzeW5jVG9rZW4gPSBuZXh0U3luY1Rva2VuO1xuXG4gICAgYXdhaXQgdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24oXG4gICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgbmV4dFBhZ2VUb2tlblxuICAgICk7XG5cbiAgICBjb25zdCBkZWxldGVkUGVvcGxlID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkID09PSB0cnVlXG4gICAgKTtcblxuICAgIGlmIChkZWxldGVkUGVvcGxlPy5bMF0/Lm5hbWVzKSB7XG4gICAgICBhd2FpdCBkZWxldGVDb250YWN0cyhkZWxldGVkUGVvcGxlIGFzIFBlcnNvblR5cGVbXSk7XG4gICAgfVxuXG4gICAgY29uc3QgcGVvcGxlVG9VcHNlcnQgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgIT09IHRydWVcbiAgICApO1xuXG4gICAgLy8gbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlblxuICAgIGlmICghKHBlb3BsZVRvVXBzZXJ0Py5bMF0/Lm5hbWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIGV2ZW50cyB0byB1cHNlcnQgY2hlY2sgbmV4dCBwYWdldG9rZW4nKTtcbiAgICAgIGNvbnN0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgICAvLyBPcHRpb25hbC4gVGhlIG51bWJlciBvZiBjb25uZWN0aW9ucyB0byBpbmNsdWRlIGluIHRoZSByZXNwb25zZS4gVmFsaWQgdmFsdWVzIGFyZSBiZXR3ZWVuIDEgYW5kIDEwMDAsIGluY2x1c2l2ZS4gRGVmYXVsdHMgdG8gMTAwIGlmIG5vdCBzZXQgb3Igc2V0IHRvIDAuXG4gICAgICAgIHBhZ2VTaXplOiAxMDAwLFxuICAgICAgICAvLyBSZXF1aXJlZC4gQSBmaWVsZCBtYXNrIHRvIHJlc3RyaWN0IHdoaWNoIGZpZWxkcyBvbiBlYWNoIHBlcnNvbiBhcmUgcmV0dXJuZWQuIE11bHRpcGxlIGZpZWxkcyBjYW4gYmUgc3BlY2lmaWVkIGJ5IHNlcGFyYXRpbmcgdGhlbSB3aXRoIGNvbW1hcy4gVmFsaWQgdmFsdWVzIGFyZTogKiBhZGRyZXNzZXMgKiBhZ2VSYW5nZXMgKiBiaW9ncmFwaGllcyAqIGJpcnRoZGF5cyAqIGNhbGVuZGFyVXJscyAqIGNsaWVudERhdGEgKiBjb3ZlclBob3RvcyAqIGVtYWlsQWRkcmVzc2VzICogZXZlbnRzICogZXh0ZXJuYWxJZHMgKiBnZW5kZXJzICogaW1DbGllbnRzICogaW50ZXJlc3RzICogbG9jYWxlcyAqIGxvY2F0aW9ucyAqIG1lbWJlcnNoaXBzICogbWV0YWRhdGEgKiBtaXNjS2V5d29yZHMgKiBuYW1lcyAqIG5pY2tuYW1lcyAqIG9jY3VwYXRpb25zICogb3JnYW5pemF0aW9ucyAqIHBob25lTnVtYmVycyAqIHBob3RvcyAqIHJlbGF0aW9ucyAqIHNpcEFkZHJlc3NlcyAqIHNraWxscyAqIHVybHMgKiB1c2VyRGVmaW5lZFxuICAgICAgICBwZXJzb25GaWVsZHM6XG4gICAgICAgICAgJ25hbWVzLG5pY2tuYW1lcyxvcmdhbml6YXRpb25zLGJpb2dyYXBoaWVzLGNvdmVyUGhvdG9zLG1ldGFkYXRhLGVtYWlsQWRkcmVzc2VzLGltQ2xpZW50cyx1cmxzJyxcbiAgICAgICAgLy8gUmVxdWlyZWQuIENvbW1hLXNlcGFyYXRlZCBsaXN0IG9mIHBlcnNvbiBmaWVsZHMgdG8gYmUgaW5jbHVkZWQgaW4gdGhlIHJlc3BvbnNlLiBFYWNoIHBhdGggc2hvdWxkIHN0YXJ0IHdpdGggYHBlcnNvbi5gOiBmb3IgZXhhbXBsZSwgYHBlcnNvbi5uYW1lc2Agb3IgYHBlcnNvbi5waG90b3NgLlxuICAgICAgICAvLyAncmVxdWVzdE1hc2suaW5jbHVkZUZpZWxkJzogJ3BlcnNvbi5uYW1lcyxwZXJzb24ubmlja25hbWVzLHBlcnNvbi5vcmdhbml6YXRpb25zLHBlcnNvbi5iaW9ncmFwaGllcyxwZXJzb24uY292ZXJQaG90b3MscGVyc29uLm1ldGFkYXRhLHBlcnNvbi5lbWFpbEFkZHJlc3NlcyxwZXJzb24uaW1DbGllbnRzLHBlcnNvbi51cmxzJyxcbiAgICAgICAgLy8gT3B0aW9uYWwuIFdoZXRoZXIgdGhlIHJlc3BvbnNlIHNob3VsZCByZXR1cm4gYG5leHRfc3luY190b2tlbmAgb24gdGhlIGxhc3QgcGFnZSBvZiByZXN1bHRzLiBJdCBjYW4gYmUgdXNlZCB0byBnZXQgaW5jcmVtZW50YWwgY2hhbmdlcyBzaW5jZSB0aGUgbGFzdCByZXF1ZXN0IGJ5IHNldHRpbmcgaXQgb24gdGhlIHJlcXVlc3QgYHN5bmNfdG9rZW5gLiBNb3JlIGRldGFpbHMgYWJvdXQgc3luYyBiZWhhdmlvciBhdCBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgLlxuICAgICAgICByZXF1ZXN0U3luY1Rva2VuOiB0cnVlLFxuICAgICAgICAvLyBSZXF1aXJlZC4gVGhlIHJlc291cmNlIG5hbWUgdG8gcmV0dXJuIGNvbm5lY3Rpb25zIGZvci4gT25seSBgcGVvcGxlL21lYCBpcyB2YWxpZC5cbiAgICAgICAgcmVzb3VyY2VOYW1lOiAncGVvcGxlL21lJyxcbiAgICAgICAgLy8gT3B0aW9uYWwuIEEgc3luYyB0b2tlbiwgcmVjZWl2ZWQgZnJvbSBhIHByZXZpb3VzIHJlc3BvbnNlIGBuZXh0X3N5bmNfdG9rZW5gIFByb3ZpZGUgdGhpcyB0byByZXRyaWV2ZSBvbmx5IHRoZSByZXNvdXJjZXMgY2hhbmdlZCBzaW5jZSB0aGUgbGFzdCByZXF1ZXN0LiBXaGVuIHN5bmNpbmcsIGFsbCBvdGhlciBwYXJhbWV0ZXJzIHByb3ZpZGVkIHRvIGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAgbXVzdCBtYXRjaCB0aGUgZmlyc3QgY2FsbCB0aGF0IHByb3ZpZGVkIHRoZSBzeW5jIHRva2VuLiBNb3JlIGRldGFpbHMgYWJvdXQgc3luYyBiZWhhdmlvciBhdCBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgLlxuICAgICAgICBzeW5jVG9rZW4sXG4gICAgICB9O1xuXG4gICAgICBpZiAocGFnZVRva2VuKSB7XG4gICAgICAgIHZhcmlhYmxlcy5wYWdlVG9rZW4gPSBwYWdlVG9rZW47XG4gICAgICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvb2dsZVBlb3BsZS5wZW9wbGUuY29ubmVjdGlvbnMubGlzdCh2YXJpYWJsZXMpO1xuXG4gICAgICAgIGNvbnN0IHsgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBjb25uZWN0aW9ucyxcbiAgICAgICAgICBuZXh0UGFnZVRva2VuLFxuICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgcGFnZVRva2VuLFxuICAgICAgICAgICcgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4sIHBhZ2VUb2tlbiBpbnNpZGUgaW5jcmVtZW50YWxHb29nbGVDb250YWN0c1N5bmMyJ1xuICAgICAgICApO1xuXG4gICAgICAgIGxvY2FsQ29ubmVjdGlvbnMgPSBjb25uZWN0aW9ucztcbiAgICAgICAgcGFnZVRva2VuID0gbmV4dFBhZ2VUb2tlbjtcbiAgICAgICAgc3luY1Rva2VuID0gbmV4dFN5bmNUb2tlbjtcbiAgICAgICAgLy8gdG9rZW5zIGluIGNhc2Ugc29tZXRoaW5nIGdvZXMgd3JvbmdcbiAgICAgICAgLy8gdXBkYXRlIHBhZ2VUb2tlbiBhbmQgc3luY1Rva2VuXG4gICAgICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUludGVncmF0aW9uKFxuICAgICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgICAgIG5leHRQYWdlVG9rZW5cbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGVsZXRlZFBlb3BsZSA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgPT09IHRydWVcbiAgICAgICAgKTtcblxuICAgICAgICBpZiAoZGVsZXRlZFBlb3BsZT8uWzBdPy5uYW1lcykge1xuICAgICAgICAgIGF3YWl0IGRlbGV0ZUNvbnRhY3RzKGRlbGV0ZWRQZW9wbGUgYXMgUGVyc29uVHlwZVtdKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHBlb3BsZVRvVXBzZXJ0MiA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgIT09IHRydWVcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKHBlb3BsZVRvVXBzZXJ0Mj8uWzBdPy5uYW1lcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgIGF3YWl0IHVwc2VydENvbnRhY3RzMihwZW9wbGVUb1Vwc2VydDIgYXMgUGVyc29uVHlwZVtdLCB1c2VySWQpO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfSBlbHNlIHtcbiAgICAgIGF3YWl0IHVwc2VydENvbnRhY3RzMihwZW9wbGVUb1Vwc2VydCBhcyBQZXJzb25UeXBlW10sIHVzZXJJZCk7XG4gICAgfVxuXG4gICAgaWYgKHBhZ2VUb2tlbikge1xuICAgICAgd2hpbGUgKHBhZ2VUb2tlbikge1xuICAgICAgICBjb25zdCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgICAgICAvLyBPcHRpb25hbC4gVGhlIG51bWJlciBvZiBjb25uZWN0aW9ucyB0byBpbmNsdWRlIGluIHRoZSByZXNwb25zZS4gVmFsaWQgdmFsdWVzIGFyZSBiZXR3ZWVuIDEgYW5kIDEwMDAsIGluY2x1c2l2ZS4gRGVmYXVsdHMgdG8gMTAwIGlmIG5vdCBzZXQgb3Igc2V0IHRvIDAuXG4gICAgICAgICAgcGFnZVNpemU6IDEwMDAsXG4gICAgICAgICAgLy8gT3B0aW9uYWwuIEEgcGFnZSB0b2tlbiwgcmVjZWl2ZWQgZnJvbSBhIHByZXZpb3VzIHJlc3BvbnNlIGBuZXh0X3BhZ2VfdG9rZW5gLiBQcm92aWRlIHRoaXMgdG8gcmV0cmlldmUgdGhlIHN1YnNlcXVlbnQgcGFnZS4gV2hlbiBwYWdpbmF0aW5nLCBhbGwgb3RoZXIgcGFyYW1ldGVycyBwcm92aWRlZCB0byBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgIG11c3QgbWF0Y2ggdGhlIGZpcnN0IGNhbGwgdGhhdCBwcm92aWRlZCB0aGUgcGFnZSB0b2tlbi5cbiAgICAgICAgICBwYWdlVG9rZW4sXG4gICAgICAgICAgLy8gUmVxdWlyZWQuIEEgZmllbGQgbWFzayB0byByZXN0cmljdCB3aGljaCBmaWVsZHMgb24gZWFjaCBwZXJzb24gYXJlIHJldHVybmVkLiBNdWx0aXBsZSBmaWVsZHMgY2FuIGJlIHNwZWNpZmllZCBieSBzZXBhcmF0aW5nIHRoZW0gd2l0aCBjb21tYXMuIFZhbGlkIHZhbHVlcyBhcmU6ICogYWRkcmVzc2VzICogYWdlUmFuZ2VzICogYmlvZ3JhcGhpZXMgKiBiaXJ0aGRheXMgKiBjYWxlbmRhclVybHMgKiBjbGllbnREYXRhICogY292ZXJQaG90b3MgKiBlbWFpbEFkZHJlc3NlcyAqIGV2ZW50cyAqIGV4dGVybmFsSWRzICogZ2VuZGVycyAqIGltQ2xpZW50cyAqIGludGVyZXN0cyAqIGxvY2FsZXMgKiBsb2NhdGlvbnMgKiBtZW1iZXJzaGlwcyAqIG1ldGFkYXRhICogbWlzY0tleXdvcmRzICogbmFtZXMgKiBuaWNrbmFtZXMgKiBvY2N1cGF0aW9ucyAqIG9yZ2FuaXphdGlvbnMgKiBwaG9uZU51bWJlcnMgKiBwaG90b3MgKiByZWxhdGlvbnMgKiBzaXBBZGRyZXNzZXMgKiBza2lsbHMgKiB1cmxzICogdXNlckRlZmluZWRcbiAgICAgICAgICBwZXJzb25GaWVsZHM6XG4gICAgICAgICAgICAnbmFtZXMsbmlja25hbWVzLG9yZ2FuaXphdGlvbnMsYmlvZ3JhcGhpZXMsY292ZXJQaG90b3MsbWV0YWRhdGEsZW1haWxBZGRyZXNzZXMsaW1DbGllbnRzLHVybHMnLFxuICAgICAgICAgIC8vIFJlcXVpcmVkLiBDb21tYS1zZXBhcmF0ZWQgbGlzdCBvZiBwZXJzb24gZmllbGRzIHRvIGJlIGluY2x1ZGVkIGluIHRoZSByZXNwb25zZS4gRWFjaCBwYXRoIHNob3VsZCBzdGFydCB3aXRoIGBwZXJzb24uYDogZm9yIGV4YW1wbGUsIGBwZXJzb24ubmFtZXNgIG9yIGBwZXJzb24ucGhvdG9zYC5cbiAgICAgICAgICAvLyAncmVxdWVzdE1hc2suaW5jbHVkZUZpZWxkJzogJ3BlcnNvbi5uYW1lcyxwZXJzb24ubmlja25hbWVzLHBlcnNvbi5vcmdhbml6YXRpb25zLHBlcnNvbi5iaW9ncmFwaGllcyxwZXJzb24uY292ZXJQaG90b3MscGVyc29uLm1ldGFkYXRhLHBlcnNvbi5lbWFpbEFkZHJlc3NlcyxwZXJzb24uaW1DbGllbnRzLHBlcnNvbi51cmxzJyxcbiAgICAgICAgICAvLyBPcHRpb25hbC4gV2hldGhlciB0aGUgcmVzcG9uc2Ugc2hvdWxkIHJldHVybiBgbmV4dF9zeW5jX3Rva2VuYCBvbiB0aGUgbGFzdCBwYWdlIG9mIHJlc3VsdHMuIEl0IGNhbiBiZSB1c2VkIHRvIGdldCBpbmNyZW1lbnRhbCBjaGFuZ2VzIHNpbmNlIHRoZSBsYXN0IHJlcXVlc3QgYnkgc2V0dGluZyBpdCBvbiB0aGUgcmVxdWVzdCBgc3luY190b2tlbmAuIE1vcmUgZGV0YWlscyBhYm91dCBzeW5jIGJlaGF2aW9yIGF0IGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAuXG4gICAgICAgICAgcmVxdWVzdFN5bmNUb2tlbjogdHJ1ZSxcbiAgICAgICAgICAvLyBSZXF1aXJlZC4gVGhlIHJlc291cmNlIG5hbWUgdG8gcmV0dXJuIGNvbm5lY3Rpb25zIGZvci4gT25seSBgcGVvcGxlL21lYCBpcyB2YWxpZC5cbiAgICAgICAgICByZXNvdXJjZU5hbWU6ICdwZW9wbGUvbWUnLFxuICAgICAgICB9O1xuXG4gICAgICAgIGlmIChzeW5jVG9rZW4pIHtcbiAgICAgICAgICB2YXJpYWJsZXMuc3luY1Rva2VuID0gc3luY1Rva2VuO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlUGVvcGxlLnBlb3BsZS5jb25uZWN0aW9ucy5saXN0KHZhcmlhYmxlcyk7XG4gICAgICAgIGNvbnNvbGUubG9nKHJlcy5kYXRhKTtcblxuICAgICAgICBjb25zdCB7IGNvbm5lY3Rpb25zLCBuZXh0UGFnZVRva2VuLCBuZXh0U3luY1Rva2VuIH0gPSByZXMuZGF0YTtcblxuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBjb25uZWN0aW9ucyxcbiAgICAgICAgICBuZXh0UGFnZVRva2VuLFxuICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgcGFnZVRva2VuLFxuICAgICAgICAgICcgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4sIHBhZ2VUb2tlbiBpbnNpZGUgaW5jcmVtZW50YWxHb29nbGVDb250YWN0c1N5bmMyIHBhcnQgb2Ygd2hpbGUgbG9vcCdcbiAgICAgICAgKTtcblxuICAgICAgICBsb2NhbENvbm5lY3Rpb25zID0gY29ubmVjdGlvbnM7XG4gICAgICAgIHBhZ2VUb2tlbiA9IG5leHRQYWdlVG9rZW47XG4gICAgICAgIHN5bmNUb2tlbiA9IG5leHRTeW5jVG9rZW47XG4gICAgICAgIC8vIHRva2VucyBpbiBjYXNlIHNvbWV0aGluZyBnb2VzIHdyb25nXG4gICAgICAgIC8vIHVwZGF0ZSBwYWdlVG9rZW4gYW5kIHN5bmNUb2tlblxuXG4gICAgICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUludGVncmF0aW9uKFxuICAgICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgICAgIG5leHRQYWdlVG9rZW5cbiAgICAgICAgKTtcblxuICAgICAgICBjb25zdCBkZWxldGVkUGVvcGxlID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCA9PT0gdHJ1ZVxuICAgICAgICApO1xuXG4gICAgICAgIGlmIChkZWxldGVkUGVvcGxlPy5bMF0/Lm5hbWVzKSB7XG4gICAgICAgICAgYXdhaXQgZGVsZXRlQ29udGFjdHMoZGVsZXRlZFBlb3BsZSBhcyBQZXJzb25UeXBlW10pO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcGVvcGxlVG9VcHNlcnQgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkICE9PSB0cnVlXG4gICAgICAgICk7XG5cbiAgICAgICAgLy8gbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlblxuICAgICAgICBpZiAoIShwZW9wbGVUb1Vwc2VydD8uWzBdPy5uYW1lcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlbicpO1xuICAgICAgICAgIGNvbnN0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgICAgICAgLy8gT3B0aW9uYWwuIFRoZSBudW1iZXIgb2YgY29ubmVjdGlvbnMgdG8gaW5jbHVkZSBpbiB0aGUgcmVzcG9uc2UuIFZhbGlkIHZhbHVlcyBhcmUgYmV0d2VlbiAxIGFuZCAxMDAwLCBpbmNsdXNpdmUuIERlZmF1bHRzIHRvIDEwMCBpZiBub3Qgc2V0IG9yIHNldCB0byAwLlxuICAgICAgICAgICAgcGFnZVNpemU6IDEwMDAsXG4gICAgICAgICAgICAvLyBPcHRpb25hbC4gQSBwYWdlIHRva2VuLCByZWNlaXZlZCBmcm9tIGEgcHJldmlvdXMgcmVzcG9uc2UgYG5leHRfcGFnZV90b2tlbmAuIFByb3ZpZGUgdGhpcyB0byByZXRyaWV2ZSB0aGUgc3Vic2VxdWVudCBwYWdlLiBXaGVuIHBhZ2luYXRpbmcsIGFsbCBvdGhlciBwYXJhbWV0ZXJzIHByb3ZpZGVkIHRvIGBwZW9wbGUuY29ubmVjdGlvbnMubGlzdGAgbXVzdCBtYXRjaCB0aGUgZmlyc3QgY2FsbCB0aGF0IHByb3ZpZGVkIHRoZSBwYWdlIHRva2VuLlxuICAgICAgICAgICAgLy8gUmVxdWlyZWQuIEEgZmllbGQgbWFzayB0byByZXN0cmljdCB3aGljaCBmaWVsZHMgb24gZWFjaCBwZXJzb24gYXJlIHJldHVybmVkLiBNdWx0aXBsZSBmaWVsZHMgY2FuIGJlIHNwZWNpZmllZCBieSBzZXBhcmF0aW5nIHRoZW0gd2l0aCBjb21tYXMuIFZhbGlkIHZhbHVlcyBhcmU6ICogYWRkcmVzc2VzICogYWdlUmFuZ2VzICogYmlvZ3JhcGhpZXMgKiBiaXJ0aGRheXMgKiBjYWxlbmRhclVybHMgKiBjbGllbnREYXRhICogY292ZXJQaG90b3MgKiBlbWFpbEFkZHJlc3NlcyAqIGV2ZW50cyAqIGV4dGVybmFsSWRzICogZ2VuZGVycyAqIGltQ2xpZW50cyAqIGludGVyZXN0cyAqIGxvY2FsZXMgKiBsb2NhdGlvbnMgKiBtZW1iZXJzaGlwcyAqIG1ldGFkYXRhICogbWlzY0tleXdvcmRzICogbmFtZXMgKiBuaWNrbmFtZXMgKiBvY2N1cGF0aW9ucyAqIG9yZ2FuaXphdGlvbnMgKiBwaG9uZU51bWJlcnMgKiBwaG90b3MgKiByZWxhdGlvbnMgKiBzaXBBZGRyZXNzZXMgKiBza2lsbHMgKiB1cmxzICogdXNlckRlZmluZWRcbiAgICAgICAgICAgIHBlcnNvbkZpZWxkczpcbiAgICAgICAgICAgICAgJ25hbWVzLG5pY2tuYW1lcyxvcmdhbml6YXRpb25zLGJpb2dyYXBoaWVzLGNvdmVyUGhvdG9zLG1ldGFkYXRhLGVtYWlsQWRkcmVzc2VzLGltQ2xpZW50cyx1cmxzJyxcbiAgICAgICAgICAgIC8vIFJlcXVpcmVkLiBDb21tYS1zZXBhcmF0ZWQgbGlzdCBvZiBwZXJzb24gZmllbGRzIHRvIGJlIGluY2x1ZGVkIGluIHRoZSByZXNwb25zZS4gRWFjaCBwYXRoIHNob3VsZCBzdGFydCB3aXRoIGBwZXJzb24uYDogZm9yIGV4YW1wbGUsIGBwZXJzb24ubmFtZXNgIG9yIGBwZXJzb24ucGhvdG9zYC5cbiAgICAgICAgICAgIC8vICdyZXF1ZXN0TWFzay5pbmNsdWRlRmllbGQnOiAncGVyc29uLm5hbWVzLHBlcnNvbi5uaWNrbmFtZXMscGVyc29uLm9yZ2FuaXphdGlvbnMscGVyc29uLmJpb2dyYXBoaWVzLHBlcnNvbi5jb3ZlclBob3RvcyxwZXJzb24ubWV0YWRhdGEscGVyc29uLmVtYWlsQWRkcmVzc2VzLHBlcnNvbi5pbUNsaWVudHMscGVyc29uLnVybHMnLFxuICAgICAgICAgICAgLy8gT3B0aW9uYWwuIFdoZXRoZXIgdGhlIHJlc3BvbnNlIHNob3VsZCByZXR1cm4gYG5leHRfc3luY190b2tlbmAgb24gdGhlIGxhc3QgcGFnZSBvZiByZXN1bHRzLiBJdCBjYW4gYmUgdXNlZCB0byBnZXQgaW5jcmVtZW50YWwgY2hhbmdlcyBzaW5jZSB0aGUgbGFzdCByZXF1ZXN0IGJ5IHNldHRpbmcgaXQgb24gdGhlIHJlcXVlc3QgYHN5bmNfdG9rZW5gLiBNb3JlIGRldGFpbHMgYWJvdXQgc3luYyBiZWhhdmlvciBhdCBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgLlxuICAgICAgICAgICAgcmVxdWVzdFN5bmNUb2tlbjogdHJ1ZSxcbiAgICAgICAgICAgIC8vIFJlcXVpcmVkLiBUaGUgcmVzb3VyY2UgbmFtZSB0byByZXR1cm4gY29ubmVjdGlvbnMgZm9yLiBPbmx5IGBwZW9wbGUvbWVgIGlzIHZhbGlkLlxuICAgICAgICAgICAgcmVzb3VyY2VOYW1lOiAncGVvcGxlL21lJyxcbiAgICAgICAgICB9O1xuXG4gICAgICAgICAgaWYgKHN5bmNUb2tlbikge1xuICAgICAgICAgICAgdmFyaWFibGVzLnN5bmNUb2tlbiA9IHN5bmNUb2tlbjtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAocGFnZVRva2VuKSB7XG4gICAgICAgICAgICB2YXJpYWJsZXMucGFnZVRva2VuID0gcGFnZVRva2VuO1xuICAgICAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlUGVvcGxlLnBlb3BsZS5jb25uZWN0aW9ucy5saXN0KHZhcmlhYmxlcyk7XG5cbiAgICAgICAgICAgIGNvbnN0IHsgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuXG4gICAgICAgICAgICBsb2NhbENvbm5lY3Rpb25zID0gY29ubmVjdGlvbnM7XG4gICAgICAgICAgICBwYWdlVG9rZW4gPSBuZXh0UGFnZVRva2VuO1xuICAgICAgICAgICAgc3luY1Rva2VuID0gbmV4dFN5bmNUb2tlbjtcbiAgICAgICAgICAgIC8vIHRva2VucyBpbiBjYXNlIHNvbWV0aGluZyBnb2VzIHdyb25nXG4gICAgICAgICAgICAvLyB1cGRhdGUgcGFnZVRva2VuIGFuZCBzeW5jVG9rZW5cbiAgICAgICAgICAgIGF3YWl0IHVwZGF0ZUdvb2dsZUludGVncmF0aW9uKFxuICAgICAgICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgICAgIG5leHRQYWdlVG9rZW5cbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBjb25zdCBkZWxldGVkUGVvcGxlID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgPT09IHRydWVcbiAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgIGlmIChkZWxldGVkUGVvcGxlPy5bMF0/Lm5hbWVzPy5bMF0pIHtcbiAgICAgICAgICAgICAgYXdhaXQgZGVsZXRlQ29udGFjdHMoZGVsZXRlZFBlb3BsZSBhcyBQZXJzb25UeXBlW10pO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBjb25zdCBwZW9wbGVUb1Vwc2VydDIgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCAhPT0gdHJ1ZVxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGlmIChwZW9wbGVUb1Vwc2VydDI/LlswXT8ubmFtZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgYXdhaXQgdXBzZXJ0Q29udGFjdHMyKHBlb3BsZVRvVXBzZXJ0MiBhcyBQZXJzb25UeXBlW10sIHVzZXJJZCk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICB9XG4gICAgICAgIGF3YWl0IHVwc2VydENvbnRhY3RzMihwZW9wbGVUb1Vwc2VydCBhcyBQZXJzb25UeXBlW10sIHVzZXJJZCk7XG4gICAgICB9XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gaW5jcmVtZW50YWwgZ29vZ2xlIHN5bmMnKTtcbiAgICAvLyByZXNldCBzeW5jXG4gICAgaWYgKGUuY29kZSA9PT0gNDEwKSB7XG4gICAgICBhd2FpdCByZXNldEdvb2dsZUludGVncmF0aW9uU3luY0ZvckNvbnRhY3RzKFxuICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICAgIHVzZXJJZFxuICAgICAgKTtcbiAgICAgIHJldHVybiB0cnVlO1xuICAgIH1cbiAgICByZXR1cm4gZmFsc2U7XG4gIH1cbn07XG5cbmNvbnN0IGluaXRpYWxHb29nbGVDb250YWN0c1N5bmMyID0gYXN5bmMgKFxuICBjYWxlbmRhckludGVncmF0aW9uSWQ6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNsaWVudFR5cGU6ICdpb3MnIHwgJ2FuZHJvaWQnIHwgJ3dlYicgfCAnYXRvbWljLXdlYidcbikgPT4ge1xuICB0cnkge1xuICAgIGxldCBsb2NhbENvbm5lY3Rpb25zOiBQZXJzb25UeXBlW10gfCBvYmplY3QgPSB7fTtcbiAgICBsZXQgcGFnZVRva2VuID0gJyc7XG4gICAgY29uc3QgdG9rZW4gPSBhd2FpdCBnZXRHb29nbGVBUElUb2tlbihcbiAgICAgIHVzZXJJZCxcbiAgICAgIGdvb2dsZVBlb3BsZVJlc291cmNlLFxuICAgICAgY2xpZW50VHlwZVxuICAgICk7XG5cbiAgICBjb25zdCBnb29nbGVQZW9wbGUgPSBnb29nbGUucGVvcGxlKHtcbiAgICAgIHZlcnNpb246ICd2MScsXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvb2dsZVBlb3BsZS5wZW9wbGUuY29ubmVjdGlvbnMubGlzdCh7XG4gICAgICAvLyBPcHRpb25hbC4gVGhlIG51bWJlciBvZiBjb25uZWN0aW9ucyB0byBpbmNsdWRlIGluIHRoZSByZXNwb25zZS4gVmFsaWQgdmFsdWVzIGFyZSBiZXR3ZWVuIDEgYW5kIDEwMDAsIGluY2x1c2l2ZS4gRGVmYXVsdHMgdG8gMTAwIGlmIG5vdCBzZXQgb3Igc2V0IHRvIDAuXG4gICAgICBwYWdlU2l6ZTogMTAwMCxcbiAgICAgIC8vIFJlcXVpcmVkLiBBIGZpZWxkIG1hc2sgdG8gcmVzdHJpY3Qgd2hpY2ggZmllbGRzIG9uIGVhY2ggcGVyc29uIGFyZSByZXR1cm5lZC4gTXVsdGlwbGUgZmllbGRzIGNhbiBiZSBzcGVjaWZpZWQgYnkgc2VwYXJhdGluZyB0aGVtIHdpdGggY29tbWFzLiBWYWxpZCB2YWx1ZXMgYXJlOiAqIGFkZHJlc3NlcyAqIGFnZVJhbmdlcyAqIGJpb2dyYXBoaWVzICogYmlydGhkYXlzICogY2FsZW5kYXJVcmxzICogY2xpZW50RGF0YSAqIGNvdmVyUGhvdG9zICogZW1haWxBZGRyZXNzZXMgKiBldmVudHMgKiBleHRlcm5hbElkcyAqIGdlbmRlcnMgKiBpbUNsaWVudHMgKiBpbnRlcmVzdHMgKiBsb2NhbGVzICogbG9jYXRpb25zICogbWVtYmVyc2hpcHMgKiBtZXRhZGF0YSAqIG1pc2NLZXl3b3JkcyAqIG5hbWVzICogbmlja25hbWVzICogb2NjdXBhdGlvbnMgKiBvcmdhbml6YXRpb25zICogcGhvbmVOdW1iZXJzICogcGhvdG9zICogcmVsYXRpb25zICogc2lwQWRkcmVzc2VzICogc2tpbGxzICogdXJscyAqIHVzZXJEZWZpbmVkXG4gICAgICBwZXJzb25GaWVsZHM6XG4gICAgICAgICduYW1lcyxuaWNrbmFtZXMsb3JnYW5pemF0aW9ucyxiaW9ncmFwaGllcyxjb3ZlclBob3RvcyxtZXRhZGF0YSxlbWFpbEFkZHJlc3NlcyxpbUNsaWVudHMsdXJscycsXG4gICAgICAvLyBSZXF1aXJlZC4gQ29tbWEtc2VwYXJhdGVkIGxpc3Qgb2YgcGVyc29uIGZpZWxkcyB0byBiZSBpbmNsdWRlZCBpbiB0aGUgcmVzcG9uc2UuIEVhY2ggcGF0aCBzaG91bGQgc3RhcnQgd2l0aCBgcGVyc29uLmA6IGZvciBleGFtcGxlLCBgcGVyc29uLm5hbWVzYCBvciBgcGVyc29uLnBob3Rvc2AuXG4gICAgICAvLyAncmVxdWVzdE1hc2suaW5jbHVkZUZpZWxkJzogJ3BlcnNvbi5uYW1lcyxwZXJzb24ubmlja25hbWVzLHBlcnNvbi5vcmdhbml6YXRpb25zLHBlcnNvbi5iaW9ncmFwaGllcyxwZXJzb24uY292ZXJQaG90b3MscGVyc29uLm1ldGFkYXRhLHBlcnNvbi5lbWFpbEFkZHJlc3NlcyxwZXJzb24uaW1DbGllbnRzLHBlcnNvbi51cmxzJyxcbiAgICAgIC8vIE9wdGlvbmFsLiBXaGV0aGVyIHRoZSByZXNwb25zZSBzaG91bGQgcmV0dXJuIGBuZXh0X3N5bmNfdG9rZW5gIG9uIHRoZSBsYXN0IHBhZ2Ugb2YgcmVzdWx0cy4gSXQgY2FuIGJlIHVzZWQgdG8gZ2V0IGluY3JlbWVudGFsIGNoYW5nZXMgc2luY2UgdGhlIGxhc3QgcmVxdWVzdCBieSBzZXR0aW5nIGl0IG9uIHRoZSByZXF1ZXN0IGBzeW5jX3Rva2VuYC4gTW9yZSBkZXRhaWxzIGFib3V0IHN5bmMgYmVoYXZpb3IgYXQgYHBlb3BsZS5jb25uZWN0aW9ucy5saXN0YC5cbiAgICAgIHJlcXVlc3RTeW5jVG9rZW46IHRydWUsXG4gICAgICAvLyBSZXF1aXJlZC4gVGhlIHJlc291cmNlIG5hbWUgdG8gcmV0dXJuIGNvbm5lY3Rpb25zIGZvci4gT25seSBgcGVvcGxlL21lYCBpcyB2YWxpZC5cbiAgICAgIHJlc291cmNlTmFtZTogJ3Blb3BsZS9tZScsXG4gICAgfSk7XG4gICAgY29uc29sZS5sb2cocmVzLmRhdGEpO1xuICAgIC8vIEV4YW1wbGUgcmVzcG9uc2VcbiAgICAvLyB7XG4gICAgLy8gICAmcXVvdDtjb25uZWN0aW9ucyZxdW90OzogW10sXG4gICAgLy8gICAmcXVvdDtuZXh0UGFnZVRva2VuJnF1b3Q7OiAmcXVvdDtteV9uZXh0UGFnZVRva2VuJnF1b3Q7LFxuICAgIC8vICAgJnF1b3Q7bmV4dFN5bmNUb2tlbiZxdW90OzogJnF1b3Q7bXlfbmV4dFN5bmNUb2tlbiZxdW90OyxcbiAgICAvLyAgICZxdW90O3RvdGFsSXRlbXMmcXVvdDs6IDAsXG4gICAgLy8gICAmcXVvdDt0b3RhbFBlb3BsZSZxdW90OzogMFxuICAgIC8vIH1cblxuICAgIGNvbnN0IHsgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgY29ubmVjdGlvbnMsXG4gICAgICBuZXh0UGFnZVRva2VuLFxuICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICcgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gaW5zaWRlIGluaXRpYWxHb29nbGVDb250YWN0c1N5bmMyJ1xuICAgICk7XG4gICAgbG9jYWxDb25uZWN0aW9ucyA9IGNvbm5lY3Rpb25zO1xuICAgIHBhZ2VUb2tlbiA9IG5leHRQYWdlVG9rZW47XG5cbiAgICBhd2FpdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbihcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICBuZXh0UGFnZVRva2VuXG4gICAgKTtcblxuICAgIGNvbnN0IGRlbGV0ZWRQZW9wbGUgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgPT09IHRydWVcbiAgICApO1xuXG4gICAgaWYgKGRlbGV0ZWRQZW9wbGU/LlswXT8ubmFtZXMpIHtcbiAgICAgIGF3YWl0IGRlbGV0ZUNvbnRhY3RzKGRlbGV0ZWRQZW9wbGUgYXMgUGVyc29uVHlwZVtdKTtcbiAgICB9XG5cbiAgICBjb25zdCBwZW9wbGVUb1Vwc2VydCA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCAhPT0gdHJ1ZVxuICAgICk7XG5cbiAgICAvLyBubyBldmVudHMgdG8gdXBzZXJ0IGNoZWNrIG5leHQgcGFnZXRva2VuXG4gICAgaWYgKCEocGVvcGxlVG9VcHNlcnQ/LlswXT8ubmFtZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRzIHRvIHVwc2VydCBjaGVjayBuZXh0IHBhZ2V0b2tlbicpO1xuICAgICAgY29uc3QgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICAgIC8vIE9wdGlvbmFsLiBUaGUgbnVtYmVyIG9mIGNvbm5lY3Rpb25zIHRvIGluY2x1ZGUgaW4gdGhlIHJlc3BvbnNlLiBWYWxpZCB2YWx1ZXMgYXJlIGJldHdlZW4gMSBhbmQgMTAwMCwgaW5jbHVzaXZlLiBEZWZhdWx0cyB0byAxMDAgaWYgbm90IHNldCBvciBzZXQgdG8gMC5cbiAgICAgICAgcGFnZVNpemU6IDEwMDAsXG4gICAgICAgIC8vIFJlcXVpcmVkLiBBIGZpZWxkIG1hc2sgdG8gcmVzdHJpY3Qgd2hpY2ggZmllbGRzIG9uIGVhY2ggcGVyc29uIGFyZSByZXR1cm5lZC4gTXVsdGlwbGUgZmllbGRzIGNhbiBiZSBzcGVjaWZpZWQgYnkgc2VwYXJhdGluZyB0aGVtIHdpdGggY29tbWFzLiBWYWxpZCB2YWx1ZXMgYXJlOiAqIGFkZHJlc3NlcyAqIGFnZVJhbmdlcyAqIGJpb2dyYXBoaWVzICogYmlydGhkYXlzICogY2FsZW5kYXJVcmxzICogY2xpZW50RGF0YSAqIGNvdmVyUGhvdG9zICogZW1haWxBZGRyZXNzZXMgKiBldmVudHMgKiBleHRlcm5hbElkcyAqIGdlbmRlcnMgKiBpbUNsaWVudHMgKiBpbnRlcmVzdHMgKiBsb2NhbGVzICogbG9jYXRpb25zICogbWVtYmVyc2hpcHMgKiBtZXRhZGF0YSAqIG1pc2NLZXl3b3JkcyAqIG5hbWVzICogbmlja25hbWVzICogb2NjdXBhdGlvbnMgKiBvcmdhbml6YXRpb25zICogcGhvbmVOdW1iZXJzICogcGhvdG9zICogcmVsYXRpb25zICogc2lwQWRkcmVzc2VzICogc2tpbGxzICogdXJscyAqIHVzZXJEZWZpbmVkXG4gICAgICAgIHBlcnNvbkZpZWxkczpcbiAgICAgICAgICAnbmFtZXMsbmlja25hbWVzLG9yZ2FuaXphdGlvbnMsYmlvZ3JhcGhpZXMsY292ZXJQaG90b3MsbWV0YWRhdGEsZW1haWxBZGRyZXNzZXMsaW1DbGllbnRzLHVybHMnLFxuICAgICAgICAvLyBSZXF1aXJlZC4gQ29tbWEtc2VwYXJhdGVkIGxpc3Qgb2YgcGVyc29uIGZpZWxkcyB0byBiZSBpbmNsdWRlZCBpbiB0aGUgcmVzcG9uc2UuIEVhY2ggcGF0aCBzaG91bGQgc3RhcnQgd2l0aCBgcGVyc29uLmA6IGZvciBleGFtcGxlLCBgcGVyc29uLm5hbWVzYCBvciBgcGVyc29uLnBob3Rvc2AuXG4gICAgICAgIC8vICdyZXF1ZXN0TWFzay5pbmNsdWRlRmllbGQnOiAncGVyc29uLm5hbWVzLHBlcnNvbi5uaWNrbmFtZXMscGVyc29uLm9yZ2FuaXphdGlvbnMscGVyc29uLmJpb2dyYXBoaWVzLHBlcnNvbi5jb3ZlclBob3RvcyxwZXJzb24ubWV0YWRhdGEscGVyc29uLmVtYWlsQWRkcmVzc2VzLHBlcnNvbi5pbUNsaWVudHMscGVyc29uLnVybHMnLFxuICAgICAgICAvLyBSZXF1aXJlZC4gVGhlIHJlc291cmNlIG5hbWUgdG8gcmV0dXJuIGNvbm5lY3Rpb25zIGZvci4gT25seSBgcGVvcGxlL21lYCBpcyB2YWxpZC5cbiAgICAgICAgcmVzb3VyY2VOYW1lOiAncGVvcGxlL21lJyxcbiAgICAgIH07XG5cbiAgICAgIGlmIChwYWdlVG9rZW4pIHtcbiAgICAgICAgdmFyaWFibGVzLnBhZ2VUb2tlbiA9IHBhZ2VUb2tlbjtcbiAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlUGVvcGxlLnBlb3BsZS5jb25uZWN0aW9ucy5saXN0KHZhcmlhYmxlcyk7XG4gICAgICAgIGNvbnNvbGUubG9nKHJlcy5kYXRhKTtcbiAgICAgICAgLy8gRXhhbXBsZSByZXNwb25zZVxuICAgICAgICAvLyB7XG4gICAgICAgIC8vICAgJnF1b3Q7Y29ubmVjdGlvbnMmcXVvdDs6IFtdLFxuICAgICAgICAvLyAgICZxdW90O25leHRQYWdlVG9rZW4mcXVvdDs6ICZxdW90O215X25leHRQYWdlVG9rZW4mcXVvdDssXG4gICAgICAgIC8vICAgJnF1b3Q7bmV4dFN5bmNUb2tlbiZxdW90OzogJnF1b3Q7bXlfbmV4dFN5bmNUb2tlbiZxdW90OyxcbiAgICAgICAgLy8gICAmcXVvdDt0b3RhbEl0ZW1zJnF1b3Q7OiAwLFxuICAgICAgICAvLyAgICZxdW90O3RvdGFsUGVvcGxlJnF1b3Q7OiAwXG4gICAgICAgIC8vIH1cblxuICAgICAgICBjb25zdCB7IGNvbm5lY3Rpb25zLCBuZXh0UGFnZVRva2VuLCBuZXh0U3luY1Rva2VuIH0gPSByZXMuZGF0YTtcblxuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBjb25uZWN0aW9ucyxcbiAgICAgICAgICBuZXh0UGFnZVRva2VuLFxuICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgcGFnZVRva2VuLFxuICAgICAgICAgICcgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4sIHBhZ2VUb2tlbiBpbnNpZGUgaW5pdGlhbEdvb2dsZUNvbnRhY3RzU3luYzInXG4gICAgICAgICk7XG5cbiAgICAgICAgbG9jYWxDb25uZWN0aW9ucyA9IGNvbm5lY3Rpb25zO1xuICAgICAgICBwYWdlVG9rZW4gPSBuZXh0UGFnZVRva2VuO1xuICAgICAgICAvLyB0b2tlbnMgaW4gY2FzZSBzb21ldGhpbmcgZ29lcyB3cm9uZ1xuICAgICAgICAvLyB1cGRhdGUgcGFnZVRva2VuIGFuZCBzeW5jVG9rZW5cblxuICAgICAgICBhd2FpdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbihcbiAgICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICAgICAgbmV4dFN5bmNUb2tlbixcbiAgICAgICAgICBuZXh0UGFnZVRva2VuXG4gICAgICAgICk7XG5cbiAgICAgICAgY29uc3QgZGVsZXRlZFBlb3BsZSA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgPT09IHRydWVcbiAgICAgICAgKTtcblxuICAgICAgICBpZiAoZGVsZXRlZFBlb3BsZT8uWzBdPy5uYW1lcz8uWzBdKSB7XG4gICAgICAgICAgYXdhaXQgZGVsZXRlQ29udGFjdHMoZGVsZXRlZFBlb3BsZSBhcyBQZXJzb25UeXBlW10pO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcGVvcGxlVG9VcHNlcnQyID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCAhPT0gdHJ1ZVxuICAgICAgICApO1xuICAgICAgICBpZiAocGVvcGxlVG9VcHNlcnQyPy5bMF0/Lm5hbWVzPy5bMF0pIHtcbiAgICAgICAgICBhd2FpdCB1cHNlcnRDb250YWN0czIocGVvcGxlVG9VcHNlcnQyIGFzIFBlcnNvblR5cGVbXSwgdXNlcklkKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH0gZWxzZSB7XG4gICAgICBhd2FpdCB1cHNlcnRDb250YWN0czIocGVvcGxlVG9VcHNlcnQgYXMgUGVyc29uVHlwZVtdLCB1c2VySWQpO1xuICAgIH1cbiAgICBpZiAocGFnZVRva2VuKSB7XG4gICAgICAvLyBmZXRjaCBhbGwgcGFnZXNcbiAgICAgIHdoaWxlIChwYWdlVG9rZW4pIHtcbiAgICAgICAgY29uc3QgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICAgICAgLy8gT3B0aW9uYWwuIFRoZSBudW1iZXIgb2YgY29ubmVjdGlvbnMgdG8gaW5jbHVkZSBpbiB0aGUgcmVzcG9uc2UuIFZhbGlkIHZhbHVlcyBhcmUgYmV0d2VlbiAxIGFuZCAxMDAwLCBpbmNsdXNpdmUuIERlZmF1bHRzIHRvIDEwMCBpZiBub3Qgc2V0IG9yIHNldCB0byAwLlxuICAgICAgICAgIHBhZ2VTaXplOiAxMDAwLFxuICAgICAgICAgIC8vIE9wdGlvbmFsLiBBIHBhZ2UgdG9rZW4sIHJlY2VpdmVkIGZyb20gYSBwcmV2aW91cyByZXNwb25zZSBgbmV4dF9wYWdlX3Rva2VuYC4gUHJvdmlkZSB0aGlzIHRvIHJldHJpZXZlIHRoZSBzdWJzZXF1ZW50IHBhZ2UuIFdoZW4gcGFnaW5hdGluZywgYWxsIG90aGVyIHBhcmFtZXRlcnMgcHJvdmlkZWQgdG8gYHBlb3BsZS5jb25uZWN0aW9ucy5saXN0YCBtdXN0IG1hdGNoIHRoZSBmaXJzdCBjYWxsIHRoYXQgcHJvdmlkZWQgdGhlIHBhZ2UgdG9rZW4uXG4gICAgICAgICAgcGFnZVRva2VuLFxuICAgICAgICAgIC8vIFJlcXVpcmVkLiBBIGZpZWxkIG1hc2sgdG8gcmVzdHJpY3Qgd2hpY2ggZmllbGRzIG9uIGVhY2ggcGVyc29uIGFyZSByZXR1cm5lZC4gTXVsdGlwbGUgZmllbGRzIGNhbiBiZSBzcGVjaWZpZWQgYnkgc2VwYXJhdGluZyB0aGVtIHdpdGggY29tbWFzLiBWYWxpZCB2YWx1ZXMgYXJlOiAqIGFkZHJlc3NlcyAqIGFnZVJhbmdlcyAqIGJpb2dyYXBoaWVzICogYmlydGhkYXlzICogY2FsZW5kYXJVcmxzICogY2xpZW50RGF0YSAqIGNvdmVyUGhvdG9zICogZW1haWxBZGRyZXNzZXMgKiBldmVudHMgKiBleHRlcm5hbElkcyAqIGdlbmRlcnMgKiBpbUNsaWVudHMgKiBpbnRlcmVzdHMgKiBsb2NhbGVzICogbG9jYXRpb25zICogbWVtYmVyc2hpcHMgKiBtZXRhZGF0YSAqIG1pc2NLZXl3b3JkcyAqIG5hbWVzICogbmlja25hbWVzICogb2NjdXBhdGlvbnMgKiBvcmdhbml6YXRpb25zICogcGhvbmVOdW1iZXJzICogcGhvdG9zICogcmVsYXRpb25zICogc2lwQWRkcmVzc2VzICogc2tpbGxzICogdXJscyAqIHVzZXJEZWZpbmVkXG4gICAgICAgICAgcGVyc29uRmllbGRzOlxuICAgICAgICAgICAgJ25hbWVzLG5pY2tuYW1lcyxvcmdhbml6YXRpb25zLGJpb2dyYXBoaWVzLGNvdmVyUGhvdG9zLG1ldGFkYXRhLGVtYWlsQWRkcmVzc2VzLGltQ2xpZW50cyx1cmxzJyxcbiAgICAgICAgICAvLyBSZXF1aXJlZC4gQ29tbWEtc2VwYXJhdGVkIGxpc3Qgb2YgcGVyc29uIGZpZWxkcyB0byBiZSBpbmNsdWRlZCBpbiB0aGUgcmVzcG9uc2UuIEVhY2ggcGF0aCBzaG91bGQgc3RhcnQgd2l0aCBgcGVyc29uLmA6IGZvciBleGFtcGxlLCBgcGVyc29uLm5hbWVzYCBvciBgcGVyc29uLnBob3Rvc2AuXG4gICAgICAgICAgLy8gLy8gJ3JlcXVlc3RNYXNrLmluY2x1ZGVGaWVsZCc6ICdwZXJzb24ubmFtZXMscGVyc29uLm5pY2tuYW1lcyxwZXJzb24ub3JnYW5pemF0aW9ucyxwZXJzb24uYmlvZ3JhcGhpZXMscGVyc29uLmNvdmVyUGhvdG9zLHBlcnNvbi5tZXRhZGF0YSxwZXJzb24uZW1haWxBZGRyZXNzZXMscGVyc29uLmltQ2xpZW50cyxwZXJzb24udXJscycsXG4gICAgICAgICAgLy8gT3B0aW9uYWwuIFdoZXRoZXIgdGhlIHJlc3BvbnNlIHNob3VsZCByZXR1cm4gYG5leHRfc3luY190b2tlbmAgb24gdGhlIGxhc3QgcGFnZSBvZiByZXN1bHRzLiBJdCBjYW4gYmUgdXNlZCB0byBnZXQgaW5jcmVtZW50YWwgY2hhbmdlcyBzaW5jZSB0aGUgbGFzdCByZXF1ZXN0IGJ5IHNldHRpbmcgaXQgb24gdGhlIHJlcXVlc3QgYHN5bmNfdG9rZW5gLiBNb3JlIGRldGFpbHMgYWJvdXQgc3luYyBiZWhhdmlvciBhdCBgcGVvcGxlLmNvbm5lY3Rpb25zLmxpc3RgLlxuICAgICAgICAgIHJlcXVlc3RTeW5jVG9rZW46IHRydWUsXG4gICAgICAgICAgLy8gUmVxdWlyZWQuIFRoZSByZXNvdXJjZSBuYW1lIHRvIHJldHVybiBjb25uZWN0aW9ucyBmb3IuIE9ubHkgYHBlb3BsZS9tZWAgaXMgdmFsaWQuXG4gICAgICAgICAgcmVzb3VyY2VOYW1lOiAncGVvcGxlL21lJyxcbiAgICAgICAgfTtcbiAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlUGVvcGxlLnBlb3BsZS5jb25uZWN0aW9ucy5saXN0KHZhcmlhYmxlcyk7XG4gICAgICAgIGNvbnNvbGUubG9nKHJlcy5kYXRhKTtcbiAgICAgICAgLy8gRXhhbXBsZSByZXNwb25zZVxuICAgICAgICAvLyB7XG4gICAgICAgIC8vICAgJnF1b3Q7Y29ubmVjdGlvbnMmcXVvdDs6IFtdLFxuICAgICAgICAvLyAgICZxdW90O25leHRQYWdlVG9rZW4mcXVvdDs6ICZxdW90O215X25leHRQYWdlVG9rZW4mcXVvdDssXG4gICAgICAgIC8vICAgJnF1b3Q7bmV4dFN5bmNUb2tlbiZxdW90OzogJnF1b3Q7bXlfbmV4dFN5bmNUb2tlbiZxdW90OyxcbiAgICAgICAgLy8gICAmcXVvdDt0b3RhbEl0ZW1zJnF1b3Q7OiAwLFxuICAgICAgICAvLyAgICZxdW90O3RvdGFsUGVvcGxlJnF1b3Q7OiAwXG4gICAgICAgIC8vIH1cblxuICAgICAgICBjb25zdCB7IGNvbm5lY3Rpb25zLCBuZXh0UGFnZVRva2VuLCBuZXh0U3luY1Rva2VuIH0gPSByZXMuZGF0YTtcblxuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBjb25uZWN0aW9ucyxcbiAgICAgICAgICBuZXh0UGFnZVRva2VuLFxuICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgcGFnZVRva2VuLFxuICAgICAgICAgICcgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4sIHBhZ2VUb2tlbiBpbnNpZGUgaW5pdGlhbEdvb2dsZUNvbnRhY3RzU3luYzIgcGFydCBvZiB3aGlsZSBsb29wJ1xuICAgICAgICApO1xuXG4gICAgICAgIGxvY2FsQ29ubmVjdGlvbnMgPSBjb25uZWN0aW9ucztcbiAgICAgICAgcGFnZVRva2VuID0gbmV4dFBhZ2VUb2tlbjtcbiAgICAgICAgLy8gdG9rZW5zIGluIGNhc2Ugc29tZXRoaW5nIGdvZXMgd3JvbmdcbiAgICAgICAgLy8gdXBkYXRlIHBhZ2VUb2tlbiBhbmQgc3luY1Rva2VuXG5cbiAgICAgICAgYXdhaXQgdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24oXG4gICAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgICAgIG5leHRTeW5jVG9rZW4sXG4gICAgICAgICAgbmV4dFBhZ2VUb2tlblxuICAgICAgICApO1xuXG4gICAgICAgIGNvbnN0IGRlbGV0ZWRQZW9wbGUgPSAobG9jYWxDb25uZWN0aW9ucyBhcyBQZXJzb25UeXBlW10pPy5maWx0ZXIoXG4gICAgICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkID09PSB0cnVlXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKGRlbGV0ZWRQZW9wbGU/LlswXT8ubmFtZXM/LlswXSkge1xuICAgICAgICAgIGF3YWl0IGRlbGV0ZUNvbnRhY3RzKGRlbGV0ZWRQZW9wbGUgYXMgUGVyc29uVHlwZVtdKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNvbnN0IHBlb3BsZVRvVXBzZXJ0ID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgIChlKSA9PiBlPy5tZXRhZGF0YT8uZGVsZXRlZCAhPT0gdHJ1ZVxuICAgICAgICApO1xuXG4gICAgICAgIC8vIG5vIGV2ZW50cyB0byB1cHNlcnQgY2hlY2sgbmV4dCBwYWdldG9rZW5cbiAgICAgICAgaWYgKCEocGVvcGxlVG9VcHNlcnQ/LlswXT8ubmFtZXM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coJ25vIGV2ZW50cyB0byB1cHNlcnQgY2hlY2sgbmV4dCBwYWdldG9rZW4nKTtcbiAgICAgICAgICBjb25zdCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgICAgICAgIC8vIE9wdGlvbmFsLiBUaGUgbnVtYmVyIG9mIGNvbm5lY3Rpb25zIHRvIGluY2x1ZGUgaW4gdGhlIHJlc3BvbnNlLiBWYWxpZCB2YWx1ZXMgYXJlIGJldHdlZW4gMSBhbmQgMTAwMCwgaW5jbHVzaXZlLiBEZWZhdWx0cyB0byAxMDAgaWYgbm90IHNldCBvciBzZXQgdG8gMC5cbiAgICAgICAgICAgIHBhZ2VTaXplOiAxMDAwLFxuICAgICAgICAgICAgLy8gUmVxdWlyZWQuIEEgZmllbGQgbWFzayB0byByZXN0cmljdCB3aGljaCBmaWVsZHMgb24gZWFjaCBwZXJzb24gYXJlIHJldHVybmVkLiBNdWx0aXBsZSBmaWVsZHMgY2FuIGJlIHNwZWNpZmllZCBieSBzZXBhcmF0aW5nIHRoZW0gd2l0aCBjb21tYXMuIFZhbGlkIHZhbHVlcyBhcmU6ICogYWRkcmVzc2VzICogYWdlUmFuZ2VzICogYmlvZ3JhcGhpZXMgKiBiaXJ0aGRheXMgKiBjYWxlbmRhclVybHMgKiBjbGllbnREYXRhICogY292ZXJQaG90b3MgKiBlbWFpbEFkZHJlc3NlcyAqIGV2ZW50cyAqIGV4dGVybmFsSWRzICogZ2VuZGVycyAqIGltQ2xpZW50cyAqIGludGVyZXN0cyAqIGxvY2FsZXMgKiBsb2NhdGlvbnMgKiBtZW1iZXJzaGlwcyAqIG1ldGFkYXRhICogbWlzY0tleXdvcmRzICogbmFtZXMgKiBuaWNrbmFtZXMgKiBvY2N1cGF0aW9ucyAqIG9yZ2FuaXphdGlvbnMgKiBwaG9uZU51bWJlcnMgKiBwaG90b3MgKiByZWxhdGlvbnMgKiBzaXBBZGRyZXNzZXMgKiBza2lsbHMgKiB1cmxzICogdXNlckRlZmluZWRcbiAgICAgICAgICAgIHBlcnNvbkZpZWxkczpcbiAgICAgICAgICAgICAgJ25hbWVzLG5pY2tuYW1lcyxvcmdhbml6YXRpb25zLGJpb2dyYXBoaWVzLGNvdmVyUGhvdG9zLG1ldGFkYXRhLGVtYWlsQWRkcmVzc2VzLGltQ2xpZW50cyx1cmxzJyxcbiAgICAgICAgICAgIC8vIFJlcXVpcmVkLiBDb21tYS1zZXBhcmF0ZWQgbGlzdCBvZiBwZXJzb24gZmllbGRzIHRvIGJlIGluY2x1ZGVkIGluIHRoZSByZXNwb25zZS4gRWFjaCBwYXRoIHNob3VsZCBzdGFydCB3aXRoIGBwZXJzb24uYDogZm9yIGV4YW1wbGUsIGBwZXJzb24ubmFtZXNgIG9yIGBwZXJzb24ucGhvdG9zYC5cbiAgICAgICAgICAgIC8vICdyZXF1ZXN0TWFzay5pbmNsdWRlRmllbGQnOiAncGVyc29uLm5hbWVzLHBlcnNvbi5uaWNrbmFtZXMscGVyc29uLm9yZ2FuaXphdGlvbnMscGVyc29uLmJpb2dyYXBoaWVzLHBlcnNvbi5jb3ZlclBob3RvcyxwZXJzb24ubWV0YWRhdGEscGVyc29uLmVtYWlsQWRkcmVzc2VzLHBlcnNvbi5pbUNsaWVudHMscGVyc29uLnVybHMnLFxuICAgICAgICAgICAgLy8gUmVxdWlyZWQuIFRoZSByZXNvdXJjZSBuYW1lIHRvIHJldHVybiBjb25uZWN0aW9ucyBmb3IuIE9ubHkgYHBlb3BsZS9tZWAgaXMgdmFsaWQuXG4gICAgICAgICAgICByZXNvdXJjZU5hbWU6ICdwZW9wbGUvbWUnLFxuICAgICAgICAgIH07XG5cbiAgICAgICAgICBpZiAocGFnZVRva2VuKSB7XG4gICAgICAgICAgICB2YXJpYWJsZXMucGFnZVRva2VuID0gcGFnZVRva2VuO1xuICAgICAgICAgICAgY29uc3QgcmVzID0gYXdhaXQgZ29vZ2xlUGVvcGxlLnBlb3BsZS5jb25uZWN0aW9ucy5saXN0KHZhcmlhYmxlcyk7XG4gICAgICAgICAgICBjb25zb2xlLmxvZyhyZXMuZGF0YSk7XG5cbiAgICAgICAgICAgIGNvbnN0IHsgY29ubmVjdGlvbnMsIG5leHRQYWdlVG9rZW4sIG5leHRTeW5jVG9rZW4gfSA9IHJlcy5kYXRhO1xuXG4gICAgICAgICAgICBsb2NhbENvbm5lY3Rpb25zID0gY29ubmVjdGlvbnM7XG4gICAgICAgICAgICBwYWdlVG9rZW4gPSBuZXh0UGFnZVRva2VuO1xuICAgICAgICAgICAgLy8gdG9rZW5zIGluIGNhc2Ugc29tZXRoaW5nIGdvZXMgd3JvbmdcbiAgICAgICAgICAgIC8vIHVwZGF0ZSBwYWdlVG9rZW4gYW5kIHN5bmNUb2tlblxuXG4gICAgICAgICAgICBhd2FpdCB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbihcbiAgICAgICAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgICAgICAgICBuZXh0U3luY1Rva2VuLFxuICAgICAgICAgICAgICBuZXh0UGFnZVRva2VuXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgY29uc3QgZGVsZXRlZFBlb3BsZSA9IChsb2NhbENvbm5lY3Rpb25zIGFzIFBlcnNvblR5cGVbXSk/LmZpbHRlcihcbiAgICAgICAgICAgICAgKGUpID0+IGU/Lm1ldGFkYXRhPy5kZWxldGVkID09PSB0cnVlXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICBpZiAoZGVsZXRlZFBlb3BsZT8uWzBdPy5uYW1lcz8uWzBdKSB7XG4gICAgICAgICAgICAgIGF3YWl0IGRlbGV0ZUNvbnRhY3RzKGRlbGV0ZWRQZW9wbGUgYXMgUGVyc29uVHlwZVtdKTtcbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgY29uc3QgcGVvcGxlVG9VcHNlcnQyID0gKGxvY2FsQ29ubmVjdGlvbnMgYXMgUGVyc29uVHlwZVtdKT8uZmlsdGVyKFxuICAgICAgICAgICAgICAoZSkgPT4gZT8ubWV0YWRhdGE/LmRlbGV0ZWQgIT09IHRydWVcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBpZiAocGVvcGxlVG9VcHNlcnQyPy5bMF0/Lm5hbWVzPy5bMF0pIHtcbiAgICAgICAgICAgICAgYXdhaXQgdXBzZXJ0Q29udGFjdHMyKHBlb3BsZVRvVXBzZXJ0MiBhcyBQZXJzb25UeXBlW10sIHVzZXJJZCk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICB9XG5cbiAgICAgICAgYXdhaXQgdXBzZXJ0Q29udGFjdHMyKHBlb3BsZVRvVXBzZXJ0IGFzIFBlcnNvblR5cGVbXSwgdXNlcklkKTtcbiAgICAgIH1cbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkbyBpbml0aWFsIGdvb2dsZSBzeW5jJyk7XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9XG59O1xuXG5jb25zdCByZXNldEdvb2dsZUludGVncmF0aW9uU3luY0ZvckNvbnRhY3RzID0gYXN5bmMgKFxuICBjYWxlbmRhckludGVncmF0aW9uSWQ6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAndXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbic7XG4gICAgY29uc3QgcXVlcnkgPSBgbXV0YXRpb24gdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbigkaWQ6IHV1aWQhLCAkY2hhbmdlczogQ2FsZW5kYXJfSW50ZWdyYXRpb25fc2V0X2lucHV0KSB7XG4gICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiAkY2hhbmdlcykge1xuICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgc3luY1Rva2VuXG4gICAgICAgIGNsaWVudFR5cGVcbiAgICAgIH1cbiAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZDogY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgY2hhbmdlczoge1xuICAgICAgICBwYWdlVG9rZW46IG51bGwsXG4gICAgICAgIHN5bmNUb2tlbjogbnVsbCxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiB7XG4gICAgICBkYXRhOiB7IHVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wazogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGUgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgdGhpcyBpcyByZXNwb25zZSBpbiByZXNldEdvb2dsZUludGVncmF0aW9uU3luYycpO1xuICAgIC8vIGNvbnN0IHsgdG9rZW46IGF1dGhUb2tlbiB9ID0gYXdhaXQgZ2V0R29vZ2xlSW50ZWdyYXRpb24oY2FsZW5kYXJJbnRlZ3JhdGlvbklkKVxuICAgIHJldHVybiBpbml0aWFsR29vZ2xlQ29udGFjdHNTeW5jMihcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgIHVzZXJJZCxcbiAgICAgIHJlc3BvbnNlPy5kYXRhPy51cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGs/LmNsaWVudFR5cGVcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcmVzZXQgZ29vZ2xlIGludGVncmF0aW9uIHN5bmMnKTtcbiAgfVxufTtcblxuY29uc3QgZ2V0R29vZ2xlSW50ZWdyYXRpb24gPSBhc3luYyAoY2FsZW5kYXJJbnRlZ3JhdGlvbklkOiBzdHJpbmcpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldENhbGVuZGFySW50ZWdyYXRpb24nO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYHF1ZXJ5IGdldENhbGVuZGFySW50ZWdyYXRpb24oJGlkOiB1dWlkISl7XG4gICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wayhpZDogJGlkKSB7XG4gICAgICAgIGlkXG4gICAgICAgIG5hbWVcbiAgICAgICAgdG9rZW5cbiAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgIHBhZ2VUb2tlblxuICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgZW5hYmxlZFxuICAgICAgICBjbGllbnRUeXBlXG4gICAgICB9XG4gICAgfWA7XG4gICAgY29uc3QgdmFyaWFibGVzID0geyBpZDogY2FsZW5kYXJJbnRlZ3JhdGlvbklkIH07XG5cbiAgICBjb25zdCByZXNwb25zZToge1xuICAgICAgZGF0YTogeyBDYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wazogQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGUgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGFkbWluU2VjcmV0LFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG4gICAgLy8ganVzdCB0byBjaGVja1xuICAgIGNvbnNvbGUubG9nKHJlc3BvbnNlLCAnIHRoaXMgaXMgcmVzcG9uc2UgaW4gZ2V0R29vZ2xlSW50ZWdyYXRpb24nKTtcbiAgICBpZiAocmVzcG9uc2U/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrKSB7XG4gICAgICBjb25zdCB7XG4gICAgICAgIGRhdGE6IHtcbiAgICAgICAgICBDYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wazoge1xuICAgICAgICAgICAgdG9rZW4sXG4gICAgICAgICAgICBwYWdlVG9rZW4sXG4gICAgICAgICAgICBzeW5jVG9rZW4sXG4gICAgICAgICAgICByZWZyZXNoVG9rZW4sXG4gICAgICAgICAgICBlbmFibGVkLFxuICAgICAgICAgICAgY2xpZW50VHlwZSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSA9IHJlc3BvbnNlO1xuXG4gICAgICByZXR1cm4geyB0b2tlbiwgcGFnZVRva2VuLCBzeW5jVG9rZW4sIHJlZnJlc2hUb2tlbiwgZW5hYmxlZCwgY2xpZW50VHlwZSB9O1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBnb29nbGUgdG9rZW4nKTtcbiAgfVxufTtcblxuY29uc3QgdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24gPSBhc3luYyAoXG4gIGNhbGVuZGFySW50ZWdyYXRpb25JZDogc3RyaW5nLFxuICBzeW5jVG9rZW4/OiBzdHJpbmcsXG4gIHBhZ2VUb2tlbj86IHN0cmluZyxcbiAgc3luY0VuYWJsZWQ/OiBib29sZWFuXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ3VwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24nO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYG11dGF0aW9uIHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oJGlkOiB1dWlkISwke3N5bmNUb2tlbiAhPT0gdW5kZWZpbmVkID8gJyAkc3luY1Rva2VuOiBTdHJpbmcsJyA6ICcnfSR7cGFnZVRva2VuICE9PSB1bmRlZmluZWQgPyAnICRwYWdlVG9rZW46IFN0cmluZywnIDogJyd9JHtzeW5jRW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJyAkc3luY0VuYWJsZWQ6IEJvb2xlYW4sJyA6ICcnfSkge1xuICAgICAgICB1cGRhdGVfQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiB7JHtwYWdlVG9rZW4gIT09IHVuZGVmaW5lZCA/ICdwYWdlVG9rZW46ICRwYWdlVG9rZW4sJyA6ICcnfSAke3N5bmNUb2tlbiAhPT0gdW5kZWZpbmVkID8gJ3N5bmNUb2tlbjogJHN5bmNUb2tlbiwnIDogJyd9ICR7c3luY0VuYWJsZWQgIT09IHVuZGVmaW5lZCA/ICdzeW5jRW5hYmxlZDogJHN5bmNFbmFibGVkLCcgOiAnJ319KSB7XG4gICAgICAgICAgaWRcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgcGFnZVRva2VuXG4gICAgICAgICAgcmVmcmVzaFRva2VuXG4gICAgICAgICAgcmVzb3VyY2VcbiAgICAgICAgICBzeW5jRW5hYmxlZFxuICAgICAgICAgIHRva2VuXG4gICAgICAgICAgc3luY1Rva2VuXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICAgZXhwaXJlc0F0XG4gICAgICAgICAgZW5hYmxlZFxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgbGV0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgaWQ6IGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICB9O1xuXG4gICAgaWYgKHN5bmNUb2tlbj8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFyaWFibGVzID0geyAuLi52YXJpYWJsZXMsIHN5bmNUb2tlbiB9O1xuICAgIH1cblxuICAgIGlmIChwYWdlVG9rZW4/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHZhcmlhYmxlcyA9IHsgLi4udmFyaWFibGVzLCBwYWdlVG9rZW4gfTtcbiAgICB9XG5cbiAgICBpZiAoc3luY0VuYWJsZWQgPT09IGZhbHNlKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7IC4uLnZhcmlhYmxlcywgc3luY0VuYWJsZWQgfTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBhZG1pblNlY3JldCxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgdGhpcyBpcyByZXNwb25zZSBpbiB1cGRhdGVHb29nbGVJbnRlZ3JhdGlvbicpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIGdvb2dsZSBpbnRlZ3JhdGlvbicpO1xuICB9XG59O1xuXG5jb25zdCBoYW5kbGVyID0gYXN5bmMgKHJlcTogUmVxdWVzdCwgcmVzOiBSZXNwb25zZSkgPT4ge1xuICB0cnkge1xuICAgIC8qKlxuICAgICAqIGhhc3VyYSB0cmlnZ2VyIGJvZHk6XG4gICAgICoge1xuICAgICAgICBcInNjaGVkdWxlZF90aW1lXCI6IFwiMjAyMi0wNS0xMlQwMDo0NTowOS40NjdaXCIsXG4gICAgICAgIFwicGF5bG9hZFwiOiBcIntcXFwidXNlcklkXFxcIjogXFxcImZjNWRmNjc0LWI0ZWUtNDNjNy1hZDllLTI5OGFlMGViNjIwOFxcXCIsIFxcXCJmaWxlS2V5XFxcIjogXFxcImZjNWRmNjc0LWI0ZWUtNDNjNy1hZDllLTI5OGFlMGViNjIwOC82NWYxMjU1ZS0wMWU0LTQwNWYtOGE1Yy1lZjQyMmZiOTRjNGIuanNvblxcXCJ9XCIsIC0gc3RyaW5naWZpZWRcbiAgICAgICAgXCJjcmVhdGVkX2F0XCI6IFwiMjAyMi0wNS0xMlQwMDo0NjoxMC44OTAwMjhaXCIsXG4gICAgICAgIFwiaWRcIjogXCIzMjc3ODgwMS04ZjhkLTQzYzItYTcyOS04NjYzM2IzZDcwMWFcIixcbiAgICAgICAgXCJjb21tZW50XCI6IFwiXCJcbiAgICAgIH1cbiAgICAgIFZTXG4gICAgICBheGlvcyBwb3N0IEJvZHkgLSBzdHJpbmdpZmllZFxuICAgICAge1xuICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWQ6IHN0cmluZyxcbiAgICAgICAgdXNlcklkOiBzdHJpbmcsXG4gICAgICAgIGV2ZW50VHJpZ2dlcklkOiBzdHJpbmcsXG4gICAgICAgIGlzSW5pdGlhbFN5bmM6IGJvb2xlYW4sXG4gICAgICB9XG4gICAgICovXG4gICAgY29uc29sZS5sb2coJ2dvb2dsZVBlb3BsZVN5bmMgY2FsbGVkJyk7XG4gICAgbGV0IGNhbGVuZGFySW50ZWdyYXRpb25JZCA9ICcnO1xuICAgIGxldCB1c2VySWQgPSAnJztcbiAgICBsZXQgaXNJbml0aWFsU3luYyA9IGZhbHNlO1xuICAgIGNvbnN0IGJvZHlPYmogPSByZXEuYm9keTtcbiAgICBpZiAodHlwZW9mIGJvZHlPYmo/LnNjaGVkdWxlZF90aW1lID09PSAnc3RyaW5nJykge1xuICAgICAgY29uc29sZS5sb2coYm9keU9iaiwgJyBzY2hlZHVsZWQgdHJpZ2dlcicpO1xuICAgICAgY29uc3QgeyBwYXlsb2FkIH0gPSBib2R5T2JqO1xuICAgICAgY29uc3QgcGF5bG9hZE9iaiA9IEpTT04ucGFyc2UocGF5bG9hZCk7XG4gICAgICBjYWxlbmRhckludGVncmF0aW9uSWQgPSBwYXlsb2FkT2JqLmNhbGVuZGFySW50ZWdyYXRpb25JZDtcbiAgICAgIHVzZXJJZCA9IHBheWxvYWRPYmoudXNlcklkO1xuICAgICAgaXNJbml0aWFsU3luYyA9IHBheWxvYWRPYmo/LmlzSW5pdGlhbFN5bmMgfHwgZmFsc2U7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnN0IGJvZHkgPSByZXEuYm9keTtcbiAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCA9IGJvZHk/LmNhbGVuZGFySW50ZWdyYXRpb25JZDtcbiAgICAgIHVzZXJJZCA9IGJvZHk/LnVzZXJJZDtcbiAgICAgIGlzSW5pdGlhbFN5bmMgPSBib2R5Py5pc0luaXRpYWxTeW5jO1xuICAgIH1cblxuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFjYWxlbmRhckludGVncmF0aW9uSWQgfHwgIXVzZXJJZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCcgY2FsZW5kYXIgaW50ZWdyYXRpb24gaWQgb3IgdXNlciBpZCBpcyBlbXB0eScpO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50VHJpZ2dlciA9XG4gICAgICBhd2FpdCBnZXRFdmVudFRyaWdnZXJCeVJlc291cmNlSWQoZ29vZ2xlUGVvcGxlUmVzb3VyY2UpO1xuXG4gICAgLy8gdmFsaWRhdGVcbiAgICBpZiAoIWlzSW5pdGlhbFN5bmMgJiYgIWV2ZW50VHJpZ2dlcikge1xuICAgICAgY29uc29sZS5sb2coJ25vdCBpbml0aWFsIGFuZCBubyBldmVudFRyaWdnZXIgc28gZG8gbm90aGluZycpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGlmIChldmVudFRyaWdnZXI/LmlkKSB7XG4gICAgICBhd2FpdCBkZWxldGVFdmVudFRyaWdnZXJCeUlkKGV2ZW50VHJpZ2dlcj8uaWQpO1xuICAgIH1cblxuICAgIGxldCBzeW5jRW5hYmxlZCA9IHRydWU7XG5cbiAgICBjb25zdCB7IHBhZ2VUb2tlbiwgc3luY1Rva2VuLCBlbmFibGVkLCBjbGllbnRUeXBlIH0gPVxuICAgICAgYXdhaXQgZ2V0R29vZ2xlSW50ZWdyYXRpb24oY2FsZW5kYXJJbnRlZ3JhdGlvbklkKTtcblxuICAgIGlmICghZW5hYmxlZCkge1xuICAgICAgY29uc29sZS5sb2coJ25vdCBlbmFibGVkIGdvb2dsZSBwZW9wbGUgc3luYycpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cbiAgICAvLyBpZiBpbml0aWFsIHN5bmMgZG8gMTAwIHJlc3V0cyBlbHNlIDEwXG4gICAgaWYgKGlzSW5pdGlhbFN5bmMpIHtcbiAgICAgIHN5bmNFbmFibGVkID0gYXdhaXQgaW5pdGlhbEdvb2dsZUNvbnRhY3RzU3luYzIoXG4gICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICBjbGllbnRUeXBlXG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICBzeW5jRW5hYmxlZCA9IGF3YWl0IGluY3JlbWVudGFsR29vZ2xlQ29udGFjdHNTeW5jMihcbiAgICAgICAgY2FsZW5kYXJJbnRlZ3JhdGlvbklkLFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNsaWVudFR5cGUsXG4gICAgICAgIHN5bmNUb2tlbixcbiAgICAgICAgcGFnZVRva2VuXG4gICAgICApO1xuICAgIH1cblxuICAgIC8vIGlmIHN5bmMgaXMgbm90IGVuYWJsZWQgbGV0IHRoZSB1c2VyIGdvIHRocm91Z2ggb2F1dGggYWdhaW4gaWYgbmVlZGVkXG4gICAgaWYgKHN5bmNFbmFibGVkID09PSBmYWxzZSkge1xuICAgICAgYXdhaXQgdXBkYXRlR29vZ2xlSW50ZWdyYXRpb24oXG4gICAgICAgIGNhbGVuZGFySW50ZWdyYXRpb25JZCxcbiAgICAgICAgdW5kZWZpbmVkLFxuICAgICAgICB1bmRlZmluZWQsXG4gICAgICAgIHN5bmNFbmFibGVkXG4gICAgICApO1xuICAgICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHtcbiAgICAgICAgbWVzc2FnZTogYHN5bmMgaXMgZGlzYWJsZWQgZm9yIGdvb2dsZVBlb3BsZVN5bmNgLFxuICAgICAgICBldmVudDogYm9keU9iaixcbiAgICAgIH0pO1xuICAgIH1cbiAgICAvLyByZWNyZWF0ZSBzY2hlZHVsZWQgZXZlbnQgZm9yIG5leHQgdGltZVxuICAgIGNvbnN0IHJlc3BvbnNlOiB7XG4gICAgICBtZXNzYWdlOiBzdHJpbmc7XG4gICAgICBldmVudF9pZDogc3RyaW5nO1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYU1ldGFkYXRhVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogYWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICB0eXBlOiAnY3JlYXRlX3NjaGVkdWxlZF9ldmVudCcsXG4gICAgICAgICAgYXJnczoge1xuICAgICAgICAgICAgd2ViaG9vazogc2VsZkdvb2dsZVBlb3BsZUFkbWluVXJsLFxuICAgICAgICAgICAgc2NoZWR1bGVfYXQ6IGRheWpzKCkuYWRkKDE0LCAnZCcpLnV0YygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgcGF5bG9hZDogSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICAgICAgICBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgIH0pLFxuICAgICAgICAgICAgaGVhZGVyczogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgbmFtZTogJ1gtSGFzdXJhLUFkbWluLVNlY3JldCcsXG4gICAgICAgICAgICAgICAgdmFsdWU6IGFkbWluU2VjcmV0LFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgbmFtZTogJ1gtSGFzdXJhLVJvbGUnLFxuICAgICAgICAgICAgICAgIHZhbHVlOiAnYWRtaW4nLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgbmFtZTogJ0NvbnRlbnQtVHlwZScsXG4gICAgICAgICAgICAgICAgdmFsdWU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgc3VjY2VzcyByZXNwb25zZSBpbnNpZGUgZ29vZ2xlUGVvcGxlU3luYycpO1xuXG4gICAgYXdhaXQgaW5zZXJ0RXZlbnRUcmlnZ2VycyhbXG4gICAgICB7XG4gICAgICAgIGlkOiByZXNwb25zZT8uZXZlbnRfaWQsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgbmFtZTogZ29vZ2xlUGVvcGxlTmFtZSxcbiAgICAgICAgcmVzb3VyY2U6IGdvb2dsZVBlb3BsZVJlc291cmNlLFxuICAgICAgICByZXNvdXJjZUlkOiBjYWxlbmRhckludGVncmF0aW9uSWQsXG4gICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgY3JlYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgfSxcbiAgICBdKTtcblxuICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7XG4gICAgICBtZXNzYWdlOiBgc3VjY2Vzc2Z1bGx5IHRha2VuIGNhcmUgb2YgZ29vZ2xlQ2FsZW5kYXJ5U3luYyFgLFxuICAgICAgZXZlbnQ6IGJvZHlPYmosXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSBzeW5jIGdvb2dsZSBjYWxlbmRhcicpO1xuXG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAwKS5qc29uKHtcbiAgICAgIG1lc3NhZ2U6IGBlcnJvciBwcm9jZXNzaW5nIGdvb2dsZVBlb3BsZVN5bmM6IG1lc3NhZ2U6ICR7ZT8ubWVzc2FnZX0sIGNvZGU6ICR7ZT8uc3RhdHVzQ29kZX1gLFxuICAgICAgZXZlbnQ6IGUsXG4gICAgfSk7XG4gIH1cbn07XG5cbmV4cG9ydCBkZWZhdWx0IGhhbmRsZXI7XG4iXX0=