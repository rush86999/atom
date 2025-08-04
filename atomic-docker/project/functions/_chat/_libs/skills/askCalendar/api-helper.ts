import { UserPreferenceType } from '@chat/_libs/types/UserPreferenceType';
import { DataAttributesType, UserWorkTimeType, time } from './types';
import { setISODay } from 'date-fns';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { dayOfWeekIntToString } from './constants';
import { hasuraAdminSecret, hasuraGraphUrl } from '@chat/_libs/constants';
import got from 'got';
import { EventType } from '@chat/_libs/types/EventType';
import listConferencesByIds from '@chat/_libs/gql/listConferencesByIds';
import { ConferenceType } from '@chat/_libs/types/ConferenceType';
import listTasksByIds from '@chat/_libs/gql/listTasksByIds';
import { TaskType } from '@chat/_libs/types/TaskType';
import { AttendeeType } from '@chat/_libs/types/AttendeeType';
import listAttendeesByEventIds from '@chat/_libs/gql/listAttendeesByEventIds';

export const generateWorkTimesForUser = (
  userPreference: UserPreferenceType,
  timezone: string
): UserWorkTimeType[] => {
  // 7 days in a week
  const daysInWeek = 7;
  const startTimes = userPreference.startTimes;
  const endTimes = userPreference.endTimes;
  const workTimes: UserWorkTimeType[] = [];

  console.log(startTimes, ' startTimes inside generateWorkTimesForUser');
  console.log(endTimes, ' endTimes inside generateWorkTimesForUser');
  console.log(timezone, ' timezone inside generateWorkTimesForUser');

  for (let i = 0; i < daysInWeek; i++) {
    const dayOfWeekInt = i + 1;
    const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
    const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
    const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
    const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;

    console.log(
      dayOfWeekInt,
      dayOfWeekIntToString[dayOfWeekInt],
      ' dayOfWeekInt, dayOfWeekIntToString[dayOfWeekInt] inside generateWorkTimesForUser'
    );
    workTimes.push({
      dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
      startTime: dayjs(
        setISODay(
          dayjs()
            .hour(startHour)
            .minute(startMinute)
            .tz(timezone, true)
            .toDate(),
          i + 1
        )
      )
        .tz(timezone)
        .format('h:mm a') as time,
      endTime: dayjs(
        setISODay(
          dayjs().hour(endHour).minute(endMinute).tz(timezone, true).toDate(),
          i + 1
        )
      )
        .tz(timezone)
        .format('h:mm a') as time,
    });
  }

  return workTimes;
};

export const getUserPreferences = async (
  userId: string
): Promise<UserPreferenceType | null> => {
  try {
    if (!userId) {
      console.log('userId is null');
      return null;
    }
    const operationName = 'getUserPreferences';
    const query = `
    query getUserPreferences($userId: uuid!) {
      User_Preference(where: {userId: {_eq: $userId}}) {
        startTimes
        endTimes
        backToBackMeetings
        copyAvailability
        copyCategories
        copyIsBreak
        copyModifiable
        copyPriorityLevel
        copyReminders
        copyTimeBlocking
        copyTimePreference
        createdDate
        deleted
        followUp
        id
        isPublicCalendar
        maxNumberOfMeetings
        maxWorkLoadPercent
        publicCalendarCategories
        reminders
        updatedAt
        userId
        minNumberOfBreaks
        breakColor
        breakLength
        copyColor
        copyIsExternalMeeting
        copyIsMeeting
        onBoarded
      }
    }    
  `;
    const res: { data: { User_Preference: UserPreferenceType[] } } = await got
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
            userId,
          },
        },
      })
      .json();
    return res?.data?.User_Preference?.[0];
  } catch (e) {
    console.log(e, ' getUserPreferences');
    return null;
  }
};

export const getEventObjectCount = async (
  userId: string,
  startDate: string,
  endDate: string
) => {
  try {
    const operationName = 'GetEventCount';
    const query = `
            query GetEventCount($userId: uuid!, $startDate: timestamp!, $endDate: timestamp!) {
                Event_aggregate(where: {userId: {_eq: $userId}, startDate: {_lte: $endDate}, endDate: {_gte: $startDate}}) {
                    aggregate {
                    count
                    }
                }
            }

        `;

    const res: { data: { Event_aggregat: { aggregate: { count: number } } } } =
      await got
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
              userId,
              startDate,
              endDate,
            },
          },
        })
        .json();

    console.log(res, ' got event aggregate count');
    return res?.data?.Event_aggregat?.aggregate?.count;
  } catch (e) {
    console.log(e, ' uanble to get event object count');
  }
};

