import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import {
  optaPlanWeekly,
  getUserPreferences,
  convertMeetingPlusTypeToEventPlusType,
  formatEventTypeToPlannerEvent,
  generateBreakEventsForDate,
  generateEventPartsLite,
  generateTimeSlotsLiteForInternalAttendee,
  generateUserPlannerRequestBody,
  generateWorkTimesForInternalAttendee,
  getGlobalCalendar,
  modifyEventPartsForMultiplePostBufferTime,
  modifyEventPartsForMultiplePreBufferTime,
  processEventsForOptaPlannerForExternalAttendees,
  setPreferredTimeForUnModifiableEvent,
  tagEventsForDailyOrWeeklyTask,
  validateEventDates,
} from '@features_apply/_libs/api-helper';
import {
  bucketName,
  onOptaPlanCalendarAdminCallBackUrl,
  optaplannerDuration,
} from '@features_apply/_libs/constants';
import { dayjs } from '@features_apply/_libs/date-utils';
import {
  MeetingAssistAttendeeType,
  EventMeetingPlusType,
  EventPlusType,
  MeetingAssistEventType,
  RemindersForEventType,
  BufferTimeObjectType,
  ReturnBodyForAttendeeForOptaplannerPrepType,
  ReturnBodyForHostForOptaplannerPrepType,
  ReturnBodyForExternalAttendeeForOptaplannerPrepType,
  EventPartPlannerRequestBodyType,
  TimeSlotType,
  UserPlannerRequestBodyType,
  CalendarType,
  UserPreferenceType,
  WorkTimeType,
} from '@features_apply/_libs/types';

import _ from 'lodash';
import { v4 as uuid } from 'uuid';

const s3Client = new S3Client({
  credentials: {
    accessKeyId: process.env.S3_ACCESS_KEY,
    secretAccessKey: process.env.S3_SECRET_KEY,
  },
  endpoint: process.env.S3_ENDPOINT,
  forcePathStyle: true,
});

