import _ from 'lodash';
import { v4 as uuid } from 'uuid';
import { RRule } from 'rrule';
import { dayjs } from '@lib/date-utils';
import { Day } from '@lib/Schedule/constants';
// dayjs.extend(utc)
// dayjs.extend(duration)
// dayjs.extend(timezone)

import { patchGoogleEvent } from '@lib/calendarLib/googleCalendarHelper';

import { CalendarType } from '@lib/dataTypes/CalendarType';
import { Time, BufferTimeType, EventType } from '@lib/dataTypes/EventType';
import { LocationType } from '@lib/dataTypes/EventType';
import {
  googleMeetName,
  googleResourceName,
  localCalendarName,
  localCalendarResource,
} from '@lib/calendarLib/constants';
import {
  GoogleAttendeeType,
  ConferenceDataType,
  GoogleReminderType,
  SendUpdatesType,
  TransparencyType,
  VisibilityType,
} from '@lib/calendarLib/types';
import { zoomName, zoomResourceName } from '@lib/zoom/constants';
import { zoomAvailable, updateZoomMeeting } from '@lib/zoom/zoomMeetingHelper';
import { Person, RecurrenceFrequencyType } from '@lib/Calendar/types';
import {
  removeAllCategoriesForEvent,
  upsertCategoryEventConnection,
} from '@lib/Category/CategoryHelper';
import {
  removeRemindersForEvent,
  updateRemindersForEvent,
} from '@lib/Calendar/Reminder/ReminderHelper';
import {
  deleteAttendeesForEvent,
  upsertAttendeesInDb,
} from '@lib/Calendar/Attendee/AttendeeHelper';

import {
  createConference,
  getCalendarInDb,
  getRruleFreq,
  meetingTypeStringType,
  upsertConferenceInDb,
  atomicUpsertEventInDb,
  upsertLocalCalendar,
  getRRuleDay,
} from '@lib/Calendar/UserCreateCalendarHelper';

import { palette } from '@lib/theme/theme';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
import getEventById from '@lib/apollo/gql/getEventById';
import getCalendarIntegrationByResourceAndName from '@lib/apollo/gql/getCalendarIntegrationByResourceAndName';
import { CalendarIntegrationType } from '@lib/dataTypes/Calendar_IntegrationType';

