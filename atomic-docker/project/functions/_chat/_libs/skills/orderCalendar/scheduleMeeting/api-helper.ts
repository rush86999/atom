import {
  createGoogleEvent,
  createPreAndPostEventsFromEvent,
  createZoomMeeting,
  extrapolateStartDateFromJSONData,
  findContactByEmailGivenUserId,
  getGlobalCalendar,
  getZoomAPIToken,
  upsertAttendeesforEvent,
  upsertConference,
  insertReminders,
  upsertEvents,
  getCalendarIntegrationByName,
  createRRuleString,
  convertEventTitleToOpenAIVector,
  putDataInTrainEventIndexInOpenSearch,
  listUserContactInfosGivenUserId,
  getUserContactInfosGivenIds,
  getContactByNameWithUserId,
  getUserGivenId,
  putDataInAllEventIndexInOpenSearch,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  extrapolateDateFromJSONData,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
} from '@chat/_libs/api-helper';
import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType, {
  MutatedCalendarExtractedJSONAttendeeType,
} from '@chat/_libs/types/UserInputToJSONType';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import requiredFields from './requiredFields';
import { dayjs } from '@chat/_libs/datetime/date-utils';

import {
  EventType,
  RecurrenceFrequencyType,
  RecurrenceRuleType,
  VisibilityType,
} from '@chat/_libs/types/EventType';
import getChatMeetingPreferenceByUserId from '@chat/_libs/gql/getChatMeetingPreferenceByUserId';
import { ChatMeetingPreferencesType } from '@chat/_libs/types/ChatMeetingPreferencesType';
import {
  googleCalendarName,
  hasuraAdminSecret,
  hasuraGraphUrl,
} from '@chat/_libs/constants';
import got from 'got';
import { ScheduleMeetingType } from './types';
import { v4 as uuid } from 'uuid';
import { ReminderType } from '@chat/_libs/types/ReminderType';
import { GoogleReminderType } from '@chat/_libs/types/GoogleReminderType';
import { ConferenceType } from '@chat/_libs/types/ConferenceType';
import { GoogleResType } from '@chat/_libs/types/GoogleResType';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import PreferredTimeRangeType from '@chat/_libs/types/PreferredTimeRangeType';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
import { AttendeeType } from '@chat/_libs/types/AttendeeType';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import relativeTime from 'dayjs/plugin/relativeTime';

export const getChatMeetingPreferenceGivenUserId = async (userId: string) => {
  try {
    const operationName = 'GetChatMeetingPreferenceByUserId';
    const query = getChatMeetingPreferenceByUserId;
    const variables = {
      userId,
    };

    const res: {
      data: { Chat_Meeting_Preference: ChatMeetingPreferencesType[] };
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
      res?.data?.Chat_Meeting_Preference,
      ' res inside getChatMeetingPreferenceGivenUserId'
    );

    return res?.data?.Chat_Meeting_Preference?.[0];
  } catch (e) {
    console.log(e, ' unable to get Email_Knowledgebase');
  }
};

