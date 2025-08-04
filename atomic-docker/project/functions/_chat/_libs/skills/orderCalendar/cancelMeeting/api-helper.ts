import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import { CancelMeetingType } from './types';
import requiredFields from './requiredFields';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import {
  allEventWithDatesOpenSearch,
  convertEventTitleToOpenAIVector,
  deleteConferenceGivenId,
  deleteDocInAllEventIndexInOpenSearch,
  deleteDocInTrainEventIndexInOpenSearch,
  deleteEventGivenId,
  deleteGoogleEvent,
  deleteZoomMeeting,
  eventSearchBoundary,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
  getCalendarIntegrationByName,
  getConferenceGivenId,
  getEventFromPrimaryKey,
  getZoomAPIToken,
} from '@chat/_libs/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { googleCalendarName } from '@chat/_libs/constants';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import OpenAI from 'openai';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import { SearchBoundaryType } from '../deleteTask/types';

export const finalStepCancelMeeting = async (
  body: CancelMeetingType,
  eventId: string,
  response: any
) => {
  try {
    // get old event
    const oldEvent = await getEventFromPrimaryKey(eventId);

    // validate
    if (!oldEvent?.id) {
      throw new Error('no old event found?!');
    }

    // delete any zoom conferences
    if (oldEvent?.conferenceId) {
      // get old conference object
      const oldConference = await getConferenceGivenId(oldEvent?.conferenceId);

      if (oldConference?.app === 'zoom') {
        // create conference object
        const zoomToken = await getZoomAPIToken(body?.userId);

        // deleteZoomMeeting
        await deleteZoomMeeting(zoomToken, parseInt(oldConference?.id, 10));

        await deleteConferenceGivenId(oldConference?.id);
      }
    }

    // get client type
    const calIntegration = await getCalendarIntegrationByName(
      body?.userId,
      googleCalendarName
    );

    // delete data in train index
    await deleteDocInTrainEventIndexInOpenSearch(eventId);

    await deleteDocInAllEventIndexInOpenSearch(eventId);

    await deleteGoogleEvent(
      body?.userId,
      oldEvent?.calendarId,
      oldEvent?.eventId,
      calIntegration?.clientType
    );

    await deleteEventGivenId(oldEvent?.id);

    // success response
    response.query = 'completed';
    response.data = 'meeting successfully cancelled';
    return response;
  } catch (e) {
    console.log(e, ' unable to final step cancel meeting');
  }
};

export const processCancelMeetingPending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string
): Promise<ResponseActionType> => {
  try {
    const body: CancelMeetingType = {
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
      skill: 'cancelMeeting',
    };

    const searchBoundary = eventSearchBoundary(
      timezone,
      dateJSONBody,
      currentTime
    );

    let startDate = searchBoundary.startDate;
    let endDate = searchBoundary.endDate;

    // validate remaining required fields
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
      userId,
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

    const response2 = await finalStepCancelMeeting(body, id, response);
    return response2;
    // // get old event
    // const oldEvent = await getEventFromPrimaryKey(eventId)

    // // validate
    // if (!oldEvent?.id) {
    //     throw new Error('no old event found?!')
    // }

    // // delete any zoom conferences
    // if (oldEvent?.conferenceId) {

    //     // get old conference object
    //     const oldConference = await getConferenceGivenId(oldEvent?.conferenceId)

    //     if (oldConference?.app === 'zoom') {

    //         // create conference object
    //         const zoomToken = await getZoomAPIToken(userId)

    //         // deleteZoomMeeting
    //         await deleteZoomMeeting(zoomToken, parseInt(oldConference?.id, 10))

    //         await deleteConferenceGivenId(oldConference?.id)
    //     }
    // }

    // // get client type
    // const calIntegration = await getCalendarIntegrationByName(
    //     userId,
    //     googleCalendarName,
    // )

    // // delete data in train index
    // await deleteDocInTrainEventIndexInOpenSearch(id)

    // await deleteDocInAllEventIndexInOpenSearch(id)

    // await deleteGoogleEvent(userId, oldEvent?.calendarId, oldEvent?.eventId, calIntegration?.clientType)

    // await deleteEventGivenId(oldEvent?.id)

    // // success response
    // response.query = 'completed'

    // return response
  } catch (e) {
    console.log(e, ' unable to process cancel meeting');
  }
};

export const processCancelMeetingMissingFieldsReturned = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string,
  messageHistoryObject: SkillMessageHistoryType
) => {
  try {
    const newBody: CancelMeetingType = {
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

    const prevBody: CancelMeetingType = {
      ...messageHistoryObject?.prevData,
      // windowStartDate: messageHistoryObject?.prevDataExtra?.windowStartDate,
      // windowEndDate: messageHistoryObject?.prevDataExtra?.windowEndDate,
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

    // validate for missing fields
    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'cancelMeeting',
    };

    let prevSearchBoundary: SearchBoundaryType = {
      startDate: messageHistoryObject?.prevDataExtra?.searchBoundary?.startDate,
      endDate: messageHistoryObject?.prevDataExtra?.searchBoundary?.endDate,
    };

    if (!prevSearchBoundary?.startDate) {
      const searchBoundaryNew = eventSearchBoundary(
        timezone,
        dateJSONBody,
        currentTime
      );
      prevSearchBoundary.startDate = searchBoundaryNew?.startDate;
    }

    if (!prevSearchBoundary?.endDate) {
      const searchBoundaryNew = eventSearchBoundary(
        timezone,
        dateJSONBody,
        currentTime
      );
      prevSearchBoundary.endDate = searchBoundaryNew?.endDate;
    }

    // prevSearchBoundary = eventSearchBoundary(timezone, dateJSONBody, currentTime)

    let startDate = prevSearchBoundary.startDate;
    let endDate = prevSearchBoundary.endDate;

    // validate remaining required fields
    if (!prevBody?.title) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[0]);
      response.data = missingFields;
      response.prevData = prevBody;
      response.prevDataExtra = {
        searchBoundary: prevSearchBoundary,
      };

      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    if (response.query === 'missing_fields') {
      return response;
    }

    // convert to vector for search
    const searchVector = await convertEventTitleToOpenAIVector(prevBody?.title);

    // allEventOpenSearch
    if (!startDate) {
      startDate = dayjs().subtract(2, 'w').format();
    }

    if (!endDate) {
      endDate = dayjs().add(4, 'w').format();
    }

    const res = await allEventWithDatesOpenSearch(
      userId,
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

    const response2 = await finalStepCancelMeeting(prevBody, id, response);
    return response2;
  } catch (e) {
    console.log(e, ' unable to process cancle meeeting missing fields');
  }
};

export const cancelMeetingControlCenterPending = async (
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

    let cancelMeetingRes: ResponseActionType = {
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
        cancelMeetingRes = await processCancelMeetingPending(
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

        cancelMeetingRes = await processCancelMeetingMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (cancelMeetingRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          cancelMeetingRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (cancelMeetingRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          cancelMeetingRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required =
        cancelMeetingRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = cancelMeetingRes?.prevData;
      messageHistoryObject.prevDataExtra = cancelMeetingRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody =
        cancelMeetingRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = cancelMeetingRes?.prevJsonBody;
    } else if (cancelMeetingRes?.query === 'event_not_found') {
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
    console.log(e, ' unable to cancel meeting');
  }
};