export const updateEventInGoogle = async (
  id: string,
  startDate: string,
  endDate: string,
  userId: string,
  client: ApolloClient<NormalizedCacheObject>,
  calendar: CalendarType,
  conferenceData?: ConferenceDataType,
  attendees?: GoogleAttendeeType[],
  title?: string,
  allDay?: boolean,
  recurringEndDate?: string,
  frequency?: RecurrenceFrequencyType,
  interval?: number,
  notes?: string,
  location?: LocationType,
  isFollowUp?: boolean,
  isPreEvent?: boolean,
  isPostEvent?: boolean,
  modifiable?: boolean,
  anyoneCanAddSelf?: boolean,
  guestsCanInviteOthers?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalAllDay?: boolean,
  alarms?: string[] | number[],
  timezone?: string,
  taskId?: string,
  taskType?: string,
  followUpEventId?: string,
  preEventId?: string,
  postEventId?: string,
  forEventId?: string,
  maxAttendees?: number,
  sendUpdates?: SendUpdatesType,
  status?: string,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  iCalUID?: string,
  backgroundColor?: string,
  foregroundColor?: string,
  colorId?: string,
  originalTimezone?: string,
  useDefaultAlarms?: boolean,
  positiveImpactScore?: number,
  negativeImpactScore?: number,
  positiveImpactDayOfWeek?: number,
  positiveImpactTime?: Time,
  negativeImpactDayOfWeek?: number,
  negativeImpactTime?: Time,
  preferredDayOfWeek?: number,
  preferredTime?: Time,
  isExternalMeeting?: boolean,
  isExternalMeetingModifiable?: boolean,
  isMeetingModifiable?: boolean,
  isMeeting?: boolean,
  dailyTaskList?: boolean,
  weeklyTaskList?: boolean,
  isBreak?: boolean,
  preferredStartTimeRange?: Time,
  preferredEndTimeRange?: Time,
  copyAvailability?: boolean,
  copyTimeBlocking?: boolean,
  copyTimePreference?: boolean,
  copyReminders?: boolean,
  copyPriorityLevel?: boolean,
  copyModifiable?: boolean,
  copyCategories?: boolean,
  copyIsBreak?: boolean,
  timeBlocking?: BufferTimeType,
  userModifiedAvailability?: boolean,
  userModifiedTimeBlocking?: boolean,
  userModifiedTimePreference?: boolean,
  userModifiedReminders?: boolean,
  userModifiedPriorityLevel?: boolean,
  userModifiedCategories?: boolean,
  userModifiedModifiable?: boolean,
  userModifiedIsBreak?: boolean,
  hardDeadline?: string,
  softDeadline?: string,
  copyIsMeeting?: boolean,
  copyIsExternalMeeting?: boolean,
  userModifiedIsMeeting?: boolean,
  userModifiedIsExternalMeeting?: boolean,
  duration?: number,
  copyDuration?: boolean,
  userModifiedDuration?: boolean,
  method?: 'create' | 'update',
  unlink?: boolean,
  byWeekDay?: Day[],
  priority?: number
) => {
  try {
    console.log(alarms, ' alarms inside updateEventInGoogle');
    console.log(
      hardDeadline,
      softDeadline,
      ' hardDeadline, softDeadline inside updateEventInGoogle'
    );
    // validate eventId
    const oldEvent = (
      await client.query<{ Event_by_pk: EventType }>({
        query: getEventById,
        variables: {
          id: id,
        },
      })
    ).data?.Event_by_pk;

    if (!oldEvent) {
      throw new Error('Event not found');
    }

    let rule: any = {};

    if (recurringEndDate && frequency) {
      rule = new RRule({
        freq: getRruleFreq(frequency),
        interval,
        until: dayjs(recurringEndDate).toDate(),
        byweekday: byWeekDay?.map((i) => getRRuleDay(i)),
      });
    }

    let modifiedAlarms: GoogleReminderType | {} = {};

    if (typeof alarms?.[0] === 'string') {
      modifiedAlarms = {
        useDefault: false,
        overrides: alarms.map((i) => ({
          method: 'email',
          minutes: dayjs.duration(dayjs(startDate).diff(dayjs(i))).asMinutes(),
        })),
      };
    } else if (typeof alarms?.[0] === 'number') {
      modifiedAlarms = {
        useDefault: false,
        overrides: alarms.map((i) => ({ method: 'email', minutes: i })),
      };
    } else if (useDefaultAlarms) {
      modifiedAlarms = { useDefault: useDefaultAlarms };
    } else {
      // default
      modifiedAlarms = { useDefault: useDefaultAlarms };
    }

    const recurrenceStringArray = frequency &&
      recurringEndDate &&
      interval && [rule.toString()];

    console.log(recurrenceStringArray, ' recurrenceStringArray');
    console.log([rule.toString()], ' [rule.toString()]');

    await patchGoogleEvent(
      client,
      userId,
      calendar?.id,
      id.split('#')[0],
      endDate,
      startDate,
      undefined,
      maxAttendees,
      sendUpdates,
      anyoneCanAddSelf,
      attendees,
      conferenceData,
      title,
      notes,
      timezone,
      allDay && dayjs(startDate).format('YYYY-MM-DD'),
      allDay && (endDate || startDate),
      undefined,
      guestsCanInviteOthers,
      false,
      guestsCanSeeOtherGuests,
      undefined,
      undefined,
      frequency && recurringEndDate && interval ? [rule.toString()] : undefined,
      (modifiedAlarms as GoogleReminderType)?.overrides?.[0]
        ? (modifiedAlarms as GoogleReminderType)
        : null,
      undefined,
      status,
      transparency,
      visibility,
      iCalUID,
      false,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      location?.title
    );

    console.log(
      recurringEndDate && frequency && id,
      ' (recurringEndDate && frequency && eventId)'
    );

    await atomicUpsertEventInDb(
      client,
      id,
      id.split('#')[0],
      userId,
      dayjs(startDate).format(),
      dayjs(endDate).format(),
      dayjs().toISOString(),
      false,
      priority || 1,
      isFollowUp ?? false,
      isPreEvent ?? false,
      isPostEvent ?? false,
      modifiable ?? true,
      anyoneCanAddSelf ?? false,
      guestsCanInviteOthers ?? false,
      guestsCanSeeOtherGuests ?? true,
      dayjs(startDate).format(),
      originalAllDay ?? false,
      dayjs().toISOString(),
      calendar?.id,
      title,
      allDay ?? false,
      (frequency &&
        recurringEndDate &&
        interval && { frequency, endDate: recurringEndDate, interval }) ??
        null,
      location,
      notes,
      undefined,
      undefined,
      // modifiedAlarms,
      timezone ?? dayjs.tz.guess(),
      taskId,
      taskType,
      followUpEventId,
      preEventId,
      postEventId,
      forEventId,
      conferenceData?.conferenceId,
      maxAttendees,
      sendUpdates,
      status,
      title,
      transparency,
      visibility,
      recurringEndDate && frequency && id,
      iCalUID,
      undefined,
      colorId,
      undefined, // creator - read only G-event
      undefined, // organizer - G-event import only
      false, // endTimeUnspecified - only for G-events
      (frequency && recurringEndDate && interval && [rule.toString()]) ?? null,
      originalTimezone, //timezone of recurrence instance
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      backgroundColor,
      foregroundColor,
      useDefaultAlarms,
      positiveImpactScore,
      negativeImpactScore,
      positiveImpactDayOfWeek,
      positiveImpactTime,
      negativeImpactDayOfWeek,
      negativeImpactTime,
      preferredDayOfWeek,
      preferredTime,
      isExternalMeeting,
      isExternalMeetingModifiable,
      isMeetingModifiable,
      isMeeting,
      dailyTaskList,
      weeklyTaskList,
      isBreak,
      preferredStartTimeRange,
      preferredEndTimeRange,
      copyAvailability,
      copyTimeBlocking,
      copyTimePreference,
      copyReminders,
      copyPriorityLevel,
      copyModifiable,
      copyCategories,
      copyIsBreak,
      timeBlocking,
      userModifiedAvailability,
      userModifiedTimeBlocking,
      userModifiedTimePreference,
      userModifiedReminders,
      userModifiedPriorityLevel,
      userModifiedCategories,
      userModifiedModifiable,
      userModifiedIsBreak,
      hardDeadline,
      softDeadline,
      copyIsMeeting,
      copyIsExternalMeeting,
      userModifiedIsMeeting,
      userModifiedIsExternalMeeting,
      duration,
      copyDuration,
      userModifiedDuration,
      method,
      unlink,
      byWeekDay
    );

    if (alarms?.length > 0) {
      console.log(
        alarms,
        ' alarms inside if clause inside updateEventInGoogle'
      );
      await updateRemindersForEvent(
        client,
        id,
        userId,
        alarms,
        timezone,
        useDefaultAlarms
      );
    } else {
      await removeRemindersForEvent(client, id);
    }
  } catch (e) {
    console.log(e, ' this is e for updateEventInGoogle');
  }
};

