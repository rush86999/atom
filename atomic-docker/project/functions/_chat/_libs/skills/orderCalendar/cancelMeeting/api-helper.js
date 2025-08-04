import requiredFields from './requiredFields';
import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, deleteConferenceGivenId, deleteDocInAllEventIndexInOpenSearch, deleteDocInTrainEventIndexInOpenSearch, deleteEventGivenId, deleteGoogleEvent, deleteZoomMeeting, eventSearchBoundary, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, getCalendarIntegrationByName, getConferenceGivenId, getEventFromPrimaryKey, getZoomAPIToken, } from '@chat/_libs/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { googleCalendarName } from '@chat/_libs/constants';
export const finalStepCancelMeeting = async (body, eventId, response) => {
    try {
        // get old event
        const oldEvent = await getEventFromPrimaryKey(eventId);
        // validate
        if (!oldEvent?.id) {
            throw new Error('no old event found?!');
        }
        // delete any zoom conferences
        if (oldEvent?.conferenceId) {
            // get old conference object
            const oldConference = await getConferenceGivenId(oldEvent?.conferenceId);
            if (oldConference?.app === 'zoom') {
                // create conference object
                const zoomToken = await getZoomAPIToken(body?.userId);
                // deleteZoomMeeting
                await deleteZoomMeeting(zoomToken, parseInt(oldConference?.id, 10));
                await deleteConferenceGivenId(oldConference?.id);
            }
        }
        // get client type
        const calIntegration = await getCalendarIntegrationByName(body?.userId, googleCalendarName);
        // delete data in train index
        await deleteDocInTrainEventIndexInOpenSearch(eventId);
        await deleteDocInAllEventIndexInOpenSearch(eventId);
        await deleteGoogleEvent(body?.userId, oldEvent?.calendarId, oldEvent?.eventId, calIntegration?.clientType);
        await deleteEventGivenId(oldEvent?.id);
        // success response
        response.query = 'completed';
        response.data = 'meeting successfully cancelled';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step cancel meeting');
    }
};
export const processCancelMeetingPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
    try {
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
            skill: 'cancelMeeting',
        };
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
        let startDate = searchBoundary.startDate;
        let endDate = searchBoundary.endDate;
        // validate remaining required fields
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
        // convert to vector for search
        const searchVector = await convertEventTitleToOpenAIVector(body?.title);
        // allEventOpenSearch
        if (!startDate) {
            startDate = dayjs().subtract(2, 'w').format();
        }
        if (!endDate) {
            endDate = dayjs().add(4, 'w').format();
        }
        const res = await allEventWithDatesOpenSearch(userId, searchVector, startDate, endDate);
        const id = res?.hits?.hits?.[0]?._id;
        // validate found event
        if (!id) {
            response.query = 'event_not_found';
            return response;
        }
        const response2 = await finalStepCancelMeeting(body, id, response);
        return response2;
        // // get old event
        // const oldEvent = await getEventFromPrimaryKey(eventId)
        // // validate
        // if (!oldEvent?.id) {
        //     throw new Error('no old event found?!')
        // }
        // // delete any zoom conferences
        // if (oldEvent?.conferenceId) {
        //     // get old conference object
        //     const oldConference = await getConferenceGivenId(oldEvent?.conferenceId)
        //     if (oldConference?.app === 'zoom') {
        //         // create conference object
        //         const zoomToken = await getZoomAPIToken(userId)
        //         // deleteZoomMeeting
        //         await deleteZoomMeeting(zoomToken, parseInt(oldConference?.id, 10))
        //         await deleteConferenceGivenId(oldConference?.id)
        //     }
        // }
        // // get client type
        // const calIntegration = await getCalendarIntegrationByName(
        //     userId,
        //     googleCalendarName,
        // )
        // // delete data in train index
        // await deleteDocInTrainEventIndexInOpenSearch(id)
        // await deleteDocInAllEventIndexInOpenSearch(id)
        // await deleteGoogleEvent(userId, oldEvent?.calendarId, oldEvent?.eventId, calIntegration?.clientType)
        // await deleteEventGivenId(oldEvent?.id)
        // // success response
        // response.query = 'completed'
        // return response
    }
    catch (e) {
        console.log(e, ' unable to process cancel meeting');
    }
};
export const processCancelMeetingMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
    try {
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
            // windowStartDate: messageHistoryObject?.prevDataExtra?.windowStartDate,
            // windowEndDate: messageHistoryObject?.prevDataExtra?.windowEndDate,
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
        // validate for missing fields
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'cancelMeeting',
        };
        let prevSearchBoundary = {
            startDate: messageHistoryObject?.prevDataExtra?.searchBoundary?.startDate,
            endDate: messageHistoryObject?.prevDataExtra?.searchBoundary?.endDate,
        };
        if (!prevSearchBoundary?.startDate) {
            const searchBoundaryNew = eventSearchBoundary(timezone, dateJSONBody, currentTime);
            prevSearchBoundary.startDate = searchBoundaryNew?.startDate;
        }
        if (!prevSearchBoundary?.endDate) {
            const searchBoundaryNew = eventSearchBoundary(timezone, dateJSONBody, currentTime);
            prevSearchBoundary.endDate = searchBoundaryNew?.endDate;
        }
        // prevSearchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime)
        let startDate = prevSearchBoundary.startDate;
        let endDate = prevSearchBoundary.endDate;
        // validate remaining required fields
        if (!prevBody?.title) {
            response.query = 'missing_fields';
            missingFields.required.push(requiredFields.required?.[0]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevDataExtra = {
                searchBoundary: prevSearchBoundary,
            };
            response.prevJsonBody = jsonBody;
            response.prevDateJsonBody = dateJSONBody;
        }
        if (response.query === 'missing_fields') {
            return response;
        }
        // convert to vector for search
        const searchVector = await convertEventTitleToOpenAIVector(prevBody?.title);
        // allEventOpenSearch
        if (!startDate) {
            startDate = dayjs().subtract(2, 'w').format();
        }
        if (!endDate) {
            endDate = dayjs().add(4, 'w').format();
        }
        const res = await allEventWithDatesOpenSearch(userId, searchVector, startDate, endDate);
        const id = res?.hits?.hits?.[0]?._id;
        // validate found event
        if (!id) {
            response.query = 'event_not_found';
            return response;
        }
        const response2 = await finalStepCancelMeeting(prevBody, id, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process cancle meeeting missing fields');
    }
};
export const cancelMeetingControlCenterPending = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let cancelMeetingRes = {
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
                cancelMeetingRes = await processCancelMeetingPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                cancelMeetingRes = await processCancelMeetingMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (cancelMeetingRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, cancelMeetingRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (cancelMeetingRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, cancelMeetingRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required =
                cancelMeetingRes?.data;
            messageHistoryObject.prevData = cancelMeetingRes?.prevData;
            messageHistoryObject.prevDataExtra = cancelMeetingRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody =
                cancelMeetingRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = cancelMeetingRes?.prevJsonBody;
        }
        else if (cancelMeetingRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to cancel meeting');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBR0EsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFFOUMsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiwrQkFBK0IsRUFDL0IsdUJBQXVCLEVBQ3ZCLG9DQUFvQyxFQUNwQyxzQ0FBc0MsRUFDdEMsa0JBQWtCLEVBQ2xCLGlCQUFpQixFQUNqQixpQkFBaUIsRUFDakIsbUJBQW1CLEVBQ25CLG1EQUFtRCxFQUNuRCxxREFBcUQsRUFDckQsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3Qiw2QkFBNkIsRUFDN0IsMENBQTBDLEVBQzFDLDRCQUE0QixFQUM1QixvQkFBb0IsRUFDcEIsc0JBQXNCLEVBQ3RCLGVBQWUsR0FDaEIsTUFBTSx3QkFBd0IsQ0FBQztBQUNoQyxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFDeEQsT0FBTyxFQUFFLGtCQUFrQixFQUFFLE1BQU0sdUJBQXVCLENBQUM7QUFTM0QsTUFBTSxDQUFDLE1BQU0sc0JBQXNCLEdBQUcsS0FBSyxFQUN6QyxJQUF1QixFQUN2QixPQUFlLEVBQ2YsUUFBYSxFQUNiLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxnQkFBZ0I7UUFDaEIsTUFBTSxRQUFRLEdBQUcsTUFBTSxzQkFBc0IsQ0FBQyxPQUFPLENBQUMsQ0FBQztRQUV2RCxXQUFXO1FBQ1gsSUFBSSxDQUFDLFFBQVEsRUFBRSxFQUFFLEVBQUUsQ0FBQztZQUNsQixNQUFNLElBQUksS0FBSyxDQUFDLHNCQUFzQixDQUFDLENBQUM7UUFDMUMsQ0FBQztRQUVELDhCQUE4QjtRQUM5QixJQUFJLFFBQVEsRUFBRSxZQUFZLEVBQUUsQ0FBQztZQUMzQiw0QkFBNEI7WUFDNUIsTUFBTSxhQUFhLEdBQUcsTUFBTSxvQkFBb0IsQ0FBQyxRQUFRLEVBQUUsWUFBWSxDQUFDLENBQUM7WUFFekUsSUFB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LGdCQUFnQixHQUF5QjtnQkFDN0MsSUFBSSxFQUFFLFdBQVc7Z0JBQ2pCLE9BQU8sRUFBRSw2Q0FBNkM7YUFDdkQsQ0FBQztZQUVGLG9CQUFvQixDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztZQUNyRCxvQkFBb0IsQ0FBQyxLQUFLLEdBQUcsaUJBQWlCLENBQUM7WUFDL0Msb0JBQW9CLENBQUMsUUFBUSxHQUFHLElBQUksQ0FBQztRQUN2QyxDQUFDO1FBRUQsT0FBTyxvQkFBb0IsQ0FBQztJQUM5QixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDJCQUEyQixDQUFDLENBQUM7SUFDOUMsQ0FBQztBQUNILENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBEYXRlVGltZUpTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL0RhdGVUaW1lSlNPTkpTT05UeXBlJztcbmltcG9ydCBVc2VySW5wdXRUb0pTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1VzZXJJbnB1dFRvSlNPTlR5cGUnO1xuaW1wb3J0IHsgQ2FuY2VsTWVldGluZ1R5cGUgfSBmcm9tICcuL3R5cGVzJztcbmltcG9ydCByZXF1aXJlZEZpZWxkcyBmcm9tICcuL3JlcXVpcmVkRmllbGRzJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCB7XG4gIGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaCxcbiAgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcixcbiAgZGVsZXRlQ29uZmVyZW5jZUdpdmVuSWQsXG4gIGRlbGV0ZURvY0luQWxsRXZlbnRJbmRleEluT3BlblNlYXJjaCxcbiAgZGVsZXRlRG9jSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2gsXG4gIGRlbGV0ZUV2ZW50R2l2ZW5JZCxcbiAgZGVsZXRlR29vZ2xlRXZlbnQsXG4gIGRlbGV0ZVpvb21NZWV0aW5nLFxuICBldmVudFNlYXJjaEJvdW5kYXJ5LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnksXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzLFxuICBnZW5lcmF0ZURhdGVUaW1lLFxuICBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dCxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzRGF0ZVRpbWUsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dCxcbiAgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZSxcbiAgZ2V0Q29uZmVyZW5jZUdpdmVuSWQsXG4gIGdldEV2ZW50RnJvbVByaW1hcnlLZXksXG4gIGdldFpvb21BUElUb2tlbixcbn0gZnJvbSAnQGNoYXQvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHsgZ29vZ2xlQ2FsZW5kYXJOYW1lIH0gZnJvbSAnQGNoYXQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCBSZXNwb25zZUFjdGlvblR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVzcG9uc2VBY3Rpb25UeXBlJztcbmltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCB7XG4gIEFzc2lzdGFudE1lc3NhZ2VUeXBlLFxuICBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvTWVzc2FnaW5nL01lc3NhZ2luZ1R5cGVzJztcbmltcG9ydCB7IFNlYXJjaEJvdW5kYXJ5VHlwZSB9IGZyb20gJy4uL2RlbGV0ZVRhc2svdHlwZXMnO1xuXG5leHBvcnQgY29uc3QgZmluYWxTdGVwQ2FuY2VsTWVldGluZyA9IGFzeW5jIChcbiAgYm9keTogQ2FuY2VsTWVldGluZ1R5cGUsXG4gIGV2ZW50SWQ6IHN0cmluZyxcbiAgcmVzcG9uc2U6IGFueVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgLy8gZ2V0IG9sZCBldmVudFxuICAgIGNvbnN0IG9sZEV2ZW50ID0gYXdhaXQgZ2V0RXZlbnRGcm9tUHJpbWFyeUtleShldmVudElkKTtcblxuICAgIC8vIHZhbGlkYXRlXG4gICAgaWYgKCFvbGRFdmVudD8uaWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gb2xkIGV2ZW50IGZvdW5kPyEnKTtcbiAgICB9XG5cbiAgICAvLyBkZWxldGUgYW55IHpvb20gY29uZmVyZW5jZXNcbiAgICBpZiAob2xkRXZlbnQ/LmNvbmZlcmVuY2VJZCkge1xuICAgICAgLy8gZ2V0IG9sZCBjb25mZXJlbmNlIG9iamVjdFxuICAgICAgY29uc3Qgb2xkQ29uZmVyZW5jZSA9IGF3YWl0IGdldENvbmZlcmVuY2VHaXZlbklkKG9sZEV2ZW50Py5jb25mZXJlbmNlSWQpO1xuXG4gICAgICBpZiAob2xkQ29uZmVyZW5jZT8uYXBwID09PSAnem9vbScpIHtcbiAgICAgICAgLy8gY3JlYXRlIGNvbmZlcmVuY2Ugb2JqZWN0XG4gICAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbihib2R5Py51c2VySWQpO1xuXG4gICAgICAgIC8vIGRlbGV0ZVpvb21NZWV0aW5nXG4gICAgICAgIGF3YWl0IGRlbGV0ZVpvb21NZWV0aW5nKHpvb21Ub2tlbiwgcGFyc2VJbnQob2xkQ29uZmVyZW5jZT8uaWQsIDEwKSk7XG5cbiAgICAgICAgYXdhaXQgZGVsZXRlQ29uZmVyZW5jZUdpdmVuSWQob2xkQ29uZmVyZW5jZT8uaWQpO1xuICAgICAgfVxuICAgIH1cblxuICAgIC8vIGdldCBjbGllbnQgdHlwZVxuICAgIGNvbnN0IGNhbEludGVncmF0aW9uID0gYXdhaXQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5TmFtZShcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIGdvb2dsZUNhbGVuZGFyTmFtZVxuICAgICk7XG5cbiAgICAvLyBkZWxldGUgZGF0YSBpbiB0cmFpbiBpbmRleFxuICAgIGF3YWl0IGRlbGV0ZURvY0luVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoKGV2ZW50SWQpO1xuXG4gICAgYXdhaXQgZGVsZXRlRG9jSW5BbGxFdmVudEluZGV4SW5PcGVuU2VhcmNoKGV2ZW50SWQpO1xuXG4gICAgYXdhaXQgZGVsZXRlR29vZ2xlRXZlbnQoXG4gICAgICBib2R5Py51c2VySWQsXG4gICAgICBvbGRFdmVudD8uY2FsZW5kYXJJZCxcbiAgICAgIG9sZEV2ZW50Py5ldmVudElkLFxuICAgICAgY2FsSW50ZWdyYXRpb24/LmNsaWVudFR5cGVcbiAgICApO1xuXG4gICAgYXdhaXQgZGVsZXRlRXZlbnRHaXZlbklkKG9sZEV2ZW50Py5pZCk7XG5cbiAgICAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICByZXNwb25zZS5kYXRhID0gJ21lZXRpbmcgc3VjY2Vzc2Z1bGx5IGNhbmNlbGxlZCc7XG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZmluYWwgc3RlcCBjYW5jZWwgbWVldGluZycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc0NhbmNlbE1lZXRpbmdQZW5kaW5nID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZ1xuKTogUHJvbWlzZTxSZXNwb25zZUFjdGlvblR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBib2R5OiBDYW5jZWxNZWV0aW5nVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgIH07XG5cbiAgICAvLyB2YWxpZGF0ZSBmb3IgbWlzc2luZyBmaWVsZHNcbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAnY2FuY2VsTWVldGluZycsXG4gICAgfTtcblxuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICAvLyB2YWxpZGF0ZSByZW1haW5pbmcgcmVxdWlyZWQgZmllbGRzXG4gICAgaWYgKCFib2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgLy8gY29udmVydCB0byB2ZWN0b3IgZm9yIHNlYXJjaFxuICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuXG4gICAgLy8gYWxsRXZlbnRPcGVuU2VhcmNoXG4gICAgaWYgKCFzdGFydERhdGUpIHtcbiAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIWVuZERhdGUpIHtcbiAgICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaChcbiAgICAgIHVzZXJJZCxcbiAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGVcbiAgICApO1xuXG4gICAgY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkO1xuXG4gICAgLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICBpZiAoIWlkKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcENhbmNlbE1lZXRpbmcoYm9keSwgaWQsIHJlc3BvbnNlKTtcbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICAgIC8vIC8vIGdldCBvbGQgZXZlbnRcbiAgICAvLyBjb25zdCBvbGRFdmVudCA9IGF3YWl0IGdldEV2ZW50RnJvbVByaW1hcnlLZXkoZXZlbnRJZClcblxuICAgIC8vIC8vIHZhbGlkYXRlXG4gICAgLy8gaWYgKCFvbGRFdmVudD8uaWQpIHtcbiAgICAvLyAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBvbGQgZXZlbnQgZm91bmQ/IScpXG4gICAgLy8gfVxuXG4gICAgLy8gLy8gZGVsZXRlIGFueSB6b29tIGNvbmZlcmVuY2VzXG4gICAgLy8gaWYgKG9sZEV2ZW50Py5jb25mZXJlbmNlSWQpIHtcblxuICAgIC8vICAgICAvLyBnZXQgb2xkIGNvbmZlcmVuY2Ugb2JqZWN0XG4gICAgLy8gICAgIGNvbnN0IG9sZENvbmZlcmVuY2UgPSBhd2FpdCBnZXRDb25mZXJlbmNlR2l2ZW5JZChvbGRFdmVudD8uY29uZmVyZW5jZUlkKVxuXG4gICAgLy8gICAgIGlmIChvbGRDb25mZXJlbmNlPy5hcHAgPT09ICd6b29tJykge1xuXG4gICAgLy8gICAgICAgICAvLyBjcmVhdGUgY29uZmVyZW5jZSBvYmplY3RcbiAgICAvLyAgICAgICAgIGNvbnN0IHpvb21Ub2tlbiA9IGF3YWl0IGdldFpvb21BUElUb2tlbih1c2VySWQpXG5cbiAgICAvLyAgICAgICAgIC8vIGRlbGV0ZVpvb21NZWV0aW5nXG4gICAgLy8gICAgICAgICBhd2FpdCBkZWxldGVab29tTWVldGluZyh6b29tVG9rZW4sIHBhcnNlSW50KG9sZENvbmZlcmVuY2U/LmlkLCAxMCkpXG5cbiAgICAvLyAgICAgICAgIGF3YWl0IGRlbGV0ZUNvbmZlcmVuY2VHaXZlbklkKG9sZENvbmZlcmVuY2U/LmlkKVxuICAgIC8vICAgICB9XG4gICAgLy8gfVxuXG4gICAgLy8gLy8gZ2V0IGNsaWVudCB0eXBlXG4gICAgLy8gY29uc3QgY2FsSW50ZWdyYXRpb24gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uQnlOYW1lKFxuICAgIC8vICAgICB1c2VySWQsXG4gICAgLy8gICAgIGdvb2dsZUNhbGVuZGFyTmFtZSxcbiAgICAvLyApXG5cbiAgICAvLyAvLyBkZWxldGUgZGF0YSBpbiB0cmFpbiBpbmRleFxuICAgIC8vIGF3YWl0IGRlbGV0ZURvY0luVHJhaW5FdmVudEluZGV4SW5PcGVuU2VhcmNoKGlkKVxuXG4gICAgLy8gYXdhaXQgZGVsZXRlRG9jSW5BbGxFdmVudEluZGV4SW5PcGVuU2VhcmNoKGlkKVxuXG4gICAgLy8gYXdhaXQgZGVsZXRlR29vZ2xlRXZlbnQodXNlcklkLCBvbGRFdmVudD8uY2FsZW5kYXJJZCwgb2xkRXZlbnQ/LmV2ZW50SWQsIGNhbEludGVncmF0aW9uPy5jbGllbnRUeXBlKVxuXG4gICAgLy8gYXdhaXQgZGVsZXRlRXZlbnRHaXZlbklkKG9sZEV2ZW50Py5pZClcblxuICAgIC8vIC8vIHN1Y2Nlc3MgcmVzcG9uc2VcbiAgICAvLyByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnXG5cbiAgICAvLyByZXR1cm4gcmVzcG9uc2VcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgY2FuY2VsIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NDYW5jZWxNZWV0aW5nTWlzc2luZ0ZpZWxkc1JldHVybmVkID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBuZXdCb2R5OiBDYW5jZWxNZWV0aW5nVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIG1ldGhvZDogZGF0ZUpTT05Cb2R5Py5tZXRob2QgYXMgYW55LFxuICAgIH07XG5cbiAgICBjb25zdCBwcmV2Qm9keTogQ2FuY2VsTWVldGluZ1R5cGUgPSB7XG4gICAgICAuLi5tZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGEsXG4gICAgICAvLyB3aW5kb3dTdGFydERhdGU6IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy53aW5kb3dTdGFydERhdGUsXG4gICAgICAvLyB3aW5kb3dFbmREYXRlOiBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGFFeHRyYT8ud2luZG93RW5kRGF0ZSxcbiAgICB9O1xuXG4gICAgaWYgKCFwcmV2Qm9keT8udXNlcklkKSB7XG4gICAgICBwcmV2Qm9keS51c2VySWQgPSB1c2VySWQgfHwgbmV3Qm9keT8udXNlcklkO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpbWV6b25lKSB7XG4gICAgICBwcmV2Qm9keS50aW1lem9uZSA9IHRpbWV6b25lIHx8IG5ld0JvZHk/LnRpbWV6b25lO1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICBwcmV2Qm9keS50aXRsZSA9IG5ld0JvZHk/LnRpdGxlO1xuICAgIH1cblxuICAgIC8vIHZhbGlkYXRlIGZvciBtaXNzaW5nIGZpZWxkc1xuICAgIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAgIHJlcXVpcmVkOiBbXSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdjYW5jZWxNZWV0aW5nJyxcbiAgICB9O1xuXG4gICAgbGV0IHByZXZTZWFyY2hCb3VuZGFyeTogU2VhcmNoQm91bmRhcnlUeXBlID0ge1xuICAgICAgc3RhcnREYXRlOiBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGFFeHRyYT8uc2VhcmNoQm91bmRhcnk/LnN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGU6IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy5zZWFyY2hCb3VuZGFyeT8uZW5kRGF0ZSxcbiAgICB9O1xuXG4gICAgaWYgKCFwcmV2U2VhcmNoQm91bmRhcnk/LnN0YXJ0RGF0ZSkge1xuICAgICAgY29uc3Qgc2VhcmNoQm91bmRhcnlOZXcgPSBldmVudFNlYXJjaEJvdW5kYXJ5KFxuICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgICBjdXJyZW50VGltZVxuICAgICAgKTtcbiAgICAgIHByZXZTZWFyY2hCb3VuZGFyeS5zdGFydERhdGUgPSBzZWFyY2hCb3VuZGFyeU5ldz8uc3RhcnREYXRlO1xuICAgIH1cblxuICAgIGlmICghcHJldlNlYXJjaEJvdW5kYXJ5Py5lbmREYXRlKSB7XG4gICAgICBjb25zdCBzZWFyY2hCb3VuZGFyeU5ldyA9IGV2ZW50U2VhcmNoQm91bmRhcnkoXG4gICAgICAgIHRpbWV6b25lLFxuICAgICAgICBkYXRlSlNPTkJvZHksXG4gICAgICAgIGN1cnJlbnRUaW1lXG4gICAgICApO1xuICAgICAgcHJldlNlYXJjaEJvdW5kYXJ5LmVuZERhdGUgPSBzZWFyY2hCb3VuZGFyeU5ldz8uZW5kRGF0ZTtcbiAgICB9XG5cbiAgICAvLyBwcmV2U2VhcmNoQm91bmRhcnkgPSBldmVudFNlYXJjaEJvdW5kYXJ5KHRpbWV6b25lLCBkYXRlSlNPTkJvZHksIGN1cnJlbnRUaW1lKVxuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHByZXZTZWFyY2hCb3VuZGFyeS5zdGFydERhdGU7XG4gICAgbGV0IGVuZERhdGUgPSBwcmV2U2VhcmNoQm91bmRhcnkuZW5kRGF0ZTtcblxuICAgIC8vIHZhbGlkYXRlIHJlbWFpbmluZyByZXF1aXJlZCBmaWVsZHNcbiAgICBpZiAoIXByZXZCb2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgc2VhcmNoQm91bmRhcnk6IHByZXZTZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG5cbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICAvLyBjb252ZXJ0IHRvIHZlY3RvciBmb3Igc2VhcmNoXG4gICAgY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcihwcmV2Qm9keT8udGl0bGUpO1xuXG4gICAgLy8gYWxsRXZlbnRPcGVuU2VhcmNoXG4gICAgaWYgKCFzdGFydERhdGUpIHtcbiAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIWVuZERhdGUpIHtcbiAgICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaChcbiAgICAgIHVzZXJJZCxcbiAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGVcbiAgICApO1xuXG4gICAgY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkO1xuXG4gICAgLy8gdmFsaWRhdGUgZm91bmQgZXZlbnRcbiAgICBpZiAoIWlkKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgcmV0dXJuIHJlc3BvbnNlO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcENhbmNlbE1lZXRpbmcocHJldkJvZHksIGlkLCByZXNwb25zZSk7XG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgY2FuY2xlIG1lZWV0aW5nIG1pc3NpbmcgZmllbGRzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjYW5jZWxNZWV0aW5nQ29udHJvbENlbnRlclBlbmRpbmcgPSBhc3luYyAoXG4gIG9wZW5haTogT3BlbkFJLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxuICB1c2VyQ3VycmVudFRpbWU6IHN0cmluZyxcbiAgcXVlcnk6ICdtaXNzaW5nX2ZpZWxkcycgfCAnY29tcGxldGVkJyB8ICdldmVudF9ub3RfZm91bmQnIHwgJ3BlbmRpbmcnXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZXNzYWdlTGVuZ3RoID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXM/Lmxlbmd0aDtcbiAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJztcbiAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgIHVzZXJNZXNzYWdlID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCB1c2VySW5wdXQgPSB1c2VyTWVzc2FnZTtcblxuICAgIGxldCBjYW5jZWxNZWV0aW5nUmVzOiBSZXNwb25zZUFjdGlvblR5cGUgPSB7XG4gICAgICBxdWVyeTogJ2NvbXBsZXRlZCcsXG4gICAgICBkYXRhOiAnJyxcbiAgICAgIHNraWxsOiAnJyxcbiAgICAgIHByZXZEYXRhOiB7fSxcbiAgICAgIHByZXZEYXRhRXh0cmE6IHt9LFxuICAgIH07XG5cbiAgICBzd2l0Y2ggKHF1ZXJ5KSB7XG4gICAgICBjYXNlICdwZW5kaW5nJzpcbiAgICAgICAgY29uc3QganNvbkJvZHkgPSBhd2FpdCBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IGRhdGVUaW1lID0gYXdhaXQgZ2VuZXJhdGVEYXRlVGltZShcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICk7XG4gICAgICAgIGNhbmNlbE1lZXRpbmdSZXMgPSBhd2FpdCBwcm9jZXNzQ2FuY2VsTWVldGluZ1BlbmRpbmcoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25Cb2R5LFxuICAgICAgICAgIGRhdGVUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ21pc3NpbmdfZmllbGRzJzpcbiAgICAgICAgbGV0IHByaW9yVXNlcklucHV0ID0gJyc7XG4gICAgICAgIGxldCBwcmlvckFzc2lzdGFudE91dHB1dCA9ICcnO1xuXG4gICAgICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICdhc3Npc3RhbnQnKSB7XG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICAgICAgaWYgKG1lc3NhZ2UuY29udGVudCAhPT0gdXNlcklucHV0KSB7XG4gICAgICAgICAgICAgIHByaW9yVXNlcklucHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoIXByaW9yVXNlcklucHV0IHx8ICFwcmlvckFzc2lzdGFudE91dHB1dCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yVXNlcklucHV0LCAnIHByaW9yVXNlcklucHV0Jyk7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JBc3Npc3RhbnRPdXRwdXQsICcgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHByaW9yVXNlcmlucHV0IG9yIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgIH1cbiAgICAgICAgY29uc3QganNvbk1pc3NpbmdGaWVsZHNCb2R5ID1cbiAgICAgICAgICBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lID0gYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuXG4gICAgICAgIGNhbmNlbE1lZXRpbmdSZXMgPSBhd2FpdCBwcm9jZXNzQ2FuY2VsTWVldGluZ01pc3NpbmdGaWVsZHNSZXR1cm5lZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbk1pc3NpbmdGaWVsZHNCb2R5LFxuICAgICAgICAgIGRhdGVNaXNzaW5nRmllbGRzVGltZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgfVxuXG4gICAgaWYgKGNhbmNlbE1lZXRpbmdSZXM/LnF1ZXJ5ID09PSAnY29tcGxldGVkJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeShcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgY2FuY2VsTWVldGluZ1Jlcy5kYXRhIGFzIHN0cmluZyxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnY29tcGxldGVkJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9IGVsc2UgaWYgKGNhbmNlbE1lZXRpbmdSZXM/LnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGNhbmNlbE1lZXRpbmdSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9XG4gICAgICAgIGNhbmNlbE1lZXRpbmdSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGEgPSBjYW5jZWxNZWV0aW5nUmVzPy5wcmV2RGF0YTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhRXh0cmEgPSBjYW5jZWxNZWV0aW5nUmVzPy5wcmV2RGF0YUV4dHJhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGVKc29uQm9keSA9XG4gICAgICAgIGNhbmNlbE1lZXRpbmdSZXM/LnByZXZEYXRlSnNvbkJvZHk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2SnNvbkJvZHkgPSBjYW5jZWxNZWV0aW5nUmVzPy5wcmV2SnNvbkJvZHk7XG4gICAgfSBlbHNlIGlmIChjYW5jZWxNZWV0aW5nUmVzPy5xdWVyeSA9PT0gJ2V2ZW50X25vdF9mb3VuZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2U6IEFzc2lzdGFudE1lc3NhZ2VUeXBlID0ge1xuICAgICAgICByb2xlOiAnYXNzaXN0YW50JyxcbiAgICAgICAgY29udGVudDogXCJPb3BzLi4uIEkgY291bGRuJ3QgZmluZCB0aGUgZXZlbnQuIFNvcnJ5IDooXCIsXG4gICAgICB9O1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9XG5cbiAgICByZXR1cm4gbWVzc2FnZUhpc3RvcnlPYmplY3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBjYW5jZWwgbWVldGluZycpO1xuICB9XG59O1xuIl19