export const finalStepScheduleMeeting = async (
  body: ScheduleMeetingType,
  defaultMeetingPreferences: ChatMeetingPreferencesType,
  response: any
) => {
  try {
    const aWithEmails = body?.attendees?.filter((a) => !!a?.email);

    const aWithContactInfos = await getUserContactInfosGivenIds(
      aWithEmails?.map((a) => a?.email)
    );

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

    const eventId = uuid();

    const attendeesFromExtractedJSON = body?.attendees;
    const attendees: AttendeeType[] = [];

    for (const a of attendeesFromExtractedJSON) {
      const contact = await findContactByEmailGivenUserId(
        body?.userId,
        a.email
      );
      const userIdFound = aWithContactInfos?.find((b) => b?.id === a?.email);

      const attendee: AttendeeType = {
        id: userIdFound?.userId || uuid(),
        userId: body?.userId,
        name:
          a?.name ||
          contact?.name ||
          `${contact?.firstName} ${contact?.lastName}`,
        contactId: contact?.id,
        emails: [{ primary: true, value: a?.email }],
        updatedAt: dayjs().format(),
        createdDate: dayjs().format(),
        deleted: false,
        eventId,
      };

      attendees.push(attendee);
    }

    const remindersToUpdateEventId: ReminderType[] = [];

    if (body?.reminders?.length > 0) {
      const newReminders: ReminderType[] = body?.reminders.map((r) => ({
        id: uuid(),
        userId: body?.userId,
        eventId,
        timezone: body?.timezone,
        minutes: r,
        useDefault: false,
        updatedAt: dayjs().format(),
        createdDate: dayjs().format(),
        deleted: false,
      }));

      remindersToUpdateEventId.push(...newReminders);
    }

    const googleReminder: GoogleReminderType = {
      overrides: remindersToUpdateEventId?.map((r) => ({
        method: 'email',
        minutes: r?.minutes,
      })),
      useDefault: false,
    };

    const newPreferredTimeRanges: PreferredTimeRangeType[] = [];

    for (const timepreference of body?.timePreferences) {
      if (timepreference.dayOfWeek?.length > 0) {
        for (const dayOfWeek of timepreference.dayOfWeek) {
          const newPreferredTimeRange: PreferredTimeRangeType = {
            id: uuid(),
            eventId,
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
          eventId,
          startTime: timepreference?.timeRange?.startTime,
          endTime: timepreference?.timeRange?.endTime,
          updatedAt: dayjs().format(),
          createdDate: dayjs().format(),
          userId: body?.userId,
        };

        newPreferredTimeRanges.push(newPreferredTimeRange);
      }
    }

    const recur = createRRuleString(
      body?.recur?.frequency,
      body?.recur?.interval,
      body?.recur?.byWeekDay,
      body?.recur?.occurrence,
      body?.recur?.endDate,
      body?.recur?.ByMonthDay
    );

    let conference: ConferenceType | {} = {};

    if (body?.conferenceApp) {
      const zoomToken = await getZoomAPIToken(body?.userId);
      conference =
        zoomToken && body?.conferenceApp === 'zoom'
          ? {}
          : {
              id: uuid(),
              userId: body?.userId,
              calendarId: primaryCalendar?.id,
              app: 'google',
              name: defaultMeetingPreferences?.name,
              notes: body?.description || body?.title,
              updatedAt: dayjs().format(),
              createdDate: dayjs().format(),
              deleted: false,
              isHost: true,
              requestId: uuid(),
            };

      if (zoomToken && body?.conferenceApp === 'zoom') {
        console.log(zoomToken, ' zoomToken inside if (zoomToken)');

        const zoomObject = await createZoomMeeting(
          zoomToken,
          body?.startDate,
          body?.timezone,
          body?.title,
          body?.duration,
          defaultMeetingPreferences?.name,
          defaultMeetingPreferences?.primaryEmail,
          body?.attendees?.map((a) => a?.email),
          body?.recur as any
        );

        console.log(zoomObject, ' zoomObject after createZoomMeeting');

        if (zoomObject) {
          conference = {
            id: `${zoomObject?.id}`,
            userId: body?.userId,
            calendarId: primaryCalendar?.id,
            app: 'zoom',
            name: zoomObject?.agenda,
            notes: zoomObject?.agenda,
            joinUrl: zoomObject?.join_url,
            startUrl: zoomObject?.start_url,
            isHost: true,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            deleted: false,
            entryPoints: [
              {
                entryPointType: 'video',
                label: zoomObject?.join_url,
                password: zoomObject?.password,
                uri: zoomObject?.join_url,
              },
            ],
          } as ConferenceType;
        }
      }

      const eventToUpsertLocal: EventType = {
        id: eventId,
        userId: body?.userId,
        title: body?.title,
        startDate: dayjs(body?.startDate).tz(body?.timezone).format(),
        endDate: dayjs(body?.startDate)
          .tz(body?.timezone)
          .add(body?.duration, 'm')
          .format(),
        allDay: false,
        notes: body?.description || body?.title,
        timezone: body?.timezone,
        createdDate: dayjs().format(),
        deleted: false,
        priority: body?.priority || 1,
        isFollowUp: false,
        isPreEvent: false,
        isPostEvent: false,
        modifiable: body?.priority > 1 || newPreferredTimeRanges?.length > 0,
        anyoneCanAddSelf: defaultMeetingPreferences?.anyoneCanAddSelf,
        guestsCanInviteOthers: defaultMeetingPreferences?.guestsCanInviteOthers,
        guestsCanSeeOtherGuests:
          defaultMeetingPreferences?.guestsCanSeeOtherGuests,
        transparency:
          body?.transparency || defaultMeetingPreferences?.transparency,
        visibility:
          (body?.visibility as VisibilityType) ||
          defaultMeetingPreferences?.visibility,
        originalStartDate: undefined,
        originalAllDay: false,
        summary: body?.title,
        updatedAt: dayjs().format(),
        calendarId: primaryCalendar?.id,
        eventId: undefined,
        conferenceId: (conference as ConferenceType)?.id,
        sendUpdates: defaultMeetingPreferences?.sendUpdates,
        duration: body?.duration,
        userModifiedAvailability: true,
        userModifiedTimeBlocking: body?.bufferTime ? true : false,
        userModifiedTimePreference:
          body?.timePreferences?.length > 0 ? true : false,
        userModifiedReminders: body?.reminders?.length > 0 ? true : false,
        userModifiedPriorityLevel:
          body?.timePreferences?.length > 0 ? true : false,
        userModifiedModifiable: true,
        userModifiedDuration: true,
        location: { title: body?.location },
        recurrence: recur,
        recurrenceRule: {
          frequency: body?.recur?.frequency,
          interval: body?.recur?.interval,
          byWeekDay: body?.recur?.byWeekDay,
          occurrence: body?.recur?.occurrence,
          endDate: body?.recur?.endDate,
          byMonthDay: body?.recur?.ByMonthDay,
        },
      };

      const googleResValue: GoogleResType = await createGoogleEvent(
        body?.userId,
        primaryCalendar?.id,
        calIntegration?.clientType,
        eventToUpsertLocal?.id,
        eventToUpsertLocal?.endDate,
        eventToUpsertLocal?.startDate,
        (conference as ConferenceType)?.id ? 1 : 0,
        undefined,
        eventToUpsertLocal?.sendUpdates,
        eventToUpsertLocal?.anyoneCanAddSelf,
        body?.attendees?.map((a) => ({ email: a?.email })),
        (conference as ConferenceType)?.id
          ? {
              type:
                (conference as ConferenceType)?.app === 'zoom'
                  ? 'addOn'
                  : 'hangoutsMeet',
              name: (conference as ConferenceType)?.name,
              conferenceId: (conference as ConferenceType)?.id,
              entryPoints: (conference as ConferenceType)?.entryPoints,
              createRequest:
                (conference as ConferenceType)?.app === 'google'
                  ? {
                      requestId: (conference as ConferenceType)?.requestId,
                      conferenceSolutionKey: {
                        type: 'hangoutsMeet',
                      },
                    }
                  : undefined,
            }
          : undefined,
        eventToUpsertLocal?.summary,
        eventToUpsertLocal?.notes,
        body?.timezone,
        undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.guestsCanInviteOthers,
        eventToUpsertLocal?.guestsCanModify,
        eventToUpsertLocal?.guestsCanSeeOtherGuests,
        eventToUpsertLocal?.originalStartDate,
        undefined,
        recur,
        remindersToUpdateEventId?.length > 0 ? googleReminder : undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.transparency,
        eventToUpsertLocal?.visibility,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.attachments,
        'default',
        body?.location,
        undefined
      );

      eventToUpsertLocal.id = googleResValue.id;
      eventToUpsertLocal.eventId = googleResValue.googleEventId;

      remindersToUpdateEventId?.forEach((r) => ({
        ...r,
        eventId: eventToUpsertLocal.id,
      }));

      newPreferredTimeRanges?.forEach((p) => ({
        ...p,
        eventId: eventToUpsertLocal.id,
      }));

      attendees?.forEach((a) => ({ ...a, eventId: eventToUpsertLocal?.id }));

      await upsertConference(conference as ConferenceType);

      if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
        const returnValues = createPreAndPostEventsFromEvent(
          eventToUpsertLocal,
          body?.bufferTime
        );

        if (returnValues?.afterEvent) {
          const googleResValue: GoogleResType = await createGoogleEvent(
            body?.userId,
            primaryCalendar?.id,
            calIntegration?.clientType,
            returnValues?.afterEvent?.id,
            returnValues?.afterEvent?.endDate,
            returnValues?.afterEvent?.startDate,
            0,
            undefined,
            returnValues?.afterEvent?.sendUpdates,
            returnValues?.afterEvent?.anyoneCanAddSelf,
            undefined,
            undefined,
            returnValues?.afterEvent?.title,
            returnValues?.afterEvent?.notes,
            body?.timezone,
            undefined,
            undefined,
            undefined,
            returnValues?.afterEvent?.guestsCanInviteOthers,
            returnValues?.afterEvent?.guestsCanModify,
            returnValues?.afterEvent?.guestsCanSeeOtherGuests,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            returnValues?.afterEvent?.transparency,
            returnValues?.afterEvent?.visibility,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            'default',
            undefined,
            undefined
          );

          returnValues.afterEvent.id = googleResValue.id;
          returnValues.afterEvent.eventId = googleResValue.googleEventId;
          returnValues.newEvent.postEventId = returnValues.afterEvent.id;
        }

        if (returnValues?.beforeEvent) {
          const googleResValue: GoogleResType = await createGoogleEvent(
            body?.userId,
            primaryCalendar?.id,
            calIntegration?.clientType,
            returnValues?.beforeEvent?.id,
            returnValues?.beforeEvent?.endDate,
            returnValues?.beforeEvent?.startDate,
            0,
            undefined,
            returnValues?.beforeEvent?.sendUpdates,
            returnValues?.beforeEvent?.anyoneCanAddSelf,
            undefined,
            undefined,
            returnValues?.beforeEvent?.title,
            returnValues?.beforeEvent?.notes,
            body?.timezone,
            undefined,
            undefined,
            undefined,
            returnValues?.beforeEvent?.guestsCanInviteOthers,
            returnValues?.beforeEvent?.guestsCanModify,
            returnValues?.beforeEvent?.guestsCanSeeOtherGuests,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            returnValues?.beforeEvent?.transparency,
            returnValues?.beforeEvent?.visibility,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            'default',
            undefined,
            undefined
          );

          returnValues.beforeEvent.id = googleResValue.id;
          returnValues.beforeEvent.eventId = googleResValue.googleEventId;
          returnValues.newEvent.preEventId = returnValues.afterEvent.id;
        }

        await upsertEvents(
          [
            returnValues.newEvent,
            returnValues?.afterEvent,
            returnValues?.beforeEvent,
          ]?.filter((e) => !!e)
        );
      } else {
        await upsertEvents([eventToUpsertLocal]);
      }

      if (remindersToUpdateEventId?.length > 0) {
        await insertReminders(remindersToUpdateEventId);
      }

      if (newPreferredTimeRanges?.length > 0) {
        await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
      }

      await upsertAttendeesforEvent(attendees);
    } else {
      const eventToUpsertLocal: EventType = {
        id: eventId,
        userId: body?.userId,
        title: body?.title,
        startDate: dayjs(body?.startDate).tz(body?.timezone).format(),
        endDate: dayjs(body?.startDate)
          .tz(body?.timezone)
          .add(body?.duration, 'm')
          .format(),
        allDay: false,
        notes: body?.description || body?.title,
        timezone: body?.timezone,
        createdDate: dayjs().format(),
        deleted: false,
        priority: body?.priority || 1,
        isFollowUp: false,
        isPreEvent: false,
        isPostEvent: false,
        modifiable: body?.priority > 1 || newPreferredTimeRanges?.length > 0,
        anyoneCanAddSelf: defaultMeetingPreferences?.anyoneCanAddSelf,
        guestsCanInviteOthers: defaultMeetingPreferences?.guestsCanInviteOthers,
        guestsCanSeeOtherGuests:
          defaultMeetingPreferences?.guestsCanSeeOtherGuests,
        transparency:
          body?.transparency || defaultMeetingPreferences?.transparency,
        visibility:
          (body?.visibility as VisibilityType) ||
          defaultMeetingPreferences?.visibility,
        originalStartDate: undefined,
        originalAllDay: false,
        summary: body?.title,
        updatedAt: dayjs().format(),
        calendarId: primaryCalendar?.id,
        eventId: undefined,
        sendUpdates: defaultMeetingPreferences?.sendUpdates,
        duration: body?.duration,
        timeBlocking: body?.bufferTime,
        userModifiedAvailability: true,
        userModifiedTimeBlocking: body?.bufferTime ? true : false,
        userModifiedTimePreference:
          body?.timePreferences?.length > 0 ? true : false,
        userModifiedReminders: body?.reminders?.length > 0 ? true : false,
        userModifiedPriorityLevel:
          body?.timePreferences?.length > 0 ? true : false,
        userModifiedModifiable: true,
        userModifiedDuration: true,
        location: { title: body?.location },
        recurrence: recur,
        recurrenceRule: {
          frequency: body?.recur?.frequency,
          interval: body?.recur?.interval,
          byWeekDay: body?.recur?.byWeekDay,
          occurrence: body?.recur?.occurrence,
          endDate: body?.recur?.endDate,
          byMonthDay: body?.recur?.ByMonthDay,
        },
      };

      const googleResValue: GoogleResType = await createGoogleEvent(
        body?.userId,
        primaryCalendar?.id,
        calIntegration?.clientType,
        eventToUpsertLocal?.id,
        eventToUpsertLocal?.endDate,
        eventToUpsertLocal?.startDate,
        0,
        undefined,
        eventToUpsertLocal?.sendUpdates,
        eventToUpsertLocal?.anyoneCanAddSelf,
        body?.attendees?.map((a) => ({ email: a?.email })),
        undefined,
        eventToUpsertLocal?.title,
        eventToUpsertLocal?.notes,
        body?.timezone,
        undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.guestsCanInviteOthers,
        eventToUpsertLocal?.guestsCanModify,
        eventToUpsertLocal?.guestsCanSeeOtherGuests,
        eventToUpsertLocal?.originalStartDate,
        undefined,
        recur,
        remindersToUpdateEventId?.length > 0 ? googleReminder : undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.transparency,
        eventToUpsertLocal?.visibility,
        undefined,
        undefined,
        undefined,
        undefined,
        undefined,
        eventToUpsertLocal?.attachments,
        'default',
        body?.location,
        undefined
      );

      eventToUpsertLocal.id = googleResValue.id;
      eventToUpsertLocal.eventId = googleResValue.googleEventId;

      if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
        const returnValues = createPreAndPostEventsFromEvent(
          eventToUpsertLocal,
          body?.bufferTime
        );

        if (returnValues?.afterEvent) {
          const googleResValue: GoogleResType = await createGoogleEvent(
            body?.userId,
            primaryCalendar?.id,
            calIntegration?.clientType,
            returnValues?.afterEvent?.id,
            returnValues?.afterEvent?.endDate,
            returnValues?.afterEvent?.startDate,
            0,
            undefined,
            returnValues?.afterEvent?.sendUpdates,
            returnValues?.afterEvent?.anyoneCanAddSelf,
            undefined,
            undefined,
            returnValues?.afterEvent?.title,
            returnValues?.afterEvent?.notes,
            body?.timezone,
            undefined,
            undefined,
            undefined,
            returnValues?.afterEvent?.guestsCanInviteOthers,
            returnValues?.afterEvent?.guestsCanModify,
            returnValues?.afterEvent?.guestsCanSeeOtherGuests,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            returnValues?.afterEvent?.transparency,
            returnValues?.afterEvent?.visibility,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            'default',
            undefined,
            undefined
          );

          returnValues.afterEvent.id = googleResValue.id;
          returnValues.afterEvent.eventId = googleResValue.googleEventId;
          returnValues.newEvent.postEventId = returnValues.afterEvent.id;
        }

        if (returnValues?.beforeEvent) {
          const googleResValue: GoogleResType = await createGoogleEvent(
            body?.userId,
            primaryCalendar?.id,
            calIntegration?.clientType,
            returnValues?.beforeEvent?.id,
            returnValues?.beforeEvent?.endDate,
            returnValues?.beforeEvent?.startDate,
            0,
            undefined,
            returnValues?.beforeEvent?.sendUpdates,
            returnValues?.beforeEvent?.anyoneCanAddSelf,
            undefined,
            undefined,
            returnValues?.beforeEvent?.title,
            returnValues?.beforeEvent?.notes,
            body?.timezone,
            undefined,
            undefined,
            undefined,
            returnValues?.beforeEvent?.guestsCanInviteOthers,
            returnValues?.beforeEvent?.guestsCanModify,
            returnValues?.beforeEvent?.guestsCanSeeOtherGuests,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            returnValues?.beforeEvent?.transparency,
            returnValues?.beforeEvent?.visibility,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            undefined,
            'default',
            undefined,
            undefined
          );

          returnValues.beforeEvent.id = googleResValue.id;
          returnValues.beforeEvent.eventId = googleResValue.googleEventId;
          returnValues.newEvent.preEventId = returnValues.afterEvent.id;
        }

        await upsertEvents(
          [
            returnValues.newEvent,
            returnValues?.afterEvent,
            returnValues?.beforeEvent,
          ]?.filter((e) => !!e)
        );
      } else {
        await upsertEvents([eventToUpsertLocal]);
      }

      remindersToUpdateEventId?.forEach((r) => ({
        ...r,
        eventId: eventToUpsertLocal.id,
      }));

      newPreferredTimeRanges?.forEach((p) => ({
        ...p,
        eventId: eventToUpsertLocal.id,
      }));

      attendees?.forEach((a) => ({ ...a, eventId: eventToUpsertLocal?.id }));

      if (remindersToUpdateEventId?.length > 0) {
        await insertReminders(remindersToUpdateEventId);
      }

      if (newPreferredTimeRanges?.length > 0) {
        await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
      }

      await upsertAttendeesforEvent(attendees);
    }

    const searchVector = await convertEventTitleToOpenAIVector(body?.title);
    if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
      await putDataInTrainEventIndexInOpenSearch(
        eventId,
        searchVector,
        body?.userId
      );
    }

    await putDataInAllEventIndexInOpenSearch(
      eventId,
      searchVector,
      body?.userId,
      body?.startDate,
      dayjs(body?.startDate)
        .tz(body?.timezone)
        .add(body?.duration, 'm')
        .format()
    );

    response.query = 'completed';
    response.data = 'successfully scheduled meeting';
    return response;
  } catch (e) {
    console.log(e, ' unable to final step schedule meeting');
  }
};

