import { Request, Response } from 'express';
import got from 'got';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import { google } from 'googleapis';

import { PersonType } from '../_libs/types/googlePeopleSync/types';

import {
  googlePeopleName,
  googlePeopleResource,
  hasuraGraphUrl,
  hasuraMetadataUrl,
  selfGooglePeopleAdminUrl,
} from '@google_calendar_sync/_libs/constants';

import {
  deleteEventTriggerById,
  getEventTriggerByResourceId,
  getGoogleAPIToken,
  insertEventTriggers,
} from '@google_calendar_sync/_libs/api-helper';
import { CalendarIntegrationType } from '@google_calendar_sync/_libs/types/googleCalendarSync/types';

dayjs.extend(utc);

const adminSecret = process.env.HASURA_GRAPHQL_ADMIN_SECRET;
// const hasuraGraphUrl = process.env.HASURA_GRAPH_URL
// const hasuraMetadataUrl = process.env.HASURA_METADATA_URL
// const selfGooglePeopleAdminUrl = process.env.SELF_GOOGLE_PEOPLE_ADMIN_UR

// const googlePeople = google.people('v1')
const deleteContacts = async (people: PersonType[]) => {
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
  } catch (e) {
    console.log(e, ' unable to delete contacts');
  }
};

const upsertContacts2 = async (people: PersonType[], userId: string) => {
  try {
    console.log(people, ' people inside upsertContacts2');
    if (!(people?.[0]?.resourceName?.length > 0)) {
      console.log(' no people present to upsert');
      return;
    }
    const formattedPeople = people?.map((p) => ({
      id: p?.resourceName?.replace('people/', ''),
      name:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.displayName || p?.names?.[0]?.displayName,
      firstName:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.givenName || p?.names?.[0]?.givenName,
      middleName:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.middleName || p?.names?.[0]?.middleName,
      lastName:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.familyName || p?.names?.[0]?.familyName,
      namePrefix:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.honorificPrefix || p?.names?.[0]?.honorificPrefix,
      nameSuffix:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.honorificSuffix || p?.names?.[0]?.honorificSuffix,
      nickname:
        p?.nicknames?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.value || p?.nicknames?.[0]?.value,
      phoneticFirstName:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.phoneticGivenName || p?.names?.[0]?.phoneticGivenName,
      phoneticMiddleName:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.phoneticMiddleName || p?.names?.[0]?.phoneticMiddleName,
      phoneticLastName:
        p?.names?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.phoneticFamilyName || p?.names?.[0]?.phoneticFamilyName,
      company:
        p?.organizations?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.name || p?.organizations?.[0]?.name,
      jobTitle:
        p?.organizations?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.title || p?.organizations?.[0]?.title,
      department:
        p?.organizations?.filter((n) => n?.metadata?.primary === true)?.[0]
          ?.department || p?.organizations?.[0]?.department,
      notes:
        p?.biographies?.filter(
          (n) => n?.metadata?.primary === true && n?.contentType === 'TEXT_HTML'
        )?.[0]?.value || p?.biographies?.[0]?.value,
      imageAvailable:
        p?.coverPhotos?.filter((n) => n?.metadata?.primary === true)?.[0]?.url
          ?.length > 0,
      image:
        p?.coverPhotos?.filter((n) => n?.metadata?.primary === true)?.[0]
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
  } catch (e) {
    console.log(e, ' unable to upsertContacts');
  }
};

const incrementalGoogleContactsSync2 = async (
  calendarIntegrationId: string,
  userId: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web',
  parentSyncToken: string,
  parentPageToken?: string
) => {
  try {
    let localConnections: PersonType[] | object = {};
    let pageToken = parentPageToken;
    let syncToken = parentSyncToken;

    const token = await getGoogleAPIToken(
      userId,
      googlePeopleResource,
      clientType
    );

    const googlePeople = google.people({
      version: 'v1',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const variables: any = {
      // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
      pageSize: 1000,
      // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
      personFields:
        'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
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

    console.log(
      connections,
      nextPageToken,
      nextSyncToken,
      ' connections, nextPageToken, nextSyncToken inside incrementalGoogleContactsSync2'
    );

    localConnections = connections;
    pageToken = nextPageToken;
    syncToken = nextSyncToken;

    await updateGoogleIntegration(
      calendarIntegrationId,
      nextSyncToken,
      nextPageToken
    );

    const deletedPeople = (localConnections as PersonType[])?.filter(
      (e) => e?.metadata?.deleted === true
    );

    if (deletedPeople?.[0]?.names) {
      await deleteContacts(deletedPeople as PersonType[]);
    }

    const peopleToUpsert = (localConnections as PersonType[])?.filter(
      (e) => e?.metadata?.deleted !== true
    );

    // no events to upsert check next pagetoken
    if (!(peopleToUpsert?.[0]?.names?.length > 0)) {
      console.log('no events to upsert check next pagetoken');
      const variables: any = {
        // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
        pageSize: 1000,
        // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
        personFields:
          'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
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
        console.log(
          connections,
          nextPageToken,
          nextSyncToken,
          pageToken,
          ' connections, nextPageToken, nextSyncToken, pageToken inside incrementalGoogleContactsSync2'
        );

        localConnections = connections;
        pageToken = nextPageToken;
        syncToken = nextSyncToken;
        // tokens in case something goes wrong
        // update pageToken and syncToken
        await updateGoogleIntegration(
          calendarIntegrationId,
          nextSyncToken,
          nextPageToken
        );
        const deletedPeople = (localConnections as PersonType[])?.filter(
          (e) => e?.metadata?.deleted === true
        );

        if (deletedPeople?.[0]?.names) {
          await deleteContacts(deletedPeople as PersonType[]);
        }

        const peopleToUpsert2 = (localConnections as PersonType[])?.filter(
          (e) => e?.metadata?.deleted !== true
        );
        if (peopleToUpsert2?.[0]?.names?.length > 0) {
          await upsertContacts2(peopleToUpsert2 as PersonType[], userId);
        }
      }
    } else {
      await upsertContacts2(peopleToUpsert as PersonType[], userId);
    }

    if (pageToken) {
      while (pageToken) {
        const variables: any = {
          // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
          pageSize: 1000,
          // Optional. A page token, received from a previous response `next_page_token`. Provide this to retrieve the subsequent page. When paginating, all other parameters provided to `people.connections.list` must match the first call that provided the page token.
          pageToken,
          // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
          personFields:
            'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
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

        console.log(
          connections,
          nextPageToken,
          nextSyncToken,
          pageToken,
          ' connections, nextPageToken, nextSyncToken, pageToken inside incrementalGoogleContactsSync2 part of while loop'
        );

        localConnections = connections;
        pageToken = nextPageToken;
        syncToken = nextSyncToken;
        // tokens in case something goes wrong
        // update pageToken and syncToken

        await updateGoogleIntegration(
          calendarIntegrationId,
          nextSyncToken,
          nextPageToken
        );

        const deletedPeople = (localConnections as PersonType[])?.filter(
          (e) => e?.metadata?.deleted === true
        );

        if (deletedPeople?.[0]?.names) {
          await deleteContacts(deletedPeople as PersonType[]);
        }

        const peopleToUpsert = (localConnections as PersonType[])?.filter(
          (e) => e?.metadata?.deleted !== true
        );

        // no events to upsert check next pagetoken
        if (!(peopleToUpsert?.[0]?.names?.length > 0)) {
          console.log('no events to upsert check next pagetoken');
          const variables: any = {
            // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
            pageSize: 1000,
            // Optional. A page token, received from a previous response `next_page_token`. Provide this to retrieve the subsequent page. When paginating, all other parameters provided to `people.connections.list` must match the first call that provided the page token.
            // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
            personFields:
              'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
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
            await updateGoogleIntegration(
              calendarIntegrationId,
              nextSyncToken,
              nextPageToken
            );
            const deletedPeople = (localConnections as PersonType[])?.filter(
              (e) => e?.metadata?.deleted === true
            );

            if (deletedPeople?.[0]?.names?.[0]) {
              await deleteContacts(deletedPeople as PersonType[]);
            }

            const peopleToUpsert2 = (localConnections as PersonType[])?.filter(
              (e) => e?.metadata?.deleted !== true
            );
            if (peopleToUpsert2?.[0]?.names?.length > 0) {
              await upsertContacts2(peopleToUpsert2 as PersonType[], userId);
            }
          }
          continue;
        }
        await upsertContacts2(peopleToUpsert as PersonType[], userId);
      }
    }
  } catch (e) {
    console.log(e, ' unable to incremental google sync');
    // reset sync
    if (e.code === 410) {
      await resetGoogleIntegrationSyncForContacts(
        calendarIntegrationId,
        userId
      );
      return true;
    }
    return false;
  }
};

const initialGoogleContactsSync2 = async (
  calendarIntegrationId: string,
  userId: string,
  clientType: 'ios' | 'android' | 'web' | 'atomic-web'
) => {
  try {
    let localConnections: PersonType[] | object = {};
    let pageToken = '';
    const token = await getGoogleAPIToken(
      userId,
      googlePeopleResource,
      clientType
    );

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
      personFields:
        'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
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
    console.log(
      connections,
      nextPageToken,
      nextSyncToken,
      ' connections, nextPageToken, nextSyncToken inside initialGoogleContactsSync2'
    );
    localConnections = connections;
    pageToken = nextPageToken;

    await updateGoogleIntegration(
      calendarIntegrationId,
      nextSyncToken,
      nextPageToken
    );

    const deletedPeople = (localConnections as PersonType[])?.filter(
      (e) => e?.metadata?.deleted === true
    );

    if (deletedPeople?.[0]?.names) {
      await deleteContacts(deletedPeople as PersonType[]);
    }

    const peopleToUpsert = (localConnections as PersonType[])?.filter(
      (e) => e?.metadata?.deleted !== true
    );

    // no events to upsert check next pagetoken
    if (!(peopleToUpsert?.[0]?.names?.length > 0)) {
      console.log('no events to upsert check next pagetoken');
      const variables: any = {
        // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
        pageSize: 1000,
        // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
        personFields:
          'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
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

        console.log(
          connections,
          nextPageToken,
          nextSyncToken,
          pageToken,
          ' connections, nextPageToken, nextSyncToken, pageToken inside initialGoogleContactsSync2'
        );

        localConnections = connections;
        pageToken = nextPageToken;
        // tokens in case something goes wrong
        // update pageToken and syncToken

        await updateGoogleIntegration(
          calendarIntegrationId,
          nextSyncToken,
          nextPageToken
        );

        const deletedPeople = (localConnections as PersonType[])?.filter(
          (e) => e?.metadata?.deleted === true
        );

        if (deletedPeople?.[0]?.names?.[0]) {
          await deleteContacts(deletedPeople as PersonType[]);
        }

        const peopleToUpsert2 = (localConnections as PersonType[])?.filter(
          (e) => e?.metadata?.deleted !== true
        );
        if (peopleToUpsert2?.[0]?.names?.[0]) {
          await upsertContacts2(peopleToUpsert2 as PersonType[], userId);
        }
      }
    } else {
      await upsertContacts2(peopleToUpsert as PersonType[], userId);
    }
    if (pageToken) {
      // fetch all pages
      while (pageToken) {
        const variables: any = {
          // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
          pageSize: 1000,
          // Optional. A page token, received from a previous response `next_page_token`. Provide this to retrieve the subsequent page. When paginating, all other parameters provided to `people.connections.list` must match the first call that provided the page token.
          pageToken,
          // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
          personFields:
            'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
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

        console.log(
          connections,
          nextPageToken,
          nextSyncToken,
          pageToken,
          ' connections, nextPageToken, nextSyncToken, pageToken inside initialGoogleContactsSync2 part of while loop'
        );

        localConnections = connections;
        pageToken = nextPageToken;
        // tokens in case something goes wrong
        // update pageToken and syncToken

        await updateGoogleIntegration(
          calendarIntegrationId,
          nextSyncToken,
          nextPageToken
        );

        const deletedPeople = (localConnections as PersonType[])?.filter(
          (e) => e?.metadata?.deleted === true
        );

        if (deletedPeople?.[0]?.names?.[0]) {
          await deleteContacts(deletedPeople as PersonType[]);
        }

        const peopleToUpsert = (localConnections as PersonType[])?.filter(
          (e) => e?.metadata?.deleted !== true
        );

        // no events to upsert check next pagetoken
        if (!(peopleToUpsert?.[0]?.names?.length > 0)) {
          console.log('no events to upsert check next pagetoken');
          const variables: any = {
            // Optional. The number of connections to include in the response. Valid values are between 1 and 1000, inclusive. Defaults to 100 if not set or set to 0.
            pageSize: 1000,
            // Required. A field mask to restrict which fields on each person are returned. Multiple fields can be specified by separating them with commas. Valid values are: * addresses * ageRanges * biographies * birthdays * calendarUrls * clientData * coverPhotos * emailAddresses * events * externalIds * genders * imClients * interests * locales * locations * memberships * metadata * miscKeywords * names * nicknames * occupations * organizations * phoneNumbers * photos * relations * sipAddresses * skills * urls * userDefined
            personFields:
              'names,nicknames,organizations,biographies,coverPhotos,metadata,emailAddresses,imClients,urls',
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

            await updateGoogleIntegration(
              calendarIntegrationId,
              nextSyncToken,
              nextPageToken
            );
            const deletedPeople = (localConnections as PersonType[])?.filter(
              (e) => e?.metadata?.deleted === true
            );

            if (deletedPeople?.[0]?.names?.[0]) {
              await deleteContacts(deletedPeople as PersonType[]);
            }

            const peopleToUpsert2 = (localConnections as PersonType[])?.filter(
              (e) => e?.metadata?.deleted !== true
            );
            if (peopleToUpsert2?.[0]?.names?.[0]) {
              await upsertContacts2(peopleToUpsert2 as PersonType[], userId);
            }
          }
          continue;
        }

        await upsertContacts2(peopleToUpsert as PersonType[], userId);
      }
    }
  } catch (e) {
    console.log(e, ' unable to do initial google sync');
    return false;
  }
};

const resetGoogleIntegrationSyncForContacts = async (
  calendarIntegrationId: string,
  userId: string
) => {
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

    const response: {
      data: { update_Calendar_Integration_by_pk: CalendarIntegrationType };
    } = await got
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
    return initialGoogleContactsSync2(
      calendarIntegrationId,
      userId,
      response?.data?.update_Calendar_Integration_by_pk?.clientType
    );
  } catch (e) {
    console.log(e, ' unable to reset google integration sync');
  }
};

const getGoogleIntegration = async (calendarIntegrationId: string) => {
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

    const response: {
      data: { Calendar_Integration_by_pk: CalendarIntegrationType };
    } = await got
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
      const {
        data: {
          Calendar_Integration_by_pk: {
            token,
            pageToken,
            syncToken,
            refreshToken,
            enabled,
            clientType,
          },
        },
      } = response;

      return { token, pageToken, syncToken, refreshToken, enabled, clientType };
    }
  } catch (e) {
    console.log(e, ' unable to get google token');
  }
};

const updateGoogleIntegration = async (
  calendarIntegrationId: string,
  syncToken?: string,
  pageToken?: string,
  syncEnabled?: boolean
) => {
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
    let variables: any = {
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
  } catch (e) {
    console.log(e, ' unable to update google integration');
  }
};

const handler = async (req: Request, res: Response) => {
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
    } else {
      const body = req.body;
      calendarIntegrationId = body?.calendarIntegrationId;
      userId = body?.userId;
      isInitialSync = body?.isInitialSync;
    }

    // validate
    if (!calendarIntegrationId || !userId) {
      throw new Error(' calendar integration id or user id is empty');
    }

    const eventTrigger =
      await getEventTriggerByResourceId(googlePeopleResource);

    // validate
    if (!isInitialSync && !eventTrigger) {
      console.log('not initial and no eventTrigger so do nothing');
      return;
    }

    if (eventTrigger?.id) {
      await deleteEventTriggerById(eventTrigger?.id);
    }

    let syncEnabled = true;

    const { pageToken, syncToken, enabled, clientType } =
      await getGoogleIntegration(calendarIntegrationId);

    if (!enabled) {
      console.log('not enabled google people sync');
      return;
    }
    // if initial sync do 100 resuts else 10
    if (isInitialSync) {
      syncEnabled = await initialGoogleContactsSync2(
        calendarIntegrationId,
        userId,
        clientType
      );
    } else {
      syncEnabled = await incrementalGoogleContactsSync2(
        calendarIntegrationId,
        userId,
        clientType,
        syncToken,
        pageToken
      );
    }

    // if sync is not enabled let the user go through oauth again if needed
    if (syncEnabled === false) {
      await updateGoogleIntegration(
        calendarIntegrationId,
        undefined,
        undefined,
        syncEnabled
      );
      return res.status(200).json({
        message: `sync is disabled for googlePeopleSync`,
        event: bodyObj,
      });
    }
    // recreate scheduled event for next time
    const response: {
      message: string;
      event_id: string;
    } = await got
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
  } catch (e) {
    console.log(e, ' unable sync google calendar');

    return res.status(400).json({
      message: `error processing googlePeopleSync: message: ${e?.message}, code: ${e?.statusCode}`,
      event: e,
    });
  }
};

export default handler;
