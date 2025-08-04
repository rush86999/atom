import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import { EditRemovePreferredTimeToPreferredTimesType } from './types';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import requiredFields from './requiredFields';
import {
  allEventWithDatesOpenSearch,
  convertEventTitleToOpenAIVector,
  eventSearchBoundary,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
} from '@chat/_libs/api-helper';
import PreferredTimeRangeType from '@chat/_libs/types/PreferredTimeRangeType';
import {
  deletePreferredTimeRangesByIds,
  listPreferredTimeRangesGivenEventId,
} from '../resolveConflictingEvents/api-helper';
import { DayOfWeekEnum } from './constants';
import { v4 as uuid } from 'uuid';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import { SearchBoundaryType } from '../deleteTask/types';

export const finalStepERPT2PTs = async (
  body: EditRemovePreferredTimeToPreferredTimesType,
  startDate: string,
  endDate: string,
  response: any
) => {
  try {
    // convert to vector for search
    const searchVector = await convertEventTitleToOpenAIVector(body?.title);

    //  allEventWithEventOpenSearch
    if (!startDate) {
      startDate = dayjs().subtract(2, 'w').format();
    }

    if (!endDate) {
      endDate = dayjs().add(4, 'w').format();
    }

    const res = await allEventWithDatesOpenSearch(
      body?.userId,
      searchVector,
      startDate,
      endDate
    );

    const id = res?.hits?.hits?.[0]?._id;

    // validate found event
    if (!id) {
      response.query = 'event_not_found';
      return response;
    }

    const preferredTimeRangesWantRemoved: PreferredTimeRangeType[] = [];

    for (const timepreference of body?.timePreferences) {
      if (timepreference.dayOfWeek?.length > 0) {
        for (const dayOfWeek of timepreference.dayOfWeek) {
          const newPreferredTimeRange: PreferredTimeRangeType = {
            id: uuid(),
            eventId: id,
            dayOfWeek: DayOfWeekEnum[dayOfWeek],
            startTime: timepreference?.timeRange?.startTime,
            endTime: timepreference?.timeRange?.endTime,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            userId: body?.userId,
          };

          preferredTimeRangesWantRemoved.push(newPreferredTimeRange);
        }
      } else {
        const newPreferredTimeRange: PreferredTimeRangeType = {
          id: uuid(),
          eventId: id,
          startTime: timepreference?.timeRange?.startTime,
          endTime: timepreference?.timeRange?.endTime,
          updatedAt: dayjs().format(),
          createdDate: dayjs().format(),
          userId: body?.userId,
        };

        preferredTimeRangesWantRemoved.push(newPreferredTimeRange);
      }
    }

    // list existing preferred time ranges
    const oldPreferredTimeRanges =
      await listPreferredTimeRangesGivenEventId(id);

    // find values to remove
    const preferredTimeRangesToBeRemoved: PreferredTimeRangeType[] = [];

    for (const preferredTimeRangeWantToRemove of preferredTimeRangesWantRemoved) {
      for (const oldPreferredTimeRange of oldPreferredTimeRanges) {
        if (
          preferredTimeRangeWantToRemove.dayOfWeek === -1 ||
          !preferredTimeRangeWantToRemove.dayOfWeek
        ) {
          if (
            oldPreferredTimeRange.dayOfWeek === -1 ||
            !oldPreferredTimeRange.dayOfWeek
          ) {
            if (
              preferredTimeRangeWantToRemove.startTime ===
              oldPreferredTimeRange.startTime
            ) {
              preferredTimeRangesToBeRemoved.push(oldPreferredTimeRange);
            }
          }
        } else if (
          preferredTimeRangeWantToRemove?.dayOfWeek ===
          oldPreferredTimeRange?.dayOfWeek
        ) {
          if (
            preferredTimeRangeWantToRemove.startTime ===
            oldPreferredTimeRange.startTime
          ) {
            preferredTimeRangesToBeRemoved.push(oldPreferredTimeRange);
          }
        }
      }
    }

    // delete time ranges to be removed
    if (preferredTimeRangesToBeRemoved?.length > 0) {
      await deletePreferredTimeRangesByIds(
        preferredTimeRangesToBeRemoved?.map((p) => p?.id)
      );
    }

    // success response
    response.query = 'completed';
    response.data = 'successfully removed preferred time';
    return response;
  } catch (e) {
    console.log(e, ' unable to final step ERPT2PTs');
  }
};

