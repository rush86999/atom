import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType, {
  MutatedCalendarExtractedJSONAttendeeType,
} from '@chat/_libs/types/UserInputToJSONType';
import {
  MeetingUrlQueryParamsType,
  ReceiverTimezoneFormDataResponseType,
  SendMeetingInviteType,
} from './types';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import requiredFields from './requiredFields';
import {
  callOpenAI,
  extrapolateEndDateFromJSONData,
  extrapolateStartDateFromJSONData,
  generateAssistantMessageToRequestUserForMissingFields,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
  getCalendarIntegrationByName,
  getContactByNameWithUserId,
  getGlobalCalendar,
  getUserGivenId,
  listUserContactInfosGivenUserId,
} from '@chat/_libs/api-helper';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import {
  atomicCalendarSubdomainUrl,
  defaultOpenAIAPIKey,
  googleCalendarName,
  openAIChatGPT35LongModel,
  openAIChatGPT35Model,
} from '@chat/_libs/constants';
import {
  DayAvailabilityType,
  SummarizeDayAvailabilityType,
} from './availabilityTypes';

import {
  meetingRequestSubjectPrompt,
  meetingRequestWithAvailabilityPrompt,
} from './prompts';
import OpenAI from 'openai';
import qs from 'qs';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import { ChatMeetingPreferencesType } from '@chat/_libs/types/ChatMeetingPreferencesType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import { generateAvailabilityForUser } from '@chat/_libs/skills/askCalendar/askAvailability/api-helper';
import {
  summarizeAvailabilityPrompt,
  summarizeAvailabilityExampleInput,
  summarizeAvailabilityExampleOutput,
  summarizeAvailabilityResponsesPrompt,
  summarizeAvailabilityResponsesPromptExampleInput,
  summarizeAvailabilityResponsesPromptExampleOutput,
} from '@chat/_libs/skills/askCalendar/askAvailability/prompts';
import _ from 'lodash';
import {
  process_day_availibility,
  process_summarize_availability,
} from '@/gpt-meeting/_libs/api-helper';
import { sendEmail } from '@/_utils/email/email';
import { ENV } from '@/_utils/env';

export const day_availability_summary = async (
  dayAvailabilityObject: DayAvailabilityType
) => {
  try {
    const response = await process_day_availibility(dayAvailabilityObject);
    return response;
  } catch (e) {
    console.log(e, ' unable to get day availability summary');
  }
};

export const summarize_availability = async (
  summarizeAvailabilityObject: SummarizeDayAvailabilityType
) => {
  try {
    const response = await process_summarize_availability(
      summarizeAvailabilityObject
    );

    console.log(response, ' response');
    return response;
  } catch (e) {
    console.log(e, ' error in summarize_availability');
  }
};

export const sendMeetingRequestTemplate = async (
  name: string,
  email: string,
  body: string,
  subject: string
) => {
  try {
    const template = 'meeting-request-template';

    await sendEmail({
      template,
      locals: {
        name,
        body,
        displayName: name,
        email,
        locale: ENV.AUTH_LOCALE_DEFAULT,
        serverUrl: ENV.FUNCTION_SERVER_URL,
        clientUrl: ENV.APP_CLIENT_URL,
      },
      message: {
        to: email,
        headers: {
          'x-email-template': {
            prepared: true,
            value: template,
          },
        },
      },
    });
  } catch (e) {
    console.log(e, ' unable to send meeting request');
  }
};

