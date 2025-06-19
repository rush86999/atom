import QueryCalendarExtractedJSONType from "@chat/_libs/datetime/QueryCalendarExtractedDateJSONType"
import UserInputToJSONType from "@chat/_libs/types/UserInputToJSONType"
import { QueryCalendarExtractedAttributesType } from "@chat/_libs/skills/askCalendar/types"
import {
    searchSingleEventByVectorWithDatesLanceDb, // Updated
    convertEventTitleToOpenAIVector,
    extractAttributesNeededFromUserInput,
    extrapolateEndDateFromJSONData,
    extrapolateStartDateFromJSONData,
    generateAssistantMessageFromAPIResponseForUserQuery,
    generateAssistantMessageToRequestUserForMissingFields,
    generateJSONDataFromUserInput,
    generateMissingFieldsJSONDataFromUserInput,
    generateMissingFieldsQueryDateFromUserInput,
    generateQueryDateFromUserInput
} from "@chat/_libs/api-helper"
import { listSortedObjectsForUserGivenDatesAndAttributes } from "../api-helper"
import RequiredFieldsType from "@chat/_libs/types/RequiredFieldsType"
import { dayjs } from "@chat/_libs/datetime/date-utils"
import ResponseActionType from "@chat/_libs/types/ResponseActionType"
import { QueryEventType } from "./types"
import _ from "lodash"
import OpenAI from 'openai'
import { AssistantMessageType, SkillMessageHistoryType } from "@chat/_libs/types/Messaging/MessagingTypes"
// import { OpenSearchResponseBodyType } from "@chat/_libs/types/OpenSearchResponseType" // Removed
import { EventSchema as LanceDbEventSchema } from '@functions/_utils/lancedb_service'; // Added
import { EventType } from "@chat/_libs/types/EventType"
import { AttendeeType } from "@chat/_libs/types/AttendeeType"
import { ConferenceType } from "@chat/_libs/types/ConferenceType"
import { TaskType } from "@chat/_libs/types/TaskType"

