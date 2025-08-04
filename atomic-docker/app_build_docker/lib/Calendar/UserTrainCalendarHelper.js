"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.trainEventForPlanning = exports.listPreferredTimeRangesByEvent = exports.deletePreferredTimeRangesByEvent = exports.deletePreferredTimeRangeWithId = exports.insertPreferredTimeRangesForEvent = exports.insertPreferredTimeRangeOneForEvent = exports.addToSearchIndex = exports.dayOfWeekIntToString = void 0;
const client_1 = require("@apollo/client");
const constants_1 = require("@lib/constants");
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
const axios_1 = __importDefault(require("axios"));
const listPreferredTimeRangesByEventId_1 = __importDefault(require("@lib/apollo/gql/listPreferredTimeRangesByEventId"));
const insertPreferredTimeRanges_1 = __importDefault(require("@lib/apollo/gql/insertPreferredTimeRanges"));
const deletePreferredTimeRangesByEventId_1 = __importDefault(require("@lib/apollo/gql/deletePreferredTimeRangesByEventId"));
const deletePreferredTimeRangeById_1 = __importDefault(require("@lib/apollo/gql/deletePreferredTimeRangeById"));
const insertPreferredTimeRange_1 = __importDefault(require("@lib/apollo/gql/insertPreferredTimeRange"));
exports.dayOfWeekIntToString = {
    1: 'MONDAY',
    2: 'TUESDAY',
    3: 'WEDNESDAY',
    4: 'THURSDAY',
    5: 'FRIDAY',
    6: 'SATURDAY',
    7: 'SUNDAY',
};
const addToSearchIndex = async (event) => {
    try {
        // text format: `${summary}: ${notes}`
        /**
         * 1. search for event if it exists
         * 2. if it exists, delete
         * 3. add it
         */
        const url = constants_1.methodToSearchIndexAuthUrl;
        const token = await session_1.default.getAccessToken();
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
        const results = await axios_1.default.post(url, searchData, config);
        console.log(results, ' results inside addToSearchIndex');
        // if it exists, delete
        if (results?.data?.event?.hits?.hits?.[0]?._id) {
            console.log('event exists, delete it');
            const deleteData = {
                eventId: results?.data?.event?.hits?.hits?.[0]?._id,
                method: 'delete',
            };
            const deleteResults = await axios_1.default.post(url, deleteData, config);
            console.log(deleteResults, ' deleteResults in search');
        }
        // add it
        const addData = {
            eventId: event?.id,
            userId: event?.userId,
            eventDetails: `${event?.summary}: ${event?.notes}`,
            method: 'create',
        };
        const res = await axios_1.default.post(url, addData, config);
        console.log(res, ' addToSearchIndex res');
        return res.data.event;
    }
    catch (e) {
        console.log(e, ' unable to add to open search index');
    }
};
exports.addToSearchIndex = addToSearchIndex;
const insertPreferredTimeRangeOneForEvent = async (client, id, eventId, startTime, endTime, dayOfWeek, userId, createdDate, updatedAt, toast) => {
    try {
        console.log(id, eventId, startTime, endTime, dayOfWeek, createdDate, updatedAt, ' id, eventId, startTime, endTime, dayOfWeek, createdDate, updatedAt, insertPreferredTimeRangeOneForEvent');
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
        const { data } = await client.mutate({
            mutation: insertPreferredTimeRange_1.default,
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
    }
    catch (e) {
        console.log(e, ' unable to insert preferred time range');
    }
};
exports.insertPreferredTimeRangeOneForEvent = insertPreferredTimeRangeOneForEvent;
const insertPreferredTimeRangesForEvent = async (client, preferredTimeRanges) => {
    try {
        const { data } = await client.mutate({
            mutation: insertPreferredTimeRanges_1.default,
            variables: {
                preferredTimeRanges,
            },
        });
        console.log(data, ' data in insertPreferredTimeRangesForEvent');
        return data.insert_PreferredTimeRange.returning;
    }
    catch (e) {
        console.log(e, ' unable to insertPreferredTimeRangesForEvent');
    }
};
exports.insertPreferredTimeRangesForEvent = insertPreferredTimeRangesForEvent;
const deletePreferredTimeRangeWithId = async (client, id) => {
    try {
        const { data } = await client.mutate({
            mutation: deletePreferredTimeRangeById_1.default,
            variables: {
                id,
            },
        });
        console.log(data, ' data in deletePreferredTimeRangeWithId');
        return data.delete_PreferredTimeRange_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to deletePreferredTimeRangeWithId');
    }
};
exports.deletePreferredTimeRangeWithId = deletePreferredTimeRangeWithId;
const deletePreferredTimeRangesByEvent = async (client, eventId) => {
    try {
        const res = await client.mutate({
            mutation: deletePreferredTimeRangesByEventId_1.default,
            variables: {
                eventId,
            },
        });
        console.log(res, ' deletePreferredTimeRangesByEvent res');
        return res.data.delete_PreferredTimeRange.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable to delete preferred time ranges');
    }
};
exports.deletePreferredTimeRangesByEvent = deletePreferredTimeRangesByEvent;
const listPreferredTimeRangesByEvent = async (client, eventId) => {
    try {
        const { data } = await client.query({
            query: listPreferredTimeRangesByEventId_1.default,
            variables: {
                eventId: eventId,
            },
            fetchPolicy: 'no-cache',
        });
        return data.PreferredTimeRange;
    }
    catch (e) {
        console.log(e, ' unable to list preferred time ranges');
    }
};
exports.listPreferredTimeRangesByEvent = listPreferredTimeRangesByEvent;
const trainEventForPlanning = async (client, id, 
// enablePreferredTime: boolean,
// preferredTimeType: PreferredTimeTypeType,
// preferredDayOfWeek?: number | null,
// preferredTime?: Time | null,
// preferredStartTimeRange?: Time | null,
// preferredEndTimeRange?: Time | null,
copyAvailability, copyTimeBlocking, copyTimePreference, copyReminders, copyPriorityLevel, copyModifiable, copyCategories, copyIsBreak, copyIsMeeting, copyIsExternalMeeting, copyDuration, copyColor) => {
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
        const trainEventMutation = (0, client_1.gql) `
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
        let variables = {
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
        const response = (await client.mutate({
            mutation: trainEventMutation,
            variables,
        }))?.data?.update_Event_by_pk;
        console.log(response, ' train event response from Hasura');
        if (response) {
            // await addToSearchIndex(response) // Removed this old call
            // New: Call Python API to train event for similarity
            if (response.id && response.userId) {
                const event_text = `${response.summary || ''}: ${response.notes || ''}`.trim();
                if (event_text === ':') {
                    // Both summary and notes are null/empty
                    console.warn(`Event ${response.id} has no summary or notes, skipping similarity training.`);
                }
                else {
                    try {
                        // Import constants for Python API URL and OpenAI API Key
                        // These should be configured in @lib/constants.ts and available in the environment
                        const { PYTHON_TRAINING_API_URL, ATOM_OPENAI_API_KEY } = await import('@lib/constants');
                        if (!PYTHON_TRAINING_API_URL) {
                            console.error('PYTHON_TRAINING_API_URL is not configured. Cannot train event for similarity.');
                        }
                        else if (!ATOM_OPENAI_API_KEY) {
                            console.error('ATOM_OPENAI_API_KEY is not configured. Cannot train event for similarity.');
                        }
                        else {
                            const pythonApiPayload = {
                                event_id: response.id,
                                user_id: response.userId,
                                event_text: event_text,
                                openai_api_key: ATOM_OPENAI_API_KEY,
                            };
                            console.log('Calling Python API to train event for similarity:', pythonApiPayload.event_id);
                            // Using axios which is already imported in this file.
                            const pythonApiResponse = await axios_1.default.post(`${PYTHON_TRAINING_API_URL}/train-event-for-similarity`, pythonApiPayload, { headers: { 'Content-Type': 'application/json' } } // Token not needed if Python service is internal
                            );
                            if (pythonApiResponse.data?.ok) {
                                console.log('Successfully trained event for similarity:', pythonApiResponse.data.data?.message);
                            }
                            else {
                                console.error('Failed to train event for similarity:', pythonApiResponse.data?.error ||
                                    'Unknown error from Python service');
                            }
                        }
                    }
                    catch (apiError) {
                        console.error('Error calling Python API for event similarity training:', apiError.response?.data || apiError.message || apiError);
                    }
                }
            }
            else {
                console.warn('Event ID or User ID missing in Hasura response, cannot train for similarity.', response);
            }
            return response; // Return the original Hasura response
        }
    }
    catch (error) {
        console.log(error, ' error in train event response');
    }
};
exports.trainEventForPlanning = trainEventForPlanning;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlclRyYWluQ2FsZW5kYXJIZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJVc2VyVHJhaW5DYWxlbmRhckhlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSwyQ0FBMEU7QUFFMUUsOENBQTREO0FBQzVELGdGQUF3RDtBQUN4RCxrREFBMEI7QUFHMUIsd0hBQWdHO0FBQ2hHLDBHQUFrRjtBQUVsRiw0SEFBb0c7QUFDcEcsZ0hBQXdGO0FBQ3hGLHdHQUFnRjtBQUVuRSxRQUFBLG9CQUFvQixHQUFHO0lBQ2xDLENBQUMsRUFBRSxRQUFRO0lBQ1gsQ0FBQyxFQUFFLFNBQVM7SUFDWixDQUFDLEVBQUUsV0FBVztJQUNkLENBQUMsRUFBRSxVQUFVO0lBQ2IsQ0FBQyxFQUFFLFFBQVE7SUFDWCxDQUFDLEVBQUUsVUFBVTtJQUNiLENBQUMsRUFBRSxRQUFRO0NBQ1osQ0FBQztBQUVLLE1BQU0sZ0JBQWdCLEdBQUcsS0FBSyxFQUFFLEtBQWdCLEVBQUUsRUFBRTtJQUN6RCxJQUFJLENBQUM7UUFDSCxzQ0FBc0M7UUFDdEM7Ozs7V0FJRztRQUVILE1BQU0sR0FBRyxHQUFHLHNDQUEwQixDQUFDO1FBQ3ZDLE1BQU0sS0FBSyxHQUFHLE1BQU0saUJBQU8sQ0FBQyxjQUFjLEVBQUUsQ0FBQztRQUM3QyxNQUFNLE1BQU0sR0FBRztZQUNiLE9BQU8sRUFBRTtnQkFDUCxhQUFhLEVBQUUsVUFBVSxLQUFLLEVBQUU7Z0JBQ2hDLGNBQWMsRUFBRSxrQkFBa0I7Z0JBQ2xDLE1BQU0sRUFBRSxrQkFBa0I7YUFDM0I7U0FDRixDQUFDO1FBRUYsU0FBUztRQUNULGdDQUFnQztRQUNoQyxNQUFNLFVBQVUsR0FBRztZQUNqQixNQUFNLEVBQUUsR0FBRyxLQUFLLEVBQUUsT0FBTyxHQUFHLEtBQUssRUFBRSxLQUFLLENBQUMsQ0FBQyxDQUFDLEtBQUssS0FBSyxFQUFFLEtBQUssRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUU7WUFDckUs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QyxpREFBaUQ7NkJBQ3RHLENBQUM7NEJBRUYsSUFBSSxpQkFBaUIsQ0FBQyxJQUFJLEVBQUUsRUFBRSxFQUFFLENBQUM7Z0NBQy9CLE9BQU8sQ0FBQyxHQUFHLENBQ1QsNENBQTRDLEVBQzVDLGlCQUFpQixDQUFDLElBQUksQ0FBQyxJQUFJLEVBQUUsT0FBTyxDQUNyQyxDQUFDOzRCQUNKLENBQUM7aUNBQU0sQ0FBQztnQ0FDTixPQUFPLENBQUMsS0FBSyxDQUNYLHVDQUF1QyxFQUN2QyxpQkFBaUIsQ0FBQyxJQUFJLEVBQUUsS0FBSztvQ0FDM0IsbUNBQW1DLENBQ3RDLENBQUM7NEJBQ0osQ0FBQzt3QkFDSCxDQUFDO29CQUNILENBQUM7b0JBQUMsT0FBTyxRQUFhLEVBQUUsQ0FBQzt3QkFDdkIsT0FBTyxDQUFDLEtBQUssQ0FDWCx5REFBeUQsRUFDekQsUUFBUSxDQUFDLFFBQVEsRUFBRSxJQUFJLElBQUksUUFBUSxDQUFDLE9BQU8sSUFBSSxRQUFRLENBQ3hELENBQUM7b0JBQ0osQ0FBQztnQkFDSCxDQUFDO1lBQ0gsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLE9BQU8sQ0FBQyxJQUFJLENBQ1YsOEVBQThFLEVBQzlFLFFBQVEsQ0FDVCxDQUFDO1lBQ0osQ0FBQztZQUNELE9BQU8sUUFBUSxDQUFDLENBQUMsc0NBQXNDO1FBQ3pELENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sQ0FBQyxHQUFHLENBQUMsS0FBSyxFQUFFLGdDQUFnQyxDQUFDLENBQUM7SUFDdkQsQ0FBQztBQUNILENBQUMsQ0FBQztBQWhXVyxRQUFBLHFCQUFxQix5QkFnV2hDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBOb3JtYWxpemVkQ2FjaGVPYmplY3QsIGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCB7IEV2ZW50VHlwZSwgVGltZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0V2ZW50VHlwZSc7XG5pbXBvcnQgeyBtZXRob2RUb1NlYXJjaEluZGV4QXV0aFVybCB9IGZyb20gJ0BsaWIvY29uc3RhbnRzJztcbmltcG9ydCBTZXNzaW9uIGZyb20gJ3N1cGVydG9rZW5zLXdlYi1qcy9yZWNpcGUvc2Vzc2lvbic7XG5pbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnO1xuXG5pbXBvcnQgeyBlc1Jlc3BvbnNlQm9keSB9IGZyb20gJ0BsaWIvQ2FsZW5kYXIvdHlwZXMnO1xuaW1wb3J0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzQnlFdmVudElkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0UHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnRJZCc7XG5pbXBvcnQgaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlcyBmcm9tICdAbGliL2Fwb2xsby9ncWwvaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlcyc7XG5pbXBvcnQgeyBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvUHJlZmVycmVkVGltZVJhbmdlVHlwZSc7XG5pbXBvcnQgZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnRJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnRJZCc7XG5pbXBvcnQgZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlQnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlQnlJZCc7XG5pbXBvcnQgaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9pbnNlcnRQcmVmZXJyZWRUaW1lUmFuZ2UnO1xuXG5leHBvcnQgY29uc3QgZGF5T2ZXZWVrSW50VG9TdHJpbmcgPSB7XG4gIDE6ICdNT05EQVknLFxuICAyOiAnVFVFU0RBWScsXG4gIDM6ICdXRURORVNEQVknLFxuICA0OiAnVEhVUlNEQVknLFxuICA1OiAnRlJJREFZJyxcbiAgNjogJ1NBVFVSREFZJyxcbiAgNzogJ1NVTkRBWScsXG59O1xuXG5leHBvcnQgY29uc3QgYWRkVG9TZWFyY2hJbmRleCA9IGFzeW5jIChldmVudDogRXZlbnRUeXBlKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gdGV4dCBmb3JtYXQ6IGAke3N1bW1hcnl9OiAke25vdGVzfWBcbiAgICAvKipcbiAgICAgKiAxLiBzZWFyY2ggZm9yIGV2ZW50IGlmIGl0IGV4aXN0c1xuICAgICAqIDIuIGlmIGl0IGV4aXN0cywgZGVsZXRlXG4gICAgICogMy4gYWRkIGl0XG4gICAgICovXG5cbiAgICBjb25zdCB1cmwgPSBtZXRob2RUb1NlYXJjaEluZGV4QXV0aFVybDtcbiAgICBjb25zdCB0b2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt0b2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICBBY2NlcHQ6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgIH0sXG4gICAgfTtcblxuICAgIC8vIHNlYXJjaFxuICAgIC8vIHJlc3BvbnNlID0gcmVzLmhpdHMuaGl0cz8uWzBdXG4gICAgY29uc3Qgc2VhcmNoRGF0YSA9IHtcbiAgICAgIHNlYXJjaDogYCR7ZXZlbnQ/LnN1bW1hcnl9JHtldmVudD8ubm90ZXMgPyBgOiAke2V2ZW50Py5ub3Rlc31gIDogJyd9YCxcbiAgICAgIG1ldGhvZDogJ3NlYXJjaCcsXG4gICAgfTtcbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgYXhpb3MucG9zdDx7XG4gICAgICBtZXNzYWdlOiBzdHJpbmc7XG4gICAgICBldmVudDogZXNSZXNwb25zZUJvZHk7XG4gICAgfT4odXJsLCBzZWFyY2hEYXRhLCBjb25maWcpO1xuXG4gICAgY29uc29sZS5sb2cocmVzdWx0cywgJyByZXN1bHRzIGluc2lkZSBhZGRUb1NlYXJjaEluZGV4Jyk7XG5cbiAgICAvLyBpZiBpdCBleGlzdHMsIGRlbGV0ZVxuICAgIGlmIChyZXN1bHRzPy5kYXRhPy5ldmVudD8uaGl0cz8uaGl0cz8uWzBdPy5faWQpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdldmVudCBleGlzdHMsIGRlbGV0ZSBpdCcpO1xuICAgICAgY29uc3QgZGVsZXRlRGF0YSA9IHtcbiAgICAgICAgZXZlbnRJZDogcmVzdWx0cz8uZGF0YT8uZXZlbnQ/LmhpdHM/LmhpdHM/LlswXT8uX2lkLFxuICAgICAgICBtZXRob2Q6ICdkZWxldGUnLFxuICAgICAgfTtcblxuICAgICAgY29uc3QgZGVsZXRlUmVzdWx0cyA9IGF3YWl0IGF4aW9zLnBvc3Q8e1xuICAgICAgICBtZXNzYWdlOiBzdHJpbmc7XG4gICAgICAgIGV2ZW50OiBvYmplY3Q7XG4gICAgICB9Pih1cmwsIGRlbGV0ZURhdGEsIGNvbmZpZyk7XG4gICAgICBjb25zb2xlLmxvZyhkZWxldGVSZXN1bHRzLCAnIGRlbGV0ZVJlc3VsdHMgaW4gc2VhcmNoJyk7XG4gICAgfVxuXG4gICAgLy8gYWRkIGl0XG4gICAgY29uc3QgYWRkRGF0YSA9IHtcbiAgICAgIGV2ZW50SWQ6IGV2ZW50Py5pZCxcbiAgICAgIHVzZXJJZDogZXZlbnQ/LnVzZXJJZCxcbiAgICAgIGV2ZW50RGV0YWlsczogYCR7ZXZlbnQ/LnN1bW1hcnl9OiAke2V2ZW50Py5ub3Rlc31gLFxuICAgICAgbWV0aG9kOiAnY3JlYXRlJyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgYXhpb3MucG9zdDx7IG1lc3NhZ2U6IHN0cmluZzsgZXZlbnQ6IEV2ZW50VHlwZSB9PihcbiAgICAgIHVybCxcbiAgICAgIGFkZERhdGEsXG4gICAgICBjb25maWdcbiAgICApO1xuICAgIGNvbnNvbGUubG9nKHJlcywgJyBhZGRUb1NlYXJjaEluZGV4IHJlcycpO1xuICAgIHJldHVybiByZXMuZGF0YS5ldmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGFkZCB0byBvcGVuIHNlYXJjaCBpbmRleCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlT25lRm9yRXZlbnQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGlkOiBzdHJpbmcsXG4gIGV2ZW50SWQ6IHN0cmluZyxcbiAgc3RhcnRUaW1lOiBUaW1lLFxuICBlbmRUaW1lOiBUaW1lLFxuICBkYXlPZldlZWs6IG51bWJlcixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNyZWF0ZWREYXRlOiBzdHJpbmcsXG4gIHVwZGF0ZWRBdDogc3RyaW5nLFxuICB0b2FzdD86IGFueVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBpZCxcbiAgICAgIGV2ZW50SWQsXG4gICAgICBzdGFydFRpbWUsXG4gICAgICBlbmRUaW1lLFxuICAgICAgZGF5T2ZXZWVrLFxuICAgICAgY3JlYXRlZERhdGUsXG4gICAgICB1cGRhdGVkQXQsXG4gICAgICAnIGlkLCBldmVudElkLCBzdGFydFRpbWUsIGVuZFRpbWUsIGRheU9mV2VlaywgY3JlYXRlZERhdGUsIHVwZGF0ZWRBdCwgaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlT25lRm9yRXZlbnQnXG4gICAgKTtcbiAgICAvLyB2YWxpZGF0ZSBzdGFydFRpbWUgYW5kIGVuZFRpbWVcbiAgICBpZiAoIXN0YXJ0VGltZSB8fCAhZW5kVGltZSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdzdGFydFRpbWUgYW5kIGVuZFRpbWUgYXJlIHJlcXVpcmVkJyk7XG4gICAgfVxuXG4gICAgaWYgKHN0YXJ0VGltZSA+IGVuZFRpbWUpIHtcbiAgICAgIGlmICh0b2FzdCkge1xuICAgICAgICB0b2FzdCh7XG4gICAgICAgICAgdGl0bGU6ICdPb3BzLi4uJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1N0YXJ0IHRpbWUgbXVzdCBiZSBiZWZvcmUgZW5kIHRpbWUnLFxuICAgICAgICAgIHN0YXR1czogJ2Vycm9yJyxcbiAgICAgICAgICBkdXJhdGlvbjogOTAwMCxcbiAgICAgICAgICBpc0Nsb3NhYmxlOiB0cnVlLFxuICAgICAgICB9KTtcbiAgICAgIH1cbiAgICAgIHRocm93IG5ldyBFcnJvcignU3RhcnQgdGltZSBtdXN0IGJlIGJlZm9yZSBlbmQgdGltZScpO1xuICAgIH1cblxuICAgIGlmICghZXZlbnRJZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdFdmVudCBJRCBpcyByZXF1aXJlZCcpO1xuICAgIH1cblxuICAgIGlmICghaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignSUQgaXMgcmVxdWlyZWQnKTtcbiAgICB9XG5cbiAgICBpZiAoIWNyZWF0ZWREYXRlKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ0NyZWF0ZWQgZGF0ZSBpcyByZXF1aXJlZCcpO1xuICAgIH1cblxuICAgIGlmICghdXBkYXRlZEF0KSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ1VwZGF0ZWQgZGF0ZSBpcyByZXF1aXJlZCcpO1xuICAgIH1cblxuICAgIGlmICghdXNlcklkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ3VzZXJJZCBpcyByZXF1aXJlZCcpO1xuICAgIH1cblxuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICBpbnNlcnRfUHJlZmVycmVkVGltZVJhbmdlX29uZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZToge1xuICAgICAgICAgIGlkLFxuICAgICAgICAgIGV2ZW50SWQsXG4gICAgICAgICAgc3RhcnRUaW1lLFxuICAgICAgICAgIGVuZFRpbWUsXG4gICAgICAgICAgZGF5T2ZXZWVrOiBkYXlPZldlZWsgPT09IC0xID8gbnVsbCA6IGRheU9mV2VlayxcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgY3JlYXRlZERhdGUsXG4gICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIGZldGNoUG9saWN5OiAnbm8tY2FjaGUnLFxuICAgIH0pO1xuICAgIHJldHVybiBkYXRhLmluc2VydF9QcmVmZXJyZWRUaW1lUmFuZ2Vfb25lO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gaW5zZXJ0IHByZWZlcnJlZCB0aW1lIHJhbmdlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBpbnNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHByZWZlcnJlZFRpbWVSYW5nZXM6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIGluc2VydF9QcmVmZXJyZWRUaW1lUmFuZ2U6IHtcbiAgICAgICAgYWZmZWN0ZWRfcm93czogbnVtYmVyO1xuICAgICAgICByZXR1cm5pbmc6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXTtcbiAgICAgIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IGluc2VydFByZWZlcnJlZFRpbWVSYW5nZXMsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgcHJlZmVycmVkVGltZVJhbmdlcyxcbiAgICAgIH0sXG4gICAgfSk7XG4gICAgY29uc29sZS5sb2coZGF0YSwgJyBkYXRhIGluIGluc2VydFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCcpO1xuICAgIHJldHVybiBkYXRhLmluc2VydF9QcmVmZXJyZWRUaW1lUmFuZ2UucmV0dXJuaW5nO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gaW5zZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VXaXRoSWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGlkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICBkZWxldGVfUHJlZmVycmVkVGltZVJhbmdlX2J5X3BrOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlO1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiBkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VCeUlkLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGlkLFxuICAgICAgfSxcbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhkYXRhLCAnIGRhdGEgaW4gZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlV2l0aElkJyk7XG4gICAgcmV0dXJuIGRhdGEuZGVsZXRlX1ByZWZlcnJlZFRpbWVSYW5nZV9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZVdpdGhJZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGV2ZW50SWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzID0gYXdhaXQgY2xpZW50Lm11dGF0ZSh7XG4gICAgICBtdXRhdGlvbjogZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnRJZCxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBldmVudElkLFxuICAgICAgfSxcbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhyZXMsICcgZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5RXZlbnQgcmVzJyk7XG4gICAgcmV0dXJuIHJlcy5kYXRhLmRlbGV0ZV9QcmVmZXJyZWRUaW1lUmFuZ2UuYWZmZWN0ZWRfcm93cztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBwcmVmZXJyZWQgdGltZSByYW5nZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzQnlFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgZXZlbnRJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5xdWVyeTx7XG4gICAgICBQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXTtcbiAgICB9Pih7XG4gICAgICBxdWVyeTogbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgZXZlbnRJZDogZXZlbnRJZCxcbiAgICAgIH0sXG4gICAgICBmZXRjaFBvbGljeTogJ25vLWNhY2hlJyxcbiAgICB9KTtcbiAgICByZXR1cm4gZGF0YS5QcmVmZXJyZWRUaW1lUmFuZ2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0IHByZWZlcnJlZCB0aW1lIHJhbmdlcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdHJhaW5FdmVudEZvclBsYW5uaW5nID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBpZDogc3RyaW5nLFxuICAvLyBlbmFibGVQcmVmZXJyZWRUaW1lOiBib29sZWFuLFxuICAvLyBwcmVmZXJyZWRUaW1lVHlwZTogUHJlZmVycmVkVGltZVR5cGVUeXBlLFxuICAvLyBwcmVmZXJyZWREYXlPZldlZWs/OiBudW1iZXIgfCBudWxsLFxuICAvLyBwcmVmZXJyZWRUaW1lPzogVGltZSB8IG51bGwsXG4gIC8vIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlPzogVGltZSB8IG51bGwsXG4gIC8vIHByZWZlcnJlZEVuZFRpbWVSYW5nZT86IFRpbWUgfCBudWxsLFxuICBjb3B5QXZhaWxhYmlsaXR5PzogYm9vbGVhbiB8IG51bGwsXG4gIGNvcHlUaW1lQmxvY2tpbmc/OiBib29sZWFuIHwgbnVsbCxcbiAgY29weVRpbWVQcmVmZXJlbmNlPzogYm9vbGVhbiB8IG51bGwsXG4gIGNvcHlSZW1pbmRlcnM/OiBib29sZWFuIHwgbnVsbCxcbiAgY29weVByaW9yaXR5TGV2ZWw/OiBib29sZWFuIHwgbnVsbCxcbiAgY29weU1vZGlmaWFibGU/OiBib29sZWFuIHwgbnVsbCxcbiAgY29weUNhdGVnb3JpZXM/OiBib29sZWFuIHwgbnVsbCxcbiAgY29weUlzQnJlYWs/OiBib29sZWFuIHwgbnVsbCxcbiAgY29weUlzTWVldGluZz86IGJvb2xlYW4gfCBudWxsLFxuICBjb3B5SXNFeHRlcm5hbE1lZXRpbmc/OiBib29sZWFuIHwgbnVsbCxcbiAgY29weUR1cmF0aW9uPzogYm9vbGVhbiB8IG51bGwsXG4gIGNvcHlDb2xvcj86IGJvb2xlYW4gfCBudWxsXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvKipcbiAgICAgICAgICogICAgICAgICAgICAgICAgICMgJHshZW5hYmxlUHJlZmVycmVkVGltZSA/ICcnIDogcHJlZmVycmVkRGF5T2ZXZWVrICE9PSB1bmRlZmluZWQgPyAnJHByZWZlcnJlZERheU9mV2VlazogSW50LCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgIyAkeyFlbmFibGVQcmVmZXJyZWRUaW1lID8gJycgOiBwcmVmZXJyZWRUaW1lVHlwZSA9PT0gJ3ByZWZlcnJlZFRpbWVSYW5nZScgPyAnJHByZWZlcnJlZEVuZFRpbWVSYW5nZTogdGltZSwnIDogJyd9XG4gICAgICAgICAgICAgICAgIyAkeyFlbmFibGVQcmVmZXJyZWRUaW1lID8gJycgOiBwcmVmZXJyZWRUaW1lVHlwZSA9PT0gJ3ByZWZlcnJlZFRpbWUnID8gJyRwcmVmZXJyZWRUaW1lOiB0aW1lLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAjICR7IWVuYWJsZVByZWZlcnJlZFRpbWUgPyAnJyA6IHByZWZlcnJlZFRpbWVUeXBlID09PSAncHJlZmVycmVkVGltZVJhbmdlJyA/ICckcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IHRpbWUsJyA6ICcnfVxuXG4gICAgICAgICAgICAgICAgICMgJHshZW5hYmxlUHJlZmVycmVkVGltZSA/ICdwcmVmZXJyZWREYXlPZldlZWs6IG51bGwsJyA6ICdwcmVmZXJyZWREYXlPZldlZWs6ICRwcmVmZXJyZWREYXlPZldlZWssJ30gXG4gICAgICAgICAgICAgICAgICAgICMgJHshZW5hYmxlUHJlZmVycmVkVGltZSA/ICdwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IG51bGwsJyA6IHByZWZlcnJlZFRpbWVUeXBlID09PSAncHJlZmVycmVkVGltZVJhbmdlJyA/ICdwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6ICRwcmVmZXJyZWRFbmRUaW1lUmFuZ2UsJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAgICAgIyAkeyFlbmFibGVQcmVmZXJyZWRUaW1lID8gJ3ByZWZlcnJlZFRpbWU6IG51bGwsJyA6IHByZWZlcnJlZFRpbWVUeXBlID09PSAncHJlZmVycmVkVGltZScgPyAncHJlZmVycmVkVGltZTogJHByZWZlcnJlZFRpbWUsJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAgICAgIyAkeyFlbmFibGVQcmVmZXJyZWRUaW1lID8gJ3ByZWZlcnJlZFN0YXJ0VGltZVJhbmdlIDogbnVsbCwnIDogcHJlZmVycmVkVGltZVR5cGUgPT09ICdwcmVmZXJyZWRUaW1lUmFuZ2UnID8gJ3ByZWZlcnJlZFN0YXJ0VGltZVJhbmdlOiAkcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2UsJyA6ICcnfSBcbiAgICAgICAgICovXG4gICAgY29uc3QgdHJhaW5FdmVudE11dGF0aW9uID0gZ3FsYFxuICAgICAgICAgICAgbXV0YXRpb24gVXBkYXRlRXZlbnRGb3JUcmFpbmluZygkaWQ6IFN0cmluZyEsXG4gICAgICAgICAgICAgICAgJHtjb3B5QXZhaWxhYmlsaXR5ICE9PSB1bmRlZmluZWQgPyAnJGNvcHlBdmFpbGFiaWxpdHk6IEJvb2xlYW4sJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7Y29weVRpbWVCbG9ja2luZyAhPT0gdW5kZWZpbmVkID8gJyRjb3B5VGltZUJsb2NraW5nOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NvcHlUaW1lUHJlZmVyZW5jZSAhPT0gdW5kZWZpbmVkID8gJyRjb3B5VGltZVByZWZlcmVuY2U6IEJvb2xlYW4sJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7Y29weVJlbWluZGVycyAhPT0gdW5kZWZpbmVkID8gJyRjb3B5UmVtaW5kZXJzOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NvcHlQcmlvcml0eUxldmVsICE9PSB1bmRlZmluZWQgPyAnJGNvcHlQcmlvcml0eUxldmVsOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NvcHlNb2RpZmlhYmxlICE9PSB1bmRlZmluZWQgPyAnJGNvcHlNb2RpZmlhYmxlOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NvcHlDYXRlZ29yaWVzICE9PSB1bmRlZmluZWQgPyAnJGNvcHlDYXRlZ29yaWVzOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NvcHlJc0JyZWFrICE9PSB1bmRlZmluZWQgPyAnJGNvcHlJc0JyZWFrOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NvcHlJc01lZXRpbmcgIT09IHVuZGVmaW5lZCA/ICckY29weUlzTWVldGluZzogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICAgICAgICAgJHtjb3B5SXNFeHRlcm5hbE1lZXRpbmcgIT09IHVuZGVmaW5lZCA/ICckY29weUlzRXh0ZXJuYWxNZWV0aW5nOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgICAgICAgICAke2NvcHlEdXJhdGlvbiAhPT0gdW5kZWZpbmVkID8gJyRjb3B5RHVyYXRpb246IEJvb2xlYW4sJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7Y29weUNvbG9yICE9PSB1bmRlZmluZWQgPyAnJGNvcHlDb2xvcjogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgICB1cGRhdGVfRXZlbnRfYnlfcGsoXG4gICAgICAgICAgICAgICAgICAgIHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgXG4gICAgICAgICAgICAgICAgICAgIF9zZXQ6IHtcbiAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weUF2YWlsYWJpbGl0eSAhPT0gdW5kZWZpbmVkID8gJ2NvcHlBdmFpbGFiaWxpdHk6ICRjb3B5QXZhaWxhYmlsaXR5LCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgICAgICAgICAke2NvcHlUaW1lQmxvY2tpbmcgIT09IHVuZGVmaW5lZCA/ICdjb3B5VGltZUJsb2NraW5nOiAkY29weVRpbWVCbG9ja2luZywnIDogJyd9IFxuICAgICAgICAgICAgICAgICAgICAgICAgJHtjb3B5VGltZVByZWZlcmVuY2UgIT09IHVuZGVmaW5lZCA/ICdjb3B5VGltZVByZWZlcmVuY2U6ICRjb3B5VGltZVByZWZlcmVuY2UsJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weVJlbWluZGVycyAhPT0gdW5kZWZpbmVkID8gJ2NvcHlSZW1pbmRlcnM6ICRjb3B5UmVtaW5kZXJzLCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgICAgICAgICAke2NvcHlQcmlvcml0eUxldmVsICE9PSB1bmRlZmluZWQgPyAnY29weVByaW9yaXR5TGV2ZWw6ICRjb3B5UHJpb3JpdHlMZXZlbCwnIDogJyd9IFxuICAgICAgICAgICAgICAgICAgICAgICAgJHtjb3B5TW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkID8gJ2NvcHlNb2RpZmlhYmxlOiAkY29weU1vZGlmaWFibGUsJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weUNhdGVnb3JpZXMgIT09IHVuZGVmaW5lZCA/ICdjb3B5Q2F0ZWdvcmllczogJGNvcHlDYXRlZ29yaWVzLCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgICAgICAgICAke2NvcHlJc0JyZWFrICE9PSB1bmRlZmluZWQgPyAnY29weUlzQnJlYWs6ICRjb3B5SXNCcmVhaywnIDogJyd9IFxuICAgICAgICAgICAgICAgICAgICAgICAgJHtjb3B5SXNNZWV0aW5nICE9PSB1bmRlZmluZWQgPyAnY29weUlzTWVldGluZzogJGNvcHlJc01lZXRpbmcsJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAgICAgICAgICR7Y29weUlzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQgPyAnY29weUlzRXh0ZXJuYWxNZWV0aW5nOiAkY29weUlzRXh0ZXJuYWxNZWV0aW5nLCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgICAgICAgICAke2NvcHlEdXJhdGlvbiAhPT0gdW5kZWZpbmVkID8gJ2NvcHlEdXJhdGlvbjogJGNvcHlEdXJhdGlvbiwnIDogJyd9IFxuICAgICAgICAgICAgICAgICAgICAgICAgJHtjb3B5Q29sb3IgIT09IHVuZGVmaW5lZCA/ICdjb3B5Q29sb3I6ICRjb3B5Q29sb3IsJyA6ICcnfVxuICAgICAgICAgICAgICAgICAgICB9KSB7XG4gICAgICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICBhbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlY3VycmVuY2VSdWxlXG4gICAgICAgICAgICAgICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIGF0dGFjaG1lbnRzXG4gICAgICAgICAgICAgICAgICAgICAgICBsaW5rc1xuICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgICAgIHRhc2tJZFxuICAgICAgICAgICAgICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGlzRm9sbG93VXBcbiAgICAgICAgICAgICAgICAgICAgICAgIGlzUHJlRXZlbnRcbiAgICAgICAgICAgICAgICAgICAgICAgIGlzUG9zdEV2ZW50XG4gICAgICAgICAgICAgICAgICAgICAgICBwcmVFdmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgICBwb3N0RXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICAgICAgZm9yRXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICAgICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgICAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICAgICAgICAgICAgICBhbnlvbmVDYW5BZGRTZWxmXG4gICAgICAgICAgICAgICAgICAgICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnNcbiAgICAgICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgICAgICBvcmlnaW5hbFN0YXJ0RGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxUaW1lem9uZVxuICAgICAgICAgICAgICAgICAgICAgICAgb3JpZ2luYWxBbGxEYXlcbiAgICAgICAgICAgICAgICAgICAgICAgIHN0YXR1c1xuICAgICAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICAgICAgdHJhbnNwYXJlbmN5XG4gICAgICAgICAgICAgICAgICAgICAgICB2aXNpYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgICAgICByZWN1cnJpbmdFdmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgICBpQ2FsVUlEXG4gICAgICAgICAgICAgICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICAgICAgY3JlYXRvclxuICAgICAgICAgICAgICAgICAgICAgICAgb3JnYW5pemVyXG4gICAgICAgICAgICAgICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGV4dGVuZGVkUHJvcGVydGllc1xuICAgICAgICAgICAgICAgICAgICAgICAgaGFuZ291dExpbmtcbiAgICAgICAgICAgICAgICAgICAgICAgIGd1ZXN0c0Nhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICAgICAgbG9ja2VkXG4gICAgICAgICAgICAgICAgICAgICAgICBzb3VyY2VcbiAgICAgICAgICAgICAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgICAgICAgICAgICAgcHJpdmF0ZUNvcHlcbiAgICAgICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmVcbiAgICAgICAgICAgICAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFRpbWVcbiAgICAgICAgICAgICAgICAgICAgICAgIG5lZ2F0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgICAgICBuZWdhdGl2ZUltcGFjdFRpbWVcbiAgICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZERheU9mV2Vla1xuICAgICAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkVGltZVxuICAgICAgICAgICAgICAgICAgICAgICAgaXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICAgICAgaXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgICAgICBkYWlseVRhc2tMaXN0XG4gICAgICAgICAgICAgICAgICAgICAgICB3ZWVrbHlUYXNrTGlzdFxuICAgICAgICAgICAgICAgICAgICAgICAgaXNCcmVha1xuICAgICAgICAgICAgICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgICAgICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgICAgICAgICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICAgICAgICAgICAgICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvcHlDYXRlZ29yaWVzXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkQXZhaWxhYmlsaXR5XG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXNcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgICAgICAgICAgICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZElzTWVldGluZ1xuICAgICAgICAgICAgICAgICAgICAgICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgICAgICBjb3B5RHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJNb2RpZmllZER1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgICAgICAgICAgICAgIHVubGlua1xuICAgICAgICAgICAgICAgICAgICAgICAgY29weUNvbG9yXG4gICAgICAgICAgICAgICAgICAgICAgICB1c2VyTW9kaWZpZWRDb2xvclxuICAgICAgICAgICAgICAgICAgICAgICAgYnlXZWVrRGF5XG4gICAgICAgICAgICAgICAgICAgICAgICBsb2NhbFN5bmNlZFxuICAgICAgICAgICAgICAgICAgICAgICAgdGl0bGVcbiAgICAgICAgICAgICAgICAgICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgICAgICAgICAgbWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuXG4gICAgbGV0IHZhcmlhYmxlczogYW55ID0ge1xuICAgICAgaWQ6IGlkLFxuICAgIH07XG5cbiAgICBpZiAoY29weUF2YWlsYWJpbGl0eSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7XG4gICAgICAgIC4uLnZhcmlhYmxlcyxcbiAgICAgICAgY29weUF2YWlsYWJpbGl0eTogY29weUF2YWlsYWJpbGl0eSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNvcHlUaW1lQmxvY2tpbmcgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzID0ge1xuICAgICAgICAuLi52YXJpYWJsZXMsXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmc6IGNvcHlUaW1lQmxvY2tpbmcsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjb3B5VGltZVByZWZlcmVuY2UgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzID0ge1xuICAgICAgICAuLi52YXJpYWJsZXMsXG4gICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZTogY29weVRpbWVQcmVmZXJlbmNlLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoY29weVJlbWluZGVycyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7XG4gICAgICAgIC4uLnZhcmlhYmxlcyxcbiAgICAgICAgY29weVJlbWluZGVyczogY29weVJlbWluZGVycyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNvcHlQcmlvcml0eUxldmVsICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcyA9IHtcbiAgICAgICAgLi4udmFyaWFibGVzLFxuICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbDogY29weVByaW9yaXR5TGV2ZWwsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjb3B5TW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7XG4gICAgICAgIC4uLnZhcmlhYmxlcyxcbiAgICAgICAgY29weU1vZGlmaWFibGU6IGNvcHlNb2RpZmlhYmxlLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoY29weUNhdGVnb3JpZXMgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzID0ge1xuICAgICAgICAuLi52YXJpYWJsZXMsXG4gICAgICAgIGNvcHlDYXRlZ29yaWVzOiBjb3B5Q2F0ZWdvcmllcyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNvcHlJc0JyZWFrICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcyA9IHtcbiAgICAgICAgLi4udmFyaWFibGVzLFxuICAgICAgICBjb3B5SXNCcmVhazogY29weUlzQnJlYWssXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjb3B5SXNNZWV0aW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcyA9IHtcbiAgICAgICAgLi4udmFyaWFibGVzLFxuICAgICAgICBjb3B5SXNNZWV0aW5nOiBjb3B5SXNNZWV0aW5nLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoY29weUlzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcyA9IHtcbiAgICAgICAgLi4udmFyaWFibGVzLFxuICAgICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmc6IGNvcHlJc0V4dGVybmFsTWVldGluZyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNvcHlEdXJhdGlvbiAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMgPSB7XG4gICAgICAgIC4uLnZhcmlhYmxlcyxcbiAgICAgICAgY29weUR1cmF0aW9uOiBjb3B5RHVyYXRpb24sXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjb3B5Q29sb3IgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzID0ge1xuICAgICAgICAuLi52YXJpYWJsZXMsXG4gICAgICAgIGNvcHlDb2xvcjogY29weUNvbG9yLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZSA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5tdXRhdGU8eyB1cGRhdGVfRXZlbnRfYnlfcGs6IEV2ZW50VHlwZSB9Pih7XG4gICAgICAgIG11dGF0aW9uOiB0cmFpbkV2ZW50TXV0YXRpb24sXG4gICAgICAgIHZhcmlhYmxlcyxcbiAgICAgIH0pXG4gICAgKT8uZGF0YT8udXBkYXRlX0V2ZW50X2J5X3BrO1xuXG4gICAgY29uc29sZS5sb2cocmVzcG9uc2UsICcgdHJhaW4gZXZlbnQgcmVzcG9uc2UgZnJvbSBIYXN1cmEnKTtcbiAgICBpZiAocmVzcG9uc2UpIHtcbiAgICAgIC8vIGF3YWl0IGFkZFRvU2VhcmNoSW5kZXgocmVzcG9uc2UpIC8vIFJlbW92ZWQgdGhpcyBvbGQgY2FsbFxuXG4gICAgICAvLyBOZXc6IENhbGwgUHl0aG9uIEFQSSB0byB0cmFpbiBldmVudCBmb3Igc2ltaWxhcml0eVxuICAgICAgaWYgKHJlc3BvbnNlLmlkICYmIHJlc3BvbnNlLnVzZXJJZCkge1xuICAgICAgICBjb25zdCBldmVudF90ZXh0ID1cbiAgICAgICAgICBgJHtyZXNwb25zZS5zdW1tYXJ5IHx8ICcnfTogJHtyZXNwb25zZS5ub3RlcyB8fCAnJ31gLnRyaW0oKTtcbiAgICAgICAgaWYgKGV2ZW50X3RleHQgPT09ICc6Jykge1xuICAgICAgICAgIC8vIEJvdGggc3VtbWFyeSBhbmQgbm90ZXMgYXJlIG51bGwvZW1wdHlcbiAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICBgRXZlbnQgJHtyZXNwb25zZS5pZH0gaGFzIG5vIHN1bW1hcnkgb3Igbm90ZXMsIHNraXBwaW5nIHNpbWlsYXJpdHkgdHJhaW5pbmcuYFxuICAgICAgICAgICk7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIC8vIEltcG9ydCBjb25zdGFudHMgZm9yIFB5dGhvbiBBUEkgVVJMIGFuZCBPcGVuQUkgQVBJIEtleVxuICAgICAgICAgICAgLy8gVGhlc2Ugc2hvdWxkIGJlIGNvbmZpZ3VyZWQgaW4gQGxpYi9jb25zdGFudHMudHMgYW5kIGF2YWlsYWJsZSBpbiB0aGUgZW52aXJvbm1lbnRcbiAgICAgICAgICAgIGNvbnN0IHsgUFlUSE9OX1RSQUlOSU5HX0FQSV9VUkwsIEFUT01fT1BFTkFJX0FQSV9LRVkgfSA9XG4gICAgICAgICAgICAgIGF3YWl0IGltcG9ydCgnQGxpYi9jb25zdGFudHMnKTtcblxuICAgICAgICAgICAgaWYgKCFQWVRIT05fVFJBSU5JTkdfQVBJX1VSTCkge1xuICAgICAgICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgICAgICAgICdQWVRIT05fVFJBSU5JTkdfQVBJX1VSTCBpcyBub3QgY29uZmlndXJlZC4gQ2Fubm90IHRyYWluIGV2ZW50IGZvciBzaW1pbGFyaXR5LidcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH0gZWxzZSBpZiAoIUFUT01fT1BFTkFJX0FQSV9LRVkpIHtcbiAgICAgICAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICAgICAgICAnQVRPTV9PUEVOQUlfQVBJX0tFWSBpcyBub3QgY29uZmlndXJlZC4gQ2Fubm90IHRyYWluIGV2ZW50IGZvciBzaW1pbGFyaXR5LidcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgIGNvbnN0IHB5dGhvbkFwaVBheWxvYWQgPSB7XG4gICAgICAgICAgICAgICAgZXZlbnRfaWQ6IHJlc3BvbnNlLmlkLFxuICAgICAgICAgICAgICAgIHVzZXJfaWQ6IHJlc3BvbnNlLnVzZXJJZCxcbiAgICAgICAgICAgICAgICBldmVudF90ZXh0OiBldmVudF90ZXh0LFxuICAgICAgICAgICAgICAgIG9wZW5haV9hcGlfa2V5OiBBVE9NX09QRU5BSV9BUElfS0VZLFxuICAgICAgICAgICAgICB9O1xuXG4gICAgICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgICAgICdDYWxsaW5nIFB5dGhvbiBBUEkgdG8gdHJhaW4gZXZlbnQgZm9yIHNpbWlsYXJpdHk6JyxcbiAgICAgICAgICAgICAgICBweXRob25BcGlQYXlsb2FkLmV2ZW50X2lkXG4gICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgIC8vIFVzaW5nIGF4aW9zIHdoaWNoIGlzIGFscmVhZHkgaW1wb3J0ZWQgaW4gdGhpcyBmaWxlLlxuICAgICAgICAgICAgICBjb25zdCBweXRob25BcGlSZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3QoXG4gICAgICAgICAgICAgICAgYCR7UFlUSE9OX1RSQUlOSU5HX0FQSV9VUkx9L3RyYWluLWV2ZW50LWZvci1zaW1pbGFyaXR5YCxcbiAgICAgICAgICAgICAgICBweXRob25BcGlQYXlsb2FkLFxuICAgICAgICAgICAgICAgIHsgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0gfSAvLyBUb2tlbiBub3QgbmVlZGVkIGlmIFB5dGhvbiBzZXJ2aWNlIGlzIGludGVybmFsXG4gICAgICAgICAgICAgICk7XG5cbiAgICAgICAgICAgICAgaWYgKHB5dGhvbkFwaVJlc3BvbnNlLmRhdGE/Lm9rKSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgICAgICAgICAnU3VjY2Vzc2Z1bGx5IHRyYWluZWQgZXZlbnQgZm9yIHNpbWlsYXJpdHk6JyxcbiAgICAgICAgICAgICAgICAgIHB5dGhvbkFwaVJlc3BvbnNlLmRhdGEuZGF0YT8ubWVzc2FnZVxuICAgICAgICAgICAgICAgICk7XG4gICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICAgICAgICAgICdGYWlsZWQgdG8gdHJhaW4gZXZlbnQgZm9yIHNpbWlsYXJpdHk6JyxcbiAgICAgICAgICAgICAgICAgIHB5dGhvbkFwaVJlc3BvbnNlLmRhdGE/LmVycm9yIHx8XG4gICAgICAgICAgICAgICAgICAgICdVbmtub3duIGVycm9yIGZyb20gUHl0aG9uIHNlcnZpY2UnXG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICAgIH0gY2F0Y2ggKGFwaUVycm9yOiBhbnkpIHtcbiAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgICAgICdFcnJvciBjYWxsaW5nIFB5dGhvbiBBUEkgZm9yIGV2ZW50IHNpbWlsYXJpdHkgdHJhaW5pbmc6JyxcbiAgICAgICAgICAgICAgYXBpRXJyb3IucmVzcG9uc2U/LmRhdGEgfHwgYXBpRXJyb3IubWVzc2FnZSB8fCBhcGlFcnJvclxuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAnRXZlbnQgSUQgb3IgVXNlciBJRCBtaXNzaW5nIGluIEhhc3VyYSByZXNwb25zZSwgY2Fubm90IHRyYWluIGZvciBzaW1pbGFyaXR5LicsXG4gICAgICAgICAgcmVzcG9uc2VcbiAgICAgICAgKTtcbiAgICAgIH1cbiAgICAgIHJldHVybiByZXNwb25zZTsgLy8gUmV0dXJuIHRoZSBvcmlnaW5hbCBIYXN1cmEgcmVzcG9uc2VcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5sb2coZXJyb3IsICcgZXJyb3IgaW4gdHJhaW4gZXZlbnQgcmVzcG9uc2UnKTtcbiAgfVxufTtcbiJdfQ==