export const finalStepSendMeetingInvite = async (
  body: SendMeetingInviteType,
  primaryHostAttendeeInfo: MutatedCalendarExtractedJSONAttendeeType,
  defaultMeetingPreferences: ChatMeetingPreferencesType,
  currentTime: string,
  response: any
) => {
  try {
    const primaryCalendar = await getGlobalCalendar(body?.userId);

    if (!primaryCalendar?.id) {
      throw new Error('no primary calendar found inside createAgenda');
    }

    const calIntegration = await getCalendarIntegrationByName(
      body?.userId,
      googleCalendarName
    );

    if (!calIntegration?.clientType) {
      throw new Error(
        'no client type inside calendar integration inside create agenda'
      );
    }

    const openai = new OpenAI({
      apiKey: defaultOpenAIAPIKey,
    });

    const availableSlots = await generateAvailabilityForUser(
      body?.userId,
      body?.windowStartDate,
      body?.windowEndDate,
      body?.receiverTimezone,
      body?.duration || 30
    );

    const uniqDates = _.uniqBy(availableSlots, (curr) =>
      dayjs(curr?.startDate?.slice(0, 19))
        .tz(body?.receiverTimezone)
        .format('YYYY-MM-DD')
    );

    const prompt = summarizeAvailabilityPrompt;

    const exampleInput = summarizeAvailabilityExampleInput;

    const exampleOutput = summarizeAvailabilityExampleOutput;

    let openAIAvailabilityRes = '';

    for (const uniqDate of uniqDates) {
      const filteredAvailability = availableSlots?.filter(
        (a) =>
          dayjs(a?.startDate)
            .tz(body?.receiverTimezone)
            .format('YYYY-MM-DD') ===
          dayjs(uniqDate?.startDate)
            .tz(body?.receiverTimezone)
            .format('YYYY-MM-DD')
      );

      if (filteredAvailability?.length > 0) {
        const miniAvailabilityText =
          `${dayjs(uniqDate?.startDate).tz(body?.receiverTimezone).format('L')} - ${filteredAvailability?.map((curr) => `${dayjs(curr?.startDate).tz(body?.receiverTimezone).format('LT')} - ${dayjs(curr?.endDate).tz(body?.receiverTimezone).format('LT')},`)?.reduce((prev, curr) => `${prev} ${curr}`, '')}` +
          '\n\n';

        const miniUserData = `My availability: ` + miniAvailabilityText;

        console.log(miniUserData, ' newAvailabilityPrompt');

        const miniOpenAIAvailabilityRes = await callOpenAI(
          openai,
          prompt,
          openAIChatGPT35LongModel,
          miniUserData,
          exampleInput,
          exampleOutput
        );

        if (!miniOpenAIAvailabilityRes) {
          throw new Error(
            'no openAIAvailabilityRes present inside appointmentRequest'
          );
        }

        openAIAvailabilityRes += '\n' + miniOpenAIAvailabilityRes;
      }
    }

    const availabilityFinalSummaryUserData = openAIAvailabilityRes;

    let finalOpenAIAvailabilitySummaryResponse = '';

    if (availabilityFinalSummaryUserData) {
      finalOpenAIAvailabilitySummaryResponse = await callOpenAI(
        openai,
        summarizeAvailabilityResponsesPrompt,
        openAIChatGPT35LongModel,
        availabilityFinalSummaryUserData,
        summarizeAvailabilityResponsesPromptExampleInput,
        summarizeAvailabilityResponsesPromptExampleOutput
      );
    }

    const meetingInvitePrompt = meetingRequestWithAvailabilityPrompt;

    const meetingInviteUserData = `${body?.title} \n ${body?.description}`;

    let meetingInviteOpenAIRes = await callOpenAI(
      openai,
      meetingInvitePrompt,
      openAIChatGPT35Model,
      meetingInviteUserData
    );

    if (!meetingInviteOpenAIRes) {
      throw new Error('no openAIRes present inside appointmentRequest');
    }

    meetingInviteOpenAIRes += '\n' + finalOpenAIAvailabilitySummaryResponse;

    const meetingQueryParams: MeetingUrlQueryParamsType = {
      userId: body?.userId,
      timezone: body?.timezone,
      enableConference: !!body?.conferenceApp ? 'true' : 'false',
      conferenceApp: body?.conferenceApp,
      useDefaultAlarms: body?.reminders?.length > 0 ? 'false' : 'true',
      reminders: body?.reminders?.map((n) => `${n}`),
      attendeeEmails: body?.attendees?.map((a) => a?.email),
      duration: `${body?.duration}`,
      calendarId: primaryCalendar?.id,
      startTime: currentTime,
      name: primaryHostAttendeeInfo?.name,
      primaryEmail: primaryHostAttendeeInfo?.email,
      sendUpdates: defaultMeetingPreferences?.sendUpdates,
      anyoneCanAddSelf: defaultMeetingPreferences?.anyoneCanAddSelf
        ? 'true'
        : 'false',
      guestsCanInviteOthers: defaultMeetingPreferences?.guestsCanInviteOthers
        ? 'true'
        : 'false',
      guestsCanSeeOtherGuests:
        defaultMeetingPreferences?.guestsCanSeeOtherGuests ? 'true' : 'false',
      transparency: body?.transparency,
      visibility: body?.visibility,
    };

    const calendarLink =
      atomicCalendarSubdomainUrl + '?' + qs.stringify(meetingQueryParams);
    const calendarLinkMessage = `You can quickly schedule a meeting by clicking \"Reply All\" with your time to send me a copy and let me take care of the heavy work. Atom, an AI assistant from <a href=\"${calendarLink}\">Atomic</a> :)`;

    meetingInviteOpenAIRes += '\n' + calendarLinkMessage;

    const emailSubjectPrompt = meetingRequestSubjectPrompt;

    const emailSubjectUserData = meetingInviteOpenAIRes;

    const emailSubjectInviteOpenAIRes = await callOpenAI(
      openai,
      emailSubjectPrompt,
      openAIChatGPT35Model,
      emailSubjectUserData
    );

    await sendMeetingRequestTemplate(
      primaryHostAttendeeInfo?.name,
      body?.attendees?.filter((a) => !!a?.isHost)?.[0]?.email,
      meetingInviteOpenAIRes,
      emailSubjectInviteOpenAIRes
    );

    response.query = 'completed';

    response.data = `Your meeting invite message is ready and sent to your email! :) \n`;

    return response;
  } catch (e) {
    console.log(e, ' unable to final step send meeting invite');
  }
};

