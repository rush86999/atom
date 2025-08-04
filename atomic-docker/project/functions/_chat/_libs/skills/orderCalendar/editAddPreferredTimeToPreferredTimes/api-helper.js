import requiredFields from './requiredFields';
import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, eventSearchBoundary, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, putDataInTrainEventIndexInOpenSearch, } from '@chat/_libs/api-helper';
import { updateEventWithIdModifiable, upsertPreferredTimeRangesForEvent, } from '../resolveConflictingEvents/api-helper';
import { DayOfWeekEnum } from './constants';
import { v4 as uuid } from 'uuid';
import { dayjs } from '@chat/_libs/datetime/date-utils';
export const finalStepEAPT2PTs = async (body, startDate, endDate, response) => {
    try {
        // convert to vector for search
        const searchVector = await convertEventTitleToOpenAIVector(body?.title);
        //  allEventWithEventOpenSearch
        // allEventOpenSearch
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
        const newPreferredTimeRanges = [];
        for (const timepreference of body?.timePreferences) {
            if (timepreference?.dayOfWeek?.length > 0) {
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
                    newPreferredTimeRanges.push(newPreferredTimeRange);
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
                newPreferredTimeRanges.push(newPreferredTimeRange);
            }
        }
        // add new time preferences
        if (newPreferredTimeRanges?.length > 0) {
            await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
        }
        else {
            console.log('something went wrong with no new preferred time ranges generated');
        }
        await updateEventWithIdModifiable(id, true);
        await putDataInTrainEventIndexInOpenSearch(id, searchVector, body?.userId);
        // success response
        response.query = 'completed';
        response.data = 'processed request';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step EAPT2PTs');
    }
};
export const processEAPT2PTsPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
    try {
        // get startDate and endDate if any
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
            timePreferences: dateJSONBody?.timePreferences || [],
        };
        // validate for missing fields
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'editAddPreferredTimeToPreferredTimes',
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
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepEAPT2PTs(body, startDate, endDate, response);
        return response2;
        // data validated start api calls
        // search for event
        // convert to vector for search
        // const searchVector = await convertEventTitleToOpenAIVector(body?.title)
        // //  allEventWithEventOpenSearch
        // // allEventOpenSearch
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
        // const newPreferredTimeRanges: PreferredTimeRangeType[] = []
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
        //             newPreferredTimeRanges.push(newPreferredTimeRange)
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
        //         newPreferredTimeRanges.push(newPreferredTimeRange)
        //     }
        // }
        // // add new time preferences
        // if (newPreferredTimeRanges?.length > 0) {
        //     await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges)
        // } else {
        //     console.log('something went wrong with no new preferred time ranges generated')
        // }
        // await updateEventWithIdModifiable(id, true)
        // // success response
        // response.query = 'completed'
        // return response
    }
    catch (e) {
        console.log(e, ' unable to process edit and preferred time to preferred times ');
    }
};
export const processEAPT2PTsMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
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
            skill: 'editAddPreferredTimeToPreferredTimes',
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
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepEAPT2PTs(prevBody, prevStartDate, prevEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to EAPT2PTs missing fields returned');
    }
};
export const EAPTToPreferredTimesControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let eaptRes = {
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
                eaptRes = await processEAPT2PTsPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                eaptRes = await processEAPT2PTsMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (eaptRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, eaptRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (eaptRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, eaptRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = eaptRes?.data;
            messageHistoryObject.prevData = eaptRes?.prevData;
            messageHistoryObject.prevDataExtra = eaptRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = eaptRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = eaptRes?.prevJsonBody;
        }
        else if (eaptRes?.query === 'event_not_found') {
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
        console.log(e, ' eapttopreferredtimes control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBS0EsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiwrQkFBK0IsRUFDL0IsbUJBQW1CLEVBQ25CLG1EQUFtRCxFQUNuRCxxREFBcUQsRUFDckQsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3Qiw2QkFBNkIsRUFDN0IsMENBQTBDLEVBQzFDLG9DQUFvQyxHQUNyQyxNQUFNLHdCQUF3QixDQUFDO0FBRWhDLE9BQU8sRUFDTCwyQkFBMkIsRUFDM0IsaUNBQWlDLEdBQ2xDLE1BQU0sd0NBQXdDLENBQUM7QUFDaEQsT0FBTyxFQUFFLGFBQWEsRUFBRSxNQUFNLGFBQWEsQ0FBQztBQUM1QyxPQUFPLEVBQUUsRUFBRSxJQUFJLElBQUksRUFBRSxNQUFNLE1BQU0sQ0FBQztBQUNsQyxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFReEQsTUFBTSxDQUFDLE1BQU0saUJBQWlCLEdBQUcsS0FBSyxFQUNwQyxJQUE4QyxFQUM5QyxTQUFpQixFQUNqQixPQUFlLEVBQ2YsUUFBYSxFQUNiLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCwrQkFBK0I7UUFDL0IsTUFBTSxZQUFZLEdBQUcsTUFBTSwrQkFBK0IsQ0FBQyxJQUFJLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFFeEUsK0JBQStCO1FBQy9CLHFCQUFxQjtRQUNyQixJQUFJLENBQUMsU0FBUyxFQUFFLENBQUM7WUFDZixTQUFTLEdBQUcsS0FBSyxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUNoRCxDQUFDO1FBRUQsSUFBSSxDQUFDLE9BQU8sRUFBRSxDQUFDO1lBQ2IsT0FBTyxHQUFHLEtBQUssRUFBRSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVB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QixDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztZQUNyRCxvQkFBb0IsQ0FBQyxLQUFLLEdBQUcsaUJBQWlCLENBQUM7WUFDL0Msb0JBQW9CLENBQUMsUUFBUSxHQUFHLElBQUksQ0FBQztRQUN2QyxDQUFDO1FBRUQsT0FBTyxvQkFBb0IsQ0FBQztJQUM5QixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDhDQUE4QyxDQUFDLENBQUM7SUFDakUsQ0FBQztBQUNILENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBEYXRlVGltZUpTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL0RhdGVUaW1lSlNPTkpTT05UeXBlJztcbmltcG9ydCBVc2VySW5wdXRUb0pTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1VzZXJJbnB1dFRvSlNPTlR5cGUnO1xuaW1wb3J0IFJlc3BvbnNlQWN0aW9uVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXNwb25zZUFjdGlvblR5cGUnO1xuaW1wb3J0IHsgRWRpdEFkZFByZWZlcnJlZFRpbWVUb1ByZWZlcnJlZFRpbWVzVHlwZSB9IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IFJlcXVpcmVkRmllbGRzVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXF1aXJlZEZpZWxkc1R5cGUnO1xuaW1wb3J0IHJlcXVpcmVkRmllbGRzIGZyb20gJy4vcmVxdWlyZWRGaWVsZHMnO1xuaW1wb3J0IHtcbiAgYWxsRXZlbnRXaXRoRGF0ZXNPcGVuU2VhcmNoLFxuICBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yLFxuICBldmVudFNlYXJjaEJvdW5kYXJ5LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnksXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzLFxuICBnZW5lcmF0ZURhdGVUaW1lLFxuICBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dCxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzRGF0ZVRpbWUsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dCxcbiAgcHV0RGF0YUluVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoLFxufSBmcm9tICdAY2hhdC9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1ByZWZlcnJlZFRpbWVSYW5nZVR5cGUnO1xuaW1wb3J0IHtcbiAgdXBkYXRlRXZlbnRXaXRoSWRNb2RpZmlhYmxlLFxuICB1cHNlcnRQcmVmZXJyZWRUaW1lUmFuZ2VzRm9yRXZlbnQsXG59IGZyb20gJy4uL3Jlc29sdmVDb25mbGljdGluZ0V2ZW50cy9hcGktaGVscGVyJztcbmltcG9ydCB7IERheU9mV2Vla0VudW0gfSBmcm9tICcuL2NvbnN0YW50cyc7XG5pbXBvcnQgeyB2NCBhcyB1dWlkIH0gZnJvbSAndXVpZCc7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHtcbiAgQXNzaXN0YW50TWVzc2FnZVR5cGUsXG4gIFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9NZXNzYWdpbmcvTWVzc2FnaW5nVHlwZXMnO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHsgU2VhcmNoQm91bmRhcnlUeXBlIH0gZnJvbSAnLi4vZGVsZXRlVGFzay90eXBlcyc7XG5cbmV4cG9ydCBjb25zdCBmaW5hbFN0ZXBFQVBUMlBUcyA9IGFzeW5jIChcbiAgYm9keTogRWRpdEFkZFByZWZlcnJlZFRpbWVUb1ByZWZlcnJlZFRpbWVzVHlwZSxcbiAgc3RhcnREYXRlOiBzdHJpbmcsXG4gIGVuZERhdGU6IHN0cmluZyxcbiAgcmVzcG9uc2U6IGFueVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gY29udmVydCB0byB2ZWN0b3IgZm9yIHNlYXJjaFxuICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuXG4gICAgLy8gIGFsbEV2ZW50V2l0aEV2ZW50T3BlblNlYXJjaFxuICAgIC8vIGFsbEV2ZW50T3BlblNlYXJjaFxuICAgIGlmICghc3RhcnREYXRlKSB7XG4gICAgICBzdGFydERhdGUgPSBkYXlqcygpLnN1YnRyYWN0KDIsICd3JykuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgaWYgKCFlbmREYXRlKSB7XG4gICAgICBlbmREYXRlID0gZGF5anMoKS5hZGQoNCwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBjb25zdCByZXMgPSBhd2FpdCBhbGxFdmVudFdpdGhEYXRlc09wZW5TZWFyY2goXG4gICAgICBib2R5Py51c2VySWQsXG4gICAgICBzZWFyY2hWZWN0b3IsXG4gICAgICBzdGFydERhdGUsXG4gICAgICBlbmREYXRlXG4gICAgKTtcblxuICAgIGNvbnN0IGlkID0gcmVzPy5oaXRzPy5oaXRzPy5bMF0/Ll9pZDtcblxuICAgIC8vIHZhbGlkYXRlIGZvdW5kIGV2ZW50XG4gICAgaWYgKCFpZCkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgdGltZXByZWZlcmVuY2Ugb2YgYm9keT8udGltZVByZWZlcmVuY2VzKSB7XG4gICAgICBpZiAodGltZXByZWZlcmVuY2U/LmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgICAgICBmb3IgKGNvbnN0IGRheU9mV2VlayBvZiB0aW1lcHJlZmVyZW5jZS5kYXlPZldlZWspIHtcbiAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgICAgZXZlbnRJZDogaWQsXG4gICAgICAgICAgICBkYXlPZldlZWs6IERheU9mV2Vla0VudW1bZGF5T2ZXZWVrXSxcbiAgICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgICAgZW5kVGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uZW5kVGltZSxcbiAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgdXNlcklkOiBib2R5Py51c2VySWQsXG4gICAgICAgICAgfTtcblxuICAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgICB9XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAgICAgICBldmVudElkOiBpZCxcbiAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgfTtcblxuICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKTtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyBhZGQgbmV3IHRpbWUgcHJlZmVyZW5jZXNcbiAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgYXdhaXQgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMpO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ3NvbWV0aGluZyB3ZW50IHdyb25nIHdpdGggbm8gbmV3IHByZWZlcnJlZCB0aW1lIHJhbmdlcyBnZW5lcmF0ZWQnXG4gICAgICApO1xuICAgIH1cblxuICAgIGF3YWl0IHVwZGF0ZUV2ZW50V2l0aElkTW9kaWZpYWJsZShpZCwgdHJ1ZSk7XG5cbiAgICBhd2FpdCBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2goaWQsIHNlYXJjaFZlY3RvciwgYm9keT8udXNlcklkKTtcblxuICAgIC8vIHN1Y2Nlc3MgcmVzcG9uc2VcbiAgICByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgIHJlc3BvbnNlLmRhdGEgPSAncHJvY2Vzc2VkIHJlcXVlc3QnO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZmluYWwgc3RlcCBFQVBUMlBUcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0VBUFQyUFRzUGVuZGluZyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICBkYXRlSlNPTkJvZHk6IERhdGVUaW1lSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmdcbik6IFByb21pc2U8UmVzcG9uc2VBY3Rpb25UeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IHN0YXJ0RGF0ZSBhbmQgZW5kRGF0ZSBpZiBhbnlcbiAgICBjb25zdCBzZWFyY2hCb3VuZGFyeSA9IGV2ZW50U2VhcmNoQm91bmRhcnkoXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGRhdGVKU09OQm9keSxcbiAgICAgIGN1cnJlbnRUaW1lXG4gICAgKTtcblxuICAgIGxldCBzdGFydERhdGUgPSBzZWFyY2hCb3VuZGFyeS5zdGFydERhdGU7XG4gICAgbGV0IGVuZERhdGUgPSBzZWFyY2hCb3VuZGFyeS5lbmREYXRlO1xuXG4gICAgY29uc3QgYm9keTogRWRpdEFkZFByZWZlcnJlZFRpbWVUb1ByZWZlcnJlZFRpbWVzVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgdGltZVByZWZlcmVuY2VzOiBkYXRlSlNPTkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fCBbXSxcbiAgICB9O1xuXG4gICAgLy8gdmFsaWRhdGUgZm9yIG1pc3NpbmcgZmllbGRzXG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAnZWRpdEFkZFByZWZlcnJlZFRpbWVUb1ByZWZlcnJlZFRpbWVzJyxcbiAgICB9O1xuXG4gICAgaWYgKCFib2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZCA9IHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKCFib2R5Py50aW1lUHJlZmVyZW5jZXM/LlswXSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZSA9IHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwRUFQVDJQVHMoXG4gICAgICBib2R5LFxuICAgICAgc3RhcnREYXRlLFxuICAgICAgZW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gICAgLy8gZGF0YSB2YWxpZGF0ZWQgc3RhcnQgYXBpIGNhbGxzXG5cbiAgICAvLyBzZWFyY2ggZm9yIGV2ZW50XG5cbiAgICAvLyBjb252ZXJ0IHRvIHZlY3RvciBmb3Igc2VhcmNoXG4gICAgLy8gY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSlcblxuICAgIC8vIC8vICBhbGxFdmVudFdpdGhFdmVudE9wZW5TZWFyY2hcbiAgICAvLyAvLyBhbGxFdmVudE9wZW5TZWFyY2hcbiAgICAvLyBpZiAoIXN0YXJ0RGF0ZSkge1xuICAgIC8vICAgICBzdGFydERhdGUgPSBkYXlqcygpLnN1YnRyYWN0KDIsICd3JykuZm9ybWF0KClcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoIWVuZERhdGUpIHtcbiAgICAvLyAgICAgZW5kRGF0ZSA9IGRheWpzKCkuYWRkKDQsICd3JykuZm9ybWF0KClcbiAgICAvLyB9XG5cbiAgICAvLyBjb25zdCByZXMgPSBhd2FpdCBhbGxFdmVudFdpdGhEYXRlc09wZW5TZWFyY2godXNlcklkLCBzZWFyY2hWZWN0b3IsIHN0YXJ0RGF0ZSwgZW5kRGF0ZSlcblxuICAgIC8vIGNvbnN0IGlkID0gcmVzPy5oaXRzPy5oaXRzPy5bMF0/Ll9pZFxuXG4gICAgLy8gLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICAvLyBpZiAoIWlkKSB7XG4gICAgLy8gICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCdcbiAgICAvLyAgICAgcmV0dXJuIHJlc3BvbnNlXG4gICAgLy8gfVxuXG4gICAgLy8gY29uc3QgbmV3UHJlZmVycmVkVGltZVJhbmdlczogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW11cblxuICAgIC8vIGZvciAoY29uc3QgdGltZXByZWZlcmVuY2Ugb2YgYm9keT8udGltZVByZWZlcmVuY2VzKSB7XG5cbiAgICAvLyAgICAgaWYgKHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaz8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICAgICAgZm9yIChjb25zdCBkYXlPZldlZWsgb2YgdGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrKSB7XG5cbiAgICAvLyAgICAgICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgLy8gICAgICAgICAgICAgICAgIGV2ZW50SWQ6IGlkLFxuICAgIC8vICAgICAgICAgICAgICAgICBkYXlPZldlZWs6IERheU9mV2Vla0VudW1bZGF5T2ZXZWVrXSxcbiAgICAvLyAgICAgICAgICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgLy8gICAgICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgLy8gICAgICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAvLyAgICAgICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgICAgICBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzLnB1c2gobmV3UHJlZmVycmVkVGltZVJhbmdlKVxuICAgIC8vICAgICAgICAgfVxuICAgIC8vICAgICB9IGVsc2Uge1xuXG4gICAgLy8gICAgICAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2U6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgLy8gICAgICAgICAgICAgaWQ6IHV1aWQoKSxcbiAgICAvLyAgICAgICAgICAgICBldmVudElkOiBpZCxcbiAgICAvLyAgICAgICAgICAgICBzdGFydFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LnN0YXJ0VGltZSxcbiAgICAvLyAgICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgIC8vICAgICAgICAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAvLyAgICAgICAgICAgICB1c2VySWQsXG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpXG4gICAgLy8gICAgIH1cblxuICAgIC8vIH1cblxuICAgIC8vIC8vIGFkZCBuZXcgdGltZSBwcmVmZXJlbmNlc1xuICAgIC8vIGlmIChuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzPy5sZW5ndGggPiAwKSB7XG5cbiAgICAvLyAgICAgYXdhaXQgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMpXG4gICAgLy8gfSBlbHNlIHtcbiAgICAvLyAgICAgY29uc29sZS5sb2coJ3NvbWV0aGluZyB3ZW50IHdyb25nIHdpdGggbm8gbmV3IHByZWZlcnJlZCB0aW1lIHJhbmdlcyBnZW5lcmF0ZWQnKVxuICAgIC8vIH1cblxuICAgIC8vIGF3YWl0IHVwZGF0ZUV2ZW50V2l0aElkTW9kaWZpYWJsZShpZCwgdHJ1ZSlcblxuICAgIC8vIC8vIHN1Y2Nlc3MgcmVzcG9uc2VcbiAgICAvLyByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnXG5cbiAgICAvLyByZXR1cm4gcmVzcG9uc2VcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3MgZWRpdCBhbmQgcHJlZmVycmVkIHRpbWUgdG8gcHJlZmVycmVkIHRpbWVzICdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0VBUFQyUFRzTWlzc2luZ0ZpZWxkc1JldHVybmVkID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBzZWFyY2hCb3VuZGFyeSA9IGV2ZW50U2VhcmNoQm91bmRhcnkoXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGRhdGVKU09OQm9keSxcbiAgICAgIGN1cnJlbnRUaW1lXG4gICAgKTtcblxuICAgIGxldCBzdGFydERhdGUgPSBzZWFyY2hCb3VuZGFyeS5zdGFydERhdGU7XG4gICAgbGV0IGVuZERhdGUgPSBzZWFyY2hCb3VuZGFyeS5lbmREYXRlO1xuXG4gICAgY29uc3QgbmV3Qm9keTogRWRpdEFkZFByZWZlcnJlZFRpbWVUb1ByZWZlcnJlZFRpbWVzVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgICAgdGltZVByZWZlcmVuY2VzOlxuICAgICAgICBkYXRlSlNPTkJvZHk/LnRpbWVQcmVmZXJlbmNlcyB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8udGltZVByZWZlcmVuY2VzIHx8XG4gICAgICAgIFtdLFxuICAgIH07XG5cbiAgICBjb25zdCBwcmV2Qm9keTogRWRpdEFkZFByZWZlcnJlZFRpbWVUb1ByZWZlcnJlZFRpbWVzVHlwZSA9IHtcbiAgICAgIC4uLm1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YSxcbiAgICB9O1xuXG4gICAgaWYgKCFwcmV2Qm9keT8udXNlcklkKSB7XG4gICAgICBwcmV2Qm9keS51c2VySWQgPSBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnRpbWVQcmVmZXJlbmNlcyA9IG5ld0JvZHk/LnRpbWVQcmVmZXJlbmNlcztcbiAgICB9XG5cbiAgICBjb25zdCBwcmV2U2VhcmNoQm91bmRhcnk6IFNlYXJjaEJvdW5kYXJ5VHlwZSA9XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGFFeHRyYT8uc2VhcmNoQm91bmRhcnk7XG5cbiAgICBsZXQgcHJldlN0YXJ0RGF0ZSA9IHByZXZTZWFyY2hCb3VuZGFyeT8uc3RhcnREYXRlO1xuXG4gICAgbGV0IHByZXZFbmREYXRlID0gcHJldlNlYXJjaEJvdW5kYXJ5Py5lbmREYXRlO1xuXG4gICAgaWYgKCFwcmV2U3RhcnREYXRlKSB7XG4gICAgICBwcmV2U3RhcnREYXRlID0gc3RhcnREYXRlO1xuICAgIH1cblxuICAgIGlmICghcHJldkVuZERhdGUpIHtcbiAgICAgIHByZXZFbmREYXRlID0gZW5kRGF0ZTtcbiAgICB9XG5cbiAgICAvLyB2YWxpZGF0ZSBmb3IgbWlzc2luZyBmaWVsZHNcblxuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdlZGl0QWRkUHJlZmVycmVkVGltZVRvUHJlZmVycmVkVGltZXMnLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZCA9IHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgc2VhcmNoQm91bmRhcnk6IHtcbiAgICAgICAgICBzdGFydERhdGU6IHByZXZTdGFydERhdGUsXG4gICAgICAgICAgZW5kRGF0ZTogcHJldkVuZERhdGUsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpbWVQcmVmZXJlbmNlcz8uWzBdKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLmRhdGVUaW1lID0gcmVxdWlyZWRGaWVsZHMuZGF0ZVRpbWU7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeToge1xuICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwRUFQVDJQVHMoXG4gICAgICBwcmV2Qm9keSxcbiAgICAgIHByZXZTdGFydERhdGUsXG4gICAgICBwcmV2RW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBFQVBUMlBUcyBtaXNzaW5nIGZpZWxkcyByZXR1cm5lZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgRUFQVFRvUHJlZmVycmVkVGltZXNDb250cm9sQ2VudGVyID0gYXN5bmMgKFxuICBvcGVuYWk6IE9wZW5BSSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbiAgdXNlckN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIHF1ZXJ5OiAnbWlzc2luZ19maWVsZHMnIHwgJ2NvbXBsZXRlZCcgfCAnZXZlbnRfbm90X2ZvdW5kJyB8ICdwZW5kaW5nJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGg7XG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG5cbiAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgIHVzZXJNZXNzYWdlID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCB1c2VySW5wdXQgPSB1c2VyTWVzc2FnZTtcblxuICAgIGxldCBlYXB0UmVzOiBSZXNwb25zZUFjdGlvblR5cGUgPSB7XG4gICAgICBxdWVyeTogJ2NvbXBsZXRlZCcsXG4gICAgICBkYXRhOiAnJyxcbiAgICAgIHNraWxsOiAnJyxcbiAgICAgIHByZXZEYXRhOiB7fSxcbiAgICAgIHByZXZEYXRhRXh0cmE6IHt9LFxuICAgIH07XG5cbiAgICBzd2l0Y2ggKHF1ZXJ5KSB7XG4gICAgICBjYXNlICdwZW5kaW5nJzpcbiAgICAgICAgY29uc3QganNvbkJvZHkgPSBhd2FpdCBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVUaW1lID0gYXdhaXQgZ2VuZXJhdGVEYXRlVGltZShcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICk7XG4gICAgICAgIGVhcHRSZXMgPSBhd2FpdCBwcm9jZXNzRUFQVDJQVHNQZW5kaW5nKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uQm9keSxcbiAgICAgICAgICBkYXRlVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdtaXNzaW5nX2ZpZWxkcyc6XG4gICAgICAgIGxldCBwcmlvclVzZXJJbnB1dCA9ICcnO1xuICAgICAgICBsZXQgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSAnJztcblxuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAnYXNzaXN0YW50Jykge1xuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgIGlmIChtZXNzYWdlLmNvbnRlbnQgIT09IHVzZXJJbnB1dCkge1xuICAgICAgICAgICAgICBwcmlvclVzZXJJbnB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmlvclVzZXJJbnB1dCB8fCAhcHJpb3JBc3Npc3RhbnRPdXRwdXQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvclVzZXJJbnB1dCwgJyBwcmlvclVzZXJJbnB1dCcpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yQXNzaXN0YW50T3V0cHV0LCAnIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBwcmlvclVzZXJpbnB1dCBvciBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGpzb25NaXNzaW5nRmllbGRzQm9keSA9XG4gICAgICAgICAgYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVNaXNzaW5nRmllbGRzVGltZSA9IGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcblxuICAgICAgICBlYXB0UmVzID0gYXdhaXQgcHJvY2Vzc0VBUFQyUFRzTWlzc2luZ0ZpZWxkc1JldHVybmVkKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uTWlzc2luZ0ZpZWxkc0JvZHksXG4gICAgICAgICAgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICB9XG5cbiAgICBpZiAoZWFwdFJlcz8ucXVlcnkgPT09ICdjb21wbGV0ZWQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5KFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBlYXB0UmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoZWFwdFJlcz8ucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyhcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgZWFwdFJlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gZWFwdFJlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IGVhcHRSZXM/LnByZXZEYXRhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGFFeHRyYSA9IGVhcHRSZXM/LnByZXZEYXRhRXh0cmE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0ZUpzb25Cb2R5ID0gZWFwdFJlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZKc29uQm9keSA9IGVhcHRSZXM/LnByZXZKc29uQm9keTtcbiAgICB9IGVsc2UgaWYgKGVhcHRSZXM/LnF1ZXJ5ID09PSAnZXZlbnRfbm90X2ZvdW5kJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZTogQXNzaXN0YW50TWVzc2FnZVR5cGUgPSB7XG4gICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgICBjb250ZW50OiBcIk9vcHMuLi4gSSBjb3VsZG4ndCBmaW5kIHRoZSBldmVudC4gU29ycnkgOihcIixcbiAgICAgIH07XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH1cblxuICAgIHJldHVybiBtZXNzYWdlSGlzdG9yeU9iamVjdDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgZWFwdHRvcHJlZmVycmVkdGltZXMgY29udHJvbCBjZW50ZXIgcGVuZGluZycpO1xuICB9XG59O1xuIl19