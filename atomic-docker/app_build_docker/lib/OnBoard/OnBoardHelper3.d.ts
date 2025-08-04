import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { ChatMeetingPreferencesType } from '@lib/dataTypes/ChatMeetingPreferenceType';
export declare const upsertChatMeetingPreferencesGivenUserId: (client: ApolloClient<NormalizedCacheObject>, chatMeetingPreference: ChatMeetingPreferencesType) => Promise<void>;
export declare const getChatMeetingPreferences: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<ChatMeetingPreferencesType>;
