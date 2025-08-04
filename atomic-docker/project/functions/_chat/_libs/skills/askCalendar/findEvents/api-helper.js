import { searchMultipleEventsByVectorWithDatesLanceDb, convertEventTitleToOpenAIVector, extractAttributesNeededFromUserInput, extrapolateEndDateFromJSONData, extrapolateStartDateFromJSONData, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateJSONDataFromUserInput, generateMissingFieldsJSONDataFromUserInput, generateMissingFieldsQueryDateFromUserInput, generateQueryDateFromUserInput, } from '@chat/_libs/api-helper'; // Updated import
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { listSortedObjectsForUserGivenDatesAndAttributes } from '@chat/_libs/skills/askCalendar/api-helper';
import _ from 'lodash';
export const finalStepQueryEvents = async (body, windowStartDate, windowEndDate, timezone, response) => {
    try {
        let searchVector = [];
        if (body?.title) {
            searchVector = await convertEventTitleToOpenAIVector(body?.title);
        }
        const eventIds = [];
        if (searchVector?.length > 0) {
            const searchResults = await searchMultipleEventsByVectorWithDatesLanceDb(body?.userId, searchVector, windowStartDate, windowEndDate); // Updated call
            for (const event of searchResults) {
                // Iterate over LanceDbEventSchema[]
                if (event?.id) {
                    eventIds.push(event.id); // Use event.id
                }
            }
        }
        let objectsWithAttributes;
        if (eventIds?.length > 0) {
            objectsWithAttributes =
                await listSortedObjectsForUserGivenDatesAndAttributes(body?.userId, body?.windowStartDate, body?.windowEndDate, body?.attributes, body?.isMeeting, eventIds);
        }
        else {
            objectsWithAttributes =
                await listSortedObjectsForUserGivenDatesAndAttributes(body?.userId, body?.windowStartDate, body?.windowEndDate, body?.attributes, body?.isMeeting);
        }
        const events = objectsWithAttributes?.events;
        const conferences = objectsWithAttributes?.conferences;
        const attendees = objectsWithAttributes?.attendees;
        const tasks = objectsWithAttributes?.tasks;
        const count = objectsWithAttributes?.count;
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
            for (const event of filteredEvents) {
                queryData += 'Event - ';
                queryData += `title: ${event?.title || event?.summary}, `;
                queryData += `time: ${dayjs(event?.startDate).tz(timezone, true).format('LT')} `;
                queryData += `- ${dayjs(event?.endDate).tz(timezone, true).format('LT')}, `;
                if (body?.attributes?.find((a) => a === 'none')) {
                    continue;
                }
                if (body?.attributes?.find((a) => a === 'all')) {
                    // queryData += `${property}: ${event[property]} `
                    queryData += `id: ${event?.id}, `;
                    continue;
                }
                else {
                    for (const property in event) {
                        if (property === 'allDay') {
                            if (body?.attributes?.find((a) => a === 'allDay')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'title') {
                            // queryData += `${property}: ${event[property]}, `
                            continue;
                        }
                        else if (property === 'startDate') {
                            continue;
                        }
                        else if (property === 'endDate') {
                            continue;
                        }
                        else if (property === 'recurrenceRule') {
                            if (body?.attributes?.find((a) => a === 'recurrenceRule')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'location') {
                            if (body?.attributes?.find((a) => a === 'location')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'notes') {
                            if (body?.attributes?.find((a) => a === 'notes')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'timezone') {
                            continue;
                        }
                        else if (property === 'taskId') {
                            if (body?.attributes?.find((a) => a === 'taskId')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'priority') {
                            if (body?.attributes?.find((a) => a === 'priority')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'isFollowUp') {
                            if (body?.attributes?.find((a) => a === 'isFollowUp')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'isPreEvent') {
                            if (body?.attributes?.find((a) => a === 'isPreEvent')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'isPostEvent') {
                            if (body?.attributes?.find((a) => a === 'isPostEvent')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'modifiable') {
                            if (body?.attributes?.find((a) => a === 'modifiable')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'isBreak') {
                            if (body?.attributes?.find((a) => a === 'isBreak')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'bufferTime') {
                            if (body?.attributes?.find((a) => a === 'bufferTime')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'hardDeadline') {
                            if (body?.attributes?.find((a) => a === 'hardDeadline')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'softDeadline') {
                            if (body?.attributes?.find((a) => a === 'softDeadline')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                        else if (property === 'duration') {
                            if (body?.attributes?.find((a) => a === 'duration')) {
                                queryData += `${property}: ${event[property]}, `;
                            }
                        }
                    }
                }
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
            queryData += '\n\n';
        }
        if (count > 0) {
            queryData += `count: ${count}`;
        }
        // success response
        response.query = 'completed';
        response.data = queryData;
        return response;
    }
    catch (e) {
        console.log(e, ' unable to final step query events');
    }
};
export const processQueryEventsPending = async (userId, timezone, jsonBody, 
// dateTimeJSONBody: DateTimeJSONType,
attributesObject, queryDateJSONBody, currentTime) => {
    try {
        let windowStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, queryDateJSONBody?.start_date?.year, queryDateJSONBody?.start_date?.month, queryDateJSONBody?.start_date?.day, undefined, queryDateJSONBody?.start_date?.hour, queryDateJSONBody?.start_date?.minute, queryDateJSONBody?.start_date?.time, queryDateJSONBody?.start_date?.relativeTimeChangeFromNow, queryDateJSONBody?.start_date?.relativeTimeFromNow);
        let windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, queryDateJSONBody?.end_date?.year, queryDateJSONBody?.end_date?.month, queryDateJSONBody?.end_date?.day, undefined, queryDateJSONBody?.end_date?.hour, queryDateJSONBody?.end_date?.minute, queryDateJSONBody?.end_date?.time, queryDateJSONBody?.end_date?.relativeTimeChangeFromNow, queryDateJSONBody?.end_date?.relativeTimeFromNow);
        if (!windowStartDate) {
            windowStartDate = dayjs().subtract(2, 'w').format();
        }
        if (!windowEndDate) {
            windowEndDate = dayjs().add(4, 'w').format();
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
            skill: 'find-events',
        };
        const response2 = await finalStepQueryEvents(body, body?.windowStartDate, body?.windowEndDate, body?.timezone, response);
        return response2;
        // let searchVector: number[] = []
        // if (body?.title) {
        //     searchVector = await convertEventTitleToOpenAIVector(body?.title)
        // }
        // const eventIds: string[] = []
        // if (searchVector?.length > 0) {
        //     const res = await allEventsWithDatesOpenSearch(userId, searchVector, windowStartDate, windowEndDate)
        //     for (const hit of res?.hits?.hits) {
        //         if (hit?._id) {
        //             eventIds.push(hit?._id)
        //         }
        //     }
        // }
        // const objectsWithAttributes = await listSortedObjectsForUserGivenDatesAndAttributes(
        //     body?.userId,
        //     body?.windowStartDate,
        //     body?.windowEndDate,
        //     body?.attributes,
        //     body?.isMeeting,
        //     eventIds,
        // )
        // const events = objectsWithAttributes?.events
        // const conferences = objectsWithAttributes?.conferences
        // const attendees = objectsWithAttributes?.attendees
        // const tasks = objectsWithAttributes?.tasks
        // const count = objectsWithAttributes?.count
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
        //         for (const property in event) {
        //             if (body?.attributes?.find(a => (a === 'all'))) {
        //                 // queryData += `${property}: ${event[property]} `
        //                 queryData += `id: ${event?.id}, `
        //                 continue
        //             }
        //             if (property === 'allDay') {
        //                 if (body?.attributes?.find(a => (a === 'allDay'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'title') {
        //                 // queryData += `${property}: ${event[property]}, `
        //                 continue
        //             } else if (property === 'startDate') {
        //                 continue
        //             } else if (property === 'endDate') {
        //                 continue
        //             } else if (property === 'recurrenceRule') {
        //                 if (body?.attributes?.find(a => (a === 'recurrenceRule'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'location') {
        //                 if (body?.attributes?.find(a => (a === 'location'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'notes') {
        //                 if (body?.attributes?.find(a => (a === 'notes'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'timezone') {
        //                 continue
        //             } else if (property === 'taskId') {
        //                 if (body?.attributes?.find(a => (a === 'taskId'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'priority') {
        //                 if (body?.attributes?.find(a => (a === 'priority'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'isFollowUp') {
        //                 if (body?.attributes?.find(a => (a === 'isFollowUp'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'isPreEvent') {
        //                 if (body?.attributes?.find(a => (a === 'isPreEvent'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'isPostEvent') {
        //                 if (body?.attributes?.find(a => (a === 'isPostEvent'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'modifiable') {
        //                 if (body?.attributes?.find(a => (a === 'modifiable'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'isBreak') {
        //                 if (body?.attributes?.find(a => (a === 'isBreak'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'bufferTime') {
        //                 if (body?.attributes?.find(a => (a === 'bufferTime'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'hardDeadline') {
        //                 if (body?.attributes?.find(a => (a === 'hardDeadline'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'softDeadline') {
        //                 if (body?.attributes?.find(a => (a === 'softDeadline'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             } else if (property === 'duration') {
        //                 if (body?.attributes?.find(a => (a === 'duration'))) {
        //                     queryData += `${property}: ${event[property]}, `
        //                 }
        //             }
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
        // if (count > 0) {
        //     queryData += `count: ${count}`
        // }
        // // success response
        // response.query = 'completed'
        // response.data = queryData
        // return response
    }
    catch (e) {
        console.log(e, ' unable to process query events');
    }
};
export const processQueryEventsMissingFieldsReturned = async (userId, timezone, jsonBody, 
// dateTimeJSONBody: DateTimeJSONType,
attributesObject, queryDateJSONBody, currentTime, messageHistoryObject) => {
    try {
        let windowStartDate = extrapolateStartDateFromJSONData(currentTime, timezone, queryDateJSONBody?.start_date?.year, queryDateJSONBody?.start_date?.month, queryDateJSONBody?.start_date?.day, undefined, queryDateJSONBody?.start_date?.hour, queryDateJSONBody?.start_date?.minute, queryDateJSONBody?.start_date?.time, queryDateJSONBody?.start_date?.relativeTimeChangeFromNow, queryDateJSONBody?.start_date?.relativeTimeFromNow);
        let windowEndDate = extrapolateEndDateFromJSONData(currentTime, timezone, queryDateJSONBody?.end_date?.year, queryDateJSONBody?.end_date?.month, queryDateJSONBody?.end_date?.day, undefined, queryDateJSONBody?.end_date?.hour, queryDateJSONBody?.end_date?.minute, queryDateJSONBody?.end_date?.time, queryDateJSONBody?.end_date?.relativeTimeChangeFromNow, queryDateJSONBody?.end_date?.relativeTimeFromNow);
        if (!windowStartDate) {
            windowStartDate = dayjs().subtract(2, 'w').format();
        }
        if (!windowEndDate) {
            windowEndDate = dayjs().add(4, 'w').format();
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
            skill: 'find-events',
        };
        const response2 = await finalStepQueryEvents(prevBody, prevBody?.windowStartDate, prevBody?.windowEndDate, prevBody?.timezone, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to query events missing fields returned');
    }
};
export const queryEventsControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        let eventsRes = {
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
                eventsRes = await processQueryEventsPending(userId, timezone, jsonBody, attributesObject, queryDate, userCurrentTime);
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
                eventsRes = await processQueryEventsMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, attributesObject, queryMissingFieldsDate, userCurrentTime, messageHistoryObject);
                break;
        }
        // const eventsRes = await processQueryEventsPending(userId, timezone, jsonBody, attributesObject, queryDate, userCurrentTime)
        if (eventsRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, eventsRes.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (eventsRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, eventsRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = eventsRes?.data;
            messageHistoryObject.prevData = eventsRes?.prevData;
            messageHistoryObject.prevDataExtra = eventsRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = eventsRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = eventsRes?.prevJsonBody;
        }
        else if (eventsRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to query events');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBR0EsT0FBTyxFQUNMLDRDQUE0QyxFQUM1QywrQkFBK0IsRUFDL0Isb0NBQW9DLEVBQ3BDLDhCQUE4QixFQUM5QixnQ0FBZ0MsRUFDaEMsbURBQW1ELEVBQ25ELHFEQUFxRCxFQUNyRCw2QkFBNkIsRUFDN0IsMENBQTBDLEVBQzFDLDJDQUEyQyxFQUMzQyw4QkFBOEIsR0FDL0IsTUFBTSx3QkFBd0IsQ0FBQyxDQUFDLGlCQUFpQjtBQUVsRCxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFFeEQsT0FBTyxFQUFFLCtDQUErQyxFQUFFLE1BQU0sMkNBQTJDLENBQUM7QUFDNUcsT0FBTyxDQUFDLE1BQU0sUUFBUSxDQUFDO0FBYXZCLE1BQU0sQ0FBQyxNQUFNLG9CQUFvQixHQUFHLEtBQUssRUFDdkMsSUFBcUIsRUFDckIsZUFBdUIsRUFDdkIsYUFBcUIsRUFDckIsUUFBZ0IsRUFDaEIsUUFBYSxFQUNiLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxJQUFJLFlBQVksR0FBYSxFQUFFLENBQUM7UUFFaEMsSUFBSSxJQUFJLEVBQUUsS0FBSyxFQUFFLENBQUM7WUFDaEIsWUFBWSxHQUFHLE1BQU0sK0JBQStCLENBQUMsSUFBSSxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQ3BFLENBQUM7UUFFRCxNQUFNLFFBQVEsR0FBYSxFQUFFLENBQUM7UUFFOUIsSUFBSSxZQUFZLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQzdCLE1BQU0sYUFBYSxHQUFHLE1BQU0sNENBQTRDLENBQ3RFLElBQUksRUFBRSxNQUFNLEVBQ1osWUFBWSxFQUNaLGVBQWUsRUFDZixhQUFhLENBQ2QsQ0FBQyxDQUFDLGVBQWU7WUFFbEIsS0FBSyxNQUFNLEtBQUssSUFBSSxhQUFhLEVBQUUsQ0FBQztnQkFDbEMsb0NBQW9DO2dCQUNwQyxJQUFJLEtBQUssRUFBRSxFQUFFLEVBQUUsQ0FBQztvQkFDZCxRQUFRLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxFQUFFLENBQUMsQ0FBQyxDQUFDLGVBQWU7Z0JBQzFDLENBQUM7WUFDSCxDQUFDO1FBQ0gsQ0FBQztRQUVELElBQUkscUJBTUgsQ0FBQztRQUVGLElBQUksUUFBUSxFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUN6QixxQkFBcUI7Z0JBQ25CLE1BQU0sK0NBQStDLENBQ25ELElBQUksRUFBRSxNQUFNLEVBQ1osSUFBSSxFQUFFLGVBQWUsRUFDckIsSUFBSSxFQUFFLGFBQWEsRUFDbkIsSUFBSSxFQUFFLFVBQVUsRUFDaEIsSUFBSSxFQUFFLFNBQVMsRUFDZixRQUFRLENBQ1QsQ0FBQztRQUNOLENBQUM7YUFBTSxDQUFDO1lBQ04scUJBQXFCO2dCQUNuQixNQUFNLCtDQUErQyxDQUNuRCxJQUFJLEVBQUUsTUFBTSxFQUNaLElBQUksRUFBRSxlQUFlLEVBQ3JCLElBQUksRUFBRSxhQUFhLEVBQ25CLElBQUksRUFBRSxVQUFVLEVBQ2hCLElBQUksRUFBRSxTQUFTLENBQ2hCLENBQUM7UUFDTixDQUFDO1FBRUQsTUFBTSxNQUFNLEdBQUcscUJBQXFCLEVBQUUsTUFBTSxDQUFDO1FBQzdDLE1BQU0sV0FBVyxHQUFHLHFCQUFxQixFQUFFLFdBQVcsQ0FBQztRQUN2RCxNQUFNLFNBQVMsR0FBRyxxQkFBcUIsRUFBRSxTQUFTLENBQUM7UUFDbkQsTUFBTSxLQUFLLEdBQUcscUJBQXFCLEVBQUUsS0FBSyxDQUFDO1FBQzNDLE1BQU0sS0FBSyxHQUFHLHFCQUFxQixFQUFFLEtBQUssQ0FBQztRQUUzQyx1QkFBdUI7UUFDdkIsSUFBSSxDQUFDLENBQUMsTUFBTSxFQUFFLE1BQU0sR0FBRyxDQUFDLENBQUMsRUFBRSxDQUFDO1lBQzFCLFFBQVEsQ0FBQyxLQUFLLEdBQUcsaUJBQWlCLENBQUM7WUFDbkMsT0FBTyxRQUFRLENBQUM7UUFDbEIsQ0FBQztRQUVELElBQUksU0FBUyxHQUFHLEVBQUUsQ0FBQztRQUVuQixhQUFhO1FBQ2IsTUFBTSxTQUFTLEdBQUcsQ0FBQyxDQUFDLE1BQU0sQ0FBQyxNQUFNLEVBQUUsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUMxQyxLQUFLLENBQUMsSUFBSSxFQUFFLFNBQVMsQ0FBQyxDQUFDLEVBQUUsQ0FBQyxRQUFRLEVBQUUsSUFBSSxDQUFDLENBQUMsTUFBTSxDQUFDLFlBQVksQ0FBQyxDQUMvRCxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLFNBQVMsQ0FBQyxDQUFDO1FBRTVCLEtBQUssTUFBTSxRQUFRLElBQUksU0FBUyxFQUFFLENBQUM7WUFDakMsTUFBTSxjQUFjLEdBQUcsTUFBTSxFQUFFLE1BQU0sQ0FDbkMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUNKLEtBQUssQ0FBQyxDQUFDLEVBQUUsU0FBUyxDQUFDLENBQUMsRUFBRSxDQUFDLFFBQVEsRUFBRSxJQUFJLENBQUMsQ0FBQyxNQUFNLENBQUMsWUFBWSxDQUFDO2dCQUMzRCxLQUFLLENBQUMsUUFBUSxDQUFDLENBQUMsRUFBRSxDQUFDLFFBQVEsRUFBRSxJQUFJLENBQUMsQ0FBQyxNQUFNLENBQUMsWUFBWSxDQUFDLENBQzFELENBQUM7WUFFRixTQUFTLElBQUksR0FBRyxLQUFLLENBQUMsUUFBUSxDQUFDLENBQUMsRUFBRSxDQUFDLFFBQVEsRUFBRSxJQUFJLENBQUMsQ0FBQyxNQUFNLENBQUMsaUJBQWlCLENBQUMsRUFBRSxDQUFDO1lBQy9FLFNBQVMsSUFBSSxJQUFJLENBQUM7WUFFbEIsS0FBSyxNQUFNLEtBQUssSUFBSSxjQUFjLEVBQUUsQ0FBQztnQkFDbkMsU0FBUyxJQUFJLFVBQVUsQ0FBQztnQkFFeEIsU0FBUyxJQUFJLFVBQVUsS0FBSyxFQUFFLEtBQUssSUFBSSxLQUFLLEVBQUUsT0FBTyxJQUFJLENBQUM7Z0JBQzFELFNBQVMsSUFBSSxTQUFTLEtBQUssQ0FBQyxLQUFLLEVBQUUsU0FBUyxDQUFDLENBQUMsRUFBRSxDQUFDLFFBQVEsRUFBRSxJQUFJLENBQUMsQ0FBQyxNQUFNLENBQUMsSUFBSSxDQUFDLEdBQUcsQ0FBQztnQkFDakYsU0FBUyxJQUFJLEtBQUssS0FBSyxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUMsQ0FBQyxFQUFFLENBQUMsUUFBUSxFQUFFLElBQUksQ0FBQyxDQUFDLE1BQU0sQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDO2dCQUU1RSxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssTUFBTSxDQUFDLEVBQUUsQ0FBQztvQkFDaEQsU0FBUztnQkFDWCxDQUFDO2dCQUVELElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxLQUFLLENBQUMsRUFBRSxDQUFDO29CQUMvQyxrREFBa0Q7b0JBQ2xELFNBQVMsSUFBSSxPQUFPLEtBQUssRUFBRSxFQUFFLElBQUksQ0FBQztvQkFDbEMsU0FBUztnQkFDWCxDQUFDO3FCQUFNLENBQUM7b0JBQ04sS0FBSyxNQUFNLFFBQVEsSUFBSSxLQUFLLEVBQUUsQ0FBQzt3QkFDN0IsSUFBSSxRQUFRLEtBQUssUUFBUSxFQUFFLENBQUM7NEJBQzFCLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxRQUFRLENBQUMsRUFBRSxDQUFDO2dDQUNsRCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxPQUFPLEVBQUUsQ0FBQzs0QkFDaEMsbURBQW1EOzRCQUNuRCxTQUFTO3dCQUNYLENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssV0FBVyxFQUFFLENBQUM7NEJBQ3BDLFNBQVM7d0JBQ1gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxTQUFTLEVBQUUsQ0FBQzs0QkFDbEMsU0FBUzt3QkFDWCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLGdCQUFnQixFQUFFLENBQUM7NEJBQ3pDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxnQkFBZ0IsQ0FBQyxFQUFFLENBQUM7Z0NBQzFELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQzs0QkFDbkQsQ0FBQzt3QkFDSCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLFVBQVUsRUFBRSxDQUFDOzRCQUNuQyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssVUFBVSxDQUFDLEVBQUUsQ0FBQztnQ0FDcEQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssT0FBTyxFQUFFLENBQUM7NEJBQ2hDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxPQUFPLENBQUMsRUFBRSxDQUFDO2dDQUNqRCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxVQUFVLEVBQUUsQ0FBQzs0QkFDbkMsU0FBUzt3QkFDWCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLFFBQVEsRUFBRSxDQUFDOzRCQUNqQyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssUUFBUSxDQUFDLEVBQUUsQ0FBQztnQ0FDbEQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssVUFBVSxFQUFFLENBQUM7NEJBQ25DLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxVQUFVLENBQUMsRUFBRSxDQUFDO2dDQUNwRCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxZQUFZLEVBQUUsQ0FBQzs0QkFDckMsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLFlBQVksQ0FBQyxFQUFFLENBQUM7Z0NBQ3RELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQzs0QkFDbkQsQ0FBQzt3QkFDSCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLFlBQVksRUFBRSxDQUFDOzRCQUNyQyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssWUFBWSxDQUFDLEVBQUUsQ0FBQztnQ0FDdEQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssYUFBYSxFQUFFLENBQUM7NEJBQ3RDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxhQUFhLENBQUMsRUFBRSxDQUFDO2dDQUN2RCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxZQUFZLEVBQUUsQ0FBQzs0QkFDckMsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLFlBQVksQ0FBQyxFQUFFLENBQUM7Z0NBQ3RELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQzs0QkFDbkQsQ0FBQzt3QkFDSCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLFNBQVMsRUFBRSxDQUFDOzRCQUNsQyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssU0FBUyxDQUFDLEVBQUUsQ0FBQztnQ0FDbkQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssWUFBWSxFQUFFLENBQUM7NEJBQ3JDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxZQUFZLENBQUMsRUFBRSxDQUFDO2dDQUN0RCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxjQUFjLEVBQUUsQ0FBQzs0QkFDdkMsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLGNBQWMsQ0FBQyxFQUFFLENBQUM7Z0NBQ3hELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQzs0QkFDbkQsQ0FBQzt3QkFDSCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLGNBQWMsRUFBRSxDQUFDOzRCQUN2QyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssY0FBYyxDQUFDLEVBQUUsQ0FBQztnQ0FDeEQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssVUFBVSxFQUFFLENBQUM7NEJBQ25DLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxVQUFVLENBQUMsRUFBRSxDQUFDO2dDQUNwRCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQztvQkFDSCxDQUFDO2dCQUNILENBQUM7Z0JBRUQsSUFBSSxLQUFLLEVBQUUsWUFBWSxFQUFFLENBQUM7b0JBQ3hCLE1BQU0sWUFBWSxHQUFHLFdBQVcsRUFBRSxJQUFJLENBQ3BDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsRUFBRSxLQUFLLEtBQUssRUFBRSxZQUFZLENBQ3JDLENBQUM7b0JBRUYsSUFBSSxZQUFZLEVBQUUsRUFBRSxFQUFFLENBQUM7d0JBQ3JCLFNBQVMsSUFBSSwyQkFBMkIsQ0FBQzt3QkFDekMsU0FBUyxJQUFJLFNBQVMsWUFBWSxFQUFFLElBQUksSUFBSSxDQUFDO3dCQUM3QyxTQUFTLElBQUksUUFBUSxZQUFZLEVBQUUsR0FBRyxJQUFJLENBQUM7d0JBRTNDLEtBQUssTUFBTSxRQUFRLElBQUksWUFBWSxFQUFFLENBQUM7NEJBQ3BDLElBQUksUUFBUSxLQUFLLE9BQU8sRUFBRSxDQUFDO2dDQUN6QixJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssa0JBQWtCLENBQUMsRUFBRSxDQUFDO29DQUM1RCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssWUFBWSxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7Z0NBQzFELENBQUM7NEJBQ0gsQ0FBQztpQ0FBTSxJQUFJLFFBQVEsS0FBSyxTQUFTLEVBQUUsQ0FBQztnQ0FDbEMsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLG9CQUFvQixDQUFDLEVBQUUsQ0FBQztvQ0FDOUQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLFlBQVksQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDO2dDQUMxRCxDQUFDOzRCQUNILENBQUM7aUNBQU0sSUFBSSxRQUFRLEtBQUssVUFBVSxFQUFFLENBQUM7Z0NBQ25DLElBQ0UsSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxxQkFBcUIsQ0FBQyxFQUMxRCxDQUFDO29DQUNELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxZQUFZLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQztnQ0FDMUQsQ0FBQzs0QkFDSCxDQUFDO3dCQUNILENBQUM7d0JBRUQsSUFBSSxTQUFTLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDOzRCQUMxQixTQUFTLElBQUksY0FBYyxDQUFDOzRCQUU1QixLQUFLLE1BQU0sUUFBUSxJQUFJLFNBQVMsRUFBRSxDQUFDO2dDQUNqQyxTQUFTLElBQUksU0FBUyxRQUFRLEVBQUUsSUFBSSxJQUFJLENBQUM7Z0NBQ3pDLFNBQVMsSUFBSSxVQUFVLFFBQVEsRUFBRSxNQUFNLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQyxFQUFFLE9BQU8sQ0FBQyxFQUFFLEtBQUssSUFBSSxDQUFDOzRCQUNoRixDQUFDO3dCQUNILENBQUM7b0JBQ0gsQ0FBQztnQkFDSCxDQUFDO2dCQUVELElBQUksS0FBSyxFQUFFLE1BQU0sRUFBRSxDQUFDO29CQUNsQixNQUFNLFlBQVksR0FBRyxLQUFLLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsRUFBRSxLQUFLLEtBQUssRUFBRSxNQUFNLENBQUMsQ0FBQztvQkFFakUsSUFBSSxZQUFZLEVBQUUsRUFBRSxFQUFFLENBQUM7d0JBQ3JCLFNBQVMsSUFBSSxxQkFBcUIsQ0FBQzt3QkFDbkMsU0FBUyxJQUFJLEdBQUcsWUFBWSxFQUFFLEtBQUssSUFBSSxDQUFDO3dCQUV4QyxLQUFLLE1BQU0sUUFBUSxJQUFJLFlBQVksRUFBRSxDQUFDOzRCQUNwQyxJQUFJLFFBQVEsS0FBSyxNQUFNLEVBQUUsQ0FBQztnQ0FDeEIsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLGVBQWUsQ0FBQyxFQUFFLENBQUM7b0NBQ3pELFNBQVMsSUFBSSxTQUFTLFlBQVksQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDO2dDQUNuRCxDQUFDOzRCQUNILENBQUM7aUNBQU0sSUFBSSxRQUFRLEtBQUssUUFBUSxFQUFFLENBQUM7Z0NBQ2pDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxhQUFhLENBQUMsRUFBRSxDQUFDO29DQUN2RCxTQUFTLElBQUksV0FBVyxZQUFZLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQztnQ0FDckQsQ0FBQzs0QkFDSCxDQUFDO3dCQUNILENBQUM7b0JBQ0gsQ0FBQztnQkFDSCxDQUFDO2dCQUVELFNBQVMsSUFBSSxJQUFJLENBQUM7WUFDcEIsQ0FBQztZQUVELFNBQVMsSUFBSSxNQUFNLENBQUM7UUFDdEIsQ0FBQztRQUVELElBQUksS0FBSyxHQUFHLENBQUMsRUFBRSxDQUFDO1lBQ2QsU0FBUyxJQUFJLFVBQVUsS0FBSyxFQUFFLENBQUM7UUFDakMsQ0FBQztRQUVELG1CQUFtQjtRQUNuQixRQUFRLENBQUMsS0FBSyxHQUFHLFdBQVcsQ0FBQztRQUU3QixRQUFRLENBQUMsSUFBSSxHQUFHLFNBQVMsQ0FBQztRQUUxQixPQUFPLFFBQVEsQ0FBQztJQUNsQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLG9DQUFvQyxDQUFDLENBQUM7SUFDdkQsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLHlCQUF5QixHQUFHLEtBQUssRUFDNUMsTUFBYyxFQUNkLFFBQWdCLEVBQ2hCLFFBQTZCO0FBQzdCLHNDQUFzQztBQUN0QyxnQkFBc0QsRUFDdEQsaUJBQWlELEVBQ2pELFdBQW1CLEVBQ25CLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxJQUFJLGVBQWUsR0FBRyxnQ0FBZ0MsQ0FDcEQsV0FBVyxFQUNYLFFBQVEsRUFDUixpQkFBaUIsRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUNuQyxpQkFBaUIsRUFBRSxVQUFVLEVBQUUsS0FBSyxFQUNwQyxpQkFBaUIsRUFBRSxVQUFVLEVBQUUsR0FBRyxFQUNsQyxTQUFTLEVBQ1QsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLElBQUksRUFDbkMsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLE1BQU0sRUFDckMsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLElBQUksRUFDbkMsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLHlCQUF5QixFQUN4RCxpQkFBaUIsRUFBRSxVQUFVLEVBQUUsbUJBQW1CLENBQ25ELENBQUM7UUFFRixJQUFJLGFBQWEsR0FBRyw4QkFBOEIsQ0FDaEQsV0FBVyxFQUNYLFFBQVEsRUFDUixpQkFBaUIsRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUNqQyxpQkFBaUIsRUFBRSxRQUFRLEVBQUUsS0FBSyxFQUNsQyxpQkFBaUIsRUFBRSxRQUFRLEVBQUUsR0FBRyxFQUNoQyxTQUFTLEVBQ1QsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLElBQUksRUFDakMsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLE1BQU0sRUFDbkMsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLElBQUksRUFDakMsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLHlCQUF5QixFQUN0RCxpQkFBaUIsRUFBRSxRQUFRLEVBQUUsbUJBQW1CLENBQ2pELENBQUM7UUFFRixJQUFJLENBQUMsZUFBZSxFQUFFLENBQUM7WUFDckIsZUFBZSxHQUFHLEtBQUssRUFBRSxDQUFDLFFBQVEsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDdEQsQ0FBQztRQUVELElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQztZQUNuQixhQUFhLEdBQUcsS0FBSyxFQUFFLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUMvQyxDQUFDO1FBRUQsTUFBTSxJQUFJLEdBQW9CO1lBQzVCLE1BQU07WUFDTixRQUFRO1lBQ1IsS0FBSyxFQUNILFFBQVEsRUFBRSxNQUFNLEVBQUUsS0FBSztnQkFDdkIsUUFBUSxFQUFFLE1BQU0sRUFBRSxPQUFPO2dCQUN6QixRQUFRLEVBQUUsTUFBTSxFQUFFLFdBQVc7Z0JBQzdCLFFBQVEsRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSTtZQUN2QyxTQUFTLEVBQUUsZ0JBQWdCLEVBQUUsU0FBUztZQUN0QyxVQUFVLEVBQUUsZ0JBQWdCLEVBQUUsVUFBVTtZQUN4QyxlQUFlO1lBQ2YsYUFBYTtTQUNkLENBQUM7UUFFRixNQUFNLFFBQVEsR0FBUTtZQUNwQixLQUFLLEVBQUUsRUFBRTtZQUNULElBQUksRUFBRSxFQUFFO1lBQ1IsS0FBSyxFQUFFLGFBQWE7U0FDckIsQ0FBQztRQUVGLE1BQU0sU0FBUyxHQUFHLE1BQU0sb0JBQW9CLENBQzFDLElBQUksRUFDSixJQUFJLEVBQUUsZUFBZSxFQUNyQixJQUFJLEVBQUUsYUFBYSxFQUNuQixJQUFJLEVBQUUsUUFBUSxFQUNkLFFBQVEsQ0FDVCxDQUFDO1FBRUYsT0FBTyxTQUFTLENBQUM7UUFDakIsa0NBQWtDO1FBRWxDLHFCQUFxQjtRQUNyQix3RUFBd0U7UUFDeEUsSUFBSTtRQUVKLGdDQUFnQztRQUVoQyxrQ0FBa0M7UUFDbEMsMkdBQTJHO1FBRTNHLDJDQUEyQztRQUUzQywwQkFBMEI7UUFDMUIsc0NBQXNDO1FBQ3RDLFlBQVk7UUFDWixRQUFRO1FBQ1IsSUFBSTtRQUVKLHVGQUF1RjtRQUN2RixvQkFBb0I7UUFDcEIsNkJBQTZCO1FBQzdCLDJCQUEyQjtRQUMzQix3QkFBd0I7UUFDeEIsdUJBQXVCO1FBQ3ZCLGdCQUFnQjtRQUNoQixJQUFJO1FBRUosK0NBQStDO1FBQy9DLHlEQUF5RDtRQUN6RCxxREFBcUQ7UUFDckQsNkNBQTZDO1FBQzdDLDZDQUE2QztRQUU3QyxxQkFBcUI7UUFFckIsZ0JBQWdCO1FBQ2hCLG1JQUFtSTtRQUVuSSxzQ0FBc0M7UUFFdEMsZ0tBQWdLO1FBRWhLLGtFQUFrRTtRQUNsRSx3QkFBd0I7UUFFeEIsNENBQTRDO1FBQzVDLGtDQUFrQztRQUVsQyxvRUFBb0U7UUFDcEUscUZBQXFGO1FBQ3JGLGdGQUFnRjtRQUVoRiw2REFBNkQ7UUFDN0QsdUJBQXVCO1FBQ3ZCLFlBQVk7UUFFWiwwQ0FBMEM7UUFFMUMsZ0VBQWdFO1FBQ2hFLHFFQUFxRTtRQUNyRSxvREFBb0Q7UUFDcEQsMkJBQTJCO1FBQzNCLGdCQUFnQjtRQUVoQiwyQ0FBMkM7UUFFM0MsdUVBQXVFO1FBQ3ZFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsaURBQWlEO1FBQ2pELHNFQUFzRTtRQUN0RSwyQkFBMkI7UUFDM0IscURBQXFEO1FBQ3JELDJCQUEyQjtRQUMzQixtREFBbUQ7UUFDbkQsMkJBQTJCO1FBQzNCLDBEQUEwRDtRQUUxRCwrRUFBK0U7UUFDL0UsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQixvREFBb0Q7UUFFcEQseUVBQXlFO1FBQ3pFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsaURBQWlEO1FBRWpELHNFQUFzRTtRQUN0RSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLG9EQUFvRDtRQUVwRCwyQkFBMkI7UUFDM0Isa0RBQWtEO1FBRWxELHVFQUF1RTtRQUN2RSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLG9EQUFvRDtRQUVwRCx5RUFBeUU7UUFDekUsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQixzREFBc0Q7UUFFdEQsMkVBQTJFO1FBQzNFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsc0RBQXNEO1FBRXRELDJFQUEyRTtRQUMzRSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLHVEQUF1RDtRQUV2RCw0RUFBNEU7UUFDNUUsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQixzREFBc0Q7UUFFdEQsMkVBQTJFO1FBQzNFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsbURBQW1EO1FBRW5ELHdFQUF3RTtRQUN4RSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLHNEQUFzRDtRQUV0RCwyRUFBMkU7UUFDM0UsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQix3REFBd0Q7UUFFeEQsNkVBQTZFO1FBQzdFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsd0RBQXdEO1FBRXhELDZFQUE2RTtRQUM3RSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLG9EQUFvRDtRQUVwRCx5RUFBeUU7UUFDekUsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQixnQkFBZ0I7UUFFaEIsWUFBWTtRQUVaLHVGQUF1RjtRQUV2RixrQ0FBa0M7UUFDbEMsdURBQXVEO1FBQ3ZELDJEQUEyRDtRQUMzRCx5REFBeUQ7UUFFekQscURBQXFEO1FBQ3JELDhDQUE4QztRQUU5QyxxRkFBcUY7UUFDckYsa0ZBQWtGO1FBQ2xGLHdCQUF3QjtRQUN4Qix1REFBdUQ7UUFFdkQsdUZBQXVGO1FBQ3ZGLGtGQUFrRjtRQUNsRix3QkFBd0I7UUFDeEIsd0RBQXdEO1FBRXhELHdGQUF3RjtRQUN4RixrRkFBa0Y7UUFDbEYsd0JBQXdCO1FBQ3hCLG9CQUFvQjtRQUNwQixnQkFBZ0I7UUFFaEIsMkNBQTJDO1FBQzNDLDhDQUE4QztRQUU5QyxzREFBc0Q7UUFDdEQsK0RBQStEO1FBQy9ELG9HQUFvRztRQUNwRyxvQkFBb0I7UUFDcEIsZ0JBQWdCO1FBQ2hCLFlBQVk7UUFFWiwyRUFBMkU7UUFFM0Usa0NBQWtDO1FBQ2xDLGlEQUFpRDtRQUNqRCxzREFBc0Q7UUFFdEQscURBQXFEO1FBQ3JELDZDQUE2QztRQUU3QyxrRkFBa0Y7UUFDbEYsMkVBQTJFO1FBQzNFLHdCQUF3QjtRQUN4QixzREFBc0Q7UUFFdEQsZ0ZBQWdGO1FBQ2hGLDZFQUE2RTtRQUM3RSx3QkFBd0I7UUFDeEIsb0JBQW9CO1FBQ3BCLGdCQUFnQjtRQUNoQixZQUFZO1FBRVosNEJBQTRCO1FBQzVCLFFBQVE7UUFFUiwwQkFBMEI7UUFDMUIsSUFBSTtRQUVKLG1CQUFtQjtRQUNuQixxQ0FBcUM7UUFDckMsSUFBSTtRQUVKLHNCQUFzQjtRQUN0QiwrQkFBK0I7UUFFL0IsNEJBQTRCO1FBRTVCLGtCQUFrQjtJQUNwQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGlDQUFpQyxDQUFDLENBQUM7SUFDcEQsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLHVDQUF1QyxHQUFHLEtBQUssRUFDMUQsTUFBYyxFQUNkLFFBQWdCLEVBQ2hCLFFBQTZCO0FBQzdCLHNDQUFzQztBQUN0QyxnQkFBc0QsRUFDdEQsaUJBQWlELEVBQ2pELFdBQW1CLEVBQ25CLG9CQUE2QyxFQUM3QyxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsSUFBSSxlQUFlLEdBQUcsZ0NBQWdDLENBQ3BELFdBQVcsRUFDWCxRQUFRLEVBQ1IsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLElBQUksRUFDbkMsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLEtBQUssRUFDcEMsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLEdBQUcsRUFDbEMsU0FBUyxFQUNULGlCQUFpQixFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQ25DLGlCQUFpQixFQUFFLFVBQVUsRUFBRSxNQUFNLEVBQ3JDLGlCQUFpQixFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQ25DLGlCQUFpQixFQUFFLFVBQVUsRUFBRSx5QkFBeUIsRUFDeEQsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLG1CQUFtQixDQUNuRCxDQUFDO1FBRUYsSUFBSSxhQUFhLEdBQUcsOEJBQThCLENBQ2hELFdBQVcsRUFDWCxRQUFRLEVBQ1IsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLElBQUksRUFDakMsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLEtBQUssRUFDbEMsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLEdBQUcsRUFDaEMsU0FBUyxFQUNULGlCQUFpQixFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQ2pDLGlCQUFpQixFQUFFLFFBQVEsRUFBRSxNQUFNLEVBQ25DLGlCQUFpQixFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQ2pDLGlCQUFpQixFQUFFLFFBQVEsRUFBRSx5QkFBeUIsRUFDdEQsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLG1CQUFtQixDQUNqRCxDQUFDO1FBRUYsSUFBSSxDQUFDLGVBQWUsRUFBRSxDQUFDO1lBQ3JCLGVBQWUsR0FBRyxLQUFLLEVBQUUsQ0FBQyxRQUFRLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQ3RELENBQUM7UUFFRCxJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7WUFDbkIsYUFBYSxHQUFHLEtBQUssRUFBRSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDL0MsQ0FBQztRQUVELE1BQU0sT0FBTyxHQUFvQjtZQUMvQixNQUFNO1lBQ04sUUFBUTtZQUNSLEtBQUssRUFDSCxRQUFRLEVBQUUsTUFBTSxFQUFFLEtBQUs7Z0JBQ3ZCLFFBQVEsRUFBRSxNQUFNLEVBQUUsT0FBTztnQkFDekIsUUFBUSxFQUFFLE1BQU0sRUFBRSxXQUFXO2dCQUM3QixRQUFRLEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUk7Z0JBQ3JDLG9CQUFvQixFQUFFLFlBQVksRUFBRSxNQUFNLEVBQUUsS0FBSztnQkFDakQsb0JBQW9CLEVBQUUsWUFBWSxFQUFFLE1BQU0sRUFBRSxPQUFPO2dCQUNuRCxvQkFBb0IsRUFBRSxZQUFZLEVBQUUsTUFBTSxFQUFFLFdBQVc7Z0JBQ3ZELG9CQUFvQixFQUFFLFlBQVksRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSTtZQUNqRSxTQUFTLEVBQUUsZ0JBQWdCLEVBQUUsU0FBUztZQUN0QyxVQUFVLEVBQUUsZ0JBQWdCLEVBQUUsVUFBVTtZQUN4QyxlQUFlO1lBQ2YsYUFBYTtTQUNkLENBQUM7UUFFRixNQUFNLFFBQVEsR0FBb0I7WUFDaEMsR0FBRyxvQkFBb0IsRUFBRSxRQUFRO1lBQ2pDLGVBQWUsRUFBRSxvQkFBb0IsRUFBRSxhQUFhLEVBQUUsZUFBZTtZQUNyRSxhQUFhLEVBQUUsb0JBQW9CLEVBQUUsYUFBYSxFQUFFLGFBQWE7U0FDbEUsQ0FBQztRQUVGLDZCQUE2QjtRQUM3QixJQUFJLENBQUMsUUFBUSxFQUFFLE1BQU0sRUFBRSxDQUFDO1lBQ3RCLFFBQVEsQ0FBQyxNQUFNLEdBQUcsTUFBTSxJQUFJLE9BQU8sRUFBRSxNQUFNLENBQUM7UUFDOUMsQ0FBQztRQUVELElBQUksQ0FBQyxRQUFRLEVBQUUsUUFBUSxFQUFFLENBQUM7WUFDeEIsUUFBUSxDQUFDLFFBQVEsR0FBRyxRQUFRLElBQUksT0FBTyxFQUFFLFFBQVEsQ0FBQztRQUNwRCxDQUFDO1FBRUQsSUFBSSxDQUFDLFFBQVEsRUFBRSxLQUFLLEVBQUUsQ0FBQztZQUNyQixRQUFRLENBQUMsS0FBSyxHQUFHLE9BQU8sRUFBRSxLQUFLLENBQUM7UUFDbEMsQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLFNBQVMsS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUN0QyxRQUFRLENBQUMsU0FBUyxHQUFHLE9BQU8sRUFBRSxTQUFTLENBQUM7UUFDMUMsQ0FBQztRQUVELElBQUksQ0FBQyxDQUFDLFFBQVEsRUFBRSxVQUFVLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7WUFDeEMsUUFBUSxDQUFDLFVBQVUsR0FBRyxPQUFPLEVBQUUsVUFBVSxDQUFDO1FBQzVDLENBQUM7UUFFRCxJQUFJLENBQUMsUUFBUSxFQUFFLGVBQWUsRUFBRSxDQUFDO1lBQy9CLFFBQVEsQ0FBQyxlQUFlLEdBQUcsT0FBTyxFQUFFLGVBQWUsQ0FBQztRQUN0RCxDQUFDO1FBRUQsSUFBSSxDQUFDLFFBQVEsRUFBRSxhQUFhLEVBQUUsQ0FBQztZQUM3QixRQUFRLENBQUMsYUFBYSxHQUFHLE9BQU8sRUFBRSxhQUFhLENBQUM7UUFDbEQsQ0FBQztRQUVELE1BQU0sUUFBUSxHQUFRO1lBQ3BCLEtBQUssRUFBRSxFQUFFO1lBQ1QsSUFBSSxFQUFFLEVBQUU7WUFDUixLQUFLLEVBQUUsYUFBYTtTQUNyQixDQUFDO1FBRUYsTUFBTSxTQUFTLEdBQUcsTUFBTSxvQkFBb0IsQ0FDMUMsUUFBUSxFQUNSLFFBQVEsRUFBRSxlQUFlLEVBQ3pCLFFBQVEsRUFBRSxhQUFhLEVBQ3ZCLFFBQVEsRUFBRSxRQUFRLEVBQ2xCLFFBQVEsQ0FDVCxDQUFDO1FBRUYsT0FBTyxTQUFTLENBQUM7SUFDbkIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxpREFBaUQsQ0FBQyxDQUFDO0lBQ3BFLENBQUM7QUFDSCxDQUFDLENBQUM7QUFFRixNQUFNLENBQUMsTUFBTSx3QkFBd0IsR0FBRyxLQUFLLEVBQzNDLE1BQWMsRUFDZCxNQUFjLEVBQ2QsUUFBZ0IsRUFDaEIsb0JBQTZDLEVBQzdDLGVBQXVCLEVBQ3ZCLEtBQXFFLEVBQ3JFLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLGFBQWEsR0FBRyxvQkFBb0IsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1FBQzVELElBQUksV0FBVyxHQUFHLEVBQUUsQ0FBQztRQUNyQixLQUFLLElBQUksQ0FBQyxHQUFHLGFBQWEsRUFBRSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsRUFBRSxFQUFFLENBQUM7WUFDdkMsTUFBTSxPQUFPLEdBQUcsb0JBQW9CLENBQUMsUUFBUSxDQUFDLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQztZQUVyRCxJQUFJLE9BQU8sQ0FBQyxJQUFJLEtBQUssTUFBTSxFQUFFLENBQUM7Z0JBQzVCLFdBQVcsR0FBRyxPQUFPLENBQUMsT0FBTyxDQUFDO2dCQUM5QixNQUFNO1lBQ1IsQ0FBQztRQUNILENBQUM7UUFDRCxNQUFNLFNBQVMsR0FBRyxXQUFXLENBQUM7UUFFOUIsTUFBTSxnQkFBZ0IsR0FDcEIsTUFBTSxvQ0FBb0MsQ0FBQyxTQUFTLENBQUMsQ0FBQztRQUV4RCxJQUFJLFNBQVMsR0FBdUI7WUFDbEMsS0FBSyxFQUFFLFdBQVc7WUFDbEIsSUFBSSxFQUFFLEVBQUU7WUFDUixLQUFLLEVBQUUsRUFBRTtZQUNULFFBQVEsRUFBRSxFQUFFO1lBQ1osYUFBYSxFQUFFLEVBQUU7U0FDbEIsQ0FBQztRQUVGLFFBQVEsS0FBSyxFQUFFLENBQUM7WUFDZCxLQUFLLFNBQVM7Z0JBQ1osTUFBTSxRQUFRLEdBQUcsTUFBTSw2QkFBNkIsQ0FDbEQsU0FBUyxFQUNULGVBQWUsQ0FDaEIsQ0FBQztnQkFDRixNQUFNLFNBQVMsR0FBRyxNQUFNLDhCQUE4QixDQUNwRCxNQUFNLEVBQ04sUUFBUSxFQUNSLFNBQVMsRUFDVCxlQUFlLENBQ2hCLENBQUM7Z0JBQ0YsU0FBUyxHQUFHLE1BQU0seUJBQXlCLENBQ3pDLE1BQU0sRUFDTixRQUFRLEVBQ1IsUUFBUSxFQUNSLGdCQUFnQixFQUNoQixTQUFTLEVBQ1QsZUFBZSxDQUNoQixDQUFDO2dCQUNGLE1BQU07WUFDUixLQUFLLGdCQUFnQjtnQkFDbkIsSUFBSSxjQUFjLEdBQUcsRUFBRSxDQUFDO2dCQUN4QixJQUFJLG9CQUFvQixHQUFHLEVBQUUsQ0FBQztnQkFFOUIsS0FBSyxJQUFJLENBQUMsR0FBRyxhQUFhLEVBQUUsQ0FBQyxHQUFHLENBQUMsRUFBRSxDQUFDLEVBQUUsRUFBRSxDQUFDO29CQUN2QyxNQUFNLE9BQU8sR0FBRyxvQkFBb0IsQ0FBQyxRQUFRLENBQUMsQ0FBQyxHQUFHLENBQUMsQ0FBQyxDQUFDO29CQUVyRCxJQUFJLE9BQU8sQ0FBQyxJQUFJLEtBQUssV0FBVyxFQUFFLENBQUM7d0JBQ2pDLG9CQUFvQixHQUFHLE9BQU8sQ0FBQyxPQUFPLENBQUM7d0JBQ3ZDLFNBQVM7b0JBQ1gsQ0FBQztvQkFFRCxJQUFJLE9BQU8sQ0FBQyxJQUFJLEtBQUssTUFBTSxFQUFFLENBQUM7d0JBQzVCLElBQUksT0FBTyxDQUFDLE9BQU8sS0FBSyxTQUFTLEVBQUUsQ0FBQzs0QkFDbEMsY0FBYyxHQUFHLE9BQU8sQ0FBQyxPQUFPLENBQUM7NEJBQ2pDLE1BQU07d0JBQ1IsQ0FBQztvQkFDSCxDQUFDO2dCQUNILENBQUM7Z0JBRUQsSUFBSSxDQUFDLGNBQWMsSUFBSSxDQUFDLG9CQUFvQixFQUFFLENBQUM7b0JBQzdDLE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYyxFQUFFLGlCQUFpQixDQUFDLENBQUM7b0JBQy9DLE9BQU8sQ0FBQyxHQUFHLENBQUMsb0JBQW9CLEVBQUUsdUJBQXVCLENBQUMsQ0FBQztvQkFDM0QsTUFBTSxJQUFJLEtBQUssQ0FBQywyQ0FBMkMsQ0FBQyxDQUFDO2dCQUMvRCxDQUFDO2dCQUNELE1BQU0scUJBQXFCLEdBQ3pCLE1BQU0sMENBQTBDLENBQzlDLFNBQVMsRUFDVCxjQUFjLEVBQ2Qsb0JBQW9CLEVBQ3BCLGVBQWUsQ0FDaEIsQ0FBQztnQkFDSixNQUFNLHNCQUFzQixHQUMxQixNQUFNLDJDQUEyQyxDQUMvQyxNQUFNLEVBQ04sUUFBUSxFQUNSLFNBQVMsRUFDVCxjQUFjLEVBQ2Qsb0JBQW9CLEVBQ3BCLGVBQWUsQ0FDaEIsQ0FBQztnQkFFSixTQUFTLEdBQUcsTUFBTSx1Q0FBdUMsQ0FDdkQsTUFBTSxFQUNOLFFBQVEsRUFDUixxQkFBcUIsRUFDckIsZ0JBQWdCLEVBQ2hCLHNCQUFzQixFQUN0QixlQUFlLEVBQ2Ysb0JBQW9CLENBQ3JCLENBQUM7Z0JBQ0YsTUFBTTtRQUNWLENBQUM7UUFFRCw4SEFBOEg7UUFDOUgsSUFBSSxTQUFTLEVBQUUsS0FBSyxLQUFLLFdBQVcsRUFBRSxDQUFDO1lBQ3JDLE1BQU0sZ0JBQWdCLEdBQ3BCLE1BQU0sbURBQW1ELENBQ3ZELE1BQU0sRUFDTixTQUFTLENBQUMsSUFBYyxFQUN4QixvQkFBb0IsQ0FDckIsQ0FBQztZQUVKLG9CQUFvQixDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztZQUNyRCxvQkFBb0IsQ0FBQyxLQUFLLEdBQUcsV0FBVyxDQUFDO1lBQ3pDLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxJQUFJLENBQUM7UUFDdkMsQ0FBQzthQUFNLElBQUksU0FBUyxFQUFFLEtBQUssS0FBSyxnQkFBZ0IsRUFBRSxDQUFDO1lBQ2pELE1BQU0sZ0JBQWdCLEdBQ3BCLE1BQU0scURBQXFELENBQ3pELE1BQU0sRUFDTixTQUFTLEVBQUUsSUFBMEIsRUFDckMsb0JBQW9CLENBQ3JCLENBQUM7WUFFSixvQkFBb0IsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7WUFDckQsb0JBQW9CLENBQUMsS0FBSyxHQUFHLGdCQUFnQixDQUFDO1lBQzlDLG9CQUFvQixDQUFDLFFBQVEsR0FBRyxTQUFTLEVBQUUsSUFBMEIsQ0FBQztZQUN0RSxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsU0FBUyxFQUFFLFFBQVEsQ0FBQztZQUNwRCxvQkFBb0IsQ0FBQyxhQUFhLEdBQUcsU0FBUyxFQUFFLGFBQWEsQ0FBQztZQUM5RCxvQkFBb0IsQ0FBQyxnQkFBZ0IsR0FBRyxTQUFTLEVBQUUsZ0JBQWdCLENBQUM7WUFDcEUsb0JBQW9CLENBQUMsWUFBWSxHQUFHLFNBQVMsRUFBRSxZQUFZLENBQUM7UUFDOUQsQ0FBQzthQUFNLElBQUksU0FBUyxFQUFFLEtBQUssS0FBSyxpQkFBaUIsRUFBRSxDQUFDO1lBQ2xELE1BQU0sZ0JBQWdCLEdBQXlCO2dCQUM3QyxJQUFJLEVBQUUsV0FBVztnQkFDakIsT0FBTyxFQUFFLDZDQUE2QzthQUN2RCxDQUFDO1lBRUYsb0JBQW9CLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQ3JELG9CQUFvQixDQUFDLEtBQUssR0FBRyxpQkFBaUIsQ0FBQztZQUMvQyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO1FBQ3ZDLENBQUM7UUFFRCxPQUFPLG9CQUFvQixDQUFDO0lBQzlCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUseUJBQXlCLENBQUMsQ0FBQztJQUM1QyxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IFF1ZXJ5Q2FsZW5kYXJFeHRyYWN0ZWRKU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9RdWVyeUNhbGVuZGFyRXh0cmFjdGVkRGF0ZUpTT05UeXBlJztcbmltcG9ydCBVc2VySW5wdXRUb0pTT05UeXBlIGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1VzZXJJbnB1dFRvSlNPTlR5cGUnO1xuaW1wb3J0IHsgUXVlcnlDYWxlbmRhckV4dHJhY3RlZEF0dHJpYnV0ZXNUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvc2tpbGxzL2Fza0NhbGVuZGFyL3R5cGVzJztcbmltcG9ydCB7XG4gIHNlYXJjaE11bHRpcGxlRXZlbnRzQnlWZWN0b3JXaXRoRGF0ZXNMYW5jZURiLFxuICBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yLFxuICBleHRyYWN0QXR0cmlidXRlc05lZWRlZEZyb21Vc2VySW5wdXQsXG4gIGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YSxcbiAgZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEsXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMsXG4gIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc1F1ZXJ5RGF0ZUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlUXVlcnlEYXRlRnJvbVVzZXJJbnB1dCxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvYXBpLWhlbHBlcic7IC8vIFVwZGF0ZWQgaW1wb3J0XG5pbXBvcnQgeyBRdWVyeUV2ZW50c1R5cGUgfSBmcm9tICcuL3R5cGVzJztcbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvZGF0ZS11dGlscyc7XG5pbXBvcnQgeyBFdmVudFNjaGVtYSBhcyBMYW5jZURiRXZlbnRTY2hlbWEgfSBmcm9tICdAZnVuY3Rpb25zL191dGlscy9sYW5jZWRiX3NlcnZpY2UnOyAvLyBBZGRlZCBpbXBvcnRcbmltcG9ydCB7IGxpc3RTb3J0ZWRPYmplY3RzRm9yVXNlckdpdmVuRGF0ZXNBbmRBdHRyaWJ1dGVzIH0gZnJvbSAnQGNoYXQvX2xpYnMvc2tpbGxzL2Fza0NhbGVuZGFyL2FwaS1oZWxwZXInO1xuaW1wb3J0IF8gZnJvbSAnbG9kYXNoJztcbmltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbmltcG9ydCB7XG4gIEFzc2lzdGFudE1lc3NhZ2VUeXBlLFxuICBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZSxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvTWVzc2FnaW5nL01lc3NhZ2luZ1R5cGVzJztcbmltcG9ydCBSZXF1aXJlZEZpZWxkc1R5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVxdWlyZWRGaWVsZHNUeXBlJztcbmltcG9ydCBSZXNwb25zZUFjdGlvblR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVzcG9uc2VBY3Rpb25UeXBlJztcbmltcG9ydCB7IEV2ZW50VHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0V2ZW50VHlwZSc7XG5pbXBvcnQgeyBDb25mZXJlbmNlVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0NvbmZlcmVuY2VUeXBlJztcbmltcG9ydCB7IEF0dGVuZGVlVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL0F0dGVuZGVlVHlwZSc7XG5pbXBvcnQgeyBUYXNrVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3R5cGVzL1Rhc2tUeXBlJztcblxuZXhwb3J0IGNvbnN0IGZpbmFsU3RlcFF1ZXJ5RXZlbnRzID0gYXN5bmMgKFxuICBib2R5OiBRdWVyeUV2ZW50c1R5cGUsXG4gIHdpbmRvd1N0YXJ0RGF0ZTogc3RyaW5nLFxuICB3aW5kb3dFbmREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIHJlc3BvbnNlOiBhbnlcbikgPT4ge1xuICB0cnkge1xuICAgIGxldCBzZWFyY2hWZWN0b3I6IG51bWJlcltdID0gW107XG5cbiAgICBpZiAoYm9keT8udGl0bGUpIHtcbiAgICAgIHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuICAgIH1cblxuICAgIGNvbnN0IGV2ZW50SWRzOiBzdHJpbmdbXSA9IFtdO1xuXG4gICAgaWYgKHNlYXJjaFZlY3Rvcj8ubGVuZ3RoID4gMCkge1xuICAgICAgY29uc3Qgc2VhcmNoUmVzdWx0cyA9IGF3YWl0IHNlYXJjaE11bHRpcGxlRXZlbnRzQnlWZWN0b3JXaXRoRGF0ZXNMYW5jZURiKFxuICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICB3aW5kb3dFbmREYXRlXG4gICAgICApOyAvLyBVcGRhdGVkIGNhbGxcblxuICAgICAgZm9yIChjb25zdCBldmVudCBvZiBzZWFyY2hSZXN1bHRzKSB7XG4gICAgICAgIC8vIEl0ZXJhdGUgb3ZlciBMYW5jZURiRXZlbnRTY2hlbWFbXVxuICAgICAgICBpZiAoZXZlbnQ/LmlkKSB7XG4gICAgICAgICAgZXZlbnRJZHMucHVzaChldmVudC5pZCk7IC8vIFVzZSBldmVudC5pZFxuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuXG4gICAgbGV0IG9iamVjdHNXaXRoQXR0cmlidXRlczoge1xuICAgICAgZXZlbnRzOiBFdmVudFR5cGVbXTtcbiAgICAgIGNvbmZlcmVuY2VzOiBDb25mZXJlbmNlVHlwZVtdO1xuICAgICAgYXR0ZW5kZWVzOiBBdHRlbmRlZVR5cGVbXTtcbiAgICAgIHRhc2tzOiBUYXNrVHlwZVtdO1xuICAgICAgY291bnQ6IG51bWJlcjtcbiAgICB9O1xuXG4gICAgaWYgKGV2ZW50SWRzPy5sZW5ndGggPiAwKSB7XG4gICAgICBvYmplY3RzV2l0aEF0dHJpYnV0ZXMgPVxuICAgICAgICBhd2FpdCBsaXN0U29ydGVkT2JqZWN0c0ZvclVzZXJHaXZlbkRhdGVzQW5kQXR0cmlidXRlcyhcbiAgICAgICAgICBib2R5Py51c2VySWQsXG4gICAgICAgICAgYm9keT8ud2luZG93U3RhcnREYXRlLFxuICAgICAgICAgIGJvZHk/LndpbmRvd0VuZERhdGUsXG4gICAgICAgICAgYm9keT8uYXR0cmlidXRlcyxcbiAgICAgICAgICBib2R5Py5pc01lZXRpbmcsXG4gICAgICAgICAgZXZlbnRJZHNcbiAgICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgb2JqZWN0c1dpdGhBdHRyaWJ1dGVzID1cbiAgICAgICAgYXdhaXQgbGlzdFNvcnRlZE9iamVjdHNGb3JVc2VyR2l2ZW5EYXRlc0FuZEF0dHJpYnV0ZXMoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIGJvZHk/LndpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICBib2R5Py53aW5kb3dFbmREYXRlLFxuICAgICAgICAgIGJvZHk/LmF0dHJpYnV0ZXMsXG4gICAgICAgICAgYm9keT8uaXNNZWV0aW5nXG4gICAgICAgICk7XG4gICAgfVxuXG4gICAgY29uc3QgZXZlbnRzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy5ldmVudHM7XG4gICAgY29uc3QgY29uZmVyZW5jZXMgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmNvbmZlcmVuY2VzO1xuICAgIGNvbnN0IGF0dGVuZGVlcyA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8uYXR0ZW5kZWVzO1xuICAgIGNvbnN0IHRhc2tzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy50YXNrcztcbiAgICBjb25zdCBjb3VudCA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8uY291bnQ7XG5cbiAgICAvLyB2YWxpZGF0ZSBmb3VuZCBldmVudFxuICAgIGlmICghKGV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgbGV0IHF1ZXJ5RGF0YSA9ICcnO1xuXG4gICAgLy8gdW5pcSBkYXRlc1xuICAgIGNvbnN0IHVuaXFEYXRlcyA9IF8udW5pcUJ5KGV2ZW50cywgKGN1cnIpID0+XG4gICAgICBkYXlqcyhjdXJyPy5zdGFydERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICk/Lm1hcCgoZSkgPT4gZT8uc3RhcnREYXRlKTtcblxuICAgIGZvciAoY29uc3QgdW5pcURhdGUgb2YgdW5pcURhdGVzKSB7XG4gICAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV2ZW50cz8uZmlsdGVyKFxuICAgICAgICAoYSkgPT5cbiAgICAgICAgICBkYXlqcyhhPy5zdGFydERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ1lZWVktTU0tREQnKSA9PT1cbiAgICAgICAgICBkYXlqcyh1bmlxRGF0ZSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICApO1xuXG4gICAgICBxdWVyeURhdGEgKz0gYCR7ZGF5anModW5pcURhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ2RkZCwgWVlZWS1NTS1ERCcpfWA7XG4gICAgICBxdWVyeURhdGEgKz0gJ1xcbic7XG5cbiAgICAgIGZvciAoY29uc3QgZXZlbnQgb2YgZmlsdGVyZWRFdmVudHMpIHtcbiAgICAgICAgcXVlcnlEYXRhICs9ICdFdmVudCAtICc7XG5cbiAgICAgICAgcXVlcnlEYXRhICs9IGB0aXRsZTogJHtldmVudD8udGl0bGUgfHwgZXZlbnQ/LnN1bW1hcnl9LCBgO1xuICAgICAgICBxdWVyeURhdGEgKz0gYHRpbWU6ICR7ZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnTFQnKX0gYDtcbiAgICAgICAgcXVlcnlEYXRhICs9IGAtICR7ZGF5anMoZXZlbnQ/LmVuZERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ0xUJyl9LCBgO1xuXG4gICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnbm9uZScpKSB7XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2FsbCcpKSB7XG4gICAgICAgICAgLy8gcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19IGBcbiAgICAgICAgICBxdWVyeURhdGEgKz0gYGlkOiAke2V2ZW50Py5pZH0sIGA7XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgZm9yIChjb25zdCBwcm9wZXJ0eSBpbiBldmVudCkge1xuICAgICAgICAgICAgaWYgKHByb3BlcnR5ID09PSAnYWxsRGF5Jykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2FsbERheScpKSB7XG4gICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAndGl0bGUnKSB7XG4gICAgICAgICAgICAgIC8vIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzdGFydERhdGUnKSB7XG4gICAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2VuZERhdGUnKSB7XG4gICAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3JlY3VycmVuY2VSdWxlJykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ3JlY3VycmVuY2VSdWxlJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdsb2NhdGlvbicpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdsb2NhdGlvbicpKSB7XG4gICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnbm90ZXMnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnbm90ZXMnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3RpbWV6b25lJykge1xuICAgICAgICAgICAgICBjb250aW51ZTtcbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICd0YXNrSWQnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAndGFza0lkJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdwcmlvcml0eScpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdwcmlvcml0eScpKSB7XG4gICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnaXNGb2xsb3dVcCcpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdpc0ZvbGxvd1VwJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdpc1ByZUV2ZW50Jykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2lzUHJlRXZlbnQnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2lzUG9zdEV2ZW50Jykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2lzUG9zdEV2ZW50JykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdtb2RpZmlhYmxlJykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ21vZGlmaWFibGUnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2lzQnJlYWsnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnaXNCcmVhaycpKSB7XG4gICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnYnVmZmVyVGltZScpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdidWZmZXJUaW1lJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdoYXJkRGVhZGxpbmUnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnaGFyZERlYWRsaW5lJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzb2Z0RGVhZGxpbmUnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnc29mdERlYWRsaW5lJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdkdXJhdGlvbicpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdkdXJhdGlvbicpKSB7XG4gICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGV2ZW50Py5jb25mZXJlbmNlSWQpIHtcbiAgICAgICAgICBjb25zdCBmaWx0ZXJlZENvbmYgPSBjb25mZXJlbmNlcz8uZmluZChcbiAgICAgICAgICAgIChjKSA9PiBjPy5pZCA9PT0gZXZlbnQ/LmNvbmZlcmVuY2VJZFxuICAgICAgICAgICk7XG5cbiAgICAgICAgICBpZiAoZmlsdGVyZWRDb25mPy5pZCkge1xuICAgICAgICAgICAgcXVlcnlEYXRhICs9ICcgY29uZmVyZW5jZSB3aXRoIGV2ZW50IC0gJztcbiAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgbmFtZTogJHtmaWx0ZXJlZENvbmY/Lm5hbWV9LCBgO1xuICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBhcHA6ICR7ZmlsdGVyZWRDb25mPy5hcHB9LCBgO1xuXG4gICAgICAgICAgICBmb3IgKGNvbnN0IHByb3BlcnR5IGluIGZpbHRlcmVkQ29uZikge1xuICAgICAgICAgICAgICBpZiAocHJvcGVydHkgPT09ICdub3RlcycpIHtcbiAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2NvbmZlcmVuY2Utbm90ZXMnKSkge1xuICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtmaWx0ZXJlZENvbmZbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdqb2luVXJsJykge1xuICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnY29uZmVyZW5jZS1qb2luVXJsJykpIHtcbiAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZmlsdGVyZWRDb25mW3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnc3RhcnRVcmwnKSB7XG4gICAgICAgICAgICAgICAgaWYgKFxuICAgICAgICAgICAgICAgICAgYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2NvbmZlcmVuY2Utc3RhcnRVcmwnKVxuICAgICAgICAgICAgICAgICkge1xuICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtmaWx0ZXJlZENvbmZbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgaWYgKGF0dGVuZGVlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gJ2F0dGVuZGVlcyAtICc7XG5cbiAgICAgICAgICAgICAgZm9yIChjb25zdCBhdHRlbmRlZSBvZiBhdHRlbmRlZXMpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYG5hbWU6ICR7YXR0ZW5kZWU/Lm5hbWV9LCBgO1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgZW1haWw6ICR7YXR0ZW5kZWU/LmVtYWlscz8uZmluZCgoZSkgPT4gISFlPy5wcmltYXJ5KT8udmFsdWV9LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGV2ZW50Py50YXNrSWQpIHtcbiAgICAgICAgICBjb25zdCBmaWx0ZXJlZFRhc2sgPSB0YXNrcz8uZmluZCgodCkgPT4gdD8uaWQgPT09IGV2ZW50Py50YXNrSWQpO1xuXG4gICAgICAgICAgaWYgKGZpbHRlcmVkVGFzaz8uaWQpIHtcbiAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnIHRhc2sgd2l0aCBldmVudCAtICc7XG4gICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7ZmlsdGVyZWRUYXNrPy5ub3Rlc30sIGA7XG5cbiAgICAgICAgICAgIGZvciAoY29uc3QgcHJvcGVydHkgaW4gZmlsdGVyZWRUYXNrKSB7XG4gICAgICAgICAgICAgIGlmIChwcm9wZXJ0eSA9PT0gJ3R5cGUnKSB7XG4gICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICd0YXNrLWxpc3ROYW1lJykpIHtcbiAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgbGlzdDogJHtmaWx0ZXJlZFRhc2tbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzdGF0dXMnKSB7XG4gICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICd0YXNrLXN0YXR1cycpKSB7XG4gICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYHN0YXR1czogJHtmaWx0ZXJlZFRhc2tbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBxdWVyeURhdGEgKz0gJ1xcbic7XG4gICAgICB9XG5cbiAgICAgIHF1ZXJ5RGF0YSArPSAnXFxuXFxuJztcbiAgICB9XG5cbiAgICBpZiAoY291bnQgPiAwKSB7XG4gICAgICBxdWVyeURhdGEgKz0gYGNvdW50OiAke2NvdW50fWA7XG4gICAgfVxuXG4gICAgLy8gc3VjY2VzcyByZXNwb25zZVxuICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2NvbXBsZXRlZCc7XG5cbiAgICByZXNwb25zZS5kYXRhID0gcXVlcnlEYXRhO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZmluYWwgc3RlcCBxdWVyeSBldmVudHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHByb2Nlc3NRdWVyeUV2ZW50c1BlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgLy8gZGF0ZVRpbWVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgYXR0cmlidXRlc09iamVjdDogUXVlcnlDYWxlbmRhckV4dHJhY3RlZEF0dHJpYnV0ZXNUeXBlLFxuICBxdWVyeURhdGVKU09OQm9keTogUXVlcnlDYWxlbmRhckV4dHJhY3RlZEpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBsZXQgd2luZG93U3RhcnREYXRlID0gZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LnllYXIsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ubW9udGgsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8uZGF5LFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LmhvdXIsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ubWludXRlLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LnRpbWUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIGxldCB3aW5kb3dFbmREYXRlID0gZXh0cmFwb2xhdGVFbmREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ueWVhcixcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ubW9udGgsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LmRheSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8uaG91cixcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ubWludXRlLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy50aW1lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5yZWxhdGl2ZVRpbWVGcm9tTm93XG4gICAgKTtcblxuICAgIGlmICghd2luZG93U3RhcnREYXRlKSB7XG4gICAgICB3aW5kb3dTdGFydERhdGUgPSBkYXlqcygpLnN1YnRyYWN0KDIsICd3JykuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgaWYgKCF3aW5kb3dFbmREYXRlKSB7XG4gICAgICB3aW5kb3dFbmREYXRlID0gZGF5anMoKS5hZGQoNCwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBjb25zdCBib2R5OiBRdWVyeUV2ZW50c1R5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBpc01lZXRpbmc6IGF0dHJpYnV0ZXNPYmplY3Q/LmlzTWVldGluZyxcbiAgICAgIGF0dHJpYnV0ZXM6IGF0dHJpYnV0ZXNPYmplY3Q/LmF0dHJpYnV0ZXMsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgIH07XG5cbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ2ZpbmQtZXZlbnRzJyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzcG9uc2UyID0gYXdhaXQgZmluYWxTdGVwUXVlcnlFdmVudHMoXG4gICAgICBib2R5LFxuICAgICAgYm9keT8ud2luZG93U3RhcnREYXRlLFxuICAgICAgYm9keT8ud2luZG93RW5kRGF0ZSxcbiAgICAgIGJvZHk/LnRpbWV6b25lLFxuICAgICAgcmVzcG9uc2VcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlc3BvbnNlMjtcbiAgICAvLyBsZXQgc2VhcmNoVmVjdG9yOiBudW1iZXJbXSA9IFtdXG5cbiAgICAvLyBpZiAoYm9keT8udGl0bGUpIHtcbiAgICAvLyAgICAgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSlcbiAgICAvLyB9XG5cbiAgICAvLyBjb25zdCBldmVudElkczogc3RyaW5nW10gPSBbXVxuXG4gICAgLy8gaWYgKHNlYXJjaFZlY3Rvcj8ubGVuZ3RoID4gMCkge1xuICAgIC8vICAgICBjb25zdCByZXMgPSBhd2FpdCBhbGxFdmVudHNXaXRoRGF0ZXNPcGVuU2VhcmNoKHVzZXJJZCwgc2VhcmNoVmVjdG9yLCB3aW5kb3dTdGFydERhdGUsIHdpbmRvd0VuZERhdGUpXG5cbiAgICAvLyAgICAgZm9yIChjb25zdCBoaXQgb2YgcmVzPy5oaXRzPy5oaXRzKSB7XG5cbiAgICAvLyAgICAgICAgIGlmIChoaXQ/Ll9pZCkge1xuICAgIC8vICAgICAgICAgICAgIGV2ZW50SWRzLnB1c2goaGl0Py5faWQpXG4gICAgLy8gICAgICAgICB9XG4gICAgLy8gICAgIH1cbiAgICAvLyB9XG5cbiAgICAvLyBjb25zdCBvYmplY3RzV2l0aEF0dHJpYnV0ZXMgPSBhd2FpdCBsaXN0U29ydGVkT2JqZWN0c0ZvclVzZXJHaXZlbkRhdGVzQW5kQXR0cmlidXRlcyhcbiAgICAvLyAgICAgYm9keT8udXNlcklkLFxuICAgIC8vICAgICBib2R5Py53aW5kb3dTdGFydERhdGUsXG4gICAgLy8gICAgIGJvZHk/LndpbmRvd0VuZERhdGUsXG4gICAgLy8gICAgIGJvZHk/LmF0dHJpYnV0ZXMsXG4gICAgLy8gICAgIGJvZHk/LmlzTWVldGluZyxcbiAgICAvLyAgICAgZXZlbnRJZHMsXG4gICAgLy8gKVxuXG4gICAgLy8gY29uc3QgZXZlbnRzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy5ldmVudHNcbiAgICAvLyBjb25zdCBjb25mZXJlbmNlcyA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8uY29uZmVyZW5jZXNcbiAgICAvLyBjb25zdCBhdHRlbmRlZXMgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmF0dGVuZGVlc1xuICAgIC8vIGNvbnN0IHRhc2tzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy50YXNrc1xuICAgIC8vIGNvbnN0IGNvdW50ID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy5jb3VudFxuXG4gICAgLy8gbGV0IHF1ZXJ5RGF0YSA9ICcnXG5cbiAgICAvLyAvLyB1bmlxIGRhdGVzXG4gICAgLy8gY29uc3QgdW5pcURhdGVzID0gXy51bmlxQnkoZXZlbnRzLCAoY3VycikgPT4gKGRheWpzKGN1cnI/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpKSk/Lm1hcChlID0+IGU/LnN0YXJ0RGF0ZSlcblxuICAgIC8vIGZvciAoY29uc3QgdW5pcURhdGUgb2YgdW5pcURhdGVzKSB7XG5cbiAgICAvLyAgICAgY29uc3QgZmlsdGVyZWRFdmVudHMgPSBldmVudHM/LmZpbHRlcihhID0+IChkYXlqcyhhPy5zdGFydERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ1lZWVktTU0tREQnKSA9PT0gZGF5anModW5pcURhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ1lZWVktTU0tREQnKSkpXG5cbiAgICAvLyAgICAgcXVlcnlEYXRhICs9IGAke2RheWpzKHVuaXFEYXRlKS5mb3JtYXQoJ2RkZCwgWVlZWS1NTS1ERCcpfWBcbiAgICAvLyAgICAgcXVlcnlEYXRhICs9ICdcXG4nXG5cbiAgICAvLyAgICAgZm9yIChjb25zdCBldmVudCBvZiBmaWx0ZXJlZEV2ZW50cykge1xuICAgIC8vICAgICAgICAgcXVlcnlEYXRhICs9ICdFdmVudCAtICdcblxuICAgIC8vICAgICAgICAgcXVlcnlEYXRhICs9IGB0aXRsZTogJHtldmVudD8udGl0bGUgfHwgZXZlbnQ/LnN1bW1hcnl9LCBgXG4gICAgLy8gICAgICAgICBxdWVyeURhdGEgKz0gYHRpbWU6ICR7ZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnTFQnKX0gYFxuICAgIC8vICAgICAgICAgcXVlcnlEYXRhICs9IGAtICR7ZGF5anMoZXZlbnQ/LmVuZERhdGUpLnR6KHRpbWV6b25lKS5mb3JtYXQoJ0xUJyl9LCBgXG5cbiAgICAvLyAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdub25lJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgY29udGludWVcbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgZm9yIChjb25zdCBwcm9wZXJ0eSBpbiBldmVudCkge1xuXG4gICAgLy8gICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2FsbCcpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAvLyBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0gYFxuICAgIC8vICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGlkOiAke2V2ZW50Py5pZH0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgY29udGludWVcbiAgICAvLyAgICAgICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgICAgICBpZiAocHJvcGVydHkgPT09ICdhbGxEYXknKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2FsbERheScpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAndGl0bGUnKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIC8vIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICBjb250aW51ZVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzdGFydERhdGUnKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGNvbnRpbnVlXG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2VuZERhdGUnKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGNvbnRpbnVlXG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3JlY3VycmVuY2VSdWxlJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdyZWN1cnJlbmNlUnVsZScpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnbG9jYXRpb24nKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2xvY2F0aW9uJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdub3RlcycpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnbm90ZXMnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3RpbWV6b25lJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGNvbnRpbnVlXG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3Rhc2tJZCcpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAndGFza0lkJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdwcmlvcml0eScpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAncHJpb3JpdHknKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2lzRm9sbG93VXAnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2lzRm9sbG93VXAnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2lzUHJlRXZlbnQnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2lzUHJlRXZlbnQnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2lzUG9zdEV2ZW50Jykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdpc1Bvc3RFdmVudCcpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnbW9kaWZpYWJsZScpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnbW9kaWZpYWJsZScpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnaXNCcmVhaycpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnaXNCcmVhaycpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnYnVmZmVyVGltZScpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnYnVmZmVyVGltZScpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnaGFyZERlYWRsaW5lJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdoYXJkRGVhZGxpbmUnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3NvZnREZWFkbGluZScpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnc29mdERlYWRsaW5lJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdkdXJhdGlvbicpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnZHVyYXRpb24nKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIGNvbnN0IGZpbHRlcmVkQ29uZiA9IGNvbmZlcmVuY2VzPy5maW5kKGMgPT4gKGM/LmlkID09PSBldmVudD8uY29uZmVyZW5jZUlkKSlcblxuICAgIC8vICAgICAgICAgaWYgKGZpbHRlcmVkQ29uZj8uaWQpIHtcbiAgICAvLyAgICAgICAgICAgICBxdWVyeURhdGEgKz0gJyBjb25mZXJlbmNlIHdpdGggZXZlbnQgLSAnXG4gICAgLy8gICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBuYW1lOiAke2ZpbHRlcmVkQ29uZj8ubmFtZX0sIGBcbiAgICAvLyAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGFwcDogJHtmaWx0ZXJlZENvbmY/LmFwcH0sIGBcblxuICAgIC8vICAgICAgICAgICAgIGZvciAoY29uc3QgcHJvcGVydHkgaW4gZmlsdGVyZWRDb25mKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChwcm9wZXJ0eSA9PT0gJ25vdGVzJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnY29uZmVyZW5jZS1ub3RlcycpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZmlsdGVyZWRDb25mW3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2pvaW5VcmwnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdjb25mZXJlbmNlLWpvaW5VcmwnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2ZpbHRlcmVkQ29uZltwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzdGFydFVybCcpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2NvbmZlcmVuY2Utc3RhcnRVcmwnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2ZpbHRlcmVkQ29uZltwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgICAgICBpZiAoYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnYXR0ZW5kZWVzIC0gJ1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGZvciAoY29uc3QgYXR0ZW5kZWUgb2YgYXR0ZW5kZWVzKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYG5hbWU6ICR7YXR0ZW5kZWU/Lm5hbWV9LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGVtYWlsOiAke2F0dGVuZGVlPy5lbWFpbHM/LmZpbmQoZSA9PiAoISFlPy5wcmltYXJ5KSk/LnZhbHVlfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICBjb25zdCBmaWx0ZXJlZFRhc2sgPSB0YXNrcz8uZmluZCh0ID0+ICh0Py5pZCA9PT0gZXZlbnQ/LnRhc2tJZCkpXG5cbiAgICAvLyAgICAgICAgIGlmIChmaWx0ZXJlZFRhc2s/LmlkKSB7XG4gICAgLy8gICAgICAgICAgICAgcXVlcnlEYXRhICs9ICcgdGFzayB3aXRoIGV2ZW50IC0gJ1xuICAgIC8vICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtmaWx0ZXJlZFRhc2s/Lm5vdGVzfSwgYFxuXG4gICAgLy8gICAgICAgICAgICAgZm9yIChjb25zdCBwcm9wZXJ0eSBpbiBmaWx0ZXJlZFRhc2spIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKHByb3BlcnR5ID09PSAndHlwZScpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ3Rhc2stbGlzdE5hbWUnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGxpc3Q6ICR7ZmlsdGVyZWRUYXNrW3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3N0YXR1cycpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ3Rhc2stc3RhdHVzJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBzdGF0dXM6ICR7ZmlsdGVyZWRUYXNrW3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgcXVlcnlEYXRhICs9ICdcXG4nXG4gICAgLy8gICAgIH1cblxuICAgIC8vICAgICBxdWVyeURhdGEgKz0gJ1xcblxcbidcbiAgICAvLyB9XG5cbiAgICAvLyBpZiAoY291bnQgPiAwKSB7XG4gICAgLy8gICAgIHF1ZXJ5RGF0YSArPSBgY291bnQ6ICR7Y291bnR9YFxuICAgIC8vIH1cblxuICAgIC8vIC8vIHN1Y2Nlc3MgcmVzcG9uc2VcbiAgICAvLyByZXNwb25zZS5xdWVyeSA9ICdjb21wbGV0ZWQnXG5cbiAgICAvLyByZXNwb25zZS5kYXRhID0gcXVlcnlEYXRhXG5cbiAgICAvLyByZXR1cm4gcmVzcG9uc2VcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHByb2Nlc3MgcXVlcnkgZXZlbnRzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzUXVlcnlFdmVudHNNaXNzaW5nRmllbGRzUmV0dXJuZWQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgLy8gZGF0ZVRpbWVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgYXR0cmlidXRlc09iamVjdDogUXVlcnlDYWxlbmRhckV4dHJhY3RlZEF0dHJpYnV0ZXNUeXBlLFxuICBxdWVyeURhdGVKU09OQm9keTogUXVlcnlDYWxlbmRhckV4dHJhY3RlZEpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nLFxuICBtZXNzYWdlSGlzdG9yeU9iamVjdDogU2tpbGxNZXNzYWdlSGlzdG9yeVR5cGVcbikgPT4ge1xuICB0cnkge1xuICAgIGxldCB3aW5kb3dTdGFydERhdGUgPSBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ueWVhcixcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5tb250aCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5kYXksXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8uaG91cixcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5taW51dGUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8udGltZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgbGV0IHdpbmRvd0VuZERhdGUgPSBleHRyYXBvbGF0ZUVuZERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy55ZWFyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5tb250aCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8uZGF5LFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5ob3VyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5taW51dGUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnRpbWUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgaWYgKCF3aW5kb3dTdGFydERhdGUpIHtcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIXdpbmRvd0VuZERhdGUpIHtcbiAgICAgIHdpbmRvd0VuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IG5ld0JvZHk6IFF1ZXJ5RXZlbnRzVHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgdGl0bGU6XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uZGVzY3JpcHRpb24gfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRpdGxlIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2SnNvbkJvZHk/LnBhcmFtcz8udGFza0xpc3Q/LlswXT8udGFzayxcbiAgICAgIGlzTWVldGluZzogYXR0cmlidXRlc09iamVjdD8uaXNNZWV0aW5nLFxuICAgICAgYXR0cmlidXRlczogYXR0cmlidXRlc09iamVjdD8uYXR0cmlidXRlcyxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgfTtcblxuICAgIGNvbnN0IHByZXZCb2R5OiBRdWVyeUV2ZW50c1R5cGUgPSB7XG4gICAgICAuLi5tZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGEsXG4gICAgICB3aW5kb3dTdGFydERhdGU6IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy53aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlOiBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGFFeHRyYT8ud2luZG93RW5kRGF0ZSxcbiAgICB9O1xuXG4gICAgLy8gZml4IHByZXZCb2R5IHdpdGggbmV3IGRhdGFcbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKHByZXZCb2R5Py5pc01lZXRpbmcgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuaXNNZWV0aW5nID0gbmV3Qm9keT8uaXNNZWV0aW5nO1xuICAgIH1cblxuICAgIGlmICghKHByZXZCb2R5Py5hdHRyaWJ1dGVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkuYXR0cmlidXRlcyA9IG5ld0JvZHk/LmF0dHJpYnV0ZXM7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ud2luZG93U3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS53aW5kb3dTdGFydERhdGUgPSBuZXdCb2R5Py53aW5kb3dTdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ud2luZG93RW5kRGF0ZSkge1xuICAgICAgcHJldkJvZHkud2luZG93RW5kRGF0ZSA9IG5ld0JvZHk/LndpbmRvd0VuZERhdGU7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdmaW5kLWV2ZW50cycsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcFF1ZXJ5RXZlbnRzKFxuICAgICAgcHJldkJvZHksXG4gICAgICBwcmV2Qm9keT8ud2luZG93U3RhcnREYXRlLFxuICAgICAgcHJldkJvZHk/LndpbmRvd0VuZERhdGUsXG4gICAgICBwcmV2Qm9keT8udGltZXpvbmUsXG4gICAgICByZXNwb25zZVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzcG9uc2UyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcXVlcnkgZXZlbnRzIG1pc3NpbmcgZmllbGRzIHJldHVybmVkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBxdWVyeUV2ZW50c0NvbnRyb2xDZW50ZXIgPSBhc3luYyAoXG4gIG9wZW5haTogT3BlbkFJLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxuICB1c2VyQ3VycmVudFRpbWU6IHN0cmluZyxcbiAgcXVlcnk6ICdtaXNzaW5nX2ZpZWxkcycgfCAnY29tcGxldGVkJyB8ICdldmVudF9ub3RfZm91bmQnIHwgJ3BlbmRpbmcnXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZXNzYWdlTGVuZ3RoID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXM/Lmxlbmd0aDtcbiAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJztcbiAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgIHVzZXJNZXNzYWdlID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICB9XG4gICAgY29uc3QgdXNlcklucHV0ID0gdXNlck1lc3NhZ2U7XG5cbiAgICBjb25zdCBhdHRyaWJ1dGVzT2JqZWN0ID1cbiAgICAgIGF3YWl0IGV4dHJhY3RBdHRyaWJ1dGVzTmVlZGVkRnJvbVVzZXJJbnB1dCh1c2VySW5wdXQpO1xuXG4gICAgbGV0IGV2ZW50c1JlczogUmVzcG9uc2VBY3Rpb25UeXBlID0ge1xuICAgICAgcXVlcnk6ICdjb21wbGV0ZWQnLFxuICAgICAgZGF0YTogJycsXG4gICAgICBza2lsbDogJycsXG4gICAgICBwcmV2RGF0YToge30sXG4gICAgICBwcmV2RGF0YUV4dHJhOiB7fSxcbiAgICB9O1xuXG4gICAgc3dpdGNoIChxdWVyeSkge1xuICAgICAgY2FzZSAncGVuZGluZyc6XG4gICAgICAgIGNvbnN0IGpzb25Cb2R5ID0gYXdhaXQgZ2VuZXJhdGVKU09ORGF0YUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBjb25zdCBxdWVyeURhdGUgPSBhd2FpdCBnZW5lcmF0ZVF1ZXJ5RGF0ZUZyb21Vc2VySW5wdXQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgKTtcbiAgICAgICAgZXZlbnRzUmVzID0gYXdhaXQgcHJvY2Vzc1F1ZXJ5RXZlbnRzUGVuZGluZyhcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbkJvZHksXG4gICAgICAgICAgYXR0cmlidXRlc09iamVjdCxcbiAgICAgICAgICBxdWVyeURhdGUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnbWlzc2luZ19maWVsZHMnOlxuICAgICAgICBsZXQgcHJpb3JVc2VySW5wdXQgPSAnJztcbiAgICAgICAgbGV0IHByaW9yQXNzaXN0YW50T3V0cHV0ID0gJyc7XG5cbiAgICAgICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ2Fzc2lzdGFudCcpIHtcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgICAgICBpZiAobWVzc2FnZS5jb250ZW50ICE9PSB1c2VySW5wdXQpIHtcbiAgICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghcHJpb3JVc2VySW5wdXQgfHwgIXByaW9yQXNzaXN0YW50T3V0cHV0KSB7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JVc2VySW5wdXQsICcgcHJpb3JVc2VySW5wdXQnKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvckFzc2lzdGFudE91dHB1dCwgJyBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpb3JVc2VyaW5wdXQgb3IgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBqc29uTWlzc2luZ0ZpZWxkc0JvZHkgPVxuICAgICAgICAgIGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgICApO1xuICAgICAgICBjb25zdCBxdWVyeU1pc3NpbmdGaWVsZHNEYXRlID1cbiAgICAgICAgICBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNRdWVyeURhdGVGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICAgKTtcblxuICAgICAgICBldmVudHNSZXMgPSBhd2FpdCBwcm9jZXNzUXVlcnlFdmVudHNNaXNzaW5nRmllbGRzUmV0dXJuZWQoXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHRpbWV6b25lLFxuICAgICAgICAgIGpzb25NaXNzaW5nRmllbGRzQm9keSxcbiAgICAgICAgICBhdHRyaWJ1dGVzT2JqZWN0LFxuICAgICAgICAgIHF1ZXJ5TWlzc2luZ0ZpZWxkc0RhdGUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgIH1cblxuICAgIC8vIGNvbnN0IGV2ZW50c1JlcyA9IGF3YWl0IHByb2Nlc3NRdWVyeUV2ZW50c1BlbmRpbmcodXNlcklkLCB0aW1lem9uZSwganNvbkJvZHksIGF0dHJpYnV0ZXNPYmplY3QsIHF1ZXJ5RGF0ZSwgdXNlckN1cnJlbnRUaW1lKVxuICAgIGlmIChldmVudHNSZXM/LnF1ZXJ5ID09PSAnY29tcGxldGVkJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeShcbiAgICAgICAgICBvcGVuYWksXG4gICAgICAgICAgZXZlbnRzUmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoZXZlbnRzUmVzPy5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgICAgY29uc3QgYXNzaXN0YW50TWVzc2FnZSA9XG4gICAgICAgIGF3YWl0IGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZVRvUmVxdWVzdFVzZXJGb3JNaXNzaW5nRmllbGRzKFxuICAgICAgICAgIG9wZW5haSxcbiAgICAgICAgICBldmVudHNSZXM/LmRhdGEgYXMgUmVxdWlyZWRGaWVsZHNUeXBlLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG5cbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcyc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IGV2ZW50c1Jlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IGV2ZW50c1Jlcz8ucHJldkRhdGE7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YUV4dHJhID0gZXZlbnRzUmVzPy5wcmV2RGF0YUV4dHJhO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucHJldkRhdGVKc29uQm9keSA9IGV2ZW50c1Jlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZKc29uQm9keSA9IGV2ZW50c1Jlcz8ucHJldkpzb25Cb2R5O1xuICAgIH0gZWxzZSBpZiAoZXZlbnRzUmVzPy5xdWVyeSA9PT0gJ2V2ZW50X25vdF9mb3VuZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2U6IEFzc2lzdGFudE1lc3NhZ2VUeXBlID0ge1xuICAgICAgICByb2xlOiAnYXNzaXN0YW50JyxcbiAgICAgICAgY29udGVudDogXCJPb3BzLi4uIEkgY291bGRuJ3QgZmluZCB0aGUgZXZlbnQuIFNvcnJ5IDooXCIsXG4gICAgICB9O1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJztcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnJlcXVpcmVkID0gbnVsbDtcbiAgICB9XG5cbiAgICByZXR1cm4gbWVzc2FnZUhpc3RvcnlPYmplY3Q7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBxdWVyeSBldmVudHMnKTtcbiAgfVxufTtcbiJdfQ==