export const processERPT2PTsPending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string
): Promise<ResponseActionType> => {
  try {
    const searchBoundary = eventSearchBoundary(
      timezone,
      dateJSONBody,
      currentTime
    );

    let startDate = searchBoundary.startDate;
    let endDate = searchBoundary.endDate;

    const body: EditRemovePreferredTimeToPreferredTimesType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      method: dateJSONBody?.method as any,
      timePreferences: dateJSONBody?.timePreferences,
    };

    // validate for missing fields

    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'editRemovePreferredTimeToPreferredTimes',
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

    // for loop to verify each time preference
    let isMissingDateTimeField = false;
    for (const timePreference of body.timePreferences) {
      if (!timePreference.dayOfWeek && !timePreference.timeRange.startTime) {
        isMissingDateTimeField = true;
      }
    }

    if (isMissingDateTimeField) {
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

    const response2 = await finalStepERPT2PTs(
      body,
      startDate,
      endDate,
      response
    );
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

    // const preferredTimeRangesWantRemoved: PreferredTimeRangeType[] = []

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

    //             preferredTimeRangesWantRemoved.push(newPreferredTimeRange)
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

    //         preferredTimeRangesWantRemoved.push(newPreferredTimeRange)
    //     }

    // }

    // // list existing preferred time ranges
    // const oldPreferredTimeRanges = await listPreferredTimeRangesGivenEventId(id)

    // // find values to remove
    // const preferredTimeRangesToBeRemoved: PreferredTimeRangeType[] = []

    // for (const preferredTimeRangeWantToRemove of preferredTimeRangesWantRemoved) {

    //     for (const oldPreferredTimeRange of oldPreferredTimeRanges) {

    //         if (
    //             (preferredTimeRangeWantToRemove.dayOfWeek === -1)
    //             || (!preferredTimeRangeWantToRemove.dayOfWeek)) {

    //             if (
    //                 (oldPreferredTimeRange.dayOfWeek === -1)
    //                 || (!oldPreferredTimeRange.dayOfWeek)) {

    //                 if (preferredTimeRangeWantToRemove.startTime === oldPreferredTimeRange.startTime) {
    //                     preferredTimeRangesToBeRemoved.push(oldPreferredTimeRange)
    //                 }
    //             }
    //         } else if (preferredTimeRangeWantToRemove?.dayOfWeek === oldPreferredTimeRange?.dayOfWeek) {

    //             if (preferredTimeRangeWantToRemove.startTime === oldPreferredTimeRange.startTime) {
    //                 preferredTimeRangesToBeRemoved.push(oldPreferredTimeRange)
    //             }

    //         }
    //     }
    // }

    // // delete time ranges to be removed
    // if (preferredTimeRangesToBeRemoved?.length > 0) {
    //     await deletePreferredTimeRangesByIds(preferredTimeRangesToBeRemoved?.map(p => (p?.id)))
    // }

    // // success response
    // response.query = 'completed'

    // return response
  } catch (e) {
    console.log(
      e,
      ' unable to process edit and preferred time to preferred times '
    );
  }
};

export const processERPT2PTsMissingFieldsReturned = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string,
  messageHistoryObject: SkillMessageHistoryType
) => {
  try {
    const searchBoundary = eventSearchBoundary(
      timezone,
      dateJSONBody,
      currentTime
    );

    let startDate = searchBoundary.startDate;
    let endDate = searchBoundary.endDate;

    const newBody: EditRemovePreferredTimeToPreferredTimesType = {
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
      method: dateJSONBody?.method as any,
      timePreferences:
        dateJSONBody?.timePreferences ||
        messageHistoryObject?.prevDateJsonBody?.timePreferences ||
        [],
    };

    const prevBody: EditRemovePreferredTimeToPreferredTimesType = {
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

    const prevSearchBoundary: SearchBoundaryType =
      messageHistoryObject?.prevDataExtra?.searchBoundary;

    let prevStartDate = prevSearchBoundary?.startDate;

    let prevEndDate = prevSearchBoundary?.endDate;

    if (!prevStartDate) {
      prevStartDate = startDate;
    }

    if (!prevEndDate) {
      prevEndDate = endDate;
    }

    // validate for missing fields

    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'editRemovePreferredTimeToPreferredTimes',
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

    // for loop to verify each time preference
    let isMissingDateTimeField = false;
    for (const timePreference of prevBody.timePreferences) {
      if (!timePreference.dayOfWeek && !timePreference.timeRange.startTime) {
        isMissingDateTimeField = true;
      }
    }

    if (isMissingDateTimeField) {
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

    const response2 = await finalStepERPT2PTs(
      prevBody,
      prevStartDate,
      prevEndDate,
      response
    );

    return response2;
  } catch (e) {
    console.log(e, ' unable to process ');
  }
};

export const ERPT2PTControlCenter = async (
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

    let eRPT2PTsRes: ResponseActionType = {
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
        const dateTime = await generateDateTime(
          userInput,
          userCurrentTime,
          timezone
        );
        eRPT2PTsRes = await processERPT2PTsPending(
          userId,
          timezone,
          jsonBody,
          dateTime,
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
        const dateMissingFieldsTime = await generateMissingFieldsDateTime(
          userInput,
          priorUserInput,
          priorAssistantOutput,
          userCurrentTime,
          timezone
        );

        eRPT2PTsRes = await processERPT2PTsMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (eRPT2PTsRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          eRPT2PTsRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (eRPT2PTsRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          eRPT2PTsRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = eRPT2PTsRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = eRPT2PTsRes?.prevData;
      messageHistoryObject.prevDataExtra = eRPT2PTsRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = eRPT2PTsRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = eRPT2PTsRes?.prevJsonBody;
    } else if (eRPT2PTsRes?.query === 'event_not_found') {
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
    console.log(e, ' unable to process ERPT2PT control center pending');
  }
};