export const listAttendeesGivenEventIds = async (eventIds: string[]) => {
  try {
    if (!(eventIds?.length > 0)) {
      console.log('no task ids provided inside listTasksGivenIds');
      return [];
    }

    const operationName = 'listAttendeesByEventIds';
    const query = listAttendeesByEventIds;

    const res: { data: { Attendee: AttendeeType[] } } = await got
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
            eventIds,
          },
        },
      })
      .json();

    console.log(
      res,
      ' successfully queried attendee inside listAttendeesByIds'
    );

    return res?.data?.Attendee;
  } catch (e) {
    console.log(e, ' unable to list attendees given ids');
  }
};

export const listTasksGivenIds = async (ids: string[]) => {
  try {
    if (!(ids?.length > 0)) {
      console.log('no task ids provided inside listTasksGivenIds');
      return [];
    }

    const operationName = 'listTasksByIds';
    const query = listTasksByIds;

    const res: { data: { Task: TaskType[] } } = await got
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
            ids,
          },
        },
      })
      .json();

    console.log(res, ' successfully queried task inside listTasksGivenIds');

    return res?.data?.Task;
  } catch (e) {
    console.log(e, ' list tasks given ids');
  }
};

export const listConferencesGivenIds = async (ids: string[]) => {
  try {
    if (!(ids?.length > 0)) {
      console.log('no conference ids provided inside listConferencesGivenIds');
      return [];
    }

    const operationName = 'listConferencesByIds';
    const query = listConferencesByIds;

    const res: { data: { Conference: ConferenceType[] } } = await got
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
            ids,
          },
        },
      })
      .json();

    console.log(res, ' res for listConferencesGivenIds');

    return res?.data?.Conference;
  } catch (e) {
    console.log(e, ' unable to list conferences given ids');
  }
};

