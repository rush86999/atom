import {
  allEventWithDatesOpenSearch,
  convertEventTitleToOpenAIVector,
  createGoogleEvent,
  createPreAndPostEventsFromEvent,
  createRRuleString,
  createZoomMeeting,
  deleteConferenceGivenId,
  deleteEventGivenId,
  deleteGoogleEvent,
  deleteRemindersWithIds,
  deleteZoomMeeting,
  eventSearchBoundary,
  extrapolateStartDateFromJSONData,
  findContactByEmailGivenUserId,
  generateAssistantMessageFromAPIResponseForUserQuery,
  generateAssistantMessageToRequestUserForMissingFields,
  generateDateTime,
  generateJSONDataFromUserInput,
  generateMissingFieldsDateTime,
  generateMissingFieldsJSONDataFromUserInput,
  getCalendarIntegrationByName,
  getConferenceGivenId,
  getContactByNameWithUserId,
  getEventFromPrimaryKey,
  getUserContactInfosGivenIds,
  getZoomAPIToken,
  insertReminders,
  patchGoogleEvent,
  putDataInTrainEventIndexInOpenSearch,
  updateZoomMeeting,
  upsertAttendeesforEvent,
  upsertConference,
  upsertEvents,
} from '@chat/_libs/api-helper';
import DateTimeJSONType from '@chat/_libs/datetime/DateTimeJSONJSONType';
import UserInputToJSONType, {
  MutatedCalendarExtractedJSONAttendeeType,
} from '@chat/_libs/types/UserInputToJSONType';
import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';
import { EditEventType } from './types';
import { getChatMeetingPreferenceGivenUserId } from '../scheduleMeeting/api-helper';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import requiredFields from './requiredFields';
import { v4 as uuid } from 'uuid';
import { ReminderType } from '@chat/_libs/types/GoogleTypes';
import { GoogleReminderType } from '@chat/_libs/types/GoogleReminderType';
import PreferredTimeRangeType from '@chat/_libs/types/PreferredTimeRangeType';
import { DayOfWeekEnum } from '../resolveConflictingEvents/constants';
import { googleCalendarName } from '@chat/_libs/constants';
import { deletePreferredTimeRangesGivenEventId } from '../removeAllPreferedTimes/api-helper';
import { ConferenceType } from '@chat/_libs/types/ConferenceType';
import {
  EventType,
  RecurrenceFrequencyType,
  RecurrenceRuleType,
  VisibilityType,
} from '@chat/_libs/types/EventType';
import { AttendeeType } from '@chat/_libs/types/AttendeeType';
import { GoogleResType } from '@chat/_libs/types/GoogleResType';
import { upsertPreferredTimeRangesForEvent } from '../resolveConflictingEvents/api-helper';
import ResponseActionType from '@chat/_libs/types/ResponseActionType';
import {
  AssistantMessageType,
  SkillMessageHistoryType,
} from '@chat/_libs/types/Messaging/MessagingTypes';
import OpenAI from 'openai';
import { ChatMeetingPreferencesType } from '@chat/_libs/types/ChatMeetingPreferencesType';
import { SearchBoundaryType } from '../deleteTask/types';

