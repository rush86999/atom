import got from 'got';
import { hasuraAdminSecret, hasuraGraphUrl } from './constants';
import { v4 as uuid } from 'uuid';
import * as pkg from 'rrule';
import { interopDefault } from 'mlly';
const { RRule } = interopDefault(pkg);
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);
export const generatePreferredTimesForRecurringMeetingAssist = (originalPreferredTimes, recurringMeetingAssist, recurringAttendee) => {
    console.log(originalPreferredTimes, recurringMeetingAssist, ' originalPreferredTimes, recurringMeetingAssist');
    const recurringPreferredTimes = [];
    for (const preferredTime of originalPreferredTimes) {
        const recurringPreferredTime = {
            id: uuid(),
            meetingId: recurringMeetingAssist?.id,
            startTime: preferredTime?.startTime,
            endTime: preferredTime?.endTime,
            updatedAt: dayjs().format(),
            createdDate: dayjs().format(),
            hostId: recurringMeetingAssist?.userId,
            attendeeId: recurringAttendee?.id,
        };
        if (preferredTime?.dayOfWeek && preferredTime?.dayOfWeek > 0) {
            recurringPreferredTime.dayOfWeek = preferredTime.dayOfWeek;
        }
        recurringPreferredTimes.push(recurringPreferredTime);
    }
    return recurringPreferredTimes;
};
export const generateAttendeesAndPreferredTimesForRecurringMeetingAssist = (originalAttendees, recurringMeetingAssist, originalPreferredTimes) => {
    console.log(originalAttendees, recurringMeetingAssist, originalPreferredTimes, ' originalAttendees, recurringMeetingAssist, originalPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist before');
    const recurringAttendees = [];
    const recurringPreferredTimes = [];
    for (const originalAttendee of originalAttendees) {
        const recurringAttendee = {
            id: uuid(),
            name: originalAttendee?.name,
            hostId: originalAttendee?.hostId,
            userId: originalAttendee?.userId,
            emails: originalAttendee?.emails,
            contactId: originalAttendee?.contactId,
            phoneNumbers: originalAttendee?.phoneNumbers,
            imAddresses: originalAttendee?.imAddresses,
            meetingId: recurringMeetingAssist?.id,
            createdDate: dayjs().format(),
            updatedAt: dayjs().format(),
            timezone: recurringMeetingAssist?.timezone,
            externalAttendee: originalAttendee?.externalAttendee,
            primaryEmail: originalAttendee?.primaryEmail,
        };
        const attendeeIndex = originalPreferredTimes?.findIndex((o) => o?.attendeeId === originalAttendee?.id);
        console.log(attendeeIndex, ' attendeeIndex inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist');
        console.log(originalPreferredTimes, ' originalPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist');
        if (originalPreferredTimes &&
            originalPreferredTimes?.length > 0 &&
            typeof attendeeIndex === 'number' &&
            attendeeIndex > -1) {
            const recurringPreferredTimesForAttendee = generatePreferredTimesForRecurringMeetingAssist(originalPreferredTimes?.filter((o) => o?.attendeeId === originalAttendee?.id), recurringMeetingAssist, recurringAttendee);
            recurringPreferredTimes.push(...recurringPreferredTimesForAttendee);
        }
        recurringAttendees.push(recurringAttendee);
    }
    console.log(recurringAttendees, ' recurringAttendees after inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist');
    console.log(recurringPreferredTimes, ' recurringPreferredTimes after inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist');
    return { recurringAttendees, recurringPreferredTimes };
};
export const generateAttendeesAndPreferredTimesForRecurringMeetingAssists = (originalAttendees, recurringMeetingAssists, originalPreferredTimes) => {
    const recurringAttendees = [];
    const recurringPreferredTimes = [];
    console.log(recurringAttendees, ' recurringAttendees inside generateAttendeesForRecurringMeetingAssists before');
    for (const recurringMeetingAssist of recurringMeetingAssists) {
        const newRecurringAttendeesAndPreferredTimes = generateAttendeesAndPreferredTimesForRecurringMeetingAssist(originalAttendees, recurringMeetingAssist, originalPreferredTimes);
        recurringAttendees.push(...newRecurringAttendeesAndPreferredTimes?.recurringAttendees);
        if (newRecurringAttendeesAndPreferredTimes?.recurringPreferredTimes?.length >
            0) {
            recurringPreferredTimes.push(...newRecurringAttendeesAndPreferredTimes?.recurringPreferredTimes);
        }
    }
    console.log(recurringAttendees, ' recurringAttendees inside generateAttendeesAndPreferredTimesForRecurringMeetingAssists after');
    console.log(recurringPreferredTimes, ' recurringPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssists after generation');
    return { recurringAttendees, recurringPreferredTimes };
};
export const insertMeetingAssists = async (meetingAssists) => {
    try {
        console.log(meetingAssists, 'insertMeetingAssists called');
        const operationName = 'InsertMeetingAssist';
        const query = `
            mutation InsertMeetingAssist($meetingAssists: [Meeting_Assist_insert_input!]!) {
                insert_Meeting_Assist(objects: $meetingAssists) {
                    affected_rows
                    returning {
                    allowAttendeeUpdatePreferences
                    anyoneCanAddSelf
                    attendeeCanModify
                    attendeeCount
                    attendeeRespondedCount
                    backgroundColor
                    bufferTime
                    calendarId
                    cancelIfAnyRefuse
                    cancelled
                    colorId
                    conferenceApp
                    createdDate
                    duration
                    enableAttendeePreferences
                    enableConference
                    enableHostPreferences
                    endDate
                    eventId
                    expireDate
                    foregroundColor
                    frequency
                    guaranteeAvailability
                    guestsCanInviteOthers
                    guestsCanSeeOtherGuests
                    id
                    interval
                    location
                    minThresholdCount
                    notes
                    originalMeetingId
                    priority
                    reminders
                    sendUpdates
                    startDate
                    summary
                    timezone
                    transparency
                    until
                    updatedAt
                    useDefaultAlarms
                    userId
                    visibility
                    windowEndDate
                    windowStartDate
                    }
                }
            }
        `;
        const variables = {
            meetingAssists,
        };
        const res = await got
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
        console.log(res?.data?.insert_Meeting_Assist?.affected_rows, ' successfully added recurring meeting assists');
        return res?.data?.insert_Meeting_Assist?.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable insert meeting assists');
    }
};
export const listMeetingAssistAttendeesGivenMeetingId = async (meetingId) => {
    try {
        const operationName = 'ListMeetingAssistAttendeesByMeetingId';
        const query = `
            query ListMeetingAssistAttendeesByMeetingId($meetingId: uuid!) {
                Meeting_Assist_Attendee(where: {meetingId: {_eq: $meetingId}}) {
                    contactId
                    createdDate
                    emails
                    externalAttendee
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    timezone
                    updatedAt
                    userId
                    primaryEmail
                }
            }
        `;
        const variables = {
            meetingId,
        };
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
        console.log(res, ' res from listMeetingAssistAttendees ');
        return res?.data?.Meeting_Assist_Attendee;
    }
    catch (e) {
        console.log(e, ' unable to list meeting assist attendees');
    }
};
export const getRruleFreq = (freq) => {
    switch (freq) {
        case 'daily':
            return RRule.DAILY;
        case 'weekly':
            return RRule.WEEKLY;
        case 'monthly':
            return RRule.MONTHLY;
        case 'yearly':
            return RRule.YEARLY;
    }
};
export const generateDatesForFutureMeetingAssistsUsingRrule = (windowStartDate, windowEndDate, frequency, interval, until) => {
    const ruleStartDate = new RRule({
        dtstart: dayjs(windowStartDate).utc().toDate(),
        freq: getRruleFreq(frequency),
        interval,
        until: dayjs(until).utc().toDate(),
    });
    console.log(ruleStartDate, ' ruleStartDate inside generateDatesForFutureMeetingAssistsUsingRrule');
    const windowStartDatesForRecurrence = ruleStartDate
        .all()
        ?.map((d) => dayjs.utc(d).format());
    windowStartDatesForRecurrence?.forEach((e) => console.log(e, ' windowDateforrecurrence inside generateDatesForFutureMeetingAssistsUsingRrule'));
    const ruleEndDate = new RRule({
        dtstart: dayjs(windowEndDate).utc().toDate(),
        freq: getRruleFreq(frequency),
        interval,
        until: dayjs(until).utc().toDate(),
    });
    console.log(ruleEndDate, ' ruleEndDate inside generateDatesForFutureMeetingAssistsUsingRrule');
    const windowEndDatesForRecurrence = ruleEndDate
        .all()
        ?.map((d) => dayjs.utc(d).format());
    windowEndDatesForRecurrence?.forEach((e) => console.log(e, ' windowEndDateforrecurrence inside generateDatesForFutureMeetingAssistsUsingRrule'));
    // reformat into windowStartDates and windowEndDates
    const timeWindows = windowStartDatesForRecurrence
        ?.slice(0, windowEndDatesForRecurrence?.length)
        ?.map((windowStartDate, inx) => {
        return {
            windowStartDate,
            windowEndDate: windowEndDatesForRecurrence?.[inx],
        };
    });
    return timeWindows;
};
export const generateRecurringMeetingAssists = (originalMeetingAssist) => {
    // validate
    if (!originalMeetingAssist?.frequency) {
        console.log('no frequency present inside generateRecurringMeetingAssists');
        return;
    }
    if (!originalMeetingAssist?.interval) {
        console.log('no internval present inside generateRecurringMeetingAssists');
        return;
    }
    if (!originalMeetingAssist?.until) {
        console.log('no until present inside generateRecurringMeetingAssists');
        return;
    }
    console.log('generateRecurringMeetingAssists called');
    const recurringMeetingAssists = [];
    const timeWindows = generateDatesForFutureMeetingAssistsUsingRrule(originalMeetingAssist?.windowStartDate, originalMeetingAssist?.windowEndDate, originalMeetingAssist?.frequency, originalMeetingAssist?.interval, originalMeetingAssist?.until);
    console.log(timeWindows, ' timeWindows inside generateRecurringMeetingAssists');
    for (let i = 0; i < timeWindows.length; i++) {
        if (i === 0) {
            continue;
        }
        const meetingId = uuid();
        const newRecurringMeetingAssist = {
            id: meetingId,
            userId: originalMeetingAssist?.userId,
            summary: originalMeetingAssist?.summary,
            notes: originalMeetingAssist?.notes,
            windowStartDate: timeWindows[i]?.windowStartDate,
            windowEndDate: timeWindows[i]?.windowEndDate,
            timezone: originalMeetingAssist?.timezone,
            location: originalMeetingAssist?.location,
            priority: 1,
            enableConference: originalMeetingAssist?.enableConference,
            conferenceApp: originalMeetingAssist?.conferenceApp,
            sendUpdates: originalMeetingAssist?.sendUpdates,
            guestsCanInviteOthers: originalMeetingAssist?.guestsCanInviteOthers,
            transparency: originalMeetingAssist?.transparency,
            visibility: originalMeetingAssist?.visibility,
            createdDate: dayjs().format(),
            updatedAt: dayjs().format(),
            colorId: originalMeetingAssist?.colorId,
            backgroundColor: originalMeetingAssist?.backgroundColor,
            foregroundColor: originalMeetingAssist?.foregroundColor,
            useDefaultAlarms: originalMeetingAssist?.useDefaultAlarms,
            reminders: originalMeetingAssist?.reminders,
            cancelIfAnyRefuse: originalMeetingAssist?.cancelIfAnyRefuse,
            enableHostPreferences: originalMeetingAssist?.enableHostPreferences,
            enableAttendeePreferences: originalMeetingAssist?.enableAttendeePreferences,
            attendeeCanModify: originalMeetingAssist?.attendeeCanModify,
            expireDate: originalMeetingAssist?.expireDate,
            cancelled: originalMeetingAssist?.cancelled,
            duration: originalMeetingAssist?.duration,
            calendarId: originalMeetingAssist?.calendarId,
            bufferTime: originalMeetingAssist?.bufferTime,
            anyoneCanAddSelf: originalMeetingAssist?.anyoneCanAddSelf,
            guestsCanSeeOtherGuests: originalMeetingAssist?.guestsCanSeeOtherGuests,
            minThresholdCount: originalMeetingAssist?.minThresholdCount,
            guaranteeAvailability: originalMeetingAssist?.guaranteeAvailability,
            frequency: originalMeetingAssist?.frequency,
            interval: originalMeetingAssist?.interval,
            until: originalMeetingAssist?.until,
            originalMeetingId: originalMeetingAssist?.id,
            attendeeRespondedCount: originalMeetingAssist?.attendeeRespondedCount,
            attendeeCount: originalMeetingAssist?.attendeeCount,
        };
        recurringMeetingAssists.push(newRecurringMeetingAssist);
    }
    recurringMeetingAssists?.forEach((a) => console.log(a, ' recurringMeetingAssist inside generateRecurringMeetingAssists'));
    return recurringMeetingAssists;
};
export const insertMeetingAssistAttendees = async (attendees) => {
    try {
        console.log(attendees, ' attendees called inside insertMeetingAssistAttendees');
        const operationName = 'InsertMeetingAssistAttendees';
        const query = `
            mutation InsertMeetingAssistAttendees($attendees: [Meeting_Assist_Attendee_insert_input!]!) {
                insert_Meeting_Assist_Attendee(objects: $attendees) {
                    affected_rows
                    returning {
                    contactId
                    createdDate
                    emails
                    externalAttendee
                    hostId
                    id
                    imAddresses
                    meetingId
                    name
                    phoneNumbers
                    primaryEmail
                    timezone
                    updatedAt
                    userId
                    }
                }
            }
        `;
        const variables = {
            attendees,
        };
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
        console.log(res, ' res from insert_Meeting_Assist_Attendee');
        return res?.data?.insert_Meeting_Assist_Attendee?.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable to insert meeting assist attendees');
    }
};
export const upsertMeetingAssistPreferredTimes = async (preferredTimes) => {
    try {
        console.log(preferredTimes, ' preferredTimes inside upsertMeetingAssistPreferredTimes');
        const operationName = 'insertMeetingAssistPreferredTimes';
        const query = `
            mutation insertMeetingAssistPreferredTimes($preferredTimes: [Meeting_Assist_Preferred_Time_Range_insert_input!]!) {
                insert_Meeting_Assist_Preferred_Time_Range(objects: $preferredTimes, 
                    on_conflict: {
                    constraint: Meeting_Assist_Preferred_Time_Ranges_pkey, 
                    update_columns: [
                        attendeeId,
                        dayOfWeek,
                        endTime,
                        hostId,
                        meetingId,
                        startTime,
                        updatedAt,
                    ]
                    }) {
                    affected_rows
                    returning {
                        attendeeId
                        createdDate
                        dayOfWeek
                        endTime
                        hostId
                        id
                        meetingId
                        startTime
                        updatedAt
                    }
                }
            }
        `;
        const variables = {
            preferredTimes: preferredTimes?.map((pt) => ({
                ...pt,
                dayOfWeek: pt?.dayOfWeek === -1 ? null : pt?.dayOfWeek,
            })),
        };
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
        console.log(res, ' res from upsertMeetingAsistPreferredTimes ');
        return res?.data?.insert_Meeting_Assist_Preferred_Time_Range?.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable to upsertMeetingAssistPreferredTimes');
    }
};
export const createRecurringMeetingAssists = async (originalMeetingAssist, originalPreferredTimes) => {
    try {
        console.log('createRecurringMeetingAssists called');
        console.log(originalPreferredTimes, ' originalPreferredTimes  inside createRecurringMeetingAssists');
        const meetingAssistAttendees = await listMeetingAssistAttendeesGivenMeetingId(originalMeetingAssist?.id);
        console.log(meetingAssistAttendees, ' meetingAssistAttendees inside createRecurringMeetingAssists');
        if (!(meetingAssistAttendees && meetingAssistAttendees?.length > 0)) {
            console.log('no attendees is present');
            return;
        }
        const recurringMeetingAssists = generateRecurringMeetingAssists(originalMeetingAssist);
        console.log(recurringMeetingAssists, ' recurringMeetingAssists');
        if (!(recurringMeetingAssists && recurringMeetingAssists?.length > 0)) {
            console.log('no recurringMeetingassists generated');
            return;
        }
        await insertMeetingAssists(recurringMeetingAssists);
        const recurringMeetingAssistAttendeesAndRecurringPreferredTimes = generateAttendeesAndPreferredTimesForRecurringMeetingAssists(meetingAssistAttendees, recurringMeetingAssists, originalPreferredTimes);
        console.log(recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringAttendees, ' recurringMeetingAssistAttendees');
        console.log(recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringPreferredTimes, ' recurringPreferredTimes');
        await insertMeetingAssistAttendees(recurringMeetingAssistAttendeesAndRecurringPreferredTimes.recurringAttendees);
        if (recurringMeetingAssistAttendeesAndRecurringPreferredTimes
            ?.recurringPreferredTimes?.length > 0) {
            await upsertMeetingAssistPreferredTimes(recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringPreferredTimes);
        }
    }
    catch (e) {
        console.log(e, ' unable to create recurring meeting assist');
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBQ3RCLE9BQU8sRUFBRSxpQkFBaUIsRUFBRSxjQUFjLEVBQUUsTUFBTSxhQUFhLENBQUM7QUFPaEUsT0FBTyxFQUFFLEVBQUUsSUFBSSxJQUFJLEVBQUUsTUFBTSxNQUFNLENBQUM7QUFDbEMsT0FBTyxLQUFLLEdBQUcsTUFBTSxPQUFPLENBQUM7QUFFN0IsT0FBTyxFQUFFLGNBQWMsRUFBRSxNQUFNLE1BQU0sQ0FBQztBQUN0QyxNQUFNLEVBQUUsS0FBSyxFQUFFLEdBQUcsY0FBYyxDQUFDLEdBQUcsQ0FBQyxDQUFDO0FBQ3RDLE9BQU8sS0FBSyxNQUFNLE9BQU8sQ0FBQztBQUUxQixPQUFPLFFBQVEsTUFBTSx1QkFBdUIsQ0FBQztBQUM3QyxPQUFPLFNBQVMsTUFBTSx3QkFBd0IsQ0FBQztBQUUvQyxPQUFPLFFBQVEsTUFBTSx1QkFBdUIsQ0FBQztBQUM3QyxPQUFPLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQztBQUVuQyxLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsU0FBUyxDQUFDLENBQUM7QUFDeEIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxRQUFRLENBQUMsQ0FBQztBQUN2QixLQUFLLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDO0FBRWxCLE1BQU0sQ0FBQyxNQUFNLCtDQUErQyxHQUFHLENBQzdELHNCQUE2RCxFQUM3RCxzQkFBeUMsRUFDekMsaUJBQTRDLEVBQzVDLEVBQUU7SUFDRixPQUFPLENBQUMsR0FBRyxDQUNULHNCQUFzQixFQUN0QixzQkFBc0IsRUFDdEIsaURBQWlELENBQ2xELENBQUM7SUFFRixNQUFNLHVCQUF1QixHQUEwQyxFQUFFLENBQUM7SUFFMUUsS0FBSyxNQUFNLGFB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LHlEQUF5RCxHQUM3RCw0REFBNEQsQ0FDMUQsc0JBQXNCLEVBQ3RCLHVCQUF1QixFQUN2QixzQkFBc0IsQ0FDdkIsQ0FBQztRQUVKLE9BQU8sQ0FBQyxHQUFHLENBQ1QseURBQXlELEVBQUUsa0JBQWtCLEVBQzdFLGtDQUFrQyxDQUNuQyxDQUFDO1FBQ0YsT0FBTyxDQUFDLEdBQUcsQ0FDVCx5REFBeUQsRUFBRSx1QkFBdUIsRUFDbEYsMEJBQTBCLENBQzNCLENBQUM7UUFFRixNQUFNLDRCQUE0QixDQUNoQyx5REFBeUQsQ0FBQyxrQkFBa0IsQ0FDN0UsQ0FBQztRQUVGLElBQ0UseURBQXlEO1lBQ3ZELEVBQUUsdUJBQXVCLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFDdkMsQ0FBQztZQUNELE1BQU0saUNBQWlDLENBQ3JDLHlEQUF5RCxFQUFFLHVCQUF1QixDQUNuRixDQUFDO1FBQ0osQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsNENBQTRDLENBQUMsQ0FBQztJQUMvRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IHsgaGFzdXJhQWRtaW5TZWNyZXQsIGhhc3VyYUdyYXBoVXJsIH0gZnJvbSAnLi9jb25zdGFudHMnO1xuaW1wb3J0IHtcbiAgTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSxcbiAgTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGUsXG4gIE1lZXRpbmdBc3Npc3RUeXBlLFxuICBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSxcbn0gZnJvbSAnLi90eXBlcyc7XG5pbXBvcnQgeyB2NCBhcyB1dWlkIH0gZnJvbSAndXVpZCc7XG5pbXBvcnQgKiBhcyBwa2cgZnJvbSAncnJ1bGUnO1xuXG5pbXBvcnQgeyBpbnRlcm9wRGVmYXVsdCB9IGZyb20gJ21sbHknO1xuY29uc3QgeyBSUnVsZSB9ID0gaW50ZXJvcERlZmF1bHQocGtnKTtcbmltcG9ydCBkYXlqcyBmcm9tICdkYXlqcyc7XG5cbmltcG9ydCBkdXJhdGlvbiBmcm9tICdkYXlqcy9wbHVnaW4vZHVyYXRpb24nO1xuaW1wb3J0IGlzQmV0d2VlbiBmcm9tICdkYXlqcy9wbHVnaW4vaXNCZXR3ZWVuJztcblxuaW1wb3J0IHRpbWV6b25lIGZyb20gJ2RheWpzL3BsdWdpbi90aW1lem9uZSc7XG5pbXBvcnQgdXRjIGZyb20gJ2RheWpzL3BsdWdpbi91dGMnO1xuXG5kYXlqcy5leHRlbmQoZHVyYXRpb24pO1xuZGF5anMuZXh0ZW5kKGlzQmV0d2Vlbik7XG5kYXlqcy5leHRlbmQodGltZXpvbmUpO1xuZGF5anMuZXh0ZW5kKHV0Yyk7XG5cbmV4cG9ydCBjb25zdCBnZW5lcmF0ZVByZWZlcnJlZFRpbWVzRm9yUmVjdXJyaW5nTWVldGluZ0Fzc2lzdCA9IChcbiAgb3JpZ2luYWxQcmVmZXJyZWRUaW1lczogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSxcbiAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGUsXG4gIHJlY3VycmluZ0F0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlXG4pID0+IHtcbiAgY29uc29sZS5sb2coXG4gICAgb3JpZ2luYWxQcmVmZXJyZWRUaW1lcyxcbiAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0LFxuICAgICcgb3JpZ2luYWxQcmVmZXJyZWRUaW1lcywgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdCdcbiAgKTtcblxuICBjb25zdCByZWN1cnJpbmdQcmVmZXJyZWRUaW1lczogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXSA9IFtdO1xuXG4gIGZvciAoY29uc3QgcHJlZmVycmVkVGltZSBvZiBvcmlnaW5hbFByZWZlcnJlZFRpbWVzKSB7XG4gICAgY29uc3QgcmVjdXJyaW5nUHJlZmVycmVkVGltZTogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGUgPSB7XG4gICAgICBpZDogdXVpZCgpLFxuICAgICAgbWVldGluZ0lkOiByZWN1cnJpbmdNZWV0aW5nQXNzaXN0Py5pZCxcbiAgICAgIHN0YXJ0VGltZTogcHJlZmVycmVkVGltZT8uc3RhcnRUaW1lLFxuICAgICAgZW5kVGltZTogcHJlZmVycmVkVGltZT8uZW5kVGltZSxcbiAgICAgIHVwZGF0ZWRBdDogZGF5anMoKS5mb3JtYXQoKSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgaG9zdElkOiByZWN1cnJpbmdNZWV0aW5nQXNzaXN0Py51c2VySWQsXG4gICAgICBhdHRlbmRlZUlkOiByZWN1cnJpbmdBdHRlbmRlZT8uaWQsXG4gICAgfTtcblxuICAgIGlmIChwcmVmZXJyZWRUaW1lPy5kYXlPZldlZWsgJiYgcHJlZmVycmVkVGltZT8uZGF5T2ZXZWVrID4gMCkge1xuICAgICAgcmVjdXJyaW5nUHJlZmVycmVkVGltZS5kYXlPZldlZWsgPSBwcmVmZXJyZWRUaW1lLmRheU9mV2VlaztcbiAgICB9XG5cbiAgICByZWN1cnJpbmdQcmVmZXJyZWRUaW1lcy5wdXNoKHJlY3VycmluZ1ByZWZlcnJlZFRpbWUpO1xuICB9XG5cbiAgcmV0dXJuIHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzO1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXNGb3JSZWN1cnJpbmdNZWV0aW5nQXNzaXN0ID0gKFxuICBvcmlnaW5hbEF0dGVuZGVlczogTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZVtdLFxuICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0OiBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgb3JpZ2luYWxQcmVmZXJyZWRUaW1lcz86IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW11cbikgPT4ge1xuICBjb25zb2xlLmxvZyhcbiAgICBvcmlnaW5hbEF0dGVuZGVlcyxcbiAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0LFxuICAgIG9yaWdpbmFsUHJlZmVycmVkVGltZXMsXG4gICAgJyBvcmlnaW5hbEF0dGVuZGVlcywgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdCwgb3JpZ2luYWxQcmVmZXJyZWRUaW1lcyBpbnNpZGUgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3QgYmVmb3JlJ1xuICApO1xuICBjb25zdCByZWN1cnJpbmdBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSA9IFtdO1xuXG4gIGNvbnN0IHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzOiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVtdID0gW107XG5cbiAgZm9yIChjb25zdCBvcmlnaW5hbEF0dGVuZGVlIG9mIG9yaWdpbmFsQXR0ZW5kZWVzKSB7XG4gICAgY29uc3QgcmVjdXJyaW5nQXR0ZW5kZWU6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUgPSB7XG4gICAgICBpZDogdXVpZCgpLFxuICAgICAgbmFtZTogb3JpZ2luYWxBdHRlbmRlZT8ubmFtZSxcbiAgICAgIGhvc3RJZDogb3JpZ2luYWxBdHRlbmRlZT8uaG9zdElkLFxuICAgICAgdXNlcklkOiBvcmlnaW5hbEF0dGVuZGVlPy51c2VySWQsXG4gICAgICBlbWFpbHM6IG9yaWdpbmFsQXR0ZW5kZWU/LmVtYWlscyxcbiAgICAgIGNvbnRhY3RJZDogb3JpZ2luYWxBdHRlbmRlZT8uY29udGFjdElkLFxuICAgICAgcGhvbmVOdW1iZXJzOiBvcmlnaW5hbEF0dGVuZGVlPy5waG9uZU51bWJlcnMsXG4gICAgICBpbUFkZHJlc3Nlczogb3JpZ2luYWxBdHRlbmRlZT8uaW1BZGRyZXNzZXMsXG4gICAgICBtZWV0aW5nSWQ6IHJlY3VycmluZ01lZXRpbmdBc3Npc3Q/LmlkLFxuICAgICAgY3JlYXRlZERhdGU6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkuZm9ybWF0KCksXG4gICAgICB0aW1lem9uZTogcmVjdXJyaW5nTWVldGluZ0Fzc2lzdD8udGltZXpvbmUsXG4gICAgICBleHRlcm5hbEF0dGVuZGVlOiBvcmlnaW5hbEF0dGVuZGVlPy5leHRlcm5hbEF0dGVuZGVlLFxuICAgICAgcHJpbWFyeUVtYWlsOiBvcmlnaW5hbEF0dGVuZGVlPy5wcmltYXJ5RW1haWwsXG4gICAgfTtcblxuICAgIGNvbnN0IGF0dGVuZGVlSW5kZXggPSBvcmlnaW5hbFByZWZlcnJlZFRpbWVzPy5maW5kSW5kZXgoXG4gICAgICAobykgPT4gbz8uYXR0ZW5kZWVJZCA9PT0gb3JpZ2luYWxBdHRlbmRlZT8uaWRcbiAgICApO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBhdHRlbmRlZUluZGV4LFxuICAgICAgJyBhdHRlbmRlZUluZGV4IGluc2lkZSBnZW5lcmF0ZUF0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzRm9yUmVjdXJyaW5nTWVldGluZ0Fzc2lzdCdcbiAgICApO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgb3JpZ2luYWxQcmVmZXJyZWRUaW1lcyxcbiAgICAgICcgb3JpZ2luYWxQcmVmZXJyZWRUaW1lcyBpbnNpZGUgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3QnXG4gICAgKTtcblxuICAgIGlmIChcbiAgICAgIG9yaWdpbmFsUHJlZmVycmVkVGltZXMgJiZcbiAgICAgIG9yaWdpbmFsUHJlZmVycmVkVGltZXM/Lmxlbmd0aCA+IDAgJiZcbiAgICAgIHR5cGVvZiBhdHRlbmRlZUluZGV4ID09PSAnbnVtYmVyJyAmJlxuICAgICAgYXR0ZW5kZWVJbmRleCA+IC0xXG4gICAgKSB7XG4gICAgICBjb25zdCByZWN1cnJpbmdQcmVmZXJyZWRUaW1lc0ZvckF0dGVuZGVlID1cbiAgICAgICAgZ2VuZXJhdGVQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3QoXG4gICAgICAgICAgb3JpZ2luYWxQcmVmZXJyZWRUaW1lcz8uZmlsdGVyKFxuICAgICAgICAgICAgKG8pID0+IG8/LmF0dGVuZGVlSWQgPT09IG9yaWdpbmFsQXR0ZW5kZWU/LmlkXG4gICAgICAgICAgKSxcbiAgICAgICAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0LFxuICAgICAgICAgIHJlY3VycmluZ0F0dGVuZGVlXG4gICAgICAgICk7XG5cbiAgICAgIHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzLnB1c2goLi4ucmVjdXJyaW5nUHJlZmVycmVkVGltZXNGb3JBdHRlbmRlZSk7XG4gICAgfVxuXG4gICAgcmVjdXJyaW5nQXR0ZW5kZWVzLnB1c2gocmVjdXJyaW5nQXR0ZW5kZWUpO1xuICB9XG5cbiAgY29uc29sZS5sb2coXG4gICAgcmVjdXJyaW5nQXR0ZW5kZWVzLFxuICAgICcgcmVjdXJyaW5nQXR0ZW5kZWVzIGFmdGVyIGluc2lkZSBnZW5lcmF0ZUF0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzRm9yUmVjdXJyaW5nTWVldGluZ0Fzc2lzdCdcbiAgKTtcbiAgY29uc29sZS5sb2coXG4gICAgcmVjdXJyaW5nUHJlZmVycmVkVGltZXMsXG4gICAgJyByZWN1cnJpbmdQcmVmZXJyZWRUaW1lcyBhZnRlciBpbnNpZGUgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3QnXG4gICk7XG5cbiAgcmV0dXJuIHsgcmVjdXJyaW5nQXR0ZW5kZWVzLCByZWN1cnJpbmdQcmVmZXJyZWRUaW1lcyB9O1xufTtcblxuZXhwb3J0IGNvbnN0IGdlbmVyYXRlQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXNGb3JSZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyA9IChcbiAgb3JpZ2luYWxBdHRlbmRlZXM6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXSxcbiAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdHM6IE1lZXRpbmdBc3Npc3RUeXBlW10sXG4gIG9yaWdpbmFsUHJlZmVycmVkVGltZXM/OiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVtdXG4pID0+IHtcbiAgY29uc3QgcmVjdXJyaW5nQXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10gPSBbXTtcbiAgY29uc3QgcmVjdXJyaW5nUHJlZmVycmVkVGltZXM6IE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lUmFuZ2VUeXBlW10gPSBbXTtcblxuICBjb25zb2xlLmxvZyhcbiAgICByZWN1cnJpbmdBdHRlbmRlZXMsXG4gICAgJyByZWN1cnJpbmdBdHRlbmRlZXMgaW5zaWRlIGdlbmVyYXRlQXR0ZW5kZWVzRm9yUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgYmVmb3JlJ1xuICApO1xuXG4gIGZvciAoY29uc3QgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdCBvZiByZWN1cnJpbmdNZWV0aW5nQXNzaXN0cykge1xuICAgIGNvbnN0IG5ld1JlY3VycmluZ0F0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzID1cbiAgICAgIGdlbmVyYXRlQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXNGb3JSZWN1cnJpbmdNZWV0aW5nQXNzaXN0KFxuICAgICAgICBvcmlnaW5hbEF0dGVuZGVlcyxcbiAgICAgICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdCxcbiAgICAgICAgb3JpZ2luYWxQcmVmZXJyZWRUaW1lc1xuICAgICAgKTtcblxuICAgIHJlY3VycmluZ0F0dGVuZGVlcy5wdXNoKFxuICAgICAgLi4ubmV3UmVjdXJyaW5nQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXM/LnJlY3VycmluZ0F0dGVuZGVlc1xuICAgICk7XG4gICAgaWYgKFxuICAgICAgbmV3UmVjdXJyaW5nQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXM/LnJlY3VycmluZ1ByZWZlcnJlZFRpbWVzPy5sZW5ndGggPlxuICAgICAgMFxuICAgICkge1xuICAgICAgcmVjdXJyaW5nUHJlZmVycmVkVGltZXMucHVzaChcbiAgICAgICAgLi4ubmV3UmVjdXJyaW5nQXR0ZW5kZWVzQW5kUHJlZmVycmVkVGltZXM/LnJlY3VycmluZ1ByZWZlcnJlZFRpbWVzXG4gICAgICApO1xuICAgIH1cbiAgfVxuXG4gIGNvbnNvbGUubG9nKFxuICAgIHJlY3VycmluZ0F0dGVuZGVlcyxcbiAgICAnIHJlY3VycmluZ0F0dGVuZGVlcyBpbnNpZGUgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3RzIGFmdGVyJ1xuICApO1xuICBjb25zb2xlLmxvZyhcbiAgICByZWN1cnJpbmdQcmVmZXJyZWRUaW1lcyxcbiAgICAnIHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzIGluc2lkZSBnZW5lcmF0ZUF0dGVuZGVlc0FuZFByZWZlcnJlZFRpbWVzRm9yUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgYWZ0ZXIgZ2VuZXJhdGlvbidcbiAgKTtcblxuICByZXR1cm4geyByZWN1cnJpbmdBdHRlbmRlZXMsIHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzIH07XG59O1xuXG5leHBvcnQgY29uc3QgaW5zZXJ0TWVldGluZ0Fzc2lzdHMgPSBhc3luYyAoXG4gIG1lZXRpbmdBc3Npc3RzOiBNZWV0aW5nQXNzaXN0VHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhtZWV0aW5nQXNzaXN0cywgJ2luc2VydE1lZXRpbmdBc3Npc3RzIGNhbGxlZCcpO1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnSW5zZXJ0TWVldGluZ0Fzc2lzdCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBtdXRhdGlvbiBJbnNlcnRNZWV0aW5nQXNzaXN0KCRtZWV0aW5nQXNzaXN0czogW01lZXRpbmdfQXNzaXN0X2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICAgICAgICAgIGluc2VydF9NZWV0aW5nX0Fzc2lzdChvYmplY3RzOiAkbWVldGluZ0Fzc2lzdHMpIHtcbiAgICAgICAgICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgICAgICBhbGxvd0F0dGVuZGVlVXBkYXRlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgYW55b25lQ2FuQWRkU2VsZlxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNhbk1vZGlmeVxuICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUNvdW50XG4gICAgICAgICAgICAgICAgICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnRcbiAgICAgICAgICAgICAgICAgICAgYmFja2dyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGJ1ZmZlclRpbWVcbiAgICAgICAgICAgICAgICAgICAgY2FsZW5kYXJJZFxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxJZkFueVJlZnVzZVxuICAgICAgICAgICAgICAgICAgICBjYW5jZWxsZWRcbiAgICAgICAgICAgICAgICAgICAgY29sb3JJZFxuICAgICAgICAgICAgICAgICAgICBjb25mZXJlbmNlQXBwXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICAgICAgICAgIGVuYWJsZUF0dGVuZGVlUHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5hYmxlQ29uZmVyZW5jZVxuICAgICAgICAgICAgICAgICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXNcbiAgICAgICAgICAgICAgICAgICAgZW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGV4cGlyZURhdGVcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGZyZXF1ZW5jeVxuICAgICAgICAgICAgICAgICAgICBndWFyYW50ZWVBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzXG4gICAgICAgICAgICAgICAgICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGludGVydmFsXG4gICAgICAgICAgICAgICAgICAgIGxvY2F0aW9uXG4gICAgICAgICAgICAgICAgICAgIG1pblRocmVzaG9sZENvdW50XG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yaWdpbmFsTWVldGluZ0lkXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHJlbWluZGVyc1xuICAgICAgICAgICAgICAgICAgICBzZW5kVXBkYXRlc1xuICAgICAgICAgICAgICAgICAgICBzdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVxuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB0cmFuc3BhcmVuY3lcbiAgICAgICAgICAgICAgICAgICAgdW50aWxcbiAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRBbGFybXNcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHZpc2liaWxpdHlcbiAgICAgICAgICAgICAgICAgICAgd2luZG93RW5kRGF0ZVxuICAgICAgICAgICAgICAgICAgICB3aW5kb3dTdGFydERhdGVcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIG1lZXRpbmdBc3Npc3RzLFxuICAgIH07XG5cbiAgICBjb25zdCByZXM6IHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0OiB7XG4gICAgICAgICAgYWZmZWN0ZWRfcm93czogbnVtYmVyO1xuICAgICAgICAgIHJldHVybmluZzogTWVldGluZ0Fzc2lzdFR5cGVbXTtcbiAgICAgICAgfTtcbiAgICAgIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlcz8uZGF0YT8uaW5zZXJ0X01lZXRpbmdfQXNzaXN0Py5hZmZlY3RlZF9yb3dzLFxuICAgICAgJyBzdWNjZXNzZnVsbHkgYWRkZWQgcmVjdXJyaW5nIG1lZXRpbmcgYXNzaXN0cydcbiAgICApO1xuXG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uaW5zZXJ0X01lZXRpbmdfQXNzaXN0Py5hZmZlY3RlZF9yb3dzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgaW5zZXJ0IG1lZXRpbmcgYXNzaXN0cycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNHaXZlbk1lZXRpbmdJZCA9IGFzeW5jIChcbiAgbWVldGluZ0lkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnTGlzdE1lZXRpbmdBc3Npc3RBdHRlbmRlZXNCeU1lZXRpbmdJZCc7XG4gICAgY29uc3QgcXVlcnkgPSBgXG4gICAgICAgICAgICBxdWVyeSBMaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlc0J5TWVldGluZ0lkKCRtZWV0aW5nSWQ6IHV1aWQhKSB7XG4gICAgICAgICAgICAgICAgTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWUod2hlcmU6IHttZWV0aW5nSWQ6IHtfZXE6ICRtZWV0aW5nSWR9fSkge1xuICAgICAgICAgICAgICAgICAgICBjb250YWN0SWRcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZW1haWxzXG4gICAgICAgICAgICAgICAgICAgIGV4dGVybmFsQXR0ZW5kZWVcbiAgICAgICAgICAgICAgICAgICAgaG9zdElkXG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIGltQWRkcmVzc2VzXG4gICAgICAgICAgICAgICAgICAgIG1lZXRpbmdJZFxuICAgICAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgICAgIHBob25lTnVtYmVyc1xuICAgICAgICAgICAgICAgICAgICB0aW1lem9uZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIHByaW1hcnlFbWFpbFxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIG1lZXRpbmdJZCxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7IE1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW10gfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSBsaXN0TWVldGluZ0Fzc2lzdEF0dGVuZGVlcyAnKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/Lk1lZXRpbmdfQXNzaXN0X0F0dGVuZGVlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gbGlzdCBtZWV0aW5nIGFzc2lzdCBhdHRlbmRlZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldFJydWxlRnJlcSA9IChmcmVxOiBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSkgPT4ge1xuICBzd2l0Y2ggKGZyZXEpIHtcbiAgICBjYXNlICdkYWlseSc6XG4gICAgICByZXR1cm4gUlJ1bGUuREFJTFk7XG4gICAgY2FzZSAnd2Vla2x5JzpcbiAgICAgIHJldHVybiBSUnVsZS5XRUVLTFk7XG4gICAgY2FzZSAnbW9udGhseSc6XG4gICAgICByZXR1cm4gUlJ1bGUuTU9OVEhMWTtcbiAgICBjYXNlICd5ZWFybHknOlxuICAgICAgcmV0dXJuIFJSdWxlLllFQVJMWTtcbiAgfVxufTtcbmV4cG9ydCBjb25zdCBnZW5lcmF0ZURhdGVzRm9yRnV0dXJlTWVldGluZ0Fzc2lzdHNVc2luZ1JydWxlID0gKFxuICB3aW5kb3dTdGFydERhdGU6IHN0cmluZyxcbiAgd2luZG93RW5kRGF0ZTogc3RyaW5nLFxuICBmcmVxdWVuY3k6IFJlY3VycmVuY2VGcmVxdWVuY3lUeXBlLFxuICBpbnRlcnZhbDogbnVtYmVyLFxuICB1bnRpbDogc3RyaW5nXG4pID0+IHtcbiAgY29uc3QgcnVsZVN0YXJ0RGF0ZSA9IG5ldyBSUnVsZSh7XG4gICAgZHRzdGFydDogZGF5anMod2luZG93U3RhcnREYXRlKS51dGMoKS50b0RhdGUoKSxcbiAgICBmcmVxOiBnZXRScnVsZUZyZXEoZnJlcXVlbmN5KSxcbiAgICBpbnRlcnZhbCxcbiAgICB1bnRpbDogZGF5anModW50aWwpLnV0YygpLnRvRGF0ZSgpLFxuICB9KTtcblxuICBjb25zb2xlLmxvZyhcbiAgICBydWxlU3RhcnREYXRlLFxuICAgICcgcnVsZVN0YXJ0RGF0ZSBpbnNpZGUgZ2VuZXJhdGVEYXRlc0ZvckZ1dHVyZU1lZXRpbmdBc3Npc3RzVXNpbmdScnVsZSdcbiAgKTtcblxuICBjb25zdCB3aW5kb3dTdGFydERhdGVzRm9yUmVjdXJyZW5jZSA9IHJ1bGVTdGFydERhdGVcbiAgICAuYWxsKClcbiAgICA/Lm1hcCgoZCkgPT4gZGF5anMudXRjKGQpLmZvcm1hdCgpKTtcblxuICB3aW5kb3dTdGFydERhdGVzRm9yUmVjdXJyZW5jZT8uZm9yRWFjaCgoZSkgPT5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHdpbmRvd0RhdGVmb3JyZWN1cnJlbmNlIGluc2lkZSBnZW5lcmF0ZURhdGVzRm9yRnV0dXJlTWVldGluZ0Fzc2lzdHNVc2luZ1JydWxlJ1xuICAgIClcbiAgKTtcblxuICBjb25zdCBydWxlRW5kRGF0ZSA9IG5ldyBSUnVsZSh7XG4gICAgZHRzdGFydDogZGF5anMod2luZG93RW5kRGF0ZSkudXRjKCkudG9EYXRlKCksXG4gICAgZnJlcTogZ2V0UnJ1bGVGcmVxKGZyZXF1ZW5jeSksXG4gICAgaW50ZXJ2YWwsXG4gICAgdW50aWw6IGRheWpzKHVudGlsKS51dGMoKS50b0RhdGUoKSxcbiAgfSk7XG5cbiAgY29uc29sZS5sb2coXG4gICAgcnVsZUVuZERhdGUsXG4gICAgJyBydWxlRW5kRGF0ZSBpbnNpZGUgZ2VuZXJhdGVEYXRlc0ZvckZ1dHVyZU1lZXRpbmdBc3Npc3RzVXNpbmdScnVsZSdcbiAgKTtcblxuICBjb25zdCB3aW5kb3dFbmREYXRlc0ZvclJlY3VycmVuY2UgPSBydWxlRW5kRGF0ZVxuICAgIC5hbGwoKVxuICAgID8ubWFwKChkKSA9PiBkYXlqcy51dGMoZCkuZm9ybWF0KCkpO1xuXG4gIHdpbmRvd0VuZERhdGVzRm9yUmVjdXJyZW5jZT8uZm9yRWFjaCgoZSkgPT5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGUsXG4gICAgICAnIHdpbmRvd0VuZERhdGVmb3JyZWN1cnJlbmNlIGluc2lkZSBnZW5lcmF0ZURhdGVzRm9yRnV0dXJlTWVldGluZ0Fzc2lzdHNVc2luZ1JydWxlJ1xuICAgIClcbiAgKTtcblxuICAvLyByZWZvcm1hdCBpbnRvIHdpbmRvd1N0YXJ0RGF0ZXMgYW5kIHdpbmRvd0VuZERhdGVzXG4gIGNvbnN0IHRpbWVXaW5kb3dzID0gd2luZG93U3RhcnREYXRlc0ZvclJlY3VycmVuY2VcbiAgICA/LnNsaWNlKDAsIHdpbmRvd0VuZERhdGVzRm9yUmVjdXJyZW5jZT8ubGVuZ3RoKVxuICAgID8ubWFwKCh3aW5kb3dTdGFydERhdGUsIGlueCkgPT4ge1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgd2luZG93U3RhcnREYXRlLFxuICAgICAgICB3aW5kb3dFbmREYXRlOiB3aW5kb3dFbmREYXRlc0ZvclJlY3VycmVuY2U/LltpbnhdLFxuICAgICAgfTtcbiAgICB9KTtcblxuICByZXR1cm4gdGltZVdpbmRvd3M7XG59O1xuXG5leHBvcnQgY29uc3QgZ2VuZXJhdGVSZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyA9IChcbiAgb3JpZ2luYWxNZWV0aW5nQXNzaXN0OiBNZWV0aW5nQXNzaXN0VHlwZVxuKSA9PiB7XG4gIC8vIHZhbGlkYXRlXG4gIGlmICghb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5mcmVxdWVuY3kpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gZnJlcXVlbmN5IHByZXNlbnQgaW5zaWRlIGdlbmVyYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMnKTtcbiAgICByZXR1cm47XG4gIH1cblxuICBpZiAoIW9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uaW50ZXJ2YWwpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gaW50ZXJudmFsIHByZXNlbnQgaW5zaWRlIGdlbmVyYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMnKTtcbiAgICByZXR1cm47XG4gIH1cblxuICBpZiAoIW9yaWdpbmFsTWVldGluZ0Fzc2lzdD8udW50aWwpIHtcbiAgICBjb25zb2xlLmxvZygnbm8gdW50aWwgcHJlc2VudCBpbnNpZGUgZ2VuZXJhdGVSZWN1cnJpbmdNZWV0aW5nQXNzaXN0cycpO1xuICAgIHJldHVybjtcbiAgfVxuXG4gIGNvbnNvbGUubG9nKCdnZW5lcmF0ZVJlY3VycmluZ01lZXRpbmdBc3Npc3RzIGNhbGxlZCcpO1xuXG4gIGNvbnN0IHJlY3VycmluZ01lZXRpbmdBc3Npc3RzOiBNZWV0aW5nQXNzaXN0VHlwZVtdID0gW107XG5cbiAgY29uc3QgdGltZVdpbmRvd3MgPSBnZW5lcmF0ZURhdGVzRm9yRnV0dXJlTWVldGluZ0Fzc2lzdHNVc2luZ1JydWxlKFxuICAgIG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8ud2luZG93U3RhcnREYXRlLFxuICAgIG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8ud2luZG93RW5kRGF0ZSxcbiAgICBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmZyZXF1ZW5jeSBhcyBSZWN1cnJlbmNlRnJlcXVlbmN5VHlwZSxcbiAgICBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmludGVydmFsLFxuICAgIG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8udW50aWxcbiAgKTtcblxuICBjb25zb2xlLmxvZyhcbiAgICB0aW1lV2luZG93cyxcbiAgICAnIHRpbWVXaW5kb3dzIGluc2lkZSBnZW5lcmF0ZVJlY3VycmluZ01lZXRpbmdBc3Npc3RzJ1xuICApO1xuXG4gIGZvciAobGV0IGkgPSAwOyBpIDwgdGltZVdpbmRvd3MubGVuZ3RoOyBpKyspIHtcbiAgICBpZiAoaSA9PT0gMCkge1xuICAgICAgY29udGludWU7XG4gICAgfVxuXG4gICAgY29uc3QgbWVldGluZ0lkID0gdXVpZCgpO1xuICAgIGNvbnN0IG5ld1JlY3VycmluZ01lZXRpbmdBc3Npc3Q6IE1lZXRpbmdBc3Npc3RUeXBlID0ge1xuICAgICAgaWQ6IG1lZXRpbmdJZCxcbiAgICAgIHVzZXJJZDogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py51c2VySWQsXG4gICAgICBzdW1tYXJ5OiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LnN1bW1hcnksXG4gICAgICBub3Rlczogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5ub3RlcyxcbiAgICAgIHdpbmRvd1N0YXJ0RGF0ZTogdGltZVdpbmRvd3NbaV0/LndpbmRvd1N0YXJ0RGF0ZSxcbiAgICAgIHdpbmRvd0VuZERhdGU6IHRpbWVXaW5kb3dzW2ldPy53aW5kb3dFbmREYXRlLFxuICAgICAgdGltZXpvbmU6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8udGltZXpvbmUsXG4gICAgICBsb2NhdGlvbjogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5sb2NhdGlvbixcbiAgICAgIHByaW9yaXR5OiAxLFxuICAgICAgZW5hYmxlQ29uZmVyZW5jZTogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5lbmFibGVDb25mZXJlbmNlLFxuICAgICAgY29uZmVyZW5jZUFwcDogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5jb25mZXJlbmNlQXBwLFxuICAgICAgc2VuZFVwZGF0ZXM6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uc2VuZFVwZGF0ZXMsXG4gICAgICBndWVzdHNDYW5JbnZpdGVPdGhlcnM6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzLFxuICAgICAgdHJhbnNwYXJlbmN5OiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LnRyYW5zcGFyZW5jeSxcbiAgICAgIHZpc2liaWxpdHk6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8udmlzaWJpbGl0eSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLmZvcm1hdCgpLFxuICAgICAgY29sb3JJZDogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5jb2xvcklkLFxuICAgICAgYmFja2dyb3VuZENvbG9yOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmJhY2tncm91bmRDb2xvcixcbiAgICAgIGZvcmVncm91bmRDb2xvcjogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5mb3JlZ3JvdW5kQ29sb3IsXG4gICAgICB1c2VEZWZhdWx0QWxhcm1zOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LnVzZURlZmF1bHRBbGFybXMsXG4gICAgICByZW1pbmRlcnM6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8ucmVtaW5kZXJzLFxuICAgICAgY2FuY2VsSWZBbnlSZWZ1c2U6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uY2FuY2VsSWZBbnlSZWZ1c2UsXG4gICAgICBlbmFibGVIb3N0UHJlZmVyZW5jZXM6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uZW5hYmxlSG9zdFByZWZlcmVuY2VzLFxuICAgICAgZW5hYmxlQXR0ZW5kZWVQcmVmZXJlbmNlczpcbiAgICAgICAgb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5lbmFibGVBdHRlbmRlZVByZWZlcmVuY2VzLFxuICAgICAgYXR0ZW5kZWVDYW5Nb2RpZnk6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uYXR0ZW5kZWVDYW5Nb2RpZnksXG4gICAgICBleHBpcmVEYXRlOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmV4cGlyZURhdGUsXG4gICAgICBjYW5jZWxsZWQ6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uY2FuY2VsbGVkLFxuICAgICAgZHVyYXRpb246IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uZHVyYXRpb24sXG4gICAgICBjYWxlbmRhcklkOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmNhbGVuZGFySWQsXG4gICAgICBidWZmZXJUaW1lOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmJ1ZmZlclRpbWUsXG4gICAgICBhbnlvbmVDYW5BZGRTZWxmOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmFueW9uZUNhbkFkZFNlbGYsXG4gICAgICBndWVzdHNDYW5TZWVPdGhlckd1ZXN0czogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5ndWVzdHNDYW5TZWVPdGhlckd1ZXN0cyxcbiAgICAgIG1pblRocmVzaG9sZENvdW50OiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/Lm1pblRocmVzaG9sZENvdW50LFxuICAgICAgZ3VhcmFudGVlQXZhaWxhYmlsaXR5OiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/Lmd1YXJhbnRlZUF2YWlsYWJpbGl0eSxcbiAgICAgIGZyZXF1ZW5jeTogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5mcmVxdWVuY3ksXG4gICAgICBpbnRlcnZhbDogb3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5pbnRlcnZhbCxcbiAgICAgIHVudGlsOiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LnVudGlsLFxuICAgICAgb3JpZ2luYWxNZWV0aW5nSWQ6IG9yaWdpbmFsTWVldGluZ0Fzc2lzdD8uaWQsXG4gICAgICBhdHRlbmRlZVJlc3BvbmRlZENvdW50OiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmF0dGVuZGVlUmVzcG9uZGVkQ291bnQsXG4gICAgICBhdHRlbmRlZUNvdW50OiBvcmlnaW5hbE1lZXRpbmdBc3Npc3Q/LmF0dGVuZGVlQ291bnQsXG4gICAgfTtcblxuICAgIHJlY3VycmluZ01lZXRpbmdBc3Npc3RzLnB1c2gobmV3UmVjdXJyaW5nTWVldGluZ0Fzc2lzdCk7XG4gIH1cblxuICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0cz8uZm9yRWFjaCgoYSkgPT5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGEsXG4gICAgICAnIHJlY3VycmluZ01lZXRpbmdBc3Npc3QgaW5zaWRlIGdlbmVyYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMnXG4gICAgKVxuICApO1xuICByZXR1cm4gcmVjdXJyaW5nTWVldGluZ0Fzc2lzdHM7XG59O1xuXG5leHBvcnQgY29uc3QgaW5zZXJ0TWVldGluZ0Fzc2lzdEF0dGVuZGVlcyA9IGFzeW5jIChcbiAgYXR0ZW5kZWVzOiBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlW11cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYXR0ZW5kZWVzLFxuICAgICAgJyBhdHRlbmRlZXMgY2FsbGVkIGluc2lkZSBpbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzJ1xuICAgICk7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdJbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIEluc2VydE1lZXRpbmdBc3Npc3RBdHRlbmRlZXMoJGF0dGVuZGVlczogW01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICAgICAgICAgIGluc2VydF9NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZShvYmplY3RzOiAkYXR0ZW5kZWVzKSB7XG4gICAgICAgICAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgICAgICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIGVtYWlsc1xuICAgICAgICAgICAgICAgICAgICBleHRlcm5hbEF0dGVuZGVlXG4gICAgICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBpbUFkZHJlc3Nlc1xuICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgbmFtZVxuICAgICAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICAgICAgcHJpbWFyeUVtYWlsXG4gICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH1cbiAgICAgICAgYDtcblxuICAgIGNvbnN0IHZhcmlhYmxlcyA9IHtcbiAgICAgIGF0dGVuZGVlcyxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzOiB7XG4gICAgICBkYXRhOiB7XG4gICAgICAgIGluc2VydF9NZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZToge1xuICAgICAgICAgIGFmZmVjdGVkX3Jvd3M6IG51bWJlcjtcbiAgICAgICAgICByZXR1cm5pbmc6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGVbXTtcbiAgICAgICAgfTtcbiAgICAgIH07XG4gICAgfSA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICdYLUhhc3VyYS1BZG1pbi1TZWNyZXQnOiBoYXN1cmFBZG1pblNlY3JldCxcbiAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICdYLUhhc3VyYS1Sb2xlJzogJ2FkbWluJyxcbiAgICAgICAgfSxcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGZyb20gaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlJyk7XG4gICAgcmV0dXJuIHJlcz8uZGF0YT8uaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0F0dGVuZGVlPy5hZmZlY3RlZF9yb3dzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gaW5zZXJ0IG1lZXRpbmcgYXNzaXN0IGF0dGVuZGVlcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgdXBzZXJ0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVzID0gYXN5bmMgKFxuICBwcmVmZXJyZWRUaW1lczogTWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVSYW5nZVR5cGVbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBwcmVmZXJyZWRUaW1lcyxcbiAgICAgICcgcHJlZmVycmVkVGltZXMgaW5zaWRlIHVwc2VydE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lcydcbiAgICApO1xuICAgIGNvbnN0IG9wZXJhdGlvbk5hbWUgPSAnaW5zZXJ0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVzJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgICAgICAgIG11dGF0aW9uIGluc2VydE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lcygkcHJlZmVycmVkVGltZXM6IFtNZWV0aW5nX0Fzc2lzdF9QcmVmZXJyZWRfVGltZV9SYW5nZV9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgICAgICAgICBpbnNlcnRfTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2Uob2JqZWN0czogJHByZWZlcnJlZFRpbWVzLCBcbiAgICAgICAgICAgICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3RyYWludDogTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2VzX3BrZXksIFxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVfY29sdW1uczogW1xuICAgICAgICAgICAgICAgICAgICAgICAgYXR0ZW5kZWVJZCxcbiAgICAgICAgICAgICAgICAgICAgICAgIGRheU9mV2VlayxcbiAgICAgICAgICAgICAgICAgICAgICAgIGVuZFRpbWUsXG4gICAgICAgICAgICAgICAgICAgICAgICBob3N0SWQsXG4gICAgICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWQsXG4gICAgICAgICAgICAgICAgICAgICAgICBzdGFydFRpbWUsXG4gICAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICAgICAgICAgIF1cbiAgICAgICAgICAgICAgICAgICAgfSkge1xuICAgICAgICAgICAgICAgICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICAgICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgICAgICAgICBhdHRlbmRlZUlkXG4gICAgICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgZGF5T2ZXZWVrXG4gICAgICAgICAgICAgICAgICAgICAgICBlbmRUaW1lXG4gICAgICAgICAgICAgICAgICAgICAgICBob3N0SWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICAgICAgICAgIHN0YXJ0VGltZVxuICAgICAgICAgICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBwcmVmZXJyZWRUaW1lczogcHJlZmVycmVkVGltZXM/Lm1hcCgocHQpID0+ICh7XG4gICAgICAgIC4uLnB0LFxuICAgICAgICBkYXlPZldlZWs6IHB0Py5kYXlPZldlZWsgPT09IC0xID8gbnVsbCA6IHB0Py5kYXlPZldlZWssXG4gICAgICB9KSksXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczoge1xuICAgICAgZGF0YToge1xuICAgICAgICBpbnNlcnRfTWVldGluZ19Bc3Npc3RfUHJlZmVycmVkX1RpbWVfUmFuZ2U6IHtcbiAgICAgICAgICBhZmZlY3RlZF9yb3dzOiBudW1iZXI7XG4gICAgICAgICAgcmV0dXJuaW5nOiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVtdO1xuICAgICAgICB9O1xuICAgICAgfTtcbiAgICB9ID0gYXdhaXQgZ290XG4gICAgICAucG9zdChoYXN1cmFHcmFwaFVybCwge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgICBqc29uOiB7XG4gICAgICAgICAgb3BlcmF0aW9uTmFtZSxcbiAgICAgICAgICBxdWVyeSxcbiAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICAgLmpzb24oKTtcblxuICAgIGNvbnNvbGUubG9nKHJlcywgJyByZXMgZnJvbSB1cHNlcnRNZWV0aW5nQXNpc3RQcmVmZXJyZWRUaW1lcyAnKTtcblxuICAgIHJldHVybiByZXM/LmRhdGE/Lmluc2VydF9NZWV0aW5nX0Fzc2lzdF9QcmVmZXJyZWRfVGltZV9SYW5nZT8uYWZmZWN0ZWRfcm93cztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwc2VydE1lZXRpbmdBc3Npc3RQcmVmZXJyZWRUaW1lcycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgY3JlYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgPSBhc3luYyAoXG4gIG9yaWdpbmFsTWVldGluZ0Fzc2lzdDogTWVldGluZ0Fzc2lzdFR5cGUsXG4gIG9yaWdpbmFsUHJlZmVycmVkVGltZXM/OiBNZWV0aW5nQXNzaXN0UHJlZmVycmVkVGltZVJhbmdlVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZygnY3JlYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgY2FsbGVkJyk7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBvcmlnaW5hbFByZWZlcnJlZFRpbWVzLFxuICAgICAgJyBvcmlnaW5hbFByZWZlcnJlZFRpbWVzICBpbnNpZGUgY3JlYXRlUmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMnXG4gICAgKTtcbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVzID1cbiAgICAgIGF3YWl0IGxpc3RNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzR2l2ZW5NZWV0aW5nSWQob3JpZ2luYWxNZWV0aW5nQXNzaXN0Py5pZCk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIG1lZXRpbmdBc3Npc3RBdHRlbmRlZXMsXG4gICAgICAnIG1lZXRpbmdBc3Npc3RBdHRlbmRlZXMgaW5zaWRlIGNyZWF0ZVJlY3VycmluZ01lZXRpbmdBc3Npc3RzJ1xuICAgICk7XG4gICAgaWYgKCEobWVldGluZ0Fzc2lzdEF0dGVuZGVlcyAmJiBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVzPy5sZW5ndGggPiAwKSkge1xuICAgICAgY29uc29sZS5sb2coJ25vIGF0dGVuZGVlcyBpcyBwcmVzZW50Jyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3QgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdHMgPSBnZW5lcmF0ZVJlY3VycmluZ01lZXRpbmdBc3Npc3RzKFxuICAgICAgb3JpZ2luYWxNZWV0aW5nQXNzaXN0XG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKHJlY3VycmluZ01lZXRpbmdBc3Npc3RzLCAnIHJlY3VycmluZ01lZXRpbmdBc3Npc3RzJyk7XG5cbiAgICBpZiAoIShyZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyAmJiByZWN1cnJpbmdNZWV0aW5nQXNzaXN0cz8ubGVuZ3RoID4gMCkpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdubyByZWN1cnJpbmdNZWV0aW5nYXNzaXN0cyBnZW5lcmF0ZWQnKTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBhd2FpdCBpbnNlcnRNZWV0aW5nQXNzaXN0cyhyZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyk7XG5cbiAgICBjb25zdCByZWN1cnJpbmdNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQW5kUmVjdXJyaW5nUHJlZmVycmVkVGltZXMgPVxuICAgICAgZ2VuZXJhdGVBdHRlbmRlZXNBbmRQcmVmZXJyZWRUaW1lc0ZvclJlY3VycmluZ01lZXRpbmdBc3Npc3RzKFxuICAgICAgICBtZWV0aW5nQXNzaXN0QXR0ZW5kZWVzLFxuICAgICAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0cyxcbiAgICAgICAgb3JpZ2luYWxQcmVmZXJyZWRUaW1lc1xuICAgICAgKTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdEF0dGVuZGVlc0FuZFJlY3VycmluZ1ByZWZlcnJlZFRpbWVzPy5yZWN1cnJpbmdBdHRlbmRlZXMsXG4gICAgICAnIHJlY3VycmluZ01lZXRpbmdBc3Npc3RBdHRlbmRlZXMnXG4gICAgKTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlY3VycmluZ01lZXRpbmdBc3Npc3RBdHRlbmRlZXNBbmRSZWN1cnJpbmdQcmVmZXJyZWRUaW1lcz8ucmVjdXJyaW5nUHJlZmVycmVkVGltZXMsXG4gICAgICAnIHJlY3VycmluZ1ByZWZlcnJlZFRpbWVzJ1xuICAgICk7XG5cbiAgICBhd2FpdCBpbnNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzKFxuICAgICAgcmVjdXJyaW5nTWVldGluZ0Fzc2lzdEF0dGVuZGVlc0FuZFJlY3VycmluZ1ByZWZlcnJlZFRpbWVzLnJlY3VycmluZ0F0dGVuZGVlc1xuICAgICk7XG5cbiAgICBpZiAoXG4gICAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQW5kUmVjdXJyaW5nUHJlZmVycmVkVGltZXNcbiAgICAgICAgPy5yZWN1cnJpbmdQcmVmZXJyZWRUaW1lcz8ubGVuZ3RoID4gMFxuICAgICkge1xuICAgICAgYXdhaXQgdXBzZXJ0TWVldGluZ0Fzc2lzdFByZWZlcnJlZFRpbWVzKFxuICAgICAgICByZWN1cnJpbmdNZWV0aW5nQXNzaXN0QXR0ZW5kZWVzQW5kUmVjdXJyaW5nUHJlZmVycmVkVGltZXM/LnJlY3VycmluZ1ByZWZlcnJlZFRpbWVzXG4gICAgICApO1xuICAgIH1cbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSByZWN1cnJpbmcgbWVldGluZyBhc3Npc3QnKTtcbiAgfVxufTtcbiJdfQ==