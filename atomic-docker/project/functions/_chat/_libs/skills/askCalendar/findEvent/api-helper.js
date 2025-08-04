import { searchSingleEventByVectorWithDatesLanceDb, // Updated
convertEventTitleToOpenAIVector, extractAttributesNeededFromUserInput, extrapolateEndDateFromJSONData, extrapolateStartDateFromJSONData, generateAssistantMessageFromAPIResponseForUserQuery, generateAssistantMessageToRequestUserForMissingFields, generateJSONDataFromUserInput, generateMissingFieldsJSONDataFromUserInput, generateMissingFieldsQueryDateFromUserInput, generateQueryDateFromUserInput, } from '@chat/_libs/api-helper';
import { listSortedObjectsForUserGivenDatesAndAttributes } from '../api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import _ from 'lodash';
export const finalStepQueryEvent = async (body, windowStartDate, windowEndDate, timezone, response) => {
    try {
        let searchVector = [];
        if (body?.title) {
            searchVector = await convertEventTitleToOpenAIVector(body?.title);
        }
        if (!windowStartDate) {
            windowStartDate = dayjs().subtract(2, 'w').format();
        }
        if (!windowEndDate) {
            windowEndDate = dayjs().add(4, 'w').format();
        }
        let searchResult = null; // Changed type
        let events = [];
        if (searchVector?.length > 0) {
            searchResult = await searchSingleEventByVectorWithDatesLanceDb(body.userId, searchVector, windowStartDate, windowEndDate); // Updated call
        }
        const id = searchResult?.id; // Updated ID extraction
        let objectsWithAttributes;
        if (id) {
            objectsWithAttributes =
                await listSortedObjectsForUserGivenDatesAndAttributes(body?.userId, body?.windowStartDate, body?.windowEndDate, body?.attributes, body?.isMeeting, [id]);
        }
        else {
            objectsWithAttributes =
                await listSortedObjectsForUserGivenDatesAndAttributes(body?.userId, body?.windowStartDate, body?.windowEndDate, body?.attributes, body?.isMeeting);
        }
        events = objectsWithAttributes?.events;
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
                    // queryData += `id: ${event?.id}, `
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
                                queryData += `name: ${attendee?.name}`;
                                queryData += `email: ${attendee?.emails?.find((e) => !!e?.primary)?.value}`;
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
        console.log(queryData, queryData?.length, ' queryData, length');
        // success response
        response.query = 'completed';
        response.data = queryData;
        return response;
    }
    catch (e) {
        console.log(e, ' unable to do final step query event');
    }
};
export const processQueryEventPending = async (userId, timezone, jsonBody, 
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
        console.log(body, ' body inside find-event');
        // validate
        const response = {
            query: '',
            data: {},
            skill: 'queryEvent',
        };
        // validate remaining required fields
        // const missingFields: RequiredFieldsType = {
        //     required: []
        // }
        // if (!body?.title) {
        //     response.query = 'missing_fields'
        //     missingFields.required.push(requiredFields.required?.[0])
        //     response.data = missingFields
        //     response.prevData = body
        //     response.prevDataExtra = {
        //         windowStartDate,
        //         windowEndDate,
        //     }
        // }
        // if (response.query === 'missing_fields') {
        //     return response
        // }
        const response2 = await finalStepQueryEvent(body, windowStartDate, windowEndDate, timezone, response);
        return response2;
        // const searchVector = await convertEventTitleToOpenAIVector(body?.title)
        // const res = await allEventWithDatesOpenSearch(userId, searchVector, windowStartDate, windowEndDate)
        // const id = res?.hits?.hits?.[0]?._id
        // // validate found event
        // if (!id) {
        //     response.query = 'event_not_found'
        //     return response
        // }
        // const objectsWithAttributes = await listSortedObjectsForUserGivenDatesAndAttributes(
        //     body?.userId,
        //     body?.windowStartDate,
        //     body?.windowEndDate,
        //     body?.attributes,
        //     body?.isMeeting,
        //     [id],
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
        //                     queryData += `name: ${attendee?.name}`
        //                     queryData += `email: ${attendee?.emails?.find(e => (!!e?.primary))?.value}`
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
        console.log(e, ' unable to process query event');
    }
};
export const processQueryEventMissingFieldsReturned = async (userId, timezone, jsonBody, 
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
            skill: 'queryEvent',
        };
        // validate remaining required fields
        // const missingFields: RequiredFieldsType = {
        //     required: []
        // }
        // if (!prevBody?.title) {
        //     response.query = 'missing_fields'
        //     missingFields.required.push(requiredFields.required?.[0])
        //     response.data = missingFields
        //     response.prevData = prevBody
        //     response.prevDataExtra = {
        //         windowStartDate,
        //         windowEndDate,
        //     }
        // }
        // if (response.query === 'missing_fields') {
        //     return response
        // }
        const response2 = await finalStepQueryEvent(prevBody, prevBody?.windowStartDate, prevBody?.windowEndDate, prevBody?.timezone, response);
        return response2;
    }
    catch (e) {
        console.log(e, ' unable to process query event missing fields returned');
    }
};
export const askEventControlCenter = async (openai, userId, timezone, messageHistoryObject, userCurrentTime, query) => {
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
        console.log(messageHistoryObject, ' messageHistoryObject before api call');
        // generateJSONDataFromUserInput
        const attributesObject = await extractAttributesNeededFromUserInput(userInput);
        let eventRes = {
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
                eventRes = await processQueryEventPending(userId, timezone, jsonBody, attributesObject, queryDate, userCurrentTime);
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
                eventRes = await processQueryEventMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, attributesObject, queryMissingFieldsDate, userCurrentTime, messageHistoryObject);
                break;
        }
        if (eventRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, eventRes.data, messageHistoryObject);
            console.log(assistantMessage, ' assistantMessage');
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'completed';
            messageHistoryObject.required = null;
        }
        else if (eventRes?.query === 'missing_fields') {
            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, eventRes?.data, messageHistoryObject);
            messageHistoryObject.messages.push(assistantMessage);
            messageHistoryObject.query = 'missing_fields';
            messageHistoryObject.required = eventRes?.data;
            messageHistoryObject.prevData = eventRes?.prevData;
            messageHistoryObject.prevDataExtra = eventRes?.prevDataExtra;
            messageHistoryObject.prevDateJsonBody = eventRes?.prevDateJsonBody;
            messageHistoryObject.prevJsonBody = eventRes?.prevJsonBody;
        }
        else if (eventRes?.query === 'event_not_found') {
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
        console.log(e, ' unable to process ask event inside control center');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBR0EsT0FBTyxFQUNMLHlDQUF5QyxFQUFFLFVBQVU7QUFDckQsK0JBQStCLEVBQy9CLG9DQUFvQyxFQUNwQyw4QkFBOEIsRUFDOUIsZ0NBQWdDLEVBQ2hDLG1EQUFtRCxFQUNuRCxxREFBcUQsRUFDckQsNkJBQTZCLEVBQzdCLDBDQUEwQyxFQUMxQywyQ0FBMkMsRUFDM0MsOEJBQThCLEdBQy9CLE1BQU0sd0JBQXdCLENBQUM7QUFDaEMsT0FBTyxFQUFFLCtDQUErQyxFQUFFLE1BQU0sZUFBZSxDQUFDO0FBRWhGLE9BQU8sRUFBRSxLQUFLLEVBQUUsTUFBTSxpQ0FBaUMsQ0FBQztBQUd4RCxPQUFPLENBQUMsTUFBTSxRQUFRLENBQUM7QUFhdkIsTUFBTSxDQUFDLE1BQU0sbUJBQW1CLEdBQUcsS0FBSyxFQUN0QyxJQUFvQixFQUNwQixlQUF1QixFQUN2QixhQUFxQixFQUNyQixRQUFnQixFQUNoQixRQUFhLEVBQ2IsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILElBQUksWUFBWSxHQUFhLEVBQUUsQ0FBQztRQUNoQyxJQUFJLElBQUksRUFBRSxLQUFLLEVBQUUsQ0FBQztZQUNoQixZQUFZLEdBQUcsTUFBTSwrQkFBK0IsQ0FBQyxJQUFJLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDcEUsQ0FBQztRQUVELElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztZQUNyQixlQUFlLEdBQUcsS0FBSyxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUN0RCxDQUFDO1FBRUQsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO1lBQ25CLGFBQWEsR0FBRyxLQUFLLEVBQUUsQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQy9D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SSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLFFBQVEsQ0FBQyxFQUFFLENBQUM7Z0NBQ2xELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQzs0QkFDbkQsQ0FBQzt3QkFDSCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLFVBQVUsRUFBRSxDQUFDOzRCQUNuQyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssVUFBVSxDQUFDLEVBQUUsQ0FBQztnQ0FDcEQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssWUFBWSxFQUFFLENBQUM7NEJBQ3JDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxZQUFZLENBQUMsRUFBRSxDQUFDO2dDQUN0RCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxZQUFZLEVBQUUsQ0FBQzs0QkFDckMsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLFlBQVksQ0FBQyxFQUFFLENBQUM7Z0NBQ3RELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQzs0QkFDbkQsQ0FBQzt3QkFDSCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLGFBQWEsRUFBRSxDQUFDOzRCQUN0QyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssYUFBYSxDQUFDLEVBQUUsQ0FBQztnQ0FDdkQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssWUFBWSxFQUFFLENBQUM7NEJBQ3JDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxZQUFZLENBQUMsRUFBRSxDQUFDO2dDQUN0RCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxTQUFTLEVBQUUsQ0FBQzs0QkFDbEMsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLFNBQVMsQ0FBQyxFQUFFLENBQUM7Z0NBQ25ELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQzs0QkFDbkQsQ0FBQzt3QkFDSCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLFlBQVksRUFBRSxDQUFDOzRCQUNyQyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssWUFBWSxDQUFDLEVBQUUsQ0FBQztnQ0FDdEQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7NkJBQU0sSUFBSSxRQUFRLEtBQUssY0FBYyxFQUFFLENBQUM7NEJBQ3ZDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxjQUFjLENBQUMsRUFBRSxDQUFDO2dDQUN4RCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssS0FBSyxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7NEJBQ25ELENBQUM7d0JBQ0gsQ0FBQzs2QkFBTSxJQUFJLFFBQVEsS0FBSyxjQUFjLEVBQUUsQ0FBQzs0QkFDdkMsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLGNBQWMsQ0FBQyxFQUFFLENBQUM7Z0NBQ3hELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxLQUFLLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQzs0QkFDbkQsQ0FBQzt3QkFDSCxDQUFDOzZCQUFNLElBQUksUUFBUSxLQUFLLFVBQVUsRUFBRSxDQUFDOzRCQUNuQyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssVUFBVSxDQUFDLEVBQUUsQ0FBQztnQ0FDcEQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLEtBQUssQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDOzRCQUNuRCxDQUFDO3dCQUNILENBQUM7b0JBQ0gsQ0FBQztnQkFDSCxDQUFDO2dCQUVELElBQUksS0FBSyxFQUFFLFlBQVksRUFBRSxDQUFDO29CQUN4QixNQUFNLFlBQVksR0FBRyxXQUFXLEVBQUUsSUFBSSxDQUNwQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEVBQUUsS0FBSyxLQUFLLEVBQUUsWUFBWSxDQUNyQyxDQUFDO29CQUVGLElBQUksWUFBWSxFQUFFLEVBQUUsRUFBRSxDQUFDO3dCQUNyQixTQUFTLElBQUksMkJBQTJCLENBQUM7d0JBQ3pDLFNBQVMsSUFBSSxTQUFTLFlBQVksRUFBRSxJQUFJLElBQUksQ0FBQzt3QkFDN0MsU0FBUyxJQUFJLFFBQVEsWUFBWSxFQUFFLEdBQUcsSUFBSSxDQUFDO3dCQUUzQyxLQUFLLE1BQU0sUUFBUSxJQUFJLFlBQVksRUFBRSxDQUFDOzRCQUNwQyxJQUFJLFFBQVEsS0FBSyxPQUFPLEVBQUUsQ0FBQztnQ0FDekIsSUFBSSxJQUFJLEVBQUUsVUFBVSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxLQUFLLGtCQUFrQixDQUFDLEVBQUUsQ0FBQztvQ0FDNUQsU0FBUyxJQUFJLEdBQUcsUUFBUSxLQUFLLFlBQVksQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDO2dDQUMxRCxDQUFDOzRCQUNILENBQUM7aUNBQU0sSUFBSSxRQUFRLEtBQUssU0FBUyxFQUFFLENBQUM7Z0NBQ2xDLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxvQkFBb0IsQ0FBQyxFQUFFLENBQUM7b0NBQzlELFNBQVMsSUFBSSxHQUFHLFFBQVEsS0FBSyxZQUFZLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQztnQ0FDMUQsQ0FBQzs0QkFDSCxDQUFDO2lDQUFNLElBQUksUUFBUSxLQUFLLFVBQVUsRUFBRSxDQUFDO2dDQUNuQyxJQUNFLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUsscUJBQXFCLENBQUMsRUFDMUQsQ0FBQztvQ0FDRCxTQUFTLElBQUksR0FBRyxRQUFRLEtBQUssWUFBWSxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7Z0NBQzFELENBQUM7NEJBQ0gsQ0FBQzt3QkFDSCxDQUFDO3dCQUVELElBQUksU0FBUyxFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQzs0QkFDMUIsU0FBUyxJQUFJLGNBQWMsQ0FBQzs0QkFFNUIsS0FBSyxNQUFNLFFBQVEsSUFBSSxTQUFTLEVBQUUsQ0FBQztnQ0FDakMsU0FBUyxJQUFJLFNBQVMsUUFBUSxFQUFFLElBQUksRUFBRSxDQUFDO2dDQUN2QyxTQUFTLElBQUksVUFBVSxRQUFRLEVBQUUsTUFBTSxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUMsRUFBRSxPQUFPLENBQUMsRUFBRSxLQUFLLEVBQUUsQ0FBQzs0QkFDOUUsQ0FBQzt3QkFDSCxDQUFDO29CQUNILENBQUM7Z0JBQ0gsQ0FBQztnQkFFRCxJQUFJLEtBQUssRUFBRSxNQUFNLEVBQUUsQ0FBQztvQkFDbEIsTUFBTSxZQUFZLEdBQUcsS0FBSyxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLEVBQUUsS0FBSyxLQUFLLEVBQUUsTUFBTSxDQUFDLENBQUM7b0JBRWpFLElBQUksWUFBWSxFQUFFLEVBQUUsRUFBRSxDQUFDO3dCQUNyQixTQUFTLElBQUkscUJBQXFCLENBQUM7d0JBQ25DLFNBQVMsSUFBSSxHQUFHLFlBQVksRUFBRSxLQUFLLElBQUksQ0FBQzt3QkFFeEMsS0FBSyxNQUFNLFFBQVEsSUFBSSxZQUFZLEVBQUUsQ0FBQzs0QkFDcEMsSUFBSSxRQUFRLEtBQUssTUFBTSxFQUFFLENBQUM7Z0NBQ3hCLElBQUksSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsS0FBSyxlQUFlLENBQUMsRUFBRSxDQUFDO29DQUN6RCxTQUFTLElBQUksU0FBUyxZQUFZLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQztnQ0FDbkQsQ0FBQzs0QkFDSCxDQUFDO2lDQUFNLElBQUksUUFBUSxLQUFLLFFBQVEsRUFBRSxDQUFDO2dDQUNqQyxJQUFJLElBQUksRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEtBQUssYUFBYSxDQUFDLEVBQUUsQ0FBQztvQ0FDdkQsU0FBUyxJQUFJLFdBQVcsWUFBWSxDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUM7Z0NBQ3JELENBQUM7NEJBQ0gsQ0FBQzt3QkFDSCxDQUFDO29CQUNILENBQUM7Z0JBQ0gsQ0FBQztnQkFFRCxTQUFTLElBQUksSUFBSSxDQUFDO1lBQ3BCLENBQUM7WUFFRCxTQUFTLElBQUksTUFBTSxDQUFDO1FBQ3RCLENBQUM7UUFFRCxJQUFJLEtBQUssR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUNkLFNBQVMsSUFBSSxVQUFVLEtBQUssRUFBRSxDQUFDO1FBQ2pDLENBQUM7UUFFRCxPQUFPLENBQUMsR0FBRyxDQUFDLFNBQVMsRUFBRSxTQUFTLEVBQUUsTUFBTSxFQUFFLG9CQUFvQixDQUFDLENBQUM7UUFDaEUsbUJBQW1CO1FBQ25CLFFBQVEsQ0FBQyxLQUFLLEdBQUcsV0FBVyxDQUFDO1FBRTdCLFFBQVEsQ0FBQyxJQUFJLEdBQUcsU0FBUyxDQUFDO1FBRTFCLE9BQU8sUUFBUSxDQUFDO0lBQ2xCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsc0NBQXNDLENBQUMsQ0FBQztJQUN6RCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsTUFBTSxDQUFDLE1BQU0sd0JBQXdCLEdBQUcsS0FBSyxFQUMzQyxNQUFjLEVBQ2QsUUFBZ0IsRUFDaEIsUUFBNkI7QUFDN0Isc0NBQXNDO0FBQ3RDLGdCQUFzRCxFQUN0RCxpQkFBaUQsRUFDakQsV0FBbUIsRUFDVSxFQUFFO0lBQy9CLElBQUksQ0FBQztRQUNILElBQUksZUFBZSxHQUFHLGdDQUFnQyxDQUNwRCxXQUFXLEVBQ1gsUUFBUSxFQUNSLGlCQUFpQixFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQ25DLGlCQUFpQixFQUFFLFVBQVUsRUFBRSxLQUFLLEVBQ3BDLGlCQUFpQixFQUFFLFVBQVUsRUFBRSxHQUFHLEVBQ2xDLFNBQVMsRUFDVCxpQkFBaUIsRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUNuQyxpQkFBaUIsRUFBRSxVQUFVLEVBQUUsTUFBTSxFQUNyQyxpQkFBaUIsRUFBRSxVQUFVLEVBQUUsSUFBSSxFQUNuQyxpQkFBaUIsRUFBRSxVQUFVLEVBQUUseUJBQXlCLEVBQ3hELGlCQUFpQixFQUFFLFVBQVUsRUFBRSxtQkFBbUIsQ0FDbkQsQ0FBQztRQUVGLElBQUksYUFBYSxHQUFHLDhCQUE4QixDQUNoRCxXQUFXLEVBQ1gsUUFBUSxFQUNSLGlCQUFpQixFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQ2pDLGlCQUFpQixFQUFFLFFBQVEsRUFBRSxLQUFLLEVBQ2xDLGlCQUFpQixFQUFFLFFBQVEsRUFBRSxHQUFHLEVBQ2hDLFNBQVMsRUFDVCxpQkFBaUIsRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUNqQyxpQkFBaUIsRUFBRSxRQUFRLEVBQUUsTUFBTSxFQUNuQyxpQkFBaUIsRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUNqQyxpQkFBaUIsRUFBRSxRQUFRLEVBQUUseUJBQXlCLEVBQ3RELGlCQUFpQixFQUFFLFFBQVEsRUFBRSxtQkFBbUIsQ0FDakQsQ0FBQztRQUVGLElBQUksQ0FBQyxlQUFlLEVBQUUsQ0FBQztZQUNyQixlQUFlLEdBQUcsS0FBSyxFQUFFLENBQUMsUUFBUSxDQUFDLENBQUMsRUFBRSxHQUFHLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUN0RCxDQUFDO1FBRUQsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO1lBQ25CLGFBQWEsR0FBRyxLQUFLLEVBQUUsQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQy9DLENBQUM7UUFFRCxNQUFNLElBQUksR0FBbUI7WUFDM0IsTUFBTTtZQUNOLFFBQVE7WUFDUixLQUFLLEVBQ0gsUUFBUSxFQUFFLE1BQU0sRUFBRSxLQUFLO2dCQUN2QixRQUFRLEVBQUUsTUFBTSxFQUFFLE9BQU87Z0JBQ3pCLFFBQVEsRUFBRSxNQUFNLEVBQUUsV0FBVztnQkFDN0IsUUFBUSxFQUFFLE1BQU0sRUFBRSxRQUFRLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxJQUFJO1lBQ3ZDLFNBQVMsRUFBRSxnQkFBZ0IsRUFBRSxTQUFTO1lBQ3RDLFVBQVUsRUFBRSxnQkFBZ0IsRUFBRSxVQUFVO1lBQ3hDLGVBQWU7WUFDZixhQUFhO1NBQ2QsQ0FBQztRQUVGLE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxFQUFFLHlCQUF5QixDQUFDLENBQUM7UUFDN0MsV0FBVztRQUNYLE1BQU0sUUFBUSxHQUFRO1lBQ3BCLEtBQUssRUFBRSxFQUFFO1lBQ1QsSUFBSSxFQUFFLEVBQUU7WUFDUixLQUFLLEVBQUUsWUFBWTtTQUNwQixDQUFDO1FBRUYscUNBQXFDO1FBQ3JDLDhDQUE4QztRQUM5QyxtQkFBbUI7UUFDbkIsSUFBSTtRQUNKLHNCQUFzQjtRQUN0Qix3Q0FBd0M7UUFDeEMsZ0VBQWdFO1FBQ2hFLG9DQUFvQztRQUNwQywrQkFBK0I7UUFDL0IsaUNBQWlDO1FBQ2pDLDJCQUEyQjtRQUMzQix5QkFBeUI7UUFDekIsUUFBUTtRQUNSLElBQUk7UUFFSiw2Q0FBNkM7UUFDN0Msc0JBQXNCO1FBQ3RCLElBQUk7UUFFSixNQUFNLFNBQVMsR0FBRyxNQUFNLG1CQUFtQixDQUN6QyxJQUFJLEVBQ0osZUFBZSxFQUNmLGFBQWEsRUFDYixRQUFRLEVBQ1IsUUFBUSxDQUNULENBQUM7UUFFRixPQUFPLFNBQVMsQ0FBQztRQUNqQiwwRUFBMEU7UUFFMUUsc0dBQXNHO1FBRXRHLHVDQUF1QztRQUV2QywwQkFBMEI7UUFDMUIsYUFBYTtRQUNiLHlDQUF5QztRQUN6QyxzQkFBc0I7UUFDdEIsSUFBSTtRQUVKLHVGQUF1RjtRQUN2RixvQkFBb0I7UUFDcEIsNkJBQTZCO1FBQzdCLDJCQUEyQjtRQUMzQix3QkFBd0I7UUFDeEIsdUJBQXVCO1FBQ3ZCLFlBQVk7UUFDWixJQUFJO1FBRUosK0NBQStDO1FBQy9DLHlEQUF5RDtRQUN6RCxxREFBcUQ7UUFDckQsNkNBQTZDO1FBQzdDLDZDQUE2QztRQUU3QyxxQkFBcUI7UUFFckIsZ0JBQWdCO1FBQ2hCLG1JQUFtSTtRQUVuSSxzQ0FBc0M7UUFFdEMsZ0tBQWdLO1FBRWhLLGtFQUFrRTtRQUNsRSx3QkFBd0I7UUFFeEIsNENBQTRDO1FBQzVDLGtDQUFrQztRQUVsQyxvRUFBb0U7UUFDcEUscUZBQXFGO1FBQ3JGLGdGQUFnRjtRQUVoRiw2REFBNkQ7UUFDN0QsdUJBQXVCO1FBQ3ZCLFlBQVk7UUFFWiwwQ0FBMEM7UUFFMUMsZ0VBQWdFO1FBQ2hFLHFFQUFxRTtRQUNyRSxvREFBb0Q7UUFDcEQsMkJBQTJCO1FBQzNCLGdCQUFnQjtRQUVoQiwyQ0FBMkM7UUFFM0MsdUVBQXVFO1FBQ3ZFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsaURBQWlEO1FBQ2pELHNFQUFzRTtRQUN0RSwyQkFBMkI7UUFDM0IscURBQXFEO1FBQ3JELDJCQUEyQjtRQUMzQixtREFBbUQ7UUFDbkQsMkJBQTJCO1FBQzNCLDBEQUEwRDtRQUUxRCwrRUFBK0U7UUFDL0UsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQixvREFBb0Q7UUFFcEQseUVBQXlFO1FBQ3pFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsaURBQWlEO1FBRWpELHNFQUFzRTtRQUN0RSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLG9EQUFvRDtRQUVwRCwyQkFBMkI7UUFDM0Isa0RBQWtEO1FBRWxELHVFQUF1RTtRQUN2RSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLG9EQUFvRDtRQUVwRCx5RUFBeUU7UUFDekUsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQixzREFBc0Q7UUFFdEQsMkVBQTJFO1FBQzNFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsc0RBQXNEO1FBRXRELDJFQUEyRTtRQUMzRSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLHVEQUF1RDtRQUV2RCw0RUFBNEU7UUFDNUUsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQixzREFBc0Q7UUFFdEQsMkVBQTJFO1FBQzNFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsbURBQW1EO1FBRW5ELHdFQUF3RTtRQUN4RSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLHNEQUFzRDtRQUV0RCwyRUFBMkU7UUFDM0UsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQix3REFBd0Q7UUFFeEQsNkVBQTZFO1FBQzdFLHVFQUF1RTtRQUN2RSxvQkFBb0I7UUFDcEIsd0RBQXdEO1FBRXhELDZFQUE2RTtRQUM3RSx1RUFBdUU7UUFDdkUsb0JBQW9CO1FBQ3BCLG9EQUFvRDtRQUVwRCx5RUFBeUU7UUFDekUsdUVBQXVFO1FBQ3ZFLG9CQUFvQjtRQUNwQixnQkFBZ0I7UUFFaEIsWUFBWTtRQUVaLHVGQUF1RjtRQUV2RixrQ0FBa0M7UUFDbEMsdURBQXVEO1FBQ3ZELDJEQUEyRDtRQUMzRCx5REFBeUQ7UUFFekQscURBQXFEO1FBQ3JELDhDQUE4QztRQUU5QyxxRkFBcUY7UUFDckYsa0ZBQWtGO1FBQ2xGLHdCQUF3QjtRQUN4Qix1REFBdUQ7UUFFdkQsdUZBQXVGO1FBQ3ZGLGtGQUFrRjtRQUNsRix3QkFBd0I7UUFDeEIsd0RBQXdEO1FBRXhELHdGQUF3RjtRQUN4RixrRkFBa0Y7UUFDbEYsd0JBQXdCO1FBQ3hCLG9CQUFvQjtRQUNwQixnQkFBZ0I7UUFFaEIsMkNBQTJDO1FBQzNDLDhDQUE4QztRQUU5QyxzREFBc0Q7UUFDdEQsNkRBQTZEO1FBQzdELGtHQUFrRztRQUNsRyxvQkFBb0I7UUFDcEIsZ0JBQWdCO1FBQ2hCLFlBQVk7UUFFWiwyRUFBMkU7UUFFM0Usa0NBQWtDO1FBQ2xDLGlEQUFpRDtRQUNqRCxzREFBc0Q7UUFFdEQscURBQXFEO1FBQ3JELDZDQUE2QztRQUU3QyxrRkFBa0Y7UUFDbEYsMkVBQTJFO1FBQzNFLHdCQUF3QjtRQUN4QixzREFBc0Q7UUFFdEQsZ0ZBQWdGO1FBQ2hGLDZFQUE2RTtRQUM3RSx3QkFBd0I7UUFDeEIsb0JBQW9CO1FBQ3BCLGdCQUFnQjtRQUNoQixZQUFZO1FBRVosNEJBQTRCO1FBQzVCLFFBQVE7UUFFUiwwQkFBMEI7UUFDMUIsSUFBSTtRQUVKLG1CQUFtQjtRQUNuQixxQ0FBcUM7UUFDckMsSUFBSTtRQUVKLHNCQUFzQjtRQUN0QiwrQkFBK0I7UUFFL0IsNEJBQTRCO1FBRTVCLGtCQUFrQjtJQUNwQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLGdDQUFnQyxDQUFDLENBQUM7SUFDbkQsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLHNDQUFzQyxHQUFHLEtBQUssRUFDekQsTUFBYyxFQUNkLFFBQWdCLEVBQ2hCLFFBQTZCO0FBQzdCLHNDQUFzQztBQUN0QyxnQkFBc0QsRUFDdEQsaUJBQWlELEVBQ2pELFdBQW1CLEVBQ25CLG9CQUE2QyxFQUM3QyxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsSUFBSSxlQUFlLEdBQUcsZ0NBQWdDLENBQ3BELFdBQVcsRUFDWCxRQUFRLEVBQ1IsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLElBQUksRUFDbkMsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLEtBQUssRUFDcEMsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLEdBQUcsRUFDbEMsU0FBUyxFQUNULGlCQUFpQixFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQ25DLGlCQUFpQixFQUFFLFVBQVUsRUFBRSxNQUFNLEVBQ3JDLGlCQUFpQixFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQ25DLGlCQUFpQixFQUFFLFVBQVUsRUFBRSx5QkFBeUIsRUFDeEQsaUJBQWlCLEVBQUUsVUFBVSxFQUFFLG1CQUFtQixDQUNuRCxDQUFDO1FBRUYsSUFBSSxhQUFhLEdBQUcsOEJBQThCLENBQ2hELFdBQVcsRUFDWCxRQUFRLEVBQ1IsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLElBQUksRUFDakMsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLEtBQUssRUFDbEMsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLEdBQUcsRUFDaEMsU0FBUyxFQUNULGlCQUFpQixFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQ2pDLGlCQUFpQixFQUFFLFFBQVEsRUFBRSxNQUFNLEVBQ25DLGlCQUFpQixFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQ2pDLGlCQUFpQixFQUFFLFFBQVEsRUFBRSx5QkFBeUIsRUFDdEQsaUJBQWlCLEVBQUUsUUFBUSxFQUFFLG1CQUFtQixDQUNqRCxDQUFDO1FBRUYsSUFBSSxDQUFDLGVBQWUsRUFBRSxDQUFDO1lBQ3JCLGVBQWUsR0FBRyxLQUFLLEVBQUUsQ0FBQyxRQUFRLENBQUMsQ0FBQyxFQUFFLEdBQUcsQ0FBQyxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQ3RELENBQUM7UUFFRCxJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7WUFDbkIsYUFBYSxHQUFHLEtBQUssRUFBRSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDL0MsQ0FBQztRQUVELE1BQU0sT0FBTyxHQUFtQjtZQUM5QixNQUFNO1lBQ04sUUFBUTtZQUNSLEtBQUssRUFDSCxRQUFRLEVBQUUsTUFBTSxFQUFFLEtBQUs7Z0JBQ3ZCLFFBQVEsRUFBRSxNQUFNLEVBQUUsT0FBTztnQkFDekIsUUFBUSxFQUFFLE1BQU0sRUFBRSxXQUFXO2dCQUM3QixRQUFRLEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFLElBQUk7Z0JBQ3JDLG9CQUFvQixFQUFFLFlBQVksRUFBRSxNQUFNLEVBQUUsS0FBSztnQkFDakQsb0JBQW9CLEVBQUUsWUFBWSxFQUFFLE1BQU0sRUFBRSxPQUFPO2dCQUNuRCxvQkFBb0IsRUFBRSxZQUFZLEVBQUUsTUFBTSxFQUFFLFdBQVc7Z0JBQ3ZELG9CQUFvQixFQUFFLFlBQVksRUFBRSxNQUFNLEVBQUUsUUFBUSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUUsSUFBSTtZQUNqRSxTQUFTLEVBQUUsZ0JBQWdCLEVBQUUsU0FBUztZQUN0QyxVQUFVLEVBQUUsZ0JBQWdCLEVBQUUsVUFBVTtZQUN4QyxlQUFlO1lBQ2YsYUFBYTtTQUNkLENBQUM7UUFFRixNQUFNLFFBQVEsR0FBbUI7WUFDL0IsR0FBRyxvQkFBb0IsRUFBRSxRQUFRO1lBQ2pDLGVBQWUsRUFBRSxvQkFBb0IsRUFBRSxhQUFhLEVBQUUsZUFBZTtZQUNyRSxhQUFhLEVBQUUsb0JBQW9CLEVBQUUsYUFBYSxFQUFFLGFBQWE7U0FDbEUsQ0FBQztRQUVGLDZCQUE2QjtRQUM3QixJQUFJLENBQUMsUUFBUSxFQUFFLE1BQU0sRUFBRSxDQUFDO1lBQ3RCLFFBQVEsQ0FBQyxNQUFNLEdBQUcsTUFBTSxJQUFJLE9BQU8sRUFBRSxNQUFNLENBQUM7UUFDOUMsQ0FBQztRQUVELElBQUksQ0FBQyxRQUFRLEVBQUUsUUFBUSxFQUFFLENBQUM7WUFDeEIsUUFBUSxDQUFDLFFBQVEsR0FBRyxRQUFRLElBQUksT0FBTyxFQUFFLFFBQVEsQ0FBQztRQUNwRCxDQUFDO1FBRUQsSUFBSSxDQUFDLFFBQVEsRUFBRSxLQUFLLEVBQUUsQ0FBQztZQUNyQixRQUFRLENBQUMsS0FBSyxHQUFHLE9BQU8sRUFBRSxLQUFLLENBQUM7UUFDbEMsQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLFNBQVMsS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUN0QyxRQUFRLENBQUMsU0FBUyxHQUFHLE9BQU8sRUFBRSxTQUFTLENBQUM7UUFDMUMsQ0FBQztRQUVELElBQUksQ0FBQyxDQUFDLFFBQVEsRUFBRSxVQUFVLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7WUFDeEMsUUFBUSxDQUFDLFVBQVUsR0FBRyxPQUFPLEVBQUUsVUFBVSxDQUFDO1FBQzVDLENBQUM7UUFFRCxJQUFJLENBQUMsUUFBUSxFQUFFLGVBQWUsRUFBRSxDQUFDO1lBQy9CLFFBQVEsQ0FBQyxlQUFlLEdBQUcsT0FBTyxFQUFFLGVBQWUsQ0FBQztRQUN0RCxDQUFDO1FBRUQsSUFBSSxDQUFDLFFBQVEsRUFBRSxhQUFhLEVBQUUsQ0FBQztZQUM3QixRQUFRLENBQUMsYUFBYSxHQUFHLE9BQU8sRUFBRSxhQUFhLENBQUM7UUFDbEQsQ0FBQztRQUVELE1BQU0sUUFBUSxHQUFRO1lBQ3BCLEtBQUssRUFBRSxFQUFFO1lBQ1QsSUFBSSxFQUFFLEVBQUU7WUFDUixLQUFLLEVBQUUsWUFBWTtTQUNwQixDQUFDO1FBRUYscUNBQXFDO1FBQ3JDLDhDQUE4QztRQUM5QyxtQkFBbUI7UUFDbkIsSUFBSTtRQUVKLDBCQUEwQjtRQUMxQix3Q0FBd0M7UUFDeEMsZ0VBQWdFO1FBQ2hFLG9DQUFvQztRQUNwQyxtQ0FBbUM7UUFDbkMsaUNBQWlDO1FBQ2pDLDJCQUEyQjtRQUMzQix5QkFBeUI7UUFDekIsUUFBUTtRQUNSLElBQUk7UUFFSiw2Q0FBNkM7UUFDN0Msc0JBQXNCO1FBQ3RCLElBQUk7UUFFSixNQUFNLFNBQVMsR0FBRyxNQUFNLG1CQUFtQixDQUN6QyxRQUFRLEVBQ1IsUUFBUSxFQUFFLGVBQWUsRUFDekIsUUFBUSxFQUFFLGFBQWEsRUFDdkIsUUFBUSxFQUFFLFFBQVEsRUFDbEIsUUFBUSxDQUNULENBQUM7UUFFRixPQUFPLFNBQVMsQ0FBQztJQUNuQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHdEQUF3RCxDQUFDLENBQUM7SUFDM0UsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLE1BQU0sQ0FBQyxNQUFNLHFCQUFxQixHQUFHLEtBQUssRUFDeEMsTUFBYyxFQUNkLE1BQWMsRUFDZCxRQUFnQixFQUNoQixvQkFBNkMsRUFDN0MsZUFBdUIsRUFDdkIsS0FBcUUsRUFDckUsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sYUFBYSxHQUFHLG9CQUFvQixDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7UUFDNUQsSUFBSSxXQUFXLEdBQUcsRUFBRSxDQUFDO1FBQ3JCLEtBQUssSUFBSSxDQUFDLEdBQUcsYUFBYSxFQUFFLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztZQUN2QyxNQUFNLE9BQU8sR0FBRyxvQkFBb0IsQ0FBQyxRQUFRLENBQUMsQ0FBQyxHQUFHLENBQUMsQ0FBQyxDQUFDO1lBRXJELElBQUksT0FBTyxDQUFDLElBQUksS0FBSyxNQUFNLEVBQUUsQ0FBQztnQkFDNUIsV0FBVyxHQUFHLE9BQU8sQ0FBQyxPQUFPLENBQUM7Z0JBQzlCLE1BQU07WUFDUixDQUFDO1FBQ0gsQ0FBQztRQUNELE1BQU0sU0FBUyxHQUFHLFdBQVcsQ0FBQztRQUU5QixPQUFPLENBQUMsR0FBRyxDQUFDLG9CQUFvQixFQUFFLHVDQUF1QyxDQUFDLENBQUM7UUFFM0UsZ0NBQWdDO1FBRWhDLE1BQU0sZ0JBQWdCLEdBQ3BCLE1BQU0sb0NBQW9DLENBQUMsU0FBUyxDQUFDLENBQUM7UUFFeEQsSUFBSSxRQUFRLEdBQXVCO1lBQ2pDLEtBQUssRUFBRSxXQUFXO1lBQ2xCLElBQUksRUFBRSxFQUFFO1lBQ1IsS0FBSyxFQUFFLEVBQUU7WUFDVCxRQUFRLEVBQUUsRUFBRTtZQUNaLGFBQWEsRUFBRSxFQUFFO1NBQ2xCLENBQUM7UUFFRixRQUFRLEtBQUssRUFBRSxDQUFDO1lBQ2QsS0FBSyxTQUFTO2dCQUNaLE1BQU0sUUFBUSxHQUFHLE1BQU0sNkJBQTZCLENBQ2xELFNBQVMsRUFDVCxlQUFlLENBQ2hCLENBQUM7Z0JBQ0YsTUFBTSxTQUFTLEdBQUcsTUFBTSw4QkFBOEIsQ0FDcEQsTUFBTSxFQUNOLFFBQVEsRUFDUixTQUFTLEVBQ1QsZUFBZSxDQUNoQixDQUFDO2dCQUNGLFFBQVEsR0FBRyxNQUFNLHdCQUF3QixDQUN2QyxNQUFNLEVBQ04sUUFBUSxFQUNSLFFBQVEsRUFDUixnQkFBZ0IsRUFDaEIsU0FBUyxFQUNULGVBQWUsQ0FDaEIsQ0FBQztnQkFDRixNQUFNO1lBQ1IsS0FBSyxnQkFBZ0I7Z0JBQ25CLElBQUksY0FBYyxHQUFHLEVBQUUsQ0FBQztnQkFDeEIsSUFBSSxvQkFBb0IsR0FBRyxFQUFFLENBQUM7Z0JBRTlCLEtBQUssSUFBSSxDQUFDLEdBQUcsYUFBYSxFQUFFLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztvQkFDdkMsTUFBTSxPQUFPLEdBQUcsb0JBQW9CLENBQUMsUUFBUSxDQUFDLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQztvQkFFckQsSUFBSSxPQUFPLENBQUMsSUFBSSxLQUFLLFdBQVcsRUFBRSxDQUFDO3dCQUNqQyxvQkFBb0IsR0FBRyxPQUFPLENBQUMsT0FBTyxDQUFDO3dCQUN2QyxTQUFTO29CQUNYLENBQUM7b0JBRUQsSUFBSSxPQUFPLENBQUMsSUFBSSxLQUFLLE1BQU0sRUFBRSxDQUFDO3dCQUM1QixJQUFJLE9BQU8sQ0FBQyxPQUFPLEtBQUssU0FBUyxFQUFFLENBQUM7NEJBQ2xDLGNBQWMsR0FBRyxPQUFPLENBQUMsT0FBTyxDQUFDOzRCQUNqQyxNQUFNO3dCQUNSLENBQUM7b0JBQ0gsQ0FBQztnQkFDSCxDQUFDO2dCQUVELElBQUksQ0FBQyxjQUFjLElBQUksQ0FBQyxvQkFBb0IsRUFBRSxDQUFDO29CQUM3QyxPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWMsRUFBRSxpQkFBaUIsQ0FBQyxDQUFDO29CQUMvQyxPQUFPLENBQUMsR0FBRyxDQUFDLG9CQUFvQixFQUFFLHVCQUF1QixDQUFDLENBQUM7b0JBQzNELE1BQU0sSUFBSSxLQUFLLENBQUMsMkNBQTJDLENBQUMsQ0FBQztnQkFDL0QsQ0FBQztnQkFDRCxNQUFNLHFCQUFxQixHQUN6QixNQUFNLDBDQUEwQyxDQUM5QyxTQUFTLEVBQ1QsY0FBYyxFQUNkLG9CQUFvQixFQUNwQixlQUFlLENBQ2hCLENBQUM7Z0JBQ0osTUFBTSxzQkFBc0IsR0FDMUIsTUFBTSwyQ0FBMkMsQ0FDL0MsTUFBTSxFQUNOLFFBQVEsRUFDUixTQUFTLEVBQ1QsY0FBYyxFQUNkLG9CQUFvQixFQUNwQixlQUFlLENBQ2hCLENBQUM7Z0JBQ0osUUFBUSxHQUFHLE1BQU0sc0NBQXNDLENBQ3JELE1BQU0sRUFDTixRQUFRLEVBQ1IscUJBQXFCLEVBQ3JCLGdCQUFnQixFQUNoQixzQkFBc0IsRUFDdEIsZUFBZSxFQUNmLG9CQUFvQixDQUNyQixDQUFDO2dCQUNGLE1BQU07UUFDVixDQUFDO1FBRUQsSUFBSSxRQUFRLEVBQUUsS0FBSyxLQUFLLFdBQVcsRUFBRSxDQUFDO1lBQ3BDLE1BQU0sZ0JBQWdCLEdBQ3BCLE1BQU0sbURBQW1ELENBQ3ZELE1BQU0sRUFDTixRQUFRLENBQUMsSUFBYyxFQUN2QixvQkFBb0IsQ0FDckIsQ0FBQztZQUNKLE9BQU8sQ0FBQyxHQUFHLENBQUMsZ0JBQWdCLEVBQUUsbUJBQW1CLENBQUMsQ0FBQztZQUNuRCxvQkFBb0IsQ0FBQyxRQUFRLENBQUMsSUFBSSxDQUFDLGdCQUFnQixDQUFDLENBQUM7WUFDckQsb0JBQW9CLENBQUMsS0FBSyxHQUFHLFdBQVcsQ0FBQztZQUN6QyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsSUFBSSxDQUFDO1FBQ3ZDLENBQUM7YUFBTSxJQUFJLFFBQVEsRUFBRSxLQUFLLEtBQUssZ0JBQWdCLEVBQUUsQ0FBQztZQUNoRCxNQUFNLGdCQUFnQixHQUNwQixNQUFNLHFEQUFxRCxDQUN6RCxNQUFNLEVBQ04sUUFBUSxFQUFFLElBQTBCLEVBQ3BDLG9CQUFvQixDQUNyQixDQUFDO1lBRUosb0JBQW9CLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDO1lBQ3JELG9CQUFvQixDQUFDLEtBQUssR0FBRyxnQkFBZ0IsQ0FBQztZQUM5QyxvQkFBb0IsQ0FBQyxRQUFRLEdBQUcsUUFBUSxFQUFFLElBQTBCLENBQUM7WUFDckUsb0JBQW9CLENBQUMsUUFBUSxHQUFHLFFBQVEsRUFBRSxRQUFRLENBQUM7WUFDbkQsb0JBQW9CLENBQUMsYUFBYSxHQUFHLFFBQVEsRUFBRSxhQUFhLENBQUM7WUFDN0Qsb0JBQW9CLENBQUMsZ0JBQWdCLEdBQUcsUUFBUSxFQUFFLGdCQUFnQixDQUFDO1lBQ25FLG9CQUFvQixDQUFDLFlBQVksR0FBRyxRQUFRLEVBQUUsWUFBWSxDQUFDO1FBQzdELENBQUM7YUFBTSxJQUFJLFFBQVEsRUFBRSxLQUFLLEtBQUssaUJBQWlCLEVBQUUsQ0FBQztZQUNqRCxNQUFNLGdCQUFnQixHQUF5QjtnQkFDN0MsSUFBSSxFQUFFLFdBQVc7Z0JBQ2pCLE9BQU8sRUFBRSw2Q0FBNkM7YUFDdkQsQ0FBQztZQUVGLG9CQUFvQixDQUFDLFFBQVEsQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsQ0FBQztZQUNyRCxvQkFBb0IsQ0FBQyxLQUFLLEdBQUcsaUJBQWlCLENBQUM7WUFDL0Msb0JBQW9CLENBQUMsUUFBUSxHQUFHLElBQUksQ0FBQztRQUN2QyxDQUFDO1FBRUQsT0FBTyxvQkFBb0IsQ0FBQztJQUM5QixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLG9EQUFvRCxDQUFDLENBQUM7SUFDdkUsQ0FBQztBQUNILENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkSlNPTlR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvZGF0ZXRpbWUvUXVlcnlDYWxlbmRhckV4dHJhY3RlZERhdGVKU09OVHlwZSc7XG5pbXBvcnQgVXNlcklucHV0VG9KU09OVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Vc2VySW5wdXRUb0pTT05UeXBlJztcbmltcG9ydCB7IFF1ZXJ5Q2FsZW5kYXJFeHRyYWN0ZWRBdHRyaWJ1dGVzVHlwZSB9IGZyb20gJ0BjaGF0L19saWJzL3NraWxscy9hc2tDYWxlbmRhci90eXBlcyc7XG5pbXBvcnQge1xuICBzZWFyY2hTaW5nbGVFdmVudEJ5VmVjdG9yV2l0aERhdGVzTGFuY2VEYiwgLy8gVXBkYXRlZFxuICBjb252ZXJ0RXZlbnRUaXRsZVRvT3BlbkFJVmVjdG9yLFxuICBleHRyYWN0QXR0cmlidXRlc05lZWRlZEZyb21Vc2VySW5wdXQsXG4gIGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YSxcbiAgZXh0cmFwb2xhdGVTdGFydERhdGVGcm9tSlNPTkRhdGEsXG4gIGdlbmVyYXRlQXNzaXN0YW50TWVzc2FnZUZyb21BUElSZXNwb25zZUZvclVzZXJRdWVyeSxcbiAgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMsXG4gIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0LFxuICBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNKU09ORGF0YUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlTWlzc2luZ0ZpZWxkc1F1ZXJ5RGF0ZUZyb21Vc2VySW5wdXQsXG4gIGdlbmVyYXRlUXVlcnlEYXRlRnJvbVVzZXJJbnB1dCxcbn0gZnJvbSAnQGNoYXQvX2xpYnMvYXBpLWhlbHBlcic7XG5pbXBvcnQgeyBsaXN0U29ydGVkT2JqZWN0c0ZvclVzZXJHaXZlbkRhdGVzQW5kQXR0cmlidXRlcyB9IGZyb20gJy4uL2FwaS1oZWxwZXInO1xuaW1wb3J0IFJlcXVpcmVkRmllbGRzVHlwZSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9SZXF1aXJlZEZpZWxkc1R5cGUnO1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAY2hhdC9fbGlicy9kYXRldGltZS9kYXRlLXV0aWxzJztcbmltcG9ydCBSZXNwb25zZUFjdGlvblR5cGUgZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvUmVzcG9uc2VBY3Rpb25UeXBlJztcbmltcG9ydCB7IFF1ZXJ5RXZlbnRUeXBlIH0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnO1xuaW1wb3J0IE9wZW5BSSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHtcbiAgQXNzaXN0YW50TWVzc2FnZVR5cGUsXG4gIFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxufSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9NZXNzYWdpbmcvTWVzc2FnaW5nVHlwZXMnO1xuLy8gaW1wb3J0IHsgT3BlblNlYXJjaFJlc3BvbnNlQm9keVR5cGUgfSBmcm9tIFwiQGNoYXQvX2xpYnMvdHlwZXMvT3BlblNlYXJjaFJlc3BvbnNlVHlwZVwiIC8vIFJlbW92ZWRcbmltcG9ydCB7IEV2ZW50U2NoZW1hIGFzIExhbmNlRGJFdmVudFNjaGVtYSB9IGZyb20gJ0BmdW5jdGlvbnMvX3V0aWxzL2xhbmNlZGJfc2VydmljZSc7IC8vIEFkZGVkXG5pbXBvcnQgeyBFdmVudFR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IHsgQXR0ZW5kZWVUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQXR0ZW5kZWVUeXBlJztcbmltcG9ydCB7IENvbmZlcmVuY2VUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQ29uZmVyZW5jZVR5cGUnO1xuaW1wb3J0IHsgVGFza1R5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9UYXNrVHlwZSc7XG5cbmV4cG9ydCBjb25zdCBmaW5hbFN0ZXBRdWVyeUV2ZW50ID0gYXN5bmMgKFxuICBib2R5OiBRdWVyeUV2ZW50VHlwZSxcbiAgd2luZG93U3RhcnREYXRlOiBzdHJpbmcsXG4gIHdpbmRvd0VuZERhdGU6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgcmVzcG9uc2U6IGFueVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IHNlYXJjaFZlY3RvcjogbnVtYmVyW10gPSBbXTtcbiAgICBpZiAoYm9keT8udGl0bGUpIHtcbiAgICAgIHNlYXJjaFZlY3RvciA9IGF3YWl0IGNvbnZlcnRFdmVudFRpdGxlVG9PcGVuQUlWZWN0b3IoYm9keT8udGl0bGUpO1xuICAgIH1cblxuICAgIGlmICghd2luZG93U3RhcnREYXRlKSB7XG4gICAgICB3aW5kb3dTdGFydERhdGUgPSBkYXlqcygpLnN1YnRyYWN0KDIsICd3JykuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgaWYgKCF3aW5kb3dFbmREYXRlKSB7XG4gICAgICB3aW5kb3dFbmREYXRlID0gZGF5anMoKS5hZGQoNCwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBsZXQgc2VhcmNoUmVzdWx0OiBMYW5jZURiRXZlbnRTY2hlbWEgfCBudWxsID0gbnVsbDsgLy8gQ2hhbmdlZCB0eXBlXG4gICAgbGV0IGV2ZW50czogRXZlbnRUeXBlW10gPSBbXTtcbiAgICBpZiAoc2VhcmNoVmVjdG9yPy5sZW5ndGggPiAwKSB7XG4gICAgICBzZWFyY2hSZXN1bHQgPSBhd2FpdCBzZWFyY2hTaW5nbGVFdmVudEJ5VmVjdG9yV2l0aERhdGVzTGFuY2VEYihcbiAgICAgICAgYm9keS51c2VySWQsXG4gICAgICAgIHNlYXJjaFZlY3RvcixcbiAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICB3aW5kb3dFbmREYXRlXG4gICAgICApOyAvLyBVcGRhdGVkIGNhbGxcbiAgICB9XG5cbiAgICBjb25zdCBpZCA9IHNlYXJjaFJlc3VsdD8uaWQ7IC8vIFVwZGF0ZWQgSUQgZXh0cmFjdGlvblxuXG4gICAgbGV0IG9iamVjdHNXaXRoQXR0cmlidXRlczoge1xuICAgICAgZXZlbnRzOiBFdmVudFR5cGVbXTtcbiAgICAgIGNvbmZlcmVuY2VzOiBDb25mZXJlbmNlVHlwZVtdO1xuICAgICAgYXR0ZW5kZWVzOiBBdHRlbmRlZVR5cGVbXTtcbiAgICAgIHRhc2tzOiBUYXNrVHlwZVtdO1xuICAgICAgY291bnQ6IG51bWJlcjtcbiAgICB9O1xuICAgIGlmIChpZCkge1xuICAgICAgb2JqZWN0c1dpdGhBdHRyaWJ1dGVzID1cbiAgICAgICAgYXdhaXQgbGlzdFNvcnRlZE9iamVjdHNGb3JVc2VyR2l2ZW5EYXRlc0FuZEF0dHJpYnV0ZXMoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIGJvZHk/LndpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICBib2R5Py53aW5kb3dFbmREYXRlLFxuICAgICAgICAgIGJvZHk/LmF0dHJpYnV0ZXMsXG4gICAgICAgICAgYm9keT8uaXNNZWV0aW5nLFxuICAgICAgICAgIFtpZF1cbiAgICAgICAgKTtcbiAgICB9IGVsc2Uge1xuICAgICAgb2JqZWN0c1dpdGhBdHRyaWJ1dGVzID1cbiAgICAgICAgYXdhaXQgbGlzdFNvcnRlZE9iamVjdHNGb3JVc2VyR2l2ZW5EYXRlc0FuZEF0dHJpYnV0ZXMoXG4gICAgICAgICAgYm9keT8udXNlcklkLFxuICAgICAgICAgIGJvZHk/LndpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgICAgICBib2R5Py53aW5kb3dFbmREYXRlLFxuICAgICAgICAgIGJvZHk/LmF0dHJpYnV0ZXMsXG4gICAgICAgICAgYm9keT8uaXNNZWV0aW5nXG4gICAgICAgICk7XG4gICAgfVxuXG4gICAgZXZlbnRzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy5ldmVudHM7XG4gICAgY29uc3QgY29uZmVyZW5jZXMgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmNvbmZlcmVuY2VzO1xuICAgIGNvbnN0IGF0dGVuZGVlcyA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8uYXR0ZW5kZWVzO1xuICAgIGNvbnN0IHRhc2tzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy50YXNrcztcbiAgICBjb25zdCBjb3VudCA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8uY291bnQ7XG5cbiAgICAvLyB2YWxpZGF0ZSBmb3VuZCBldmVudFxuICAgIGlmICghKGV2ZW50cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIHJlc3BvbnNlLnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICByZXR1cm4gcmVzcG9uc2U7XG4gICAgfVxuXG4gICAgbGV0IHF1ZXJ5RGF0YSA9ICcnO1xuXG4gICAgLy8gdW5pcSBkYXRlc1xuICAgIGNvbnN0IHVuaXFEYXRlcyA9IF8udW5pcUJ5KGV2ZW50cywgKGN1cnIpID0+XG4gICAgICBkYXlqcyhjdXJyPy5zdGFydERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ1lZWVktTU0tREQnKVxuICAgICk/Lm1hcCgoZSkgPT4gZT8uc3RhcnREYXRlKTtcblxuICAgIGZvciAoY29uc3QgdW5pcURhdGUgb2YgdW5pcURhdGVzKSB7XG4gICAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV2ZW50cz8uZmlsdGVyKFxuICAgICAgICAoYSkgPT5cbiAgICAgICAgICBkYXlqcyhhPy5zdGFydERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ1lZWVktTU0tREQnKSA9PT1cbiAgICAgICAgICBkYXlqcyh1bmlxRGF0ZSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpXG4gICAgICApO1xuXG4gICAgICBxdWVyeURhdGEgKz0gYCR7ZGF5anModW5pcURhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ2RkZCwgWVlZWS1NTS1ERCcpfWA7XG4gICAgICBxdWVyeURhdGEgKz0gJ1xcbic7XG5cbiAgICAgIGZvciAoY29uc3QgZXZlbnQgb2YgZmlsdGVyZWRFdmVudHMpIHtcbiAgICAgICAgcXVlcnlEYXRhICs9ICdFdmVudCAtICc7XG5cbiAgICAgICAgcXVlcnlEYXRhICs9IGB0aXRsZTogJHtldmVudD8udGl0bGUgfHwgZXZlbnQ/LnN1bW1hcnl9LCBgO1xuICAgICAgICBxdWVyeURhdGEgKz0gYHRpbWU6ICR7ZGF5anMoZXZlbnQ/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnTFQnKX0gYDtcbiAgICAgICAgcXVlcnlEYXRhICs9IGAtICR7ZGF5anMoZXZlbnQ/LmVuZERhdGUpLnR6KHRpbWV6b25lLCB0cnVlKS5mb3JtYXQoJ0xUJyl9LCBgO1xuXG4gICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnbm9uZScpKSB7XG4gICAgICAgICAgY29udGludWU7XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2FsbCcpKSB7XG4gICAgICAgICAgLy8gcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19IGBcbiAgICAgICAgICAvLyBxdWVyeURhdGEgKz0gYGlkOiAke2V2ZW50Py5pZH0sIGBcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBmb3IgKGNvbnN0IHByb3BlcnR5IGluIGV2ZW50KSB7XG4gICAgICAgICAgICBpZiAocHJvcGVydHkgPT09ICdhbGxEYXknKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnYWxsRGF5JykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICd0aXRsZScpIHtcbiAgICAgICAgICAgICAgLy8gcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3N0YXJ0RGF0ZScpIHtcbiAgICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnZW5kRGF0ZScpIHtcbiAgICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAncmVjdXJyZW5jZVJ1bGUnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAncmVjdXJyZW5jZVJ1bGUnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2xvY2F0aW9uJykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2xvY2F0aW9uJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdub3RlcycpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdub3RlcycpKSB7XG4gICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAndGltZXpvbmUnKSB7XG4gICAgICAgICAgICAgIGNvbnRpbnVlO1xuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3Rhc2tJZCcpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICd0YXNrSWQnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3ByaW9yaXR5Jykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ3ByaW9yaXR5JykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdpc0ZvbGxvd1VwJykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2lzRm9sbG93VXAnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2lzUHJlRXZlbnQnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnaXNQcmVFdmVudCcpKSB7XG4gICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnaXNQb3N0RXZlbnQnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnaXNQb3N0RXZlbnQnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ21vZGlmaWFibGUnKSB7XG4gICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnbW9kaWZpYWJsZScpKSB7XG4gICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnaXNCcmVhaycpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdpc0JyZWFrJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdidWZmZXJUaW1lJykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2J1ZmZlclRpbWUnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2hhcmREZWFkbGluZScpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdoYXJkRGVhZGxpbmUnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3NvZnREZWFkbGluZScpIHtcbiAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdzb2Z0RGVhZGxpbmUnKSkge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2R1cmF0aW9uJykge1xuICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZCgoYSkgPT4gYSA9PT0gJ2R1cmF0aW9uJykpIHtcbiAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgICBpZiAoZXZlbnQ/LmNvbmZlcmVuY2VJZCkge1xuICAgICAgICAgIGNvbnN0IGZpbHRlcmVkQ29uZiA9IGNvbmZlcmVuY2VzPy5maW5kKFxuICAgICAgICAgICAgKGMpID0+IGM/LmlkID09PSBldmVudD8uY29uZmVyZW5jZUlkXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGlmIChmaWx0ZXJlZENvbmY/LmlkKSB7XG4gICAgICAgICAgICBxdWVyeURhdGEgKz0gJyBjb25mZXJlbmNlIHdpdGggZXZlbnQgLSAnO1xuICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBuYW1lOiAke2ZpbHRlcmVkQ29uZj8ubmFtZX0sIGA7XG4gICAgICAgICAgICBxdWVyeURhdGEgKz0gYGFwcDogJHtmaWx0ZXJlZENvbmY/LmFwcH0sIGA7XG5cbiAgICAgICAgICAgIGZvciAoY29uc3QgcHJvcGVydHkgaW4gZmlsdGVyZWRDb25mKSB7XG4gICAgICAgICAgICAgIGlmIChwcm9wZXJ0eSA9PT0gJ25vdGVzJykge1xuICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnY29uZmVyZW5jZS1ub3RlcycpKSB7XG4gICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2ZpbHRlcmVkQ29uZltwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2pvaW5VcmwnKSB7XG4gICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoKGEpID0+IGEgPT09ICdjb25mZXJlbmNlLWpvaW5VcmwnKSkge1xuICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtmaWx0ZXJlZENvbmZbcHJvcGVydHldfSwgYDtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzdGFydFVybCcpIHtcbiAgICAgICAgICAgICAgICBpZiAoXG4gICAgICAgICAgICAgICAgICBib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAnY29uZmVyZW5jZS1zdGFydFVybCcpXG4gICAgICAgICAgICAgICAgKSB7XG4gICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2ZpbHRlcmVkQ29uZltwcm9wZXJ0eV19LCBgO1xuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoYXR0ZW5kZWVzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnYXR0ZW5kZWVzIC0gJztcblxuICAgICAgICAgICAgICBmb3IgKGNvbnN0IGF0dGVuZGVlIG9mIGF0dGVuZGVlcykge1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgbmFtZTogJHthdHRlbmRlZT8ubmFtZX1gO1xuICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgZW1haWw6ICR7YXR0ZW5kZWU/LmVtYWlscz8uZmluZCgoZSkgPT4gISFlPy5wcmltYXJ5KT8udmFsdWV9YDtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmIChldmVudD8udGFza0lkKSB7XG4gICAgICAgICAgY29uc3QgZmlsdGVyZWRUYXNrID0gdGFza3M/LmZpbmQoKHQpID0+IHQ/LmlkID09PSBldmVudD8udGFza0lkKTtcblxuICAgICAgICAgIGlmIChmaWx0ZXJlZFRhc2s/LmlkKSB7XG4gICAgICAgICAgICBxdWVyeURhdGEgKz0gJyB0YXNrIHdpdGggZXZlbnQgLSAnO1xuICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke2ZpbHRlcmVkVGFzaz8ubm90ZXN9LCBgO1xuXG4gICAgICAgICAgICBmb3IgKGNvbnN0IHByb3BlcnR5IGluIGZpbHRlcmVkVGFzaykge1xuICAgICAgICAgICAgICBpZiAocHJvcGVydHkgPT09ICd0eXBlJykge1xuICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAndGFzay1saXN0TmFtZScpKSB7XG4gICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGxpc3Q6ICR7ZmlsdGVyZWRUYXNrW3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnc3RhdHVzJykge1xuICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKChhKSA9PiBhID09PSAndGFzay1zdGF0dXMnKSkge1xuICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBzdGF0dXM6ICR7ZmlsdGVyZWRUYXNrW3Byb3BlcnR5XX0sIGA7XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG5cbiAgICAgICAgcXVlcnlEYXRhICs9ICdcXG4nO1xuICAgICAgfVxuXG4gICAgICBxdWVyeURhdGEgKz0gJ1xcblxcbic7XG4gICAgfVxuXG4gICAgaWYgKGNvdW50ID4gMCkge1xuICAgICAgcXVlcnlEYXRhICs9IGBjb3VudDogJHtjb3VudH1gO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKHF1ZXJ5RGF0YSwgcXVlcnlEYXRhPy5sZW5ndGgsICcgcXVlcnlEYXRhLCBsZW5ndGgnKTtcbiAgICAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJztcblxuICAgIHJlc3BvbnNlLmRhdGEgPSBxdWVyeURhdGE7XG5cbiAgICByZXR1cm4gcmVzcG9uc2U7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkbyBmaW5hbCBzdGVwIHF1ZXJ5IGV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzUXVlcnlFdmVudFBlbmRpbmcgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBqc29uQm9keTogVXNlcklucHV0VG9KU09OVHlwZSxcbiAgLy8gZGF0ZVRpbWVKU09OQm9keTogRGF0ZVRpbWVKU09OVHlwZSxcbiAgYXR0cmlidXRlc09iamVjdDogUXVlcnlDYWxlbmRhckV4dHJhY3RlZEF0dHJpYnV0ZXNUeXBlLFxuICBxdWVyeURhdGVKU09OQm9keTogUXVlcnlDYWxlbmRhckV4dHJhY3RlZEpTT05UeXBlLFxuICBjdXJyZW50VGltZTogc3RyaW5nXG4pOiBQcm9taXNlPFJlc3BvbnNlQWN0aW9uVHlwZT4gPT4ge1xuICB0cnkge1xuICAgIGxldCB3aW5kb3dTdGFydERhdGUgPSBleHRyYXBvbGF0ZVN0YXJ0RGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ueWVhcixcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5tb250aCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5kYXksXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8uaG91cixcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5taW51dGUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8udGltZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5yZWxhdGl2ZVRpbWVDaGFuZ2VGcm9tTm93LFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgbGV0IHdpbmRvd0VuZERhdGUgPSBleHRyYXBvbGF0ZUVuZERhdGVGcm9tSlNPTkRhdGEoXG4gICAgICBjdXJyZW50VGltZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy55ZWFyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5tb250aCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8uZGF5LFxuICAgICAgdW5kZWZpbmVkLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5ob3VyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5taW51dGUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnRpbWUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnJlbGF0aXZlVGltZUZyb21Ob3dcbiAgICApO1xuXG4gICAgaWYgKCF3aW5kb3dTdGFydERhdGUpIHtcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSA9IGRheWpzKCkuc3VidHJhY3QoMiwgJ3cnKS5mb3JtYXQoKTtcbiAgICB9XG5cbiAgICBpZiAoIXdpbmRvd0VuZERhdGUpIHtcbiAgICAgIHdpbmRvd0VuZERhdGUgPSBkYXlqcygpLmFkZCg0LCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGNvbnN0IGJvZHk6IFF1ZXJ5RXZlbnRUeXBlID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgdGltZXpvbmUsXG4gICAgICB0aXRsZTpcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8udGl0bGUgfHxcbiAgICAgICAganNvbkJvZHk/LnBhcmFtcz8uc3VtbWFyeSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50YXNrTGlzdD8uWzBdPy50YXNrLFxuICAgICAgaXNNZWV0aW5nOiBhdHRyaWJ1dGVzT2JqZWN0Py5pc01lZXRpbmcsXG4gICAgICBhdHRyaWJ1dGVzOiBhdHRyaWJ1dGVzT2JqZWN0Py5hdHRyaWJ1dGVzLFxuICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICB9O1xuXG4gICAgY29uc29sZS5sb2coYm9keSwgJyBib2R5IGluc2lkZSBmaW5kLWV2ZW50Jyk7XG4gICAgLy8gdmFsaWRhdGVcbiAgICBjb25zdCByZXNwb25zZTogYW55ID0ge1xuICAgICAgcXVlcnk6ICcnLFxuICAgICAgZGF0YToge30sXG4gICAgICBza2lsbDogJ3F1ZXJ5RXZlbnQnLFxuICAgIH07XG5cbiAgICAvLyB2YWxpZGF0ZSByZW1haW5pbmcgcmVxdWlyZWQgZmllbGRzXG4gICAgLy8gY29uc3QgbWlzc2luZ0ZpZWxkczogUmVxdWlyZWRGaWVsZHNUeXBlID0ge1xuICAgIC8vICAgICByZXF1aXJlZDogW11cbiAgICAvLyB9XG4gICAgLy8gaWYgKCFib2R5Py50aXRsZSkge1xuICAgIC8vICAgICByZXNwb25zZS5xdWVyeSA9ICdtaXNzaW5nX2ZpZWxkcydcbiAgICAvLyAgICAgbWlzc2luZ0ZpZWxkcy5yZXF1aXJlZC5wdXNoKHJlcXVpcmVkRmllbGRzLnJlcXVpcmVkPy5bMF0pXG4gICAgLy8gICAgIHJlc3BvbnNlLmRhdGEgPSBtaXNzaW5nRmllbGRzXG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRhID0gYm9keVxuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YUV4dHJhID0ge1xuICAgIC8vICAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgIC8vICAgICAgICAgd2luZG93RW5kRGF0ZSxcbiAgICAvLyAgICAgfVxuICAgIC8vIH1cblxuICAgIC8vIGlmIChyZXNwb25zZS5xdWVyeSA9PT0gJ21pc3NpbmdfZmllbGRzJykge1xuICAgIC8vICAgICByZXR1cm4gcmVzcG9uc2VcbiAgICAvLyB9XG5cbiAgICBjb25zdCByZXNwb25zZTIgPSBhd2FpdCBmaW5hbFN0ZXBRdWVyeUV2ZW50KFxuICAgICAgYm9keSxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gICAgLy8gY29uc3Qgc2VhcmNoVmVjdG9yID0gYXdhaXQgY29udmVydEV2ZW50VGl0bGVUb09wZW5BSVZlY3Rvcihib2R5Py50aXRsZSlcblxuICAgIC8vIGNvbnN0IHJlcyA9IGF3YWl0IGFsbEV2ZW50V2l0aERhdGVzT3BlblNlYXJjaCh1c2VySWQsIHNlYXJjaFZlY3Rvciwgd2luZG93U3RhcnREYXRlLCB3aW5kb3dFbmREYXRlKVxuXG4gICAgLy8gY29uc3QgaWQgPSByZXM/LmhpdHM/LmhpdHM/LlswXT8uX2lkXG5cbiAgICAvLyAvLyB2YWxpZGF0ZSBmb3VuZCBldmVudFxuICAgIC8vIGlmICghaWQpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnZXZlbnRfbm90X2ZvdW5kJ1xuICAgIC8vICAgICByZXR1cm4gcmVzcG9uc2VcbiAgICAvLyB9XG5cbiAgICAvLyBjb25zdCBvYmplY3RzV2l0aEF0dHJpYnV0ZXMgPSBhd2FpdCBsaXN0U29ydGVkT2JqZWN0c0ZvclVzZXJHaXZlbkRhdGVzQW5kQXR0cmlidXRlcyhcbiAgICAvLyAgICAgYm9keT8udXNlcklkLFxuICAgIC8vICAgICBib2R5Py53aW5kb3dTdGFydERhdGUsXG4gICAgLy8gICAgIGJvZHk/LndpbmRvd0VuZERhdGUsXG4gICAgLy8gICAgIGJvZHk/LmF0dHJpYnV0ZXMsXG4gICAgLy8gICAgIGJvZHk/LmlzTWVldGluZyxcbiAgICAvLyAgICAgW2lkXSxcbiAgICAvLyApXG5cbiAgICAvLyBjb25zdCBldmVudHMgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmV2ZW50c1xuICAgIC8vIGNvbnN0IGNvbmZlcmVuY2VzID0gb2JqZWN0c1dpdGhBdHRyaWJ1dGVzPy5jb25mZXJlbmNlc1xuICAgIC8vIGNvbnN0IGF0dGVuZGVlcyA9IG9iamVjdHNXaXRoQXR0cmlidXRlcz8uYXR0ZW5kZWVzXG4gICAgLy8gY29uc3QgdGFza3MgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LnRhc2tzXG4gICAgLy8gY29uc3QgY291bnQgPSBvYmplY3RzV2l0aEF0dHJpYnV0ZXM/LmNvdW50XG5cbiAgICAvLyBsZXQgcXVlcnlEYXRhID0gJydcblxuICAgIC8vIC8vIHVuaXEgZGF0ZXNcbiAgICAvLyBjb25zdCB1bmlxRGF0ZXMgPSBfLnVuaXFCeShldmVudHMsIChjdXJyKSA9PiAoZGF5anMoY3Vycj8uc3RhcnREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCdZWVlZLU1NLUREJykpKT8ubWFwKGUgPT4gZT8uc3RhcnREYXRlKVxuXG4gICAgLy8gZm9yIChjb25zdCB1bmlxRGF0ZSBvZiB1bmlxRGF0ZXMpIHtcblxuICAgIC8vICAgICBjb25zdCBmaWx0ZXJlZEV2ZW50cyA9IGV2ZW50cz8uZmlsdGVyKGEgPT4gKGRheWpzKGE/LnN0YXJ0RGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpID09PSBkYXlqcyh1bmlxRGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnWVlZWS1NTS1ERCcpKSlcblxuICAgIC8vICAgICBxdWVyeURhdGEgKz0gYCR7ZGF5anModW5pcURhdGUpLmZvcm1hdCgnZGRkLCBZWVlZLU1NLUREJyl9YFxuICAgIC8vICAgICBxdWVyeURhdGEgKz0gJ1xcbidcblxuICAgIC8vICAgICBmb3IgKGNvbnN0IGV2ZW50IG9mIGZpbHRlcmVkRXZlbnRzKSB7XG4gICAgLy8gICAgICAgICBxdWVyeURhdGEgKz0gJ0V2ZW50IC0gJ1xuXG4gICAgLy8gICAgICAgICBxdWVyeURhdGEgKz0gYHRpdGxlOiAke2V2ZW50Py50aXRsZSB8fCBldmVudD8uc3VtbWFyeX0sIGBcbiAgICAvLyAgICAgICAgIHF1ZXJ5RGF0YSArPSBgdGltZTogJHtkYXlqcyhldmVudD8uc3RhcnREYXRlKS50eih0aW1lem9uZSkuZm9ybWF0KCdMVCcpfSBgXG4gICAgLy8gICAgICAgICBxdWVyeURhdGEgKz0gYC0gJHtkYXlqcyhldmVudD8uZW5kRGF0ZSkudHoodGltZXpvbmUpLmZvcm1hdCgnTFQnKX0sIGBcblxuICAgIC8vICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ25vbmUnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICBjb250aW51ZVxuICAgIC8vICAgICAgICAgfVxuXG4gICAgLy8gICAgICAgICBmb3IgKGNvbnN0IHByb3BlcnR5IGluIGV2ZW50KSB7XG5cbiAgICAvLyAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnYWxsJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIC8vIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSBgXG4gICAgLy8gICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgaWQ6ICR7ZXZlbnQ/LmlkfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICBjb250aW51ZVxuICAgIC8vICAgICAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgICAgIGlmIChwcm9wZXJ0eSA9PT0gJ2FsbERheScpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnYWxsRGF5JykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICd0aXRsZScpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgLy8gcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIGNvbnRpbnVlXG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3N0YXJ0RGF0ZScpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgY29udGludWVcbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnZW5kRGF0ZScpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgY29udGludWVcbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAncmVjdXJyZW5jZVJ1bGUnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ3JlY3VycmVuY2VSdWxlJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdsb2NhdGlvbicpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnbG9jYXRpb24nKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ25vdGVzJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdub3RlcycpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAndGltZXpvbmUnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgY29udGludWVcbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAndGFza0lkJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICd0YXNrSWQnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3ByaW9yaXR5Jykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdwcmlvcml0eScpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnaXNGb2xsb3dVcCcpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnaXNGb2xsb3dVcCcpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnaXNQcmVFdmVudCcpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnaXNQcmVFdmVudCcpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnaXNQb3N0RXZlbnQnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2lzUG9zdEV2ZW50JykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdtb2RpZmlhYmxlJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdtb2RpZmlhYmxlJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdpc0JyZWFrJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdpc0JyZWFrJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdidWZmZXJUaW1lJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdidWZmZXJUaW1lJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7cHJvcGVydHl9OiAke2V2ZW50W3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdoYXJkRGVhZGxpbmUnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2hhcmREZWFkbGluZScpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnc29mdERlYWRsaW5lJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdzb2Z0RGVhZGxpbmUnKSkpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZXZlbnRbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ2R1cmF0aW9uJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdkdXJhdGlvbicpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtldmVudFtwcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgY29uc3QgZmlsdGVyZWRDb25mID0gY29uZmVyZW5jZXM/LmZpbmQoYyA9PiAoYz8uaWQgPT09IGV2ZW50Py5jb25mZXJlbmNlSWQpKVxuXG4gICAgLy8gICAgICAgICBpZiAoZmlsdGVyZWRDb25mPy5pZCkge1xuICAgIC8vICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnIGNvbmZlcmVuY2Ugd2l0aCBldmVudCAtICdcbiAgICAvLyAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYG5hbWU6ICR7ZmlsdGVyZWRDb25mPy5uYW1lfSwgYFxuICAgIC8vICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgYXBwOiAke2ZpbHRlcmVkQ29uZj8uYXBwfSwgYFxuXG4gICAgLy8gICAgICAgICAgICAgZm9yIChjb25zdCBwcm9wZXJ0eSBpbiBmaWx0ZXJlZENvbmYpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgaWYgKHByb3BlcnR5ID09PSAnbm90ZXMnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICdjb25mZXJlbmNlLW5vdGVzJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGAke3Byb3BlcnR5fTogJHtmaWx0ZXJlZENvbmZbcHJvcGVydHldfSwgYFxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgICAgICB9IGVsc2UgaWYgKHByb3BlcnR5ID09PSAnam9pblVybCcpIHtcblxuICAgIC8vICAgICAgICAgICAgICAgICAgICAgaWYgKGJvZHk/LmF0dHJpYnV0ZXM/LmZpbmQoYSA9PiAoYSA9PT0gJ2NvbmZlcmVuY2Utam9pblVybCcpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZmlsdGVyZWRDb25mW3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICAgICAgfSBlbHNlIGlmIChwcm9wZXJ0eSA9PT0gJ3N0YXJ0VXJsJykge1xuXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBpZiAoYm9keT8uYXR0cmlidXRlcz8uZmluZChhID0+IChhID09PSAnY29uZmVyZW5jZS1zdGFydFVybCcpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgJHtwcm9wZXJ0eX06ICR7ZmlsdGVyZWRDb25mW3Byb3BlcnR5XX0sIGBcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgICAgIGlmIChhdHRlbmRlZXM/Lmxlbmd0aCA+IDApIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9ICdhdHRlbmRlZXMgLSAnXG5cbiAgICAvLyAgICAgICAgICAgICAgICAgZm9yIChjb25zdCBhdHRlbmRlZSBvZiBhdHRlbmRlZXMpIHtcbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgbmFtZTogJHthdHRlbmRlZT8ubmFtZX1gXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYGVtYWlsOiAke2F0dGVuZGVlPy5lbWFpbHM/LmZpbmQoZSA9PiAoISFlPy5wcmltYXJ5KSk/LnZhbHVlfWBcbiAgICAvLyAgICAgICAgICAgICAgICAgfVxuICAgIC8vICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgIH1cblxuICAgIC8vICAgICAgICAgY29uc3QgZmlsdGVyZWRUYXNrID0gdGFza3M/LmZpbmQodCA9PiAodD8uaWQgPT09IGV2ZW50Py50YXNrSWQpKVxuXG4gICAgLy8gICAgICAgICBpZiAoZmlsdGVyZWRUYXNrPy5pZCkge1xuICAgIC8vICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSAnIHRhc2sgd2l0aCBldmVudCAtICdcbiAgICAvLyAgICAgICAgICAgICBxdWVyeURhdGEgKz0gYCR7ZmlsdGVyZWRUYXNrPy5ub3Rlc30sIGBcblxuICAgIC8vICAgICAgICAgICAgIGZvciAoY29uc3QgcHJvcGVydHkgaW4gZmlsdGVyZWRUYXNrKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgIGlmIChwcm9wZXJ0eSA9PT0gJ3R5cGUnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICd0YXNrLWxpc3ROYW1lJykpKSB7XG4gICAgLy8gICAgICAgICAgICAgICAgICAgICAgICAgcXVlcnlEYXRhICs9IGBsaXN0OiAke2ZpbHRlcmVkVGFza1twcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgICAgIH0gZWxzZSBpZiAocHJvcGVydHkgPT09ICdzdGF0dXMnKSB7XG5cbiAgICAvLyAgICAgICAgICAgICAgICAgICAgIGlmIChib2R5Py5hdHRyaWJ1dGVzPy5maW5kKGEgPT4gKGEgPT09ICd0YXNrLXN0YXR1cycpKSkge1xuICAgIC8vICAgICAgICAgICAgICAgICAgICAgICAgIHF1ZXJ5RGF0YSArPSBgc3RhdHVzOiAke2ZpbHRlcmVkVGFza1twcm9wZXJ0eV19LCBgXG4gICAgLy8gICAgICAgICAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICAgICAgICAgIH1cbiAgICAvLyAgICAgICAgICAgICB9XG4gICAgLy8gICAgICAgICB9XG5cbiAgICAvLyAgICAgICAgIHF1ZXJ5RGF0YSArPSAnXFxuJ1xuICAgIC8vICAgICB9XG5cbiAgICAvLyAgICAgcXVlcnlEYXRhICs9ICdcXG5cXG4nXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKGNvdW50ID4gMCkge1xuICAgIC8vICAgICBxdWVyeURhdGEgKz0gYGNvdW50OiAke2NvdW50fWBcbiAgICAvLyB9XG5cbiAgICAvLyAvLyBzdWNjZXNzIHJlc3BvbnNlXG4gICAgLy8gcmVzcG9uc2UucXVlcnkgPSAnY29tcGxldGVkJ1xuXG4gICAgLy8gcmVzcG9uc2UuZGF0YSA9IHF1ZXJ5RGF0YVxuXG4gICAgLy8gcmV0dXJuIHJlc3BvbnNlXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIHF1ZXJ5IGV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBwcm9jZXNzUXVlcnlFdmVudE1pc3NpbmdGaWVsZHNSZXR1cm5lZCA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGpzb25Cb2R5OiBVc2VySW5wdXRUb0pTT05UeXBlLFxuICAvLyBkYXRlVGltZUpTT05Cb2R5OiBEYXRlVGltZUpTT05UeXBlLFxuICBhdHRyaWJ1dGVzT2JqZWN0OiBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkQXR0cmlidXRlc1R5cGUsXG4gIHF1ZXJ5RGF0ZUpTT05Cb2R5OiBRdWVyeUNhbGVuZGFyRXh0cmFjdGVkSlNPTlR5cGUsXG4gIGN1cnJlbnRUaW1lOiBzdHJpbmcsXG4gIG1lc3NhZ2VIaXN0b3J5T2JqZWN0OiBTa2lsbE1lc3NhZ2VIaXN0b3J5VHlwZVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgbGV0IHdpbmRvd1N0YXJ0RGF0ZSA9IGV4dHJhcG9sYXRlU3RhcnREYXRlRnJvbUpTT05EYXRhKFxuICAgICAgY3VycmVudFRpbWUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy55ZWFyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/Lm1vbnRoLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LmRheSxcbiAgICAgIHVuZGVmaW5lZCxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy5ob3VyLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/Lm1pbnV0ZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5zdGFydF9kYXRlPy50aW1lLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LnN0YXJ0X2RhdGU/LnJlbGF0aXZlVGltZUNoYW5nZUZyb21Ob3csXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uc3RhcnRfZGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBsZXQgd2luZG93RW5kRGF0ZSA9IGV4dHJhcG9sYXRlRW5kRGF0ZUZyb21KU09ORGF0YShcbiAgICAgIGN1cnJlbnRUaW1lLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LnllYXIsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/Lm1vbnRoLFxuICAgICAgcXVlcnlEYXRlSlNPTkJvZHk/LmVuZF9kYXRlPy5kYXksXG4gICAgICB1bmRlZmluZWQsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/LmhvdXIsXG4gICAgICBxdWVyeURhdGVKU09OQm9keT8uZW5kX2RhdGU/Lm1pbnV0ZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8udGltZSxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ucmVsYXRpdmVUaW1lQ2hhbmdlRnJvbU5vdyxcbiAgICAgIHF1ZXJ5RGF0ZUpTT05Cb2R5Py5lbmRfZGF0ZT8ucmVsYXRpdmVUaW1lRnJvbU5vd1xuICAgICk7XG5cbiAgICBpZiAoIXdpbmRvd1N0YXJ0RGF0ZSkge1xuICAgICAgd2luZG93U3RhcnREYXRlID0gZGF5anMoKS5zdWJ0cmFjdCgyLCAndycpLmZvcm1hdCgpO1xuICAgIH1cblxuICAgIGlmICghd2luZG93RW5kRGF0ZSkge1xuICAgICAgd2luZG93RW5kRGF0ZSA9IGRheWpzKCkuYWRkKDQsICd3JykuZm9ybWF0KCk7XG4gICAgfVxuXG4gICAgY29uc3QgbmV3Qm9keTogUXVlcnlFdmVudFR5cGUgPSB7XG4gICAgICB1c2VySWQsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIHRpdGxlOlxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBqc29uQm9keT8ucGFyYW1zPy5zdW1tYXJ5IHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LmRlc2NyaXB0aW9uIHx8XG4gICAgICAgIGpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2sgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy50aXRsZSB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnN1bW1hcnkgfHxcbiAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3Q/LnByZXZKc29uQm9keT8ucGFyYW1zPy5kZXNjcmlwdGlvbiB8fFxuICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkpzb25Cb2R5Py5wYXJhbXM/LnRhc2tMaXN0Py5bMF0/LnRhc2ssXG4gICAgICBpc01lZXRpbmc6IGF0dHJpYnV0ZXNPYmplY3Q/LmlzTWVldGluZyxcbiAgICAgIGF0dHJpYnV0ZXM6IGF0dHJpYnV0ZXNPYmplY3Q/LmF0dHJpYnV0ZXMsXG4gICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlLFxuICAgIH07XG5cbiAgICBjb25zdCBwcmV2Qm9keTogUXVlcnlFdmVudFR5cGUgPSB7XG4gICAgICAuLi5tZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGEsXG4gICAgICB3aW5kb3dTdGFydERhdGU6IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Py5wcmV2RGF0YUV4dHJhPy53aW5kb3dTdGFydERhdGUsXG4gICAgICB3aW5kb3dFbmREYXRlOiBtZXNzYWdlSGlzdG9yeU9iamVjdD8ucHJldkRhdGFFeHRyYT8ud2luZG93RW5kRGF0ZSxcbiAgICB9O1xuXG4gICAgLy8gZml4IHByZXZCb2R5IHdpdGggbmV3IGRhdGFcbiAgICBpZiAoIXByZXZCb2R5Py51c2VySWQpIHtcbiAgICAgIHByZXZCb2R5LnVzZXJJZCA9IHVzZXJJZCB8fCBuZXdCb2R5Py51c2VySWQ7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGltZXpvbmUpIHtcbiAgICAgIHByZXZCb2R5LnRpbWV6b25lID0gdGltZXpvbmUgfHwgbmV3Qm9keT8udGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAgIHByZXZCb2R5LnRpdGxlID0gbmV3Qm9keT8udGl0bGU7XG4gICAgfVxuXG4gICAgaWYgKHByZXZCb2R5Py5pc01lZXRpbmcgPT09IHVuZGVmaW5lZCkge1xuICAgICAgcHJldkJvZHkuaXNNZWV0aW5nID0gbmV3Qm9keT8uaXNNZWV0aW5nO1xuICAgIH1cblxuICAgIGlmICghKHByZXZCb2R5Py5hdHRyaWJ1dGVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgcHJldkJvZHkuYXR0cmlidXRlcyA9IG5ld0JvZHk/LmF0dHJpYnV0ZXM7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ud2luZG93U3RhcnREYXRlKSB7XG4gICAgICBwcmV2Qm9keS53aW5kb3dTdGFydERhdGUgPSBuZXdCb2R5Py53aW5kb3dTdGFydERhdGU7XG4gICAgfVxuXG4gICAgaWYgKCFwcmV2Qm9keT8ud2luZG93RW5kRGF0ZSkge1xuICAgICAgcHJldkJvZHkud2luZG93RW5kRGF0ZSA9IG5ld0JvZHk/LndpbmRvd0VuZERhdGU7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzcG9uc2U6IGFueSA9IHtcbiAgICAgIHF1ZXJ5OiAnJyxcbiAgICAgIGRhdGE6IHt9LFxuICAgICAgc2tpbGw6ICdxdWVyeUV2ZW50JyxcbiAgICB9O1xuXG4gICAgLy8gdmFsaWRhdGUgcmVtYWluaW5nIHJlcXVpcmVkIGZpZWxkc1xuICAgIC8vIGNvbnN0IG1pc3NpbmdGaWVsZHM6IFJlcXVpcmVkRmllbGRzVHlwZSA9IHtcbiAgICAvLyAgICAgcmVxdWlyZWQ6IFtdXG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKCFwcmV2Qm9keT8udGl0bGUpIHtcbiAgICAvLyAgICAgcmVzcG9uc2UucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnXG4gICAgLy8gICAgIG1pc3NpbmdGaWVsZHMucmVxdWlyZWQucHVzaChyZXF1aXJlZEZpZWxkcy5yZXF1aXJlZD8uWzBdKVxuICAgIC8vICAgICByZXNwb25zZS5kYXRhID0gbWlzc2luZ0ZpZWxkc1xuICAgIC8vICAgICByZXNwb25zZS5wcmV2RGF0YSA9IHByZXZCb2R5XG4gICAgLy8gICAgIHJlc3BvbnNlLnByZXZEYXRhRXh0cmEgPSB7XG4gICAgLy8gICAgICAgICB3aW5kb3dTdGFydERhdGUsXG4gICAgLy8gICAgICAgICB3aW5kb3dFbmREYXRlLFxuICAgIC8vICAgICB9XG4gICAgLy8gfVxuXG4gICAgLy8gaWYgKHJlc3BvbnNlLnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgLy8gICAgIHJldHVybiByZXNwb25zZVxuICAgIC8vIH1cblxuICAgIGNvbnN0IHJlc3BvbnNlMiA9IGF3YWl0IGZpbmFsU3RlcFF1ZXJ5RXZlbnQoXG4gICAgICBwcmV2Qm9keSxcbiAgICAgIHByZXZCb2R5Py53aW5kb3dTdGFydERhdGUsXG4gICAgICBwcmV2Qm9keT8ud2luZG93RW5kRGF0ZSxcbiAgICAgIHByZXZCb2R5Py50aW1lem9uZSxcbiAgICAgIHJlc3BvbnNlXG4gICAgKTtcblxuICAgIHJldHVybiByZXNwb25zZTI7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBwcm9jZXNzIHF1ZXJ5IGV2ZW50IG1pc3NpbmcgZmllbGRzIHJldHVybmVkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBhc2tFdmVudENvbnRyb2xDZW50ZXIgPSBhc3luYyAoXG4gIG9wZW5haTogT3BlbkFJLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgdGltZXpvbmU6IHN0cmluZyxcbiAgbWVzc2FnZUhpc3RvcnlPYmplY3Q6IFNraWxsTWVzc2FnZUhpc3RvcnlUeXBlLFxuICB1c2VyQ3VycmVudFRpbWU6IHN0cmluZyxcbiAgcXVlcnk6ICdtaXNzaW5nX2ZpZWxkcycgfCAnY29tcGxldGVkJyB8ICdldmVudF9ub3RfZm91bmQnIHwgJ3BlbmRpbmcnXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBtZXNzYWdlTGVuZ3RoID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXM/Lmxlbmd0aDtcbiAgICBsZXQgdXNlck1lc3NhZ2UgPSAnJztcbiAgICBmb3IgKGxldCBpID0gbWVzc2FnZUxlbmd0aDsgaSA+IDA7IGktLSkge1xuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzW2kgLSAxXTtcblxuICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgIHVzZXJNZXNzYWdlID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICBicmVhaztcbiAgICAgIH1cbiAgICB9XG4gICAgY29uc3QgdXNlcklucHV0ID0gdXNlck1lc3NhZ2U7XG5cbiAgICBjb25zb2xlLmxvZyhtZXNzYWdlSGlzdG9yeU9iamVjdCwgJyBtZXNzYWdlSGlzdG9yeU9iamVjdCBiZWZvcmUgYXBpIGNhbGwnKTtcblxuICAgIC8vIGdlbmVyYXRlSlNPTkRhdGFGcm9tVXNlcklucHV0XG5cbiAgICBjb25zdCBhdHRyaWJ1dGVzT2JqZWN0ID1cbiAgICAgIGF3YWl0IGV4dHJhY3RBdHRyaWJ1dGVzTmVlZGVkRnJvbVVzZXJJbnB1dCh1c2VySW5wdXQpO1xuXG4gICAgbGV0IGV2ZW50UmVzOiBSZXNwb25zZUFjdGlvblR5cGUgPSB7XG4gICAgICBxdWVyeTogJ2NvbXBsZXRlZCcsXG4gICAgICBkYXRhOiAnJyxcbiAgICAgIHNraWxsOiAnJyxcbiAgICAgIHByZXZEYXRhOiB7fSxcbiAgICAgIHByZXZEYXRhRXh0cmE6IHt9LFxuICAgIH07XG5cbiAgICBzd2l0Y2ggKHF1ZXJ5KSB7XG4gICAgICBjYXNlICdwZW5kaW5nJzpcbiAgICAgICAgY29uc3QganNvbkJvZHkgPSBhd2FpdCBnZW5lcmF0ZUpTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGNvbnN0IHF1ZXJ5RGF0ZSA9IGF3YWl0IGdlbmVyYXRlUXVlcnlEYXRlRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgdXNlcklucHV0LFxuICAgICAgICAgIHVzZXJDdXJyZW50VGltZVxuICAgICAgICApO1xuICAgICAgICBldmVudFJlcyA9IGF3YWl0IHByb2Nlc3NRdWVyeUV2ZW50UGVuZGluZyhcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbkJvZHksXG4gICAgICAgICAgYXR0cmlidXRlc09iamVjdCxcbiAgICAgICAgICBxdWVyeURhdGUsXG4gICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICk7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnbWlzc2luZ19maWVsZHMnOlxuICAgICAgICBsZXQgcHJpb3JVc2VySW5wdXQgPSAnJztcbiAgICAgICAgbGV0IHByaW9yQXNzaXN0YW50T3V0cHV0ID0gJyc7XG5cbiAgICAgICAgZm9yIChsZXQgaSA9IG1lc3NhZ2VMZW5ndGg7IGkgPiAwOyBpLS0pIHtcbiAgICAgICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXNbaSAtIDFdO1xuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ2Fzc2lzdGFudCcpIHtcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0ID0gbWVzc2FnZS5jb250ZW50O1xuICAgICAgICAgICAgY29udGludWU7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgaWYgKG1lc3NhZ2Uucm9sZSA9PT0gJ3VzZXInKSB7XG4gICAgICAgICAgICBpZiAobWVzc2FnZS5jb250ZW50ICE9PSB1c2VySW5wdXQpIHtcbiAgICAgICAgICAgICAgcHJpb3JVc2VySW5wdXQgPSBtZXNzYWdlLmNvbnRlbnQ7XG4gICAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH1cbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghcHJpb3JVc2VySW5wdXQgfHwgIXByaW9yQXNzaXN0YW50T3V0cHV0KSB7XG4gICAgICAgICAgY29uc29sZS5sb2cocHJpb3JVc2VySW5wdXQsICcgcHJpb3JVc2VySW5wdXQnKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhwcmlvckFzc2lzdGFudE91dHB1dCwgJyBwcmlvckFzc2lzdGFudE91dHB1dCcpO1xuICAgICAgICAgIHRocm93IG5ldyBFcnJvcignbm8gcHJpb3JVc2VyaW5wdXQgb3IgcHJpb3JBc3Npc3RhbnRPdXRwdXQnKTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCBqc29uTWlzc2luZ0ZpZWxkc0JvZHkgPVxuICAgICAgICAgIGF3YWl0IGdlbmVyYXRlTWlzc2luZ0ZpZWxkc0pTT05EYXRhRnJvbVVzZXJJbnB1dChcbiAgICAgICAgICAgIHVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yVXNlcklucHV0LFxuICAgICAgICAgICAgcHJpb3JBc3Npc3RhbnRPdXRwdXQsXG4gICAgICAgICAgICB1c2VyQ3VycmVudFRpbWVcbiAgICAgICAgICApO1xuICAgICAgICBjb25zdCBxdWVyeU1pc3NpbmdGaWVsZHNEYXRlID1cbiAgICAgICAgICBhd2FpdCBnZW5lcmF0ZU1pc3NpbmdGaWVsZHNRdWVyeURhdGVGcm9tVXNlcklucHV0KFxuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICB1c2VySW5wdXQsXG4gICAgICAgICAgICBwcmlvclVzZXJJbnB1dCxcbiAgICAgICAgICAgIHByaW9yQXNzaXN0YW50T3V0cHV0LFxuICAgICAgICAgICAgdXNlckN1cnJlbnRUaW1lXG4gICAgICAgICAgKTtcbiAgICAgICAgZXZlbnRSZXMgPSBhd2FpdCBwcm9jZXNzUXVlcnlFdmVudE1pc3NpbmdGaWVsZHNSZXR1cm5lZChcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAganNvbk1pc3NpbmdGaWVsZHNCb2R5LFxuICAgICAgICAgIGF0dHJpYnV0ZXNPYmplY3QsXG4gICAgICAgICAgcXVlcnlNaXNzaW5nRmllbGRzRGF0ZSxcbiAgICAgICAgICB1c2VyQ3VycmVudFRpbWUsXG4gICAgICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3RcbiAgICAgICAgKTtcbiAgICAgICAgYnJlYWs7XG4gICAgfVxuXG4gICAgaWYgKGV2ZW50UmVzPy5xdWVyeSA9PT0gJ2NvbXBsZXRlZCcpIHtcbiAgICAgIGNvbnN0IGFzc2lzdGFudE1lc3NhZ2UgPVxuICAgICAgICBhd2FpdCBnZW5lcmF0ZUFzc2lzdGFudE1lc3NhZ2VGcm9tQVBJUmVzcG9uc2VGb3JVc2VyUXVlcnkoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGV2ZW50UmVzLmRhdGEgYXMgc3RyaW5nLFxuICAgICAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0XG4gICAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyhhc3Npc3RhbnRNZXNzYWdlLCAnIGFzc2lzdGFudE1lc3NhZ2UnKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0Lm1lc3NhZ2VzLnB1c2goYXNzaXN0YW50TWVzc2FnZSk7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5xdWVyeSA9ICdjb21wbGV0ZWQnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBudWxsO1xuICAgIH0gZWxzZSBpZiAoZXZlbnRSZXM/LnF1ZXJ5ID09PSAnbWlzc2luZ19maWVsZHMnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlID1cbiAgICAgICAgYXdhaXQgZ2VuZXJhdGVBc3Npc3RhbnRNZXNzYWdlVG9SZXF1ZXN0VXNlckZvck1pc3NpbmdGaWVsZHMoXG4gICAgICAgICAgb3BlbmFpLFxuICAgICAgICAgIGV2ZW50UmVzPy5kYXRhIGFzIFJlcXVpcmVkRmllbGRzVHlwZSxcbiAgICAgICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdFxuICAgICAgICApO1xuXG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5tZXNzYWdlcy5wdXNoKGFzc2lzdGFudE1lc3NhZ2UpO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucXVlcnkgPSAnbWlzc2luZ19maWVsZHMnO1xuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QucmVxdWlyZWQgPSBldmVudFJlcz8uZGF0YSBhcyBSZXF1aXJlZEZpZWxkc1R5cGU7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5wcmV2RGF0YSA9IGV2ZW50UmVzPy5wcmV2RGF0YTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRhRXh0cmEgPSBldmVudFJlcz8ucHJldkRhdGFFeHRyYTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZEYXRlSnNvbkJvZHkgPSBldmVudFJlcz8ucHJldkRhdGVKc29uQm9keTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnByZXZKc29uQm9keSA9IGV2ZW50UmVzPy5wcmV2SnNvbkJvZHk7XG4gICAgfSBlbHNlIGlmIChldmVudFJlcz8ucXVlcnkgPT09ICdldmVudF9ub3RfZm91bmQnKSB7XG4gICAgICBjb25zdCBhc3Npc3RhbnRNZXNzYWdlOiBBc3Npc3RhbnRNZXNzYWdlVHlwZSA9IHtcbiAgICAgICAgcm9sZTogJ2Fzc2lzdGFudCcsXG4gICAgICAgIGNvbnRlbnQ6IFwiT29wcy4uLiBJIGNvdWxkbid0IGZpbmQgdGhlIGV2ZW50LiBTb3JyeSA6KFwiLFxuICAgICAgfTtcblxuICAgICAgbWVzc2FnZUhpc3RvcnlPYmplY3QubWVzc2FnZXMucHVzaChhc3Npc3RhbnRNZXNzYWdlKTtcbiAgICAgIG1lc3NhZ2VIaXN0b3J5T2JqZWN0LnF1ZXJ5ID0gJ2V2ZW50X25vdF9mb3VuZCc7XG4gICAgICBtZXNzYWdlSGlzdG9yeU9iamVjdC5yZXF1aXJlZCA9IG51bGw7XG4gICAgfVxuXG4gICAgcmV0dXJuIG1lc3NhZ2VIaXN0b3J5T2JqZWN0O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcHJvY2VzcyBhc2sgZXZlbnQgaW5zaWRlIGNvbnRyb2wgY2VudGVyJyk7XG4gIH1cbn07XG4iXX0=