export const finalStepEditEvent = async (
  body: EditEventType,
  defaultMeetingPreferences: ChatMeetingPreferencesType,
  startDate: string,
  endDate: string,
  response: any
) => {
  try {
    // convert to vector for search
    const searchTitle = body?.oldTitle || body?.title;
    const searchVector = await convertEventTitleToOpenAIVector(searchTitle);

    //  allEventWithEventOpenSearch
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

    const eventId = id;

    // get client type
    const calIntegration = await getCalendarIntegrationByName(
      body?.userId,
      googleCalendarName
    );

    // delete old reminders
    if (body?.reminders?.length > 0) {
      await deleteRemindersWithIds([eventId], body?.userId);
    }

    // delete old time preferences
    if (body?.timePreferences?.length > 0) {
      await deletePreferredTimeRangesGivenEventId(eventId);
    }

    // get old event
    const oldEvent = await getEventFromPrimaryKey(eventId);

    // validate
    if (!oldEvent?.id) {
      throw new Error('no old event found?!');
    }

    // if no priority use old
    if (!body?.priority) {
      body.priority = oldEvent.priority || 1;
    }

    // findContactByEmailGivenUserId
    // get attendees with provided emails
    const aWithEmails = body?.attendees?.filter((a) => !!a?.email);

    const aWithContactInfos = await getUserContactInfosGivenIds(
      aWithEmails?.map((a) => a?.email)
    );

    const attendeesFromExtractedJSON = body?.attendees || [];
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

    // take care of recurrence
    const recur = createRRuleString(
      body?.recur?.frequency,
      body?.recur?.interval,
      body?.recur?.byWeekDay,
      body?.recur?.occurrence,
      body?.recur?.endDate,
      (body?.recur as RecurrenceRuleType)?.byMonthDay
    );

    let conference: ConferenceType | {} = {};

    // conference: create / update and store in db
    if (body?.conferenceApp && !oldEvent.conferenceId) {
      // create conference object
      const zoomToken = await getZoomAPIToken(body?.userId);

      conference =
        zoomToken && body?.conferenceApp === 'zoom'
          ? {}
          : {
              id: uuid(),
              userId: body?.userId,
              calendarId: oldEvent?.calendarId,
              app: 'google',
              name: defaultMeetingPreferences?.name,
              notes: body?.description || body?.title,
              updatedAt: dayjs().format(),
              createdDate: dayjs().format(),
              deleted: false,
              isHost: true,
            };

      if (body?.conferenceApp === 'zoom') {
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
            calendarId: oldEvent?.id,
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

      // insert new conference
      await upsertConference(conference as ConferenceType);
    } else if (body?.conferenceApp && oldEvent.conferenceId) {
      // get old conference object
      const oldConference = await getConferenceGivenId(oldEvent?.conferenceId);
      // create conference object
      const zoomToken = await getZoomAPIToken(body?.userId);

      // updateZoomMeeting
      conference =
        zoomToken && body?.conferenceApp === 'zoom'
          ? {}
          : {
              ...oldConference,
              id: oldEvent?.conferenceId,
              userId: body?.userId,
              calendarId: oldEvent?.calendarId,
              app: 'google',
              name: defaultMeetingPreferences?.name,
              notes: body?.description || body?.title,
              updatedAt: dayjs().format(),
              createdDate: dayjs().format(),
              deleted: false,
              isHost: true,
            };

      if (body?.conferenceApp === oldConference.app) {
        console.log(zoomToken, ' zoomToken inside if (zoomToken)');

        if (zoomToken && body?.conferenceApp === 'zoom') {
          await updateZoomMeeting(
            zoomToken,
            parseInt(oldEvent?.conferenceId, 10),
            body?.startDate,
            body?.timezone,
            body?.title || body?.description,
            body?.duration || oldEvent?.duration,
            defaultMeetingPreferences?.name,
            defaultMeetingPreferences?.primaryEmail,
            attendees?.length > 0
              ? attendees?.map((a) => a?.emails?.[0]?.value)
              : undefined,
            undefined,
            body?.recur as any
          );

          conference = {
            ...oldConference,
            id: oldConference?.id,
            userId: body?.userId,
            calendarId: oldEvent?.calendarId,
            app: 'zoom',
            name: defaultMeetingPreferences?.name,
            notes: body?.description || oldEvent?.notes,
            isHost: true,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            deleted: false,
          } as ConferenceType;
        } else {
          conference = {
            ...oldConference,
            userId: body?.userId,
            calendarId: oldEvent?.calendarId,
            app: 'google',
            name: defaultMeetingPreferences?.name,
            notes: body?.description || body?.title,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            deleted: false,
            isHost: true,
          };
        }

        // insert new conference
        await upsertConference(conference as ConferenceType);
      } else if (body?.conferenceApp !== oldConference.app) {
        // create conference object
        const zoomToken = await getZoomAPIToken(body?.userId);

        conference =
          zoomToken && body?.conferenceApp === 'zoom'
            ? {}
            : {
                id: uuid(),
                userId: body?.userId,
                calendarId: oldEvent?.calendarId,
                app: 'google',
                name: defaultMeetingPreferences?.name,
                notes: body?.description || body?.title,
                updatedAt: dayjs().format(),
                createdDate: dayjs().format(),
                deleted: false,
                isHost: true,
              };

        if (zoomToken && body?.conferenceApp === 'zoom') {
          console.log(zoomToken, ' zoomToken inside if (zoomToken)');

          const zoomObject = await createZoomMeeting(
            zoomToken,
            body?.startDate,
            body?.timezone,
            body?.title || body?.description,
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
              calendarId: oldEvent?.id,
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

        // delete old conference
        await deleteConferenceGivenId(oldConference?.id);
        if (oldConference.app === 'zoom') {
          await deleteZoomMeeting(zoomToken, parseInt(oldConference.id, 10));
        }
        // insert new conference
        await upsertConference(conference as ConferenceType);
      }
    }
    // if existing buffer times
    // delete old and create new ones later on
    if (
      (oldEvent?.preEventId && body?.bufferTime?.beforeEvent) ||
      (oldEvent?.postEventId && body?.bufferTime?.afterEvent)
    ) {
      // delete buffere times if any

      if (oldEvent?.preEventId) {
        const preEvent = await getEventFromPrimaryKey(oldEvent?.preEventId);
        await deleteGoogleEvent(
          body?.userId,
          preEvent?.calendarId,
          preEvent?.eventId,
          calIntegration?.clientType
        );
        await deleteEventGivenId(oldEvent?.preEventId);
      }

      if (oldEvent?.postEventId) {
        const postEvent = await getEventFromPrimaryKey(oldEvent?.postEventId);
        await deleteGoogleEvent(
          body?.userId,
          postEvent?.calendarId,
          postEvent?.eventId,
          calIntegration?.clientType
        );
        await deleteEventGivenId(oldEvent?.postEventId);
      }
    }

    // create new time preferences and priority
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

    // create new reminders for updated event
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

    // patchGoogleEvent
    const startDateTime = startDate
      ? dayjs(startDate).tz(body?.timezone).format()
      : oldEvent?.startDate;
    const endDateTime =
      startDateTime && body?.duration
        ? dayjs(startDateTime)
            .tz(body?.timezone)
            .add(body?.duration, 'minute')
            .format()
        : oldEvent?.endDate;

    const eventToUpsertLocal: EventType = {
      ...oldEvent,
      id: eventId,
      userId: body?.userId,
      timezone: body?.timezone,
      isPreEvent: false,
      isPostEvent: false,
      updatedAt: dayjs().format(),
    };

    if (body?.allDay) {
      eventToUpsertLocal.allDay = body?.allDay;
    }

    if (body?.title) {
      eventToUpsertLocal.title = body?.title;
      eventToUpsertLocal.summary = body?.title;
    }

    if (startDate) {
      eventToUpsertLocal.startDate = dayjs(startDate)
        .tz(body?.timezone)
        .format();
    }

    if (endDateTime && endDateTime !== oldEvent?.endDate) {
      eventToUpsertLocal.endDate = dayjs(startDateTime)
        .tz(body?.timezone)
        .add(body?.duration, 'minute')
        .format();
    }

    if (body?.duration && body?.duration !== oldEvent?.duration) {
      eventToUpsertLocal.duration = body?.duration;
    }

    if (body?.isFollowUp) {
      eventToUpsertLocal.isFollowUp = body.isFollowUp;
    }

    if (body?.description || body?.title) {
      eventToUpsertLocal.notes = body?.description || body?.title;
    }

    if (body?.priority) {
      eventToUpsertLocal.priority = body.priority;
    }

    if (body?.transparency) {
      eventToUpsertLocal.transparency = body.transparency;
      eventToUpsertLocal.userModifiedAvailability = true;
    }

    if (body?.visibility) {
      eventToUpsertLocal.visibility = body.visibility as VisibilityType;
    }

    if ((conference as ConferenceType)?.id) {
      eventToUpsertLocal.conferenceId = (conference as ConferenceType)?.id;
    }

    if (body?.bufferTime) {
      eventToUpsertLocal.timeBlocking = body.bufferTime;
      eventToUpsertLocal.userModifiedTimeBlocking = true;
    }

    if (body?.timePreferences?.length > 0) {
      eventToUpsertLocal.userModifiedTimePreference = true;
      eventToUpsertLocal.modifiable = true;
      eventToUpsertLocal.userModifiedModifiable = true;
    }

    if (body?.reminders?.length > 0) {
      eventToUpsertLocal.userModifiedReminders = true;
    }

    if (body?.priority > 1) {
      eventToUpsertLocal.userModifiedPriorityLevel = true;
      eventToUpsertLocal.modifiable = true;
      eventToUpsertLocal.userModifiedModifiable = true;
    }

    if (body?.duration) {
      eventToUpsertLocal.userModifiedDuration = true;
    }

    if (body?.location) {
      eventToUpsertLocal.location = { title: body?.location };
    }

    if (body?.recur) {
      eventToUpsertLocal.recurrence = recur;
      eventToUpsertLocal.recurrenceRule = {
        frequency: body?.recur?.frequency,
        interval: body?.recur?.interval,
        byWeekDay: body?.recur?.byWeekDay,
        occurrence: body?.recur?.occurrence,
        endDate: body?.recur?.endDate,
        byMonthDay: (body?.recur as RecurrenceRuleType)?.byMonthDay,
      };
    }

    const googleReminder: GoogleReminderType = {
      overrides: remindersToUpdateEventId?.map((r) => ({
        method: 'email',
        minutes: r?.minutes,
      })),
      useDefault: false,
    };

    await patchGoogleEvent(
      body?.userId,
      oldEvent?.calendarId,
      eventToUpsertLocal?.eventId,
      calIntegration?.clientType,
      eventToUpsertLocal?.endDate,
      eventToUpsertLocal?.startDate,
      eventToUpsertLocal?.conferenceId ? 1 : 0,
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
      eventToUpsertLocal?.timezone,
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
      undefined,
      'default',
      body?.location,
      undefined
    );

    // add buffer time
    // add buffer time if any
    if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {
      const returnValues = createPreAndPostEventsFromEvent(
        eventToUpsertLocal,
        body?.bufferTime
      );

      if (returnValues?.afterEvent) {
        const googleResValue: GoogleResType = await createGoogleEvent(
          body?.userId,
          oldEvent?.calendarId,
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
          recur,
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
          oldEvent?.calendarId,
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
          recur,
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

      // insert events
      await upsertEvents(
        [
          returnValues.newEvent,
          returnValues?.afterEvent,
          returnValues?.beforeEvent,
        ]?.filter((e) => !!e)
      );
    } else {
      // insert events
      await upsertEvents([eventToUpsertLocal]);
    }

    // update reminders
    remindersToUpdateEventId?.forEach((r) => ({ ...r, eventId: oldEvent?.id }));

    // update timePreferences
    newPreferredTimeRanges?.forEach((pt) => ({ ...pt, eventId: oldEvent?.id }));

    // insert reminders
    if (remindersToUpdateEventId?.length > 0) {
      await insertReminders(remindersToUpdateEventId);
    }

    // insert time preferences
    if (newPreferredTimeRanges?.length > 0) {
      await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges);
    }

    // add training for time preferences and priority
    // convert to vector for search
    if (newPreferredTimeRanges?.length > 0 || body?.priority > 1) {
      const searchVector = await convertEventTitleToOpenAIVector(body?.title);

      // train event
      await putDataInTrainEventIndexInOpenSearch(
        eventId,
        searchVector,
        body?.userId
      );
    }

    // update attendees for event Id
    await upsertAttendeesforEvent(attendees);

    // success response
    response.query = 'completed';
    response.data = 'event successfully edited';
    return response;
  } catch (e) {
    console.log(e, ' unable final step edit event');
  }
};

export const processEditEventPending = async (
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

    let duration = 0;

    const year = dateJSONBody?.year;
    const month = dateJSONBody?.month;
    const day = dateJSONBody?.day;
    const isoWeekday = dateJSONBody?.isoWeekday;
    const hour = dateJSONBody?.hour;
    const minute = dateJSONBody?.minute;
    const startTime = dateJSONBody?.startTime;

    const eventStartDate = extrapolateStartDateFromJSONData(
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

    // get default values
    const defaultMeetingPreferences =
      await getChatMeetingPreferenceGivenUserId(userId);

    if (dateJSONBody?.duration) {
      duration = dateJSONBody?.duration;
    } else if (dateJSONBody?.startTime && dateJSONBody?.endTime) {
      // likely start time also present

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
    }

    // take care of any recurring dates
    let recurObject: RecurrenceRuleType | {} = {};
    if (dateJSONBody?.recur?.frequency) {
      const recurEndDate = extrapolateStartDateFromJSONData(
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

    const body: EditEventType = {
      userId,
      timezone,
      title:
        jsonBody?.params?.title ||
        jsonBody?.params?.summary ||
        jsonBody?.params?.description ||
        jsonBody?.params?.taskList?.[0]?.task,
      oldTitle: jsonBody?.params?.oldTitle,
      attendees: jsonBody?.params?.attendees,
      method: dateJSONBody?.method as any,
      duration,
      description: jsonBody?.params?.description || jsonBody?.params?.notes,
      conferenceApp: jsonBody?.params?.conference?.app,
      startDate: jsonBody?.params?.startTime || eventStartDate,
      bufferTime: jsonBody?.params?.bufferTime,
      reminders: jsonBody?.params?.alarms,
      priority: jsonBody?.params?.priority,
      timePreferences: dateJSONBody?.timePreferences,
      location: jsonBody?.params?.location,
      transparency: jsonBody?.params?.transparency,
      visibility: jsonBody?.params?.visibility,
      isFollowUp: jsonBody?.params?.isFollowUp,
      isBreak: jsonBody?.params?.isBreak,
      allDay: dateJSONBody?.allDay,
    };

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      body.recur = recurObject as any;
    }
    // validate for missing fields
    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'editEvent',
    };

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

    // get info of contacts without emails provided and assign values
    const newAttendees: MutatedCalendarExtractedJSONAttendeeType[] = [];

    for (const a of body?.attendees) {
      if (!a?.email) {
        const contact = await getContactByNameWithUserId(userId, a?.name);
        if (contact?.emails?.[0]?.value) {
          const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
          const anyEmail = contact?.emails?.[0]?.value;
          newAttendees.push({ ...a, email: primaryEmail || anyEmail });
        } else {
          response.query = 'missing_fields';
          missingFields.required.push(
            requiredFields.optional?.[7]?.['and']?.[2]
          );
          response.data = missingFields;
          response.prevData = body;
          response.prevDataExtra = {
            searchBoundary,
          };
          response.prevJsonBody = jsonBody;
          response.prevDateJsonBody = dateJSONBody;
        }
      } else {
        newAttendees.push(a);
      }
    }

    body.attendees = newAttendees;

    if (response.query === 'missing_fields') {
      return response;
    }

    const response2 = await finalStepEditEvent(
      body,
      defaultMeetingPreferences,
      startDate,
      endDate,
      response
    );

    return response2;
    // convert to vector for search
    // const searchTitle = body?.oldTitle || body?.title
    // const searchVector = await convertEventTitleToOpenAIVector(searchTitle)

    // //  allEventWithEventOpenSearch
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

    // const eventId = id

    // // get client type
    // const calIntegration = await getCalendarIntegrationByName(
    //     userId,
    //     googleCalendarName,
    // )

    // // delete old reminders
    // if (body?.reminders?.length > 0) {

    //     await deleteRemindersWithIds([eventId], userId)
    // }

    // // delete old time preferences
    // if (body?.timePreferences?.length > 0) {
    //     await deletePreferredTimeRangesGivenEventId(eventId)
    // }

    // // get old event
    // const oldEvent = await getEventFromPrimaryKey(eventId)

    // // validate
    // if (!oldEvent?.id) {
    //     throw new Error('no old event found?!')
    // }

    // // if no priority use old
    // if (!body?.priority) {
    //     body.priority = oldEvent.priority || 1
    // }

    // // findContactByEmailGivenUserId
    // // get attendees with provided emails
    // const aWithEmails = body?.attendees?.filter(a => !!a?.email)

    // const aWithContactInfos = await getUserContactInfosGivenIds(aWithEmails?.map(a => (a?.email)))

    // const attendeesFromExtractedJSON = body?.attendees || []
    // const attendees: AttendeeType[] = []

    // for (const a of attendeesFromExtractedJSON) {
    //     const contact = await findContactByEmailGivenUserId(userId, a.email)
    //     const userIdFound = aWithContactInfos?.find(b => (b?.id === a?.email))

    //     const attendee: AttendeeType = {
    //         id: userIdFound?.userId || uuid(),
    //         userId,
    //         name: a?.name || contact?.name || `${contact?.firstName} ${contact?.lastName}`,
    //         contactId: contact?.id,
    //         emails: [{ primary: true, value: a?.email }],
    //         updatedAt: dayjs().format(),
    //         createdDate: dayjs().format(),
    //         deleted: false,
    //         eventId,
    //     }

    //     attendees.push(attendee)
    // }

    // // take care of recurrence
    // const recur = createRRuleString(body?.recur?.frequency, body?.recur?.interval, body?.recur?.byWeekDay, body?.recur?.occurrence, body?.recur?.endDate, (body?.recur as RecurrenceRuleType)?.byMonthDay)

    // let conference: ConferenceType | {} = {}

    // // conference: create / update and store in db
    // if (body?.conferenceApp && !oldEvent.conferenceId) {

    //     // create conference object
    //     const zoomToken = await getZoomAPIToken(userId)

    //     conference = (zoomToken && (body?.conferenceApp === 'zoom')) ? {} : {
    //         id: uuid(),
    //         userId,
    //         calendarId: oldEvent?.calendarId,
    //         app: 'google',
    //         name: defaultMeetingPreferences?.name,
    //         notes: body?.description || body?.title,
    //         updatedAt: dayjs().format(),
    //         createdDate: dayjs().format(),
    //         deleted: false,
    //         isHost: true,
    //     }

    //     if (body?.conferenceApp === 'zoom') {

    //         console.log(zoomToken, ' zoomToken inside if (zoomToken)')

    //         const zoomObject = await createZoomMeeting(
    //             zoomToken,
    //             body?.startDate,
    //             timezone,
    //             body?.title,
    //             duration,
    //             defaultMeetingPreferences?.name,
    //             defaultMeetingPreferences?.primaryEmail,
    //             body?.attendees?.map(a => a?.email),
    //             body?.recur as any,
    //         )

    //         console.log(zoomObject, ' zoomObject after createZoomMeeting')

    //         if (zoomObject) {
    //             conference = {
    //                 id: `${zoomObject?.id}`,
    //                 userId: userId,
    //                 calendarId: oldEvent?.id,
    //                 app: 'zoom',
    //                 name: zoomObject?.agenda,
    //                 notes: zoomObject?.agenda,
    //                 joinUrl: zoomObject?.join_url,
    //                 startUrl: zoomObject?.start_url,
    //                 isHost: true,
    //                 updatedAt: dayjs().format(),
    //                 createdDate: dayjs().format(),
    //                 deleted: false,
    //                 entryPoints: [{
    //                     entryPointType: 'video',
    //                     label: zoomObject?.join_url,
    //                     password: zoomObject?.password,
    //                     uri: zoomObject?.join_url,
    //                 }]
    //             } as ConferenceType

    //         }
    //     }

    //     // insert new conference
    //     await upsertConference(conference as ConferenceType)

    // } else if (body?.conferenceApp && oldEvent.conferenceId) {
    //     // get old conference object
    //     const oldConference = await getConferenceGivenId(oldEvent?.conferenceId)
    //     // create conference object
    //     const zoomToken = await getZoomAPIToken(userId)

    //     // updateZoomMeeting
    //     conference = (zoomToken && (body?.conferenceApp === 'zoom')) ? {} : {
    //         ...oldConference,
    //         id: oldEvent?.conferenceId,
    //         userId,
    //         calendarId: oldEvent?.calendarId,
    //         app: 'google',
    //         name: defaultMeetingPreferences?.name,
    //         notes: body?.description || body?.title,
    //         updatedAt: dayjs().format(),
    //         createdDate: dayjs().format(),
    //         deleted: false,
    //         isHost: true,
    //     }

    //     if (body?.conferenceApp === oldConference.app) {

    //         console.log(zoomToken, ' zoomToken inside if (zoomToken)')

    //         if (zoomToken && (body?.conferenceApp === 'zoom')) {
    //             await updateZoomMeeting(
    //                 zoomToken,
    //                 parseInt(oldEvent?.conferenceId, 10),
    //                 body?.startDate,
    //                 body?.timezone,
    //                 body?.title || body?.description,
    //                 duration || body?.duration || oldEvent?.duration,
    //                 defaultMeetingPreferences?.name,
    //                 defaultMeetingPreferences?.primaryEmail,
    //                 attendees?.length > 0 ? attendees?.map(a => a?.emails?.[0]?.value) : undefined,
    //                 undefined,
    //                 body?.recur as any,
    //             )

    //             conference = {
    //                 ...oldConference,
    //                 id: oldConference?.id,
    //                 userId: userId,
    //                 calendarId: oldEvent?.calendarId,
    //                 app: 'zoom',
    //                 name: defaultMeetingPreferences?.name,
    //                 notes: body?.description || oldEvent?.notes,
    //                 isHost: true,
    //                 updatedAt: dayjs().format(),
    //                 createdDate: dayjs().format(),
    //                 deleted: false,
    //             } as ConferenceType
    //         } else {
    //             conference = {
    //                 ...oldConference,
    //                 userId,
    //                 calendarId: oldEvent?.calendarId,
    //                 app: 'google',
    //                 name: defaultMeetingPreferences?.name,
    //                 notes: body?.description || body?.title,
    //                 updatedAt: dayjs().format(),
    //                 createdDate: dayjs().format(),
    //                 deleted: false,
    //                 isHost: true,
    //             }
    //         }

    //         // insert new conference
    //         await upsertConference(conference as ConferenceType)

    //     } else if (body?.conferenceApp !== oldConference.app) {

    //         // create conference object
    //         const zoomToken = await getZoomAPIToken(userId)

    //         conference = (zoomToken && (body?.conferenceApp === 'zoom')) ? {} : {
    //             id: uuid(),
    //             userId,
    //             calendarId: oldEvent?.calendarId,
    //             app: 'google',
    //             name: defaultMeetingPreferences?.name,
    //             notes: body?.description || body?.title,
    //             updatedAt: dayjs().format(),
    //             createdDate: dayjs().format(),
    //             deleted: false,
    //             isHost: true,
    //         }

    //         if (zoomToken && (body?.conferenceApp === 'zoom')) {

    //             console.log(zoomToken, ' zoomToken inside if (zoomToken)')

    //             const zoomObject = await createZoomMeeting(
    //                 zoomToken,
    //                 body?.startDate,
    //                 timezone,
    //                 body?.title || body?.description,
    //                 duration,
    //                 defaultMeetingPreferences?.name,
    //                 defaultMeetingPreferences?.primaryEmail,
    //                 body?.attendees?.map(a => a?.email),
    //                 body?.recur as any,
    //             )

    //             console.log(zoomObject, ' zoomObject after createZoomMeeting')

    //             if (zoomObject) {
    //                 conference = {
    //                     id: `${zoomObject?.id}`,
    //                     userId: userId,
    //                     calendarId: oldEvent?.id,
    //                     app: 'zoom',
    //                     name: zoomObject?.agenda,
    //                     notes: zoomObject?.agenda,
    //                     joinUrl: zoomObject?.join_url,
    //                     startUrl: zoomObject?.start_url,
    //                     isHost: true,
    //                     updatedAt: dayjs().format(),
    //                     createdDate: dayjs().format(),
    //                     deleted: false,
    //                     entryPoints: [{
    //                         entryPointType: 'video',
    //                         label: zoomObject?.join_url,
    //                         password: zoomObject?.password,
    //                         uri: zoomObject?.join_url,
    //                     }]
    //                 } as ConferenceType

    //             }

    //         }

    //         // delete old conference
    //         await deleteConferenceGivenId(oldConference?.id)
    //         if (oldConference.app === 'zoom') {
    //             await deleteZoomMeeting(zoomToken, parseInt(oldConference.id, 10))
    //         }
    //         // insert new conference
    //         await upsertConference(conference as ConferenceType)
    //     }

    // }
    // // if existing buffer times
    // // delete old and create new ones later on
    // if ((oldEvent?.preEventId && body?.bufferTime?.beforeEvent) || (oldEvent?.postEventId && body?.bufferTime?.afterEvent)) {
    //     // delete buffere times if any

    //     if (oldEvent?.preEventId) {
    //         const preEvent = await getEventFromPrimaryKey(oldEvent?.preEventId)
    //         await deleteGoogleEvent(userId, preEvent?.calendarId, preEvent?.eventId, calIntegration?.clientType)
    //         await deleteEventGivenId(oldEvent?.preEventId)

    //     }

    //     if (oldEvent?.postEventId) {

    //         const postEvent = await getEventFromPrimaryKey(oldEvent?.postEventId)
    //         await deleteGoogleEvent(userId, postEvent?.calendarId, postEvent?.eventId, calIntegration?.clientType)
    //         await deleteEventGivenId(oldEvent?.postEventId)
    //     }
    // }

    // // create new time preferences and priority
    // const newPreferredTimeRanges: PreferredTimeRangeType[] = []

    // for (const timepreference of body?.timePreferences) {

    //     if (timepreference.dayOfWeek?.length > 0) {
    //         for (const dayOfWeek of timepreference.dayOfWeek) {

    //             const newPreferredTimeRange: PreferredTimeRangeType = {
    //                 id: uuid(),
    //                 eventId,
    //                 dayOfWeek: DayOfWeekEnum[dayOfWeek],
    //                 startTime: timepreference?.timeRange?.startTime,
    //                 endTime: timepreference?.timeRange?.endTime,
    //                 updatedAt: dayjs().format(),
    //                 createdDate: dayjs().format(),
    //                 userId,
    //             }

    //             newPreferredTimeRanges.push(newPreferredTimeRange)
    //         }
    //     } else {

    //         const newPreferredTimeRange: PreferredTimeRangeType = {
    //             id: uuid(),
    //             eventId,
    //             startTime: timepreference?.timeRange?.startTime,
    //             endTime: timepreference?.timeRange?.endTime,
    //             updatedAt: dayjs().format(),
    //             createdDate: dayjs().format(),
    //             userId,
    //         }

    //         newPreferredTimeRanges.push(newPreferredTimeRange)
    //     }

    // }

    // // create new reminders for updated event
    // const remindersToUpdateEventId: ReminderType[] = []

    // if (body?.reminders?.length > 0) {
    //     const newReminders: ReminderType[] = body?.reminders.map(r => ({
    //         id: uuid(),
    //         userId,
    //         eventId,
    //         timezone,
    //         minutes: r,
    //         useDefault: false,
    //         updatedAt: dayjs().format(),
    //         createdDate: dayjs().format(),
    //         deleted: false,
    //     }))

    //     remindersToUpdateEventId.push(...newReminders)
    // }

    // // patchGoogleEvent
    // const startDateTime = startDate ? dayjs(startDate).tz(timezone).format() : oldEvent?.startDate
    // const endDateTime = (startDateTime && duration) ? dayjs(startDateTime).tz(timezone).add(duration, 'minute').format()
    //     : oldEvent?.endDate

    // const eventToUpsertLocal: EventType = {
    //     ...oldEvent,
    //     id: eventId,
    //     userId,
    //     timezone,
    //     isPreEvent: false,
    //     isPostEvent: false,
    //     updatedAt: dayjs().format(),
    // }

    // if (body?.allDay) {
    //     eventToUpsertLocal.allDay = body?.allDay
    // }

    // if (body?.title) {
    //     eventToUpsertLocal.title = body?.title
    //     eventToUpsertLocal.summary = body?.title
    // }

    // if (startDate) {
    //     eventToUpsertLocal.startDate = dayjs(startDate).tz(timezone).format()
    // }

    // if (endDateTime && (endDateTime !== oldEvent?.endDate)) {
    //     eventToUpsertLocal.endDate = dayjs(startDateTime).tz(timezone).add(duration, 'minute').format()
    // }

    // if (duration && (duration !== oldEvent?.duration)) {
    //     eventToUpsertLocal.duration = duration
    // }

    // if (body?.isFollowUp) {
    //     eventToUpsertLocal.isFollowUp = body.isFollowUp
    // }

    // if (body?.description || body?.title) {
    //     eventToUpsertLocal.notes = body?.description || body?.title
    // }

    // if (body?.priority) {
    //     eventToUpsertLocal.priority = body.priority
    // }

    // if (body?.transparency) {
    //     eventToUpsertLocal.transparency = body.transparency
    //     eventToUpsertLocal.userModifiedAvailability = true
    // }

    // if (body?.visibility) {
    //     eventToUpsertLocal.visibility = body.visibility as VisibilityType
    // }

    // if ((conference as ConferenceType)?.id) {
    //     eventToUpsertLocal.conferenceId = (conference as ConferenceType)?.id
    // }

    // if (body?.bufferTime) {
    //     eventToUpsertLocal.timeBlocking = body.bufferTime
    //     eventToUpsertLocal.userModifiedTimeBlocking = true
    // }

    // if (body?.timePreferences?.length > 0) {
    //     eventToUpsertLocal.userModifiedTimePreference = true
    //     eventToUpsertLocal.modifiable = true
    //     eventToUpsertLocal.userModifiedModifiable = true
    // }

    // if (body?.reminders?.length > 0) {
    //     eventToUpsertLocal.userModifiedReminders = true
    // }

    // if (body?.priority > 1) {
    //     eventToUpsertLocal.userModifiedPriorityLevel = true
    //     eventToUpsertLocal.modifiable = true
    //     eventToUpsertLocal.userModifiedModifiable = true
    // }

    // if (body?.duration) {
    //     eventToUpsertLocal.userModifiedDuration = true
    // }

    // if (body?.location) {
    //     eventToUpsertLocal.location = { title: body?.location }
    // }

    // if (body?.recur) {
    //     eventToUpsertLocal.recurrence = recur
    //     eventToUpsertLocal.recurrenceRule = {
    //         frequency: body?.recur?.frequency,
    //         interval: body?.recur?.interval,
    //         byWeekDay: body?.recur?.byWeekDay,
    //         occurrence: body?.recur?.occurrence,
    //         endDate: body?.recur?.endDate,
    //         byMonthDay: (body?.recur as RecurrenceRuleType)?.byMonthDay,
    //     }
    // }

    // const googleReminder: GoogleReminderType = {
    //     overrides: remindersToUpdateEventId?.map(r => ({ method: 'email', minutes: r?.minutes })),
    //     useDefault: false,
    // }

    // await patchGoogleEvent(
    //     userId,
    //     oldEvent?.calendarId,
    //     eventToUpsertLocal?.eventId,
    //     calIntegration?.clientType,
    //     eventToUpsertLocal?.endDate,
    //     eventToUpsertLocal?.startDate,
    //     eventToUpsertLocal?.conferenceId ? 1 : 0,
    //     undefined,
    //     eventToUpsertLocal?.sendUpdates,
    //     eventToUpsertLocal?.anyoneCanAddSelf,
    //     body?.attendees?.map(a => ({ email: a?.email })),
    //     (conference as ConferenceType)?.id ? {
    //         type: (conference as ConferenceType)?.app === 'zoom' ? 'addOn' : 'hangoutsMeet',
    //         name: (conference as ConferenceType)?.name,
    //         conferenceId: (conference as ConferenceType)?.id,
    //         entryPoints: (conference as ConferenceType)?.entryPoints,
    //         createRequest: (conference as ConferenceType)?.app === 'google' ? {
    //             requestId: (conference as ConferenceType)?.requestId,
    //             conferenceSolutionKey: {
    //                 type: 'hangoutsMeet',
    //             }
    //         } : undefined,
    //     } : undefined,
    //     eventToUpsertLocal?.summary,
    //     eventToUpsertLocal?.notes,
    //     eventToUpsertLocal?.timezone,
    //     undefined,
    //     undefined,
    //     undefined,
    //     eventToUpsertLocal?.guestsCanInviteOthers,
    //     eventToUpsertLocal?.guestsCanModify,
    //     eventToUpsertLocal?.guestsCanSeeOtherGuests,
    //     eventToUpsertLocal?.originalStartDate,
    //     undefined,
    //     recur,
    //     remindersToUpdateEventId?.length > 0 ? googleReminder : undefined,
    //     undefined,
    //     undefined,
    //     eventToUpsertLocal?.transparency,
    //     eventToUpsertLocal?.visibility,
    //     undefined,
    //     undefined,
    //     undefined,
    //     undefined,
    //     undefined,
    //     undefined,
    //     'default',
    //     body?.location,
    //     undefined,
    // )

    // // add buffer time
    // // add buffer time if any
    // if (body?.bufferTime?.afterEvent || body?.bufferTime?.beforeEvent) {

    //     const returnValues = createPreAndPostEventsFromEvent(eventToUpsertLocal, body?.bufferTime)

    //     if (returnValues?.afterEvent) {

    //         const googleResValue: GoogleResType = await createGoogleEvent(
    //             userId,
    //             oldEvent?.calendarId,
    //             calIntegration?.clientType,
    //             returnValues?.afterEvent?.id,
    //             returnValues?.afterEvent?.endDate,
    //             returnValues?.afterEvent?.startDate,
    //             0,
    //             undefined,
    //             returnValues?.afterEvent?.sendUpdates,
    //             returnValues?.afterEvent?.anyoneCanAddSelf,
    //             undefined,
    //             undefined,
    //             returnValues?.afterEvent?.title,
    //             returnValues?.afterEvent?.notes,
    //             timezone,
    //             undefined,
    //             undefined,
    //             undefined,
    //             returnValues?.afterEvent?.guestsCanInviteOthers,
    //             returnValues?.afterEvent?.guestsCanModify,
    //             returnValues?.afterEvent?.guestsCanSeeOtherGuests,
    //             returnValues?.afterEvent?.originalStartDate,
    //             undefined,
    //             recur,
    //             undefined,
    //             undefined,
    //             undefined,
    //             returnValues?.afterEvent?.transparency,
    //             returnValues?.afterEvent?.visibility,
    //             undefined,
    //             undefined,
    //             undefined,
    //             undefined,
    //             undefined,
    //             undefined,
    //             'default',
    //             undefined,
    //             undefined,
    //         )

    //         returnValues.afterEvent.id = googleResValue.id
    //         returnValues.afterEvent.eventId = googleResValue.googleEventId
    //         returnValues.newEvent.postEventId = returnValues.afterEvent.id

    //     }

    //     if (returnValues?.beforeEvent) {

    //         const googleResValue: GoogleResType = await createGoogleEvent(
    //             userId,
    //             oldEvent?.calendarId,
    //             calIntegration?.clientType,
    //             returnValues?.beforeEvent?.id,
    //             returnValues?.beforeEvent?.endDate,
    //             returnValues?.beforeEvent?.startDate,
    //             0,
    //             undefined,
    //             returnValues?.beforeEvent?.sendUpdates,
    //             returnValues?.beforeEvent?.anyoneCanAddSelf,
    //             undefined,
    //             undefined,
    //             returnValues?.beforeEvent?.title,
    //             returnValues?.beforeEvent?.notes,
    //             timezone,
    //             undefined,
    //             undefined,
    //             undefined,
    //             returnValues?.beforeEvent?.guestsCanInviteOthers,
    //             returnValues?.beforeEvent?.guestsCanModify,
    //             returnValues?.beforeEvent?.guestsCanSeeOtherGuests,
    //             returnValues?.beforeEvent?.originalStartDate,
    //             undefined,
    //             recur,
    //             undefined,
    //             undefined,
    //             undefined,
    //             returnValues?.beforeEvent?.transparency,
    //             returnValues?.beforeEvent?.visibility,
    //             undefined,
    //             undefined,
    //             undefined,
    //             undefined,
    //             undefined,
    //             undefined,
    //             'default',
    //             undefined,
    //             undefined,
    //         )

    //         returnValues.beforeEvent.id = googleResValue.id
    //         returnValues.beforeEvent.eventId = googleResValue.googleEventId
    //         returnValues.newEvent.preEventId = returnValues.afterEvent.id

    //     }

    //     // insert events
    //     await upsertEvents([returnValues.newEvent, returnValues?.afterEvent, returnValues?.beforeEvent]?.filter(e => !!e))
    // } else {
    //     // insert events
    //     await upsertEvents([eventToUpsertLocal])
    // }

    // // update reminders
    // remindersToUpdateEventId?.forEach(r => ({ ...r, eventId: oldEvent?.id }))

    // // update timePreferences
    // newPreferredTimeRanges?.forEach(pt => ({ ...pt, eventId: oldEvent?.id }))

    // // insert reminders
    // if (remindersToUpdateEventId?.length > 0) {
    //     await insertReminders(remindersToUpdateEventId)
    // }

    // // insert time preferences
    // if (newPreferredTimeRanges?.length > 0) {
    //     await upsertPreferredTimeRangesForEvent(newPreferredTimeRanges)
    // }

    // // add training for time preferences and priority
    // // convert to vector for search
    // if ((newPreferredTimeRanges?.length > 0) || body?.priority > 1) {

    //     const searchVector = await convertEventTitleToOpenAIVector(body?.title)

    //     // train event
    //     await putDataInTrainEventIndexInOpenSearch(eventId, searchVector, userId)
    // }

    // // update attendees for event Id
    // await upsertAttendeesforEvent(attendees)

    // // success response
    // response.query = 'completed'

    // return response
  } catch (e) {
    console.log(e, ' unable to update meeting');
  }
};

export const processEditEventMissingFieldsReturned = async (
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

    const eventStartDate = extrapolateStartDateFromJSONData(
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

    // get default values
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
      // likely start time also present

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
    }

    // take care of any recurring dates
    let recurObject: RecurrenceRuleType | {} = {};
    if (
      dateJSONBody?.recur?.frequency ||
      messageHistoryObject?.prevDateJsonBody?.recur?.frequency
    ) {
      const recurEndDate = extrapolateStartDateFromJSONData(
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
          messageHistoryObject?.prevDateJsonBody?.recur?.frequency ||
          messageHistoryObject?.prevJsonBody?.params?.recurrence?.frequency ||
          jsonBody?.params?.recurrence?.frequency,
        interval:
          dateJSONBody?.recur?.interval ||
          messageHistoryObject?.prevDateJsonBody?.recur?.interval ||
          messageHistoryObject?.prevDateJsonBody?.recur?.frequency ||
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

    const newBody: EditEventType = {
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
      oldTitle:
        jsonBody?.params?.oldTitle ||
        messageHistoryObject?.prevJsonBody?.params?.oldTitle,
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
        messageHistoryObject?.prevJsonBody?.params?.conference?.app,
      startDate:
        jsonBody?.params?.startTime ||
        messageHistoryObject?.prevJsonBody?.params?.startTime ||
        eventStartDate,
      bufferTime:
        jsonBody?.params?.bufferTime ||
        messageHistoryObject?.prevJsonBody?.params?.bufferTime,
      reminders:
        jsonBody?.params?.alarms ||
        messageHistoryObject?.prevJsonBody?.params?.alarms ||
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
        jsonBody?.params?.visibility ||
        messageHistoryObject?.prevJsonBody?.params?.visibility,
      isFollowUp:
        jsonBody?.params?.isFollowUp ||
        messageHistoryObject?.prevJsonBody?.params?.isFollowUp,
      isBreak:
        jsonBody?.params?.isBreak ||
        messageHistoryObject?.prevJsonBody?.params?.isBreak,
      allDay:
        dateJSONBody?.allDay || messageHistoryObject?.prevDateJsonBody?.allDay,
    };

    if (
      (recurObject as RecurrenceRuleType)?.frequency as RecurrenceFrequencyType
    ) {
      newBody.recur = recurObject as any;
    }
    // validate for missing fields
    const missingFields: RequiredFieldsType = {
      required: [],
    };

    const response: any = {
      query: '',
      data: {},
      skill: 'editEvent',
    };

    const prevBody: EditEventType = {
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

    if (!prevBody?.oldTitle) {
      prevBody.oldTitle = newBody?.oldTitle;
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

    if (prevBody.isFollowUp === undefined) {
      prevBody.isFollowUp = newBody?.isFollowUp;
    }

    if (prevBody.isBreak === undefined) {
      prevBody.isBreak = newBody?.isBreak;
    }

    if (prevBody.allDay === undefined) {
      prevBody.allDay = newBody?.allDay;
    }

    if (!prevBody?.recur) {
      prevBody.recur = newBody?.recur;
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

    if (!prevBody?.startDate && !day && !isoWeekday) {
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
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    if (
      !prevBody?.startDate &&
      hour === null &&
      minute === null &&
      !startTime
    ) {
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
      response.prevJsonBody = jsonBody;
      response.prevDateJsonBody = dateJSONBody;
    }

    // get info of contacts without emails provided and assign values
    const newAttendees: MutatedCalendarExtractedJSONAttendeeType[] = [];

    for (const a of newBody?.attendees) {
      if (!a?.email) {
        const contact = await getContactByNameWithUserId(userId, a?.name);
        if (contact?.emails?.[0]?.value) {
          const primaryEmail = contact?.emails?.find((e) => !!e.primary)?.value;
          const anyEmail = contact?.emails?.[0]?.value;
          newAttendees.push({ ...a, email: primaryEmail || anyEmail });
        } else {
          response.query = 'missing_fields';
          missingFields.required.push(
            requiredFields.optional?.[7]?.['and']?.[2]
          );
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
      } else {
        newAttendees.push(a);
      }
    }

    newBody.attendees = newAttendees;

    if (!(prevBody?.attendees?.length > 0)) {
      prevBody.attendees = newBody?.attendees;
    }

    // validate remaining required fields
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

    const response2 = await finalStepEditEvent(
      prevBody,
      defaultMeetingPreferences,
      prevStartDate,
      prevEndDate,
      response
    );

    return response2;
  } catch (e) {
    console.log(e, ' unable to edit event missing fields returned');
  }
};

export const editEventControlCenter = async (
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

    let editEventRes: ResponseActionType = {
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
        editEventRes = await processEditEventPending(
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

        editEventRes = await processEditEventMissingFieldsReturned(
          userId,
          timezone,
          jsonMissingFieldsBody,
          dateMissingFieldsTime,
          userCurrentTime,
          messageHistoryObject
        );
        break;
    }

    if (editEventRes?.query === 'completed') {
      const assistantMessage =
        await generateAssistantMessageFromAPIResponseForUserQuery(
          openai,
          editEventRes.data as string,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'completed';
      messageHistoryObject.required = null;
    } else if (editEventRes?.query === 'missing_fields') {
      const assistantMessage =
        await generateAssistantMessageToRequestUserForMissingFields(
          openai,
          editEventRes?.data as RequiredFieldsType,
          messageHistoryObject
        );

      messageHistoryObject.messages.push(assistantMessage);
      messageHistoryObject.query = 'missing_fields';
      messageHistoryObject.required = editEventRes?.data as RequiredFieldsType;
      messageHistoryObject.prevData = editEventRes?.prevData;
      messageHistoryObject.prevDataExtra = editEventRes?.prevDataExtra;
      messageHistoryObject.prevDateJsonBody = editEventRes?.prevDateJsonBody;
      messageHistoryObject.prevJsonBody = editEventRes?.prevJsonBody;
    } else if (editEventRes?.query === 'event_not_found') {
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
    console.log(e, ' unable to edit event control center pending');
  }
};
