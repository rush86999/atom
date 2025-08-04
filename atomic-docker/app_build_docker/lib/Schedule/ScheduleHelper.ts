import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import { getCalendarInDb } from '@lib/Calendar/UserCreateCalendarHelper';

export const getGlobalPrimaryCalendarFunction = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    // get global primary calendar
    return getCalendarInDb(client, userId, undefined, true);
  } catch (e) {
    console.log(e, ' getGlobalPrimaryCalendarFunction');
  }
};

import { scheduleMeeting as callScheduleMeetingApi } from '@lib/api-backend-helper';
import { ScheduleMeetingRequestType } from '@lib/dataTypes/ScheduleMeetingRequestType';

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
export const requestScheduleMeeting = async (
  client: ApolloClient<NormalizedCacheObject>, // Maintained for API consistency, not directly used unless for session/auth
  userId: string, // Maintained for future use (e.g., logging, auth context)
  participantNames: string[],
  durationMinutes: number,
  preferredDate: string,
  preferredStartTimeFrom: string,
  preferredStartTimeTo: string
): Promise<any> => {
  // eslint-disable-line @typescript-eslint/no-explicit-any
  try {
    console.log(
      `requestScheduleMeeting called by userId: ${userId} with params:`,
      {
        participantNames,
        durationMinutes,
        preferredDate,
        preferredStartTimeFrom,
        preferredStartTimeTo,
      }
    );

    const payload: ScheduleMeetingRequestType = {
      participantNames,
      durationMinutes,
      preferredDate,
      preferredStartTimeFrom,
      preferredStartTimeTo,
    };

    // Note: The current `callScheduleMeetingApi` in api-backend-helper.ts doesn't take userId or client.
    // If authentication or user context is needed at the `got` call level,
    // `api-backend-helper.ts` will need to be updated.
    const response = await callScheduleMeetingApi(payload);

    console.log('Meeting scheduling requested successfully:', response);
    return response;
  } catch (error) {
    console.error('Error in requestScheduleMeeting helper:', error);
    // Propagate the error so the caller can handle it
    throw error;
  }
};
