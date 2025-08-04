import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
export declare const getGlobalPrimaryCalendarFunction: (client: ApolloClient<NormalizedCacheObject>, userId: string) => Promise<any>;
/**
 * Helper function to request scheduling a new meeting.
 * This function constructs the request payload and calls the backend API.
 * @param client ApolloClient instance (currently unused but kept for consistency or future use with session/auth)
 * @param userId The ID of the user initiating the request (currently unused, might be needed for auth)
 * @param participantNames Array of participant names or IDs
 * @param durationMinutes Duration of the meeting in minutes
 * @param preferredDate Preferred date in YYYY-MM-DD format
 * @param preferredTime Preferred time in HH:MM:SS format
 * @returns Promise<any> The response from the scheduling API.
 */
export declare const requestScheduleMeeting: (client: ApolloClient<NormalizedCacheObject>, // Maintained for API consistency, not directly used unless for session/auth
userId: string, // Maintained for future use (e.g., logging, auth context)
participantNames: string[], durationMinutes: number, preferredDate: string, preferredStartTimeFrom: string, preferredStartTimeTo: string) => Promise<any>;
