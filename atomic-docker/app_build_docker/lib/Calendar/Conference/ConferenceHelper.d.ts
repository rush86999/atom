import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
export declare const deleteConferencesWithIds: (client: ApolloClient<NormalizedCacheObject>, ids: string[]) => Promise<void>;
