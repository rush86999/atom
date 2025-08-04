import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import deleteConferencesByIds from '@lib/apollo/gql/deleteConferencesByIds';

export const deleteConferencesWithIds = async (
  client: ApolloClient<NormalizedCacheObject>,
  ids: string[]
) => {
  try {
    const res = await client.mutate<{
      delete_Conference: { affected_rows: number };
    }>({
      mutation: deleteConferencesByIds,
      variables: {
        ids,
      },
    });

    console.log(
      res?.data?.delete_Conference?.affected_rows,
      'successfully removed conferences for event'
    );
  } catch (e) {
    console.log(e, ' unable to remove attendees for event');
  }
};
