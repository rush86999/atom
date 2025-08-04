import { searchSingleEventByVectorWithDatesLanceDb, convertEventTitleToOpenAIVector, extractAttributesNeededFromUserInput, extrapolateEndDateFromJSONData, extrapolateStartDateFromJSONData, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateJSONDataFromUserInput, generateMissingFieldsJSONDataFromUserInput, generateMissingFieldsQueryDateFromUserInput, generateQueryDateFromUserInput, } from '@chat/_libs/api-helper'; // Updated import
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { listSortedObjectsForUserGivenDatesAndAttributes } from '@chat/_libs/skills/askCalendar/api-helper';
import _ from 'lodash';
export const finalStepQueryNextEvent = async (body, windowStartDate, windowEndDate, timezone, response) => {
    try {
        let searchVector = [];
        if (body?.title) {
            searchVector = await convertEventTitleToOpenAIVector(body?.title);
        }
        let searchResult = null; // Updated type
        let eventId = '';
        if (searchVector?.length > 0) {
            searchResult = await searchSingleEventByVectorWithDatesLanceDb(body?.userId, searchVector, windowStartDate, windowEndDate); // Updated call
            eventId = searchResult?.id; // Updated ID extraction
        }
        let objectsWithAttributes;
        if (eventId) {
            objectsWithAttributes =
                await listSortedObjectsForUserGivenDatesAndAttributes(body?.userId, body?.windowStartDate, body?.windowEndDate, body?.attributes, body?.isMeeting, [eventId]);
        }
        else {
            objectsWithAttributes =
                await listSortedObjectsForUserGivenDatesAndAttributes(body?.userId, body?.windowStartDate, body?.windowEndDate, body?.attributes, body?.isMeeting);
        }
        const events = objectsWithAttributes?.events;
        const conferences = objectsWithAttributes?.conferences;
        const attendees = objectsWithAttributes?.attendees;
        const tasks = objectsWithAttributes?.tasks;
        // const count = objectsWithAttributes?.count
        // validate found event
        if (!(events?.length > 0)) {
            response.query = 'event_not_found';
            return response;
        }
        let queryData = '';
        // uniq dates
        const uniqDates = _.uniqBy(events, (curr) => dayjs(curr?.startDate).tz(timezone, true).format('YYYY-MM-DD'))?.map((e) => e?.startDate);
        for (const uniqDate of uniqDates) {
            const filteredEvents = events?.filter((a) => dayjs(a?.startDate).tz(timezone, true).format('YYYY-MM-DD') ===
                dayjs(uniqDate).tz(timezone, true).format('YYYY-MM-DD'));
            queryData += `${dayjs(uniqDate).tz(timezone, true).format('ddd, YYYY-MM-DD')}`;
            queryData += '\n';
            if (body?.attributes?.find((a) => a === 'none')) {
                continue;
            }
            else {
                for (const event of filteredEvents) {
                    queryData += 'Event - ';
                    queryData += `title: ${event?.title || event?.summary}, `;
                    queryData += `time: ${dayjs(event?.startDate).tz(timezone, true).format('LT')} `;
                    queryData += `- ${dayjs(event?.endDate).tz(timezone, true).format('LT')}, `;
                    if (event?.conferenceId) {
                        const filteredConf = conferences?.find((c) => c?.id === event?.conferenceId);
                        if (filteredConf?.id) {
                            queryData += ' conference with event - ';
                            queryData += `name: ${filteredConf?.name}, `;
                            queryData += `app: ${filteredConf?.app}, `;
                            for (const property in filteredConf) {
                                if (property === 'notes') {
                                    if (body?.attributes?.find((a) => a === 'conference-notes')) {
                                        queryData += `${property}: ${filteredConf[property]}, `;
                                    }
                                }
                                else if (property === 'joinUrl') {
                                    if (body?.attributes?.find((a) => a === 'conference-joinUrl')) {
                                        queryData += `${property}: ${filteredConf[property]}, `;
                                    }
                                }
                                else if (property === 'startUrl') {
                                    if (body?.attributes?.find((a) => a === 'conference-startUrl')) {
                                        queryData += `${property}: ${filteredConf[property]}, `;
                                    }
                                }
                            }
                            if (attendees?.length > 0) {
                                queryData += 'attendees - ';
                                for (const attendee of attendees) {
                                    queryData += `name: ${attendee?.name}, `;
                                    queryData += `email: ${attendee?.emails?.find((e) => !!e?.primary)?.value}, `;
                                }
                            }
                        }
                    }
                    if (event?.taskId) {
                        const filteredTask = tasks?.find((t) => t?.id === event?.taskId);
                        if (filteredTask?.id) {
                            queryData += ' task with event - ';
                            queryData += `${filteredTask?.notes}, `;
                            for (const property in filteredTask) {
                                if (property === 'type') {
                                    if (body?.attributes?.find((a) => a === 'task-listName')) {
                                        queryData += `list: ${filteredTask[property]}, `;
                                    }
                                }
                                else if (property === 'status') {
                                    if (body?.attributes?.find((a) => a === 'task-status')) {
                                        queryData += `status: ${filteredTask[property]}, `;
                                    }
                                }
                            }
                        }
                    }
                    queryData += '\n';
                }
            }
            queryData += '\n\n';
        }
        // success response
        response.query = 'completed';
        response.data = queryData;
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step query next event');
    }
};
export const processQueryNextEventPending = async (userId, timezone, jsonBody, 
// dateTimeJSONBody: DateTimeJSONType,
attributesObject, queryDateJSONBody, currentTime) => {
    try {
        let windowStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, queryDateJSONBody?.start_date?.year, queryDateJSONBody?.start_date?.month, queryDateJSONBody?.start_date?.day, undefined, queryDateJSONBody?.start_date?.hour, queryDateJSONBody?.start_date?.minute, queryDateJSONBody?.start_date?.time, queryDateJSONBody?.start_date?.relativeTimeChangeFromNow, queryDateJSONBody?.start_date?.relativeTimeFromNow);
        let windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, queryDateJSONBody?.end_date?.year, queryDateJSONBody?.end_date?.month, queryDateJSONBody?.end_date?.day, undefined, queryDateJSONBody?.end_date?.hour, queryDateJSONBody?.end_date?.minute, queryDateJSONBody?.end_date?.time, queryDateJSONBody?.end_date?.relativeTimeChangeFromNow, queryDateJSONBody?.end_date?.relativeTimeFromNow);
        if (!windowStartDate) {
            windowStartDate = dayjs().format();
        }
        if (!windowEndDate) {
            windowEndDate = dayjs().add(1, 'w').format();
        }
        const body = {
            userId,
            timezone,
            title: jsonBody?.params?.title ||
                jsonBody?.params?.summary ||
                jsonBody?.params?.description ||
                jsonBody?.params?.taskList?.[0]?.task,
            isMeeting: attributesObject?.isMeeting,
            attributes: attributesObject?.attributes,
            windowStartDate,
            windowEndDate,
        };
        const response = {
            query: '',
            data: {},
            skill: 'queryNextEvent',
        };
        const response2 = await finalStepQueryNextEvent(body, windowStartDate, windowEndDate, timezone, response);
        return response2;
        // let searchVector: number[] = []
        // if (body?.title) {
        //     searchVector = await convertEventTitleToOpenAIVector(body?.title)
        // }
        // let eventId: string = ''
        // if (searchVector?.length > 0) {
        //     const res = await allEventWithDatesOpenSearch(userId, searchVector, windowStartDate, windowEndDate)
        //     eventId = res?.hits?.hits?.[0]?._id
        // }
        // const objectsWithAttributes = await listSortedObjectsForUserGivenDatesAndAttributes(
        //     body?.userId,
        //     body?.windowStartDate,
        //     body?.windowEndDate,
        //     body?.attributes,
        //     body?.isMeeting,
        //     eventId?.length > 0 ? [eventId] : [],
        // )
        // const events = objectsWithAttributes?.events
        // const conferences = objectsWithAttributes?.conferences
        // const attendees = objectsWithAttributes?.attendees
        // const tasks = objectsWithAttributes?.tasks
        // // const count = objectsWithAttributes?.count
        // let queryData = ''
        // // uniq dates
        // const uniqDates = _.uniqBy(events, (curr) => (dayjs(curr?.startDate).tz(timezone).format('YYYY-MM-DD')))?.map(e => e?.startDate)
        // for (const uniqDate of uniqDates) {
        //     const filteredEvents = events?.filter(a => (dayjs(a?.startDate).tz(timezone).format('YYYY-MM-DD') === dayjs(uniqDate).tz(timezone).format('YYYY-MM-DD')))
        //     queryData += `${dayjs(uniqDate).format('ddd, YYYY-MM-DD')}`
        //     queryData += '\n'
        //     for (const event of filteredEvents) {
        //         queryData += 'Event - '
        //         queryData += `title: ${event?.title || event?.summary}, `
        //         queryData += `time: ${dayjs(event?.startDate).tz(timezone).format('LT')} `
        //         queryData += `- ${dayjs(event?.endDate).tz(timezone).format('LT')}, `
        //         if (body?.attributes?.find(a => (a === 'none'))) {
        //             continue
        //         }
        //         const filteredConf = conferences?.find(c => (c?.id === event?.conferenceId))
        //         if (filteredConf?.id) {
        //             queryData += ' conference with event - '
        //             queryData += `name: ${filteredConf?.name}, `
        //             queryData += `app: ${filteredConf?.app}, `
        //             for (const property in filteredConf) {
        //                 if (property === 'notes') {
        //                     if (body?.attributes?.find(a => (a === 'conference-notes'))) {
        //                         queryData += `${property}: ${filteredConf[property]}, `
        //                     }
        //                 } else if (property === 'joinUrl') {
        //                     if (body?.attributes?.find(a => (a === 'conference-joinUrl'))) {
        //                         queryData += `${property}: ${filteredConf[property]}, `
        //                     }
        //                 } else if (property === 'startUrl') {
        //                     if (body?.attributes?.find(a => (a === 'conference-startUrl'))) {
        //                         queryData += `${property}: ${filteredConf[property]}, `
        //                     }
        //                 }
        //             }
        //             if (attendees?.length > 0) {
        //                 queryData += 'attendees - '
        //                 for (const attendee of attendees) {
        //                     queryData += `name: ${attendee?.name}, `
        //                     queryData += `email: ${attendee?.emails?.find(e => (!!e?.primary))?.value}, `
        //                 }
        //             }
        //         }
        //         const filteredTask = tasks?.find(t => (t?.id === event?.taskId))
        //         if (filteredTask?.id) {
        //             queryData += ' task with event - '
        //             queryData += `${filteredTask?.notes}, `
        //             for (const property in filteredTask) {
        //                 if (property === 'type') {
        //                     if (body?.attributes?.find(a => (a === 'task-listName'))) {
        //                         queryData += `list: ${filteredTask[property]}, `
        //                     }
        //                 } else if (property === 'status') {
        //                     if (body?.attributes?.find(a => (a === 'task-status'))) {
        //                         queryData += `status: ${filteredTask[property]}, `
        //                     }
        //                 }
        //             }
        //         }
        //         queryData += '\n'
        //     }
        //     queryData += '\n\n'
        // }
        // // success response
        // response.query = 'completed'
        // response.data = queryData
        // return response
    }
    catch (e) {
        console.log(e, ' unable to process query next event');
    }
};
export const processQueryNextEventMissingFieldsReturned = async (userId, timezone, jsonBody, 
// dateTimeJSONBody: DateTimeJSONType,
attributesObject, queryDateJSONBody, currentTime, messageHistoryObject) => {
    try {
        let windowStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, queryDateJSONBody?.start_date?.year, queryDateJSONBody?.start_date?.month, queryDateJSONBody?.start_date?.day, undefined, queryDateJSONBody?.start_date?.hour, queryDateJSONBody?.start_date?.minute, queryDateJSONBody?.start_date?.time, queryDateJSONBody?.start_date?.relativeTimeChangeFromNow, queryDateJSONBody?.start_date?.relativeTimeFromNow);
        let windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, queryDateJSONBody?.end_date?.year, queryDateJSONBody?.end_date?.month, queryDateJSONBody?.end_date?.day, undefined, queryDateJSONBody?.end_date?.hour, queryDateJSONBody?.end_date?.minute, queryDateJSONBody?.end_date?.time, queryDateJSONBody?.end_date?.relativeTimeChangeFromNow, queryDateJSONBody?.end_date?.relativeTimeFromNow);
        if (!windowStartDate) {
            windowStartDate = dayjs().format();
        }
        if (!windowEndDate) {
            windowEndDate = dayjs().add(1, 'w').format();
        }
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
            isMeeting: attributesObject?.isMeeting,
            attributes: attributesObject?.attributes,
            windowStartDate,
            windowEndDate,
        };
        const prevBody = {
            ...messageHistoryObject?.prevData,
            windowStartDate: messageHistoryObject?.prevDataExtra?.windowStartDate,
            windowEndDate: messageHistoryObject?.prevDataExtra?.windowEndDate,
        };
        // fix prevBody with new data
        if (!prevBody?.userId) {
            prevBody.userId = userId || newBody?.userId;
        }
        if (!prevBody?.timezone) {
            prevBody.timezone = timezone || newBody?.timezone;
        }
        if (!prevBody?.title) {
            prevBody.title = newBody?.title;
        }
        if (prevBody?.isMeeting === undefined) {
            prevBody.isMeeting = newBody?.isMeeting;
        }
        if (!(prevBody?.attributes?.length > 0)) {
            prevBody.attributes = newBody?.attributes;
        }
        if (!prevBody?.windowStartDate) {
            prevBody.windowStartDate = newBody?.windowStartDate;
        }
        if (!prevBody?.windowEndDate) {
            prevBody.windowEndDate = newBody?.windowEndDate;
        }
        const response = {
            query: '',
            data: {},
            skill: 'queryNextEvent',
        };
        const response2 = await finalStepQueryNextEvent(prevBody, prevBody?.windowStartDate, prevBody?.windowEndDate, prevBody?.timezone, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process query event missing fields returned');
    }
};
export const nextEventControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        const attributesObject = await extractAttributesNeededFromUserInput(userInput);
        let nextEventRes = {
            query: 'completed',
            data: '',
            skill: '',
            prevData: {},
            prevDataExtra: {},
        };
        switch (query) {
            case 'pending':
                const jsonBody = await generateJSONDataFromUserInput(userInput, userCurrentTime);
                const queryDate = await generateQueryDateFromUserInput(userId, timezone, userInput, userCurrentTime);
                nextEventRes = await processQueryNextEventPending(userId, timezone, jsonBody, attributesObject, queryDate, userCurrentTime);
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
                const queryMissingFieldsDate = await generateMissingFieldsQueryDateFromUserInput(userId, timezone, userInput, priorUserInput, priorAssistantOutput, userCurrentTime);
                nextEventRes = await processQueryNextEventMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, attributesObject, queryMissingFieldsDate, userCurrentTime, messageHistoryObject);
                break;
        }
        if (nextEventRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, nextEventRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (nextEventRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, nextEventRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = nextEventRes?.data;
            messageHistoryObject.prevData = nextEventRes?.prevData;
            messageHistoryObject.prevDataExtra = nextEventRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = nextEventRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = nextEventRes?.prevJsonBody;
        }
        else if (nextEventRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to next event control center');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBR0EsT0FBTyxFQUNMLHlDQUF5QyxFQUN6QywrQkFBK0IsRUFDL0Isb0NBQW9DLEVBQ3BDLDhCQUE4QixFQUM5QixnQ0FBZ0MsRUFDaEMsbURBQW1ELEVBQ25ELHFEQUFxRCxFQUNyRCw2QkFBNkIsRUFDN0IsMENBQTBDLEVBQzFDLDJDQUEyQyxFQUMzQyw4QkFBOEIsR0FDL0IsTUFBTSx3QkFBd0IsQ0FBQyxDQUFDLGlCQUFpQjtBQUVsRCxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFFeEQsT0FBTyxFQUFFLCtDQUErQyxFQUFFLE1BQU0sMkNBQTJDLENBQUM7QUFDNUcsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBY3ZCLE1BQU0sQ0FBQyxNQUFNLHVCQUF1QixHQUFHLEtBQUssRUFDMUMsSUFBd0IsRUFDeEIsZUFBdUIsRUFDdkIsYUFBcUIsRUFDckIsUUFBZ0IsRUFDaEIsUUFBYSxFQUNiLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxJQUFJLFlBQVksR0FBYSxFQUFFLENBQUM7UUFFaEMsSUFBSSxJQUFJLEVBQUUsS0FBSyxFQUFFLENBQUM7WUFDaEIsWUFBWSxHQUFHLE1BQU0sK0JBQStCLENBQUMsSUFBSSxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQ3BFLENBQUM7UUFFRCxJQUFJLFlBQVksR0FBOEIsSUFBSSxDQUFDLENBQUMsZUFBZTtRQUNuRSxJQUFJLE9BQU8sR0FBVyxFQUFFLENBQUM7UUFFekIsSUFBSSxZQUFZLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQzdCLFlBQVksR0FBRyxNQUFNLHlDQUF5QyxDQUM1RCxJQUFJLEVBQUUsTUFBTSxFQUNaLFlBQVksRUFDWixlQUFlLEVBQ2YsYUFBYSxDQUNkLENBQUMsQ0FBQyxlQUFlO1lBQ2xCLE9BQU8sR0FBRyxZ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MEIsQ0FBQztZQUN6RSxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsWUFBWSxFQUFFLFFBQVEsQ0FBQztZQUN2RCxvQkFBb0IsQ0FBQyxhQUFhLEdBQUcsWUFBWSxFQUFFLGFBQWEsQ0FBQztZQUNqRSxvQkFBb0IsQ0FBQyxnQkFBZ0IsR0FBRyxZQUFZLEVBQUUsZ0JBQWdCLENBQUM7WUFDdkUsb0JBQW9CLENBQUMsWUFBWSxHQUFHLFlBQVksRUFBRSxZQUFZLENBQUM7UUFDakUsQ0FBQzthQUFNLElBQUksWUFBWSxFQUFFLEtBQUssS0FBSyxpQkFBaUIsRUFBRSxDQUFDO1lBQ3JELE1BQU0sZ0JBQWdCLEdBQXlCO2dCQUM3QyxJQUFJLEVBQUUsV0FBVztnQkFDakIsT0FBTyxFQUFFLDZDQUE2QzthQUN2RCxDQUFDO1lBRUYsb0JBQW9CLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQ3JELG9CQUFvQixDQUFDLEtBQUssR0FBRyxpQkFBaUIsQ0FBQztZQUMvQyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO1FBQ3ZDLENBQUM7UUFFRCxPQUFPLG9CQUFvQixDQUFDO0lBQzlCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsc0NBQXNDLENBQUMsQ0FBQztJQUN6RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFF1ZXJ5Q2FsZW5kYXJFeHRyYWN0ZWRKU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9RdWVyeUNhbGVuZGFyRXh0cmFjdGVkRGF0ZUpTT05UeXBlJztcbmltcG9ydCBVc2VySW5wdXRUb0pTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1VzZXJJbnB1dFRvSlNPTlR5cGUnO1xuaW1wb3J0IHsgUXVlcnlDYWxlbmRhckV4dHJhY3RlZEF0dHJpYnV0ZXNUeXBlIH0gZnJvbSAnLi4vdHlwZXMnO1xuaW1wb3J0IHtcbiAgc2VhcmNoU2luZ2xlRXZlbnRCeVZlY3RvcldpdGhEYXRlc0xhbmNlRGIsXG4gIGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IsXG4gIGV4dHJhY3RBdHRyaWJ1dGVzTmVlZGVkRnJvbVVzZXJJbnB1dCxcbiAgZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhLFxuICBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5LFxuICBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VUb1JlcXVlc3RVc2VyRm9yTWlzc2luZ0ZpZWxkcyxcbiAgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dCxcbiAgZ2VuZXJhdGVNaXNzaW5nRmllbGRzUXVlcnlEYXRlRnJvbVVzZXJJbnB1dCxcbiAgZ2VuZXJhdGVRdWVyeURhdGVGcm9tVXNlcklucHV0LFxufSBmcm9tICdAY2hhdC9fbGlicy9hcGktaGVscGVyJzsgLy8gVXBkYXRlZCBpbXBvcnRcbmltcG9ydCB7IFF1ZXJ5TmV4dEV2ZW50VHlwZSB9IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9kYXRlLXV0aWxzJztcbmltcG9ydCB7IEV2ZW50U2NoZW1hIGFzIExhbmNlRGJFdmVudFNjaGVtYSB9IGZyb20gJ0BmdW5jdGlvbnMvX3V0aWxzL2xhbmNlZGJfc2VydmljZSc7IC8vIEFkZGVkIGltcG9ydFxuaW1wb3J0IHsgbGlzdFNvcnRlZE9iamVjdHNGb3JVc2VyR2l2ZW5EYXRlc0FuZEF0dHJpYnV0ZXMgfSBmcm9tICdAY2hhdC9fbGlicy9za2lsbHMvYXNrQ2FsZW5kYXIvYXBpLWhlbHBlcic7XG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnO1xuaW1wb3J0IHtcbiAgQXNzaXN0YW50TWVzc2FnZVR5cGUsXG4gIFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9NZXNzYWdpbmcvTWVzc2FnaW5nVHlwZXMnO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IFJlc3BvbnNlQWN0aW9uVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXNwb25zZUFjdGlvblR5cGUnO1xuaW1wb3J0IFJlcXVpcmVkRmllbGRzVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXF1aXJlZEZpZWxkc1R5cGUnO1xuLy8gUmVtb3ZlZDogaW1wb3J0IHsgT3BlblNlYXJjaFJlc3BvbnNlQm9keVR5cGUgfSBmcm9tIFwiQGNoYXQvX2xpYnMvdHlwZXMvT3BlblNlYXJjaFJlc3BvbnNlVHlwZVwiXG5pbXBvcnQgeyBFdmVudFR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IHsgQ29uZmVyZW5jZVR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Db25mZXJlbmNlVHlwZSc7XG5pbXBvcnQgeyBBdHRlbmRlZVR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9BdHRlbmRlZVR5cGUnO1xuaW1wb3J0IHsgVGFza1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9UYXNrVHlwZSc7XG5cbmV4cG9ydCBjb25zdCBmaW5hbFN0ZXBRdWVyeU5leHRFdmVudCA9IGFzeW5jIChcbiAgYm9keTogUXVlcnlOZXh0RXZlbnRUeXBlLFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICByZXNwb25zZTogYW55XG4pID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgc2VhcmNoVmVjdG9yOiBudW1iZXJbXSA9IFtdO1xuXG4gICAgaWYgKGJvZHk/LnRpdGxlKSB7XG4gICAgICBzZWFyY2hWZWN0b3IgPSBhd2FpdCBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yKGJvZHk/LnRpdGxlKTtcbiAgICB9XG5cbiAgICBsZXQgc2VhcmNoUmVzdWx0OiBMYW5jZURiRXZlbnRTY2hlbWEgfCBudWxsID0gbnVsbDsgLy8gVXBkYXRlZCB0eXBlXG4gICAgbGV0IGV2ZW50SWQ6IHN0cmluZyA9ICcnO1xuXG4gICAgaWYgKHNlYXJjaFZlY3Rvcj8ubGVuZ3RoID4gMCkge1xuICAgICAgc2VhcmNoUmVzdWx0ID0gYXdhaXQgc2VhcmNoU2luZ2xlRXZlbnRCeVZlY3RvcldpdGhEYXRlc0xhbmNlRGIoXG4gICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgc2VhcmNoVmVjdG9yLFxuICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICAgIHdpbmRvd0VuZERhdGVcbiAgICAgICk7IC8vIFVwZGF0ZWQgY2FsbFxuICAgICAgZXZlbnRJZCA9IHNlYXJjaFJlc3VsdD8uaWQ7IC8vIFVwZGF0ZWQgSUQgZXh0cmFjdGlvblxuICAgIH1cblxuICAgIGxldCBvYmplY3RzV2l0aEF0dHJpYnV0ZXM6IHtcbiAgICAgIGV2ZW50czogRXZlbnRUeXBlW107XG4gICAgICBjb25mZXJlbmNlczogQ29uZmVyZW5jZVR5cGVbXTtcbiAgICAgIGF0dGVuZGVlczogQXR0ZW5kZWVUeXBlW107XG4gICAgICB0YXNrczogVGFza1R5cGVbXTtcbiAgICAgIGNvdW50OiBudW1iZXI7XG4gICAgfTtcblxuICAgIGlmIChldmVudElkKSB7XG4gICAgICBvYmplY3RzV2l0aEF0dHJpYnV0ZXMgPVxuICAgICAgICBhd2FpdCBsaXN0U29ydGVkT2JqZWN0c0ZvclVzZXJHaXZlbkRhdGVzQW5kQXR0cmlidXRlcyhcbiAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgYm9keT8ud2luZG93U3RhcnREYXRlLFxuICAgICAgICAgIGJvZHk/LndpbmRvd0VuZERhdGUsXG4gICAgICAgICAgYm9keT8uYXR0cmlidXRlcyxcbiAgICAgICAgICBib2R5Py5pc01lZXRpbmcsXG4gICAgICAgICAgW2V2ZW50SWRdXG4gICAgICAgICk7XG4gICAgfSBlbHNlIHtcbiAgICAgIG9iamVjdHNXaXRoQXR0cmlidXRlcyA9XG4gICAgICAgIGF3YWl0IGxpc3RTb3J0ZWRPYmplY3RzRm9yVXNlckdpdmVuRGF0ZXNBbmRBdHRyaWJ1dGVzKFxuICAgICAgICAgIGJvZHk/LnVzZXJJZCxcbiAgICAgICAgICBib2R5Py53aW5kb3dTdGFydERhdGUsXG4gICAgICAgICAgYm9keT8ud2luZG93RW5kRGF0ZSxcbiAgICAgICAgICBib2R5Py5hdHRyaWJ1dGVzLFxuICAgICAgICAgIGJvZHk/LmlzTWVldGluZ1xuICAgICAgICApO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50cyA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8uZXZlbnRzO1xuICAgIGNvbnN0IGNvbmZlcmVuY2VzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy5jb25mZXJlbmNlcztcbiAgICBjb25zdCBhdHRlbmRlZXMgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmF0dGVuZGVlcztcbiAgICBjb25zdCB0YXNrcyA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8udGFza3M7XG4gICAgLy8gY29uc3QgY291bnQgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmNvdW50XG5cbiAgICAvLyB2YWxpZGF0ZSBmb3VuZCBldmVudFxuICAgIGlmICghKGV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgbGV0IHF1ZXJ5RGF0YSA9ICcnO1xuXG4gICAgLy8gdW5pcSBkYXRlc1xuICAgIGNvbnN0IHVuaXFEYXRlcyA9IF8udW5pcUJ5KGV2ZW50cywgKGN1cnIpID0+XG4gICAgICBkYXlqcyhjdXJyPy5zdGFydERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICk/Lm1hcCgoZSkgPT4gZT8uc3RhcnREYXRlKTtcblxuICAgIGZvciAoY29uc3QgdW5pcURhdGUgb2YgdW5pcURhdGVzKSB7XG4gICAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV2ZW50cz8uZmlsdGVyKFxuICAgICAgICAoYSkgPT5cbiAgICAgICAgICBkYXlqcyhhPy5zdGFydERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ1lZWVktTU0tREQnKSA9PT1cbiAgICAgICAgICBkYXlqcyh1bmlxRGF0ZSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICApO1xuXG4gICAgICBxdWVyeURhdGEgKz0gYCR7ZGF5anModW5pcURhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ2RkZCwgWVlZWS1NTS1ERCcpfWA7XG4gICAgICBxdWVyeURhdGEgKz0gJ1xcbic7XG5cbiAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnbm9uZScpKSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgZm9yIChjb25zdCBldmVudCBvZiBmaWx0ZXJlZEV2ZW50cykge1xuICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnRXZlbnQgLSAnO1xuXG4gICAgICAgICAgcXVlcnlEYXRhICs9IGB0aXRsZTogJHtldmVudD8udGl0bGUgfHwgZXZlbnQ/LnN1bW1hcnl9LCBgO1xuICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgdGltZTogJHtkYXlqcyhldmVudD8uc3RhcnREYXRlKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdMVCcpfSBgO1xuICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgLSAke2RheWpzKGV2ZW50Py5lbmREYXRlKS50eih0aW1lem9uZSwgdHJ1ZSkuZm9ybWF0KCdMVCcpfSwgYDtcblxuICAgICAgICAgIGlmIChldmVudD8uY29uZmVyZW5jZUlkKSB7XG4gICAgICAgICAgICBjb25zdCBmaWx0ZXJlZENvbmYgPSBjb25mZXJlbmNlcz8uZmluZChcbiAgICAgICAgICAgICAgKGMpID0+IGM/LmlkID09PSBldmVudD8uY29uZmVyZW5jZUlkXG4gICAgICAgICAgICApO1xuXG4gICAgICAgICAgICBpZiAoZmlsdGVyZWRDb25mPy5pZCkge1xuICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gJyBjb25mZXJlbmNlIHdpdGggZXZlbnQgLSAnO1xuICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYG5hbWU6ICR7ZmlsdGVyZWRDb25mPy5uYW1lfSwgYDtcbiAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBhcHA6ICR7ZmlsdGVyZWRDb25mPy5hcHB9LCBgO1xuXG4gICAgICAgICAgICAgIGZvciAoY29uc3QgcHJvcGVydHkgaW4gZmlsdGVyZWRDb25mKSB7XG4gICAgICAgICAgICAgICAgaWYgKHByb3BlcnR5ID09PSAnbm90ZXMnKSB7XG4gICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2NvbmZlcmVuY2Utbm90ZXMnKSkge1xuICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2ZpbHRlcmVkQ29uZltwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdqb2luVXJsJykge1xuICAgICAgICAgICAgICAgICAgaWYgKFxuICAgICAgICAgICAgICAgICAgICBib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnY29uZmVyZW5jZS1qb2luVXJsJylcbiAgICAgICAgICAgICAgICAgICkge1xuICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2ZpbHRlcmVkQ29uZltwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzdGFydFVybCcpIHtcbiAgICAgICAgICAgICAgICAgIGlmIChcbiAgICAgICAgICAgICAgICAgICAgYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2NvbmZlcmVuY2Utc3RhcnRVcmwnKVxuICAgICAgICAgICAgICAgICAgKSB7XG4gICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZmlsdGVyZWRDb25mW3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgaWYgKGF0dGVuZGVlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnYXR0ZW5kZWVzIC0gJztcblxuICAgICAgICAgICAgICAgIGZvciAoY29uc3QgYXR0ZW5kZWUgb2YgYXR0ZW5kZWVzKSB7XG4gICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYG5hbWU6ICR7YXR0ZW5kZWU/Lm5hbWV9LCBgO1xuICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBlbWFpbDogJHthdHRlbmRlZT8uZW1haWxzPy5maW5kKChlKSA9PiAhIWU/LnByaW1hcnkpPy52YWx1ZX0sIGA7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKGV2ZW50Py50YXNrSWQpIHtcbiAgICAgICAgICAgIGNvbnN0IGZpbHRlcmVkVGFzayA9IHRhc2tzPy5maW5kKCh0KSA9PiB0Py5pZCA9PT0gZXZlbnQ/LnRhc2tJZCk7XG5cbiAgICAgICAgICAgIGlmIChmaWx0ZXJlZFRhc2s/LmlkKSB7XG4gICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnIHRhc2sgd2l0aCBldmVudCAtICc7XG4gICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtmaWx0ZXJlZFRhc2s/Lm5vdGVzfSwgYDtcblxuICAgICAgICAgICAgICBmb3IgKGNvbnN0IHByb3BlcnR5IGluIGZpbHRlcmVkVGFzaykge1xuICAgICAgICAgICAgICAgIGlmIChwcm9wZXJ0eSA9PT0gJ3R5cGUnKSB7XG4gICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ3Rhc2stbGlzdE5hbWUnKSkge1xuICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGxpc3Q6ICR7ZmlsdGVyZWRUYXNrW3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3N0YXR1cycpIHtcbiAgICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAndGFzay1zdGF0dXMnKSkge1xuICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYHN0YXR1czogJHtmaWx0ZXJlZFRhc2tbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG5cbiAgICAgICAgICBxdWVyeURhdGEgKz0gJ1xcbic7XG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgcXVlcnlEYXRhICs9ICdcXG5cXG4nO1xuICAgIH1cblxuICAgIC8vIHN1Y2Nlc3MgcmVzcG9uc2VcbiAgICByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuXG4gICAgcmVzcG9uc2UuZGF0YSA9IHF1ZXJ5RGF0YTtcblxuICAgIHJldHVybiByZXNwb25zZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGZpbmFsIHN0ZXAgcXVlcnkgbmV4dCBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcHJvY2Vzc1F1ZXJ5TmV4dEV2ZW50UGVuZGluZyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICAvLyBkYXRlVGltZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBhdHRyaWJ1dGVzT2JqZWN0OiBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkQXR0cmlidXRlc1R5cGUsXG4gIHF1ZXJ5RGF0ZUpTT05Cb2R5OiBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmdcbik6IFByb21pc2U8UmVzcG9uc2VBY3Rpb25UeXBlPiA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IHdpbmRvd1N0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy55ZWFyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/Lm1vbnRoLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LmRheSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5ob3VyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/Lm1pbnV0ZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy50aW1lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBsZXQgd2luZG93RW5kRGF0ZSA9IGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnllYXIsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/Lm1vbnRoLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5kYXksXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LmhvdXIsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/Lm1pbnV0ZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8udGltZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBpZiAoIXdpbmRvd1N0YXJ0RGF0ZSkge1xuICAgICAgd2luZG93U3RhcnREYXRlID0gZGF5anMoKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIXdpbmRvd0VuZERhdGUpIHtcbiAgICAgIHdpbmRvd0VuZERhdGUgPSBkYXlqcygpLmFkZCgxLCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IGJvZHk6IFF1ZXJ5TmV4dEV2ZW50VHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIGlzTWVldGluZzogYXR0cmlidXRlc09iamVjdD8uaXNNZWV0aW5nLFxuICAgICAgYXR0cmlidXRlczogYXR0cmlidXRlc09iamVjdD8uYXR0cmlidXRlcyxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlOiBhbnkgPSB7XG4gICAgICBxdWVyeTogJycsXG4gICAgICBkYXRhOiB7fSxcbiAgICAgIHNraWxsOiAncXVlcnlOZXh0RXZlbnQnLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBRdWVyeU5leHRFdmVudChcbiAgICAgIGJvZHksXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgICAgdGltZXpvbmUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuXG4gICAgLy8gbGV0IHNlYXJjaFZlY3RvcjogbnVtYmVyW10gPSBbXVxuXG4gICAgLy8gaWYgKGJvZHk/LnRpdGxlKSB7XG4gICAgLy8gICAgIHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpXG4gICAgLy8gfVxuXG4gICAgLy8gbGV0IGV2ZW50SWQ6IHN0cmluZyA9ICcnXG5cbiAgICAvLyBpZiAoc2VhcmNoVmVjdG9yPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaCh1c2VySWQsIHNlYXJjaFZlY3Rvciwgd2luZG93U3RhcnREYXRlLCB3aW5kb3dFbmREYXRlKVxuXG4gICAgLy8gICAgIGV2ZW50SWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkXG4gICAgLy8gfVxuXG4gICAgLy8gY29uc3Qgb2JqZWN0c1dpdGhBdHRyaWJ1dGVzID0gYXdhaXQgbGlzdFNvcnRlZE9iamVjdHNGb3JVc2VyR2l2ZW5EYXRlc0FuZEF0dHJpYnV0ZXMoXG4gICAgLy8gICAgIGJvZHk/LnVzZXJJZCxcbiAgICAvLyAgICAgYm9keT8ud2luZG93U3RhcnREYXRlLFxuICAgIC8vICAgICBib2R5Py53aW5kb3dFbmREYXRlLFxuICAgIC8vICAgICBib2R5Py5hdHRyaWJ1dGVzLFxuICAgIC8vICAgICBib2R5Py5pc01lZXRpbmcsXG4gICAgLy8gICAgIGV2ZW50SWQ/Lmxlbmd0aCA+IDAgPyBbZXZlbnRJZF0gOiBbXSxcbiAgICAvLyApXG5cbiAgICAvLyBjb25zdCBldmVudHMgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmV2ZW50c1xuICAgIC8vIGNvbnN0IGNvbmZlcmVuY2VzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy5jb25mZXJlbmNlc1xuICAgIC8vIGNvbnN0IGF0dGVuZGVlcyA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8uYXR0ZW5kZWVzXG4gICAgLy8gY29uc3QgdGFza3MgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LnRhc2tzXG4gICAgLy8gLy8gY29uc3QgY291bnQgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmNvdW50XG5cbiAgICAvLyBsZXQgcXVlcnlEYXRhID0gJydcblxuICAgIC8vIC8vIHVuaXEgZGF0ZXNcbiAgICAvLyBjb25zdCB1bmlxRGF0ZXMgPSBfLnVuaXFCeShldmVudHMsIChjdXJyKSA9PiAoZGF5anMoY3Vycj8uc3RhcnREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCdZWVlZLU1NLUREJykpKT8ubWFwKGUgPT4gZT8uc3RhcnREYXRlKVxuXG4gICAgLy8gZm9yIChjb25zdCB1bmlxRGF0ZSBvZiB1bmlxRGF0ZXMpIHtcblxuICAgIC8vICAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV2ZW50cz8uZmlsdGVyKGEgPT4gKGRheWpzKGE/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpID09PSBkYXlqcyh1bmlxRGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpKSlcblxuICAgIC8vICAgICBxdWVyeURhdGEgKz0gYCR7ZGF5anModW5pcURhdGUpLmZvcm1hdCgnZGRkLCBZWVlZLU1NLUREJyl9YFxuICAgIC8vICAgICBxdWVyeURhdGEgKz0gJ1xcbidcblxuICAgIC8vICAgICBmb3IgKGNvbnN0IGV2ZW50IG9mIGZpbHRlcmVkRXZlbnRzKSB7XG5cbiAgICAvLyAgICAgICAgIHF1ZXJ5RGF0YSArPSAnRXZlbnQgLSAnXG5cbiAgICAvLyAgICAgICAgIHF1ZXJ5RGF0YSArPSBgdGl0bGU6ICR7ZXZlbnQ/LnRpdGxlIHx8IGV2ZW50Py5zdW1tYXJ5fSwgYFxuICAgIC8vICAgICAgICAgcXVlcnlEYXRhICs9IGB0aW1lOiAke2RheWpzKGV2ZW50Py5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9IGBcbiAgICAvLyAgICAgICAgIHF1ZXJ5RGF0YSArPSBgLSAke2RheWpzKGV2ZW50Py5lbmREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCdMVCcpfSwgYFxuXG4gICAgLy8gICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnbm9uZScpKSkge1xuICAgIC8vICAgICAgICAgICAgIGNvbnRpbnVlXG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIGNvbnN0IGZpbHRlcmVkQ29uZiA9IGNvbmZlcmVuY2VzPy5maW5kKGMgPT4gKGM/LmlkID09PSBldmVudD8uY29uZmVyZW5jZUlkKSlcblxuICAgIC8vICAgICAgICAgaWYgKGZpbHRlcmVkQ29uZj8uaWQpIHtcbiAgICAvLyAgICAgICAgICAgICBxdWVyeURhdGEgKz0gJyBjb25mZXJlbmNlIHdpdGggZXZlbnQgLSAnXG4gICAgLy8gICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBuYW1lOiAke2ZpbHRlcmVkQ29uZj8ubmFtZX0sIGBcbiAgICAvLyAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGFwcDogJHtmaWx0ZXJlZENvbmY/LmFwcH0sIGBcblxuICAgIC8vICAgICAgICAgICAgIGZvciAoY29uc3QgcHJvcGVydHkgaW4gZmlsdGVyZWRDb25mKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChwcm9wZXJ0eSA9PT0gJ25vdGVzJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnY29uZmVyZW5jZS1ub3RlcycpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZmlsdGVyZWRDb25mW3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2pvaW5VcmwnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdjb25mZXJlbmNlLWpvaW5VcmwnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2ZpbHRlcmVkQ29uZltwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzdGFydFVybCcpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2NvbmZlcmVuY2Utc3RhcnRVcmwnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2ZpbHRlcmVkQ29uZltwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgICAgICBpZiAoYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnYXR0ZW5kZWVzIC0gJ1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGZvciAoY29uc3QgYXR0ZW5kZWUgb2YgYXR0ZW5kZWVzKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYG5hbWU6ICR7YXR0ZW5kZWU/Lm5hbWV9LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGVtYWlsOiAke2F0dGVuZGVlPy5lbWFpbHM/LmZpbmQoZSA9PiAoISFlPy5wcmltYXJ5KSk/LnZhbHVlfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICBjb25zdCBmaWx0ZXJlZFRhc2sgPSB0YXNrcz8uZmluZCh0ID0+ICh0Py5pZCA9PT0gZXZlbnQ/LnRhc2tJZCkpXG5cbiAgICAvLyAgICAgICAgIGlmIChmaWx0ZXJlZFRhc2s/LmlkKSB7XG4gICAgLy8gICAgICAgICAgICAgcXVlcnlEYXRhICs9ICcgdGFzayB3aXRoIGV2ZW50IC0gJ1xuICAgIC8vICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtmaWx0ZXJlZFRhc2s/Lm5vdGVzfSwgYFxuXG4gICAgLy8gICAgICAgICAgICAgZm9yIChjb25zdCBwcm9wZXJ0eSBpbiBmaWx0ZXJlZFRhc2spIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKHByb3BlcnR5ID09PSAndHlwZScpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ3Rhc2stbGlzdE5hbWUnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGxpc3Q6ICR7ZmlsdGVyZWRUYXNrW3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3N0YXR1cycpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ3Rhc2stc3RhdHVzJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBzdGF0dXM6ICR7ZmlsdGVyZWRUYXNrW3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgcXVlcnlEYXRhICs9ICdcXG4nXG4gICAgLy8gICAgIH1cblxuICAgIC8vICAgICBxdWVyeURhdGEgKz0gJ1xcblxcbidcbiAgICAvLyB9XG5cbiAgICAvLyAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgLy8gcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJ1xuXG4gICAgLy8gcmVzcG9uc2UuZGF0YSA9IHF1ZXJ5RGF0YVxuXG4gICAgLy8gcmV0dXJuIHJlc3BvbnNlXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIHF1ZXJ5IG5leHQgZXZlbnQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NRdWVyeU5leHRFdmVudE1pc3NpbmdGaWVsZHNSZXR1cm5lZCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICAvLyBkYXRlVGltZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBhdHRyaWJ1dGVzT2JqZWN0OiBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkQXR0cmlidXRlc1R5cGUsXG4gIHF1ZXJ5RGF0ZUpTT05Cb2R5OiBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IHdpbmRvd1N0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy55ZWFyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/Lm1vbnRoLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LmRheSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5ob3VyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/Lm1pbnV0ZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy50aW1lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBsZXQgd2luZG93RW5kRGF0ZSA9IGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnllYXIsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/Lm1vbnRoLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5kYXksXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LmhvdXIsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/Lm1pbnV0ZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8udGltZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBpZiAoIXdpbmRvd1N0YXJ0RGF0ZSkge1xuICAgICAgd2luZG93U3RhcnREYXRlID0gZGF5anMoKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIXdpbmRvd0VuZERhdGUpIHtcbiAgICAgIHdpbmRvd0VuZERhdGUgPSBkYXlqcygpLmFkZCgxLCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IG5ld0JvZHk6IFF1ZXJ5TmV4dEV2ZW50VHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIGlzTWVldGluZzogYXR0cmlidXRlc09iamVjdD8uaXNNZWV0aW5nLFxuICAgICAgYXR0cmlidXRlczogYXR0cmlidXRlc09iamVjdD8uYXR0cmlidXRlcyxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgfTtcblxuICAgIGNvbnN0IHByZXZCb2R5OiBRdWVyeU5leHRFdmVudFR5cGUgPSB7XG4gICAgICAuLi5tZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGEsXG4gICAgICB3aW5kb3dTdGFydERhdGU6IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy53aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlOiBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGFFeHRyYT8ud2luZG93RW5kRGF0ZSxcbiAgICB9O1xuXG4gICAgLy8gZml4IHByZXZCb2R5IHdpdGggbmV3IGRhdGFcbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKHByZXZCb2R5Py5pc01lZXRpbmcgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuaXNNZWV0aW5nID0gbmV3Qm9keT8uaXNNZWV0aW5nO1xuICAgIH1cblxuICAgIGlmICghKHByZXZCb2R5Py5hdHRyaWJ1dGVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkuYXR0cmlidXRlcyA9IG5ld0JvZHk/LmF0dHJpYnV0ZXM7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ud2luZG93U3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS53aW5kb3dTdGFydERhdGUgPSBuZXdCb2R5Py53aW5kb3dTdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ud2luZG93RW5kRGF0ZSkge1xuICAgICAgcHJldkJvZHkud2luZG93RW5kRGF0ZSA9IG5ld0JvZHk/LndpbmRvd0VuZERhdGU7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdxdWVyeU5leHRFdmVudCcsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcFF1ZXJ5TmV4dEV2ZW50KFxuICAgICAgcHJldkJvZHksXG4gICAgICBwcmV2Qm9keT8ud2luZG93U3RhcnREYXRlLFxuICAgICAgcHJldkJvZHk/LndpbmRvd0VuZERhdGUsXG4gICAgICBwcmV2Qm9keT8udGltZXpvbmUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBxdWVyeSBldmVudCBtaXNzaW5nIGZpZWxkcyByZXR1cm5lZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbmV4dEV2ZW50Q29udHJvbENlbnRlciA9IGFzeW5jIChcbiAgb3BlbmFpOiBPcGVuQUksXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGUsXG4gIHVzZXJDdXJyZW50VGltZTogc3RyaW5nLFxuICBxdWVyeTogJ21pc3NpbmdfZmllbGRzJyB8ICdjb21wbGV0ZWQnIHwgJ2V2ZW50X25vdF9mb3VuZCcgfCAncGVuZGluZydcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG1lc3NhZ2VMZW5ndGggPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcz8ubGVuZ3RoO1xuICAgIGxldCB1c2VyTWVzc2FnZSA9ICcnO1xuICAgIGZvciAobGV0IGkgPSBtZXNzYWdlTGVuZ3RoOyBpID4gMDsgaS0tKSB7XG4gICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgdXNlck1lc3NhZ2UgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH1cbiAgICBjb25zdCB1c2VySW5wdXQgPSB1c2VyTWVzc2FnZTtcblxuICAgIGNvbnN0IGF0dHJpYnV0ZXNPYmplY3QgPVxuICAgICAgYXdhaXQgZXh0cmFjdEF0dHJpYnV0ZXNOZWVkZWRGcm9tVXNlcklucHV0KHVzZXJJbnB1dCk7XG5cbiAgICBsZXQgbmV4dEV2ZW50UmVzOiBSZXNwb25zZUFjdGlvblR5cGUgPSB7XG4gICAgICBxdWVyeTogJ2NvbXBsZXRlZCcsXG4gICAgICBkYXRhOiAnJyxcbiAgICAgIHNraWxsOiAnJyxcbiAgICAgIHByZXZEYXRhOiB7fSxcbiAgICAgIHByZXZEYXRhRXh0cmE6IHt9LFxuICAgIH07XG5cbiAgICBzd2l0Y2ggKHF1ZXJ5KSB7XG4gICAgICBjYXNlICdwZW5kaW5nJzpcbiAgICAgICAgY29uc3QganNvbkJvZHkgPSBhd2FpdCBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZSA9IGF3YWl0IGdlbmVyYXRlUXVlcnlEYXRlRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBuZXh0RXZlbnRSZXMgPSBhd2FpdCBwcm9jZXNzUXVlcnlOZXh0RXZlbnRQZW5kaW5nKFxuICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICBqc29uQm9keSxcbiAgICAgICAgICBhdHRyaWJ1dGVzT2JqZWN0LFxuICAgICAgICAgIHF1ZXJ5RGF0ZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdtaXNzaW5nX2ZpZWxkcyc6XG4gICAgICAgIGxldCBwcmlvclVzZXJJbnB1dCA9ICcnO1xuICAgICAgICBsZXQgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSAnJztcblxuICAgICAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlc1tpIC0gMV07XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAnYXNzaXN0YW50Jykge1xuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBpZiAobWVzc2FnZS5yb2xlID09PSAndXNlcicpIHtcbiAgICAgICAgICAgIGlmIChtZXNzYWdlLmNvbnRlbnQgIT09IHVzZXJJbnB1dCkge1xuICAgICAgICAgICAgICBwcmlvclVzZXJJbnB1dCA9IG1lc3NhZ2UuY29udGVudDtcbiAgICAgICAgICAgICAgYnJlYWs7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKCFwcmlvclVzZXJJbnB1dCB8fCAhcHJpb3JBc3Npc3RhbnRPdXRwdXQpIHtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvclVzZXJJbnB1dCwgJyBwcmlvclVzZXJJbnB1dCcpO1xuICAgICAgICAgIGNvbnNvbGUubG9nKHByaW9yQXNzaXN0YW50T3V0cHV0LCAnIHByaW9yQXNzaXN0YW50T3V0cHV0Jyk7XG4gICAgICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBwcmlvclVzZXJpbnB1dCBvciBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICB9XG4gICAgICAgIGNvbnN0IGpzb25NaXNzaW5nRmllbGRzQm9keSA9XG4gICAgICAgICAgYXdhaXQgZ2VuZXJhdGVNaXNzaW5nRmllbGRzSlNPTkRhdGFGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvckFzc2lzdGFudE91dHB1dCxcbiAgICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICAgICk7XG4gICAgICAgIGNvbnN0IHF1ZXJ5TWlzc2luZ0ZpZWxkc0RhdGUgPVxuICAgICAgICAgIGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc1F1ZXJ5RGF0ZUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICB0aW1lem9uZSxcbiAgICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgICApO1xuXG4gICAgICAgIG5leHRFdmVudFJlcyA9IGF3YWl0IHByb2Nlc3NRdWVyeU5leHRFdmVudE1pc3NpbmdGaWVsZHNSZXR1cm5lZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbk1pc3NpbmdGaWVsZHNCb2R5LFxuICAgICAgICAgIGF0dHJpYnV0ZXNPYmplY3QsXG4gICAgICAgICAgcXVlcnlNaXNzaW5nRmllbGRzRGF0ZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgfVxuXG4gICAgaWYgKG5leHRFdmVudFJlcz8ucXVlcnkgPT09ICdjb21wbGV0ZWQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlRnJvbUFQSVJlc3BvbnNlRm9yVXNlclF1ZXJ5KFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBuZXh0RXZlbnRSZXMuZGF0YSBhcyBzdHJpbmcsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfSBlbHNlIGlmIChuZXh0RXZlbnRSZXM/LnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIG5leHRFdmVudFJlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ21pc3NpbmdfZmllbGRzJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbmV4dEV2ZW50UmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhID0gbmV4dEV2ZW50UmVzPy5wcmV2RGF0YTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhRXh0cmEgPSBuZXh0RXZlbnRSZXM/LnByZXZEYXRhRXh0cmE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0ZUpzb25Cb2R5ID0gbmV4dEV2ZW50UmVzPy5wcmV2RGF0ZUpzb25Cb2R5O1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkpzb25Cb2R5ID0gbmV4dEV2ZW50UmVzPy5wcmV2SnNvbkJvZHk7XG4gICAgfSBlbHNlIGlmIChuZXh0RXZlbnRSZXM/LnF1ZXJ5ID09PSAnZXZlbnRfbm90X2ZvdW5kJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZTogQXNzaXN0YW50TWVzc2FnZVR5cGUgPSB7XG4gICAgICAgIHJvbGU6ICdhc3Npc3RhbnQnLFxuICAgICAgICBjb250ZW50OiBcIk9vcHMuLi4gSSBjb3VsZG4ndCBmaW5kIHRoZSBldmVudC4gU29ycnkgOihcIixcbiAgICAgIH07XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdldmVudF9ub3RfZm91bmQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH1cblxuICAgIHJldHVybiBtZXNzYWdlSGlzdG9yeU9iamVjdDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIG5leHQgZXZlbnQgY29udHJvbCBjZW50ZXInKTtcbiAgfVxufTtcbiJdfQ==