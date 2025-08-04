import requiredFields from './requiredFields';
import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, eventSearchBoundary, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, } from '@chat/_libs/api-helper';
import { deletePreferredTimeRangesByIds, listPreferredTimeRangesGivenEventId, } from '../resolveConflictingEvents/api-helper';
import { DayOfWeekEnum } from './constants';
import { v4 as uuid } from 'uuid';
import { dayjs } from '@chat/_libs/datetime/date-utils';
export const finalStepERPT2PTs = async (body, startDate, endDate, response) => {
    try {
        // convert to vector for search
        const searchVector = await convertEventTitleToOpenAIVector(body?.title);
        //  allEventWithEventOpenSearch
        if (!startDate) {
            startDate = dayjs().subtract(2, 'w').format();
        }
        if (!endDate) {
            endDate = dayjs().add(4, 'w').format();
        }
        const res = await allEventWithDatesOpenSearch(body?.userId, searchVector, startDate, endDate);
        const id = res?.hits?.hits?.[0]?._id;
        // validate found event
        if (!id) {
            response.query = 'event_not_found';
            return response;
        }
        const preferredTimeRangesWantRemoved = [];
        for (const timepreference of body?.timePreferences) {
            if (timepreference.dayOfWeek?.length > 0) {
                for (const dayOfWeek of timepreference.dayOfWeek) {
                    const newPreferredTimeRange = {
                        id: uuid(),
                        eventId: id,
                        dayOfWeek: DayOfWeekEnum[dayOfWeek],
                        startTime: timepreference?.timeRange?.startTime,
                        endTime: timepreference?.timeRange?.endTime,
                        updatedAt: dayjs().format(),
                        createdDate: dayjs().format(),
                        userId: body?.userId,
                    };
                    preferredTimeRangesWantRemoved.push(newPreferredTimeRange);
                }
            }
            else {
                const newPreferredTimeRange = {
                    id: uuid(),
                    eventId: id,
                    startTime: timepreference?.timeRange?.startTime,
                    endTime: timepreference?.timeRange?.endTime,
                    updatedAt: dayjs().format(),
                    createdDate: dayjs().format(),
                    userId: body?.userId,
                };
                preferredTimeRangesWantRemoved.push(newPreferredTimeRange);
            }
        }
        // list existing preferred time ranges
        const oldPreferredTimeRanges = await listPreferredTimeRangesGivenEventId(id);
        // find values to remove
        const preferredTimeRangesToBeRemoved = [];
        for (const preferredTimeRangeWantToRemove of preferredTimeRangesWantRemoved) {
            for (const oldPreferredTimeRange of oldPreferredTimeRanges) {
                if (preferredTimeRangeWantToRemove.dayOfWeek === -1 ||
                    !preferredTimeRangeWantToRemove.dayOfWeek) {
                    if (oldPreferredTimeRange.dayOfWeek === -1 ||
                        !oldPreferredTimeRange.dayOfWeek) {
                        if (preferredTimeRangeWantToRemove.startTime ===
                            oldPreferredTimeRange.startTime) {
                            preferredTimeRangesToBeRemoved.push(oldPreferredTimeRange);
                        }
                    }
                }
                else if (preferredTimeRangeWantToRemove?.dayOfWeek ===
                    oldPreferredTimeRange?.dayOfWeek) {
                    if (preferredTimeRangeWantToRemove.startTime ===
                        oldPreferredTimeRange.startTime) {
                        preferredTimeRangesToBeRemoved.push(oldPreferredTimeRange);
                    }
                }
            }
        }
        // delete time ranges to be removed
        if (preferredTimeRangesToBeRemoved?.length > 0) {
            await deletePreferredTimeRangesByIds(preferredTimeRangesToBeRemoved?.map((p) => p?.id));
        }
        // success response
        response.query = 'completed';
        response.data = 'successfully removed preferred time';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step ERPT2PTs');
    }
};
export const processERPT2PTsPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
    try {
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
        let startDate = searchBoundary.startDate;
        let endDate = searchBoundary.endDate;
        const body = {
            userId,
            timezone,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task,
            method: dateJSONBody?.method,
            timePreferences: dateJSONBody?.timePreferences,
        };
        // validate for missing fields
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'editRemovePreferredTimeToPreferredTimes',
        };
        if (!body?.title) {
            response.query = 'missing_fields';
            missingFields.required = requiredFields.required;
            response.data = missingFields;
            response.prevData = body;
            response.prevDataExtra = {
                searchBoundary,
            };
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!body?.timePreferences?.[0]) {
            response.query = 'missing_fields';
            missingFields.dateTime = requiredFields.dateTime;
            response.data = missingFields;
            response.prevData = body;
            response.prevDataExtra = {
                searchBoundary,
            };
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        // for loop to verify each time preference
        let isMissingDateTimeField = false;
        for (const timePreference of body.timePreferences) {
            if (!timePreference.dayOfWeek && !timePreference.timeRange.startTime) {
                isMissingDateTimeField = true;
            }
        }
        if (isMissingDateTimeField) {
            response.query = 'missing_fields';
            missingFields.dateTime = requiredFields.dateTime;
            response.data = missingFields;
            response.prevData = body;
            response.prevDataExtra = {
                searchBoundary,
            };
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepERPT2PTs(body, startDate, endDate, response);
        return response2;
        // data validated start api calls
        // search for event
        // convert to vector for search
        // const searchVector = await convertEventTitleToOpenAIVector(body?.title)
        // //  allEventWithEventOpenSearch
        // if (!startDate) {
        //     startDate = dayjs().subtract(2, 'w').format()
        // }
        // if (!endDate) {
        //     endDate = dayjs().add(4, 'w').format()
        // }
        // const res = await allEventWithDatesOpenSearch(userId, searchVector, startDate, endDate)
        // const id = res?.hits?.hits?.[0]?._id
        // // validate found event
        // if (!id) {
        //     response.query = 'event_not_found'
        //     return response
        // }
        // const preferredTimeRangesWantRemoved: PreferredTimeRangeType[] = []
        // for (const timepreference of body?.timePreferences) {
        //     if (timepreference.dayOfWeek?.length > 0) {
        //         for (const dayOfWeek of timepreference.dayOfWeek) {
        //             const newPreferredTimeRange: PreferredTimeRangeType = {
        //                 id: uuid(),
        //                 eventId: id,
        //                 dayOfWeek: DayOfWeekEnum[dayOfWeek],
        //                 startTime: timepreference?.timeRange?.startTime,
        //                 endTime: timepreference?.timeRange?.endTime,
        //                 updatedAt: dayjs().format(),
        //                 createdDate: dayjs().format(),
        //                 userId,
        //             }
        //             preferredTimeRangesWantRemoved.push(newPreferredTimeRange)
        //         }
        //     } else {
        //         const newPreferredTimeRange: PreferredTimeRangeType = {
        //             id: uuid(),
        //             eventId: id,
        //             startTime: timepreference?.timeRange?.startTime,
        //             endTime: timepreference?.timeRange?.endTime,
        //             updatedAt: dayjs().format(),
        //             createdDate: dayjs().format(),
        //             userId,
        //         }
        //         preferredTimeRangesWantRemoved.push(newPreferredTimeRange)
        //     }
        // }
        // // list existing preferred time ranges
        // const oldPreferredTimeRanges = await listPreferredTimeRangesGivenEventId(id)
        // // find values to remove
        // const preferredTimeRangesToBeRemoved: PreferredTimeRangeType[] = []
        // for (const preferredTimeRangeWantToRemove of preferredTimeRangesWantRemoved) {
        //     for (const oldPreferredTimeRange of oldPreferredTimeRanges) {
        //         if (
        //             (preferredTimeRangeWantToRemove.dayOfWeek === -1)
        //             || (!preferredTimeRangeWantToRemove.dayOfWeek)) {
        //             if (
        //                 (oldPreferredTimeRange.dayOfWeek === -1)
        //                 || (!oldPreferredTimeRange.dayOfWeek)) {
        //                 if (preferredTimeRangeWantToRemove.startTime === oldPreferredTimeRange.startTime) {
        //                     preferredTimeRangesToBeRemoved.push(oldPreferredTimeRange)
        //                 }
        //             }
        //         } else if (preferredTimeRangeWantToRemove?.dayOfWeek === oldPreferredTimeRange?.dayOfWeek) {
        //             if (preferredTimeRangeWantToRemove.startTime === oldPreferredTimeRange.startTime) {
        //                 preferredTimeRangesToBeRemoved.push(oldPreferredTimeRange)
        //             }
        //         }
        //     }
        // }
        // // delete time ranges to be removed
        // if (preferredTimeRangesToBeRemoved?.length > 0) {
        //     await deletePreferredTimeRangesByIds(preferredTimeRangesToBeRemoved?.map(p => (p?.id)))
        // }
        // // success response
        // response.query = 'completed'
        // return response
    }
    catch (e) {
        console.log(e, ' unable to process edit and preferred time to preferred times ');
    }
};
export const processERPT2PTsMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
    try {
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
        let startDate = searchBoundary.startDate;
        let endDate = searchBoundary.endDate;
        const newBody = {
            userId,
            timezone,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task ||
                messageHistoryObject?.prevJsonBody?.params?.title ||
                messageHistoryObject?.prevJsonBody?.params?.summary ||
                messageHistoryObject?.prevJsonBody?.params?.description ||
                messageHistoryObject?.prevJsonBody?.params?.taskList?.[0]?.task,
            method: dateJSONBody?.method,
            timePreferences: dateJSONBody?.timePreferences ||
                messageHistoryObject?.prevDateJsonBody?.timePreferences ||
                [],
        };
        const prevBody = {
            ...messageHistoryObject?.prevData,
        };
        if (!prevBody?.userId) {
            prevBody.userId = newBody?.userId;
        }
        if (!prevBody?.timezone) {
            prevBody.timezone = timezone || newBody?.timezone;
        }
        if (!prevBody?.title) {
            prevBody.title = newBody?.title;
        }
        if (!(prevBody?.timePreferences?.length > 0)) {
            prevBody.timePreferences = newBody?.timePreferences;
        }
        const prevSearchBoundary = messageHistoryObject?.prevDataExtra?.searchBoundary;
        let prevStartDate = prevSearchBoundary?.startDate;
        let prevEndDate = prevSearchBoundary?.endDate;
        if (!prevStartDate) {
            prevStartDate = startDate;
        }
        if (!prevEndDate) {
            prevEndDate = endDate;
        }
        // validate for missing fields
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'editRemovePreferredTimeToPreferredTimes',
        };
        if (!prevBody?.title) {
            response.query = 'missing_fields';
            missingFields.required = requiredFields.required;
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevDataExtra = {
                searchBoundary: {
                    startDate: prevStartDate,
                    endDate: prevEndDate,
                },
            };
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (!prevBody?.timePreferences?.[0]) {
            response.query = 'missing_fields';
            missingFields.dateTime = requiredFields.dateTime;
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevDataExtra = {
                searchBoundary: {
                    startDate: prevStartDate,
                    endDate: prevEndDate,
                },
            };
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        // for loop to verify each time preference
        let isMissingDateTimeField = false;
        for (const timePreference of prevBody.timePreferences) {
            if (!timePreference.dayOfWeek && !timePreference.timeRange.startTime) {
                isMissingDateTimeField = true;
            }
        }
        if (isMissingDateTimeField) {
            response.query = 'missing_fields';
            missingFields.dateTime = requiredFields.dateTime;
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevDataExtra = {
                searchBoundary: {
                    startDate: prevStartDate,
                    endDate: prevEndDate,
                },
            };
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepERPT2PTs(prevBody, prevStartDate, prevEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process ');
    }
};
export const ERPT2PTControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
    try {
        const messageLength = messageHistoryObject.messages?.length;
        let userMessage = '';
        for (let i = messageLength; i > 0; i--) {
            const message = messageHistoryObject.messages[i - 1];
            if (message.role === 'user') {
                userMessage = message.content;
                break;
            }
        }
        const userInput = userMessage;
        let eRPT2PTsRes = {
            query: 'completed',
            data: '',
            skill: '',
            prevData: {},
            prevDataExtra: {},
        };
        switch (query) {
            case 'pending':
                const jsonBody = await generateJSONDataFromUserInput(userInput, userCurrentTime);
                const dateTime = await generateDateTime(userInput, userCurrentTime, timezone);
                eRPT2PTsRes = await processERPT2PTsPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
                break;
            case 'missing_fields':
                let priorUserInput = '';
                let priorAssistantOutput = '';
                for (let i = messageLength; i > 0; i--) {
                    const message = messageHistoryObject.messages[i - 1];
                    if (message.role === 'assistant') {
                        priorAssistantOutput = message.content;
                        continue;
                    }
                    if (message.role === 'user') {
                        if (message.content !== userInput) {
                            priorUserInput = message.content;
                            break;
                        }
                    }
                }
                if (!priorUserInput || !priorAssistantOutput) {
                    console.log(priorUserInput, ' priorUserInput');
                    console.log(priorAssistantOutput, ' priorAssistantOutput');
                    throw new Error('no priorUserinput or priorAssistantOutput');
                }
                const jsonMissingFieldsBody = await generateMissingFieldsJSONDataFromUserInput(userInput, priorUserInput, priorAssistantOutput, userCurrentTime);
                const dateMissingFieldsTime = await generateMissingFieldsDateTime(userInput, priorUserInput, priorAssistantOutput, userCurrentTime, timezone);
                eRPT2PTsRes = await processERPT2PTsMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (eRPT2PTsRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, eRPT2PTsRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (eRPT2PTsRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, eRPT2PTsRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = eRPT2PTsRes?.data;
            messageHistoryObject.prevData = eRPT2PTsRes?.prevData;
            messageHistoryObject.prevDataExtra = eRPT2PTsRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = eRPT2PTsRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = eRPT2PTsRes?.prevJsonBody;
        }
        else if (eRPT2PTsRes?.query === 'event_not_found') {
            const assistantMessage = {
                role: 'assistant',
                content: "Oops... I couldn't find the event. Sorry :(",
            };
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'event_not_found';
            messageHistoryObject.required = null;
        }
        return messageHistoryObject;
    }
    catch (e) {
        console.log(e, ' unable to process ERPT2PT control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBS0EsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiwrQkFBK0IsRUFDL0IsbUJBQW1CLEVBQ25CLG1EQUFtRCxFQUNuRCxxREFBcUQsRUFDckQsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3Qiw2QkFBNkIsRUFDN0IsMENBQTBDLEdBQzNDLE1BQU0sd0JBQXdCLENBQUM7QUFFaEMsT0FBTyxFQUNMLDhCQUE4QixFQUM5QixtQ0FBbUMsR0FDcEMsTUFBTSx3Q0FBd0MsQ0FBQztBQUNoRCxPQUFPLEVBQUUsYUFBYSxFQUFFLE1BQU0sYUFBYSxDQUFDO0FBQzVDLE9BQU8sRUFBRSxFQUFFLElBQUksSUFBSSxFQUFFLE1BQU0sTUFBTSxDQUFDO0FBQ2xDLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQVF4RCxNQUFNLENBQUMsTUFBTSxpQkFBaUIsR0FBRyxLQUFLLEVBQ3BDLElBQWlELEVBQ2pELFNBQWlCLEVBQ2pCLE9BQWUsRUFDZixRQUFhLEVBQ2IsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILCtCQUErQjtRQUMvQixNQUFNLFlBQVksR0FBRyxNQUFNLCtCQUErQixDQUFDLElBQUksRUFBRSxLQUFLLENBQUMsQ0FBQztRQUV4RSwrQkFBK0I7UUFDL0IsSUFBSSxDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ2YsU0FBUyxHQUFHLEtBQUssRUFBRSxDQUFDLFFBQVEsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDaEQsQ0FBQztRQUVELElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNiLE9BQU8sR0FBRyxLQUFLLEVBQUUsQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQ3pDLENBQUM7UUFFRCxNQUFNLEdBQUcsR0FBRyxNQUFNLDJCQUEyQixDQUMzQyxJQUFJLEVBQUUsTUFBTSxFQUNaLFlBQVksRUFDWixTQUFTLEVBQ1QsT0FBTyxDQUNSLENBQUM7UUFFRixNQUFNLEVBQUUsR0FBRyxHQUFHLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQztRQUVyQyx1QkFBdUI7UUFDdkIsSUFBSSxDQUFDLEVBQUUsRUFBRSxDQUFDO1lBQ1IsUUFBUSxDQUFDLEtBQUssR0FBRyxpQkFBaUIsQ0FBQztZQUNuQyxPQUFPLFFBQVEsQ0FBQztRQUNsQixDQUFDO1FBRUQsTUFBTSw4QkFBOEIsR0FBNkIsRUFBRSxDQUFDO1FBRXBFLEtBQUssTUFBTSxjQUFjLElBQUksSUFBSSxFQUFFLGVBQWUsRUFBRSxDQUFDO1lBQ25ELElBQUksY0FBYyxDQUFDLFNBQVMsRUFBRSxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7Z0JBQ3pDLEtBQUssTUFBTSxTQUFTLElBQUksY0FBYyxDQUFDLFNBQVMsRUFBRSxDQUFDO29CQUNqRCxNQUFNLHFCQUFxQixHQUEyQjt3QkFDcEQsRUFBRSxFQUFFLElBQUksRUFBRTt3QkFDVixPQUFPLEVBQUUsRUFBRTt3QkFDWCxTQUFTLEVBQUUsYUFBYSxDQUFDLFNBQVMsQ0FBQzt3QkFDbkMsU0FBUyxFQUFFLGNBQWMsRUFBRSxTQUFTLEVBQUUsU0FBUzt3QkFDL0MsT0FBTyxFQUFFLGNBQWMsRUFBRSxTQUFTLEVBQUUsT0FBTzt3QkFDM0MsU0FBUyxFQUFFLEtBQUssRUFBRSxDQUFDLE1BQU0sRUFBRTt3QkFDM0IsV0FBVyxFQUFFLEtBQUssRUFBRSxDQUFDLE1BQU0sRUFBRTt3QkFDN0IsTUFBTSxFQUFFLElBQUksRUFBRSxNQUFNO3FCQUNyQixDQUFDO29CQUVGLDhCQUE4QixDQUFDLElBQUksQ0FBQyxxQkFBcUIsQ0FBQyxDQUFDO2dCQUM3RCxDQUFDO1lBQ0gsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLE1BQU0scUJBQXFCLEdBQTJCO29CQUNwRCxFQUFFLEVBQUUsSUFBSSxFQUFFO29CQUNWLE9BQU8sRUFBRSxFQUFFO29CQUNYLFNBQVMsRUFBRSxjQUFjLEVBQUUsU0FBUyxFQUFFLFNBQVM7b0JBQy9DLE9BQU8sRUFBRSxjQUFjLEVBQUUsU0FBUyxFQUFFLE9BQU87b0JBQzNDLFNBQVMsRUFBRSxLQUFLLEVBQUUsQ0FBQyxNQUFNLEVBQUU7b0JBQzNCLFdBQVcsRUFBRSxLQUFLLEVBQUUsQ0FBQyxNQUFNLEVBQUU7b0JBQzdCLE1BQU0sRUFBRSxJQUFJLEVBQUUsTUFBTTtpQkFDckIsQ0FBQztnQkFFRiw4QkFBOEIsQ0FBQyxJQUFJLENBQUMscUJBQXFCLENBQUMsQ0FBQztZQUM3RCxDQUFDO1FBQ0gsQ0FBQztRQUVELHNDQUFzQztRQUN0QyxNQUFNLHNCQUFzQixHQUMxQixNQUFNLG1DQUFtQyxDQUFDLEVBQUUsQ0FBQyxDQUFDO1FBRWhELHdCQUF3QjtRQUN4QixNQUFNLDhCQUE4QixHQUE2QixFQUFFLENBQUM7UUFFcEUsS0FBSyxNQUFNLDhCQUE4QixJQUFJLDhCQUE4QixFQUFFLENBQUM7WUFDNUUsS0FBSyxNQUFNLHFCQUFxQixJQUFJLHNCQUFzQixFQUFFLENBQUM7Z0JBQzNELElBQ0UsOEJBQThCLENBQUMsU0FBUyxLQUFLLENBQUMsQ0FBQztvQkFDL0MsQ0FBQyw4QkFBOEIsQ0FBQyxTQUFTLEVBQ3pDLENBQUM7b0JBQ0QsSUFDRSxxQkFBcUIsQ0FBQyxTQUFTLEtBQUssQ0FBQyxDQUFDO3dCQUN0QyxDQUFDLHFCQUFxQixDQUFDLFNBQVMsRUFDaEMsQ0FBQzt3QkFDRCxJQUNFLDhCQUE4QixDQUFDLFNBQVM7NEJBQ3hDLHFCQUFxQixDQUFDLFNBQVMsRUFDL0IsQ0FBQzs0QkFDRCw4QkFBOEIsQ0FBQyxJQUFJLENBQUMscUJBQXFCLENBQUMsQ0FBQzt3QkFDN0QsQ0FBQztvQkFDSCxDQUFDO2dCQUNILENBQUM7cUJBQU0sSUFDTCw4QkFBOEIsRUFBRSxTQUFTO29CQUN6QyxxQkFBcUIsRUFBRSxTQUFTLEVBQ2hDLENBQUM7b0JBQ0QsSUFDRSw4QkFBOEIsQ0FBQyxTQUFTO3dCQUN4QyxxQkFBcUIsQ0FBQyxTQUFTLEVBQy9CLENBQUM7d0JBQ0QsOEJBQThCLENBQUMsSUFBSSxDQUFDLHFCQUFxQixDQUFDLENBQUM7b0JBQzdELENBQUM7Z0JBQ0gsQ0FBQztZQUNILENBQUM7UUFDSCxDQUFDO1FBRUQsbUNBQW1DO1FBQ25DLElBQUksOEJBQThCLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQy9DLE1BQU0sOEJBQThCLENBQ2xDLDhCQUE4QixFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUNsRCxDQUFDO1FBQ0osQ0FBQztRQUVELG1CQUFtQjtRQUNuQixRQUFRLENBQUMsS0FBSyxHQUFHLFdBQVcsQ0FBQztRQUM3QixRQUFRLENBQUMsSUFBSSxHQUFHLHFDQUFxQyxDQUFDO1FBQ3RELE9BQU8sUUFBUSxDQUFDO0lBQ2xCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsZ0NBQWdDLENBQUMsQ0FBQztJQUNuRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsTUFBTSxDQUFDLE1BQU0sc0JBQXNCLEdBQUcsS0FBSyxFQUN6QyxNQUFjLEVBQ2QsUUFBZ0IsRUFDaEIsUUFBNkIsRUFDN0IsWUFBOEIsRUFDOUIsV0FBbUIsRUFDVSxFQUFFO0lBQy9CLElBQUksQ0FBQztRQUNILE1BQU0sY0FBYyxHQUFHLG1CQUFtQixDQUN4QyxRQUFRLEVBQ1IsWUFBWSxFQUNaLFdBQVcsQ0FDWixDQUFDO1FBRUYsSUFBSSxTQUFTLEdBQUcsY0FBYyxDQUFDLFNBQVMsQ0FBQztRQUN6QyxJQUFJLE9BQU8sR0FBRyxjQUFjLENBQUMsT0FBTyxDQUFDO1FBRXJDLE1BQU0sSUFBSSxHQUFnRDtZQUN4RCxNQUFNO1lBQ04sUUFBUTtZQUNSLEtBQUssRUFDSCxRQUFRLEVBQUUsTUFBTSxFQUFFLEtBQUs7Z0JBQ3ZCLFFBQVEsRUFBRSxNQUFNLEVBQUUsT0FBTztnQkFDekIsUUFBUSxFQUFFLE1BQU0sRUFBRSxXQUFXO2dCQUM3QixRQUFRLEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUk7WUFDdkMsTUFBTSxFQUFFLFlBQVksRUFBRSxNQUFhO1lBQ25DLGVBQWUsRUFBRSxZQUFZLEVBQUUsZUFBZTtTQUMvQyxDQUFDO1FBRUYsOEJBQThCO1FBRTlCLE1BQU0sYUFBYSxHQUF1QjtZQUN4QyxRQUFRLEVBQUUsRUFBRTtTQUNiLENBQUM7UUFFRixNQUFNLFFBQVEsR0FBUTtZQUNwQixLQUFLLEVBQUUsRUFBRTtZQUNULElBQUksRUFBRSxFQUFFO1lBQ1IsS0FBSyxFQUFFLHlDQUF5QztTQUNqRCxDQUFDO1FBRUYsSUFBSSxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsQ0FBQztZQUNqQixRQUFRLENBQUMsS0FBSyxHQUFHLGdCQUFnQixDQUFDO1lBQ2xDLGFBQWEsQ0FBQyxRQUFRLEdBQUcsY0FBYyxDQUFDLFFBQVEsQ0FBQztZQUNqRCxRQUFRLENBQUMsSUFBSSxHQUFHLGFBQWEsQ0FBQztZQUM5QixRQUFRLENBQUMsUUFBUSxHQUFHLElBQUksQ0FBQztZQUN6QixRQUFRLENBQUMsYUFBYSxHQUFHO2dCQUN2QixjQUFjO2FBQ2YsQ0FBQztZQUNGLFFBQVEsQ0FBQyxZQUFZLEdBQUcsUUFBUSxDQUFDO1lBQ2pDLFFBQVEsQ0FBQyxnQkFBZ0IsR0FBRyxZQUFZLENBQUM7UUFDM0MsQ0FBQztRQUVELElBQUksQ0FBQyxJQUFJLEVBQUUsZUFBZSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsQ0FBQztZQUNoQyxRQUFRLENBQUMsS0FBSyxHQUFHLGdCQUFnQixDQUFDO1lBQ2xDLGFBQWEsQ0FBQyxRQUFRLEdBQUcsY0FBYyxDQUFDLFFBQVEsQ0FBQztZQUNqRCxRQUFRLENBQUMsSUFBSSxHQUFHLGFBQWEsQ0FBQztZQUM5QixRQUFRLENBQUMsUUFBUSxHQUFHLElBQUksQ0FBQztZQUN6QixRQUFRLENBQUMsYUFBYSxHQUFHO2dCQUN2QixjQUFjO2FBQ2YsQ0FBQztZQUNGLFFBQVEsQ0FBQyxZQUFZLEdBQUcsUUFBUSxDQUFDO1lBQ2pDLFFBQVEsQ0FBQyxnQkFBZ0IsR0FBRyxZQUFZLENBQUM7UUFDM0MsQ0FBQztRQUVELDBDQUEwQztRQUMxQyxJQUFJLHNCQUFzQixHQUFHLEtBQUssQ0FBQztRQUNuQyxLQUFLLE1BQU0sY0FBYyxJQUFJLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztZQUNsRCxJQUFJLENBQUMsY0FBYyxDQUFDLFNBQVMsSUFBSSxDQUFDLGNBQWMsQ0FBQyxTQUFTLENBQUMsU0FBUyxFQUFFLENBQUM7Z0JBQ3JFLHNCQUFzQixHQUFHLElBQUksQ0FBQztZQUNoQyxDQUFDO1FBQ0gsQ0FBQztRQUVELElBQUksc0JBQXNCLEVBQUUsQ0FBQztZQUMzQixRQUFRLENBQUMsS0FBSyxHQUFHLGdCQUFnQixDQUFDO1lBQ2xDLGFBQWEsQ0FBQyxRQUFRLEdBQUcsY0FBYyxDQUFDLFFBQVEsQ0FBQztZQUNqRCxRQUFRLENBQUMsSUFBSSxHQUFHLGFBQWEsQ0FBQztZQUM5QixRQUFRLENBQUMsUUFBUSxHQUFHLElBQUksQ0FBQztZQUN6QixRQUFRLENBQUMsYUFBYSxHQUFHO2dCQUN2QixjQUFjO2FBQ2YsQ0FBQztZQUNGLFFBQVEsQ0FBQyxZQUFZLEdBQUcsUUFBUSxDQUFDO1lBQ2pDLFFBQVEsQ0FBQyxnQkFBZ0IsR0FBRyxZQUFZLENBQUM7UUFDM0MsQ0FBQztRQUVELElBQUksUUFBUSxDQUFDLEtBQUssS0FBSyxnQkFBZ0IsRUFBRSxDQUFDO1lBQ3hDLE9BQU8sUUFBUSxDQUFDO1FBQ2xCLENBQUM7UUFFRCxNQUFNLFNBQVMsR0FBRyxNQUFNLGlCQUFpQixDQUN2QyxJQUFJLEVBQ0osU0FBUyxFQUNULE9BQU8sRUFDUCxRQUFRLENBQ1QsQ0FBQztRQUNGLE9BQU8sU0FBUyxDQUFDO1FBRWpCLGlDQUFpQztRQUVqQyxtQkFBbUI7UUFFbkIsK0JBQStCO1FBQy9CLDBFQUEwRTtRQUUxRSxrQ0FBa0M7UUFDbEMsb0JBQW9CO1FBQ3BCLG9EQUFvRDtRQUNwRCxJQUFJO1FBRUosa0JBQWtCO1FBQ2xCLDZDQUE2QztRQUM3QyxJQUFJO1FBRUosMEZBQTBGO1FBRTFGLHVDQUF1QztRQUV2QywwQkFBMEI7UUFDMUIsYUFBYTtRQUNiLHlDQUF5QztRQUN6QyxzQkFBc0I7UUFDdEIsSUFBSTtRQUVKLHNFQUFzRTtRQUV0RSx3REFBd0Q7UUFFeEQsa0RBQWtEO1FBQ2xELDhEQUE4RDtRQUU5RCxzRUFBc0U7UUFDdEUsOEJBQThCO1FBQzlCLCtCQUErQjtRQUMvQix1REFBdUQ7UUFDdkQsbUVBQW1FO1FBQ25FLCtEQUErRDtRQUMvRCwrQ0FBK0M7UUFDL0MsaURBQWlEO1FBQ2pELDBCQUEwQjtRQUMxQixnQkFBZ0I7UUFFaEIseUVBQXlFO1FBQ3pFLFlBQVk7UUFDWixlQUFlO1FBRWYsa0VBQWtFO1FBQ2xFLDBCQUEwQjtRQUMxQiwyQkFBMkI7UUFDM0IsK0RBQStEO1FBQy9ELDJEQUEyRDtRQUMzRCwyQ0FBMkM7UUFDM0MsNkNBQTZDO1FBQzdDLHNCQUFzQjtRQUN0QixZQUFZO1FBRVoscUVBQXFFO1FBQ3JFLFFBQVE7UUFFUixJQUFJO1FBRUoseUNBQXlDO1FBQ3pDLCtFQUErRTtRQUUvRSwyQkFBMkI7UUFDM0Isc0VBQXNFO1FBRXRFLGlGQUFpRjtRQUVqRixvRUFBb0U7UUFFcEUsZUFBZTtRQUNmLGdFQUFnRTtRQUNoRSxnRUFBZ0U7UUFFaEUsbUJBQW1CO1FBQ25CLDJEQUEyRDtRQUMzRCwyREFBMkQ7UUFFM0Qsc0dBQXNHO1FBQ3RHLGlGQUFpRjtRQUNqRixvQkFBb0I7UUFDcEIsZ0JBQWdCO1FBQ2hCLHVHQUF1RztRQUV2RyxrR0FBa0c7UUFDbEcsNkVBQTZFO1FBQzdFLGdCQUFnQjtRQUVoQixZQUFZO1FBQ1osUUFBUTtRQUNSLElBQUk7UUFFSixzQ0FBc0M7UUFDdEMsb0RBQW9EO1FBQ3BELDhGQUE4RjtRQUM5RixJQUFJO1FBRUosc0JBQXNCO1FBQ3RCLCtCQUErQjtRQUUvQixrQkFBa0I7SUFDcEIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUNULENBQUMsRUFDRCxnRUFBZ0UsQ0FDakUsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSxvQ0FBb0MsR0FBRyxLQUFLLEVBQ3ZELE1BQWMsRUFDZCxRQUFnQixFQUNoQixRQUE2QixFQUM3QixZQUE4QixFQUM5QixXQUFtQixFQUNuQixvQkFBNkMsRUFDN0MsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sY0FBYyxHQUFHLG1CQUFtQixDQUN4QyxRQUFRLEVBQ1IsWUFBWSxFQUNaLFdBQVcsQ0FDWixDQUFDO1FBRUYsSUFBSSxTQUFTLEdBQUcsY0FBYyxDQUFDLFNBQVMsQ0FBQztRQUN6QyxJQUFJLE9BQU8sR0FBRyxjQUFjLENBQUMsT0FBTyxDQUFDO1FBRXJDLE1BQU0sT0FBTyxHQUFnRDtZQUMzRCxNQUFNO1lBQ04sUUFBUTtZQUNSLEtBQUssRUFDSCxRQUFRLEVBQUUsTUFBTSxFQUFFLEtBQUs7Z0JBQ3ZCLFFBQVEsRUFBRSxNQUFNLEVBQUUsT0FBTztnQkFDekIsUUFBUSxFQUFFLE1BQU0sRUFBRSxXQUFXO2dCQUM3QixRQUFRLEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUk7Z0JBQ3JDLG9CQUFvQixFQUFFLFlBQVksRUFBRSxNQUFNLEVBQUUsS0FBSztnQkFDakQsb0JBQW9CLEVBQUUsWUFBWSxFQUFFLE1BQU0sRUFBRSxPQUFPO2dCQUNuRCxvQkFBb0IsRUFBRSxZQUFZLEVBQUUsTUFBTSxFQUFFLFdBQVc7Z0JBQ3ZELG9CQUFvQixFQUFFLFlBQVksRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSTtZQUNqRSxNQUFNLEVBQUUsWUFBWSxFQUFFLE1BQWE7WUFDbkMsZUFBZSxFQUNiLFlBQVksRUFBRSxlQUFlO2dCQUM3QixvQkFBb0IsRUFBRSxnQkFBZ0IsRUFBRSxlQUFlO2dCQUN2RCxFQUFFO1NBQ0wsQ0FBQztRQUVGLE1BQU0sUUFBUSxHQUFnRDtZQUM1RCxHQUFHLG9CQUFvQixFQUFFLFFBQVE7U0FDbEMsQ0FBQztRQUVGLElBQUksQ0FBQyxRQUFRLEVBQUUsTUFBTSxFQUFFLENBQUM7WUFDdEIsUUFBUSxDQUFDLE1BQU0sR0FBRyxPQUFPLEVBQUUsTUFBTSxDQUFDO1FBQ3BDLENBQUM7UUFFRCxJQUFJLENBQUMsUUFBUSxFQUFFLFFBQVEsRUFBRSxDQUFDO1lBQ3hCLFFBQVEsQ0FBQyxRQUFRLEdBQUcsUUFBUSxJQUFJLE9BQU8sRUFBRSxRQUFRLENBQUM7UUFDcEQsQ0FBQztRQUVELElBQUksQ0FBQyxRQUFRLEVBQUUsS0FBSyxFQUFFLENBQUM7WUFDckIsUUFBUSxDQUFDLEtBQUssR0FBRyxPQUFPLEVBQUUsS0FBSyxDQUFDO1FBQ2xDLENBQUM7UUFFRCxJQUFJLENBQUMsQ0FBQyxRQUFRLEVBQUUsZUFBZSxFQUFFLE1BQU0sR0FBRyxDQUFDLENBQUMsRUFBRSxDQUFDO1lBQzdDLFFBQVEsQ0FBQyxlQUFlLEdBQUcsT0FBTyxFQUFFLGVBQWUsQ0FBQztRQUN0RCxDQUFDO1FBRUQsTUFBTSxrQkFBa0IsR0FDdEIsb0JBQW9CLEVBQUUsYUFBYSxFQUFFLGNBQWMsQ0FBQztRQUV0RCxJQUFJLGFBQWEsR0FBRyxrQkFBa0IsRUFBRSxTQUFTLENBQUM7UUFFbEQsSUFBSSxXQUFXLEdBQUcsa0JBQWtCLEVBQUUsT0FBTyxDQUFDO1FBRTlDLElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQztZQUNuQixhQUFhLEdBQUcsU0FBUyxDQUFDO1FBQzVCLENBQUM7UUFFRCxJQUFJLENBQUMsV0FBVyxFQUFFLENBQUM7WUFDakIsV0FBVyxHQUFHLE9BQU8sQ0FBQztRQUN4QixDQUFDO1FBRUQsOEJBQThCO1FBRTlCLE1BQU0sYUFBYSxHQUF1QjtZQUN4QyxRQUFRLEVBQUUsRUFBRTtTQUNiLENBQUM7UUFFRixNQUFNLFFBQVEsR0FBUTtZQUNwQixLQUFLLEVBQUUsRUFBRTtZQUNULElBQUksRUFBRSxFQUFFO1lBQ1IsS0FBSyxFQUFFLHlDQUF5QztTQUNqRCxDQUFDO1FBRUYsSUFBSSxDQUFDLFFBQVEsRUFBRSxLQUFLLEVBQUUsQ0FBQztZQUNyQixRQUFRLENBQUMsS0FBSyxHQUFHLGdCQUFnQixDQUFDO1lBQ2xDLGFBQWEsQ0FBQyxRQUFRLEdBQUcsY0FBYyxDQUFDLFFBQVEsQ0FBQztZQUNqRCxRQUFRLENBQUMsSUFBSSxHQUFHLGFBQWEsQ0FBQztZQUM5QixRQUFRLENBQUMsUUFBUSxHQUFHLFFBQVEsQ0FBQztZQUM3QixRQUFRLENBQUMsYUFBYSxHQUFHO2dCQUN2QixjQUFjLEVBQUU7b0JBQ2QsU0FBUyxFQUFFLGFBQWE7b0JBQ3hCLE9BQU8sRUFBRSxXQUFXO2lCQUNyQjthQUNGLENBQUM7WUFDRixRQUFRLENBQUMsWUFBWSxHQUFHLFFBQVEsQ0FBQztZQUNqQyxRQUFRLENBQUMsZ0JBQWdCLEdBQUcsWUFBWSxDQUFDO1FBQzNDLENBQUM7UUFFRCxJQUFJLENBQUMsUUFBUSxFQUFFLGVBQWUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLENBQUM7WUFDcEMsUUFBUSxDQUFDLEtBQUssR0FBRyxnQkFBZ0IsQ0FBQztZQUNsQyxhQUFhLENBQUMsUUFBUSxHQUFHLGNBQWMsQ0FBQyxRQUFRLENBQUM7WUFDakQsUUFBUSxDQUFDLElBQUksR0FBRyxhQUFhLENBQUM7WUFDOUIsUUFBUSxDQUFDLFFBQVEsR0FBRyxRQUFRLENBQUM7WUFDN0IsUUFBUSxDQUFDLGFBQWEsR0FBRztnQkFDdkIsY0FBYyxFQUFFO29CQUNkLFNBQVMsRUFBRSxhQUFhO29CQUN4QixPQUFPLEVBQUUsV0FBVztpQkFDckI7YUFDRixDQUFDO1lBQ0YsUUFBUSxDQUFDLFlBQVksR0FBRyxRQUFRLENBQUM7WUFDakMsUUFBUSxDQUFDLGdCQUFnQixHQUFHLFlBQVksQ0FBQztRQUMzQyxDQUFDO1FBRUQsMENBQTBDO1FBQzFDLElBQUksc0JBQXNCLEdBQUcsS0FBSyxDQUFDO1FBQ25DLEtBQUssTUFBTSxjQUFjLElBQUksUUFBUSxDQUFDLGVBQWUsRUFBRSxDQUFDO1lBQ3RELElBQUksQ0FBQyxjQUFjLENBQUMsU0FBUyxJQUFJLENBQUMsY0FBYyxDQUFDLFNBQVMsQ0FBQyxTQUFTLEVBQUUsQ0FBQztnQkFDckUsc0JBQXNCLEdBQUcsSUFBSSxDQUFDO1lBQ2hDLENBQUM7UUFDSCxDQUFDO1FBRUQsSUFBSSxzQkFBc0IsRUFBRSxDQUFDO1lBQzNCLFFBQVEsQ0FBQyxLQUFLLEdBQUcsZ0JBQWdCLENBQUM7WUFDbEMsYUFBYSxDQUFDLFFBQVEsR0FBRyxjQUFjLENBQUMsUUFBUSxDQUFDO1lBQ2pELFFBQVEsQ0FBQyxJQUFJLEdBQUcsYUFBYSxDQUFDO1lBQzlCLFFBQVEsQ0FBQyxRQUFRLEdBQUcsUUFBUSxDQUFDO1lBQzdCLFFBQVEsQ0FBQyxhQUFhLEdBQUc7Z0JBQ3ZCLGNBQWMsRUFBRTtvQkFDZCxTQUFTLEVBQUUsYUFBYTtvQkFDeEIsT0FBTyxFQUFFLFdBQVc7aUJBQ3JCO2FBQ0YsQ0FBQztZQUNGLFFBQVEsQ0FBQyxZQUFZLEdBQUcsUUFBUSxDQUFDO1lBQ2pDLFFBQVEsQ0FBQyxnQkFBZ0IsR0FBRyxZQUFZLENBQUM7UUFDM0MsQ0FBQztRQUVELElBQUksUUFBUSxDQUFDLEtBQUssS0FBSyxnQkFBZ0IsRUFBRSxDQUFDO1lBQ3hDLE9BQU8sUUFBUSxDQUFDO1FBQ2xCLENBQUM7UUFFRCxNQUFNLFNBQVMsR0FBRyxNQUFNLGlCQUFpQixDQUN2QyxRQUFRLEVBQ1IsYUFBYSxFQUNiLFdBQVcsRUFDWCxRQUFRLENBQ1QsQ0FBQztRQUVGLE9BQU8sU0FBUyxDQUFDO0lBQ25CLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUscUJBQXFCLENBQUMsQ0FBQztJQUN4QyxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsTUFBTSxDQUFDLE1BQU0sb0JBQW9CLEdBQUcsS0FBSyxFQUN2QyxNQUFjLEVBQ2QsTUFBYyxFQUNkLFFBQWdCLEVBQ2hCLG9CQUE2QyxFQUM3QyxlQUF1QixFQUN2QixLQUFxRSxFQUNyRSxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxhQUFhLEdBQUcsb0JBQW9CLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztRQUM1RCxJQUFJLFdBQVcsR0FBRyxFQUFFLENBQUM7UUFDckIsS0FBSyxJQUFJLENBQUMsR0FBRyxhQUFhLEVBQUUsQ0FBQyxHQUFHLENBQUMsRUFBRSxDQUFDLEVBQUUsRUFBRSxDQUFDO1lBQ3ZDLE1BQU0sT0FBTyxHQUFHLG9CQUFvQixDQUFDLFFBQVEsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxDQUFDLENBQUM7WUFFckQsSUFBSSxPQUFPLENBQUMsSUFBSSxLQUFLLE1BQU0sRUFBRSxDQUFDO2dCQUM1QixXQUFXLEdBQUcsT0FBTyxDQUFDLE9BQU8sQ0FBQztnQkFDOUIsTUFBTTtZQUNSLENBQUM7UUFDSCxDQUFDO1FBRUQsTUFBTSxTQUFTLEdBQUcsV0FBVyxDQUFDO1FBRTlCLElBQUksV0FBVyxHQUF1QjtZQUNwQyxLQUFLLEVBQUUsV0FBVztZQUNsQixJQUFJLEVBQUUsRUFBRTtZQUNSLEtBQUssRUFBRSxFQUFFO1lBQ1QsUUFBUSxFQUFFLEVBQUU7WUFDWixhQUFhLEVBQUUsRUFBRTtTQUNsQixDQUFDO1FBRUYsUUFBUSxLQUFLLEVBQUUsQ0FBQztZQUNkLEtBQUssU0FBUztnQkFDWixNQUFNLFFBQVEsR0FBRyxNQUFNLDZCQUE2QixDQUNsRCxTQUFTLEVBQ1QsZUFBZSxDQUNoQixDQUFDO2dCQUNGLE1BQU0sUUFBUSxHQUFHLE1BQU0sZ0JBQWdCLENBQ3JDLFNBQVMsRUFDVCxlQUFlLEVBQ2YsUUFBUSxDQUNULENBQUM7Z0JBQ0YsV0FBVyxHQUFHLE1BQU0sc0JBQXNCLENBQ3hDLE1BQU0sRUFDTixRQUFRLEVBQ1IsUUFBUSxFQUNSLFFBQVEsRUFDUixlQUFlLENBQ2hCLENBQUM7Z0JBQ0YsTUFBTTtZQUNSLEtBQUssZ0JBQWdCO2dCQUNuQixJQUFJLGNBQWMsR0FBRyxFQUFFLENBQUM7Z0JBQ3hCLElBQUksb0JBQW9CLEdBQUcsRUFBRSxDQUFDO2dCQUU5QixLQUFLLElBQUksQ0FBQyxHQUFHLGFBQWEsRUFBRSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsRUFBRSxFQUFFLENBQUM7b0JBQ3ZDLE1BQU0sT0FBTyxHQUFHLG9CQUFvQixDQUFDLFFBQVEsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxDQUFDLENBQUM7b0JBRXJELElBQUksT0FBTyxDQUFDLElBQUksS0FBSyxXQUFXLEVBQUUsQ0FBQzt3QkFDakMsb0JBQW9CLEdBQUcsT0FBTyxDQUFDLE9BQU8sQ0FBQzt3QkFDdkMsU0FBUztvQkFDWCxDQUFDO29CQUVELElBQUksT0FBTyxDQUFDLElBQUksS0FBSyxNQUFNLEVBQUUsQ0FBQzt3QkFDNUIsSUFBSSxPQUFPLENBQUMsT0FBTyxLQUFLLFNBQVMsRUFBRSxDQUFDOzRCQUNsQyxjQUFjLEdBQUcsT0FBTyxDQUFDLE9BQU8sQ0FBQzs0QkFDakMsTUFBTTt3QkFDUixDQUFDO29CQUNILENBQUM7Z0JBQ0gsQ0FBQztnQkFFRCxJQUFJLENBQUMsY0FBYyxJQUFJLENBQUMsb0JBQW9CLEVBQUUsQ0FBQztvQkFDN0MsT0FBTyxDQUFDLEdBQUcsQ0FBQyxjQUFjLEVBQUUsaUJBQWlCLENBQUMsQ0FBQztvQkFDL0MsT0FBTyxDQUFDLEdBQUcsQ0FBQyxvQkFBb0IsRUFBRSx1QkFBdUIsQ0FBQyxDQUFDO29CQUMzRCxNQUFNLElBQUksS0FBSyxDQUFDLDJDQUEyQyxDQUFDLENBQUM7Z0JBQy9ELENBQUM7Z0JBQ0QsTUFBTSxxQkFBcUIsR0FDekIsTUFBTSwwQ0FBMEMsQ0FDOUMsU0FBUyxFQUNULGNBQWMsRUFDZCxvQkFBb0IsRUFDcEIsZUFBZSxDQUNoQixDQUFDO2dCQUNKLE1BQU0scUJBQXFCLEdBQUcsTUFBTSw2QkFBNkIsQ0FDL0QsU0FBUyxFQUNULGNBQWMsRUFDZCxvQkFBb0IsRUFDcEIsZUFBZSxFQUNmLFFBQVEsQ0FDVCxDQUFDO2dCQUVGLFdBQVcsR0FBRyxNQUFNLG9DQUFvQyxDQUN0RCxNQUFNLEVBQ04sUUFBUSxFQUNSLHFCQUFxQixFQUNyQixxQkFBcUIsRUFDckIsZUFBZSxFQUNmLG9CQUFvQixDQUNyQixDQUFDO2dCQUNGLE1BQU07UUFDVixDQUFDO1FBRUQsSUFBSSxXQUFXLEVBQUUsS0FBSyxLQUFLLFdBQVcsRUFBRSxDQUFDO1lBQ3ZDLE1BQU0sZ0JBQWdCLEdBQ3BCLE1BQU0sbURBQW1ELENBQ3ZELE1BQU0sRUFDTixXQUFXLENBQUMsSUFBYyxFQUMxQixvQkFBb0IsQ0FDckIsQ0FBQztZQUVKLG9CQUFvQixDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztZQUNyRCxvQkFBb0IsQ0FBQyxLQUFLLEdBQUcsV0FBVyxDQUFDO1lBQ3pDLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxJQUFJLENBQUM7UUFDdkMsQ0FBQzthQUFNLElBQUksV0FBVyxFQUFFLEtBQUssS0FBSyxnQkFBZ0IsRUFBRSxDQUFDO1lBQ25ELE1BQU0sZ0JBQWdCLEdBQ3BCLE1BQU0scURBQXFELENBQ3pELE1BQU0sRUFDTixXQUFXLEVBQUUsSUFBMEIsRUFDdkMsb0JBQW9CLENBQ3JCLENBQUM7WUFFSixvQkFBb0IsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7WUFDckQsb0JBQW9CLENBQUMsS0FBSyxHQUFHLGdCQUFnQixDQUFDO1lBQzlDLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxXQUFXLEVBQUUsSUFBMEIsQ0FBQztZQUN4RSxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsV0FBVyxFQUFFLFFBQVEsQ0FBQztZQUN0RCxvQkFBb0IsQ0FBQyxhQUFhLEdBQUcsV0FBVyxFQUFFLGFBQWEsQ0FBQztZQUNoRSxvQkFBb0IsQ0FBQyxnQkFBZ0IsR0FBRyxXQUFXLEVBQUUsZ0JBQWdCLENBQUM7WUFDdEUsb0JBQW9CLENBQUMsWUFBWSxHQUFHLFdBQVcsRUFBRSxZQUFZLENBQUM7UUFDaEUsQ0FBQzthQUFNLElBQUksV0FBVyxFQUFFLEtBQUssS0FBSyxpQkFBaUIsRUFBRSxDQUFDO1lBQ3BELE1BQU0sZ0JBQWdCLEdBQXlCO2dCQUM3QyxJQUFJLEVBQUUsV0FBVztnQkFDakIsT0FBTyxFQUFFLDZDQUE2QzthQUN2RCxDQUFDO1lBRUYsb0JBQW9CLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQ3JELG9CQUFvQixDQUFDLEtBQUssR0FBRyxpQkFBaUIsQ0FBQztZQUMvQyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO1FBQ3ZDLENBQUM7UUFFRCxPQUFPLG9CQUFvQixDQUFDO0lBQzlCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsbURBQW1ELENBQUMsQ0FBQztJQUN0RSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IERhdGVUaW1lSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvRGF0ZVRpbWVKU09OSlNPTlR5cGUnO1xuaW1wb3J0IFVzZXJJbnB1dFRvSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVXNlcklucHV0VG9KU09OVHlwZSc7XG5pbXBvcnQgUmVzcG9uc2VBY3Rpb25UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1Jlc3BvbnNlQWN0aW9uVHlwZSc7XG5pbXBvcnQgeyBFZGl0UmVtb3ZlUHJlZmVycmVkVGltZVRvUHJlZmVycmVkVGltZXNUeXBlIH0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgUmVxdWlyZWRGaWVsZHNUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1JlcXVpcmVkRmllbGRzVHlwZSc7XG5pbXBvcnQgcmVxdWlyZWRGaWVsZHMgZnJvbSAnLi9yZXF1aXJlZEZpZWxkcyc7XG5pbXBvcnQge1xuICBhbGxFdmVudFdpdGhEYXRlc09wZW5TZWFyY2gsXG4gIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IsXG4gIGV2ZW50U2VhcmNoQm91bmRhcnksXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMsXG4gIGdlbmVyYXRlRGF0ZVRpbWUsXG4gIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZSxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0LFxufSBmcm9tICdAY2hhdC9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1ByZWZlcnJlZFRpbWVSYW5nZVR5cGUnO1xuaW1wb3J0IHtcbiAgZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5SWRzLFxuICBsaXN0UHJlZmVycmVkVGltZVJhbmdlc0dpdmVuRXZlbnRJZCxcbn0gZnJvbSAnLi4vcmVzb2x2ZUNvbmZsaWN0aW5nRXZlbnRzL2FwaS1oZWxwZXInO1xuaW1wb3J0IHsgRGF5T2ZXZWVrRW51bSB9IGZyb20gJy4vY29uc3RhbnRzJztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvZGF0ZS11dGlscyc7XG5pbXBvcnQge1xuICBBc3Npc3RhbnRNZXNzYWdlVHlwZSxcbiAgU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcyc7XG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBTZWFyY2hCb3VuZGFyeVR5cGUgfSBmcm9tICcuLi9kZWxldGVUYXNrL3R5cGVzJztcblxuZXhwb3J0IGNvbnN0IGZpbmFsU3RlcEVSUFQyUFRzID0gYXN5bmMgKFxuICBib2R5OiBFZGl0UmVtb3ZlUHJlZmVycmVkVGltZVRvUHJlZmVycmVkVGltZXNUeXBlLFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nLFxuICByZXNwb25zZTogYW55XG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBjb252ZXJ0IHRvIHZlY3RvciBmb3Igc2VhcmNoXG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSk7XG5cbiAgICAvLyAgYWxsRXZlbnRXaXRoRXZlbnRPcGVuU2VhcmNoXG4gICAgaWYgKCFzdGFydERhdGUpIHtcbiAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIWVuZERhdGUpIHtcbiAgICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaChcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGVcbiAgICApO1xuXG4gICAgY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkO1xuXG4gICAgLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICBpZiAoIWlkKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXNXYW50UmVtb3ZlZDogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IHRpbWVwcmVmZXJlbmNlIG9mIGJvZHk/LnRpbWVQcmVmZXJlbmNlcykge1xuICAgICAgaWYgKHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBmb3IgKGNvbnN0IGRheU9mV2VlayBvZiB0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWspIHtcbiAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZDogaWQsXG4gICAgICAgICAgICBkYXlPZldlZWs6IERheU9mV2Vla0VudW1bZGF5T2ZXZWVrXSxcbiAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgfTtcblxuICAgICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXNXYW50UmVtb3ZlZC5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIGV2ZW50SWQ6IGlkLFxuICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICB9O1xuXG4gICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXNXYW50UmVtb3ZlZC5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gbGlzdCBleGlzdGluZyBwcmVmZXJyZWQgdGltZSByYW5nZXNcbiAgICBjb25zdCBvbGRQcmVmZXJyZWRUaW1lUmFuZ2VzID1cbiAgICAgIGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkKGlkKTtcblxuICAgIC8vIGZpbmQgdmFsdWVzIHRvIHJlbW92ZVxuICAgIGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZXNUb0JlUmVtb3ZlZDogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW107XG5cbiAgICBmb3IgKGNvbnN0IHByZWZlcnJlZFRpbWVSYW5nZVdhbnRUb1JlbW92ZSBvZiBwcmVmZXJyZWRUaW1lUmFuZ2VzV2FudFJlbW92ZWQpIHtcbiAgICAgIGZvciAoY29uc3Qgb2xkUHJlZmVycmVkVGltZVJhbmdlIG9mIG9sZFByZWZlcnJlZFRpbWVSYW5nZXMpIHtcbiAgICAgICAgaWYgKFxuICAgICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZVdhbnRUb1JlbW92ZS5kYXlPZldlZWsgPT09IC0xIHx8XG4gICAgICAgICAgIXByZWZlcnJlZFRpbWVSYW5nZVdhbnRUb1JlbW92ZS5kYXlPZldlZWtcbiAgICAgICAgKSB7XG4gICAgICAgICAgaWYgKFxuICAgICAgICAgICAgb2xkUHJlZmVycmVkVGltZVJhbmdlLmRheU9mV2VlayA9PT0gLTEgfHxcbiAgICAgICAgICAgICFvbGRQcmVmZXJyZWRUaW1lUmFuZ2UuZGF5T2ZXZWVrXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBpZiAoXG4gICAgICAgICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZVdhbnRUb1JlbW92ZS5zdGFydFRpbWUgPT09XG4gICAgICAgICAgICAgIG9sZFByZWZlcnJlZFRpbWVSYW5nZS5zdGFydFRpbWVcbiAgICAgICAgICAgICkge1xuICAgICAgICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzVG9CZVJlbW92ZWQucHVzaChvbGRQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIGlmIChcbiAgICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VXYW50VG9SZW1vdmU/LmRheU9mV2VlayA9PT1cbiAgICAgICAgICBvbGRQcmVmZXJyZWRUaW1lUmFuZ2U/LmRheU9mV2Vla1xuICAgICAgICApIHtcbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VXYW50VG9SZW1vdmUuc3RhcnRUaW1lID09PVxuICAgICAgICAgICAgb2xkUHJlZmVycmVkVGltZVJhbmdlLnN0YXJ0VGltZVxuICAgICAgICAgICkge1xuICAgICAgICAgICAgcHJlZmVycmVkVGltZVJhbmdlc1RvQmVSZW1vdmVkLnB1c2gob2xkUHJlZmVycmVkVGltZVJhbmdlKTtcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBkZWxldGUgdGltZSByYW5nZXMgdG8gYmUgcmVtb3ZlZFxuICAgIGlmIChwcmVmZXJyZWRUaW1lUmFuZ2VzVG9CZVJlbW92ZWQ/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNCeUlkcyhcbiAgICAgICAgcHJlZmVycmVkVGltZVJhbmdlc1RvQmVSZW1vdmVkPy5tYXAoKHApID0+IHA/LmlkKVxuICAgICAgKTtcbiAgICB9XG5cbiAgICAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICByZXNwb25zZS5kYXRhID0gJ3N1Y2Nlc3NmdWxseSByZW1vdmVkIHByZWZlcnJlZCB0aW1lJztcbiAgICByZXR1cm4gcmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBmaW5hbCBzdGVwIEVSUFQyUFRzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRVJQVDJQVHNQZW5kaW5nID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZ1xuKTogUHJvbWlzZTxSZXNwb25zZUFjdGlvblR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBzZWFyY2hCb3VuZGFyeSA9IGV2ZW50U2VhcmNoQm91bmRhcnkoXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGRhdGVKU09OQm9keSxcbiAgICAgIGN1cnJlbnRUaW1lXG4gICAgKTtcblxuICAgIGxldCBzdGFydERhdGUgPSBzZWFyY2hCb3VuZGFyeS5zdGFydERhdGU7XG4gICAgbGV0IGVuZERhdGUgPSBzZWFyY2hCb3VuZGFyeS5lbmREYXRlO1xuXG4gICAgY29uc3QgYm9keTogRWRpdFJlbW92ZVByZWZlcnJlZFRpbWVUb1ByZWZlcnJlZFRpbWVzVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgdGltZVByZWZlcmVuY2VzOiBkYXRlSlNPTkJvZHk/LnRpbWVQcmVmZXJlbmNlcyxcbiAgICB9O1xuXG4gICAgLy8gdmFsaWRhdGUgZm9yIG1pc3NpbmcgZmllbGRzXG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAnZWRpdFJlbW92ZVByZWZlcnJlZFRpbWVUb1ByZWZlcnJlZFRpbWVzJyxcbiAgICB9O1xuXG4gICAgaWYgKCFib2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZCA9IHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKCFib2R5Py50aW1lUHJlZmVyZW5jZXM/LlswXSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZSA9IHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgLy8gZm9yIGxvb3AgdG8gdmVyaWZ5IGVhY2ggdGltZSBwcmVmZXJlbmNlXG4gICAgbGV0IGlzTWlzc2luZ0RhdGVUaW1lRmllbGQgPSBmYWxzZTtcbiAgICBmb3IgKGNvbnN0IHRpbWVQcmVmZXJlbmNlIG9mIGJvZHkudGltZVByZWZlcmVuY2VzKSB7XG4gICAgICBpZiAoIXRpbWVQcmVmZXJlbmNlLmRheU9mV2VlayAmJiAhdGltZVByZWZlcmVuY2UudGltZVJhbmdlLnN0YXJ0VGltZSkge1xuICAgICAgICBpc01pc3NpbmdEYXRlVGltZUZpZWxkID0gdHJ1ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoaXNNaXNzaW5nRGF0ZVRpbWVGaWVsZCkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZSA9IHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwRVJQVDJQVHMoXG4gICAgICBib2R5LFxuICAgICAgc3RhcnREYXRlLFxuICAgICAgZW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuXG4gICAgLy8gZGF0YSB2YWxpZGF0ZWQgc3RhcnQgYXBpIGNhbGxzXG5cbiAgICAvLyBzZWFyY2ggZm9yIGV2ZW50XG5cbiAgICAvLyBjb252ZXJ0IHRvIHZlY3RvciBmb3Igc2VhcmNoXG4gICAgLy8gY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSlcblxuICAgIC8vIC8vICBhbGxFdmVudFdpdGhFdmVudE9wZW5TZWFyY2hcbiAgICAvLyBpZiAoIXN0YXJ0RGF0ZSkge1xuICAgIC8vICAgICBzdGFydERhdGUgPSBkYXlqcygpLnN1YnRyYWN0KDIsICd3JykuZm9ybWF0KClcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoIWVuZERhdGUpIHtcbiAgICAvLyAgICAgZW5kRGF0ZSA9IGRheWpzKCkuYWRkKDQsICd3JykuZm9ybWF0KClcbiAgICAvLyB9XG5cbiAgICAvLyBjb25zdCByZXMgPSBhd2FpdCBhbGxFdmVudFdpdGhEYXRlc09wZW5TZWFyY2godXNlcklkLCBzZWFyY2hWZWN0b3IsIHN0YXJ0RGF0ZSwgZW5kRGF0ZSlcblxuICAgIC8vIGNvbnN0IGlkID0gcmVzPy5oaXRzPy5oaXRzPy5bMF0/Ll9pZFxuXG4gICAgLy8gLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICAvLyBpZiAoIWlkKSB7XG4gICAgLy8gICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCdcbiAgICAvLyAgICAgcmV0dXJuIHJlc3BvbnNlXG4gICAgLy8gfVxuXG4gICAgLy8gY29uc3QgcHJlZmVycmVkVGltZVJhbmdlc1dhbnRSZW1vdmVkOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXVxuXG4gICAgLy8gZm9yIChjb25zdCB0aW1lcHJlZmVyZW5jZSBvZiBib2R5Py50aW1lUHJlZmVyZW5jZXMpIHtcblxuICAgIC8vICAgICBpZiAodGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgICAgICBmb3IgKGNvbnN0IGRheU9mV2VlayBvZiB0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWspIHtcblxuICAgIC8vICAgICAgICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAvLyAgICAgICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZXZlbnRJZDogaWQsXG4gICAgLy8gICAgICAgICAgICAgICAgIGRheU9mV2VlazogRGF5T2ZXZWVrRW51bVtkYXlPZldlZWtdLFxuICAgIC8vICAgICAgICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAvLyAgICAgICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgIC8vICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgdXNlcklkLFxuICAgIC8vICAgICAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXNXYW50UmVtb3ZlZC5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSlcbiAgICAvLyAgICAgICAgIH1cbiAgICAvLyAgICAgfSBlbHNlIHtcblxuICAgIC8vICAgICAgICAgY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlID0ge1xuICAgIC8vICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgLy8gICAgICAgICAgICAgZXZlbnRJZDogaWQsXG4gICAgLy8gICAgICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAvLyAgICAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgdXNlcklkLFxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzV2FudFJlbW92ZWQucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpXG4gICAgLy8gICAgIH1cblxuICAgIC8vIH1cblxuICAgIC8vIC8vIGxpc3QgZXhpc3RpbmcgcHJlZmVycmVkIHRpbWUgcmFuZ2VzXG4gICAgLy8gY29uc3Qgb2xkUHJlZmVycmVkVGltZVJhbmdlcyA9IGF3YWl0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkKGlkKVxuXG4gICAgLy8gLy8gZmluZCB2YWx1ZXMgdG8gcmVtb3ZlXG4gICAgLy8gY29uc3QgcHJlZmVycmVkVGltZVJhbmdlc1RvQmVSZW1vdmVkOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXVxuXG4gICAgLy8gZm9yIChjb25zdCBwcmVmZXJyZWRUaW1lUmFuZ2VXYW50VG9SZW1vdmUgb2YgcHJlZmVycmVkVGltZVJhbmdlc1dhbnRSZW1vdmVkKSB7XG5cbiAgICAvLyAgICAgZm9yIChjb25zdCBvbGRQcmVmZXJyZWRUaW1lUmFuZ2Ugb2Ygb2xkUHJlZmVycmVkVGltZVJhbmdlcykge1xuXG4gICAgLy8gICAgICAgICBpZiAoXG4gICAgLy8gICAgICAgICAgICAgKHByZWZlcnJlZFRpbWVSYW5nZVdhbnRUb1JlbW92ZS5kYXlPZldlZWsgPT09IC0xKVxuICAgIC8vICAgICAgICAgICAgIHx8ICghcHJlZmVycmVkVGltZVJhbmdlV2FudFRvUmVtb3ZlLmRheU9mV2VlaykpIHtcblxuICAgIC8vICAgICAgICAgICAgIGlmIChcbiAgICAvLyAgICAgICAgICAgICAgICAgKG9sZFByZWZlcnJlZFRpbWVSYW5nZS5kYXlPZldlZWsgPT09IC0xKVxuICAgIC8vICAgICAgICAgICAgICAgICB8fCAoIW9sZFByZWZlcnJlZFRpbWVSYW5nZS5kYXlPZldlZWspKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKHByZWZlcnJlZFRpbWVSYW5nZVdhbnRUb1JlbW92ZS5zdGFydFRpbWUgPT09IG9sZFByZWZlcnJlZFRpbWVSYW5nZS5zdGFydFRpbWUpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHByZWZlcnJlZFRpbWVSYW5nZXNUb0JlUmVtb3ZlZC5wdXNoKG9sZFByZWZlcnJlZFRpbWVSYW5nZSlcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgIH0gZWxzZSBpZiAocHJlZmVycmVkVGltZVJhbmdlV2FudFRvUmVtb3ZlPy5kYXlPZldlZWsgPT09IG9sZFByZWZlcnJlZFRpbWVSYW5nZT8uZGF5T2ZXZWVrKSB7XG5cbiAgICAvLyAgICAgICAgICAgICBpZiAocHJlZmVycmVkVGltZVJhbmdlV2FudFRvUmVtb3ZlLnN0YXJ0VGltZSA9PT0gb2xkUHJlZmVycmVkVGltZVJhbmdlLnN0YXJ0VGltZSkge1xuICAgIC8vICAgICAgICAgICAgICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzVG9CZVJlbW92ZWQucHVzaChvbGRQcmVmZXJyZWRUaW1lUmFuZ2UpXG4gICAgLy8gICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICB9XG4gICAgLy8gICAgIH1cbiAgICAvLyB9XG5cbiAgICAvLyAvLyBkZWxldGUgdGltZSByYW5nZXMgdG8gYmUgcmVtb3ZlZFxuICAgIC8vIGlmIChwcmVmZXJyZWRUaW1lUmFuZ2VzVG9CZVJlbW92ZWQ/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgYXdhaXQgZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0J5SWRzKHByZWZlcnJlZFRpbWVSYW5nZXNUb0JlUmVtb3ZlZD8ubWFwKHAgPT4gKHA/LmlkKSkpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gc3VjY2VzcyByZXNwb25zZVxuICAgIC8vIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCdcblxuICAgIC8vIHJldHVybiByZXNwb25zZVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLFxuICAgICAgJyB1bmFibGUgdG8gcHJvY2VzcyBlZGl0IGFuZCBwcmVmZXJyZWQgdGltZSB0byBwcmVmZXJyZWQgdGltZXMgJ1xuICAgICk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRVJQVDJQVHNNaXNzaW5nRmllbGRzUmV0dXJuZWQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICBjb25zdCBuZXdCb2R5OiBFZGl0UmVtb3ZlUHJlZmVycmVkVGltZVRvUHJlZmVycmVkVGltZXNUeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgbWV0aG9kOiBkYXRlSlNPTkJvZHk/Lm1ldGhvZCBhcyBhbnksXG4gICAgICB0aW1lUHJlZmVyZW5jZXM6XG4gICAgICAgIGRhdGVKU09OQm9keT8udGltZVByZWZlcmVuY2VzIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py50aW1lUHJlZmVyZW5jZXMgfHxcbiAgICAgICAgW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHByZXZCb2R5OiBFZGl0UmVtb3ZlUHJlZmVycmVkVGltZVRvUHJlZmVycmVkVGltZXNUeXBlID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IG5ld0JvZHk/LnVzZXJJZDtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aW1lem9uZSkge1xuICAgICAgcHJldkJvZHkudGltZXpvbmUgPSB0aW1lem9uZSB8fCBuZXdCb2R5Py50aW1lem9uZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcHJldkJvZHkudGl0bGUgPSBuZXdCb2R5Py50aXRsZTtcbiAgICB9XG5cbiAgICBpZiAoIShwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkudGltZVByZWZlcmVuY2VzID0gbmV3Qm9keT8udGltZVByZWZlcmVuY2VzO1xuICAgIH1cblxuICAgIGNvbnN0IHByZXZTZWFyY2hCb3VuZGFyeTogU2VhcmNoQm91bmRhcnlUeXBlID1cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy5zZWFyY2hCb3VuZGFyeTtcblxuICAgIGxldCBwcmV2U3RhcnREYXRlID0gcHJldlNlYXJjaEJvdW5kYXJ5Py5zdGFydERhdGU7XG5cbiAgICBsZXQgcHJldkVuZERhdGUgPSBwcmV2U2VhcmNoQm91bmRhcnk/LmVuZERhdGU7XG5cbiAgICBpZiAoIXByZXZTdGFydERhdGUpIHtcbiAgICAgIHByZXZTdGFydERhdGUgPSBzdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2RW5kRGF0ZSkge1xuICAgICAgcHJldkVuZERhdGUgPSBlbmREYXRlO1xuICAgIH1cblxuICAgIC8vIHZhbGlkYXRlIGZvciBtaXNzaW5nIGZpZWxkc1xuXG4gICAgY29uc3QgbWlzc2luZ0ZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICAgICAgcmVxdWlyZWQ6IFtdLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ2VkaXRSZW1vdmVQcmVmZXJyZWRUaW1lVG9QcmVmZXJyZWRUaW1lcycsXG4gICAgfTtcblxuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkID0gcmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeToge1xuICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5bMF0pIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUgPSByZXF1aXJlZEZpZWxkcy5kYXRlVGltZTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgIHNlYXJjaEJvdW5kYXJ5OiB7XG4gICAgICAgICAgc3RhcnREYXRlOiBwcmV2U3RhcnREYXRlLFxuICAgICAgICAgIGVuZERhdGU6IHByZXZFbmREYXRlLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICAvLyBmb3IgbG9vcCB0byB2ZXJpZnkgZWFjaCB0aW1lIHByZWZlcmVuY2VcbiAgICBsZXQgaXNNaXNzaW5nRGF0ZVRpbWVGaWVsZCA9IGZhbHNlO1xuICAgIGZvciAoY29uc3QgdGltZVByZWZlcmVuY2Ugb2YgcHJldkJvZHkudGltZVByZWZlcmVuY2VzKSB7XG4gICAgICBpZiAoIXRpbWVQcmVmZXJlbmNlLmRheU9mV2VlayAmJiAhdGltZVByZWZlcmVuY2UudGltZVJhbmdlLnN0YXJ0VGltZSkge1xuICAgICAgICBpc01pc3NpbmdEYXRlVGltZUZpZWxkID0gdHJ1ZTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICBpZiAoaXNNaXNzaW5nRGF0ZVRpbWVGaWVsZCkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZSA9IHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgc2VhcmNoQm91bmRhcnk6IHtcbiAgICAgICAgICBzdGFydERhdGU6IHByZXZTdGFydERhdGUsXG4gICAgICAgICAgZW5kRGF0ZTogcHJldkVuZERhdGUsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcEVSUFQyUFRzKFxuICAgICAgcHJldkJvZHksXG4gICAgICBwcmV2U3RhcnREYXRlLFxuICAgICAgcHJldkVuZERhdGUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyAnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IEVSUFQyUFRDb250cm9sQ2VudGVyID0gYXN5bmMgKFxuICBvcGVuYWk6IE9wZW5BSSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbiAgdXNlckN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIHF1ZXJ5OiAnbWlzc2luZ19maWVsZHMnIHwgJ2NvbXBsZXRlZCcgfCAnZXZlbnRfbm90X2ZvdW5kJyB8ICdwZW5kaW5nJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGg7XG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG4gICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICB1c2VyTWVzc2FnZSA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgYnJlYWs7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgdXNlcklucHV0ID0gdXNlck1lc3NhZ2U7XG5cbiAgICBsZXQgZVJQVDJQVHNSZXM6IFJlc3BvbnNlQWN0aW9uVHlwZSA9IHtcbiAgICAgIHF1ZXJ5OiAnY29tcGxldGVkJyxcbiAgICAgIGRhdGE6ICcnLFxuICAgICAgc2tpbGw6ICcnLFxuICAgICAgcHJldkRhdGE6IHt9LFxuICAgICAgcHJldkRhdGFFeHRyYToge30sXG4gICAgfTtcblxuICAgIHN3aXRjaCAocXVlcnkpIHtcbiAgICAgIGNhc2UgJ3BlbmRpbmcnOlxuICAgICAgICBjb25zdCBqc29uQm9keSA9IGF3YWl0IGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZVRpbWUgPSBhd2FpdCBnZW5lcmF0ZURhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgZVJQVDJQVHNSZXMgPSBhd2FpdCBwcm9jZXNzRVJQVDJQVHNQZW5kaW5nKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uQm9keSxcbiAgICAgICAgICBkYXRlVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdtaXNzaW5nX2ZpZWxkcyc6XG4gICAgICAgIGxldCBwcmlvclVzZXJJbnB1dCA9ICcnO1xuICAgICAgICBsZXQgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSAnJztcblxuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAnYXNzaXN0YW50Jykge1xuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgIGlmIChtZXNzYWdlLmNvbnRlbnQgIT09IHVzZXJJbnB1dCkge1xuICAgICAgICAgICAgICBwcmlvclVzZXJJbnB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmlvclVzZXJJbnB1dCB8fCAhcHJpb3JBc3Npc3RhbnRPdXRwdXQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvclVzZXJJbnB1dCwgJyBwcmlvclVzZXJJbnB1dCcpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yQXNzaXN0YW50T3V0cHV0LCAnIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBwcmlvclVzZXJpbnB1dCBvciBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGpzb25NaXNzaW5nRmllbGRzQm9keSA9XG4gICAgICAgICAgYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVNaXNzaW5nRmllbGRzVGltZSA9IGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcblxuICAgICAgICBlUlBUMlBUc1JlcyA9IGF3YWl0IHByb2Nlc3NFUlBUMlBUc01pc3NpbmdGaWVsZHNSZXR1cm5lZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbk1pc3NpbmdGaWVsZHNCb2R5LFxuICAgICAgICAgIGRhdGVNaXNzaW5nRmllbGRzVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgfVxuXG4gICAgaWYgKGVSUFQyUFRzUmVzPy5xdWVyeSA9PT0gJ2NvbXBsZXRlZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnkoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGVSUFQyUFRzUmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoZVJQVDJQVHNSZXM/LnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGVSUFQyUFRzUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBlUlBUMlBUc1Jlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IGVSUFQyUFRzUmVzPy5wcmV2RGF0YTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhRXh0cmEgPSBlUlBUMlBUc1Jlcz8ucHJldkRhdGFFeHRyYTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPSBlUlBUMlBUc1Jlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZKc29uQm9keSA9IGVSUFQyUFRzUmVzPy5wcmV2SnNvbkJvZHk7XG4gICAgfSBlbHNlIGlmIChlUlBUMlBUc1Jlcz8ucXVlcnkgPT09ICdldmVudF9ub3RfZm91bmQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6IFwiT29wcy4uLiBJIGNvdWxkbid0IGZpbmQgdGhlIGV2ZW50LiBTb3JyeSA6KFwiLFxuICAgICAgfTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfVxuXG4gICAgcmV0dXJuIG1lc3NhZ2VIaXN0b3J5T2JqZWN0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBFUlBUMlBUIGNvbnRyb2wgY2VudGVyIHBlbmRpbmcnKTtcbiAgfVxufTtcbiJdfQ==