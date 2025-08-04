import QueryCalendarExtractedJSONType from '@chat/_libs/datetime/QueryCalendarExtractedDateJSONType';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import { QueryCalendarExtractedAttributesType } from '@chat/_libs/skills/askCalendar/types';
import {
  searchMultipleEventsByVectorWithDatesLanceDb,
  convertEventTitleToOpenAIVector,
  extractAttributesNeededFromUserInput,
  extrapolateEndDateFromJSONData,
  extrapolateStartDateFromJSONData,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateJSONDataFromUserInput,
  generateMissingFieldsJSONDataFromUserInput,
  generateMissingFieldsQueryDateFromUserInput,
  generateQueryDateFromUserInput,
} from '@chat/_libs/api-helper'; // Updated import
import { QueryEventsType } from './types';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { EventSchema as LanceDbEventSchema } from '@functions/_utils/lancedb_service'; // Added import
import { listSortedObjectsForUserGivenDatesAndAttributes } from '@chat/_libs/skills/askCalendar/api-helper';
import _ from 'lodash';
import OpenAI from 'openai';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import { EventType } from '@chat/_libs/types/EventType';
import { ConferenceType } from '@chat/_libs/types/ConferenceType';
import { AttendeeType } from '@chat/_libs/types/AttendeeType';
import { TaskType } from '@chat/_libs/types/TaskType';