export type conferenceName = typeof zoomName | typeof googleMeetName;
export type conferenceType = 'hangoutsMeet' | 'addOn';

export const updateConference = async (
  conferenceId: string,
  startDate: string,
  endDate: string,
  client: ApolloClient<NormalizedCacheObject>,
  calendarId: string,
  zoomMeet: boolean = false,
  googleMeet: boolean = false,
  userId: string,
  meetingTypeString: meetingTypeStringType,
  attendees: GoogleAttendeeType[],
  requestId?: string,
  summary?: string,
  taskType?: string,
  notes?: string,
  zoomPassword?: string,
  zoomPrivateMeeting?: boolean
) => {
  try {
    // validate
    if (!startDate || !endDate) {
      throw new Error('startDate and endDate are required');
    }
    if (!conferenceId) {
      throw new Error('conferenceId is required');
    }
    if (!calendarId) {
      throw new Error('calendarId is required');
    }

    if (!userId) {
      throw new Error('userId is required');
    }

    let newJoinUrl = '';
    let newStartUrl = '';
    let newConferenceStatus = '';
    let newConferenceId: string | number = conferenceId;
    let conferenceName: conferenceName = zoomName;
    let conferenceType: conferenceType = 'addOn';
    let conferenceData: ConferenceDataType = {
      type: 'addOn',
      name: conferenceName,
      requestId: uuid(),
      conferenceId,
      createRequest: false,
      entryPoints: [
        {
          label: zoomName,
          entryPointType: 'video',
          uri: newJoinUrl,
          password: zoomPassword,
        },
      ],
    };
    let newRequestId = requestId || uuid();
    if (zoomMeet) {
      const isZoomAvailable = await zoomAvailable(client, userId);

      if (isZoomAvailable) {
        const zoomInteg = (
          await client.query<{
            Calendar_Integration: CalendarIntegrationType[];
          }>({
            query: getCalendarIntegrationByResourceAndName,
            variables: {
              userId,
              name: zoomName,
              resource: zoomResourceName,
            },
          })
        ).data?.Calendar_Integration?.[0];
        const {
          id: zoomConferenceId,
          join_url: zoomJoinUrl,
          start_url: zoomStartUrl,
          status: zoomStatus,
        } = await updateZoomMeeting(
          userId,
          parseInt(newConferenceId, 10),
          dayjs(startDate).format(),
          dayjs.tz.guess(),
          summary ?? taskType ?? notes,
          dayjs
            .duration({
              hours: dayjs(endDate).hour(),
              minutes: dayjs(endDate).minute(),
            })
            .asMinutes(),
          zoomInteg?.contactName,
          zoomInteg?.contactEmail,
          attendees?.map((i) => i?.email),
          zoomPrivateMeeting
        );
        newConferenceId = zoomConferenceId;
        newJoinUrl = zoomJoinUrl;
        newStartUrl = zoomStartUrl;
        newConferenceStatus = zoomStatus;
        conferenceName = zoomName;
        conferenceType = 'addOn';
        conferenceData = {
          type: conferenceType,
          name: conferenceName,
          requestId: newRequestId,
          conferenceId: `${newConferenceId}`,
          createRequest: false,
          entryPoints: [
            {
              label: zoomName,
              entryPointType: 'video',
              uri: newJoinUrl,
              password: zoomPassword,
            },
          ],
        };
      }
    } else if (googleMeet) {
      conferenceName = googleMeetName;
      conferenceType = 'hangoutsMeet';
      conferenceData = {
        type: conferenceType,
        name: conferenceName,
        requestId: newRequestId,
        createRequest: true,
      };
    }

    await upsertConferenceInDb(
      client,
      typeof newConferenceId === 'number'
        ? `${newConferenceId}`
        : newConferenceId,
      userId,
      calendarId,
      zoomMeet ? zoomResourceName : googleResourceName,
      newRequestId,
      meetingTypeString,
      undefined,
      undefined,
      zoomMeet ? zoomName : googleMeetName,
      notes,
      conferenceData?.entryPoints,
      undefined,
      undefined,
      undefined,
      newJoinUrl,
      newStartUrl,
      zoomPrivateMeeting
    );

    return {
      newConferenceId,
      newJoinUrl,
      newStartUrl,
      newConferenceStatus,
      conferenceName,
      conferenceType,
      conferenceData,
    };
  } catch (e) {
    console.log(e, ' this is e for updateConference');
  }
};