export const processScheduleMeetingPending = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string
): Promise<ResponseActionType> => {
  try {
    let duration = 0;

    const year = dateJSONBody?.year;
    const month = dateJSONBody?.month;
    const day = dateJSONBody?.day;
    const isoWeekday = dateJSONBody?.isoWeekday;
    const hour = dateJSONBody?.hour;
    const minute = dateJSONBody?.minute;
    const startTime = dateJSONBody?.startTime;

    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'scheduleMeeting',
    };

    const meetingStartDate = extrapolateStartDateFromJSONData(
      currentTime,
      timezone,
      year,
      month,
      day,
      isoWeekday,
      hour,
      minute,
      startTime,
      dateJSONBody?.relativeTimeChangeFromNow,
      dateJSONBody?.relativeTimeFromNow
    );

    const defaultMeetingPreferences =
      await getChatMeetingPreferenceGivenUserId(userId);

    if (dateJSONBody?.duration) {
      duration = dateJSONBody?.duration;
    } else if (dateJSONBody?.startTime && dateJSONBody?.endTime) {
      const startTimeObject = dayjs(dateJSONBody?.startTime, 'HH:mm');
      const endTimeObject = dayjs(dateJSONBody.endTime, 'HH:mm');

      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else if (jsonBody?.params?.startTime && jsonBody?.params?.endTime) {
      const startTimeObject = dayjs(jsonBody?.params?.startTime);
      const endTimeObject = dayjs(jsonBody?.params?.endTime);
      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else if (defaultMeetingPreferences?.duration) {
      duration = defaultMeetingPreferences?.duration;
    } else {
      duration = 30;
    }

    let recurObject: RecurrenceRuleType | {} = {};
    if (dateJSONBody?.recur?.frequency) {
      const recurEndDate = extrapolateDateFromJSONData(
        currentTime,
        timezone,
        dateJSONBody?.recur?.endDate?.year,
        dateJSONBody?.recur?.endDate?.month,
        dateJSONBody?.recur?.endDate?.day,
        dateJSONBody?.recur?.endDate?.isoWeekday,
        dateJSONBody?.recur?.endDate?.hour,
        dateJSONBody?.recur?.endDate?.minute,
        dateJSONBody?.recur?.endDate?.startTime,
        dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow,
        dateJSONBody?.recur?.endDate?.relativeTimeFromNow
      );

      recurObject = {
        frequency:
          (dateJSONBody?.recur?.frequency as RecurrenceFrequencyType) ||
          jsonBody?.params?.recurrence?.frequency,
        interval:
          dateJSONBody?.recur?.interval ||
          jsonBody?.params?.recurrence?.interval,
      };

      if (dateJSONBody?.recur?.byWeekDay) {
        (recurObject as RecurrenceRuleType).byWeekDay =
          dateJSONBody?.recur?.byWeekDay;
      }

      if (dateJSONBody?.recur?.byMonthDay) {
        (recurObject as RecurrenceRuleType).byMonthDay =
          dateJSONBody?.recur?.byMonthDay;
      }

      if (dateJSONBody?.recur?.occurrence) {
        (recurObject as RecurrenceRuleType).occurrence =
          dateJSONBody?.recur?.occurrence;
      }

      if (recurEndDate || jsonBody?.params?.recurrence?.endDate) {
        (recurObject as RecurrenceRuleType).endDate =
          recurEndDate || jsonBody?.params?.recurrence?.endDate;
      }
    }

    const body: ScheduleMeetingType = {
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
      startDate: jsonBody?.params?.startTime || meetingStartDate,
      bufferTime:
        jsonBody?.params?.bufferTime || defaultMeetingPreferences?.bufferTime,
      reminders:
        jsonBody?.params?.alarms || defaultMeetingPreferences?.reminders || [],
      priority: jsonBody?.params?.priority || 1,
      timePreferences: dateJSONBody?.timePreferences || [],
      location: jsonBody?.params?.location,
      transparency: jsonBody?.params?.transparency,
      visibility: jsonBody?.params.visibility,
    };

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      body.recur = recurObject as any;
    }

    // if (!day && !isoWeekday) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0])
    //     response.data = missingFields
    //     response.prevData = body
    //     response.prevJsonBody = jsonBody
    //     response.prevDateJsonBody = dateJSONBody
    // }

    // if ((hour === null) && (minute === null) && !startTime) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1])
    //     response.data = missingFields
    //     response.prevData = body
    //     response.prevJsonBody = jsonBody
    //     response.prevDateJsonBody = dateJSONBody
    // }

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
          response.prevData = body;
          response.prevJsonBody = jsonBody;
          response.prevDateJsonBody = dateJSONBody;
        }
      } else {
        newAttendees.push(a);
      }
    }

    body.attendees = newAttendees;

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

    const response2 = await finalStepScheduleMeeting(
      body,
      defaultMeetingPreferences,
      response
    );

    return response2;
  } catch (e) {
    console.log(e, ' unable to process schedule meeting');
  }
};

