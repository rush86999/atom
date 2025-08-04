import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import { RemoveAllPreferredTimes } from './types';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import requiredFields from './requiredFields';
import {
  allEventWithDatesOpenSearch,
  convertEventTitleToOpenAIVector,
  deleteDocInTrainEventIndexInOpenSearch,
  eventSearchBoundary,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
} from '@chat/_libs/api-helper';
import PreferredTimeRangeType from '@chat/_libs/types/PreferredTimeRangeType';
import deletePreferredTimeRangesByEventId from '@chat/_libs/gql/deletePreferredTimeRangesByEventId';
import { hasuraAdminSecret, hasuraGraphUrl } from '@chat/_libs/constants';
import got from 'got';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import { SearchBoundaryType } from '../deleteTask/types';

export const deletePreferredTimeRangesGivenEventId = async (
  eventId: string
) => {
  try {
    const operationName = 'DeletePreferredTimeRangesGivenEventId';
    const query = deletePreferredTimeRangesByEventId;
    const variables = {
      eventId,
    };

    const res: {
      data: {
        delete_PreferredTimeRange: {
          affected_rows: number;
          returning: PreferredTimeRangeType[];
        };
      };
    } = await got
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

    console.log(
      res?.data?.delete_PreferredTimeRange?.affected_rows,
      ' res inside deletePreferredTimeRangesGivenEventId'
    );

    return res?.data?.delete_PreferredTimeRange?.returning;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const finalStepRemoveAllPreferredTimes = async (
  body: RemoveAllPreferredTimes,
  startDate: string,
  endDate: string,
  response: any
) => {
  try {
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

    // delete all preferred time ranges

    await deletePreferredTimeRangesGivenEventId(id);

    // delete data in train index
    await deleteDocInTrainEventIndexInOpenSearch(id);

    // success response
    response.query = 'completed';
    response.data = 'successfully removed all preferred times';
    return response;
  } catch (e) {
    console.log(e, ' unable to final step RemoveAllPreferredTimes');
  }
};

export const processRemoveAllPreferredTimesPending = async (
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

    const body: RemoveAllPreferredTimes = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      method: dateJSONBody?.method as any,
    };

    // validate for missing fields

    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
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

    const response2 = await finalStepRemoveAllPreferredTimes(
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

    // // delete all preferred time ranges

    // await deletePreferredTimeRangesGivenEventId(id)

    // // delete data in train index
    // await deleteDocInTrainEventIndexInOpenSearch(id)

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

export const processRemoveAllPreferredTimesMissingFieldsReturned = async (
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

    const newBody: RemoveAllPreferredTimes = {
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
    };

    const prevBody: RemoveAllPreferredTimes = {
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

    const response2 = await finalStepRemoveAllPreferredTimes(
      prevBody,
      prevStartDate,
      prevEndDate,
      response
    );

    return response2;
  } catch (e) {
    console.log(
      e,
      ' unable to process removal all preferred times missing fields returned'
    );
  }
};

export const RAPControlCenter = async (
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

    let RAPTRes: ResponseActionType = {
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
        RAPTRes = await processRemoveAllPreferredTimesPending(
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

        RAPTRes = await processRemoveAllPreferredTimesMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (RAPTRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          RAPTRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (RAPTRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          RAPTRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = RAPTRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = RAPTRes?.prevData;
      messageHistoryObject.prevDataExtra = RAPTRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = RAPTRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = RAPTRes?.prevJsonBody;
    } else if (RAPTRes?.query === 'event_not_found') {
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
    console.log(
      e,
      ' unable to remove all preferred times control center pending'
    );
  }
};
