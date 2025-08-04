import {
  allEventWithDatesOpenSearch,
  convertEventTitleToOpenAIVector,
  deleteDocInAllEventIndexInOpenSearch,
  deleteDocInTrainEventIndexInOpenSearch,
  deleteEventGivenId,
  eventSearchBoundary,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
  getEventFromPrimaryKey,
} from '@chat/_libs/api-helper';
import { hasuraAdminSecret, hasuraGraphUrl } from '@chat/_libs/constants';
import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import deleteTaskById from '@chat/_libs/gql/deleteTaskById';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import { TaskType } from '@chat/_libs/types/TaskType';
import got from 'got';
import { DeleteTaskType, SearchBoundaryType } from './types';
import requiredFields from './requiredFields';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';

export const deleteTaskGivenId = async (id: string): Promise<TaskType> => {
  try {
    const operationName = 'DeleteTaskById';
    const query = deleteTaskById;
    const res: { data: { delete_Task_by_pk: TaskType } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables: {
            id,
          },
        },
      })
      .json();
    console.log(res, ' res from getTaskGivenId');
    return res?.data?.delete_Task_by_pk;
  } catch (e) {
    console.log(e, ' getTaskGivenId');
  }
};

export const finalStepDeleteTask = async (
  body: DeleteTaskType,
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

    // delete data in train index
    await deleteDocInTrainEventIndexInOpenSearch(id);

    await deleteDocInAllEventIndexInOpenSearch(id);

    const eventToDelete = await getEventFromPrimaryKey(id);

    await deleteTaskGivenId(eventToDelete?.taskId);

    await deleteEventGivenId(id);

    // success response
    response.query = 'completed';
    response.data = 'task successfully deleted';
    return response;
  } catch (e) {
    console.log(e, ' unable to final step delete task');
  }
};

export const processDeleteTaskPending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string
) => {
  try {
    const searchBoundary = eventSearchBoundary(
      timezone,
      dateJSONBody,
      currentTime
    );

    let startDate = searchBoundary.startDate;
    let endDate = searchBoundary.endDate;

    const body: DeleteTaskType = {
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
      skill: 'deleteTask',
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

    const response2 = await finalStepDeleteTask(
      body,
      startDate,
      endDate,
      response
    );
    return response2;
  } catch (e) {
    console.log(e, ' unable to process delete task');
  }
};

export const processDeleteTaskMissingFieldsReturned = async (
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

    const newBody: DeleteTaskType = {
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

    const prevBody: DeleteTaskType = {
      ...messageHistoryObject?.prevData,
    };

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

    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'deleteTask',
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

    const response2 = await finalStepDeleteTask(
      prevBody,
      prevStartDate,
      prevEndDate,
      response
    );
    return response2;
  } catch (e) {
    console.log(e, ' unable to process delete task missing fields returned');
  }
};

export const deleteTaskControlCenter = async (
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

    let deleteTaskRes: ResponseActionType = {
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
        deleteTaskRes = await processDeleteTaskPending(
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

        deleteTaskRes = await processDeleteTaskMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (deleteTaskRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          deleteTaskRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (deleteTaskRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          deleteTaskRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = deleteTaskRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = deleteTaskRes?.prevData;
      messageHistoryObject.prevDataExtra = deleteTaskRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = deleteTaskRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = deleteTaskRes?.prevJsonBody;
    } else if (deleteTaskRes?.query === 'event_not_found') {
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
    console.log(e, ' unable to delete task control center pending');
  }
};
