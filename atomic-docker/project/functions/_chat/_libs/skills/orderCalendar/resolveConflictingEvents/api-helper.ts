import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import { ResolveConflictingEventsType } from './types';
import UserInputToJSONType from '@chat/_libs/types/UserInputToJSONType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
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
  putDataInTrainEventIndexInOpenSearch,
} from '@chat/_libs/api-helper';
import listPreferredTimeRangesByEventId from '@chat/_libs/gql/listPreferredTimeRangesByEventId';
import PreferredTimeRangeType from '@chat/_libs/types/PreferredTimeRangeType';
import got from 'got';
import { hasuraAdminSecret, hasuraGraphUrl } from '@chat/_libs/constants';
import { v4 as uuid } from 'uuid';
import { DayOfWeekEnum } from './constants';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import deletePreferredTimeRangesWithIds from '@chat/_libs/gql/deletePreferredTimeRangesWithIds';

import { EventType } from '@chat/_libs/types/EventType';
import upsertPreferredTimeRanges from '@chat/_libs/gql/upsertPreferredTimeRanges';
import trainEventWithPriorityAndModifiableGraphql from '@chat/_libs/gql/trainEventWithPriorityAndModifiable';
import trainEventModifiable from '@chat/_libs/gql/trainEventModifiable';
import untrainEventModifiable from '@chat/_libs/gql/untrainEventModifiable';
import updateEventModifiable from '@chat/_libs/gql/updateEventModifiable';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import { SearchBoundaryType } from '../deleteTask/types';

