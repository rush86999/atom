import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { AutopilotType, ScheduleAssistWithMeetingQueueBodyType } from '@lib/dataTypes/AutopilotType';
export declare const deleteScheduledEvent: (eventId: string) => Promise<void>;
export declare const triggerAddDailyFeaturesApplyUrl: (autopilot: AutopilotType, body: ScheduleAssistWithMeetingQueueBodyType) => Promise<void>;
export declare const deleteAutopilotsGivenUserId: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<void>;
export declare const upsertManyAutopilot: (client: ApolloClient<NormalizedCacheObject>, autopilots: AutopilotType[]) => Promise<void>;
export declare const listAutopilotsByUserId: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<any>;