export const processSendMeetingInvitePending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string,
  formData: ReceiverTimezoneFormDataResponseType
) => {
  try {
    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'sendMeetingInvite',
    };

    let duration = 0;

    const yearStart = dateJSONBody?.findTimeWindowStart?.year;
    const monthStart = dateJSONBody?.findTimeWindowStart?.month;
    const dayStart = dateJSONBody?.findTimeWindowStart?.day;
    const isoWeekdayStart = dateJSONBody?.findTimeWindowStart?.isoWeekday;
    const hourStart = dateJSONBody?.findTimeWindowStart?.hour;
    const minuteStart = dateJSONBody?.findTimeWindowStart?.minute;
    const startTimeStart = dateJSONBody?.findTimeWindowStart?.startTime;

    const yearEnd = dateJSONBody?.findTimeWindowEnd?.year;
    const monthEnd = dateJSONBody?.findTimeWindowEnd?.month;
    const dayEnd = dateJSONBody?.findTimeWindowEnd?.day;
    const isoWeekdayEnd = dateJSONBody?.findTimeWindowEnd?.isoWeekday;
    const hourEnd = dateJSONBody?.findTimeWindowEnd?.hour;
    const minuteEnd = dateJSONBody?.findTimeWindowEnd?.minute;
    const endTimeEnd = dateJSONBody?.findTimeWindowEnd?.startTime;

    const windowBranchStartDate = extrapolateStartDateFromJSONData(
      currentTime,
      timezone,
      yearStart,
      monthStart,
      dayStart,
      isoWeekdayStart,
      hourStart,
      minuteStart,
      startTimeStart,
      dateJSONBody?.findTimeWindowStart?.relativeTimeChangeFromNow,
      dateJSONBody?.findTimeWindowStart?.relativeTimeFromNow
    );

    let windowStartDate = windowBranchStartDate;

    if (!windowStartDate) {
      windowStartDate = dayjs().format();
    }

    let windowEndDate = extrapolateEndDateFromJSONData(
      currentTime,
      timezone,
      yearEnd,
      monthEnd,
      dayEnd,
      isoWeekdayEnd,
      hourEnd,
      minuteEnd,
      endTimeEnd,
      dateJSONBody?.findTimeWindowEnd?.relativeTimeChangeFromNow,
      dateJSONBody?.findTimeWindowEnd?.relativeTimeFromNow
    );

    if (!windowEndDate) {
      windowEndDate = dayjs(windowStartDate).add(1, 'w').format();
    }

    const defaultMeetingPreferences =
      await getChatMeetingPreferenceGivenUserId(userId);

    if (dateJSONBody?.duration) {
      duration = dateJSONBody?.duration;
    } else if (defaultMeetingPreferences?.duration) {
      duration = defaultMeetingPreferences?.duration;
    } else {
      duration = 30;
    }

    const body: SendMeetingInviteType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      attendees: jsonBody?.params?.attendees,
      method: dateJSONBody?.method as any,
      duration,
      description: jsonBody?.params?.description || jsonBody?.params?.notes,
      conferenceApp:
        jsonBody?.params?.conference?.app ||
        defaultMeetingPreferences?.conferenceApp,
      windowStartDate:
        jsonBody?.params?.startTime || windowStartDate || currentTime,
      windowEndDate:
        jsonBody?.params?.endTime ||
        windowEndDate ||
        dayjs(currentTime).add(7, 'd').format(),
      reminders:
        jsonBody?.params?.alarms || defaultMeetingPreferences?.reminders || [],
      transparency: jsonBody?.params?.transparency,
      visibility: jsonBody?.params.visibility,
      receiverTimezone: formData?.value,
    };

    if (!formData?.value) {
      response.query = 'missing_fields';
      missingFields.dateTime.required.push(requiredFields.required?.[2]);
      response.data = missingFields;
      response.prevData = body;
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    if (!body?.title) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[0]);
      response.data = missingFields;
      response.prevData = body;
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    if (!(body?.attendees?.length > 0)) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[1]);
      response.data = missingFields;
      response.prevData = body;
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    const newAttendees: MutatedCalendarExtractedJSONAttendeeType[] = [];

    for (const a of body?.attendees) {
      if (!a?.email) {
        const contact = await getContactByNameWithUserId(
          userId,
          `%${a?.name}%`
        );
        if (contact?.emails?.[0]?.value) {
          const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
          const anyEmail = contact?.emails?.[0]?.value;
          newAttendees.push({ ...a, email: primaryEmail || anyEmail });
        } else {
          response.query = 'missing_fields';
          missingFields.required.push(
            requiredFields.required?.[1]?.['and']?.[2]
          );
          response.data = missingFields;
          response.prevJsonBody = jsonBody;
          response.prevDateJsonBody = dateJSONBody;
        }
      } else {
        newAttendees.push(a);
      }
    }

    body.attendees = newAttendees;

    const userContactInfos = await listUserContactInfosGivenUserId(userId);

    const providedHostInfo = body?.attendees?.find((a) => a?.isHost === true);

    const primaryInfoItem = userContactInfos?.find(
      (u) => u.primary && u.type === 'email'
    );

    const user = await getUserGivenId(userId);

    const primaryHostAttendeeInfo: MutatedCalendarExtractedJSONAttendeeType = {
      name: primaryInfoItem?.name || user?.name,
      email: primaryInfoItem?.id || user?.email,
      isHost: true,
    };

    if (!providedHostInfo && primaryHostAttendeeInfo?.email) {
      body?.attendees.push(primaryHostAttendeeInfo);
    }

    const hostInfo = providedHostInfo || primaryHostAttendeeInfo;

    if (!hostInfo?.email) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[1]['and'][1]);
      response.data = missingFields;
      response.prevData = body;
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepSendMeetingInvite(
      body,
      primaryHostAttendeeInfo,
      defaultMeetingPreferences,
      currentTime,
      response
    );

    return response2;
  } catch (e) {
    console.log(e, ' unable to process send meeting invite');
  }
};

