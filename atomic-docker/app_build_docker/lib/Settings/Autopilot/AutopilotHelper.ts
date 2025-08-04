import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import deleteAutopilotsByUserId from '@lib/apollo/gql/deleteAutopilotsByUserId';
import listAutopilotsGivenUserId from '@lib/apollo/gql/listAutopilotsGivenUserId';
import upsertAutopilotMany from '@lib/apollo/gql/upsertAutopilotMany';
import {
  AutopilotType,
  ScheduleAssistWithMeetingQueueBodyType,
} from '@lib/dataTypes/AutopilotType';
import {
  addDailyFeaturesAutopilotProdUrl,
  deleteScheduledEventProdUrl,
} from '@lib/Settings/Autopilot/constants';
import { AddDailyFeaturesApplyEventTriggerType } from '@lib/Settings/Autopilot/types';
import Session from 'supertokens-web-js/recipe/session';
import axios from 'axios';

export const deleteScheduledEvent = async (eventId: string) => {
  try {
    const url = deleteScheduledEventProdUrl;
    const data = eventId;

    const accessToken = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    };

    const res = await axios.post(url, data, config);
  } catch (e) {
    console.log(e, ' unable to delete scheduled event');
  }
};

export const triggerAddDailyFeaturesApplyUrl = async (
  autopilot: AutopilotType,
  body: ScheduleAssistWithMeetingQueueBodyType
) => {
  try {
    const url = addDailyFeaturesAutopilotProdUrl;

    const data: AddDailyFeaturesApplyEventTriggerType = {
      autopilot,
      body,
    };

    const accessToken = await Session.getAccessToken();

    const config = {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
    };

    const results = await axios.post(url, data, config);

    console.log(results, ' successfully triggered add daily features apply');
  } catch (e) {
    console.log(e, ' unable to trigger add daily features apply url');
  }
};

export const deleteAutopilotsGivenUserId = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const affectedRows = (
      await client.mutate<{
        delete_Autopilot: { affected_rows: number; returning: AutopilotType[] };
      }>({
        mutation: deleteAutopilotsByUserId,
        variables: {
          userId,
        },
      })
    )?.data?.delete_Autopilot?.affected_rows;

    console.log(affectedRows, ' successfully deleted autopilots');
  } catch (e) {
    console.log(e, ' unable to delete many autopilots');
  }
};

export const upsertManyAutopilot = async (
  client: ApolloClient<NormalizedCacheObject>,
  autopilots: AutopilotType[]
) => {
  try {
    const affectedRows = (
      await client.mutate<{
        insert_Autopilot: { affected_rows: number; returning: AutopilotType[] };
      }>({
        mutation: upsertAutopilotMany,
        variables: {
          autopilots,
        },
      })
    )?.data?.insert_Autopilot?.affected_rows;

    console.log(affectedRows, ' successfully upserted many autopilots');
  } catch (e) {
    console.log(e, ' unable to upsert autopilot many');
  }
};

export const listAutopilotsByUserId = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const autopilotsDoc = (
      await client.query<{ Autopilot: AutopilotType[] }>({
        query: listAutopilotsGivenUserId,
        variables: {
          userId,
        },
        fetchPolicy: 'no-cache',
      })
    )?.data?.Autopilot;

    return autopilotsDoc;
  } catch (e) {
    console.log(e, ' unable to list autopilots by userId');
  }
};
