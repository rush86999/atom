import { ApolloClient, NormalizedCacheObject, gql } from '@apollo/client';
import { EventType, Time } from '@lib/dataTypes/EventType';
import { methodToSearchIndexAuthUrl } from '@lib/constants';
import Session from 'supertokens-web-js/recipe/session';
import axios from 'axios';

import { esResponseBody } from '@lib/Calendar/types';
import listPreferredTimeRangesByEventId from '@lib/apollo/gql/listPreferredTimeRangesByEventId';
import insertPreferredTimeRanges from '@lib/apollo/gql/insertPreferredTimeRanges';
import { PreferredTimeRangeType } from '@lib/dataTypes/PreferredTimeRangeType';
import deletePreferredTimeRangesByEventId from '@lib/apollo/gql/deletePreferredTimeRangesByEventId';
import deletePreferredTimeRangeById from '@lib/apollo/gql/deletePreferredTimeRangeById';
import insertPreferredTimeRange from '@lib/apollo/gql/insertPreferredTimeRange';

export const dayOfWeekIntToString = {
  1: 'MONDAY',
  2: 'TUESDAY',
  3: 'WEDNESDAY',
  4: 'THURSDAY',
  5: 'FRIDAY',
  6: 'SATURDAY',
  7: 'SUNDAY',
};

export const addToSearchIndex = async (event: EventType) => {
  try {
    // text format: `${summary}: ${notes}`
    /**
     * 1. search for event if it exists
     * 2. if it exists, delete
     * 3. add it
     */

    const url = methodToSearchIndexAuthUrl;
    const token = await Session.getAccessToken();
    const config = {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    };

    // search
    // response = res.hits.hits?.[0]
    const searchData = {
      search: `${event?.summary}${event?.notes ? `: ${event?.notes}` : ''}`,
      method: 'search',
    };
    const results = await axios.post<{
      message: string;
      event: esResponseBody;
    }>(url, searchData, config);

    console.log(results, ' results inside addToSearchIndex');

    // if it exists, delete
    if (results?.data?.event?.hits?.hits?.[0]?._id) {
      console.log('event exists, delete it');
      const deleteData = {
        eventId: results?.data?.event?.hits?.hits?.[0]?._id,
        method: 'delete',
      };

      const deleteResults = await axios.post<{
        message: string;
        event: object;
      }>(url, deleteData, config);
      console.log(deleteResults, ' deleteResults in search');
    }

    // add it
    const addData = {
      eventId: event?.id,
      userId: event?.userId,
      eventDetails: `${event?.summary}: ${event?.notes}`,
      method: 'create',
    };

    const res = await axios.post<{ message: string; event: EventType }>(
      url,
      addData,
      config
    );
    console.log(res, ' addToSearchIndex res');
    return res.data.event;
  } catch (e) {
    console.log(e, ' unable to add to open search index');
  }
};

export const insertPreferredTimeRangeOneForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string,
  eventId: string,
  startTime: Time,
  endTime: Time,
  dayOfWeek: number,
  userId: string,
  createdDate: string,
  updatedAt: string,
  toast?: any
) => {
  try {
    console.log(
      id,
      eventId,
      startTime,
      endTime,
      dayOfWeek,
      createdDate,
      updatedAt,
      ' id, eventId, startTime, endTime, dayOfWeek, createdDate, updatedAt, insertPreferredTimeRangeOneForEvent'
    );
    // validate startTime and endTime
    if (!startTime || !endTime) {
      throw new Error('startTime and endTime are required');
    }

    if (startTime > endTime) {
      if (toast) {
        toast({
          title: 'Oops...',
          description: 'Start time must be before end time',
          status: 'error',
          duration: 9000,
          isClosable: true,
        });
      }
      throw new Error('Start time must be before end time');
    }

    if (!eventId) {
      throw new Error('Event ID is required');
    }

    if (!id) {
      throw new Error('ID is required');
    }

    if (!createdDate) {
      throw new Error('Created date is required');
    }

    if (!updatedAt) {
      throw new Error('Updated date is required');
    }

    if (!userId) {
      throw new Error('userId is required');
    }

    const { data } = await client.mutate<{
      insert_PreferredTimeRange_one: PreferredTimeRangeType;
    }>({
      mutation: insertPreferredTimeRange,
      variables: {
        preferredTimeRange: {
          id,
          eventId,
          startTime,
          endTime,
          dayOfWeek: dayOfWeek === -1 ? null : dayOfWeek,
          userId,
          createdDate,
          updatedAt,
        },
      },
      fetchPolicy: 'no-cache',
    });
    return data.insert_PreferredTimeRange_one;
  } catch (e) {
    console.log(e, ' unable to insert preferred time range');
  }
};

export const insertPreferredTimeRangesForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  preferredTimeRanges: PreferredTimeRangeType[]
) => {
  try {
    const { data } = await client.mutate<{
      insert_PreferredTimeRange: {
        affected_rows: number;
        returning: PreferredTimeRangeType[];
      };
    }>({
      mutation: insertPreferredTimeRanges,
      variables: {
        preferredTimeRanges,
      },
    });
    console.log(data, ' data in insertPreferredTimeRangesForEvent');
    return data.insert_PreferredTimeRange.returning;
  } catch (e) {
    console.log(e, ' unable to insertPreferredTimeRangesForEvent');
  }
};

export const deletePreferredTimeRangeWithId = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string
) => {
  try {
    const { data } = await client.mutate<{
      delete_PreferredTimeRange_by_pk: PreferredTimeRangeType;
    }>({
      mutation: deletePreferredTimeRangeById,
      variables: {
        id,
      },
    });
    console.log(data, ' data in deletePreferredTimeRangeWithId');
    return data.delete_PreferredTimeRange_by_pk;
  } catch (e) {
    console.log(e, ' unable to deletePreferredTimeRangeWithId');
  }
};

export const deletePreferredTimeRangesByEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string
) => {
  try {
    const res = await client.mutate({
      mutation: deletePreferredTimeRangesByEventId,
      variables: {
        eventId,
      },
    });
    console.log(res, ' deletePreferredTimeRangesByEvent res');
    return res.data.delete_PreferredTimeRange.affected_rows;
  } catch (e) {
    console.log(e, ' unable to delete preferred time ranges');
  }
};

export const listPreferredTimeRangesByEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string
) => {
  try {
    const { data } = await client.query<{
      PreferredTimeRange: PreferredTimeRangeType[];
    }>({
      query: listPreferredTimeRangesByEventId,
      variables: {
        eventId: eventId,
      },
      fetchPolicy: 'no-cache',
    });
    return data.PreferredTimeRange;
  } catch (e) {
    console.log(e, ' unable to list preferred time ranges');
  }
};

