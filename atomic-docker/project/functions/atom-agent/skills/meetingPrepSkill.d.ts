import { MeetingPrepNluEntities, AggregatedPrepResults } from '../types';
/**
 * Fetches and aggregates information from various sources in preparation for a meeting.
 *
 * @param userId The ID of the user for whom the preparation is being done.
 * @param nluEntities The parsed NLU entities from the RequestMeetingPreparation intent.
 * @returns A promise that resolves to AggregatedPrepResults containing all fetched information.
 */
export declare function fetchMeetingPrepInfo(userId: string, nluEntities: MeetingPrepNluEntities): Promise<AggregatedPrepResults>;