export const finalStepQueryEvents = async (
  body: QueryEventsType,
  windowStartDate: string,
  windowEndDate: string,
  timezone: string,
  response: any
) => {
  try {
    let searchVector: number[] = [];

    if (body?.title) {
      searchVector = await convertEventTitleToOpenAIVector(body?.title);
    }

    const eventIds: string[] = [];

    if (searchVector?.length > 0) {
      const searchResults = await searchMultipleEventsByVectorWithDatesLanceDb(
        body?.userId,
        searchVector,
        windowStartDate,
        windowEndDate
      ); // Updated call

      for (const event of searchResults) {
        // Iterate over LanceDbEventSchema[]
        if (event?.id) {
          eventIds.push(event.id); // Use event.id
        }
      }
    }

    let objectsWithAttributes: {
      events: EventType[];
      conferences: ConferenceType[];
      attendees: AttendeeType[];
      tasks: TaskType[];
      count: number;
    };

    if (eventIds?.length > 0) {
      objectsWithAttributes =
        await listSortedObjectsForUserGivenDatesAndAttributes(
          body?.userId,
          body?.windowStartDate,
          body?.windowEndDate,
          body?.attributes,
          body?.isMeeting,
          eventIds
        );
    } else {
      objectsWithAttributes =
        await listSortedObjectsForUserGivenDatesAndAttributes(
          body?.userId,
          body?.windowStartDate,
          body?.windowEndDate,
          body?.attributes,
          body?.isMeeting
        );
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
    const uniqDates = _.uniqBy(events, (curr) =>
      dayjs(curr?.startDate).tz(timezone, true).format('YYYY-MM-DD')
    )?.map((e) => e?.startDate);

    for (const uniqDate of uniqDates) {
      const filteredEvents = events?.filter(
        (a) =>
          dayjs(a?.startDate).tz(timezone, true).format('YYYY-MM-DD') ===
          dayjs(uniqDate).tz(timezone, true).format('YYYY-MM-DD')
      );

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
        } else {
          for (const property in event) {
            if (property === 'allDay') {
              if (body?.attributes?.find((a) => a === 'allDay')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'title') {
              // queryData += `${property}: ${event[property]}, `
              continue;
            } else if (property === 'startDate') {
              continue;
            } else if (property === 'endDate') {
              continue;
            } else if (property === 'recurrenceRule') {
              if (body?.attributes?.find((a) => a === 'recurrenceRule')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'location') {
              if (body?.attributes?.find((a) => a === 'location')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'notes') {
              if (body?.attributes?.find((a) => a === 'notes')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'timezone') {
              continue;
            } else if (property === 'taskId') {
              if (body?.attributes?.find((a) => a === 'taskId')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'priority') {
              if (body?.attributes?.find((a) => a === 'priority')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'isFollowUp') {
              if (body?.attributes?.find((a) => a === 'isFollowUp')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'isPreEvent') {
              if (body?.attributes?.find((a) => a === 'isPreEvent')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'isPostEvent') {
              if (body?.attributes?.find((a) => a === 'isPostEvent')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'modifiable') {
              if (body?.attributes?.find((a) => a === 'modifiable')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'isBreak') {
              if (body?.attributes?.find((a) => a === 'isBreak')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'bufferTime') {
              if (body?.attributes?.find((a) => a === 'bufferTime')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'hardDeadline') {
              if (body?.attributes?.find((a) => a === 'hardDeadline')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'softDeadline') {
              if (body?.attributes?.find((a) => a === 'softDeadline')) {
                queryData += `${property}: ${event[property]}, `;
              }
            } else if (property === 'duration') {
              if (body?.attributes?.find((a) => a === 'duration')) {
                queryData += `${property}: ${event[property]}, `;
              }
            }
          }
        }

        if (event?.conferenceId) {
          const filteredConf = conferences?.find(
            (c) => c?.id === event?.conferenceId
          );

          if (filteredConf?.id) {
            queryData += ' conference with event - ';
            queryData += `name: ${filteredConf?.name}, `;
            queryData += `app: ${filteredConf?.app}, `;

            for (const property in filteredConf) {
              if (property === 'notes') {
                if (body?.attributes?.find((a) => a === 'conference-notes')) {
                  queryData += `${property}: ${filteredConf[property]}, `;
                }
              } else if (property === 'joinUrl') {
                if (body?.attributes?.find((a) => a === 'conference-joinUrl')) {
                  queryData += `${property}: ${filteredConf[property]}, `;
                }
              } else if (property === 'startUrl') {
                if (
                  body?.attributes?.find((a) => a === 'conference-startUrl')
                ) {
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
              } else if (property === 'status') {
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
  } catch (e) {
    console.log(e, ' unable to final step query events');
  }
};

export const processQueryEventsPending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  // dateTimeJSONBody: DateTimeJSONType,
  attributesObject: QueryCalendarExtractedAttributesType,
  queryDateJSONBody: QueryCalendarExtractedJSONType,
  currentTime: string
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
      queryDateJSONBody?.start_date?.relativeTimeFromNow
    );

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
      queryDateJSONBody?.end_date?.relativeTimeFromNow
    );

    if (!windowStartDate) {
      windowStartDate = dayjs().subtract(2, 'w').format();
    }

    if (!windowEndDate) {
      windowEndDate = dayjs().add(4, 'w').format();
    }

    const body: QueryEventsType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      isMeeting: attributesObject?.isMeeting,
      attributes: attributesObject?.attributes,
      windowStartDate,
      windowEndDate,
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'find-events',
    };

    const response2 = await finalStepQueryEvents(
      body,
      body?.windowStartDate,
      body?.windowEndDate,
      body?.timezone,
      response
    );

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
  } catch (e) {
    console.log(e, ' unable to process query events');
  }
};

export const processQueryEventsMissingFieldsReturned = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  // dateTimeJSONBody: DateTimeJSONType,
  attributesObject: QueryCalendarExtractedAttributesType,
  queryDateJSONBody: QueryCalendarExtractedJSONType,
  currentTime: string,
  messageHistoryObject: SkillMessageHistoryType
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
      queryDateJSONBody?.start_date?.relativeTimeFromNow
    );

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
      queryDateJSONBody?.end_date?.relativeTimeFromNow
    );

    if (!windowStartDate) {
      windowStartDate = dayjs().subtract(2, 'w').format();
    }

    if (!windowEndDate) {
      windowEndDate = dayjs().add(4, 'w').format();
    }

    const newBody: QueryEventsType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
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

    const prevBody: QueryEventsType = {
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

    const response: any = {
      query: '',
      data: {},
      skill: 'find-events',
    };

    const response2 = await finalStepQueryEvents(
      prevBody,
      prevBody?.windowStartDate,
      prevBody?.windowEndDate,
      prevBody?.timezone,
      response
    );

    return response2;
  } catch (e) {
    console.log(e, ' unable to query events missing fields returned');
  }
};

export const queryEventsControlCenter = async (
  openai: OpenAI,
  userId: string,
  timezone: string,
  messageHistoryObject: SkillMessageHistoryType,
  userCurrentTime: string,
  query: 'missing_fields' | 'completed' | 'event_not_found' | 'pending'
) => {
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

    const attributesObject =
      await extractAttributesNeededFromUserInput(userInput);

    let eventsRes: ResponseActionType = {
      query: 'completed',
      data: '',
      skill: '',
      prevData: {},
      prevDataExtra: {},
    };

    switch (query) {
      case 'pending':
        const jsonBody = await generateJSONDataFromUserInput(
          userInput,
          userCurrentTime
        );
        const queryDate = await generateQueryDateFromUserInput(
          userId,
          timezone,
          userInput,
          userCurrentTime
        );
        eventsRes = await processQueryEventsPending(
          userId,
          timezone,
          jsonBody,
          attributesObject,
          queryDate,
          userCurrentTime
        );
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
        const jsonMissingFieldsBody =
          await generateMissingFieldsJSONDataFromUserInput(
            userInput,
            priorUserInput,
            priorAssistantOutput,
            userCurrentTime
          );
        const queryMissingFieldsDate =
          await generateMissingFieldsQueryDateFromUserInput(
            userId,
            timezone,
            userInput,
            priorUserInput,
            priorAssistantOutput,
            userCurrentTime
          );

        eventsRes = await processQueryEventsMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          attributesObject,
          queryMissingFieldsDate,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    // const eventsRes = await processQueryEventsPending(userId, timezone, jsonBody, attributesObject, queryDate, userCurrentTime)
    if (eventsRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          eventsRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (eventsRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          eventsRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = eventsRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = eventsRes?.prevData;
      messageHistoryObject.prevDataExtra = eventsRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = eventsRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = eventsRes?.prevJsonBody;
    } else if (eventsRes?.query === 'event_not_found') {
      const assistantMessage: AssistantMessageType = {
        role: 'assistant',
        content: "Oops... I couldn't find the event. Sorry :(",
      };

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'event_not_found';
      messageHistoryObject.required = null;
    }

    return messageHistoryObject;
  } catch (e) {
    console.log(e, ' unable to query events');
  }
};