export const processEventsForOptaPlannerForMainHost = async (
  mainHostId: string,
  allHostEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  oldHostEvents: EventPlusType[],
  newHostBufferTimes?: BufferTimeObjectType[]
): Promise<ReturnBodyForHostForOptaplannerPrepType> => {
  try {
    const newBufferTimeArray: EventPlusType[] = [];

    for (const newHostBufferTime of newHostBufferTimes) {
      if (newHostBufferTime?.beforeEvent?.id) {
        console.log(
          newHostBufferTime?.beforeEvent,
          ' newTimeBlocking?.beforeEvent'
        );
        newBufferTimeArray.push(newHostBufferTime.beforeEvent);
      }

      if (newHostBufferTime?.afterEvent?.id) {
        console.log(
          newHostBufferTime?.afterEvent,
          ' newTimeBlocking?.afterEvent'
        );
        newBufferTimeArray.push(newHostBufferTime.afterEvent);
      }
    }

    const modifiedAllHostEvents = _.cloneDeep(allHostEvents);

    if (newBufferTimeArray?.length > 0) {
      modifiedAllHostEvents.push(...newBufferTimeArray);
    }

    const userPreferences = await getUserPreferences(mainHostId);

    const globalPrimaryCalendar = await getGlobalCalendar(mainHostId);

    const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(
      dayjs(windowStartDate.slice(0, 19)),
      'day'
    );

    const modifiedAllEventsWithBreaks: EventPlusType[] = [];

    const startDatesForEachDay = [];

    for (let i = 0; i <= diffDays; i++) {
      startDatesForEachDay.push(
        dayjs(windowStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .add(i, 'day')
          .format()
      );
    }

    let parentBreaks: EventPlusType[] = [];

    const breaks = await generateBreakEventsForDate(
      userPreferences,
      mainHostId,
      windowStartDate,
      windowEndDate,
      hostTimezone,
      globalPrimaryCalendar?.id
    );

    breaks.forEach((b) => console.log(b, ' generatedBreaks'));

    if (breaks?.length > 0) {
      const allEventsWithDuplicateFreeBreaks = _.differenceBy(
        modifiedAllHostEvents,
        breaks,
        'id'
      );
      modifiedAllEventsWithBreaks.push(...allEventsWithDuplicateFreeBreaks);
      modifiedAllEventsWithBreaks.push(...breaks);
      parentBreaks.push(...breaks);
    } else {
      modifiedAllEventsWithBreaks.push(...modifiedAllHostEvents);
    }

    const workTimes = generateWorkTimesForInternalAttendee(
      mainHostId,
      mainHostId,
      userPreferences,
      hostTimezone,
      hostTimezone
    );
    const timeslots = [];

    for (let i = 0; i < startDatesForEachDay.length; i++) {
      if (i === 0) {
        const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(
          startDatesForEachDay?.[i],
          mainHostId,
          userPreferences,
          hostTimezone,
          hostTimezone,
          true
        );
        timeslots.push(...timeslotsForDay);
        continue;
      }
      const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(
        startDatesForEachDay?.[i],
        mainHostId,
        userPreferences,
        hostTimezone,
        hostTimezone,
        false
      );
      timeslots.push(...timeslotsForDay);
    }
    console.log(timeslots, ' timeslots');

    const filteredAllEvents = _.uniqBy(
      modifiedAllEventsWithBreaks.filter((e) =>
        validateEventDates(e, userPreferences)
      ),
      'id'
    );
    let eventParts: EventPartPlannerRequestBodyType[] = [];

    const eventPartMinisAccumulated = [];
    for (const event of filteredAllEvents) {
      const eventPartMinis = generateEventPartsLite(event, mainHostId);
      eventPartMinisAccumulated.push(...eventPartMinis);
    }

    const modifiedEventPartMinisPreBuffer =
      modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
    const modifiedEventPartMinisPreAndPostBuffer =
      modifyEventPartsForMultiplePostBufferTime(
        modifiedEventPartMinisPreBuffer
      );
    const formattedEventParts: EventPartPlannerRequestBodyType[] =
      modifiedEventPartMinisPreAndPostBuffer.map((e) =>
        formatEventTypeToPlannerEvent(
          e,
          userPreferences,
          workTimes,
          hostTimezone
        )
      );
    if (formattedEventParts?.length > 0) {
      eventParts.push(...formattedEventParts);
    }

    if (eventParts?.length > 0) {
      eventParts.forEach((e) => console.log(e, ' eventParts after formatting'));
      const newEventPartsWithPreferredTimeSet = eventParts.map((e) =>
        setPreferredTimeForUnModifiableEvent(
          e,
          allHostEvents.find((f) => f.id === e.eventId)?.timezone
        )
      );
      newEventPartsWithPreferredTimeSet.forEach((e) =>
        console.log(e, ' newEventPartsWithPreferredTimeSet')
      );
      const newEventParts = await tagEventsForDailyOrWeeklyTask(
        newEventPartsWithPreferredTimeSet
      );
      newEventParts.forEach((e) =>
        console.log(e, ' newEventParts after tagEventsForDailyOrWeeklyTask')
      );
      const userPlannerRequestBody = generateUserPlannerRequestBody(
        userPreferences,
        userPreferences.userId,
        workTimes,
        mainHostId
      );
      console.log(userPlannerRequestBody, ' userPlannerRequestBody');

      const modifiedNewEventParts: EventPartPlannerRequestBodyType[] =
        newEventParts.map((eventPart) => {
          const oldEvent = filteredAllEvents.find(
            (event) => event.id === eventPart.eventId
          );
          return {
            groupId: eventPart?.groupId,
            eventId: eventPart?.eventId,
            part: eventPart?.part,
            lastPart: eventPart?.lastPart,
            meetingPart: eventPart?.meetingPart,
            meetingLastPart: eventPart?.meetingLastPart,
            meetingId: eventPart?.meetingId,
            hostId: mainHostId,
            startDate: dayjs(eventPart?.startDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .format(),
            endDate: dayjs(eventPart?.endDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .format(),
            userId: eventPart?.userId,
            user: eventPart?.user,
            priority: eventPart?.priority,
            isPreEvent: eventPart?.isPreEvent,
            isPostEvent: eventPart?.isPostEvent,
            positiveImpactScore: eventPart?.positiveImpactScore,
            negativeImpactScore: eventPart?.negativeImpactScore,
            modifiable: eventPart?.modifiable,
            isMeeting: eventPart?.isMeeting,
            isExternalMeeting: eventPart?.isExternalMeeting,
            isExternalMeetingModifiable: eventPart?.isExternalMeetingModifiable,
            isMeetingModifiable: eventPart?.isMeetingModifiable,
            dailyTaskList: eventPart?.dailyTaskList,
            weeklyTaskList: eventPart?.weeklyTaskList,
            gap: eventPart?.gap,
            totalWorkingHours: eventPart?.totalWorkingHours,
            hardDeadline: eventPart?.hardDeadline,
            softDeadline: eventPart?.softDeadline,
            forEventId: eventPart?.forEventId,
            positiveImpactDayOfWeek: eventPart?.positiveImpactDayOfWeek,
            positiveImpactTime: eventPart?.positiveImpactTime,
            negativeImpactDayOfWeek: eventPart?.negativeImpactDayOfWeek,
            negativeImpactTime: eventPart?.negativeImpactTime,
            preferredDayOfWeek: eventPart?.preferredDayOfWeek,
            preferredTime: eventPart?.preferredTime,
            preferredStartTimeRange: eventPart?.preferredStartTimeRange,
            preferredEndTimeRange: eventPart?.preferredEndTimeRange,
            event: eventPart?.event,
          };
        });

      return modifiedNewEventParts?.length > 0
        ? {
            userId: mainHostId,
            hostId: mainHostId,
            eventParts: modifiedNewEventParts,
            allEvents: filteredAllEvents,
            breaks: parentBreaks,
            oldEvents: oldHostEvents,
            timeslots,
            userPlannerRequestBody,
          }
        : null;
    }
  } catch (e) {
    console.log(
      e,
      ' unable to process events for optaplanner for host attendee'
    );
  }
};

export const processEventsForOptaPlannerForInternalAttendees = async (
  mainHostId: string,
  allEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  internalAttendees: MeetingAssistAttendeeType[],
  oldEvents: EventPlusType[],
  oldMeetingEvents?: EventMeetingPlusType[],
  newMeetingEvents?: EventMeetingPlusType[],
  newHostBufferTimes?: BufferTimeObjectType[]
): Promise<ReturnBodyForAttendeeForOptaplannerPrepType> => {
  try {
    const newBufferTimeArray: EventPlusType[] = [];

    for (const newHostBufferTime of newHostBufferTimes) {
      if (newHostBufferTime?.beforeEvent?.id) {
        console.log(
          newHostBufferTime?.beforeEvent,
          ' newTimeBlocking?.beforeEvent'
        );
        newBufferTimeArray.push(newHostBufferTime.beforeEvent);
      }

      if (newHostBufferTime?.afterEvent?.id) {
        console.log(
          newHostBufferTime?.afterEvent,
          ' newTimeBlocking?.afterEvent'
        );
        newBufferTimeArray.push(newHostBufferTime.afterEvent);
      }
    }

    oldMeetingEvents?.forEach((o) => console.log(o, ' oldMeetingEvents'));
    internalAttendees?.forEach((i) =>
      console.log(
        i,
        ' internalAttendees inside processEventsForOptaPlannerForInternalAttendees'
      )
    );
    const filteredOldMeetingEvents = oldMeetingEvents
      ?.map((m) => {
        const foundIndex = allEvents?.findIndex((a) => a?.id === m?.id);

        if (foundIndex > -1) {
          return null;
        }
        return m;
      })
      ?.filter((e) => !!e);

    filteredOldMeetingEvents?.forEach((e) =>
      console.log(e, ' filteredOldMeetingEvents')
    );
    const modifiedAllEvents = _.cloneDeep(allEvents)?.filter((e) => {
      if (filteredOldMeetingEvents?.[0]?.id) {
        const foundIndex = filteredOldMeetingEvents?.findIndex(
          (m) => m?.id === e?.id
        );
        if (foundIndex > -1) {
          return false;
        }
        return true;
      }
      return true;
    });

    if (filteredOldMeetingEvents?.[0]?.id) {
      modifiedAllEvents.push(
        ...filteredOldMeetingEvents?.map((a) =>
          convertMeetingPlusTypeToEventPlusType(a)
        )
      );
    }

    if (newBufferTimeArray?.length > 0) {
      modifiedAllEvents.push(...newBufferTimeArray);
    }

    if (newMeetingEvents?.length > 0) {
      modifiedAllEvents.push(
        ...newMeetingEvents?.map((m) =>
          convertMeetingPlusTypeToEventPlusType(m)
        )
      );
    }

    modifiedAllEvents?.forEach((e) => console.log(e, ' modifiedAllEvents'));

    const unfilteredUserPreferences: UserPreferenceType[] = [];
    for (const internalAttendee of internalAttendees) {
      const userPreference = await getUserPreferences(internalAttendee?.userId);
      unfilteredUserPreferences.push(userPreference);
    }

    const userPreferences: UserPreferenceType[] = _.uniqWith(
      unfilteredUserPreferences,
      _.isEqual
    );

    const unfilteredGlobalPrimaryCalendars: CalendarType[] = [];

    for (const internalAttendee of internalAttendees) {
      const globalPrimaryCalendar = await getGlobalCalendar(
        internalAttendee?.userId
      );
      unfilteredGlobalPrimaryCalendars.push(globalPrimaryCalendar);
    }

    const globalPrimaryCalendars = _.uniqWith(
      unfilteredGlobalPrimaryCalendars,
      _.isEqual
    );

    globalPrimaryCalendars?.forEach((c) =>
      console.log(c, ' globalPrimaryCalendars')
    );

    const modifiedAllEventsWithBreaks: EventPlusType[] = [];

    let parentBreaks: EventPlusType[] = [];
    for (const userPreference of userPreferences) {
      const globalPrimaryCalendar = globalPrimaryCalendars?.find(
        (g) => g?.userId === userPreference?.userId
      );
      if (!globalPrimaryCalendar) {
        throw new Error('no global primary calendar found');
      }
      const userId = userPreference?.userId;

      const breaks = await generateBreakEventsForDate(
        userPreference,
        userId,
        windowStartDate,
        windowEndDate,
        hostTimezone,
        globalPrimaryCalendar?.id
      );

      breaks.forEach((b) => console.log(b, ' generatedBreaks'));

      if (breaks?.length > 0) {
        const allEventsWithDuplicateFreeBreaks = _.differenceBy(
          modifiedAllEvents,
          breaks,
          'id'
        );
        modifiedAllEventsWithBreaks.push(
          ...allEventsWithDuplicateFreeBreaks?.filter(
            (e) => e?.userId === userId
          )
        );
        modifiedAllEventsWithBreaks.push(...breaks);
        parentBreaks.push(...breaks);
      } else {
        modifiedAllEventsWithBreaks.push(
          ...modifiedAllEvents?.filter((e) => e?.userId === userId)
        );
      }
    }

    modifiedAllEventsWithBreaks?.forEach((m) =>
      console.log(m, ' modifiedAllEventsWithBreaks')
    );

    const diffDays = dayjs(windowEndDate.slice(0, 19)).diff(
      dayjs(windowStartDate.slice(0, 19)),
      'day'
    );
    console.log(
      diffDays,
      windowEndDate,
      windowStartDate,
      ' diffDays, windowEndDate, windowStartDate'
    );
    const startDatesForEachDay = [];

    for (let i = 0; i <= diffDays; i++) {
      startDatesForEachDay.push(
        dayjs(windowStartDate.slice(0, 19))
          .tz(hostTimezone, true)
          .add(i, 'day')
          .format()
      );
    }

    console.log(startDatesForEachDay, ' startDatesForEachDay');

    const unfilteredWorkTimes: WorkTimeType[] = [];
    for (const internalAttendee of internalAttendees) {
      const userPreference = userPreferences.find(
        (u) => u.userId === internalAttendee.userId
      );
      const attendeeTimezone = internalAttendee?.timezone;
      const workTimesForAttendee = generateWorkTimesForInternalAttendee(
        mainHostId,
        internalAttendee.userId,
        userPreference,
        hostTimezone,
        attendeeTimezone
      );
      unfilteredWorkTimes.push(...workTimesForAttendee);
    }

    console.log(unfilteredWorkTimes, 'unfilteredWorkTimes');
    const workTimes: WorkTimeType[] = _.uniqWith(
      unfilteredWorkTimes,
      _.isEqual
    );

    const unfilteredTimeslots = [];
    const timeslots = [];

    for (let i = 0; i < startDatesForEachDay.length; i++) {
      if (i === 0) {
        for (const internalAttendee of internalAttendees) {
          const userPreference = userPreferences.find(
            (u) => u.userId === internalAttendee.userId
          );
          const timeslotsForDay =
            await generateTimeSlotsLiteForInternalAttendee(
              startDatesForEachDay?.[i],
              mainHostId,
              userPreference,
              hostTimezone,
              internalAttendee?.timezone,
              true
            );
          unfilteredTimeslots.push(...timeslotsForDay);
        }
        continue;
      }
      for (const internalAttendee of internalAttendees) {
        const userPreference = userPreferences.find(
          (u) => u.userId === internalAttendee.userId
        );
        const timeslotsForDay = await generateTimeSlotsLiteForInternalAttendee(
          startDatesForEachDay?.[i],
          mainHostId,
          userPreference,
          hostTimezone,
          internalAttendee?.timezone,
          false
        );
        unfilteredTimeslots.push(...timeslotsForDay);
      }
    }

    timeslots.push(..._.uniqWith(unfilteredTimeslots, _.isEqual));
    console.log(timeslots, ' timeslots');

    const unfilteredAllEvents: EventPlusType[] = [];
    for (const internalAttendee of internalAttendees) {
      const userPreference = userPreferences.find(
        (u) => u.userId === internalAttendee.userId
      );
      const modifiedAllEventsWithBreaksWithUser =
        modifiedAllEventsWithBreaks.filter(
          (e) => e.userId === internalAttendee.userId
        );
      const events = modifiedAllEventsWithBreaksWithUser.filter((e) =>
        validateEventDates(e, userPreference)
      );
      unfilteredAllEvents.push(...events);
    }
    unfilteredAllEvents?.forEach((e) => console.log(e, ' unfilteredAllEvents'));

    const filteredAllEvents = _.uniqBy(unfilteredAllEvents, 'id');

    filteredAllEvents?.forEach((e) => console.log(e, ' filteredAllEvents'));

    let eventParts: EventPartPlannerRequestBodyType[] = [];

    const eventPartMinisAccumulated = [];
    for (const event of filteredAllEvents) {
      const eventPartMinis = generateEventPartsLite(event, mainHostId);
      eventPartMinisAccumulated.push(...eventPartMinis);
    }

    eventPartMinisAccumulated?.forEach((e) =>
      console.log(e, ' eventPartMinisAccumulated')
    );
    const modifiedEventPartMinisPreBuffer =
      modifyEventPartsForMultiplePreBufferTime(eventPartMinisAccumulated);
    const modifiedEventPartMinisPreAndPostBuffer =
      modifyEventPartsForMultiplePostBufferTime(
        modifiedEventPartMinisPreBuffer
      );

    modifiedEventPartMinisPreAndPostBuffer?.forEach((e) =>
      console.log(e, ' modifiedEventPartMinisPreAndPostBuffer')
    );

    const formattedEventParts: EventPartPlannerRequestBodyType[] = [];
    for (const userPreference of userPreferences) {
      const formattedEventPartsForUser: EventPartPlannerRequestBodyType[] =
        modifiedEventPartMinisPreAndPostBuffer
          ?.filter((e) => e?.userId === userPreference?.userId)
          ?.map((e) =>
            formatEventTypeToPlannerEvent(
              e,
              userPreference,
              workTimes,
              hostTimezone
            )
          );

      formattedEventPartsForUser?.forEach((e) =>
        console.log(e, ' formattedEventPartsForUser')
      );

      formattedEventParts.push(...formattedEventPartsForUser);
    }

    formattedEventParts?.forEach((e) => console.log(e, ' formattedEventParts'));

    if (formattedEventParts.length > 0) {
      eventParts.push(..._.uniqWith(formattedEventParts, _.isEqual));
    }

    if (eventParts.length > 0) {
      eventParts.forEach((e) => console.log(e, ' eventParts after formatting'));
      const newEventPartsWithPreferredTimeSet = eventParts.map((e) =>
        setPreferredTimeForUnModifiableEvent(
          e,
          allEvents.find((f) => f.id === e.eventId)?.timezone
        )
      );
      newEventPartsWithPreferredTimeSet.forEach((e) =>
        console.log(e, ' newEventPartsWithPreferredTimeSet')
      );
      const newEventParts = await tagEventsForDailyOrWeeklyTask(
        newEventPartsWithPreferredTimeSet
      );
      newEventParts.forEach((e) =>
        console.log(e, ' newEventParts after tagEventsForDailyOrWeeklyTask')
      );
      const unfilteredUserList: UserPlannerRequestBodyType[] = [];
      for (const userPreference of userPreferences) {
        const userPlannerRequestBody = generateUserPlannerRequestBody(
          userPreference,
          userPreference?.userId,
          workTimes,
          mainHostId
        );
        console.log(userPlannerRequestBody, ' userPlannerRequestBody');
        unfilteredUserList.push(userPlannerRequestBody);
      }

      const userList: UserPlannerRequestBodyType[] = _.uniqWith(
        unfilteredUserList,
        _.isEqual
      );

      const modifiedNewEventParts: EventPartPlannerRequestBodyType[] =
        newEventParts.map((eventPart) => {
          const oldEvent = filteredAllEvents.find(
            (event) => event.id === eventPart.eventId
          );
          return {
            groupId: eventPart?.groupId,
            eventId: eventPart?.eventId,
            part: eventPart?.part,
            lastPart: eventPart?.lastPart,
            meetingPart: eventPart?.meetingPart,
            meetingLastPart: eventPart?.meetingLastPart,
            meetingId: eventPart?.meetingId,
            hostId: mainHostId,
            startDate: dayjs(eventPart?.startDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .tz(hostTimezone)
              .format(),
            endDate: dayjs(eventPart?.endDate.slice(0, 19))
              .tz(oldEvent.timezone, true)
              .tz(hostTimezone)
              .format(),
            userId: eventPart?.userId,
            user: eventPart?.user,
            priority: eventPart?.priority,
            isPreEvent: eventPart?.isPreEvent,
            isPostEvent: eventPart?.isPostEvent,
            positiveImpactScore: eventPart?.positiveImpactScore,
            negativeImpactScore: eventPart?.negativeImpactScore,
            modifiable: eventPart?.modifiable,
            isMeeting: eventPart?.isMeeting,
            isExternalMeeting: eventPart?.isExternalMeeting,
            isExternalMeetingModifiable: eventPart?.isExternalMeetingModifiable,
            isMeetingModifiable: eventPart?.isMeetingModifiable,
            dailyTaskList: eventPart?.dailyTaskList,
            weeklyTaskList: eventPart?.weeklyTaskList,
            gap: eventPart?.gap,
            totalWorkingHours: eventPart?.totalWorkingHours,
            hardDeadline: eventPart?.hardDeadline,
            softDeadline: eventPart?.softDeadline,
            forEventId: eventPart?.forEventId,
            positiveImpactDayOfWeek: eventPart?.positiveImpactDayOfWeek,
            positiveImpactTime: eventPart?.positiveImpactTime,
            negativeImpactDayOfWeek: eventPart?.negativeImpactDayOfWeek,
            negativeImpactTime: eventPart?.negativeImpactTime,
            preferredDayOfWeek: eventPart?.preferredDayOfWeek,
            preferredTime: eventPart?.preferredTime,
            preferredStartTimeRange: eventPart?.preferredStartTimeRange,
            preferredEndTimeRange: eventPart?.preferredEndTimeRange,
            event: eventPart?.event,
          };
        });

      modifiedNewEventParts?.forEach((e) =>
        console.log(e, ' modifiedNewEventParts')
      );

      return modifiedNewEventParts?.length > 0
        ? {
            userIds: internalAttendees.map((a) => a.userId),
            hostId: mainHostId,
            eventParts: modifiedNewEventParts,
            allEvents: filteredAllEvents,
            breaks: parentBreaks,
            oldEvents,
            timeslots,
            userList,
          }
        : null;
    }
  } catch (e) {
    console.log(
      e,
      ' unable to process events for optaplanner for each attendee'
    );
  }
};

export const processEventsForOptaPlanner = async (
  mainHostId: string,
  internalAttendees: MeetingAssistAttendeeType[],
  meetingEventPlus: EventMeetingPlusType[],
  newMeetingEventPlus: EventMeetingPlusType[],
  allEvents: EventPlusType[],
  windowStartDate: string,
  windowEndDate: string,
  hostTimezone: string,
  oldEvents: EventPlusType[],
  externalAttendees?: MeetingAssistAttendeeType[],
  meetingAssistEvents?: MeetingAssistEventType[],
  newHostReminders?: RemindersForEventType[],
  newHostBufferTimes?: BufferTimeObjectType[]
) => {
  try {
    console.log(
      windowStartDate,
      windowEndDate,
      ' windowStartDate, windowEndDate inside processEventsForOptaPlanner'
    );

    const newInternalMeetingEventsPlus = newMeetingEventPlus
      ?.map((e) => {
        const foundIndex = externalAttendees?.findIndex(
          (a) => a?.userId === e?.userId
        );

        if (foundIndex > -1) {
          return null;
        }
        return e;
      })
      ?.filter((e) => e !== null);

    const newExternalMeetingEventsPlus = newMeetingEventPlus
      ?.map((e) => {
        const foundIndex = externalAttendees?.findIndex(
          (a) => a?.userId === e?.userId
        );

        if (foundIndex > -1) {
          return e;
        }
        return null;
      })
      ?.filter((e) => e !== null);

    const allHostEvents = allEvents.filter((e) => e.userId === mainHostId);

    const oldHostEvents = oldEvents.filter((e) => e?.userId === mainHostId);

    const hostIsInternalAttendee = internalAttendees.some(
      (ia) => ia?.userId === mainHostId
    );

    let returnValuesFromInternalAttendees:
      | ReturnBodyForAttendeeForOptaplannerPrepType
      | {} = {};
    let returnValuesFromHost: ReturnBodyForHostForOptaplannerPrepType | {} = {};

    console.log(hostIsInternalAttendee, ' hostIsInternalAttendee');

    if (hostIsInternalAttendee) {
      returnValuesFromInternalAttendees =
        await processEventsForOptaPlannerForInternalAttendees(
          mainHostId,
          allEvents,
          windowStartDate,
          windowEndDate,
          hostTimezone,
          internalAttendees,
          oldEvents,
          meetingEventPlus,
          newInternalMeetingEventsPlus,
          newHostBufferTimes
        );
    } else {
      returnValuesFromHost = await processEventsForOptaPlannerForMainHost(
        mainHostId,
        allHostEvents,
        windowStartDate,
        windowEndDate,
        hostTimezone,
        oldHostEvents,
        newHostBufferTimes
      );
    }

    console.log(
      returnValuesFromInternalAttendees,
      ' returnValuesFromInternalAttendees'
    );
    const externalMeetingEventPlus = meetingEventPlus
      .map((e) => {
        const foundIndex = externalAttendees.findIndex(
          (a) => a?.userId === e?.userId
        );
        if (foundIndex > -1) {
          return e;
        }
        return null;
      })
      ?.filter((e) => e !== null);

    const returnValuesFromExternalAttendees: ReturnBodyForExternalAttendeeForOptaplannerPrepType =
      externalAttendees?.length > 0
        ? await processEventsForOptaPlannerForExternalAttendees(
            externalAttendees?.map((a) => a.userId),
            mainHostId,
            meetingAssistEvents,
            windowStartDate,
            windowEndDate,
            hostTimezone,
            externalAttendees,
            externalMeetingEventPlus,
            newExternalMeetingEventsPlus
          )
        : null;

    const eventParts: EventPartPlannerRequestBodyType[] = [];
    const allEventsForPlanner: EventPlusType[] = [];
    const breaks: EventPlusType[] = [];
    const oldEventsForPlanner: EventPlusType[] = [];
    const oldAttendeeEvents: MeetingAssistEventType[] = [];
    const unfilteredTimeslots: TimeSlotType[] = [];
    const unfilteredUserList: UserPlannerRequestBodyType[] = [];

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.eventParts?.length > 0
    ) {
      eventParts.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.eventParts
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.allEvents?.length > 0
    ) {
      allEventsForPlanner.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.allEvents
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)?.breaks
        ?.length > 0
    ) {
      breaks.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.breaks
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.oldEvents?.length > 0
    ) {
      oldEventsForPlanner.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.oldEvents
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.timeslots?.length > 0
    ) {
      unfilteredTimeslots.push(
        ...(returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.timeslots
      );
    }

    if (
      (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
        ?.userPlannerRequestBody?.id
    ) {
      unfilteredUserList.push(
        (returnValuesFromHost as ReturnBodyForHostForOptaplannerPrepType)
          ?.userPlannerRequestBody
      );
    }

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.userList?.[0]?.id
    ) {
      unfilteredUserList.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.userList
      );
    }

    (
      returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
    )?.eventParts?.forEach((e) =>
      console.log(
        e,
        ' (returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType)?.eventParts'
      )
    );

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.eventParts?.length > 0
    ) {
      eventParts.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.eventParts
      );
    }

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.allEvents?.length > 0
    ) {
      allEventsForPlanner.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.allEvents
      );
    }

    (
      returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
    )?.breaks?.forEach((e) =>
      console.log(
        e,
        ' (returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType)?.breaks'
      )
    );

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.breaks?.length > 0
    ) {
      breaks.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.breaks
      );
    }

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.oldEvents?.length > 0
    ) {
      oldEventsForPlanner.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.oldEvents
      );
    }

    if (
      (
        returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
      )?.timeslots?.length > 0
    ) {
      unfilteredTimeslots.push(
        ...(
          returnValuesFromInternalAttendees as ReturnBodyForAttendeeForOptaplannerPrepType
        )?.timeslots
      );
    }

    if (returnValuesFromExternalAttendees?.eventParts?.length > 0) {
      eventParts.push(...returnValuesFromExternalAttendees?.eventParts);
    }

    if (returnValuesFromExternalAttendees?.allEvents?.length > 0) {
      allEventsForPlanner.push(...returnValuesFromExternalAttendees?.allEvents);
    }

    if (returnValuesFromExternalAttendees?.oldAttendeeEvents?.length > 0) {
      oldAttendeeEvents.push(
        ...returnValuesFromExternalAttendees?.oldAttendeeEvents
      );
    }

    if (returnValuesFromExternalAttendees?.timeslots?.length > 0) {
      unfilteredTimeslots.push(...returnValuesFromExternalAttendees?.timeslots);
    }

    if (returnValuesFromExternalAttendees?.userList?.length > 0) {
      unfilteredUserList.push(...returnValuesFromExternalAttendees?.userList);
    }

    console.log(oldEvents, ' oldEvents before saving to s3');

    const duplicateFreeEventParts: EventPartPlannerRequestBodyType[] =
      _.uniqWith(eventParts, _.isEqual);
    const duplicateFreeAllEvents = _.uniqWith(allEventsForPlanner, _.isEqual);
    const duplicateFreeBreaks = _.uniqWith(breaks, _.isEqual);
    const duplicateFreeOldEvents = _.uniqWith(oldEvents, _.isEqual);
    const duplicateFreeOldAttendeeEvents = _.uniqWith(
      oldAttendeeEvents,
      _.isEqual
    );
    const duplicateFreeTimeslots: TimeSlotType[] = _.uniqWith(
      unfilteredTimeslots,
      _.isEqual
    );
    const singletonId = uuid();

    console.log(eventParts, ' eventParts before validation');
    console.log(
      duplicateFreeEventParts,
      ' duplicateFreeEventParts before validation'
    );
    console.log(duplicateFreeAllEvents, ' duplicateFreeAllEvents');
    console.log(duplicateFreeOldEvents, ' duplicateFreeOldEvents');
    console.log(duplicateFreeTimeslots, ' duplicateFreeTimeslots');
    if (!duplicateFreeEventParts || duplicateFreeEventParts?.length === 0) {
      throw new Error('Event Parts length is 0 or do not exist');
    }

    if (!duplicateFreeTimeslots || !(duplicateFreeTimeslots?.length > 0)) {
      throw new Error(' duplicateFreeTimeslots is empty');
    }

    if (!unfilteredUserList || !(unfilteredUserList?.length > 0)) {
      throw new Error('unfilteredUserList is empty');
    }

    duplicateFreeTimeslots?.forEach((d) =>
      console.log(d, ' duplicateFreeTimeslots')
    );
    unfilteredUserList?.forEach((u) => console.log(u, ' unfilteredUserList'));
    newHostBufferTimes?.forEach((b) =>
      console.log(b.beforeEvent, b.afterEvent, ' b.beforeEvent b.afterEvent ')
    );

    const params = {
      Body: JSON.stringify({
        singletonId,
        hostId: mainHostId,
        eventParts: duplicateFreeEventParts,
        allEvents: duplicateFreeAllEvents,
        breaks: duplicateFreeBreaks,
        oldEvents: duplicateFreeOldEvents,
        oldAttendeeEvents: duplicateFreeOldAttendeeEvents,
        newHostBufferTimes: newHostBufferTimes,
        newHostReminders: newHostReminders,
        hostTimezone,
      }),
      Bucket: bucketName,
      Key: `${mainHostId}/${singletonId}.json`,
      ContentType: 'application/json',
    };

    const s3Command = new PutObjectCommand(params);

    const s3Response = await s3Client.send(s3Command);

    console.log(s3Response, ' s3Response');

    await optaPlanWeekly(
      duplicateFreeTimeslots,
      unfilteredUserList,
      duplicateFreeEventParts,
      singletonId,
      mainHostId,
      `${mainHostId}/${singletonId}.json`,
      optaplannerDuration,
      onOptaPlanCalendarAdminCallBackUrl
    );

    console.log('optaplanner request sent');
  } catch (e) {
    console.log(e, ' unable to process events for optaplanner');
  }
};
