import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import { DeletePriorityType } from './types';
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
import { untrainEventWithPriorityAndModifiable } from '../resolveConflictingEvents/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import { SearchBoundaryType } from '../deleteTask/types';

export const finalStepDeletePriority = async (
  body: DeletePriorityType,
  startDate: string,
  endDate: string,
  response: any
) => {
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

    await untrainEventWithPriorityAndModifiable(id, false, 1);

    // delete data in train index
    await deleteDocInTrainEventIndexInOpenSearch(id);

    // success response
    response.query = 'completed';
    response.data = 'successfully deleted priority';
    return response;
  } catch (e) {
    console.log(e, ' unable to delete priority');
  }
};

export const processDeletePriorityPending = async (
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

    const body: DeletePriorityType = {
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

    const response2 = await finalStepDeletePriority(
      body,
      startDate,
      endDate,
      response
    );

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
  } catch (e) {
    console.log(e, ' unable to process add priority');
  }
};

export const processDeletePriorityMissingFieldsReturned = async (
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

    const newBody: DeletePriorityType = {
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

    const prevBody: DeletePriorityType = {
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

    const response2 = await finalStepDeletePriority(
      prevBody,
      prevStartDate,
      prevEndDate,
      response
    );

    return response2;
  } catch (e) {
    console.log(
      e,
      ' unable to process delete priority time missing fields returned'
    );
  }
};

export const deletePriorityControlCenter = async (
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

    let deletePriorityRes: ResponseActionType = {
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
        deletePriorityRes = await processDeletePriorityPending(
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

        deletePriorityRes = await processDeletePriorityMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (deletePriorityRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          deletePriorityRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (deletePriorityRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          deletePriorityRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required =
        deletePriorityRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = deletePriorityRes.prevData;
      messageHistoryObject.prevDataExtra = deletePriorityRes.prevDataExtra;
      messageHistoryObject.prevDateJsonBody =
        deletePriorityRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = deletePriorityRes?.prevJsonBody;
    } else if (deletePriorityRes?.query === 'event_not_found') {
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
    console.log(e, ' unable to delete priority control center pending');
  }
};