export const trainEventForPlanning = async (
  client: ApolloClient<NormalizedCacheObject>,
  id: string,
  // enablePreferredTime: boolean,
  // preferredTimeType: PreferredTimeTypeType,
  // preferredDayOfWeek?: number | null,
  // preferredTime?: Time | null,
  // preferredStartTimeRange?: Time | null,
  // preferredEndTimeRange?: Time | null,
  copyAvailability?: boolean | null,
  copyTimeBlocking?: boolean | null,
  copyTimePreference?: boolean | null,
  copyReminders?: boolean | null,
  copyPriorityLevel?: boolean | null,
  copyModifiable?: boolean | null,
  copyCategories?: boolean | null,
  copyIsBreak?: boolean | null,
  copyIsMeeting?: boolean | null,
  copyIsExternalMeeting?: boolean | null,
  copyDuration?: boolean | null,
  copyColor?: boolean | null
) => {
  try {
    /**
         *                 # ${!enablePreferredTime ? '' : preferredDayOfWeek !== undefined ? '$preferredDayOfWeek: Int,' : ''} 
                # ${!enablePreferredTime ? '' : preferredTimeType === 'preferredTimeRange' ? '$preferredEndTimeRange: time,' : ''}
                # ${!enablePreferredTime ? '' : preferredTimeType === 'preferredTime' ? '$preferredTime: time,' : ''}
                # ${!enablePreferredTime ? '' : preferredTimeType === 'preferredTimeRange' ? '$preferredStartTimeRange: time,' : ''}

                 # ${!enablePreferredTime ? 'preferredDayOfWeek: null,' : 'preferredDayOfWeek: $preferredDayOfWeek,'} 
                    # ${!enablePreferredTime ? 'preferredEndTimeRange: null,' : preferredTimeType === 'preferredTimeRange' ? 'preferredEndTimeRange: $preferredEndTimeRange,' : ''} 
                    # ${!enablePreferredTime ? 'preferredTime: null,' : preferredTimeType === 'preferredTime' ? 'preferredTime: $preferredTime,' : ''} 
                    # ${!enablePreferredTime ? 'preferredStartTimeRange : null,' : preferredTimeType === 'preferredTimeRange' ? 'preferredStartTimeRange: $preferredStartTimeRange,' : ''} 
         */
    const trainEventMutation = gql`
            mutation UpdateEventForTraining($id: String!,
                ${copyAvailability !== undefined ? '$copyAvailability: Boolean,' : ''}
                ${copyTimeBlocking !== undefined ? '$copyTimeBlocking: Boolean,' : ''}
                ${copyTimePreference !== undefined ? '$copyTimePreference: Boolean,' : ''}
                ${copyReminders !== undefined ? '$copyReminders: Boolean,' : ''}
                ${copyPriorityLevel !== undefined ? '$copyPriorityLevel: Boolean,' : ''}
                ${copyModifiable !== undefined ? '$copyModifiable: Boolean,' : ''}
                ${copyCategories !== undefined ? '$copyCategories: Boolean,' : ''}
                ${copyIsBreak !== undefined ? '$copyIsBreak: Boolean,' : ''}
                ${copyIsMeeting !== undefined ? '$copyIsMeeting: Boolean,' : ''}
                ${copyIsExternalMeeting !== undefined ? '$copyIsExternalMeeting: Boolean,' : ''}
                ${copyDuration !== undefined ? '$copyDuration: Boolean,' : ''}
                ${copyColor !== undefined ? '$copyColor: Boolean,' : ''}
            ) {
                update_Event_by_pk(
                    pk_columns: {id: $id}, 
                    _set: {
                        ${copyAvailability !== undefined ? 'copyAvailability: $copyAvailability,' : ''} 
                        ${copyTimeBlocking !== undefined ? 'copyTimeBlocking: $copyTimeBlocking,' : ''} 
                        ${copyTimePreference !== undefined ? 'copyTimePreference: $copyTimePreference,' : ''} 
                        ${copyReminders !== undefined ? 'copyReminders: $copyReminders,' : ''} 
                        ${copyPriorityLevel !== undefined ? 'copyPriorityLevel: $copyPriorityLevel,' : ''} 
                        ${copyModifiable !== undefined ? 'copyModifiable: $copyModifiable,' : ''} 
                        ${copyCategories !== undefined ? 'copyCategories: $copyCategories,' : ''} 
                        ${copyIsBreak !== undefined ? 'copyIsBreak: $copyIsBreak,' : ''} 
                        ${copyIsMeeting !== undefined ? 'copyIsMeeting: $copyIsMeeting,' : ''} 
                        ${copyIsExternalMeeting !== undefined ? 'copyIsExternalMeeting: $copyIsExternalMeeting,' : ''} 
                        ${copyDuration !== undefined ? 'copyDuration: $copyDuration,' : ''} 
                        ${copyColor !== undefined ? 'copyColor: $copyColor,' : ''}
                    }) {
                        id
                        startDate
                        endDate
                        allDay
                        recurrence
                        recurrenceRule
                        location
                        notes
                        attachments
                        links
                        timezone
                        taskId
                        taskType
                        priority
                        followUpEventId
                        isFollowUp
                        isPreEvent
                        isPostEvent
                        preEventId
                        postEventId
                        modifiable
                        forEventId
                        conferenceId
                        maxAttendees
                        attendeesOmitted
                        sendUpdates
                        anyoneCanAddSelf
                        guestsCanInviteOthers
                        guestsCanSeeOtherGuests
                        originalStartDate
                        originalTimezone
                        originalAllDay
                        status
                        summary
                        transparency
                        visibility
                        recurringEventId
                        iCalUID
                        htmlLink
                        colorId
                        creator
                        organizer
                        endTimeUnspecified
                        extendedProperties
                        hangoutLink
                        guestsCanModify
                        locked
                        source
                        eventType
                        privateCopy
                        backgroundColor
                        foregroundColor
                        useDefaultAlarms
                        deleted
                        createdDate
                        updatedAt
                        userId
                        calendarId
                        positiveImpactScore
                        negativeImpactScore
                        positiveImpactDayOfWeek
                        positiveImpactTime
                        negativeImpactDayOfWeek
                        negativeImpactTime
                        preferredDayOfWeek
                        preferredTime
                        isExternalMeeting
                        isExternalMeetingModifiable
                        isMeetingModifiable
                        isMeeting
                        dailyTaskList
                        weeklyTaskList
                        isBreak
                        preferredStartTimeRange
                        preferredEndTimeRange
                        copyAvailability
                        copyTimeBlocking
                        copyTimePreference
                        copyReminders
                        copyPriorityLevel
                        copyModifiable
                        copyCategories
                        copyIsBreak
                        userModifiedAvailability
                        userModifiedTimeBlocking
                        userModifiedTimePreference
                        userModifiedReminders
                        userModifiedPriorityLevel
                        userModifiedCategories
                        userModifiedModifiable
                        userModifiedIsBreak
                        hardDeadline
                        softDeadline
                        copyIsMeeting
                        copyIsExternalMeeting
                        userModifiedIsMeeting
                        userModifiedIsExternalMeeting
                        duration
                        copyDuration
                        userModifiedDuration
                        method
                        unlink
                        copyColor
                        userModifiedColor
                        byWeekDay
                        localSynced
                        title
                        timeBlocking
                        meetingId
                        eventId
                }
            }
        `;

    let variables: any = {
      id: id,
    };

    if (copyAvailability !== undefined) {
      variables = {
        ...variables,
        copyAvailability: copyAvailability,
      };
    }

    if (copyTimeBlocking !== undefined) {
      variables = {
        ...variables,
        copyTimeBlocking: copyTimeBlocking,
      };
    }

    if (copyTimePreference !== undefined) {
      variables = {
        ...variables,
        copyTimePreference: copyTimePreference,
      };
    }

    if (copyReminders !== undefined) {
      variables = {
        ...variables,
        copyReminders: copyReminders,
      };
    }

    if (copyPriorityLevel !== undefined) {
      variables = {
        ...variables,
        copyPriorityLevel: copyPriorityLevel,
      };
    }

    if (copyModifiable !== undefined) {
      variables = {
        ...variables,
        copyModifiable: copyModifiable,
      };
    }

    if (copyCategories !== undefined) {
      variables = {
        ...variables,
        copyCategories: copyCategories,
      };
    }

    if (copyIsBreak !== undefined) {
      variables = {
        ...variables,
        copyIsBreak: copyIsBreak,
      };
    }

    if (copyIsMeeting !== undefined) {
      variables = {
        ...variables,
        copyIsMeeting: copyIsMeeting,
      };
    }

    if (copyIsExternalMeeting !== undefined) {
      variables = {
        ...variables,
        copyIsExternalMeeting: copyIsExternalMeeting,
      };
    }

    if (copyDuration !== undefined) {
      variables = {
        ...variables,
        copyDuration: copyDuration,
      };
    }

    if (copyColor !== undefined) {
      variables = {
        ...variables,
        copyColor: copyColor,
      };
    }

    const response = (
      await client.mutate<{ update_Event_by_pk: EventType }>({
        mutation: trainEventMutation,
        variables,
      })
    )?.data?.update_Event_by_pk;

    console.log(response, ' train event response from Hasura');
    if (response) {
      // await addToSearchIndex(response) // Removed this old call

      // New: Call Python API to train event for similarity
      if (response.id && response.userId) {
        const event_text =
          `${response.summary || ''}: ${response.notes || ''}`.trim();
        if (event_text === ':') {
          // Both summary and notes are null/empty
          console.warn(
            `Event ${response.id} has no summary or notes, skipping similarity training.`
          );
        } else {
          try {
            // Import constants for Python API URL and OpenAI API Key
            // These should be configured in @lib/constants.ts and available in the environment
            const { PYTHON_TRAINING_API_URL, ATOM_OPENAI_API_KEY } =
              await import('@lib/constants');

            if (!PYTHON_TRAINING_API_URL) {
              console.error(
                'PYTHON_TRAINING_API_URL is not configured. Cannot train event for similarity.'
              );
            } else if (!ATOM_OPENAI_API_KEY) {
              console.error(
                'ATOM_OPENAI_API_KEY is not configured. Cannot train event for similarity.'
              );
            } else {
              const pythonApiPayload = {
                event_id: response.id,
                user_id: response.userId,
                event_text: event_text,
                openai_api_key: ATOM_OPENAI_API_KEY,
              };

              console.log(
                'Calling Python API to train event for similarity:',
                pythonApiPayload.event_id
              );
              // Using axios which is already imported in this file.
              const pythonApiResponse = await axios.post(
                `${PYTHON_TRAINING_API_URL}/train-event-for-similarity`,
                pythonApiPayload,
                { headers: { 'Content-Type': 'application/json' } } // Token not needed if Python service is internal
              );

              if (pythonApiResponse.data?.ok) {
                console.log(
                  'Successfully trained event for similarity:',
                  pythonApiResponse.data.data?.message
                );
              } else {
                console.error(
                  'Failed to train event for similarity:',
                  pythonApiResponse.data?.error ||
                    'Unknown error from Python service'
                );
              }
            }
          } catch (apiError: any) {
            console.error(
              'Error calling Python API for event similarity training:',
              apiError.response?.data || apiError.message || apiError
            );
          }
        }
      } else {
        console.warn(
          'Event ID or User ID missing in Hasura response, cannot train for similarity.',
          response
        );
      }
      return response; // Return the original Hasura response
    }
  } catch (error) {
    console.log(error, ' error in train event response');
  }
};
