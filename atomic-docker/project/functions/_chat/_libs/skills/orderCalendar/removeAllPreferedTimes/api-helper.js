import requiredFields from './requiredFields';
import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, deleteDocInTrainEventIndexInOpenSearch, eventSearchBoundary, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, } from '@chat/_libs/api-helper';
import deletePreferredTimeRangesByEventId from '@chat/_libs/gql/deletePreferredTimeRangesByEventId';
import { hasuraAdminSecret, hasuraGraphUrl } from '@chat/_libs/constants';
import got from 'got';
import { dayjs } from '@chat/_libs/datetime/date-utils';
export const deletePreferredTimeRangesGivenEventId = async (eventId) => {
    try {
        const operationName = 'DeletePreferredTimeRangesGivenEventId';
        const query = deletePreferredTimeRangesByEventId;
        const variables = {
            eventId,
        };
        const res = await got
            .post(hasuraGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin',
            },
        })
            .json();
        console.log(res?.data?.delete_PreferredTimeRange?.affected_rows, ' res inside deletePreferredTimeRangesGivenEventId');
        return res?.data?.delete_PreferredTimeRange?.returning;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const finalStepRemoveAllPreferredTimes = async (body, startDate, endDate, response) => {
    try {
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
        // delete all preferred time ranges
        await deletePreferredTimeRangesGivenEventId(id);
        // delete data in train index
        await deleteDocInTrainEventIndexInOpenSearch(id);
        // success response
        response.query = 'completed';
        response.data = 'successfully removed all preferred times';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step RemoveAllPreferredTimes');
    }
};
export const processRemoveAllPreferredTimesPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
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
        };
        // validate for missing fields
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'removeAllPreferedTimes',
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
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepRemoveAllPreferredTimes(body, startDate, endDate, response);
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
        // // delete all preferred time ranges
        // await deletePreferredTimeRangesGivenEventId(id)
        // // delete data in train index
        // await deleteDocInTrainEventIndexInOpenSearch(id)
        // // success response
        // response.query = 'completed'
        // return response
    }
    catch (e) {
        console.log(e, ' unable to process edit and preferred time to preferred times ');
    }
};
export const processRemoveAllPreferredTimesMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
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
        };
        const prevBody = {
            ...messageHistoryObject?.prevData,
        };
        if (!prevBody?.userId) {
            prevBody.userId = userId || newBody?.userId;
        }
        if (!prevBody?.timezone) {
            prevBody.timezone = timezone || newBody?.timezone;
        }
        if (!prevBody?.title) {
            prevBody.title = newBody?.title;
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
            skill: 'removeAllPreferedTimes',
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
        if (response.query === 'missing_fields') {
            return response;
        }
        const response2 = await finalStepRemoveAllPreferredTimes(prevBody, prevStartDate, prevEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process removal all preferred times missing fields returned');
    }
};
export const RAPControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let RAPTRes = {
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
                RAPTRes = await processRemoveAllPreferredTimesPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                RAPTRes = await processRemoveAllPreferredTimesMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (RAPTRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, RAPTRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (RAPTRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, RAPTRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = RAPTRes?.data;
            messageHistoryObject.prevData = RAPTRes?.prevData;
            messageHistoryObject.prevDataExtra = RAPTRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = RAPTRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = RAPTRes?.prevJsonBody;
        }
        else if (RAPTRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to remove all preferred times control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBS0EsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiwrQkFBK0IsRUFDL0Isc0NBQXNDLEVBQ3RDLG1CQUFtQixFQUNuQixtREFBbUQsRUFDbkQscURBQXFELEVBQ3JELGdCQUFnQixFQUNoQiw2QkFBNkIsRUFDN0IsNkJBQTZCLEVBQzdCLDBDQUEwQyxHQUMzQyxNQUFNLHdCQUF3QixDQUFDO0FBRWhDLE9BQU8sa0NBQWtDLE1BQU0sb0RBQW9ELENBQUM7QUFDcEcsT0FBTyxFQUFFLGlCQUFpQixFQUFFLGNBQWMsRUFBRSxNQUFNLHVCQUF1QixDQUFDO0FBQzFFLE9BQU8sR0FBRyxNQUFNLEtBQUssQ0FBQztBQUN0QixPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFReEQsTUFBTSxDQUFDLE1BQU0scUNBQXFDLEdBQUcsS0FBSyxFQUN4RCxPQUFlLEVBQ2YsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sYUFBYSxHQUFHLHVDQUF1QyxDQUFDO1FBQzlELE1BQU0sS0FBSyxHQUFHLGtDQUFrQyxDQUFDO1FBQ2pELE1BQU0sU0FBUyxHQUFHO1lBQ2hCLE9BQU87U0FDUixDQUFDO1FBRUYsTUFBTSxHQUFHLEdBT0wsTUFBTSxHQUFHO2FBQ1YsSUFBSSxDQUFDLGNBQWMsRUFBRTtZQUNwQixJQUFJLEVBQUU7Z0JBQ0osYUFBYTtnQkFDYixLQUFLO2dCQUNMLFNBQVM7YUFDVjtZQUNELE9BQU8sRUFBRTtnQkFDUCx1QkFBdUIsRUFBRSxpQkFBaUI7Z0JBQzFDLGNBQWMsRUFBRSxrQkFBa0I7Z0JBQ2xDLGVBQWUsRUFBRSxPQUFPO2FBQ3pCO1NBQ0YsQ0FBQzthQUNELElBQUksRUFBRSxDQUFDO1FBRVYsT0FBTyxDQUFDLEdBQUcsQ0FDVCxH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QUFDO1FBRUQsT0FBTyxvQkFBb0IsQ0FBQztJQUM5QixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQ1QsQ0FBQyxFQUNELDhEQUE4RCxDQUMvRCxDQUFDO0lBQ0osQ0FBQztBQUNILENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBEYXRlVGltZUpTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL0RhdGVUaW1lSlNPTkpTT05UeXBlJztcbmltcG9ydCBVc2VySW5wdXRUb0pTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1VzZXJJbnB1dFRvSlNPTlR5cGUnO1xuaW1wb3J0IFJlc3BvbnNlQWN0aW9uVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXNwb25zZUFjdGlvblR5cGUnO1xuaW1wb3J0IHsgUmVtb3ZlQWxsUHJlZmVycmVkVGltZXMgfSBmcm9tICcuL3R5cGVzJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCByZXF1aXJlZEZpZWxkcyBmcm9tICcuL3JlcXVpcmVkRmllbGRzJztcbmltcG9ydCB7XG4gIGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaCxcbiAgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcixcbiAgZGVsZXRlRG9jSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsXG4gIGV2ZW50U2VhcmNoQm91bmRhcnksXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMsXG4gIGdlbmVyYXRlRGF0ZVRpbWUsXG4gIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZSxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0LFxufSBmcm9tICdAY2hhdC9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1ByZWZlcnJlZFRpbWVSYW5nZVR5cGUnO1xuaW1wb3J0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQgZnJvbSAnQGNoYXQvX2xpYnMvZ3FsL2RlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQnO1xuaW1wb3J0IHsgaGFzdXJhQWRtaW5TZWNyZXQsIGhhc3VyYUdyYXBoVXJsIH0gZnJvbSAnQGNoYXQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCBnb3QgZnJvbSAnZ290JztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvZGF0ZS11dGlscyc7XG5pbXBvcnQge1xuICBBc3Npc3RhbnRNZXNzYWdlVHlwZSxcbiAgU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcyc7XG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBTZWFyY2hCb3VuZGFyeVR5cGUgfSBmcm9tICcuLi9kZWxldGVUYXNrL3R5cGVzJztcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQgPSBhc3luYyAoXG4gIGV2ZW50SWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdEZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkJztcbiAgICBjb25zdCBxdWVyeSA9IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQ7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgZXZlbnRJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7XG4gICAgICAgIGRlbGV0ZV9QcmVmZXJyZWRUaW1lUmFuZ2U6IHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzOiBudW1iZXI7XG4gICAgICAgICAgcmV0dXJuaW5nOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW107XG4gICAgICAgIH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXM/LmRhdGE/LmRlbGV0ZV9QcmVmZXJyZWRUaW1lUmFuZ2U/LmFmZmVjdGVkX3Jvd3MsXG4gICAgICAnIHJlcyBpbnNpZGUgZGVsZXRlUHJlZmVycmVkVGltZVJhbmdlc0dpdmVuRXZlbnRJZCdcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uZGVsZXRlX1ByZWZlcnJlZFRpbWVSYW5nZT8ucmV0dXJuaW5nO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IEVtYWlsX0tub3dsZWRnZWJhc2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGZpbmFsU3RlcFJlbW92ZUFsbFByZWZlcnJlZFRpbWVzID0gYXN5bmMgKFxuICBib2R5OiBSZW1vdmVBbGxQcmVmZXJyZWRUaW1lcyxcbiAgc3RhcnREYXRlOiBzdHJpbmcsXG4gIGVuZERhdGU6IHN0cmluZyxcbiAgcmVzcG9uc2U6IGFueVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSk7XG5cbiAgICAvLyAgYWxsRXZlbnRXaXRoRXZlbnRPcGVuU2VhcmNoXG4gICAgaWYgKCFzdGFydERhdGUpIHtcbiAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIWVuZERhdGUpIHtcbiAgICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaChcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGVcbiAgICApO1xuXG4gICAgY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkO1xuXG4gICAgLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICBpZiAoIWlkKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIC8vIGRlbGV0ZSBhbGwgcHJlZmVycmVkIHRpbWUgcmFuZ2VzXG5cbiAgICBhd2FpdCBkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkKGlkKTtcblxuICAgIC8vIGRlbGV0ZSBkYXRhIGluIHRyYWluIGluZGV4XG4gICAgYXdhaXQgZGVsZXRlRG9jSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2goaWQpO1xuXG4gICAgLy8gc3VjY2VzcyByZXNwb25zZVxuICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgcmVzcG9uc2UuZGF0YSA9ICdzdWNjZXNzZnVsbHkgcmVtb3ZlZCBhbGwgcHJlZmVycmVkIHRpbWVzJztcbiAgICByZXR1cm4gcmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBmaW5hbCBzdGVwIFJlbW92ZUFsbFByZWZlcnJlZFRpbWVzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzUmVtb3ZlQWxsUHJlZmVycmVkVGltZXNQZW5kaW5nID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZ1xuKTogUHJvbWlzZTxSZXNwb25zZUFjdGlvblR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBzZWFyY2hCb3VuZGFyeSA9IGV2ZW50U2VhcmNoQm91bmRhcnkoXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGRhdGVKU09OQm9keSxcbiAgICAgIGN1cnJlbnRUaW1lXG4gICAgKTtcblxuICAgIGxldCBzdGFydERhdGUgPSBzZWFyY2hCb3VuZGFyeS5zdGFydERhdGU7XG4gICAgbGV0IGVuZERhdGUgPSBzZWFyY2hCb3VuZGFyeS5lbmREYXRlO1xuXG4gICAgY29uc3QgYm9keTogUmVtb3ZlQWxsUHJlZmVycmVkVGltZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICB9O1xuXG4gICAgLy8gdmFsaWRhdGUgZm9yIG1pc3NpbmcgZmllbGRzXG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAncmVtb3ZlQWxsUHJlZmVyZWRUaW1lcycsXG4gICAgfTtcblxuICAgIGlmICghYm9keT8udGl0bGUpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQgPSByZXF1aXJlZEZpZWxkcy5yZXF1aXJlZDtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBib2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgc2VhcmNoQm91bmRhcnksXG4gICAgICB9O1xuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcFJlbW92ZUFsbFByZWZlcnJlZFRpbWVzKFxuICAgICAgYm9keSxcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICAgIC8vIGRhdGEgdmFsaWRhdGVkIHN0YXJ0IGFwaSBjYWxsc1xuXG4gICAgLy8gc2VhcmNoIGZvciBldmVudFxuXG4gICAgLy8gY29udmVydCB0byB2ZWN0b3IgZm9yIHNlYXJjaFxuICAgIC8vIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpXG5cbiAgICAvLyAvLyAgYWxsRXZlbnRXaXRoRXZlbnRPcGVuU2VhcmNoXG4gICAgLy8gaWYgKCFzdGFydERhdGUpIHtcbiAgICAvLyAgICAgc3RhcnREYXRlID0gZGF5anMoKS5zdWJ0cmFjdCgyLCAndycpLmZvcm1hdCgpXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKCFlbmREYXRlKSB7XG4gICAgLy8gICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpXG4gICAgLy8gfVxuXG4gICAgLy8gY29uc3QgcmVzID0gYXdhaXQgYWxsRXZlbnRXaXRoRGF0ZXNPcGVuU2VhcmNoKHVzZXJJZCwgc2VhcmNoVmVjdG9yLCBzdGFydERhdGUsIGVuZERhdGUpXG5cbiAgICAvLyBjb25zdCBpZCA9IHJlcz8uaGl0cz8uaGl0cz8uWzBdPy5faWRcblxuICAgIC8vIC8vIHZhbGlkYXRlIGZvdW5kIGV2ZW50XG4gICAgLy8gaWYgKCFpZCkge1xuICAgIC8vICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnXG4gICAgLy8gICAgIHJldHVybiByZXNwb25zZVxuICAgIC8vIH1cblxuICAgIC8vIC8vIGRlbGV0ZSBhbGwgcHJlZmVycmVkIHRpbWUgcmFuZ2VzXG5cbiAgICAvLyBhd2FpdCBkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkKGlkKVxuXG4gICAgLy8gLy8gZGVsZXRlIGRhdGEgaW4gdHJhaW4gaW5kZXhcbiAgICAvLyBhd2FpdCBkZWxldGVEb2NJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaChpZClcblxuICAgIC8vIC8vIHN1Y2Nlc3MgcmVzcG9uc2VcbiAgICAvLyByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnXG5cbiAgICAvLyByZXR1cm4gcmVzcG9uc2VcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZSxcbiAgICAgICcgdW5hYmxlIHRvIHByb2Nlc3MgZWRpdCBhbmQgcHJlZmVycmVkIHRpbWUgdG8gcHJlZmVycmVkIHRpbWVzICdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc1JlbW92ZUFsbFByZWZlcnJlZFRpbWVzTWlzc2luZ0ZpZWxkc1JldHVybmVkID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBzZWFyY2hCb3VuZGFyeSA9IGV2ZW50U2VhcmNoQm91bmRhcnkoXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGRhdGVKU09OQm9keSxcbiAgICAgIGN1cnJlbnRUaW1lXG4gICAgKTtcblxuICAgIGxldCBzdGFydERhdGUgPSBzZWFyY2hCb3VuZGFyeS5zdGFydERhdGU7XG4gICAgbGV0IGVuZERhdGUgPSBzZWFyY2hCb3VuZGFyeS5lbmREYXRlO1xuXG4gICAgY29uc3QgbmV3Qm9keTogUmVtb3ZlQWxsUHJlZmVycmVkVGltZXMgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2sgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICB9O1xuXG4gICAgY29uc3QgcHJldkJvZHk6IFJlbW92ZUFsbFByZWZlcnJlZFRpbWVzID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgY29uc3QgcHJldlNlYXJjaEJvdW5kYXJ5OiBTZWFyY2hCb3VuZGFyeVR5cGUgPVxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhRXh0cmE/LnNlYXJjaEJvdW5kYXJ5O1xuXG4gICAgbGV0IHByZXZTdGFydERhdGUgPSBwcmV2U2VhcmNoQm91bmRhcnk/LnN0YXJ0RGF0ZTtcblxuICAgIGxldCBwcmV2RW5kRGF0ZSA9IHByZXZTZWFyY2hCb3VuZGFyeT8uZW5kRGF0ZTtcblxuICAgIGlmICghcHJldlN0YXJ0RGF0ZSkge1xuICAgICAgcHJldlN0YXJ0RGF0ZSA9IHN0YXJ0RGF0ZTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZFbmREYXRlKSB7XG4gICAgICBwcmV2RW5kRGF0ZSA9IGVuZERhdGU7XG4gICAgfVxuXG4gICAgLy8gdmFsaWRhdGUgZm9yIG1pc3NpbmcgZmllbGRzXG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAncmVtb3ZlQWxsUHJlZmVyZWRUaW1lcycsXG4gICAgfTtcblxuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkID0gcmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeToge1xuICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwUmVtb3ZlQWxsUHJlZmVycmVkVGltZXMoXG4gICAgICBwcmV2Qm9keSxcbiAgICAgIHByZXZTdGFydERhdGUsXG4gICAgICBwcmV2RW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byBwcm9jZXNzIHJlbW92YWwgYWxsIHByZWZlcnJlZCB0aW1lcyBtaXNzaW5nIGZpZWxkcyByZXR1cm5lZCdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgUkFQQ29udHJvbENlbnRlciA9IGFzeW5jIChcbiAgb3BlbmFpOiBPcGVuQUksXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG4gIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuICBxdWVyeTogJ21pc3NpbmdfZmllbGRzJyB8ICdjb21wbGV0ZWQnIHwgJ2V2ZW50X25vdF9mb3VuZCcgfCAncGVuZGluZydcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG1lc3NhZ2VMZW5ndGggPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcz8ubGVuZ3RoO1xuICAgIGxldCB1c2VyTWVzc2FnZSA9ICcnO1xuICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgdXNlck1lc3NhZ2UgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHVzZXJJbnB1dCA9IHVzZXJNZXNzYWdlO1xuXG4gICAgbGV0IFJBUFRSZXM6IFJlc3BvbnNlQWN0aW9uVHlwZSA9IHtcbiAgICAgIHF1ZXJ5OiAnY29tcGxldGVkJyxcbiAgICAgIGRhdGE6ICcnLFxuICAgICAgc2tpbGw6ICcnLFxuICAgICAgcHJldkRhdGE6IHt9LFxuICAgICAgcHJldkRhdGFFeHRyYToge30sXG4gICAgfTtcblxuICAgIHN3aXRjaCAocXVlcnkpIHtcbiAgICAgIGNhc2UgJ3BlbmRpbmcnOlxuICAgICAgICBjb25zdCBqc29uQm9keSA9IGF3YWl0IGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZVRpbWUgPSBhd2FpdCBnZW5lcmF0ZURhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgUkFQVFJlcyA9IGF3YWl0IHByb2Nlc3NSZW1vdmVBbGxQcmVmZXJyZWRUaW1lc1BlbmRpbmcoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25Cb2R5LFxuICAgICAgICAgIGRhdGVUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ21pc3NpbmdfZmllbGRzJzpcbiAgICAgICAgbGV0IHByaW9yVXNlcklucHV0ID0gJyc7XG4gICAgICAgIGxldCBwcmlvckFzc2lzdGFudE91dHB1dCA9ICcnO1xuXG4gICAgICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICdhc3Npc3RhbnQnKSB7XG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICAgICAgaWYgKG1lc3NhZ2UuY29udGVudCAhPT0gdXNlcklucHV0KSB7XG4gICAgICAgICAgICAgIHByaW9yVXNlcklucHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoIXByaW9yVXNlcklucHV0IHx8ICFwcmlvckFzc2lzdGFudE91dHB1dCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yVXNlcklucHV0LCAnIHByaW9yVXNlcklucHV0Jyk7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JBc3Npc3RhbnRPdXRwdXQsICcgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHByaW9yVXNlcmlucHV0IG9yIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgIH1cbiAgICAgICAgY29uc3QganNvbk1pc3NpbmdGaWVsZHNCb2R5ID1cbiAgICAgICAgICBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lID0gYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuXG4gICAgICAgIFJBUFRSZXMgPSBhd2FpdCBwcm9jZXNzUmVtb3ZlQWxsUHJlZmVycmVkVGltZXNNaXNzaW5nRmllbGRzUmV0dXJuZWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25NaXNzaW5nRmllbGRzQm9keSxcbiAgICAgICAgICBkYXRlTWlzc2luZ0ZpZWxkc1RpbWUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgIH1cblxuICAgIGlmIChSQVBUUmVzPy5xdWVyeSA9PT0gJ2NvbXBsZXRlZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnkoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIFJBUFRSZXMuZGF0YSBhcyBzdHJpbmcsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfSBlbHNlIGlmIChSQVBUUmVzPy5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzKFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBSQVBUUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBSQVBUUmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhID0gUkFQVFJlcz8ucHJldkRhdGE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YUV4dHJhID0gUkFQVFJlcz8ucHJldkRhdGFFeHRyYTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPSBSQVBUUmVzPy5wcmV2RGF0ZUpzb25Cb2R5O1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkpzb25Cb2R5ID0gUkFQVFJlcz8ucHJldkpzb25Cb2R5O1xuICAgIH0gZWxzZSBpZiAoUkFQVFJlcz8ucXVlcnkgPT09ICdldmVudF9ub3RfZm91bmQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6IFwiT29wcy4uLiBJIGNvdWxkbid0IGZpbmQgdGhlIGV2ZW50LiBTb3JyeSA6KFwiLFxuICAgICAgfTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfVxuXG4gICAgcmV0dXJuIG1lc3NhZ2VIaXN0b3J5T2JqZWN0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLFxuICAgICAgJyB1bmFibGUgdG8gcmVtb3ZlIGFsbCBwcmVmZXJyZWQgdGltZXMgY29udHJvbCBjZW50ZXIgcGVuZGluZydcbiAgICApO1xuICB9XG59O1xuIl19