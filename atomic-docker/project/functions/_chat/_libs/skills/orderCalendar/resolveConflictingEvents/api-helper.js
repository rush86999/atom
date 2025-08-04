import requiredFields from './requiredFields';
import { allEventWithDatesOpenSearch, convertEventTitleToOpenAIVector, eventSearchBoundary, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateDateTime, generateJSONDataFromUserInput, generateMissingFieldsDateTime, generateMissingFieldsJSONDataFromUserInput, putDataInTrainEventIndexInOpenSearch, } from '@chat/_libs/api-helper';
import listPreferredTimeRangesByEventId from '@chat/_libs/gql/listPreferredTimeRangesByEventId';
import got from 'got';
import { hasuraAdminSecret, hasuraGraphUrl } from '@chat/_libs/constants';
import { v4 as uuid } from 'uuid';
import { DayOfWeekEnum } from './constants';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import deletePreferredTimeRangesWithIds from '@chat/_libs/gql/deletePreferredTimeRangesWithIds';
import upsertPreferredTimeRanges from '@chat/_libs/gql/upsertPreferredTimeRanges';
import trainEventWithPriorityAndModifiableGraphql from '@chat/_libs/gql/trainEventWithPriorityAndModifiable';
import trainEventModifiable from '@chat/_libs/gql/trainEventModifiable';
import untrainEventModifiable from '@chat/_libs/gql/untrainEventModifiable';
import updateEventModifiable from '@chat/_libs/gql/updateEventModifiable';
export const upsertPreferredTimeRangesForEvent = async (preferredTimeRanges) => {
    try {
        const operationName = 'UpsertPreferredTimeRanges';
        const query = upsertPreferredTimeRanges;
        const variables = {
            preferredTimeRanges,
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
        console.log(res?.data?.insert_PreferredTimeRange?.affected_rows, ' res inside upsertPreferredTimeRangesForEvent');
        return res?.data?.insert_PreferredTimeRange?.returning;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const trainEventWithPriorityAndModifiable = async (id, modifiable, priority) => {
    try {
        const operationName = 'UpdateEventTrainingWithPriorityAndModifiable';
        const query = trainEventWithPriorityAndModifiableGraphql;
        const variables = {
            id,
            modifiable,
            priority,
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
        console.log(res?.data?.update_Event_by_pk, ' res inside updateEventWithIdModifiable');
        return res?.data?.update_Event_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const untrainEventWithPriorityAndModifiable = async (id, modifiable, priority) => {
    try {
        const operationName = 'UntrainEventWithPriorityAndModifiable';
        const query = untrainEventWithPriorityAndModifiable;
        const variables = {
            id,
            modifiable,
            priority,
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
        console.log(res?.data?.update_Event_by_pk, ' res inside updateEventWithIdModifiable');
        return res?.data?.update_Event_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const updateEventWithPriorityAndModifiable = async (id, modifiable, priority) => {
    try {
        const operationName = 'UpdateEventWithPriorityAndModifiable';
        const query = updateEventWithPriorityAndModifiable;
        const variables = {
            id,
            modifiable,
            priority,
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
        console.log(res?.data?.update_Event_by_pk, ' res inside updateEventWithIdModifiable');
        return res?.data?.update_Event_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const trainEventWithIdModifiable = async (id, modifiable) => {
    try {
        const operationName = 'TrainEventModifiable';
        const query = trainEventModifiable;
        const variables = {
            id,
            modifiable,
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
        console.log(res?.data?.update_Event_by_pk, ' res inside updateEventWithIdModifiable');
        return res?.data?.update_Event_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const untrainEventWithIdModifiable = async (id, modifiable) => {
    try {
        const operationName = 'UntrainEventModifiable';
        const query = untrainEventModifiable;
        const variables = {
            id,
            modifiable,
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
        console.log(res?.data?.update_Event_by_pk, ' res inside updateEventWithIdModifiable');
        return res?.data?.update_Event_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const updateEventWithIdModifiable = async (id, modifiable) => {
    try {
        const operationName = 'UpdateEventModifiable';
        const query = updateEventModifiable;
        const variables = {
            id,
            modifiable,
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
        console.log(res?.data?.update_Event_by_pk, ' res inside updateEventWithIdModifiable');
        return res?.data?.update_Event_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const deletePreferredTimeRangesByIds = async (ids) => {
    try {
        const operationName = 'DeletePreferredTimeRangesWithIds';
        const query = deletePreferredTimeRangesWithIds;
        const variables = {
            ids,
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
        console.log(res?.data?.PreferredTimeRange?.affected_rows, ' res inside deletePreferredTimeRangesByIds');
        return res?.data?.PreferredTimeRange?.returning;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const listPreferredTimeRangesGivenEventId = async (eventId) => {
    try {
        const operationName = 'ListPreferredTimeRangesGivenEventId';
        const query = listPreferredTimeRangesByEventId;
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
        console.log(res, ' res inside listPreferredTimeRangesByUserId');
        if (res?.data?.PreferredTimeRange?.length > 0) {
            return res?.data?.PreferredTimeRange;
        }
        return null;
    }
    catch (e) {
        console.log(e, ' unable to get Email_Knowledgebase');
    }
};
export const finalStepRCE = async (body, startDate, endDate, response) => {
    try {
        const searchVector = await convertEventTitleToOpenAIVector(body?.title);
        if (!startDate) {
            startDate = dayjs().subtract(2, 'w').format();
        }
        if (!endDate) {
            endDate = dayjs().add(4, 'w').format();
        }
        const res = await allEventWithDatesOpenSearch(body?.userId, searchVector, startDate, endDate);
        const id = res?.hits?.hits?.[0]?._id;
        if (!id) {
            response.query = 'event_not_found';
            return response;
        }
        const newPreferredTimeRanges = [];
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
        const oldPreferredTimeRanges = await listPreferredTimeRangesGivenEventId(id);
        if (oldPreferredTimeRanges?.length > 0) {
            await deletePreferredTimeRangesByIds(oldPreferredTimeRanges?.map((p) => p?.id));
        }
        newPreferredTimeRanges?.forEach((pt) => ({ ...pt, eventId: id }));
        if (newPreferredTimeRanges?.length > 0) {
            await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
        }
        else {
            console.log('something went wrong with no new preferred time ranges generated');
        }
        if (body?.priority > 1) {
            await trainEventWithPriorityAndModifiable(id, true, body?.priority);
        }
        else {
            await trainEventWithIdModifiable(id, true);
        }
        await putDataInTrainEventIndexInOpenSearch(id, searchVector, body?.userId);
        response.query = 'completed';
        response.data =
            'successfully added time preferences and priorities to resolve future conflicting events';
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step RCE');
    }
};
export const processRCEPending = async (userId, timezone, jsonBody, dateJSONBody, currentTime) => {
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
            priority: jsonBody?.params?.priority || 1,
            method: dateJSONBody?.method,
            timePreferences: dateJSONBody?.timePreferences,
        };
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'resolveConflictingEvents',
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
        const response2 = await finalStepRCE(body, startDate, endDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process resolve conflicting events');
    }
};
export const processRCEMissingFieldsReturned = async (userId, timezone, jsonBody, dateJSONBody, currentTime, messageHistoryObject) => {
    try {
        const searchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime);
        let startDate = searchBoundary.startDate;
        let endDate = searchBoundary.endDate;
        const day = dateJSONBody?.day || messageHistoryObject?.prevDateJsonBody?.day;
        const isoWeekday = dateJSONBody?.isoWeekday ||
            messageHistoryObject?.prevDateJsonBody?.isoWeekday;
        const hour = dateJSONBody?.hour || messageHistoryObject?.prevDateJsonBody?.hour;
        const minute = dateJSONBody?.minute || messageHistoryObject?.prevDateJsonBody?.minute;
        const startTime = dateJSONBody?.startTime ||
            messageHistoryObject?.prevDateJsonBody?.startTime;
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
            priority: jsonBody?.params?.priority ||
                messageHistoryObject?.prevJsonBody?.params?.priority ||
                1,
            method: dateJSONBody?.method,
            timePreferences: dateJSONBody?.timePreferences,
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
        if (!prevBody?.priority) {
            prevBody.priority = newBody?.priority;
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
        const missingFields = {
            required: [],
        };
        const response = {
            query: '',
            data: {},
            skill: 'resolveConflictingEvents',
        };
        if (!prevStartDate && !day && !isoWeekday) {
            response.query = 'missing_fields';
            missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevDataExtra = {
                searchBoundary: {
                    startDate: prevStartDate,
                    endDate: prevEndDate,
                },
            };
        }
        if (!prevStartDate && hour === null && minute === null && !startTime) {
            response.query = 'missing_fields';
            missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1]);
            response.data = missingFields;
            response.prevData = prevBody;
            response.prevDataExtra = {
                searchBoundary: {
                    startDate: prevStartDate,
                    endDate: prevEndDate,
                },
            };
        }
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
        const response2 = await finalStepRCE(prevBody, prevStartDate, prevEndDate, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process rce fields returned');
    }
};
export const RCEControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let RCERes = {
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
                RCERes = await processRCEPending(userId, timezone, jsonBody, dateTime, userCurrentTime);
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
                RCERes = await processRCEMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, dateMissingFieldsTime, userCurrentTime, messageHistoryObject);
                break;
        }
        if (RCERes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, RCERes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (RCERes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, RCERes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = RCERes?.data;
            messageHistoryObject.prevData = RCERes?.prevData;
            messageHistoryObject.prevDataExtra = RCERes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = RCERes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = RCERes?.prevJsonBody;
        }
        else if (RCERes?.query === 'event_not_found') {
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
        console.log(e, ' unable to resolve conflicting events control center pending');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBS0EsT0FBTyxjQUFjLE1BQU0sa0JBQWtCLENBQUM7QUFDOUMsT0FBTyxFQUNMLDJCQUEyQixFQUMzQiwrQkFBK0IsRUFDL0IsbUJBQW1CLEVBQ25CLG1EQUFtRCxFQUNuRCxxREFBcUQsRUFDckQsZ0JBQWdCLEVBQ2hCLDZCQUE2QixFQUM3Qiw2QkFBNkIsRUFDN0IsMENBQTBDLEVBQzFDLG9DQUFvQyxHQUNyQyxNQUFNLHdCQUF3QixDQUFDO0FBQ2hDLE9BQU8sZ0NBQWdDLE1BQU0sa0RBQWtELENBQUM7QUFFaEcsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBQ3RCLE9BQU8sRUFBRSxpQkFBaUIsRUFBRSxjQUFjLEVBQUUsTUFBTSx1QkFBdUIsQ0FBQztBQUMxRSxPQUFPLEVBQUUsRUFBRSxJQUFJLElBQUksRUFBRSxNQUFNLE1BQU0sQ0FBQztBQUNsQyxPQUFPLEVBQUUsYUFBYSxFQUFFLE1BQU0sYUFBYSxDQUFDO0FBQzVDLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQUN4RCxPQUFPLGdDQUFnQyxNQUFNLGtEQUFrRCxDQUFDO0FBR2hHLE9BQU8seUJBQXlCLE1BQU0sMkNBQTJDLENBQUM7QUFDbEYsT0FBTywwQ0FBMEMsTUFBTSxxREFBcUQsQ0FBQztBQUM3RyxPQUFPLG9CQUFvQixNQUFNLHNDQUFzQyxDQUFDO0FBQ3hFLE9BQU8sc0JBQXNCLE1BQU0sd0NBQXdDLENBQUM7QUFDNUUsT0FBTyxxQkFBcUIsTUFBTSx1Q0FBdUMsQ0FBQztBQVExRSxNQUFNLENBQUMsTUFBTSxpQ0FBaUMsR0FBRyxLQUFLLEVBQ3BELG1CQUE2QyxFQUM3QyxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxhQUFhLEdBQUcsMkJBQTJCLENBQUM7UUFDbEQsTUFBTSxLQUFLLEdBQUcseUJBQXlC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b0IsQ0FBQyxZQUFZLEdBQUcsTUFBTSxFQUFFLFlBQVksQ0FBQztRQUMzRCxDQUFDO2FBQU0sSUFBSSxNQUFNLEVBQUUsS0FBSyxLQUFLLGlCQUFpQixFQUFFLENBQUM7WUFDL0MsTUFBTSxnQkFBZ0IsR0FBeUI7Z0JBQzdDLElBQUksRUFBRSxXQUFXO2dCQUNqQixPQUFPLEVBQUUsNkNBQTZDO2FBQ3ZELENBQUM7WUFFRixvQkFBb0IsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7WUFDckQsb0JBQW9CLENBQUMsS0FBSyxHQUFHLGlCQUFpQixDQUFDO1lBQy9DLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxJQUFJLENBQUM7UUFDdkMsQ0FBQztRQUVELE9BQU8sb0JBQW9CLENBQUM7SUFDOUIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUNULENBQUMsRUFDRCw4REFBOEQsQ0FDL0QsQ0FBQztJQUNKLENBQUM7QUFDSCxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgRGF0ZVRpbWVKU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9EYXRlVGltZUpTT05KU09OVHlwZSc7XG5pbXBvcnQgeyBSZXNvbHZlQ29uZmxpY3RpbmdFdmVudHNUeXBlIH0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgVXNlcklucHV0VG9KU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Vc2VySW5wdXRUb0pTT05UeXBlJztcbmltcG9ydCBSZXNwb25zZUFjdGlvblR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVzcG9uc2VBY3Rpb25UeXBlJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCByZXF1aXJlZEZpZWxkcyBmcm9tICcuL3JlcXVpcmVkRmllbGRzJztcbmltcG9ydCB7XG4gIGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaCxcbiAgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3RvcixcbiAgZXZlbnRTZWFyY2hCb3VuZGFyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyxcbiAgZ2VuZXJhdGVEYXRlVGltZSxcbiAgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0RhdGVUaW1lLFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIHB1dERhdGFJblRyYWluRXZlbnRJbmRleEluT3BlblNlYXJjaCxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQgZnJvbSAnQGNoYXQvX2xpYnMvZ3FsL2xpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzQnlFdmVudElkJztcbmltcG9ydCBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1ByZWZlcnJlZFRpbWVSYW5nZVR5cGUnO1xuaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IHsgaGFzdXJhQWRtaW5TZWNyZXQsIGhhc3VyYUdyYXBoVXJsIH0gZnJvbSAnQGNoYXQvX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJztcbmltcG9ydCB7IERheU9mV2Vla0VudW0gfSBmcm9tICcuL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuaW1wb3J0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNXaXRoSWRzIGZyb20gJ0BjaGF0L19saWJzL2dxbC9kZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzV2l0aElkcyc7XG5cbmltcG9ydCB7IEV2ZW50VHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0V2ZW50VHlwZSc7XG5pbXBvcnQgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlcyBmcm9tICdAY2hhdC9fbGlicy9ncWwvdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlcyc7XG5pbXBvcnQgdHJhaW5FdmVudFdpdGhQcmlvcml0eUFuZE1vZGlmaWFibGVHcmFwaHFsIGZyb20gJ0BjaGF0L19saWJzL2dxbC90cmFpbkV2ZW50V2l0aFByaW9yaXR5QW5kTW9kaWZpYWJsZSc7XG5pbXBvcnQgdHJhaW5FdmVudE1vZGlmaWFibGUgZnJvbSAnQGNoYXQvX2xpYnMvZ3FsL3RyYWluRXZlbnRNb2RpZmlhYmxlJztcbmltcG9ydCB1bnRyYWluRXZlbnRNb2RpZmlhYmxlIGZyb20gJ0BjaGF0L19saWJzL2dxbC91bnRyYWluRXZlbnRNb2RpZmlhYmxlJztcbmltcG9ydCB1cGRhdGVFdmVudE1vZGlmaWFibGUgZnJvbSAnQGNoYXQvX2xpYnMvZ3FsL3VwZGF0ZUV2ZW50TW9kaWZpYWJsZSc7XG5pbXBvcnQge1xuICBBc3Npc3RhbnRNZXNzYWdlVHlwZSxcbiAgU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG59IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL01lc3NhZ2luZy9NZXNzYWdpbmdUeXBlcyc7XG5pbXBvcnQgT3BlbkFJIGZyb20gJ29wZW5haSc7XG5pbXBvcnQgeyBTZWFyY2hCb3VuZGFyeVR5cGUgfSBmcm9tICcuLi9kZWxldGVUYXNrL3R5cGVzJztcblxuZXhwb3J0IGNvbnN0IHVwc2VydFByZWZlcnJlZFRpbWVSYW5nZXNGb3JFdmVudCA9IGFzeW5jIChcbiAgcHJlZmVycmVkVGltZVJhbmdlczogUHJlZmVycmVkVGltZVJhbmdlVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ1Vwc2VydFByZWZlcnJlZFRpbWVSYW5nZXMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlcztcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBwcmVmZXJyZWRUaW1lUmFuZ2VzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgaW5zZXJ0X1ByZWZlcnJlZFRpbWVSYW5nZToge1xuICAgICAgICAgIGFmZmVjdGVkX3Jvd3M6IG51bWJlcjtcbiAgICAgICAgICByZXR1cm5pbmc6IFByZWZlcnJlZFRpbWVSYW5nZVR5cGU7XG4gICAgICAgIH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXM/LmRhdGE/Lmluc2VydF9QcmVmZXJyZWRUaW1lUmFuZ2U/LmFmZmVjdGVkX3Jvd3MsXG4gICAgICAnIHJlcyBpbnNpZGUgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50J1xuICAgICk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5pbnNlcnRfUHJlZmVycmVkVGltZVJhbmdlPy5yZXR1cm5pbmc7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgRW1haWxfS25vd2xlZGdlYmFzZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdHJhaW5FdmVudFdpdGhQcmlvcml0eUFuZE1vZGlmaWFibGUgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmcsXG4gIG1vZGlmaWFibGU6IGJvb2xlYW4sXG4gIHByaW9yaXR5OiBudW1iZXJcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBkYXRlRXZlbnRUcmFpbmluZ1dpdGhQcmlvcml0eUFuZE1vZGlmaWFibGUnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gdHJhaW5FdmVudFdpdGhQcmlvcml0eUFuZE1vZGlmaWFibGVHcmFwaHFsO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgICAgbW9kaWZpYWJsZSxcbiAgICAgIHByaW9yaXR5LFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyB1cGRhdGVfRXZlbnRfYnlfcGs6IEV2ZW50VHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXM/LmRhdGE/LnVwZGF0ZV9FdmVudF9ieV9wayxcbiAgICAgICcgcmVzIGluc2lkZSB1cGRhdGVFdmVudFdpdGhJZE1vZGlmaWFibGUnXG4gICAgKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LnVwZGF0ZV9FdmVudF9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBFbWFpbF9Lbm93bGVkZ2ViYXNlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1bnRyYWluRXZlbnRXaXRoUHJpb3JpdHlBbmRNb2RpZmlhYmxlID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICBtb2RpZmlhYmxlOiBib29sZWFuLFxuICBwcmlvcml0eTogbnVtYmVyXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ1VudHJhaW5FdmVudFdpdGhQcmlvcml0eUFuZE1vZGlmaWFibGUnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gdW50cmFpbkV2ZW50V2l0aFByaW9yaXR5QW5kTW9kaWZpYWJsZTtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICAgIG1vZGlmaWFibGUsXG4gICAgICBwcmlvcml0eSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgdXBkYXRlX0V2ZW50X2J5X3BrOiBFdmVudFR5cGUgfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzPy5kYXRhPy51cGRhdGVfRXZlbnRfYnlfcGssXG4gICAgICAnIHJlcyBpbnNpZGUgdXBkYXRlRXZlbnRXaXRoSWRNb2RpZmlhYmxlJ1xuICAgICk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy51cGRhdGVfRXZlbnRfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgRW1haWxfS25vd2xlZGdlYmFzZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBkYXRlRXZlbnRXaXRoUHJpb3JpdHlBbmRNb2RpZmlhYmxlID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICBtb2RpZmlhYmxlOiBib29sZWFuLFxuICBwcmlvcml0eTogbnVtYmVyXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ1VwZGF0ZUV2ZW50V2l0aFByaW9yaXR5QW5kTW9kaWZpYWJsZSc7XG4gICAgY29uc3QgcXVlcnkgPSB1cGRhdGVFdmVudFdpdGhQcmlvcml0eUFuZE1vZGlmaWFibGU7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgICBtb2RpZmlhYmxlLFxuICAgICAgcHJpb3JpdHksXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IHVwZGF0ZV9FdmVudF9ieV9wazogRXZlbnRUeXBlIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlcz8uZGF0YT8udXBkYXRlX0V2ZW50X2J5X3BrLFxuICAgICAgJyByZXMgaW5zaWRlIHVwZGF0ZUV2ZW50V2l0aElkTW9kaWZpYWJsZSdcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8udXBkYXRlX0V2ZW50X2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IEVtYWlsX0tub3dsZWRnZWJhc2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHRyYWluRXZlbnRXaXRoSWRNb2RpZmlhYmxlID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICBtb2RpZmlhYmxlOiBib29sZWFuXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ1RyYWluRXZlbnRNb2RpZmlhYmxlJztcbiAgICBjb25zdCBxdWVyeSA9IHRyYWluRXZlbnRNb2RpZmlhYmxlO1xuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGlkLFxuICAgICAgbW9kaWZpYWJsZSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgdXBkYXRlX0V2ZW50X2J5X3BrOiBFdmVudFR5cGUgfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzPy5kYXRhPy51cGRhdGVfRXZlbnRfYnlfcGssXG4gICAgICAnIHJlcyBpbnNpZGUgdXBkYXRlRXZlbnRXaXRoSWRNb2RpZmlhYmxlJ1xuICAgICk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy51cGRhdGVfRXZlbnRfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgRW1haWxfS25vd2xlZGdlYmFzZScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdW50cmFpbkV2ZW50V2l0aElkTW9kaWZpYWJsZSA9IGFzeW5jIChcbiAgaWQ6IHN0cmluZyxcbiAgbW9kaWZpYWJsZTogYm9vbGVhblxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdVbnRyYWluRXZlbnRNb2RpZmlhYmxlJztcbiAgICBjb25zdCBxdWVyeSA9IHVudHJhaW5FdmVudE1vZGlmaWFibGU7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgaWQsXG4gICAgICBtb2RpZmlhYmxlLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyB1cGRhdGVfRXZlbnRfYnlfcGs6IEV2ZW50VHlwZSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXM/LmRhdGE/LnVwZGF0ZV9FdmVudF9ieV9wayxcbiAgICAgICcgcmVzIGluc2lkZSB1cGRhdGVFdmVudFdpdGhJZE1vZGlmaWFibGUnXG4gICAgKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LnVwZGF0ZV9FdmVudF9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBFbWFpbF9Lbm93bGVkZ2ViYXNlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVFdmVudFdpdGhJZE1vZGlmaWFibGUgPSBhc3luYyAoXG4gIGlkOiBzdHJpbmcsXG4gIG1vZGlmaWFibGU6IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnVXBkYXRlRXZlbnRNb2RpZmlhYmxlJztcbiAgICBjb25zdCBxdWVyeSA9IHVwZGF0ZUV2ZW50TW9kaWZpYWJsZTtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICAgIG1vZGlmaWFibGUsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IHVwZGF0ZV9FdmVudF9ieV9wazogRXZlbnRUeXBlIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlcz8uZGF0YT8udXBkYXRlX0V2ZW50X2J5X3BrLFxuICAgICAgJyByZXMgaW5zaWRlIHVwZGF0ZUV2ZW50V2l0aElkTW9kaWZpYWJsZSdcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8udXBkYXRlX0V2ZW50X2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IEVtYWlsX0tub3dsZWRnZWJhc2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNCeUlkcyA9IGFzeW5jIChpZHM6IHN0cmluZ1tdKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdEZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzV2l0aElkcyc7XG4gICAgY29uc3QgcXVlcnkgPSBkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzV2l0aElkcztcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZHMsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YToge1xuICAgICAgICBQcmVmZXJyZWRUaW1lUmFuZ2U6IHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzOiBudW1iZXI7XG4gICAgICAgICAgcmV0dXJuaW5nOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW107XG4gICAgICAgIH07XG4gICAgICB9O1xuICAgIH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgfSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICByZXM/LmRhdGE/LlByZWZlcnJlZFRpbWVSYW5nZT8uYWZmZWN0ZWRfcm93cyxcbiAgICAgICcgcmVzIGluc2lkZSBkZWxldGVQcmVmZXJyZWRUaW1lUmFuZ2VzQnlJZHMnXG4gICAgKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/LlByZWZlcnJlZFRpbWVSYW5nZT8ucmV0dXJuaW5nO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IEVtYWlsX0tub3dsZWRnZWJhc2UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzR2l2ZW5FdmVudElkID0gYXN5bmMgKGV2ZW50SWQ6IHN0cmluZykgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnTGlzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNCeUV2ZW50SWQ7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgZXZlbnRJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgUHJlZmVycmVkVGltZVJhbmdlOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gfSB9ID1cbiAgICAgIGF3YWl0IGdvdFxuICAgICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICAgIGpzb246IHtcbiAgICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICAgIHZhcmlhYmxlcyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgaW5zaWRlIGxpc3RQcmVmZXJyZWRUaW1lUmFuZ2VzQnlVc2VySWQnKTtcbiAgICBpZiAocmVzPy5kYXRhPy5QcmVmZXJyZWRUaW1lUmFuZ2U/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHJldHVybiByZXM/LmRhdGE/LlByZWZlcnJlZFRpbWVSYW5nZTtcbiAgICB9XG5cbiAgICByZXR1cm4gbnVsbDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBFbWFpbF9Lbm93bGVkZ2ViYXNlJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBmaW5hbFN0ZXBSQ0UgPSBhc3luYyAoXG4gIGJvZHk6IFJlc29sdmVDb25mbGljdGluZ0V2ZW50c1R5cGUsXG4gIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICBlbmREYXRlOiBzdHJpbmcsXG4gIHJlc3BvbnNlOiBhbnlcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuXG4gICAgaWYgKCFzdGFydERhdGUpIHtcbiAgICAgIHN0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIWVuZERhdGUpIHtcbiAgICAgIGVuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaChcbiAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGVcbiAgICApO1xuXG4gICAgY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkO1xuXG4gICAgaWYgKCFpZCkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCBuZXdQcmVmZXJyZWRUaW1lUmFuZ2VzOiBQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgdGltZXByZWZlcmVuY2Ugb2YgYm9keT8udGltZVByZWZlcmVuY2VzKSB7XG4gICAgICBpZiAodGltZXByZWZlcmVuY2UuZGF5T2ZXZWVrPy5sZW5ndGggPiAwKSB7XG4gICAgICAgIGZvciAoY29uc3QgZGF5T2ZXZWVrIG9mIHRpbWVwcmVmZXJlbmNlLmRheU9mV2Vlaykge1xuICAgICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgICBldmVudElkOiBpZCxcbiAgICAgICAgICAgIGRheU9mV2VlazogRGF5T2ZXZWVrRW51bVtkYXlPZldlZWtdLFxuICAgICAgICAgICAgc3RhcnRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5zdGFydFRpbWUsXG4gICAgICAgICAgICBlbmRUaW1lOiB0aW1lcHJlZmVyZW5jZT8udGltZVJhbmdlPy5lbmRUaW1lLFxuICAgICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICAgICAgICB1c2VySWQ6IGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICB9O1xuXG4gICAgICAgICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcy5wdXNoKG5ld1ByZWZlcnJlZFRpbWVSYW5nZSk7XG4gICAgICAgIH1cbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnN0IG5ld1ByZWZlcnJlZFRpbWVSYW5nZTogUHJlZmVycmVkVGltZVJhbmdlVHlwZSA9IHtcbiAgICAgICAgICBpZDogdXVpZCgpLFxuICAgICAgICAgIGV2ZW50SWQ6IGlkLFxuICAgICAgICAgIHN0YXJ0VGltZTogdGltZXByZWZlcmVuY2U/LnRpbWVSYW5nZT8uc3RhcnRUaW1lLFxuICAgICAgICAgIGVuZFRpbWU6IHRpbWVwcmVmZXJlbmNlPy50aW1lUmFuZ2U/LmVuZFRpbWUsXG4gICAgICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgICAgIHVzZXJJZDogYm9keT8udXNlcklkLFxuICAgICAgICB9O1xuXG4gICAgICAgIG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMucHVzaChuZXdQcmVmZXJyZWRUaW1lUmFuZ2UpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IG9sZFByZWZlcnJlZFRpbWVSYW5nZXMgPVxuICAgICAgYXdhaXQgbGlzdFByZWZlcnJlZFRpbWVSYW5nZXNHaXZlbkV2ZW50SWQoaWQpO1xuXG4gICAgaWYgKG9sZFByZWZlcnJlZFRpbWVSYW5nZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIGF3YWl0IGRlbGV0ZVByZWZlcnJlZFRpbWVSYW5nZXNCeUlkcyhcbiAgICAgICAgb2xkUHJlZmVycmVkVGltZVJhbmdlcz8ubWFwKChwKSA9PiBwPy5pZClcbiAgICAgICk7XG4gICAgfVxuXG4gICAgbmV3UHJlZmVycmVkVGltZVJhbmdlcz8uZm9yRWFjaCgocHQpID0+ICh7IC4uLnB0LCBldmVudElkOiBpZCB9KSk7XG5cbiAgICBpZiAobmV3UHJlZmVycmVkVGltZVJhbmdlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgYXdhaXQgdXBzZXJ0UHJlZmVycmVkVGltZVJhbmdlc0ZvckV2ZW50KG5ld1ByZWZlcnJlZFRpbWVSYW5nZXMpO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ3NvbWV0aGluZyB3ZW50IHdyb25nIHdpdGggbm8gbmV3IHByZWZlcnJlZCB0aW1lIHJhbmdlcyBnZW5lcmF0ZWQnXG4gICAgICApO1xuICAgIH1cblxuICAgIGlmIChib2R5Py5wcmlvcml0eSA+IDEpIHtcbiAgICAgIGF3YWl0IHRyYWluRXZlbnRXaXRoUHJpb3JpdHlBbmRNb2RpZmlhYmxlKGlkLCB0cnVlLCBib2R5Py5wcmlvcml0eSk7XG4gICAgfSBlbHNlIHtcbiAgICAgIGF3YWl0IHRyYWluRXZlbnRXaXRoSWRNb2RpZmlhYmxlKGlkLCB0cnVlKTtcbiAgICB9XG5cbiAgICBhd2FpdCBwdXREYXRhSW5UcmFpbkV2ZW50SW5kZXhJbk9wZW5TZWFyY2goaWQsIHNlYXJjaFZlY3RvciwgYm9keT8udXNlcklkKTtcblxuICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG5cbiAgICByZXNwb25zZS5kYXRhID1cbiAgICAgICdzdWNjZXNzZnVsbHkgYWRkZWQgdGltZSBwcmVmZXJlbmNlcyBhbmQgcHJpb3JpdGllcyB0byByZXNvbHZlIGZ1dHVyZSBjb25mbGljdGluZyBldmVudHMnO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZmluYWwgc3RlcCBSQ0UnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NSQ0VQZW5kaW5nID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAganNvbkJvZHk6IFVzZXJJbnB1dFRvSlNPTlR5cGUsXG4gIGRhdGVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgY3VycmVudFRpbWU6IHN0cmluZ1xuKTogUHJvbWlzZTxSZXNwb25zZUFjdGlvblR5cGU+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBzZWFyY2hCb3VuZGFyeSA9IGV2ZW50U2VhcmNoQm91bmRhcnkoXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGRhdGVKU09OQm9keSxcbiAgICAgIGN1cnJlbnRUaW1lXG4gICAgKTtcblxuICAgIGxldCBzdGFydERhdGUgPSBzZWFyY2hCb3VuZGFyeS5zdGFydERhdGU7XG4gICAgbGV0IGVuZERhdGUgPSBzZWFyY2hCb3VuZGFyeS5lbmREYXRlO1xuXG4gICAgY29uc3QgYm9keTogUmVzb2x2ZUNvbmZsaWN0aW5nRXZlbnRzVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIHByaW9yaXR5OiBqc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fCAxLFxuICAgICAgbWV0aG9kOiBkYXRlSlNPTkJvZHk/Lm1ldGhvZCBhcyBhbnksXG4gICAgICB0aW1lUHJlZmVyZW5jZXM6IGRhdGVKU09OQm9keT8udGltZVByZWZlcmVuY2VzLFxuICAgIH07XG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAncmVzb2x2ZUNvbmZsaWN0aW5nRXZlbnRzJyxcbiAgICB9O1xuXG4gICAgaWYgKCFib2R5Py50aXRsZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZCA9IHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKCFib2R5Py50aW1lUHJlZmVyZW5jZXM/LlswXSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZSA9IHJlcXVpcmVkRmllbGRzLmRhdGVUaW1lO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IGJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwUkNFKGJvZHksIHN0YXJ0RGF0ZSwgZW5kRGF0ZSwgcmVzcG9uc2UpO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgcmVzb2x2ZSBjb25mbGljdGluZyBldmVudHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NSQ0VNaXNzaW5nRmllbGRzUmV0dXJuZWQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgZGF0ZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHNlYXJjaEJvdW5kYXJ5ID0gZXZlbnRTZWFyY2hCb3VuZGFyeShcbiAgICAgIHRpbWV6b25lLFxuICAgICAgZGF0ZUpTT05Cb2R5LFxuICAgICAgY3VycmVudFRpbWVcbiAgICApO1xuXG4gICAgbGV0IHN0YXJ0RGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LnN0YXJ0RGF0ZTtcbiAgICBsZXQgZW5kRGF0ZSA9IHNlYXJjaEJvdW5kYXJ5LmVuZERhdGU7XG5cbiAgICBjb25zdCBkYXkgPVxuICAgICAgZGF0ZUpTT05Cb2R5Py5kYXkgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmRheTtcbiAgICBjb25zdCBpc29XZWVrZGF5ID1cbiAgICAgIGRhdGVKU09OQm9keT8uaXNvV2Vla2RheSB8fFxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/Lmlzb1dlZWtkYXk7XG4gICAgY29uc3QgaG91ciA9XG4gICAgICBkYXRlSlNPTkJvZHk/LmhvdXIgfHwgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRlSnNvbkJvZHk/LmhvdXI7XG4gICAgY29uc3QgbWludXRlID1cbiAgICAgIGRhdGVKU09OQm9keT8ubWludXRlIHx8IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0ZUpzb25Cb2R5Py5taW51dGU7XG4gICAgY29uc3Qgc3RhcnRUaW1lID1cbiAgICAgIGRhdGVKU09OQm9keT8uc3RhcnRUaW1lIHx8XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGVKc29uQm9keT8uc3RhcnRUaW1lO1xuXG4gICAgY29uc3QgbmV3Qm9keTogUmVzb2x2ZUNvbmZsaWN0aW5nRXZlbnRzVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIHByaW9yaXR5OlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5wcmlvcml0eSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnByaW9yaXR5IHx8XG4gICAgICAgIDEsXG4gICAgICBtZXRob2Q6IGRhdGVKU09OQm9keT8ubWV0aG9kIGFzIGFueSxcbiAgICAgIHRpbWVQcmVmZXJlbmNlczogZGF0ZUpTT05Cb2R5Py50aW1lUHJlZmVyZW5jZXMsXG4gICAgfTtcblxuICAgIGNvbnN0IHByZXZCb2R5OiBSZXNvbHZlQ29uZmxpY3RpbmdFdmVudHNUeXBlID0ge1xuICAgICAgLi4ubWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZEYXRhLFxuICAgIH07XG5cbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ucHJpb3JpdHkpIHtcbiAgICAgIHByZXZCb2R5LnByaW9yaXR5ID0gbmV3Qm9keT8ucHJpb3JpdHk7XG4gICAgfVxuXG4gICAgaWYgKCEocHJldkJvZHk/LnRpbWVQcmVmZXJlbmNlcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHByZXZCb2R5LnRpbWVQcmVmZXJlbmNlcyA9IG5ld0JvZHk/LnRpbWVQcmVmZXJlbmNlcztcbiAgICB9XG5cbiAgICBjb25zdCBwcmV2U2VhcmNoQm91bmRhcnk6IFNlYXJjaEJvdW5kYXJ5VHlwZSA9XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGFFeHRyYT8uc2VhcmNoQm91bmRhcnk7XG5cbiAgICBsZXQgcHJldlN0YXJ0RGF0ZSA9IHByZXZTZWFyY2hCb3VuZGFyeT8uc3RhcnREYXRlO1xuXG4gICAgbGV0IHByZXZFbmREYXRlID0gcHJldlNlYXJjaEJvdW5kYXJ5Py5lbmREYXRlO1xuXG4gICAgaWYgKCFwcmV2U3RhcnREYXRlKSB7XG4gICAgICBwcmV2U3RhcnREYXRlID0gc3RhcnREYXRlO1xuICAgIH1cblxuICAgIGlmICghcHJldkVuZERhdGUpIHtcbiAgICAgIHByZXZFbmREYXRlID0gZW5kRGF0ZTtcbiAgICB9XG5cbiAgICBjb25zdCBtaXNzaW5nRmllbGRzOiBSZXF1aXJlZEZpZWxkc1R5cGUgPSB7XG4gICAgICByZXF1aXJlZDogW10sXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAncmVzb2x2ZUNvbmZsaWN0aW5nRXZlbnRzJyxcbiAgICB9O1xuXG4gICAgaWYgKCFwcmV2U3RhcnREYXRlICYmICFkYXkgJiYgIWlzb1dlZWtkYXkpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQucHVzaChcbiAgICAgICAgcmVxdWlyZWRGaWVsZHMuZGF0ZVRpbWUucmVxdWlyZWQ/LlswXVxuICAgICAgKTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgIHNlYXJjaEJvdW5kYXJ5OiB7XG4gICAgICAgICAgc3RhcnREYXRlOiBwcmV2U3RhcnREYXRlLFxuICAgICAgICAgIGVuZERhdGU6IHByZXZFbmREYXRlLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoIXByZXZTdGFydERhdGUgJiYgaG91ciA9PT0gbnVsbCAmJiBtaW51dGUgPT09IG51bGwgJiYgIXN0YXJ0VGltZSkge1xuICAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWlzc2luZ0ZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZC5wdXNoKFxuICAgICAgICByZXF1aXJlZEZpZWxkcy5kYXRlVGltZS5yZXF1aXJlZD8uWzFdXG4gICAgICApO1xuICAgICAgcmVzcG9uc2UuZGF0YSA9IG1pc3NpbmdGaWVsZHM7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGFFeHRyYSA9IHtcbiAgICAgICAgc2VhcmNoQm91bmRhcnk6IHtcbiAgICAgICAgICBzdGFydERhdGU6IHByZXZTdGFydERhdGUsXG4gICAgICAgICAgZW5kRGF0ZTogcHJldkVuZERhdGUsXG4gICAgICAgIH0sXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmICghcHJldkJvZHk/LnRpdGxlKSB7XG4gICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtaXNzaW5nRmllbGRzLnJlcXVpcmVkID0gcmVxdWlyZWRGaWVsZHMucmVxdWlyZWQ7XG4gICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkcztcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhID0gcHJldkJvZHk7XG4gICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgICAgICBzZWFyY2hCb3VuZGFyeToge1xuICAgICAgICAgIHN0YXJ0RGF0ZTogcHJldlN0YXJ0RGF0ZSxcbiAgICAgICAgICBlbmREYXRlOiBwcmV2RW5kRGF0ZSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICByZXNwb25zZS5wcmV2SnNvbkJvZHkgPSBqc29uQm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRlSnNvbkJvZHkgPSBkYXRlSlNPTkJvZHk7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZVByZWZlcmVuY2VzPy5bMF0pIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1pc3NpbmdGaWVsZHMuZGF0ZVRpbWUgPSByZXF1aXJlZEZpZWxkcy5kYXRlVGltZTtcbiAgICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzO1xuICAgICAgcmVzcG9uc2UucHJldkRhdGEgPSBwcmV2Qm9keTtcbiAgICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgICAgIHNlYXJjaEJvdW5kYXJ5OiB7XG4gICAgICAgICAgc3RhcnREYXRlOiBwcmV2U3RhcnREYXRlLFxuICAgICAgICAgIGVuZERhdGU6IHByZXZFbmREYXRlLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICAgIHJlc3BvbnNlLnByZXZKc29uQm9keSA9IGpzb25Cb2R5O1xuICAgICAgcmVzcG9uc2UucHJldkRhdGVKc29uQm9keSA9IGRhdGVKU09OQm9keTtcbiAgICB9XG5cbiAgICBpZiAocmVzcG9uc2UucXVlcnkgPT09ICdtaXNzaW5nX2ZpZWxkcycpIHtcbiAgICAgIHJldHVybiByZXNwb25zZTtcbiAgICB9XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBSQ0UoXG4gICAgICBwcmV2Qm9keSxcbiAgICAgIHByZXZTdGFydERhdGUsXG4gICAgICBwcmV2RW5kRGF0ZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIHJjZSBmaWVsZHMgcmV0dXJuZWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IFJDRUNvbnRyb2xDZW50ZXIgPSBhc3luYyAoXG4gIG9wZW5haTogT3BlbkFJLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxuICB1c2VyQ3VycmVudFRpbWU6IHN0cmluZyxcbiAgcXVlcnk6ICdtaXNzaW5nX2ZpZWxkcycgfCAnY29tcGxldGVkJyB8ICdldmVudF9ub3RfZm91bmQnIHwgJ3BlbmRpbmcnXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZXNzYWdlTGVuZ3RoID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXM/Lmxlbmd0aDtcbiAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJztcbiAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgIHVzZXJNZXNzYWdlID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICB9XG5cbiAgICBjb25zdCB1c2VySW5wdXQgPSB1c2VyTWVzc2FnZTtcblxuICAgIGxldCBSQ0VSZXM6IFJlc3BvbnNlQWN0aW9uVHlwZSA9IHtcbiAgICAgIHF1ZXJ5OiAnY29tcGxldGVkJyxcbiAgICAgIGRhdGE6ICcnLFxuICAgICAgc2tpbGw6ICcnLFxuICAgICAgcHJldkRhdGE6IHt9LFxuICAgICAgcHJldkRhdGFFeHRyYToge30sXG4gICAgfTtcblxuICAgIHN3aXRjaCAocXVlcnkpIHtcbiAgICAgIGNhc2UgJ3BlbmRpbmcnOlxuICAgICAgICBjb25zdCBqc29uQm9keSA9IGF3YWl0IGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZVRpbWUgPSBhd2FpdCBnZW5lcmF0ZURhdGVUaW1lKFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgKTtcbiAgICAgICAgUkNFUmVzID0gYXdhaXQgcHJvY2Vzc1JDRVBlbmRpbmcoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25Cb2R5LFxuICAgICAgICAgIGRhdGVUaW1lLFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ21pc3NpbmdfZmllbGRzJzpcbiAgICAgICAgbGV0IHByaW9yVXNlcklucHV0ID0gJyc7XG4gICAgICAgIGxldCBwcmlvckFzc2lzdGFudE91dHB1dCA9ICcnO1xuXG4gICAgICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICdhc3Npc3RhbnQnKSB7XG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgIH1cblxuICAgICAgICAgIGlmIChtZXNzYWdlLnJvbGUgPT09ICd1c2VyJykge1xuICAgICAgICAgICAgaWYgKG1lc3NhZ2UuY29udGVudCAhPT0gdXNlcklucHV0KSB7XG4gICAgICAgICAgICAgIHByaW9yVXNlcklucHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgICBicmVhaztcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoIXByaW9yVXNlcklucHV0IHx8ICFwcmlvckFzc2lzdGFudE91dHB1dCkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yVXNlcklucHV0LCAnIHByaW9yVXNlcklucHV0Jyk7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JBc3Npc3RhbnRPdXRwdXQsICcgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHByaW9yVXNlcmlucHV0IG9yIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgIH1cbiAgICAgICAgY29uc3QganNvbk1pc3NpbmdGaWVsZHNCb2R5ID1cbiAgICAgICAgICBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICAgKTtcbiAgICAgICAgY29uc3QgZGF0ZU1pc3NpbmdGaWVsZHNUaW1lID0gYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzRGF0ZVRpbWUoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZSxcbiAgICAgICAgICB0aW1lem9uZVxuICAgICAgICApO1xuXG4gICAgICAgIFJDRVJlcyA9IGF3YWl0IHByb2Nlc3NSQ0VNaXNzaW5nRmllbGRzUmV0dXJuZWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25NaXNzaW5nRmllbGRzQm9keSxcbiAgICAgICAgICBkYXRlTWlzc2luZ0ZpZWxkc1RpbWUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgIH1cblxuICAgIGlmIChSQ0VSZXM/LnF1ZXJ5ID09PSAnY29tcGxldGVkJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeShcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgUkNFUmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoUkNFUmVzPy5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzKFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBSQ0VSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IFJDRVJlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IFJDRVJlcz8ucHJldkRhdGE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YUV4dHJhID0gUkNFUmVzPy5wcmV2RGF0YUV4dHJhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGVKc29uQm9keSA9IFJDRVJlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZKc29uQm9keSA9IFJDRVJlcz8ucHJldkpzb25Cb2R5O1xuICAgIH0gZWxzZSBpZiAoUkNFUmVzPy5xdWVyeSA9PT0gJ2V2ZW50X25vdF9mb3VuZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2U6IEFzc2lzdGFudE1lc3NhZ2VUeXBlID0ge1xuICAgICAgICByb2xlOiAnYXNzaXN0YW50JyxcbiAgICAgICAgY29udGVudDogXCJPb3BzLi4uIEkgY291bGRuJ3QgZmluZCB0aGUgZXZlbnQuIFNvcnJ5IDooXCIsXG4gICAgICB9O1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9XG5cbiAgICByZXR1cm4gbWVzc2FnZUhpc3RvcnlPYmplY3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHVuYWJsZSB0byByZXNvbHZlIGNvbmZsaWN0aW5nIGV2ZW50cyBjb250cm9sIGNlbnRlciBwZW5kaW5nJ1xuICAgICk7XG4gIH1cbn07XG4iXX0=