export const finalStepQueryEvent = async (
    body: QueryEventType,
    windowStartDate: string,
    windowEndDate: string,
    timezone: string,
    response: any,
) => {
    try {
        let searchVector: number[] = []
        if (body?.title) {
            searchVector = await convertEventTitleToOpenAIVector(body?.title)
        }
        

        if (!windowStartDate) {
            windowStartDate = dayjs().subtract(2, 'w').format()
        }

        if (!windowEndDate) {
            windowEndDate = dayjs().add(4, 'w').format()
        }

        let searchResult: LanceDbEventSchema | null = null; // Changed type
        let events: EventType[] = []
        if (searchVector?.length > 0) {
            searchResult = await searchSingleEventByVectorWithDatesLanceDb(body.userId, searchVector, windowStartDate, windowEndDate) // Updated call
        }
        

        const id = searchResult?.id; // Updated ID extraction

        let objectsWithAttributes: {
            events: EventType[];
            conferences: ConferenceType[];
            attendees: AttendeeType[];
            tasks: TaskType[];
            count: number;
        }
        if (id) {
            objectsWithAttributes = await listSortedObjectsForUserGivenDatesAndAttributes(
                body?.userId,
                body?.windowStartDate,
                body?.windowEndDate,
                body?.attributes,
                body?.isMeeting,
                [id],
            )
        } else {
            objectsWithAttributes = await listSortedObjectsForUserGivenDatesAndAttributes(
                body?.userId,
                body?.windowStartDate,
                body?.windowEndDate,
                body?.attributes,
                body?.isMeeting,
            )
        }
        

        events = objectsWithAttributes?.events
        const conferences = objectsWithAttributes?.conferences
        const attendees = objectsWithAttributes?.attendees
        const tasks = objectsWithAttributes?.tasks
        const count = objectsWithAttributes?.count

        // validate found event
        if (!(events?.length > 0)) {
            response.query = 'event_not_found'
            return response
        }

        let queryData = ''

        // uniq dates
        const uniqDates = _.uniqBy(events, (curr) => (dayjs(curr?.startDate).tz(timezone, true).format('YYYY-MM-DD')))?.map(e => e?.startDate)

        for (const uniqDate of uniqDates) {

            const filteredEvents = events?.filter(a => (dayjs(a?.startDate).tz(timezone, true).format('YYYY-MM-DD') === dayjs(uniqDate).tz(timezone, true).format('YYYY-MM-DD')))

            queryData += `${dayjs(uniqDate).tz(timezone, true).format('ddd, YYYY-MM-DD')}`
            queryData += '\n'

            for (const event of filteredEvents) {
                queryData += 'Event - '

                queryData += `title: ${event?.title || event?.summary}, `
                queryData += `time: ${dayjs(event?.startDate).tz(timezone, true).format('LT')} `
                queryData += `- ${dayjs(event?.endDate).tz(timezone, true).format('LT')}, `

                if (body?.attributes?.find(a => (a === 'none'))) {
                    continue
                }

                if (body?.attributes?.find(a => (a === 'all'))) {
                    // queryData += `${property}: ${event[property]} `
                    // queryData += `id: ${event?.id}, `
                    
                } else {
                    for (const property in event) {

                        if (property === 'allDay') {
    
                            if (body?.attributes?.find(a => (a === 'allDay'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'title') {
                            // queryData += `${property}: ${event[property]}, `
                            continue
                        } else if (property === 'startDate') {
                            continue
                        } else if (property === 'endDate') {
                            continue
                        } else if (property === 'recurrenceRule') {
    
                            if (body?.attributes?.find(a => (a === 'recurrenceRule'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'location') {
    
                            if (body?.attributes?.find(a => (a === 'location'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'notes') {
    
                            if (body?.attributes?.find(a => (a === 'notes'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'timezone') {
    
                            continue
                        } else if (property === 'taskId') {
    
                            if (body?.attributes?.find(a => (a === 'taskId'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'priority') {
    
                            if (body?.attributes?.find(a => (a === 'priority'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'isFollowUp') {
    
                            if (body?.attributes?.find(a => (a === 'isFollowUp'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'isPreEvent') {
    
                            if (body?.attributes?.find(a => (a === 'isPreEvent'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'isPostEvent') {
    
                            if (body?.attributes?.find(a => (a === 'isPostEvent'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'modifiable') {
    
                            if (body?.attributes?.find(a => (a === 'modifiable'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'isBreak') {
    
                            if (body?.attributes?.find(a => (a === 'isBreak'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'bufferTime') {
    
                            if (body?.attributes?.find(a => (a === 'bufferTime'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'hardDeadline') {
    
                            if (body?.attributes?.find(a => (a === 'hardDeadline'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'softDeadline') {
    
                            if (body?.attributes?.find(a => (a === 'softDeadline'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        } else if (property === 'duration') {
    
                            if (body?.attributes?.find(a => (a === 'duration'))) {
                                queryData += `${property}: ${event[property]}, `
                            }
                        }
    
                    }
                }

                if (event?.conferenceId) {
                    const filteredConf = conferences?.find(c => (c?.id === event?.conferenceId))

                    if (filteredConf?.id) {
                        queryData += ' conference with event - '
                        queryData += `name: ${filteredConf?.name}, `
                        queryData += `app: ${filteredConf?.app}, `

                        for (const property in filteredConf) {
                            if (property === 'notes') {

                                if (body?.attributes?.find(a => (a === 'conference-notes'))) {
                                    queryData += `${property}: ${filteredConf[property]}, `
                                }
                            } else if (property === 'joinUrl') {

                                if (body?.attributes?.find(a => (a === 'conference-joinUrl'))) {
                                    queryData += `${property}: ${filteredConf[property]}, `
                                }
                            } else if (property === 'startUrl') {

                                if (body?.attributes?.find(a => (a === 'conference-startUrl'))) {
                                    queryData += `${property}: ${filteredConf[property]}, `
                                }
                            }
                        }

                        if (attendees?.length > 0) {
                            queryData += 'attendees - '

                            for (const attendee of attendees) {
                                queryData += `name: ${attendee?.name}`
                                queryData += `email: ${attendee?.emails?.find(e => (!!e?.primary))?.value}`
                            }
                        }
                    }
                }

                if (event?.taskId) {
                    const filteredTask = tasks?.find(t => (t?.id === event?.taskId))

                    if (filteredTask?.id) {
                        queryData += ' task with event - '
                        queryData += `${filteredTask?.notes}, `

                        for (const property in filteredTask) {
                            if (property === 'type') {

                                if (body?.attributes?.find(a => (a === 'task-listName'))) {
                                    queryData += `list: ${filteredTask[property]}, `
                                }
                            } else if (property === 'status') {

                                if (body?.attributes?.find(a => (a === 'task-status'))) {
                                    queryData += `status: ${filteredTask[property]}, `
                                }
                            }
                        }
                    }
                }
                

                queryData += '\n'
            }

            queryData += '\n\n'
        }


        if (count > 0) {
            queryData += `count: ${count}`
        }

        console.log(queryData, queryData?.length, ' queryData, length')
        // success response
        response.query = 'completed'

        response.data = queryData

        return response
    } catch (e) {
        console.log(e, ' unable to do final step query event')
    }
}

export const processQueryEventPending = async (
    userId: string,
    timezone: string,
    jsonBody: UserInputToJSONType,
    // dateTimeJSONBody: DateTimeJSONType,
    attributesObject: QueryCalendarExtractedAttributesType,
    queryDateJSONBody: QueryCalendarExtractedJSONType,
    currentTime: string,
): Promise<ResponseActionType> => {
    try {
        let windowStartDate = extrapolateStartDateFromJSONData(
            currentTime,
            timezone,
            queryDateJSONBody?.start_date?.year,
            queryDateJSONBody?.start_date?.month,
            queryDateJSONBody?.start_date?.day,
            undefined,
            queryDateJSONBody?.start_date?.hour,
            queryDateJSONBody?.start_date?.minute,
            queryDateJSONBody?.start_date?.time,
            queryDateJSONBody?.start_date?.relativeTimeChangeFromNow,
            queryDateJSONBody?.start_date?.relativeTimeFromNow,
        )

        let windowEndDate = extrapolateEndDateFromJSONData(
            currentTime,
            timezone,
            queryDateJSONBody?.end_date?.year,
            queryDateJSONBody?.end_date?.month,
            queryDateJSONBody?.end_date?.day,
            undefined,
            queryDateJSONBody?.end_date?.hour,
            queryDateJSONBody?.end_date?.minute,
            queryDateJSONBody?.end_date?.time,
            queryDateJSONBody?.end_date?.relativeTimeChangeFromNow,
            queryDateJSONBody?.end_date?.relativeTimeFromNow,
        )

        if (!windowStartDate) {
            windowStartDate = dayjs().subtract(2, 'w').format()
        }

        if (!windowEndDate) {
            windowEndDate = dayjs().add(4, 'w').format()
        }

        const body: QueryEventType = {
            userId,
            timezone,
            title: jsonBody?.params?.title || jsonBody?.params?.summary || jsonBody?.params?.description || jsonBody?.params?.taskList?.[0]?.task,
            isMeeting: attributesObject?.isMeeting,
            attributes: attributesObject?.attributes,
            windowStartDate,
            windowEndDate,
        }

        console.log(body, ' body inside find-event')
        // validate
        const response: any = {
            query: '',
            data: {},
            skill: 'queryEvent'
        }

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

        const response2 = await finalStepQueryEvent(body, windowStartDate, windowEndDate, timezone, response)

        return response2
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

    } catch (e) {
        console.log(e, ' unable to process query event')
    }
}

export const processQueryEventMissingFieldsReturned = async (
    userId: string,
    timezone: string,
    jsonBody: UserInputToJSONType,
    // dateTimeJSONBody: DateTimeJSONType,
    attributesObject: QueryCalendarExtractedAttributesType,
    queryDateJSONBody: QueryCalendarExtractedJSONType,
    currentTime: string,
    messageHistoryObject: SkillMessageHistoryType,
) => {
    try {

        let windowStartDate = extrapolateStartDateFromJSONData(
            currentTime,
            timezone,
            queryDateJSONBody?.start_date?.year,
            queryDateJSONBody?.start_date?.month,
            queryDateJSONBody?.start_date?.day,
            undefined,
            queryDateJSONBody?.start_date?.hour,
            queryDateJSONBody?.start_date?.minute,
            queryDateJSONBody?.start_date?.time,
            queryDateJSONBody?.start_date?.relativeTimeChangeFromNow,
            queryDateJSONBody?.start_date?.relativeTimeFromNow,
        )

        let windowEndDate = extrapolateEndDateFromJSONData(
            currentTime,
            timezone,
            queryDateJSONBody?.end_date?.year,
            queryDateJSONBody?.end_date?.month,
            queryDateJSONBody?.end_date?.day,
            undefined,
            queryDateJSONBody?.end_date?.hour,
            queryDateJSONBody?.end_date?.minute,
            queryDateJSONBody?.end_date?.time,
            queryDateJSONBody?.end_date?.relativeTimeChangeFromNow,
            queryDateJSONBody?.end_date?.relativeTimeFromNow,
        )

        if (!windowStartDate) {
            windowStartDate = dayjs().subtract(2, 'w').format()
        }

        if (!windowEndDate) {
            windowEndDate = dayjs().add(4, 'w').format()
        }

        const newBody: QueryEventType = {
            userId,
            timezone,
            title: jsonBody?.params?.title || jsonBody?.params?.summary || jsonBody?.params?.description || jsonBody?.params?.taskList?.[0]?.task || messageHistoryObject?.prevJsonBody?.params?.title || messageHistoryObject?.prevJsonBody?.params?.summary || messageHistoryObject?.prevJsonBody?.params?.description || messageHistoryObject?.prevJsonBody?.params?.taskList?.[0]?.task,
            isMeeting: attributesObject?.isMeeting,
            attributes: attributesObject?.attributes,
            windowStartDate,
            windowEndDate,
        }

        const prevBody: QueryEventType = {
            ...messageHistoryObject?.prevData,
            windowStartDate: messageHistoryObject?.prevDataExtra?.windowStartDate,
            windowEndDate: messageHistoryObject?.prevDataExtra?.windowEndDate,
        }

        // fix prevBody with new data
        if (!prevBody?.userId) {
            prevBody.userId = userId || newBody?.userId
        }

        if (!prevBody?.timezone) {
            prevBody.timezone = timezone || newBody?.timezone
        }

        if (!prevBody?.title) {
            prevBody.title = newBody?.title
        }

        if (prevBody?.isMeeting === undefined) {
            prevBody.isMeeting = newBody?.isMeeting
        }

        if (!(prevBody?.attributes?.length > 0)) {
            prevBody.attributes = newBody?.attributes
        }

        if (!prevBody?.windowStartDate) {
            prevBody.windowStartDate = newBody?.windowStartDate
        }

        if (!prevBody?.windowEndDate) {
            prevBody.windowEndDate = newBody?.windowEndDate
        }

        const response: any = {
            query: '',
            data: {},
            skill: 'queryEvent'
        }

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

        const response2 = await finalStepQueryEvent(prevBody, prevBody?.windowStartDate, prevBody?.windowEndDate, prevBody?.timezone, response)

        return response2

    } catch (e) {
        console.log(e, ' unable to process query event missing fields returned')
    }
}

export const askEventControlCenter = async (
    openai: OpenAI,
    userId: string,
    timezone: string,
    messageHistoryObject: SkillMessageHistoryType,
    userCurrentTime: string,
    query: 'missing_fields' | 'completed' | 'event_not_found' | 'pending',
) => {
    try {
        const messageLength = messageHistoryObject.messages?.length
        let userMessage = ''
        for (let i = messageLength; i > 0; i--) {

            const message = messageHistoryObject.messages[i - 1]

            if (message.role === 'user') {
                userMessage = message.content
                break
            }
        }
        const userInput = userMessage

        console.log(messageHistoryObject, ' messageHistoryObject before api call')

        // generateJSONDataFromUserInput
        
        const attributesObject = await extractAttributesNeededFromUserInput(userInput)
        
        let eventRes: ResponseActionType = {
            query: 'completed',
            data: '',
            skill: '',
            prevData: {},
            prevDataExtra: {},
        }

        switch (query) {
            case 'pending':
                const jsonBody = await generateJSONDataFromUserInput(userInput, userCurrentTime)
                const queryDate = await generateQueryDateFromUserInput(userId, timezone, userInput, userCurrentTime)
                eventRes = await processQueryEventPending(userId, timezone, jsonBody, attributesObject, queryDate, userCurrentTime)
                break
            case 'missing_fields':
                let priorUserInput = ''
                let priorAssistantOutput = ''
                
                for (let i = messageLength; i > 0; i--) {

                    const message = messageHistoryObject.messages[i - 1]
        
                    if (message.role === 'assistant') {
                        priorAssistantOutput = message.content
                        continue
                    }

                    if (message.role === 'user') {
                        if (message.content !== userInput) {
                            priorUserInput = message.content
                            break
                        }
                        
                    }
                }

                if (!priorUserInput || !priorAssistantOutput) {
                    console.log(priorUserInput,  ' priorUserInput')
                    console.log(priorAssistantOutput, ' priorAssistantOutput')
                    throw new Error('no priorUserinput or priorAssistantOutput')
                }
                const jsonMissingFieldsBody = await generateMissingFieldsJSONDataFromUserInput(userInput, priorUserInput, priorAssistantOutput, userCurrentTime)
                const queryMissingFieldsDate = await generateMissingFieldsQueryDateFromUserInput(userId, timezone, userInput, priorUserInput, priorAssistantOutput, userCurrentTime)
                eventRes = await processQueryEventMissingFieldsReturned(userId, timezone, jsonMissingFieldsBody, attributesObject, queryMissingFieldsDate, userCurrentTime, messageHistoryObject)
                break
        }
        
        if (eventRes?.query === 'completed') {
            const assistantMessage = await generateAssistantMessageFromAPIResponseForUserQuery(openai, eventRes.data as string, messageHistoryObject)
            console.log(assistantMessage, ' assistantMessage')
            messageHistoryObject.messages.push(assistantMessage)
            messageHistoryObject.query = 'completed'
            messageHistoryObject.required = null
        } else if (eventRes?.query === 'missing_fields') {

            const assistantMessage = await generateAssistantMessageToRequestUserForMissingFields(openai, eventRes?.data as RequiredFieldsType, messageHistoryObject)

            messageHistoryObject.messages.push(assistantMessage)
            messageHistoryObject.query = 'missing_fields'
            messageHistoryObject.required = eventRes?.data as RequiredFieldsType
            messageHistoryObject.prevData = eventRes?.prevData
            messageHistoryObject.prevDataExtra = eventRes?.prevDataExtra
            messageHistoryObject.prevDateJsonBody = eventRes?.prevDateJsonBody
            messageHistoryObject.prevJsonBody = eventRes?.prevJsonBody
        } else if (eventRes?.query === 'event_not_found') {
            const assistantMessage: AssistantMessageType = {
                role: 'assistant',
                content: 'Oops... I couldn\'t find the event. Sorry :(',
            }

            messageHistoryObject.messages.push(assistantMessage)
            messageHistoryObject.query = 'event_not_found'
            messageHistoryObject.required = null
        }

        return messageHistoryObject

    } catch (e) {
        console.log(e, ' unable to process ask event inside control center')
    }
}