export const processSendMeetingInviteMissingFieldsReturned = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string,
  formData: ReceiverTimezoneFormDataResponseType,
  messageHistoryObject: SkillMessageHistoryType
) => {
  try {
    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'sendMeetingInvite',
    };

    let duration = 0;

    const yearStart =
      dateJSONBody?.findTimeWindowStart?.year ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.year;
    const monthStart =
      dateJSONBody?.findTimeWindowStart?.month ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.month;
    const dayStart =
      dateJSONBody?.findTimeWindowStart?.day ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.day;
    const isoWeekdayStart =
      dateJSONBody?.findTimeWindowStart?.isoWeekday ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.isoWeekday;
    const hourStart =
      dateJSONBody?.findTimeWindowStart?.hour ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.hour;
    const minuteStart =
      dateJSONBody?.findTimeWindowStart?.minute ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.minute;
    const startTimeStart =
      dateJSONBody?.findTimeWindowStart?.startTime ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart?.startTime;

    const yearEnd =
      dateJSONBody?.findTimeWindowEnd?.year ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.year;
    const monthEnd =
      dateJSONBody?.findTimeWindowEnd?.month ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.month;
    const dayEnd =
      dateJSONBody?.findTimeWindowEnd?.day ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.day;
    const isoWeekdayEnd =
      dateJSONBody?.findTimeWindowEnd?.isoWeekday ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.isoWeekday;
    const hourEnd =
      dateJSONBody?.findTimeWindowEnd?.hour ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.hour;
    const minuteEnd =
      dateJSONBody?.findTimeWindowEnd?.minute ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.minute;
    const endTimeEnd =
      dateJSONBody?.findTimeWindowEnd?.startTime ||
      messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd?.startTime;

    const windowBranchStartDate = extrapolateStartDateFromJSONData(
      currentTime,
      timezone,
      yearStart,
      monthStart,
      dayStart,
      isoWeekdayStart,
      hourStart,
      minuteStart,
      startTimeStart,
      dateJSONBody?.findTimeWindowStart?.relativeTimeChangeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
          ?.relativeTimeChangeFromNow,
      dateJSONBody?.findTimeWindowStart?.relativeTimeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.findTimeWindowStart
          ?.relativeTimeFromNow
    );

    let windowStartDate = windowBranchStartDate;

    if (!windowStartDate) {
      windowStartDate = dayjs().format();
    }

    let windowEndDate = extrapolateEndDateFromJSONData(
      currentTime,
      timezone,
      yearEnd,
      monthEnd,
      dayEnd,
      isoWeekdayEnd,
      hourEnd,
      minuteEnd,
      endTimeEnd,
      dateJSONBody?.findTimeWindowEnd?.relativeTimeChangeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd
          ?.relativeTimeChangeFromNow,
      dateJSONBody?.findTimeWindowEnd?.relativeTimeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.findTimeWindowEnd
          ?.relativeTimeFromNow
    );

    if (!windowEndDate) {
      windowEndDate = dayjs(windowStartDate).add(1, 'w').format();
    }

    const defaultMeetingPreferences =
      await getChatMeetingPreferenceGivenUserId(userId);

    if (dateJSONBody?.duration) {
      duration = dateJSONBody?.duration;
    } else if (defaultMeetingPreferences?.duration) {
      duration = defaultMeetingPreferences?.duration;
    } else {
      duration = 30;
    }

    const newBody: SendMeetingInviteType = {
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
      attendees:
        jsonBody?.params?.attendees ||
        messageHistoryObject?.prevJsonBody?.params?.attendees,
      method: dateJSONBody?.method as any,
      duration,
      description:
        jsonBody?.params?.description ||
        jsonBody?.params?.notes ||
        messageHistoryObject?.prevJsonBody?.params?.description ||
        messageHistoryObject?.prevJsonBody?.params?.notes,
      conferenceApp:
        jsonBody?.params?.conference?.app ||
        messageHistoryObject?.prevJsonBody?.params?.conference?.app ||
        defaultMeetingPreferences?.conferenceApp,
      windowStartDate:
        jsonBody?.params?.startTime ||
        messageHistoryObject?.prevJsonBody?.params?.startTime ||
        windowStartDate ||
        currentTime,
      windowEndDate:
        jsonBody?.params?.endTime ||
        messageHistoryObject?.prevJsonBody?.params?.endTime ||
        windowEndDate ||
        dayjs(currentTime).add(7, 'd').format(),
      reminders:
        jsonBody?.params?.alarms ||
        messageHistoryObject?.prevJsonBody?.params?.alarms ||
        defaultMeetingPreferences?.reminders ||
        [],
      transparency:
        jsonBody?.params?.transparency ||
        messageHistoryObject?.prevJsonBody?.params?.transparency,
      visibility:
        jsonBody?.params.visibility ||
        messageHistoryObject?.prevJsonBody?.params?.visibility,
      receiverTimezone: formData?.value,
    };

    const prevBody: SendMeetingInviteType = {
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

    if (!prevBody?.duration) {
      prevBody.duration = newBody?.duration;
    }

    if (!prevBody?.description) {
      prevBody.description = newBody?.description;
    }

    if (!prevBody?.conferenceApp) {
      prevBody.conferenceApp = newBody?.conferenceApp;
    }

    if (!prevBody?.windowStartDate) {
      prevBody.windowStartDate = newBody?.windowStartDate;
    }

    if (!prevBody?.windowEndDate) {
      prevBody.windowEndDate = newBody?.windowEndDate;
    }

    if (!(prevBody?.reminders?.length > 0)) {
      prevBody.reminders = newBody?.reminders || [];
    }

    if (!prevBody?.transparency) {
      prevBody.transparency = newBody?.transparency;
    }

    if (!prevBody?.visibility) {
      prevBody.visibility = newBody?.visibility;
    }

    if (!prevBody?.receiverTimezone) {
      prevBody.receiverTimezone = newBody?.receiverTimezone;
    }

    if (!prevBody?.title) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[0]);
      response.data = missingFields;
      response.prevData = prevBody;
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    if (!(prevBody?.attendees?.length > 0)) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[1]);
      response.data = missingFields;
      response.prevData = prevBody;
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    const newAttendees: MutatedCalendarExtractedJSONAttendeeType[] = [];

    for (const a of newBody?.attendees) {
      if (!a?.email) {
        const contact = await getContactByNameWithUserId(
          userId,
          `%${a?.name}%`
        );
        if (contact?.emails?.[0]?.value) {
          const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
          const anyEmail = contact?.emails?.[0]?.value;
          newAttendees.push({ ...a, email: primaryEmail || anyEmail });
        } else {
          response.query = 'missing_fields';
          missingFields.required.push(
            requiredFields.required?.[1]?.['and']?.[2]
          );
          response.data = missingFields;
          response.prevData = prevBody;
          response.prevJsonBody = jsonBody;
          response.prevDateJsonBody = dateJSONBody;
        }
      } else {
        newAttendees.push(a);
      }
    }

    newBody.attendees = newAttendees;

    if (!(prevBody?.attendees?.length > 0)) {
      prevBody.attendees = newBody?.attendees;
    }

    const userContactInfos = await listUserContactInfosGivenUserId(userId);

    const newProvidedHostInfo = newBody?.attendees?.find(
      (a) => a?.isHost === true
    );

    const prevProvidedHostInfo = prevBody?.attendees?.find(
      (a) => a?.isHost === true
    );

    const primaryInfoItem = userContactInfos?.find(
      (u) => u.primary && u.type === 'email'
    );

    const user = await getUserGivenId(userId);

    const primaryHostAttendeeInfo: MutatedCalendarExtractedJSONAttendeeType = {
      name: primaryInfoItem?.name || user?.name,
      email: primaryInfoItem?.id || user?.email,
      isHost: true,
    };

    if (!newProvidedHostInfo && primaryHostAttendeeInfo?.email) {
      newBody?.attendees.push(primaryHostAttendeeInfo);
    }

    if (!prevProvidedHostInfo && primaryHostAttendeeInfo?.email) {
      prevBody?.attendees.push(primaryHostAttendeeInfo);
    }

    const prevHostInfo =
      prevProvidedHostInfo || newProvidedHostInfo || primaryHostAttendeeInfo;

    if (!prevHostInfo?.email) {
      response.query = 'missing_fields';
      missingFields.required.push(requiredFields.required?.[1]['and'][1]);
      response.data = missingFields;
      response.prevData = prevBody;
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    if (!prevBody?.receiverTimezone) {
      response.query = 'missing_fields';
      missingFields.dateTime.required.push(requiredFields.required?.[2]);
      response.data = missingFields;
      response.prevData = prevBody;
    }

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepSendMeetingInvite(
      prevBody,
      prevHostInfo,
      defaultMeetingPreferences,
      currentTime,
      response
    );

    return response2;
  } catch (e) {
    console.log(
      e,
      ' unable to process send meeitng invite missing fields returned'
    );
  }
};

export const sendMeetingInviteControlCenter = async (
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

    let SMIRes: ResponseActionType = {
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
        SMIRes = await processSendMeetingInvitePending(
          userId,
          timezone,
          jsonBody,
          dateTime,
          userCurrentTime,
          messageHistoryObject?.formData
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

        SMIRes = await processSendMeetingInviteMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject?.formData,
          messageHistoryObject
        );
        break;
    }

    if (SMIRes?.query === 'completed') {
      const assistantMessage: AssistantMessageType = {
        role: 'assistant',
        content: SMIRes?.data as string,
      };
      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (SMIRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          SMIRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = SMIRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = SMIRes?.prevData;
      messageHistoryObject.prevDataExtra = SMIRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = SMIRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = SMIRes?.prevJsonBody;
    } else if (SMIRes?.query === 'event_not_found') {
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
    console.log(e, ' unable to send meeting invite control center pending');
  }
};
