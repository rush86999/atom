import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import listChatMeetingPreferencesType from '@lib/apollo/gql/listChatMeetingPreferencesType';
import upsertChatMeetingPreferences from '@lib/apollo/gql/upsertChatMeetingPreferences';
import { ChatMeetingPreferencesType } from '@lib/dataTypes/ChatMeetingPreferenceType';

export const upsertChatMeetingPreferencesGivenUserId = async (
  client: ApolloClient<NormalizedCacheObject>,
  chatMeetingPreference: ChatMeetingPreferencesType
) => {
  try {
    const { data } = await client.mutate<{
      insert_Chat_Meeting_Preference_one: ChatMeetingPreferencesType;
    }>({
      mutation: upsertChatMeetingPreferences,
      variables: {
        chatMeetingPreference,
      },
    });

    console.log(data, ' data inside upsertChatMeetingPreferences');
  } catch (e) {
    console.log(e, ' unable to upsert chat meeting preferences given userId');
  }
};
export const getChatMeetingPreferences = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
): Promise<ChatMeetingPreferencesType> => {
  try {
    const { data } = await client.query<{
      Chat_Meeting_Preference: ChatMeetingPreferencesType[];
    }>({
      query: listChatMeetingPreferencesType,
      variables: {
        userId,
      },
      fetchPolicy: 'no-cache',
    });
    console.log(data, ' data getChatMeetingPreferences');

    if (data?.Chat_Meeting_Preference?.length > 0) {
      console.log(
        data.Chat_Meeting_Preference[0],
        ' data.Chat_Meeting_Preference[0]'
      );
      return data.Chat_Meeting_Preference[0];
    }
    return null;
  } catch (e) {
    console.log(e, ' unable to get chat meeting preferences');
  }
};
