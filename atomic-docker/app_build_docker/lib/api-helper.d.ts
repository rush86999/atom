import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
export declare const updateCalendarIntegration: (client: ApolloClient<NormalizedCacheObject>, calIntegId: string, enabled?: boolean, token?: string, refreshToken?: string, expiresAt?: string, clientType?: "ios" | "android" | "web" | "atomic-web") => Promise<any>;
/**
end
 */
