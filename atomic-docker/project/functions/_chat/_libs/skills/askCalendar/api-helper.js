import { setISODay } from 'date-fns';
import { dayjs } from '@chat/_libs/datetime/date-utils';
import { dayOfWeekIntToString } from './constants';
import { hasuraAdminSecret, hasuraGraphUrl } from '@chat/_libs/constants';
import got from 'got';
import listConferencesByIds from '@chat/_libs/gql/listConferencesByIds';
import listTasksByIds from '@chat/_libs/gql/listTasksByIds';
import listAttendeesByEventIds from '@chat/_libs/gql/listAttendeesByEventIds';
export const generateWorkTimesForUser = (userPreference, timezone) => {
    // 7 days in a week
    const daysInWeek = 7;
    const startTimes = userPreference.startTimes;
    const endTimes = userPreference.endTimes;
    const workTimes = [];
    console.log(startTimes, ' startTimes inside generateWorkTimesForUser');
    console.log(endTimes, ' endTimes inside generateWorkTimesForUser');
    console.log(timezone, ' timezone inside generateWorkTimesForUser');
    for (let i = 0; i < daysInWeek; i++) {
        const dayOfWeekInt = i + 1;
        const startHour = startTimes.find((i) => i.day === dayOfWeekInt).hour;
        const startMinute = startTimes.find((i) => i.day === dayOfWeekInt).minutes;
        const endHour = endTimes.find((i) => i.day === dayOfWeekInt).hour;
        const endMinute = endTimes.find((i) => i.day === dayOfWeekInt).minutes;
        console.log(dayOfWeekInt, dayOfWeekIntToString[dayOfWeekInt], ' dayOfWeekInt, dayOfWeekIntToString[dayOfWeekInt] inside generateWorkTimesForUser');
        workTimes.push({
            dayOfWeek: dayOfWeekIntToString[dayOfWeekInt],
            startTime: dayjs(setISODay(dayjs()
                .hour(startHour)
                .minute(startMinute)
                .tz(timezone, true)
                .toDate(), i + 1))
                .tz(timezone)
                .format('h:mm a'),
            endTime: dayjs(setISODay(dayjs().hour(endHour).minute(endMinute).tz(timezone, true).toDate(), i + 1))
                .tz(timezone)
                .format('h:mm a'),
        });
    }
    return workTimes;
};
export const getUserPreferences = async (userId) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' getUserPreferences');
        return null;
    }
};
export const getEventObjectCount = async (userId, startDate, endDate) => {
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
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' uanble to get event object count');
    }
};
export const listAttendeesGivenEventIds = async (eventIds) => {
    try {
        if (!(eventIds?.length > 0)) {
            console.log('no task ids provided inside listTasksGivenIds');
            return [];
        }
        const operationName = 'listAttendeesByEventIds';
        const query = listAttendeesByEventIds;
        const res = await got
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
        console.log(res, ' successfully queried attendee inside listAttendeesByIds');
        return res?.data?.Attendee;
    }
    catch (e) {
        console.log(e, ' unable to list attendees given ids');
    }
};
export const listTasksGivenIds = async (ids) => {
    try {
        if (!(ids?.length > 0)) {
            console.log('no task ids provided inside listTasksGivenIds');
            return [];
        }
        const operationName = 'listTasksByIds';
        const query = listTasksByIds;
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' list tasks given ids');
    }
};
export const listConferencesGivenIds = async (ids) => {
    try {
        if (!(ids?.length > 0)) {
            console.log('no conference ids provided inside listConferencesGivenIds');
            return [];
        }
        const operationName = 'listConferencesByIds';
        const query = listConferencesByIds;
        const res = await got
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
    }
    catch (e) {
        console.log(e, ' unable to list conferences given ids');
    }
};
export const listSortedObjectsForUserGivenDatesAndAttributes = async (userId, startDate, endDate, attributes, isMeeting, ids = []) => {
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
        let conferences = [];
        let attendees = [];
        let isTask = false;
        let tasks = [];
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
            }
            else if (attribute === 'count') {
                isCount = true;
                continue;
            }
            else if (attribute === 'all') {
                isAllAttributes = true;
                break;
            }
            else if (attribute === 'none') {
                isNone = true;
                break;
            }
            else if (attribute === 'id') {
                continue;
            }
            else if (attribute === 'userId') {
                continue;
            }
            else if (attribute === 'title') {
                continue;
            }
            else if (attribute === 'startDate') {
                continue;
            }
            else if (attribute === 'endDate') {
                continue;
            }
            else if (attribute === 'notes') {
                continue;
            }
            else if (attribute === 'timezone') {
                continue;
            }
            else if (attribute === 'taskId') {
                continue;
            }
            else if (attribute === 'conferenceId') {
                isConference = true;
                continue;
            }
            else if (attribute === 'duration') {
                continue;
            }
            else if (attribute === 'conference-name') {
                isConference = true;
                continue;
            }
            else if (attribute === 'conference-notes') {
                isConference = true;
                continue;
            }
            else if (attribute === 'conference-joinUrl') {
                isConference = true;
                continue;
            }
            else if (attribute === 'conference-startUrl') {
                isConference = true;
                continue;
            }
            else if (attribute === 'task') {
                isTask = true;
                continue;
            }
            else if (attribute === 'task-listName') {
                isTask = true;
                continue;
            }
            else if (attribute === 'task-status') {
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
        let variables = {
            userId,
            startDate,
            endDate,
        };
        if (ids?.length > 0) {
            variables.ids = ids;
        }
        const res = await got
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
            conferences = await listConferencesGivenIds(events?.filter((e) => !!e?.conferenceId)?.map((e) => e?.conferenceId));
            attendees = await listAttendeesGivenEventIds(events?.map((e) => e?.id));
        }
        if (isTask) {
            tasks = await listTasksGivenIds(events?.filter((e) => !!e?.taskId)?.map((e) => e?.taskId));
        }
        // return all values
        return {
            events,
            conferences,
            attendees,
            tasks,
            count,
        };
    }
    catch (e) {
        console.log(e, ' listEventsForUser');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBRUEsT0FBTyxFQUFFLFNBQVMsRUFBRSxNQUFNLFVBQVUsQ0FBQztBQUNyQyxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQU0saUNBQWlDLENBQUM7QUFDeEQsT0FBTyxFQUFFLG9CQUFvQixFQUFFLE1BQU0sYUFBYSxDQUFDO0FBQ25ELE9BQU8sRUFBRSxpQkFBaUIsRUFBRSxjQUFjLEVBQUUsTUFBTSx1QkFBdUIsQ0FBQztBQUMxRSxPQUFPLEdBQUcsTUFBTSxLQUFLLENBQUM7QUFFdEIsT0FBTyxvQkFBb0IsTUFBTSxzQ0FBc0MsQ0FBQztBQUV4RSxPQUFPLGNBQWMsTUFBTSxnQ0FBZ0MsQ0FBQztBQUc1RCxPQUFPLHVCQUF1QixNQUFNLHlDQUF5QyxDQUFDO0FBRTlFLE1BQU0sQ0FBQyxNQUFNLHdCQUF3QixHQUFHLENBQ3RDLGNBQWtDLEVBQ2xDLFFBQWdCLEVBQ0ksRUFBRTtJQUN0QixtQkFBbUI7SUFDbkIsTUFBTSxVQUFVLEdBQUcsQ0FBQyxDQUFDO0lBQ3JCLE1BQU0sVUFBVSxHQUFHLGNBQWMsQ0FBQyxVQUFVLENBQUM7SUFDN0MsTUFBTSxRQUFRLEdBQUcsY0FBYyxDQUFDLFFBQVEsQ0FBQztJQUN6QyxNQUFNLFNBQVMsR0FBdUIsRUFBRSxDQUFDO0lBRXpDLE9BQU8sQ0FBQyxHQUFHLENBQUMsVUFBVSxFQUFFLDZDQUE2QyxDQUFDLENBQUM7SUFDdkUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxRQUFRLEVBQUUsMkNBQTJDLENBQUMsQ0FBQztJQUNuRSxPQUFPLENBQUMsR0FBRyxDQUFDLFFBQVEsRUFBRSwyQ0FBMkMsQ0FBQyxDQUFDO0lBRW5FLEtBQUssSUFBSSxDQUFDLEdBQUcsQ0FBQyxFQUFFLENBQUMsR0FBRyxVQUFVLEVBQUUsQ0FBQyxFQUFFLEVBQUUsQ0FBQztRQUNwQyxNQUFNLFlBQVksR0FBRyxD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QyxDQUFDLEVBQUUsWUFBWSxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsWUFBWSxDQUFDLENBQ3RFLENBQUM7WUFDRixTQUFTLEdBQUcsTUFBTSwwQkFBMEIsQ0FBQyxNQUFNLEVBQUUsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQztRQUMxRSxDQUFDO1FBRUQsSUFBSSxNQUFNLEVBQUUsQ0FBQztZQUNYLEtBQUssR0FBRyxNQUFNLGlCQUFpQixDQUM3QixNQUFNLEVBQUUsTUFBTSxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQyxFQUFFLE1BQU0sQ0FBQyxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxFQUFFLE1BQU0sQ0FBQyxDQUMxRCxDQUFDO1FBQ0osQ0FBQztRQUVELG9CQUFvQjtRQUNwQixPQUFPO1lBQ0wsTUFBTTtZQUNOLFdBQVc7WUFDWCxTQUFTO1lBQ1QsS0FBSztZQUNMLEtBQUs7U0FDTixDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxvQkFBb0IsQ0FBQyxDQUFDO0lBQ3ZDLENBQUM7QUFDSCxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBVc2VyUHJlZmVyZW5jZVR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Vc2VyUHJlZmVyZW5jZVR5cGUnO1xuaW1wb3J0IHsgRGF0YUF0dHJpYnV0ZXNUeXBlLCBVc2VyV29ya1RpbWVUeXBlLCB0aW1lIH0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgeyBzZXRJU09EYXkgfSBmcm9tICdkYXRlLWZucyc7XG5pbXBvcnQgeyBkYXlqcyB9IGZyb20gJ0BjaGF0L19saWJzL2RhdGV0aW1lL2RhdGUtdXRpbHMnO1xuaW1wb3J0IHsgZGF5T2ZXZWVrSW50VG9TdHJpbmcgfSBmcm9tICcuL2NvbnN0YW50cyc7XG5pbXBvcnQgeyBoYXN1cmFBZG1pblNlY3JldCwgaGFzdXJhR3JhcGhVcmwgfSBmcm9tICdAY2hhdC9fbGlicy9jb25zdGFudHMnO1xuaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IHsgRXZlbnRUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvRXZlbnRUeXBlJztcbmltcG9ydCBsaXN0Q29uZmVyZW5jZXNCeUlkcyBmcm9tICdAY2hhdC9fbGlicy9ncWwvbGlzdENvbmZlcmVuY2VzQnlJZHMnO1xuaW1wb3J0IHsgQ29uZmVyZW5jZVR5cGUgfSBmcm9tICdAY2hhdC9fbGlicy90eXBlcy9Db25mZXJlbmNlVHlwZSc7XG5pbXBvcnQgbGlzdFRhc2tzQnlJZHMgZnJvbSAnQGNoYXQvX2xpYnMvZ3FsL2xpc3RUYXNrc0J5SWRzJztcbmltcG9ydCB7IFRhc2tUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvVGFza1R5cGUnO1xuaW1wb3J0IHsgQXR0ZW5kZWVUeXBlIH0gZnJvbSAnQGNoYXQvX2xpYnMvdHlwZXMvQXR0ZW5kZWVUeXBlJztcbmltcG9ydCBsaXN0QXR0ZW5kZWVzQnlFdmVudElkcyBmcm9tICdAY2hhdC9fbGlicy9ncWwvbGlzdEF0dGVuZGVlc0J5RXZlbnRJZHMnO1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVXb3JrVGltZXNGb3JVc2VyID0gKFxuICB1c2VyUHJlZmVyZW5jZTogVXNlclByZWZlcmVuY2VUeXBlLFxuICB0aW1lem9uZTogc3RyaW5nXG4pOiBVc2VyV29ya1RpbWVUeXBlW10gPT4ge1xuICAvLyA3IGRheXMgaW4gYSB3ZWVrXG4gIGNvbnN0IGRheXNJbldlZWsgPSA3O1xuICBjb25zdCBzdGFydFRpbWVzID0gdXNlclByZWZlcmVuY2Uuc3RhcnRUaW1lcztcbiAgY29uc3QgZW5kVGltZXMgPSB1c2VyUHJlZmVyZW5jZS5lbmRUaW1lcztcbiAgY29uc3Qgd29ya1RpbWVzOiBVc2VyV29ya1RpbWVUeXBlW10gPSBbXTtcblxuICBjb25zb2xlLmxvZyhzdGFydFRpbWVzLCAnIHN0YXJ0VGltZXMgaW5zaWRlIGdlbmVyYXRlV29ya1RpbWVzRm9yVXNlcicpO1xuICBjb25zb2xlLmxvZyhlbmRUaW1lcywgJyBlbmRUaW1lcyBpbnNpZGUgZ2VuZXJhdGVXb3JrVGltZXNGb3JVc2VyJyk7XG4gIGNvbnNvbGUubG9nKHRpbWV6b25lLCAnIHRpbWV6b25lIGluc2lkZSBnZW5lcmF0ZVdvcmtUaW1lc0ZvclVzZXInKTtcblxuICBmb3IgKGxldCBpID0gMDsgaSA8IGRheXNJbldlZWs7IGkrKykge1xuICAgIGNvbnN0IGRheU9mV2Vla0ludCA9IGkgKyAxO1xuICAgIGNvbnN0IHN0YXJ0SG91ciA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCBzdGFydE1pbnV0ZSA9IHN0YXJ0VGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkubWludXRlcztcbiAgICBjb25zdCBlbmRIb3VyID0gZW5kVGltZXMuZmluZCgoaSkgPT4gaS5kYXkgPT09IGRheU9mV2Vla0ludCkuaG91cjtcbiAgICBjb25zdCBlbmRNaW51dGUgPSBlbmRUaW1lcy5maW5kKChpKSA9PiBpLmRheSA9PT0gZGF5T2ZXZWVrSW50KS5taW51dGVzO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBkYXlPZldlZWtJbnQsXG4gICAgICBkYXlPZldlZWtJbnRUb1N0cmluZ1tkYXlPZldlZWtJbnRdLFxuICAgICAgJyBkYXlPZldlZWtJbnQsIGRheU9mV2Vla0ludFRvU3RyaW5nW2RheU9mV2Vla0ludF0gaW5zaWRlIGdlbmVyYXRlV29ya1RpbWVzRm9yVXNlcidcbiAgICApO1xuICAgIHdvcmtUaW1lcy5wdXNoKHtcbiAgICAgIGRheU9mV2VlazogZGF5T2ZXZWVrSW50VG9TdHJpbmdbZGF5T2ZXZWVrSW50XSxcbiAgICAgIHN0YXJ0VGltZTogZGF5anMoXG4gICAgICAgIHNldElTT0RheShcbiAgICAgICAgICBkYXlqcygpXG4gICAgICAgICAgICAuaG91cihzdGFydEhvdXIpXG4gICAgICAgICAgICAubWludXRlKHN0YXJ0TWludXRlKVxuICAgICAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAgICAgLnRvRGF0ZSgpLFxuICAgICAgICAgIGkgKyAxXG4gICAgICAgIClcbiAgICAgIClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdoOm1tIGEnKSBhcyB0aW1lLFxuICAgICAgZW5kVGltZTogZGF5anMoXG4gICAgICAgIHNldElTT0RheShcbiAgICAgICAgICBkYXlqcygpLmhvdXIoZW5kSG91cikubWludXRlKGVuZE1pbnV0ZSkudHoodGltZXpvbmUsIHRydWUpLnRvRGF0ZSgpLFxuICAgICAgICAgIGkgKyAxXG4gICAgICAgIClcbiAgICAgIClcbiAgICAgICAgLnR6KHRpbWV6b25lKVxuICAgICAgICAuZm9ybWF0KCdoOm1tIGEnKSBhcyB0aW1lLFxuICAgIH0pO1xuICB9XG5cbiAgcmV0dXJuIHdvcmtUaW1lcztcbn07XG5cbmV4cG9ydCBjb25zdCBnZXRVc2VyUHJlZmVyZW5jZXMgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nXG4pOiBQcm9taXNlPFVzZXJQcmVmZXJlbmNlVHlwZSB8IG51bGw+ID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIXVzZXJJZCkge1xuICAgICAgY29uc29sZS5sb2coJ3VzZXJJZCBpcyBudWxsJyk7XG4gICAgICByZXR1cm4gbnVsbDtcbiAgICB9XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdnZXRVc2VyUHJlZmVyZW5jZXMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgIHF1ZXJ5IGdldFVzZXJQcmVmZXJlbmNlcygkdXNlcklkOiB1dWlkISkge1xuICAgICAgVXNlcl9QcmVmZXJlbmNlKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfX0pIHtcbiAgICAgICAgc3RhcnRUaW1lc1xuICAgICAgICBlbmRUaW1lc1xuICAgICAgICBiYWNrVG9CYWNrTWVldGluZ3NcbiAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgIGRlbGV0ZWRcbiAgICAgICAgZm9sbG93VXBcbiAgICAgICAgaWRcbiAgICAgICAgaXNQdWJsaWNDYWxlbmRhclxuICAgICAgICBtYXhOdW1iZXJPZk1lZXRpbmdzXG4gICAgICAgIG1heFdvcmtMb2FkUGVyY2VudFxuICAgICAgICBwdWJsaWNDYWxlbmRhckNhdGVnb3JpZXNcbiAgICAgICAgcmVtaW5kZXJzXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VySWRcbiAgICAgICAgbWluTnVtYmVyT2ZCcmVha3NcbiAgICAgICAgYnJlYWtDb2xvclxuICAgICAgICBicmVha0xlbmd0aFxuICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgb25Cb2FyZGVkXG4gICAgICB9XG4gICAgfSAgICBcbiAgYDtcbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBVc2VyX1ByZWZlcmVuY2U6IFVzZXJQcmVmZXJlbmNlVHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuICAgIHJldHVybiByZXM/LmRhdGE/LlVzZXJfUHJlZmVyZW5jZT8uWzBdO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBnZXRVc2VyUHJlZmVyZW5jZXMnKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEV2ZW50T2JqZWN0Q291bnQgPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBzdGFydERhdGU6IHN0cmluZyxcbiAgZW5kRGF0ZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ0dldEV2ZW50Q291bnQnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgR2V0RXZlbnRDb3VudCgkdXNlcklkOiB1dWlkISwgJHN0YXJ0RGF0ZTogdGltZXN0YW1wISwgJGVuZERhdGU6IHRpbWVzdGFtcCEpIHtcbiAgICAgICAgICAgICAgICBFdmVudF9hZ2dyZWdhdGUod2hlcmU6IHt1c2VySWQ6IHtfZXE6ICR1c2VySWR9LCBzdGFydERhdGU6IHtfbHRlOiAkZW5kRGF0ZX0sIGVuZERhdGU6IHtfZ3RlOiAkc3RhcnREYXRlfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgYWdncmVnYXRlIHtcbiAgICAgICAgICAgICAgICAgICAgY291bnRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cblxuICAgICAgICBgO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnRfYWdncmVnYXQ6IHsgYWdncmVnYXRlOiB7IGNvdW50OiBudW1iZXIgfSB9IH0gfSA9XG4gICAgICBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgICAganNvbjoge1xuICAgICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgIHVzZXJJZCxcbiAgICAgICAgICAgICAgc3RhcnREYXRlLFxuICAgICAgICAgICAgICBlbmREYXRlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cocmVzLCAnIGdvdCBldmVudCBhZ2dyZWdhdGUgY291bnQnKTtcbiAgICByZXR1cm4gcmVzPy5kYXRhPy5FdmVudF9hZ2dyZWdhdD8uYWdncmVnYXRlPy5jb3VudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdWFuYmxlIHRvIGdldCBldmVudCBvYmplY3QgY291bnQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RBdHRlbmRlZXNHaXZlbkV2ZW50SWRzID0gYXN5bmMgKGV2ZW50SWRzOiBzdHJpbmdbXSkgPT4ge1xuICB0cnkge1xuICAgIGlmICghKGV2ZW50SWRzPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIHRhc2sgaWRzIHByb3ZpZGVkIGluc2lkZSBsaXN0VGFza3NHaXZlbklkcycpO1xuICAgICAgcmV0dXJuIFtdO1xuICAgIH1cblxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnbGlzdEF0dGVuZGVlc0J5RXZlbnRJZHMnO1xuICAgIGNvbnN0IHF1ZXJ5ID0gbGlzdEF0dGVuZGVlc0J5RXZlbnRJZHM7XG5cbiAgICBjb25zdCByZXM6IHsgZGF0YTogeyBBdHRlbmRlZTogQXR0ZW5kZWVUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIGV2ZW50SWRzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVzLFxuICAgICAgJyBzdWNjZXNzZnVsbHkgcXVlcmllZCBhdHRlbmRlZSBpbnNpZGUgbGlzdEF0dGVuZGVlc0J5SWRzJ1xuICAgICk7XG5cbiAgICByZXR1cm4gcmVzPy5kYXRhPy5BdHRlbmRlZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgYXR0ZW5kZWVzIGdpdmVuIGlkcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdFRhc2tzR2l2ZW5JZHMgPSBhc3luYyAoaWRzOiBzdHJpbmdbXSkgPT4ge1xuICB0cnkge1xuICAgIGlmICghKGlkcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyB0YXNrIGlkcyBwcm92aWRlZCBpbnNpZGUgbGlzdFRhc2tzR2l2ZW5JZHMnKTtcbiAgICAgIHJldHVybiBbXTtcbiAgICB9XG5cbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2xpc3RUYXNrc0J5SWRzJztcbiAgICBjb25zdCBxdWVyeSA9IGxpc3RUYXNrc0J5SWRzO1xuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgVGFzazogVGFza1R5cGVbXSB9IH0gPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGhhc3VyYUdyYXBoVXJsLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICAnWC1IYXN1cmEtUm9sZSc6ICdhZG1pbicsXG4gICAgICAgIH0sXG4gICAgICAgIGpzb246IHtcbiAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgIHF1ZXJ5LFxuICAgICAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICAgICAgaWRzLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyBzdWNjZXNzZnVsbHkgcXVlcmllZCB0YXNrIGluc2lkZSBsaXN0VGFza3NHaXZlbklkcycpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uVGFzaztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgbGlzdCB0YXNrcyBnaXZlbiBpZHMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGxpc3RDb25mZXJlbmNlc0dpdmVuSWRzID0gYXN5bmMgKGlkczogc3RyaW5nW10pID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAoIShpZHM/Lmxlbmd0aCA+IDApKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gY29uZmVyZW5jZSBpZHMgcHJvdmlkZWQgaW5zaWRlIGxpc3RDb25mZXJlbmNlc0dpdmVuSWRzJyk7XG4gICAgICByZXR1cm4gW107XG4gICAgfVxuXG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdsaXN0Q29uZmVyZW5jZXNCeUlkcyc7XG4gICAgY29uc3QgcXVlcnkgPSBsaXN0Q29uZmVyZW5jZXNCeUlkcztcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IENvbmZlcmVuY2U6IENvbmZlcmVuY2VUeXBlW10gfSB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICAgIGlkcyxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZvciBsaXN0Q29uZmVyZW5jZXNHaXZlbklkcycpO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uQ29uZmVyZW5jZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgY29uZmVyZW5jZXMgZ2l2ZW4gaWRzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBsaXN0U29ydGVkT2JqZWN0c0ZvclVzZXJHaXZlbkRhdGVzQW5kQXR0cmlidXRlcyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICBlbmREYXRlOiBzdHJpbmcsXG4gIGF0dHJpYnV0ZXM6IERhdGFBdHRyaWJ1dGVzVHlwZVtdLFxuICBpc01lZXRpbmc6IGJvb2xlYW4sXG4gIGlkczogc3RyaW5nW10gPSBbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgaWYgKCEoYXR0cmlidXRlcz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCcgbm8gYXR0cmlidXRlcyBmb3VuZCcpO1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGxldCBldmVudEF0dHJpYnV0ZXNTdHJpbmcgPSAnJztcblxuICAgIGxldCBpc0NvdW50ID0gZmFsc2U7XG4gICAgbGV0IGNvdW50ID0gMDtcblxuICAgIGxldCBpc0FsbEF0dHJpYnV0ZXMgPSBmYWxzZTtcblxuICAgIGxldCBpc05vbmUgPSBmYWxzZTtcblxuICAgIGxldCBpc0NvbmZlcmVuY2UgPSBmYWxzZTtcbiAgICBsZXQgY29uZmVyZW5jZXM6IENvbmZlcmVuY2VUeXBlW10gPSBbXTtcbiAgICBsZXQgYXR0ZW5kZWVzOiBBdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gICAgbGV0IGlzVGFzayA9IGZhbHNlO1xuICAgIGxldCB0YXNrczogVGFza1R5cGVbXSA9IFtdO1xuXG4gICAgY29uc3QgYWxsQXR0cmlidXRlcyA9IGBcbiAgICAgICAgICAgIGFsbERheVxuICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgYXR0YWNobWVudHNcbiAgICAgICAgICAgIGF0dGVuZGVlc09taXR0ZWRcbiAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICBjb3B5QXZhaWxhYmlsaXR5XG4gICAgICAgICAgICBjb3B5Q2F0ZWdvcmllc1xuICAgICAgICAgICAgY29weUR1cmF0aW9uXG4gICAgICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgIGNvcHlSZW1pbmRlcnNcbiAgICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgIGNvcHlUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGNyZWF0b3JcbiAgICAgICAgICAgIGRhaWx5VGFza0xpc3RcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICBlbmREYXRlXG4gICAgICAgICAgICBlbmRUaW1lVW5zcGVjaWZpZWRcbiAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgIGV2ZW50VHlwZVxuICAgICAgICAgICAgZXh0ZW5kZWRQcm9wZXJ0aWVzXG4gICAgICAgICAgICBmb2xsb3dVcEV2ZW50SWRcbiAgICAgICAgICAgIGZvckV2ZW50SWRcbiAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgICAgICBndWVzdHNDYW5Nb2RpZnlcbiAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICBoYW5nb3V0TGlua1xuICAgICAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgICAgICBodG1sTGlua1xuICAgICAgICAgICAgaUNhbFVJRFxuICAgICAgICAgICAgaWRcbiAgICAgICAgICAgIGlzQnJlYWtcbiAgICAgICAgICAgIGlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICBpc0V4dGVybmFsTWVldGluZ01vZGlmaWFibGVcbiAgICAgICAgICAgIGlzRm9sbG93VXBcbiAgICAgICAgICAgIGlzTWVldGluZ1xuICAgICAgICAgICAgaXNNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgaXNQb3N0RXZlbnRcbiAgICAgICAgICAgIGlzUHJlRXZlbnRcbiAgICAgICAgICAgIGxpbmtzXG4gICAgICAgICAgICBsb2NhdGlvblxuICAgICAgICAgICAgbG9ja2VkXG4gICAgICAgICAgICBtYXhBdHRlbmRlZXNcbiAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgbWV0aG9kXG4gICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICBuZWdhdGl2ZUltcGFjdERheU9mV2Vla1xuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RTY29yZVxuICAgICAgICAgICAgbmVnYXRpdmVJbXBhY3RUaW1lXG4gICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgb3JnYW5pemVyXG4gICAgICAgICAgICBvcmlnaW5hbEFsbERheVxuICAgICAgICAgICAgb3JpZ2luYWxTdGFydERhdGVcbiAgICAgICAgICAgIG9yaWdpbmFsVGltZXpvbmVcbiAgICAgICAgICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFNjb3JlXG4gICAgICAgICAgICBwb3NpdGl2ZUltcGFjdFRpbWVcbiAgICAgICAgICAgIHBvc3RFdmVudElkXG4gICAgICAgICAgICBwcmVFdmVudElkXG4gICAgICAgICAgICBwcmVmZXJyZWREYXlPZldlZWtcbiAgICAgICAgICAgIHByZWZlcnJlZEVuZFRpbWVSYW5nZVxuICAgICAgICAgICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2VcbiAgICAgICAgICAgIHByZWZlcnJlZFRpbWVcbiAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICBwcml2YXRlQ29weVxuICAgICAgICAgICAgcmVjdXJyZW5jZVxuICAgICAgICAgICAgcmVjdXJyZW5jZVJ1bGVcbiAgICAgICAgICAgIHJlY3VycmluZ0V2ZW50SWRcbiAgICAgICAgICAgIHNlbmRVcGRhdGVzXG4gICAgICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgICAgIHNvdXJjZVxuICAgICAgICAgICAgc3RhcnREYXRlXG4gICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgIHN1bW1hcnlcbiAgICAgICAgICAgIHRhc2tJZFxuICAgICAgICAgICAgdGFza1R5cGVcbiAgICAgICAgICAgIHRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgIHVubGlua1xuICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICB1c2VEZWZhdWx0QWxhcm1zXG4gICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eVxuICAgICAgICAgICAgdXNlck1vZGlmaWVkQ2F0ZWdvcmllc1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkRHVyYXRpb25cbiAgICAgICAgICAgIHVzZXJNb2RpZmllZElzQnJlYWtcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRJc01lZXRpbmdcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZE1vZGlmaWFibGVcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZFByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZFJlbWluZGVyc1xuICAgICAgICAgICAgdXNlck1vZGlmaWVkVGltZUJsb2NraW5nXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgdmlzaWJpbGl0eVxuICAgICAgICAgICAgd2Vla2x5VGFza0xpc3RcbiAgICAgICAgICAgIGJ5V2Vla0RheVxuICAgICAgICAgICAgbG9jYWxTeW5jZWRcbiAgICAgICAgICAgIHVzZXJNb2RpZmllZENvbG9yXG4gICAgICAgICAgICBjb3B5Q29sb3JcbiAgICAgICAgICAgIGNvcHlFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgICAgICB1c2VyTW9kaWZpZWRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICBgO1xuXG4gICAgZm9yIChjb25zdCBhdHRyaWJ1dGUgb2YgYXR0cmlidXRlcykge1xuICAgICAgaWYgKGF0dHJpYnV0ZSA9PT0gJ2FsbERheScpIHtcbiAgICAgICAgZXZlbnRBdHRyaWJ1dGVzU3RyaW5nICs9ICdhbGxEYXknICsgJ1xcbic7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICdjb3VudCcpIHtcbiAgICAgICAgaXNDb3VudCA9IHRydWU7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICdhbGwnKSB7XG4gICAgICAgIGlzQWxsQXR0cmlidXRlcyA9IHRydWU7XG4gICAgICAgIGJyZWFrO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICdub25lJykge1xuICAgICAgICBpc05vbmUgPSB0cnVlO1xuICAgICAgICBicmVhaztcbiAgICAgIH0gZWxzZSBpZiAoYXR0cmlidXRlID09PSAnaWQnKSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICd1c2VySWQnKSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICd0aXRsZScpIHtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9IGVsc2UgaWYgKGF0dHJpYnV0ZSA9PT0gJ3N0YXJ0RGF0ZScpIHtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9IGVsc2UgaWYgKGF0dHJpYnV0ZSA9PT0gJ2VuZERhdGUnKSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICdub3RlcycpIHtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9IGVsc2UgaWYgKGF0dHJpYnV0ZSA9PT0gJ3RpbWV6b25lJykge1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH0gZWxzZSBpZiAoYXR0cmlidXRlID09PSAndGFza0lkJykge1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH0gZWxzZSBpZiAoYXR0cmlidXRlID09PSAnY29uZmVyZW5jZUlkJykge1xuICAgICAgICBpc0NvbmZlcmVuY2UgPSB0cnVlO1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH0gZWxzZSBpZiAoYXR0cmlidXRlID09PSAnZHVyYXRpb24nKSB7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICdjb25mZXJlbmNlLW5hbWUnKSB7XG4gICAgICAgIGlzQ29uZmVyZW5jZSA9IHRydWU7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICdjb25mZXJlbmNlLW5vdGVzJykge1xuICAgICAgICBpc0NvbmZlcmVuY2UgPSB0cnVlO1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH0gZWxzZSBpZiAoYXR0cmlidXRlID09PSAnY29uZmVyZW5jZS1qb2luVXJsJykge1xuICAgICAgICBpc0NvbmZlcmVuY2UgPSB0cnVlO1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH0gZWxzZSBpZiAoYXR0cmlidXRlID09PSAnY29uZmVyZW5jZS1zdGFydFVybCcpIHtcbiAgICAgICAgaXNDb25mZXJlbmNlID0gdHJ1ZTtcbiAgICAgICAgY29udGludWU7XG4gICAgICB9IGVsc2UgaWYgKGF0dHJpYnV0ZSA9PT0gJ3Rhc2snKSB7XG4gICAgICAgIGlzVGFzayA9IHRydWU7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfSBlbHNlIGlmIChhdHRyaWJ1dGUgPT09ICd0YXNrLWxpc3ROYW1lJykge1xuICAgICAgICBpc1Rhc2sgPSB0cnVlO1xuICAgICAgICBjb250aW51ZTtcbiAgICAgIH0gZWxzZSBpZiAoYXR0cmlidXRlID09PSAndGFzay1zdGF0dXMnKSB7XG4gICAgICAgIGlzVGFzayA9IHRydWU7XG4gICAgICAgIGNvbnRpbnVlO1xuICAgICAgfVxuICAgICAgZXZlbnRBdHRyaWJ1dGVzU3RyaW5nICs9IGF0dHJpYnV0ZSArICdcXG4nO1xuICAgIH1cblxuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnbGlzdEV2ZW50c0ZvclVzZXInO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgICAgICAgcXVlcnkgbGlzdEV2ZW50c0ZvclVzZXIoJHtpZHM/Lmxlbmd0aCA+IDAgPyAnJGlkczogW1N0cmluZyFdISwgJyA6ICcnfSR1c2VySWQ6IHV1aWQhLCAkc3RhcnREYXRlOiB0aW1lc3RhbXAhLCAkZW5kRGF0ZTogdGltZXN0YW1wISkge1xuICAgICAgICAgICAgICAgIEV2ZW50KHdoZXJlOiB7JHtpZHM/Lmxlbmd0aCA+IDAgPyAnaWQ6IHtfaW46ICRpZHN9LCAnIDogJyd9dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgZW5kRGF0ZToge19ndGU6ICRzdGFydERhdGV9LCBzdGFydERhdGU6IHtfbHRlOiAkZW5kRGF0ZX0sIGRlbGV0ZWQ6IHtfbmVxOiB0cnVlfX0sIG9yZGVyX2J5OiB7c3RhcnREYXRlOiBhc2N9KSB7XG4gICAgICAgICAgICAgICAgICAgIGNhbGVuZGFySWRcbiAgICAgICAgICAgICAgICAgICAgY29uZmVyZW5jZUlkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGVuZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBub3Rlc1xuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0YXNrSWRcbiAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgdGl0bGVcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICAkeyFpc05vbmUgJiYgZXZlbnRBdHRyaWJ1dGVzU3RyaW5nfVxuICAgICAgICAgICAgICAgICAgICAkeyFpc05vbmUgJiYgaXNBbGxBdHRyaWJ1dGVzICYmIGFsbEF0dHJpYnV0ZXN9XG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICBgO1xuICAgIGxldCB2YXJpYWJsZXM6IGFueSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIGVuZERhdGUsXG4gICAgfTtcblxuICAgIGlmIChpZHM/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHZhcmlhYmxlcy5pZHMgPSBpZHM7XG4gICAgfVxuXG4gICAgY29uc3QgcmVzOiB7IGRhdGE6IHsgRXZlbnQ6IEV2ZW50VHlwZVtdIH0gfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gbGlzdEV2ZW50c2ZvclVzZXInKTtcblxuICAgIGNvbnN0IGV2ZW50cyA9IHJlcz8uZGF0YT8uRXZlbnQ7XG5cbiAgICBpZiAoaXNDb3VudCkge1xuICAgICAgY291bnQgPSBhd2FpdCBnZXRFdmVudE9iamVjdENvdW50KHVzZXJJZCwgc3RhcnREYXRlLCBlbmREYXRlKTtcbiAgICB9XG5cbiAgICBpZiAoaXNDb25mZXJlbmNlIHx8IGlzTWVldGluZykge1xuICAgICAgY29uZmVyZW5jZXMgPSBhd2FpdCBsaXN0Q29uZmVyZW5jZXNHaXZlbklkcyhcbiAgICAgICAgZXZlbnRzPy5maWx0ZXIoKGUpID0+ICEhZT8uY29uZmVyZW5jZUlkKT8ubWFwKChlKSA9PiBlPy5jb25mZXJlbmNlSWQpXG4gICAgICApO1xuICAgICAgYXR0ZW5kZWVzID0gYXdhaXQgbGlzdEF0dGVuZGVlc0dpdmVuRXZlbnRJZHMoZXZlbnRzPy5tYXAoKGUpID0+IGU/LmlkKSk7XG4gICAgfVxuXG4gICAgaWYgKGlzVGFzaykge1xuICAgICAgdGFza3MgPSBhd2FpdCBsaXN0VGFza3NHaXZlbklkcyhcbiAgICAgICAgZXZlbnRzPy5maWx0ZXIoKGUpID0+ICEhZT8udGFza0lkKT8ubWFwKChlKSA9PiBlPy50YXNrSWQpXG4gICAgICApO1xuICAgIH1cblxuICAgIC8vIHJldHVybiBhbGwgdmFsdWVzXG4gICAgcmV0dXJuIHtcbiAgICAgIGV2ZW50cyxcbiAgICAgIGNvbmZlcmVuY2VzLFxuICAgICAgYXR0ZW5kZWVzLFxuICAgICAgdGFza3MsXG4gICAgICBjb3VudCxcbiAgICB9O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBsaXN0RXZlbnRzRm9yVXNlcicpO1xuICB9XG59O1xuIl19