export const listSortedObjectsForUserGivenDatesAndAttributes = async (
  userId: string,
  startDate: string,
  endDate: string,
  attributes: DataAttributesType[],
  isMeeting: boolean,
  ids: string[] = []
) => {
  try {
    if (!(attributes?.length > 0)) {
      console.log(' no attributes found');
      return;
    }

    let eventAttributesString = '';

    let isCount = false;
    let count = 0;

    let isAllAttributes = false;

    let isNone = false;

    let isConference = false;
    let conferences: ConferenceType[] = [];
    let attendees: AttendeeType[] = [];

    let isTask = false;
    let tasks: TaskType[] = [];

    const allAttributes = `
            allDay
            anyoneCanAddSelf
            attachments
            attendeesOmitted
            backgroundColor
            calendarId
            colorId
            conferenceId
            copyAvailability
            copyCategories
            copyDuration
            copyIsBreak
            copyIsExternalMeeting
            copyIsMeeting
            copyModifiable
            copyPriorityLevel
            copyReminders
            copyTimeBlocking
            copyTimePreference
            createdDate
            creator
            dailyTaskList
            deleted
            duration
            endDate
            endTimeUnspecified
            eventId
            eventType
            extendedProperties
            followUpEventId
            forEventId
            foregroundColor
            guestsCanInviteOthers
            guestsCanModify
            guestsCanSeeOtherGuests
            hangoutLink
            hardDeadline
            htmlLink
            iCalUID
            id
            isBreak
            isExternalMeeting
            isExternalMeetingModifiable
            isFollowUp
            isMeeting
            isMeetingModifiable
            isPostEvent
            isPreEvent
            links
            location
            locked
            maxAttendees
            meetingId
            method
            modifiable
            negativeImpactDayOfWeek
            negativeImpactScore
            negativeImpactTime
            notes
            organizer
            originalAllDay
            originalStartDate
            originalTimezone
            positiveImpactDayOfWeek
            positiveImpactScore
            positiveImpactTime
            postEventId
            preEventId
            preferredDayOfWeek
            preferredEndTimeRange
            preferredStartTimeRange
            preferredTime
            priority
            privateCopy
            recurrence
            recurrenceRule
            recurringEventId
            sendUpdates
            softDeadline
            source
            startDate
            status
            summary
            taskId
            taskType
            timeBlocking
            timezone
            title
            transparency
            unlink
            updatedAt
            useDefaultAlarms
            userId
            userModifiedAvailability
            userModifiedCategories
            userModifiedDuration
            userModifiedIsBreak
            userModifiedIsExternalMeeting
            userModifiedIsMeeting
            userModifiedModifiable
            userModifiedPriorityLevel
            userModifiedReminders
            userModifiedTimeBlocking
            userModifiedTimePreference
            visibility
            weeklyTaskList
            byWeekDay
            localSynced
            userModifiedColor
            copyColor
            copyExternalMeetingModifiable
            userModifiedExternalMeetingModifiable
            userModifiedMeetingModifiable
        `;

    for (const attribute of attributes) {
      if (attribute === 'allDay') {
        eventAttributesString += 'allDay' + '\n';
        continue;
      } else if (attribute === 'count') {
        isCount = true;
        continue;
      } else if (attribute === 'all') {
        isAllAttributes = true;
        break;
      } else if (attribute === 'none') {
        isNone = true;
        break;
      } else if (attribute === 'id') {
        continue;
      } else if (attribute === 'userId') {
        continue;
      } else if (attribute === 'title') {
        continue;
      } else if (attribute === 'startDate') {
        continue;
      } else if (attribute === 'endDate') {
        continue;
      } else if (attribute === 'notes') {
        continue;
      } else if (attribute === 'timezone') {
        continue;
      } else if (attribute === 'taskId') {
        continue;
      } else if (attribute === 'conferenceId') {
        isConference = true;
        continue;
      } else if (attribute === 'duration') {
        continue;
      } else if (attribute === 'conference-name') {
        isConference = true;
        continue;
      } else if (attribute === 'conference-notes') {
        isConference = true;
        continue;
      } else if (attribute === 'conference-joinUrl') {
        isConference = true;
        continue;
      } else if (attribute === 'conference-startUrl') {
        isConference = true;
        continue;
      } else if (attribute === 'task') {
        isTask = true;
        continue;
      } else if (attribute === 'task-listName') {
        isTask = true;
        continue;
      } else if (attribute === 'task-status') {
        isTask = true;
        continue;
      }
      eventAttributesString += attribute + '\n';
    }

    const operationName = 'listEventsForUser';
    const query = `
            query listEventsForUser(${ids?.length > 0 ? '$ids: [String!]!, ' : ''}$userId: uuid!, $startDate: timestamp!, $endDate: timestamp!) {
                Event(where: {${ids?.length > 0 ? 'id: {_in: $ids}, ' : ''}userId: {_eq: $userId}, endDate: {_gte: $startDate}, startDate: {_lte: $endDate}, deleted: {_neq: true}}, order_by: {startDate: asc}) {
                    calendarId
                    conferenceId
                    createdDate
                    duration
                    endDate
                    eventId
                    id
                    notes
                    startDate
                    summary
                    taskId
                    timezone
                    title
                    updatedAt
                    userId
                    ${!isNone && eventAttributesString}
                    ${!isNone && isAllAttributes && allAttributes}
                }
            }
        `;
    let variables: any = {
      userId,
      startDate,
      endDate,
    };

    if (ids?.length > 0) {
      variables.ids = ids;
    }

    const res: { data: { Event: EventType[] } } = await got
      .post(hasuraGraphUrl, {
        headers: {
          'X-Hasura-Admin-Secret': hasuraAdminSecret,
          'Content-Type': 'application/json',
          'X-Hasura-Role': 'admin',
        },
        json: {
          operationName,
          query,
          variables,
        },
      })
      .json();

    console.log(res, ' res from listEventsforUser');

    const events = res?.data?.Event;

    if (isCount) {
      count = await getEventObjectCount(userId, startDate, endDate);
    }

    if (isConference || isMeeting) {
      conferences = await listConferencesGivenIds(
        events?.filter((e) => !!e?.conferenceId)?.map((e) => e?.conferenceId)
      );
      attendees = await listAttendeesGivenEventIds(events?.map((e) => e?.id));
    }

    if (isTask) {
      tasks = await listTasksGivenIds(
        events?.filter((e) => !!e?.taskId)?.map((e) => e?.taskId)
      );
    }

    // return all values
    return {
      events,
      conferences,
      attendees,
      tasks,
      count,
    };
  } catch (e) {
    console.log(e, ' listEventsForUser');
  }
};