export const processScheduleMeetingMissingFieldsReturned = async (
  userId: string,
  timezone: string,
  jsonBody: UserInputToJSONType,
  dateJSONBody: DateTimeJSONType,
  currentTime: string,
  messageHistoryObject: SkillMessageHistoryType
) => {
  try {
    let duration = 0;

    const year =
      dateJSONBody?.year || messageHistoryObject?.prevDateJsonBody?.year;
    const month =
      dateJSONBody?.month || messageHistoryObject?.prevDateJsonBody?.month;
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

    const missingFields: RequiredFieldsType = {
      required: [],
      dateTime: { required: [] },
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'scheduleMeeting',
    };

    const meetingStartDate = extrapolateStartDateFromJSONData(
      currentTime,
      timezone,
      year,
      month,
      day,
      isoWeekday,
      hour,
      minute,
      startTime,
      dateJSONBody?.relativeTimeChangeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.relativeTimeChangeFromNow,
      dateJSONBody?.relativeTimeFromNow ||
        messageHistoryObject?.prevDateJsonBody?.relativeTimeFromNow
    );

    const defaultMeetingPreferences =
      await getChatMeetingPreferenceGivenUserId(userId);

    if (
      dateJSONBody?.duration ||
      messageHistoryObject?.prevDateJsonBody?.duration
    ) {
      duration =
        dateJSONBody?.duration ||
        messageHistoryObject?.prevDateJsonBody?.duration;
    } else if (
      (dateJSONBody?.startTime ||
        messageHistoryObject?.prevDateJsonBody?.startTime) &&
      (dateJSONBody?.endTime || messageHistoryObject?.prevDateJsonBody?.endTime)
    ) {
      const startTimeObject = dayjs(
        dateJSONBody?.startTime ||
          messageHistoryObject?.prevDateJsonBody?.startTime,
        'HH:mm'
      );
      const endTimeObject = dayjs(
        dateJSONBody.endTime || messageHistoryObject?.prevDateJsonBody?.endTime,
        'HH:mm'
      );

      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else if (defaultMeetingPreferences?.duration) {
      duration = defaultMeetingPreferences?.duration;
    } else if (
      (jsonBody?.params?.startTime ||
        messageHistoryObject?.prevJsonBody?.params?.startTime) &&
      (jsonBody?.params?.endTime ||
        messageHistoryObject?.prevJsonBody?.params?.endTime)
    ) {
      const startTimeObject = dayjs(
        jsonBody?.params?.startTime ||
          messageHistoryObject?.prevJsonBody?.params?.startTime
      );
      const endTimeObject = dayjs(
        jsonBody?.params?.endTime ||
          messageHistoryObject?.prevJsonBody?.params?.endTime
      );
      const minutes = endTimeObject.diff(startTimeObject, 'm');

      if (minutes > 0) {
        duration = minutes;
      }
    } else {
      duration = 30;
    }

    let recurObject: RecurrenceRuleType | {} = {};
    if (
      dateJSONBody?.recur?.frequency ||
      messageHistoryObject?.prevDateJsonBody?.recur?.frequency
    ) {
      const recurEndDate = extrapolateDateFromJSONData(
        currentTime,
        timezone,
        dateJSONBody?.recur?.endDate?.year ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.year,
        dateJSONBody?.recur?.endDate?.month ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.month,
        dateJSONBody?.recur?.endDate?.day ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.day,
        dateJSONBody?.recur?.endDate?.isoWeekday ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.isoWeekday,
        dateJSONBody?.recur?.endDate?.hour ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.hour,
        dateJSONBody?.recur?.endDate?.minute ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.minute,
        dateJSONBody?.recur?.endDate?.startTime ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate?.startTime,
        dateJSONBody?.recur?.endDate?.relativeTimeChangeFromNow ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate
            ?.relativeTimeChangeFromNow,
        dateJSONBody?.recur?.endDate?.relativeTimeFromNow ||
          messageHistoryObject?.prevDateJsonBody?.recur?.endDate
            ?.relativeTimeFromNow
      );

      recurObject = {
        frequency:
          (dateJSONBody?.recur?.frequency as RecurrenceFrequencyType) ||
          messageHistoryObject?.prevDateJsonBody?.recur?.frequency ||
          messageHistoryObject?.prevJsonBody?.params?.recurrence?.frequency ||
          jsonBody?.params?.recurrence?.frequency,
        interval:
          dateJSONBody?.recur?.interval ||
          messageHistoryObject?.prevDateJsonBody?.recur?.interval ||
          messageHistoryObject?.prevJsonBody?.params?.recurrence?.interval ||
          jsonBody?.params?.recurrence?.interval,
      };

      if (
        dateJSONBody?.recur?.byWeekDay ||
        messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay
      ) {
        (recurObject as RecurrenceRuleType).byWeekDay =
          dateJSONBody?.recur?.byWeekDay ||
          messageHistoryObject?.prevDateJsonBody?.recur?.byWeekDay;
      }

      if (
        dateJSONBody?.recur?.byMonthDay ||
        messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay
      ) {
        (recurObject as RecurrenceRuleType).byMonthDay =
          dateJSONBody?.recur?.byMonthDay ||
          messageHistoryObject?.prevDateJsonBody?.recur?.byMonthDay;
      }

      if (
        dateJSONBody?.recur?.occurrence ||
        messageHistoryObject?.prevDateJsonBody?.recur?.occurrence
      ) {
        (recurObject as RecurrenceRuleType).occurrence =
          dateJSONBody?.recur?.occurrence ||
          messageHistoryObject?.prevDateJsonBody?.recur?.occurrence;
      }

      if (
        recurEndDate ||
        messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
        jsonBody?.params?.recurrence?.endDate
      ) {
        (recurObject as RecurrenceRuleType).endDate =
          recurEndDate ||
          messageHistoryObject?.prevJsonBody?.params?.recurrence?.endDate ||
          jsonBody?.params?.recurrence?.endDate;
      }
    }

    const newBody: ScheduleMeetingType = {
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
      startDate:
        jsonBody?.params?.startTime ||
        messageHistoryObject?.prevJsonBody?.params?.startTime ||
        meetingStartDate,
      bufferTime:
        jsonBody?.params?.bufferTime ||
        messageHistoryObject?.prevJsonBody?.params?.bufferTime ||
        defaultMeetingPreferences?.bufferTime,
      reminders:
        jsonBody?.params?.alarms ||
        messageHistoryObject?.prevJsonBody?.params?.alarms ||
        defaultMeetingPreferences?.reminders ||
        [],
      priority:
        jsonBody?.params?.priority ||
        messageHistoryObject?.prevJsonBody?.params?.priority ||
        1,
      timePreferences:
        dateJSONBody?.timePreferences ||
        messageHistoryObject?.prevDateJsonBody?.timePreferences ||
        [],
      location:
        jsonBody?.params?.location ||
        messageHistoryObject?.prevJsonBody?.params?.location,
      transparency:
        jsonBody?.params?.transparency ||
        messageHistoryObject?.prevJsonBody?.params?.transparency,
      visibility:
        jsonBody?.params.visibility ||
        messageHistoryObject?.prevJsonBody?.params?.visibility,
    };

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      newBody.recur = recurObject as any;
    }

    const prevBody: ScheduleMeetingType = {
      ...messageHistoryObject?.prevData,
    };

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

    if (!prevBody?.userId) {
      prevBody.userId = userId || newBody?.userId;
    }

    if (!prevBody?.timezone) {
      prevBody.timezone = timezone || newBody?.timezone;
    }

    if (!prevBody?.title) {
      prevBody.title = newBody?.title;
    }

    if (!(prevBody?.attendees?.length > 0)) {
      prevBody.attendees = newBody?.attendees;
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

    if (!prevBody?.startDate) {
      prevBody.startDate = newBody?.startDate;
    }

    if (!prevBody?.bufferTime) {
      prevBody.bufferTime = newBody?.bufferTime;
    }

    if (!(prevBody?.reminders?.length > 0)) {
      prevBody.reminders = newBody?.reminders || [];
    }

    if (!prevBody?.priority) {
      prevBody.priority = newBody?.priority;
    }

    if (!(prevBody?.timePreferences?.length > 0)) {
      prevBody.timePreferences = newBody?.timePreferences;
    }

    if (!prevBody?.location) {
      prevBody.location = newBody?.location;
    }

    if (!prevBody?.transparency) {
      prevBody.transparency = newBody?.transparency;
    }

    if (!prevBody?.visibility) {
      prevBody.visibility = newBody?.visibility;
    }

    // if (!prevBody?.startDate) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[0])
    //     response.data = missingFields
    //     response.prevData = prevBody
    //     response.prevJsonBody = jsonBody
    //     response.prevDateJsonBody = dateJSONBody
    // }

    // if (!prevBody?.startDate && (hour === null) && (minute === null) && !startTime) {
    //     response.query = 'missing_fields'
    //     missingFields.dateTime.required.push(requiredFields.dateTime.required?.[1])
    //     response.data = missingFields
    //     response.prevData = prevBody
    //     response.prevJsonBody = jsonBody
    //     response.prevDateJsonBody = dateJSONBody
    // }

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

    if (!prevBody?.recur) {
      prevBody.recur = newBody?.recur;
    }

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepScheduleMeeting(
      prevBody,
      defaultMeetingPreferences,
      response
    );

    return response2;
  } catch (e) {
    console.log(
      e,
      ' unable to process schedule meeting missing fields returned'
    );
  }
};

export const scheduleMeetingControlCenter = async (
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

    let scheduleMeetingRes: ResponseActionType = {
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
        scheduleMeetingRes = await processScheduleMeetingPending(
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

        scheduleMeetingRes = await processScheduleMeetingMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (scheduleMeetingRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          scheduleMeetingRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (scheduleMeetingRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          scheduleMeetingRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required =
        scheduleMeetingRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = scheduleMeetingRes?.prevData;
      messageHistoryObject.prevDataExtra = scheduleMeetingRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody =
        scheduleMeetingRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = scheduleMeetingRes?.prevJsonBody;
    } else if (scheduleMeetingRes?.query === 'event_not_found') {
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
    console.log(e, ' unable to schedule meeting control center pending');
  }
};