export const updateEvent = async (
  id: string,
  startDate: string,
  endDate: string,
  userId: string,
  client: ApolloClient<NormalizedCacheObject>,
  selectedCalendarId: string,
  categoryIds?: string[],
  title?: string,
  allDay?: boolean,
  recurringEndDate?: string,
  frequency?: RecurrenceFrequencyType,
  interval?: number,
  alarms?: string[] | number[],
  notes?: string,
  location?: LocationType,
  isFollowUp?: boolean,
  isPreEvent?: boolean,
  isPostEvent?: boolean,
  modifiable?: boolean,
  anyoneCanAddSelf?: boolean,
  guestsCanInviteOthers?: boolean,
  guestsCanSeeOtherGuests?: boolean,
  originalAllDay?: boolean,
  timezone?: string,
  taskId?: string,
  taskType?: string,
  followUpEventId?: string,
  preEventId?: string,
  postEventId?: string,
  forEventId?: string,
  zoomMeet?: boolean,
  googleMeet?: boolean,
  meetingTypeString?: meetingTypeStringType,
  zoomPassword?: string,
  zoomPrivateMeeting?: boolean,
  attendees?: Person[],
  conferenceId?: string,
  maxAttendees?: number,
  sendUpdates?: SendUpdatesType,
  status?: string,
  summary?: string,
  transparency?: TransparencyType,
  visibility?: VisibilityType,
  recurringEventId?: string,
  iCalUID?: string,
  htmlLink?: string,
  colorId?: string,
  originalTimezone?: string,
  backgroundColor?: string,
  foregroundColor?: string,
  useDefaultAlarms?: boolean,
  positiveImpactScore?: number,
  negativeImpactScore?: number,
  positiveImpactDayOfWeek?: number,
  positiveImpactTime?: Time,
  negativeImpactDayOfWeek?: number,
  negativeImpactTime?: Time,
  preferredDayOfWeek?: number,
  preferredTime?: Time,
  isExternalMeeting?: boolean,
  isExternalMeetingModifiable?: boolean,
  isMeetingModifiable?: boolean,
  isMeeting?: boolean,
  dailyTaskList?: boolean,
  weeklyTaskList?: boolean,
  isBreak?: boolean,
  preferredStartTimeRange?: Time,
  preferredEndTimeRange?: Time,
  copyAvailability?: boolean,
  copyTimeBlocking?: boolean,
  copyTimePreference?: boolean,
  copyReminders?: boolean,
  copyPriorityLevel?: boolean,
  copyModifiable?: boolean,
  copyCategories?: boolean,
  copyIsBreak?: boolean,
  timeBlocking?: BufferTimeType,
  userModifiedAvailability?: boolean,
  userModifiedTimeBlocking?: boolean,
  userModifiedTimePreference?: boolean,
  userModifiedReminders?: boolean,
  userModifiedPriorityLevel?: boolean,
  userModifiedCategories?: boolean,
  userModifiedModifiable?: boolean,
  userModifiedIsBreak?: boolean,
  hardDeadline?: string,
  softDeadline?: string,
  copyIsMeeting?: boolean,
  copyIsExternalMeeting?: boolean,
  userModifiedIsMeeting?: boolean,
  userModifiedIsExternalMeeting?: boolean,
  duration?: number,
  copyDuration?: boolean,
  userModifiedDuration?: boolean,
  method?: 'create' | 'update',
  unlink?: boolean,
  byWeekDay?: Day[],
  priority?: number
) => {
  try {
    console.log(alarms, ' alarms inside updateEvent');
    console.log(categoryIds, ' categoryIds inside updateEvent');
    console.log(
      hardDeadline,
      softDeadline,
      ' hardDeadline, softDeadline inside updateEvent'
    );
    let calendar: CalendarType | {} = {};

    if (selectedCalendarId?.length > 0) {
      calendar = await getCalendarInDb(client, userId, selectedCalendarId);
    }

    // validate eventId and selectedCalendarId
    if (id.length === 0) {
      throw new Error('id is required');
    }

    if (selectedCalendarId.length === 0) {
      throw new Error('selectedCalendarId is required');
    }

    if ((calendar as CalendarType)?.resource === googleResourceName) {
      const modifiedAttendees: GoogleAttendeeType[] = attendees?.map((a) => ({
        additionalGuests: a?.additionalGuests,
        displayName: a?.name,
        email: a?.emails?.[0]?.value,
        id: a?.id,
      }));
      if (conferenceId) {
        // create conferece
        const {
          // newConferenceId,
          // newJoinUrl,
          // newStartUrl,
          // newConferenceStatus,
          // conferenceName,
          // conferenceType,
          conferenceData,
        } = await updateConference(
          conferenceId,
          startDate,
          endDate,
          client,
          (calendar as CalendarType)?.id,
          zoomMeet,
          googleMeet,
          userId,
          meetingTypeString,
          modifiedAttendees,
          undefined,
          summary,
          taskType,
          notes,
          zoomPassword,
          zoomPrivateMeeting
        );

        await updateEventInGoogle(
          id,
          startDate,
          endDate,
          userId,
          client,
          calendar as CalendarType,
          conferenceData, // isConference
          modifiedAttendees,
          title,
          allDay,
          recurringEndDate,
          frequency,
          interval,
          notes,
          location,
          isFollowUp,
          isPreEvent,
          isPostEvent,
          modifiable,
          anyoneCanAddSelf,
          guestsCanInviteOthers,
          guestsCanSeeOtherGuests,
          originalAllDay,
          alarms,
          timezone,
          taskId,
          taskType,
          followUpEventId,
          preEventId,
          postEventId,
          forEventId,
          maxAttendees,
          sendUpdates,
          status,
          transparency,
          visibility,
          iCalUID,
          backgroundColor,
          foregroundColor,
          colorId,
          originalTimezone,
          useDefaultAlarms,
          positiveImpactScore,
          negativeImpactScore,
          positiveImpactDayOfWeek,
          positiveImpactTime,
          negativeImpactDayOfWeek,
          negativeImpactTime,
          preferredDayOfWeek,
          preferredTime,
          isExternalMeeting,
          isExternalMeetingModifiable,
          isMeetingModifiable,
          isMeeting,
          dailyTaskList,
          weeklyTaskList,
          isBreak,
          preferredStartTimeRange,
          preferredEndTimeRange,
          copyAvailability,
          copyTimeBlocking,
          copyTimePreference,
          copyReminders,
          copyPriorityLevel,
          copyModifiable,
          copyCategories,
          copyIsBreak,
          timeBlocking,
          userModifiedAvailability,
          userModifiedTimeBlocking,
          userModifiedTimePreference,
          userModifiedReminders,
          userModifiedPriorityLevel,
          userModifiedCategories,
          userModifiedModifiable,
          userModifiedIsBreak,
          hardDeadline,
          softDeadline,
          copyIsMeeting,
          copyIsExternalMeeting,
          userModifiedIsMeeting,
          userModifiedIsExternalMeeting,
          duration,
          copyDuration,
          userModifiedDuration,
          method,
          unlink,
          byWeekDay,
          priority
        );
      } else {
        if (googleMeet || zoomMeet) {
          const {
            // newConferenceId,
            // newJoinUrl,
            // newStartUrl,
            // newConferenceStatus,
            // conferenceName,
            // conferenceType,
            conferenceData,
          } = await createConference(
            startDate,
            endDate,
            client,
            (calendar as CalendarType)?.id,
            zoomMeet,
            googleMeet,
            userId,
            meetingTypeString,
            modifiedAttendees,
            undefined,
            summary,
            taskType,
            notes,
            zoomPassword,
            zoomPrivateMeeting
          );

          await updateEventInGoogle(
            id,
            startDate,
            endDate,
            userId,
            client,
            calendar as CalendarType,
            conferenceData, // isConference
            modifiedAttendees,
            title,
            allDay,
            recurringEndDate,
            frequency,
            interval,
            notes,
            location,
            isFollowUp,
            isPreEvent,
            isPostEvent,
            modifiable,
            anyoneCanAddSelf,
            guestsCanInviteOthers,
            guestsCanSeeOtherGuests,
            originalAllDay,
            alarms,
            timezone,
            taskId,
            taskType,
            followUpEventId,
            preEventId,
            postEventId,
            forEventId,
            maxAttendees,
            sendUpdates,
            status,
            transparency,
            visibility,
            iCalUID,
            backgroundColor,
            foregroundColor,
            colorId,
            originalTimezone,
            useDefaultAlarms,
            positiveImpactScore,
            negativeImpactScore,
            positiveImpactDayOfWeek,
            positiveImpactTime,
            negativeImpactDayOfWeek,
            negativeImpactTime,
            preferredDayOfWeek,
            preferredTime,
            isExternalMeeting,
            isExternalMeetingModifiable,
            isMeetingModifiable,
            isMeeting,
            dailyTaskList,
            weeklyTaskList,
            isBreak,
            preferredStartTimeRange,
            preferredEndTimeRange,
            copyAvailability,
            copyTimeBlocking,
            copyTimePreference,
            copyReminders,
            copyPriorityLevel,
            copyModifiable,
            copyCategories,
            copyIsBreak,
            timeBlocking,
            userModifiedAvailability,
            userModifiedTimeBlocking,
            userModifiedTimePreference,
            userModifiedReminders,
            userModifiedPriorityLevel,
            userModifiedCategories,
            userModifiedModifiable,
            userModifiedIsBreak,
            hardDeadline,
            softDeadline,
            copyIsMeeting,
            copyIsExternalMeeting,
            userModifiedIsMeeting,
            userModifiedIsExternalMeeting,
            duration,
            copyDuration,
            userModifiedDuration,
            method,
            unlink,
            byWeekDay,
            priority
          );
        } else {
          await updateEventInGoogle(
            id,
            startDate,
            endDate,
            userId,
            client,
            calendar as CalendarType,
            undefined, // isConference
            modifiedAttendees,
            title,
            allDay,
            recurringEndDate,
            frequency,
            interval,
            notes,
            location,
            isFollowUp,
            isPreEvent,
            isPostEvent,
            modifiable,
            anyoneCanAddSelf,
            guestsCanInviteOthers,
            guestsCanSeeOtherGuests,
            originalAllDay,
            alarms,
            timezone,
            taskId,
            taskType,
            followUpEventId,
            preEventId,
            postEventId,
            forEventId,
            maxAttendees,
            sendUpdates,
            status,
            transparency,
            visibility,
            iCalUID,
            backgroundColor,
            foregroundColor,
            colorId,
            originalTimezone,
            useDefaultAlarms,
            positiveImpactScore,
            negativeImpactScore,
            positiveImpactDayOfWeek,
            positiveImpactTime,
            negativeImpactDayOfWeek,
            negativeImpactTime,
            preferredDayOfWeek,
            preferredTime,
            isExternalMeeting,
            isExternalMeetingModifiable,
            isMeetingModifiable,
            isMeeting,
            dailyTaskList,
            weeklyTaskList,
            isBreak,
            preferredStartTimeRange,
            preferredEndTimeRange,
            copyAvailability,
            copyTimeBlocking,
            copyTimePreference,
            copyReminders,
            copyPriorityLevel,
            copyModifiable,
            copyCategories,
            copyIsBreak,
            timeBlocking,
            userModifiedAvailability,
            userModifiedTimeBlocking,
            userModifiedTimePreference,
            userModifiedReminders,
            userModifiedPriorityLevel,
            userModifiedCategories,
            userModifiedModifiable,
            userModifiedIsBreak,
            hardDeadline,
            softDeadline,
            copyIsMeeting,
            copyIsExternalMeeting,
            userModifiedIsMeeting,
            userModifiedIsExternalMeeting,
            duration,
            copyDuration,
            userModifiedDuration,
            method,
            unlink,
            byWeekDay,
            priority
          );
        }
      }

      if (attendees?.length > 0) {
        await deleteAttendeesForEvent(client, id);
        // create new attendees
        const attendeePromises = attendees.map((a) => {
          return upsertAttendeesInDb(
            client,
            uuid(),
            userId,
            id,
            a?.emails,
            a?.name,
            a?.id,
            a?.phoneNumbers,
            a?.imAddresses,
            a?.additionalGuests,
            a?.optional,
            a?.resource
          );
        });

        await Promise.all(attendeePromises);
      }
    }

    if (categoryIds?.length > 0) {
      console.log(categoryIds, ' categoryIds after if if inside updateEvent');
      // remove old category connections
      await removeAllCategoriesForEvent(client, id);

      // create category_event connections
      const categoryPromises = categoryIds?.map((i) =>
        upsertCategoryEventConnection(client, userId, i, id)
      );

      await Promise.all(categoryPromises);
    } else {
      // remove old category connections
      await removeAllCategoriesForEvent(client, id);
    }
  } catch (e) {
    console.log(e, ' this is e for updateEvent');
  }
};