export const upsertPreferredTimeRangesForEvent = async (
  preferredTimeRanges: PreferredTimeRangeType[]
) => {
  try {
    const operationName = 'UpsertPreferredTimeRanges';
    const query = upsertPreferredTimeRanges;
    const variables = {
      preferredTimeRanges,
    };

    const res: {
      data: {
        insert_PreferredTimeRange: {
          affected_rows: number;
          returning: PreferredTimeRangeType;
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
      res?.data?.insert_PreferredTimeRange?.affected_rows,
      ' res inside upsertPreferredTimeRangesForEvent'
    );

    return res?.data?.insert_PreferredTimeRange?.returning;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const trainEventWithPriorityAndModifiable = async (
  id: string,
  modifiable: boolean,
  priority: number
) => {
  try {
    const operationName = 'UpdateEventTrainingWithPriorityAndModifiable';
    const query = trainEventWithPriorityAndModifiableGraphql;
    const variables = {
      id,
      modifiable,
      priority,
    };

    const res: { data: { update_Event_by_pk: EventType } } = await got
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
      res?.data?.update_Event_by_pk,
      ' res inside updateEventWithIdModifiable'
    );

    return res?.data?.update_Event_by_pk;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const untrainEventWithPriorityAndModifiable = async (
  id: string,
  modifiable: boolean,
  priority: number
) => {
  try {
    const operationName = 'UntrainEventWithPriorityAndModifiable';
    const query = untrainEventWithPriorityAndModifiable;
    const variables = {
      id,
      modifiable,
      priority,
    };

    const res: { data: { update_Event_by_pk: EventType } } = await got
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
      res?.data?.update_Event_by_pk,
      ' res inside updateEventWithIdModifiable'
    );

    return res?.data?.update_Event_by_pk;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const updateEventWithPriorityAndModifiable = async (
  id: string,
  modifiable: boolean,
  priority: number
) => {
  try {
    const operationName = 'UpdateEventWithPriorityAndModifiable';
    const query = updateEventWithPriorityAndModifiable;
    const variables = {
      id,
      modifiable,
      priority,
    };

    const res: { data: { update_Event_by_pk: EventType } } = await got
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
      res?.data?.update_Event_by_pk,
      ' res inside updateEventWithIdModifiable'
    );

    return res?.data?.update_Event_by_pk;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const trainEventWithIdModifiable = async (
  id: string,
  modifiable: boolean
) => {
  try {
    const operationName = 'TrainEventModifiable';
    const query = trainEventModifiable;
    const variables = {
      id,
      modifiable,
    };

    const res: { data: { update_Event_by_pk: EventType } } = await got
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
      res?.data?.update_Event_by_pk,
      ' res inside updateEventWithIdModifiable'
    );

    return res?.data?.update_Event_by_pk;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const untrainEventWithIdModifiable = async (
  id: string,
  modifiable: boolean
) => {
  try {
    const operationName = 'UntrainEventModifiable';
    const query = untrainEventModifiable;
    const variables = {
      id,
      modifiable,
    };

    const res: { data: { update_Event_by_pk: EventType } } = await got
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
      res?.data?.update_Event_by_pk,
      ' res inside updateEventWithIdModifiable'
    );

    return res?.data?.update_Event_by_pk;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const updateEventWithIdModifiable = async (
  id: string,
  modifiable: boolean
) => {
  try {
    const operationName = 'UpdateEventModifiable';
    const query = updateEventModifiable;
    const variables = {
      id,
      modifiable,
    };

    const res: { data: { update_Event_by_pk: EventType } } = await got
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
      res?.data?.update_Event_by_pk,
      ' res inside updateEventWithIdModifiable'
    );

    return res?.data?.update_Event_by_pk;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const deletePreferredTimeRangesByIds = async (ids: string[]) => {
  try {
    const operationName = 'DeletePreferredTimeRangesWithIds';
    const query = deletePreferredTimeRangesWithIds;
    const variables = {
      ids,
    };

    const res: {
      data: {
        PreferredTimeRange: {
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
      res?.data?.PreferredTimeRange?.affected_rows,
      ' res inside deletePreferredTimeRangesByIds'
    );

    return res?.data?.PreferredTimeRange?.returning;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const listPreferredTimeRangesGivenEventId = async (eventId: string) => {
  try {
    const operationName = 'ListPreferredTimeRangesGivenEventId';
    const query = listPreferredTimeRangesByEventId;
    const variables = {
      eventId,
    };

    const res: { data: { PreferredTimeRange: PreferredTimeRangeType[] } } =
      await got
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

    console.log(res, ' res inside listPreferredTimeRangesByUserId');
    if (res?.data?.PreferredTimeRange?.length > 0) {
      return res?.data?.PreferredTimeRange;
    }

    return null;
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const finalStepRCE = async (
  body: ResolveConflictingEventsType,
  startDate: string,
  endDate: string,
  response: any
) => {
  try {
    const searchVector = await convertEventTitleToOpenAIVector(body?.title);

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

    if (!id) {
      response.query = 'event_not_found';
      return response;
    }

    const newPreferredTimeRanges: PreferredTimeRangeType[] = [];

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

          newPreferredTimeRanges.push(newPreferredTimeRange);
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

        newPreferredTimeRanges.push(newPreferredTimeRange);
      }
    }

    const oldPreferredTimeRanges =
      await listPreferredTimeRangesGivenEventId(id);

    if (oldPreferredTimeRanges?.length > 0) {
      await deletePreferredTimeRangesByIds(
        oldPreferredTimeRanges?.map((p) => p?.id)
      );
    }

    newPreferredTimeRanges?.forEach((pt) => ({ ...pt, eventId: id }));

    if (newPreferredTimeRanges?.length > 0) {
      await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
    } else {
      console.log(
        'something went wrong with no new preferred time ranges generated'
      );
    }

    if (body?.priority > 1) {
      await trainEventWithPriorityAndModifiable(id, true, body?.priority);
    } else {
      await trainEventWithIdModifiable(id, true);
    }

    await putDataInTrainEventIndexInOpenSearch(id, searchVector, body?.userId);

    response.query = 'completed';

    response.data =
      'successfully added time preferences and priorities to resolve future conflicting events';

    return response;
  } catch (e) {
    console.log(e, ' unable to final step RCE');
  }
};

export const processRCEPending = async (
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

    const body: ResolveConflictingEventsType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      priority: jsonBody?.params?.priority || 1,
      method: dateJSONBody?.method as any,
      timePreferences: dateJSONBody?.timePreferences,
    };

    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'resolveConflictingEvents',
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

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepRCE(body, startDate, endDate, response);

    return response2;
  } catch (e) {
    console.log(e, ' unable to process resolve conflicting events');
  }
};

export const processRCEMissingFieldsReturned = async (
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

    const day =
      dateJSONBody?.day || messageHistoryObject?.prevDateJsonBody?.day;
    const isoWeekday =
      dateJSONBody?.isoWeekday ||
      messageHistoryObject?.prevDateJsonBody?.isoWeekday;
    const hour =
      dateJSONBody?.hour || messageHistoryObject?.prevDateJsonBody?.hour;
    const minute =
      dateJSONBody?.minute || messageHistoryObject?.prevDateJsonBody?.minute;
    const startTime =
      dateJSONBody?.startTime ||
      messageHistoryObject?.prevDateJsonBody?.startTime;

    const newBody: ResolveConflictingEventsType = {
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
      priority:
        jsonBody?.params?.priority ||
        messageHistoryObject?.prevJsonBody?.params?.priority ||
        1,
      method: dateJSONBody?.method as any,
      timePreferences: dateJSONBody?.timePreferences,
    };

    const prevBody: ResolveConflictingEventsType = {
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

    if (!prevBody?.priority) {
      prevBody.priority = newBody?.priority;
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

    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'resolveConflictingEvents',
    };

    if (!prevStartDate && !day && !isoWeekday) {
      response.query = 'missing_fields';
      missingFields.dateTime.required.push(
        requiredFields.dateTime.required?.[0]
      );
      response.data = missingFields;
      response.prevData = prevBody;
      response.prevDataExtra = {
        searchBoundary: {
          startDate: prevStartDate,
          endDate: prevEndDate,
        },
      };
    }

    if (!prevStartDate && hour === null && minute === null && !startTime) {
      response.query = 'missing_fields';
      missingFields.dateTime.required.push(
        requiredFields.dateTime.required?.[1]
      );
      response.data = missingFields;
      response.prevData = prevBody;
      response.prevDataExtra = {
        searchBoundary: {
          startDate: prevStartDate,
          endDate: prevEndDate,
        },
      };
    }

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

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepRCE(
      prevBody,
      prevStartDate,
      prevEndDate,
      response
    );

    return response2;
  } catch (e) {
    console.log(e, ' unable to process rce fields returned');
  }
};

export const RCEControlCenter = async (
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

    let RCERes: ResponseActionType = {
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
        RCERes = await processRCEPending(
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

        RCERes = await processRCEMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (RCERes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          RCERes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (RCERes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          RCERes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = RCERes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = RCERes?.prevData;
      messageHistoryObject.prevDataExtra = RCERes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = RCERes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = RCERes?.prevJsonBody;
    } else if (RCERes?.query === 'event_not_found') {
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
      ' unable to resolve conflicting events control center pending'
    );
  }
};
