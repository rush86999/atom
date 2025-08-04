import requiredFields from './requiredFields';
import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, deleteDocInTrainEventIndexInOpenSearch, eventSearchBoundary, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, } from '@chat/_libs/api-helper';
import { untrainEventWithPriorityAndModifiable } from '../resolveConflictingEvents/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
export const finalStepDeletePriority = async (body, startDate, endDate, response) => {
    try {
        // convert to vector for search
        const searchVector = await convertEventTitleToOpenAIVector(body?.title);
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
        await untrainEventWithPriorityAndModifiable(id, false, 1);
        // delete data in train index
        await deleteDocInTrainEventIndexInOpenSearch(id);
        // success response
        response.query = 'completed';
        response.data = 'successfully deleted priority';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to delete priority');
    }
};
export const processDeletePriorityPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
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
            skill: 'deletePriority',
        };
        if (!body?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
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
        const response2 = await finalStepDeletePriority(body, startDate, endDate, response);
        return response2;
        // convert to vector for search
        // const searchVector = await convertEventTitleToOpenAIVector(body?.title)
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
        // await untrainEventWithPriorityAndModifiable(id, false, 1)
        // // delete data in train index
        // await deleteDocInTrainEventIndexInOpenSearch(id)
        // // success response
        // response.query = 'completed'
        // return response
    }
    catch (e) {
        console.log(e, ' unable to process add priority');
    }
};
export const processDeletePriorityMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
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
            skill: 'deletePriority',
        };
        if (!prevBody?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
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
        const response2 = await finalStepDeletePriority(prevBody, prevStartDate, prevEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process delete priority time missing fields returned');
    }
};
export const deletePriorityControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let deletePriorityRes = {
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
                deletePriorityRes = await processDeletePriorityPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                deletePriorityRes = await processDeletePriorityMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (deletePriorityRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, deletePriorityRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (deletePriorityRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, deletePriorityRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required =
                deletePriorityRes?.data;
            messageHistoryObject.prevData = deletePriorityRes.prevData;
            messageHistoryObject.prevDataExtra = deletePriorityRes.prevDataExtra;
            messageHistoryObject.prevDateJsonBody =
                deletePriorityRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = deletePriorityRes?.prevJsonBody;
        }
        else if (deletePriorityRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to delete priority control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBS0EsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiwrQkFBK0IsRUFDL0Isc0NBQXNDLEVBQ3RDLG1CQUFtQixFQUNuQixtREFBbUQsRUFDbkQscURBQXFELEVBQ3JELGdCQUFnQixFQUNoQiw2QkFBNkIsRUFDN0IsNkJBQTZCLEVBQzdCLDBDQUEwQyxHQUMzQyxNQUFNLHdCQUF3QixDQUFDO0FBQ2hDLE9BQU8sRUFBRSxxQ0FBcUMsRUFBRSxNQUFNLHdDQUF3QyxDQUFDO0FBQy9GLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQVF4RCxNQUFNLENBQUMsTUFBTSx1QkFBdUIsR0FBRyxLQUFLLEVBQzFDLElBQXdCLEVBQ3hCLFNBQWlCLEVBQ2pCLE9BQWUsRUFDZixRQUFhLEVBQ2IsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILCtCQUErQjtRQUMvQixNQUFNLFlBQVksR0FBRyxNQUFNLCtCQUErQixDQUFDLElBQUksRUFBRSxLQUFLLENBQUMsQ0FBQztRQUV4RSxxQkFBcUI7UUFDckIsSUFBSSxDQUFDLFNBQVMsRUFBRSxDQUFDO1lBQ2YsU0FBUyxHQUFHLEtBQUssRUFBRSxDQUFDLFFBQVEsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDaEQsQ0FBQztRQUVELElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNiLE9BQU8sR0FBRyxLQUFLLEVBQUUsQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQ3pDLENBQUM7UUFFRCxNQUFNLEdBQUcsR0FBRyxNQUFNLDJCQUEyQixDQUMzQyxJQUFJLEVBQUUsTUFBTSxFQUNaLFlBQVksRUFDWixTQUFTLEVB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S0FBSyxpQkFBaUIsRUFBRSxDQUFDO1lBQzFELE1BQU0sZ0JBQWdCLEdBQXlCO2dCQUM3QyxJQUFJLEVBQUUsV0FBVztnQkFDakIsT0FBTyxFQUFFLDZDQUE2QzthQUN2RCxDQUFDO1lBRUYsb0JBQW9CLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQ3JELG9CQUFvQixDQUFDLEtBQUssR0FBRyxpQkFBaUIsQ0FBQztZQUMvQyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO1FBQ3ZDLENBQUM7UUFFRCxPQUFPLG9CQUFvQixDQUFDO0lBQzlCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsbURBQW1ELENBQUMsQ0FBQztJQUN0RSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IERhdGVUaW1lSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvRGF0ZVRpbWVKU09OSlNPTlR5cGUnO1xuaW1wb3J0IFVzZXJJbnB1dFRvSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVXNlcklucHV0VG9KU09OVHlwZSc7XG5pbXBvcnQgUmVzcG9uc2VBY3Rpb25UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1Jlc3BvbnNlQWN0aW9uVHlwZSc7XG5pbXBvcnQgeyBEZWxldGVQcmlvcml0eVR5cGUgfSBmcm9tICcuL3R5cGVzJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCByZXF1aXJlZEZpZWxkcyBmcm9tICcuL3JlcXVpcmVkRmllbGRzJztcbmltcG9ydCB7XG4gIGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaCxcbiAgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcixcbiAgZGVsZXRlRG9jSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsXG4gIGV2ZW50U2VhcmNoQm91bmRhcnksXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMsXG4gIGdlbmVyYXRlRGF0ZVRpbWUsXG4gIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNEYXRlVGltZSxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0LFxufSBmcm9tICdAY2hhdC9fbGlicy9hcGktaGVscGVyJztcbmltcG9ydCB7IHVudHJhaW5FdmVudFdpdGhQcmlvcml0eUFuZE1vZGlmaWFibGUgfSBmcm9tICcuLi9yZXNvbHZlQ29uZmxpY3RpbmdFdmVudHMvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHtcbiAgQXNzaXN0YW50TWVzc2FnZVR5cGUsXG4gIFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9NZXNzYWdpbmcvTWVzc2FnaW5nVHlwZXMnO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHsgU2VhcmNoQm91bmRhcnlUeXBlIH0gZnJvbSAnLi4vZGVsZXRlVGFzay90eXBlcyc7XG5cbmV4cG9ydCBjb25zdCBmaW5hbFN0ZXBEZWxldGVQcmlvcml0eSA9IGFzeW5jIChcbiAgYm9keTogRGVsZXRlUHJpb3JpdHlUeXBlLFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nLFxuICByZXNwb25zZTogYW55XG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvLyBjb252ZXJ0IHRvIHZlY3RvciBmb3Igc2VhcmNoXG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSk7XG5cbiAgICAvLyBhbGxFdmVudE9wZW5TZWFyY2hcbiAgICBpZiAoIXN0YXJ0RGF0ZSkge1xuICAgICAgc3RhcnREYXRlID0gZGF5anMoKS5zdWJ0cmFjdCgyLCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGlmICghZW5kRGF0ZSkge1xuICAgICAgZW5kRGF0ZSA9IGRheWpzKCkuYWRkKDQsICd3JykuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzID0gYXdhaXQgYWxsRXZlbnRXaXRoRGF0ZXNPcGVuU2VhcmNoKFxuICAgICAgYm9keT8udXNlcklkLFxuICAgICAgc2VhcmNoVmVjdG9yLFxuICAgICAgc3RhcnREYXRlLFxuICAgICAgZW5kRGF0ZVxuICAgICk7XG5cbiAgICBjb25zdCBpZCA9IHJlcz8uaGl0cz8uaGl0cz8uWzBdPy5faWQ7XG5cbiAgICAvLyB2YWxpZGF0ZSBmb3VuZCBldmVudFxuICAgIGlmICghaWQpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgYXdhaXQgdW50cmFpbkV2ZW50V2l0aFByaW9yaXR5QW5kTW9kaWZpYWJsZShpZCwgZmFsc2UsIDEpO1xuXG4gICAgLy8gZGVsZXRlIGRhdGEgaW4gdHJhaW4gaW5kZXhcbiAgICBhd2FpdCBkZWxldGVEb2NJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaChpZCk7XG5cbiAgICAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICByZXNwb25zZS5kYXRhID0gJ3N1Y2Nlc3NmdWxseSBkZWxldGVkIHByaW9yaXR5JztcbiAgICByZXR1cm4gcmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkZWxldGUgcHJpb3JpdHknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NEZWxldGVQcmlvcml0eVBlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nXG4pOiBQcm9taXNlPFJlc3BvbnNlQWN0aW9uVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICBjb25zdCBib2R5OiBEZWxldGVQcmlvcml0eVR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICB9O1xuXG4gICAgLy8gdmFsaWRhdGUgZm9yIG1pc3NpbmcgZmllbGRzXG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAnZGVsZXRlUHJpb3JpdHknLFxuICAgIH07XG5cbiAgICBpZiAoIWJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkLnB1c2gocmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ/LlswXSk7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgIHNlYXJjaEJvdW5kYXJ5LFxuICAgICAgfTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBEZWxldGVQcmlvcml0eShcbiAgICAgIGJvZHksXG4gICAgICBzdGFydERhdGUsXG4gICAgICBlbmREYXRlLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcblxuICAgIC8vIGNvbnZlcnQgdG8gdmVjdG9yIGZvciBzZWFyY2hcbiAgICAvLyBjb25zdCBzZWFyY2hWZWN0b3IgPSBhd2FpdCBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yKGJvZHk/LnRpdGxlKVxuXG4gICAgLy8gLy8gYWxsRXZlbnRPcGVuU2VhcmNoXG4gICAgLy8gaWYgKCFzdGFydERhdGUpIHtcbiAgICAvLyAgICAgc3RhcnREYXRlID0gZGF5anMoKS5zdWJ0cmFjdCgyLCAndycpLmZvcm1hdCgpXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKCFlbmREYXRlKSB7XG4gICAgLy8gICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpXG4gICAgLy8gfVxuXG4gICAgLy8gY29uc3QgcmVzID0gYXdhaXQgYWxsRXZlbnRXaXRoRGF0ZXNPcGVuU2VhcmNoKHVzZXJJZCwgc2VhcmNoVmVjdG9yLCBzdGFydERhdGUsIGVuZERhdGUpXG5cbiAgICAvLyBjb25zdCBpZCA9IHJlcz8uaGl0cz8uaGl0cz8uWzBdPy5faWRcblxuICAgIC8vIC8vIHZhbGlkYXRlIGZvdW5kIGV2ZW50XG4gICAgLy8gaWYgKCFpZCkge1xuICAgIC8vICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnXG4gICAgLy8gICAgIHJldHVybiByZXNwb25zZVxuICAgIC8vIH1cblxuICAgIC8vIGF3YWl0IHVudHJhaW5FdmVudFdpdGhQcmlvcml0eUFuZE1vZGlmaWFibGUoaWQsIGZhbHNlLCAxKVxuXG4gICAgLy8gLy8gZGVsZXRlIGRhdGEgaW4gdHJhaW4gaW5kZXhcbiAgICAvLyBhd2FpdCBkZWxldGVEb2NJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaChpZClcblxuICAgIC8vIC8vIHN1Y2Nlc3MgcmVzcG9uc2VcbiAgICAvLyByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnXG5cbiAgICAvLyByZXR1cm4gcmVzcG9uc2VcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgYWRkIHByaW9yaXR5Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzRGVsZXRlUHJpb3JpdHlNaXNzaW5nRmllbGRzUmV0dXJuZWQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICBjb25zdCBuZXdCb2R5OiBEZWxldGVQcmlvcml0eVR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2sgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICB9O1xuXG4gICAgY29uc3QgcHJldkJvZHk6IERlbGV0ZVByaW9yaXR5VHlwZSA9IHtcbiAgICAgIC4uLm1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YSxcbiAgICB9O1xuXG4gICAgaWYgKCFwcmV2Qm9keT8udXNlcklkKSB7XG4gICAgICBwcmV2Qm9keS51c2VySWQgPSB1c2VySWQgfHwgbmV3Qm9keT8udXNlcklkO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpbWV6b25lKSB7XG4gICAgICBwcmV2Qm9keS50aW1lem9uZSA9IHRpbWV6b25lIHx8IG5ld0JvZHk/LnRpbWV6b25lO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICBwcmV2Qm9keS50aXRsZSA9IG5ld0JvZHk/LnRpdGxlO1xuICAgIH1cblxuICAgIGNvbnN0IHByZXZTZWFyY2hCb3VuZGFyeTogU2VhcmNoQm91bmRhcnlUeXBlID1cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy5zZWFyY2hCb3VuZGFyeTtcblxuICAgIGxldCBwcmV2U3RhcnREYXRlID0gcHJldlNlYXJjaEJvdW5kYXJ5Py5zdGFydERhdGU7XG5cbiAgICBsZXQgcHJldkVuZERhdGUgPSBwcmV2U2VhcmNoQm91bmRhcnk/LmVuZERhdGU7XG5cbiAgICBpZiAoIXByZXZTdGFydERhdGUpIHtcbiAgICAgIHByZXZTdGFydERhdGUgPSBzdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2RW5kRGF0ZSkge1xuICAgICAgcHJldkVuZERhdGUgPSBlbmREYXRlO1xuICAgIH1cblxuICAgIC8vIHZhbGlkYXRlIGZvciBtaXNzaW5nIGZpZWxkc1xuXG4gICAgY29uc3QgbWlzc2luZ0ZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICAgICAgcmVxdWlyZWQ6IFtdLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ2RlbGV0ZVByaW9yaXR5JyxcbiAgICB9O1xuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzBdKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgIHNlYXJjaEJvdW5kYXJ5OiB7XG4gICAgICAgICAgc3RhcnREYXRlOiBwcmV2U3RhcnREYXRlLFxuICAgICAgICAgIGVuZERhdGU6IHByZXZFbmREYXRlLFxuICAgICAgICB9LFxuICAgICAgfTtcblxuICAgICAgcmVzcG9uc2UucHJldkpzb25Cb2R5ID0ganNvbkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0ZUpzb25Cb2R5ID0gZGF0ZUpTT05Cb2R5O1xuICAgIH1cblxuICAgIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcERlbGV0ZVByaW9yaXR5KFxuICAgICAgcHJldkJvZHksXG4gICAgICBwcmV2U3RhcnREYXRlLFxuICAgICAgcHJldkVuZERhdGUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBlLFxuICAgICAgJyB1bmFibGUgdG8gcHJvY2VzcyBkZWxldGUgcHJpb3JpdHkgdGltZSBtaXNzaW5nIGZpZWxkcyByZXR1cm5lZCdcbiAgICApO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlUHJpb3JpdHlDb250cm9sQ2VudGVyID0gYXN5bmMgKFxuICBvcGVuYWk6IE9wZW5BSSxcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbiAgdXNlckN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIHF1ZXJ5OiAnbWlzc2luZ19maWVsZHMnIHwgJ2NvbXBsZXRlZCcgfCAnZXZlbnRfbm90X2ZvdW5kJyB8ICdwZW5kaW5nJ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbWVzc2FnZUxlbmd0aCA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzPy5sZW5ndGg7XG4gICAgbGV0IHVzZXJNZXNzYWdlID0gJyc7XG4gICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICB1c2VyTWVzc2FnZSA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgYnJlYWs7XG4gICAgICB9XG4gICAgfVxuXG4gICAgY29uc3QgdXNlcklucHV0ID0gdXNlck1lc3NhZ2U7XG5cbiAgICBsZXQgZGVsZXRlUHJpb3JpdHlSZXM6IFJlc3BvbnNlQWN0aW9uVHlwZSA9IHtcbiAgICAgIHF1ZXJ5OiAnY29tcGxldGVkJyxcbiAgICAgIGRhdGE6ICcnLFxuICAgICAgc2tpbGw6ICcnLFxuICAgICAgcHJldkRhdGE6IHt9LFxuICAgICAgcHJldkRhdGFFeHRyYToge30sXG4gICAgfTtcblxuICAgIHN3aXRjaCAocXVlcnkpIHtcbiAgICAgIGNhc2UgJ3BlbmRpbmcnOlxuICAgICAgICBjb25zdCBqc29uQm9keSA9IGF3YWl0IGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZVRpbWUgPSBhd2FpdCBnZW5lcmF0ZURhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgZGVsZXRlUHJpb3JpdHlSZXMgPSBhd2FpdCBwcm9jZXNzRGVsZXRlUHJpb3JpdHlQZW5kaW5nKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uQm9keSxcbiAgICAgICAgICBkYXRlVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdtaXNzaW5nX2ZpZWxkcyc6XG4gICAgICAgIGxldCBwcmlvclVzZXJJbnB1dCA9ICcnO1xuICAgICAgICBsZXQgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSAnJztcblxuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAnYXNzaXN0YW50Jykge1xuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgIGlmIChtZXNzYWdlLmNvbnRlbnQgIT09IHVzZXJJbnB1dCkge1xuICAgICAgICAgICAgICBwcmlvclVzZXJJbnB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmlvclVzZXJJbnB1dCB8fCAhcHJpb3JBc3Npc3RhbnRPdXRwdXQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvclVzZXJJbnB1dCwgJyBwcmlvclVzZXJJbnB1dCcpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yQXNzaXN0YW50T3V0cHV0LCAnIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBwcmlvclVzZXJpbnB1dCBvciBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGpzb25NaXNzaW5nRmllbGRzQm9keSA9XG4gICAgICAgICAgYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVNaXNzaW5nRmllbGRzVGltZSA9IGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcblxuICAgICAgICBkZWxldGVQcmlvcml0eVJlcyA9IGF3YWl0IHByb2Nlc3NEZWxldGVQcmlvcml0eU1pc3NpbmdGaWVsZHNSZXR1cm5lZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbk1pc3NpbmdGaWVsZHNCb2R5LFxuICAgICAgICAgIGRhdGVNaXNzaW5nRmllbGRzVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgfVxuXG4gICAgaWYgKGRlbGV0ZVByaW9yaXR5UmVzPy5xdWVyeSA9PT0gJ2NvbXBsZXRlZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnkoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGRlbGV0ZVByaW9yaXR5UmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoZGVsZXRlUHJpb3JpdHlSZXM/LnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGRlbGV0ZVByaW9yaXR5UmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPVxuICAgICAgICBkZWxldGVQcmlvcml0eVJlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IGRlbGV0ZVByaW9yaXR5UmVzLnByZXZEYXRhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGFFeHRyYSA9IGRlbGV0ZVByaW9yaXR5UmVzLnByZXZEYXRhRXh0cmE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0ZUpzb25Cb2R5ID1cbiAgICAgICAgZGVsZXRlUHJpb3JpdHlSZXM/LnByZXZEYXRlSnNvbkJvZHk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2SnNvbkJvZHkgPSBkZWxldGVQcmlvcml0eVJlcz8ucHJldkpzb25Cb2R5O1xuICAgIH0gZWxzZSBpZiAoZGVsZXRlUHJpb3JpdHlSZXM/LnF1ZXJ5ID09PSAnZXZlbnRfbm90X2ZvdW5kJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZTogQXNzaXN0YW50TWVzc2FnZVR5cGUgPSB7XG4gICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgICBjb250ZW50OiBcIk9vcHMuLi4gSSBjb3VsZG4ndCBmaW5kIHRoZSBldmVudC4gU29ycnkgOihcIixcbiAgICAgIH07XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH1cblxuICAgIHJldHVybiBtZXNzYWdlSGlzdG9yeU9iamVjdDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBwcmlvcml0eSBjb250cm9sIGNlbnRlciBwZW5kaW5nJyk7XG4gIH1cbn07XG4iXX0=