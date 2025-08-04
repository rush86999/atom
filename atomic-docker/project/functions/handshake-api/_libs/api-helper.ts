import got from 'got';
import { hasuraAdminSecret, hasuraGraphUrl } from './constants';
import {
  MeetingAssistAttendeeType,
  MeetingAssistPreferredTimeRangeType,
  MeetingAssistType,
  RecurrenceFrequencyType,
} from './types';
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

export const generatePreferredTimesForRecurringMeetingAssist = (
  originalPreferredTimes: MeetingAssistPreferredTimeRangeType[],
  recurringMeetingAssist: MeetingAssistType,
  recurringAttendee: MeetingAssistAttendeeType
) => {
  console.log(
    originalPreferredTimes,
    recurringMeetingAssist,
    ' originalPreferredTimes, recurringMeetingAssist'
  );

  const recurringPreferredTimes: MeetingAssistPreferredTimeRangeType[] = [];

  for (const preferredTime of originalPreferredTimes) {
    const recurringPreferredTime: MeetingAssistPreferredTimeRangeType = {
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

export const generateAttendeesAndPreferredTimesForRecurringMeetingAssist = (
  originalAttendees: MeetingAssistAttendeeType[],
  recurringMeetingAssist: MeetingAssistType,
  originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]
) => {
  console.log(
    originalAttendees,
    recurringMeetingAssist,
    originalPreferredTimes,
    ' originalAttendees, recurringMeetingAssist, originalPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist before'
  );
  const recurringAttendees: MeetingAssistAttendeeType[] = [];

  const recurringPreferredTimes: MeetingAssistPreferredTimeRangeType[] = [];

  for (const originalAttendee of originalAttendees) {
    const recurringAttendee: MeetingAssistAttendeeType = {
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

    const attendeeIndex = originalPreferredTimes?.findIndex(
      (o) => o?.attendeeId === originalAttendee?.id
    );

    console.log(
      attendeeIndex,
      ' attendeeIndex inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist'
    );
    console.log(
      originalPreferredTimes,
      ' originalPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist'
    );

    if (
      originalPreferredTimes &&
      originalPreferredTimes?.length > 0 &&
      typeof attendeeIndex === 'number' &&
      attendeeIndex > -1
    ) {
      const recurringPreferredTimesForAttendee =
        generatePreferredTimesForRecurringMeetingAssist(
          originalPreferredTimes?.filter(
            (o) => o?.attendeeId === originalAttendee?.id
          ),
          recurringMeetingAssist,
          recurringAttendee
        );

      recurringPreferredTimes.push(...recurringPreferredTimesForAttendee);
    }

    recurringAttendees.push(recurringAttendee);
  }

  console.log(
    recurringAttendees,
    ' recurringAttendees after inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist'
  );
  console.log(
    recurringPreferredTimes,
    ' recurringPreferredTimes after inside generateAttendeesAndPreferredTimesForRecurringMeetingAssist'
  );

  return { recurringAttendees, recurringPreferredTimes };
};

export const generateAttendeesAndPreferredTimesForRecurringMeetingAssists = (
  originalAttendees: MeetingAssistAttendeeType[],
  recurringMeetingAssists: MeetingAssistType[],
  originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]
) => {
  const recurringAttendees: MeetingAssistAttendeeType[] = [];
  const recurringPreferredTimes: MeetingAssistPreferredTimeRangeType[] = [];

  console.log(
    recurringAttendees,
    ' recurringAttendees inside generateAttendeesForRecurringMeetingAssists before'
  );

  for (const recurringMeetingAssist of recurringMeetingAssists) {
    const newRecurringAttendeesAndPreferredTimes =
      generateAttendeesAndPreferredTimesForRecurringMeetingAssist(
        originalAttendees,
        recurringMeetingAssist,
        originalPreferredTimes
      );

    recurringAttendees.push(
      ...newRecurringAttendeesAndPreferredTimes?.recurringAttendees
    );
    if (
      newRecurringAttendeesAndPreferredTimes?.recurringPreferredTimes?.length >
      0
    ) {
      recurringPreferredTimes.push(
        ...newRecurringAttendeesAndPreferredTimes?.recurringPreferredTimes
      );
    }
  }

  console.log(
    recurringAttendees,
    ' recurringAttendees inside generateAttendeesAndPreferredTimesForRecurringMeetingAssists after'
  );
  console.log(
    recurringPreferredTimes,
    ' recurringPreferredTimes inside generateAttendeesAndPreferredTimesForRecurringMeetingAssists after generation'
  );

  return { recurringAttendees, recurringPreferredTimes };
};

export const insertMeetingAssists = async (
  meetingAssists: MeetingAssistType[]
) => {
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

    const res: {
      data: {
        insert_Meeting_Assist: {
          affected_rows: number;
          returning: MeetingAssistType[];
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
      res?.data?.insert_Meeting_Assist?.affected_rows,
      ' successfully added recurring meeting assists'
    );

    return res?.data?.insert_Meeting_Assist?.affected_rows;
  } catch (e) {
    console.log(e, ' unable insert meeting assists');
  }
};

export const listMeetingAssistAttendeesGivenMeetingId = async (
  meetingId: string
) => {
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

    const res: {
      data: { Meeting_Assist_Attendee: MeetingAssistAttendeeType[] };
    } = await got
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
  } catch (e) {
    console.log(e, ' unable to list meeting assist attendees');
  }
};

export const getRruleFreq = (freq: RecurrenceFrequencyType) => {
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
export const generateDatesForFutureMeetingAssistsUsingRrule = (
  windowStartDate: string,
  windowEndDate: string,
  frequency: RecurrenceFrequencyType,
  interval: number,
  until: string
) => {
  const ruleStartDate = new RRule({
    dtstart: dayjs(windowStartDate).utc().toDate(),
    freq: getRruleFreq(frequency),
    interval,
    until: dayjs(until).utc().toDate(),
  });

  console.log(
    ruleStartDate,
    ' ruleStartDate inside generateDatesForFutureMeetingAssistsUsingRrule'
  );

  const windowStartDatesForRecurrence = ruleStartDate
    .all()
    ?.map((d) => dayjs.utc(d).format());

  windowStartDatesForRecurrence?.forEach((e) =>
    console.log(
      e,
      ' windowDateforrecurrence inside generateDatesForFutureMeetingAssistsUsingRrule'
    )
  );

  const ruleEndDate = new RRule({
    dtstart: dayjs(windowEndDate).utc().toDate(),
    freq: getRruleFreq(frequency),
    interval,
    until: dayjs(until).utc().toDate(),
  });

  console.log(
    ruleEndDate,
    ' ruleEndDate inside generateDatesForFutureMeetingAssistsUsingRrule'
  );

  const windowEndDatesForRecurrence = ruleEndDate
    .all()
    ?.map((d) => dayjs.utc(d).format());

  windowEndDatesForRecurrence?.forEach((e) =>
    console.log(
      e,
      ' windowEndDateforrecurrence inside generateDatesForFutureMeetingAssistsUsingRrule'
    )
  );

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

export const generateRecurringMeetingAssists = (
  originalMeetingAssist: MeetingAssistType
) => {
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

  const recurringMeetingAssists: MeetingAssistType[] = [];

  const timeWindows = generateDatesForFutureMeetingAssistsUsingRrule(
    originalMeetingAssist?.windowStartDate,
    originalMeetingAssist?.windowEndDate,
    originalMeetingAssist?.frequency as RecurrenceFrequencyType,
    originalMeetingAssist?.interval,
    originalMeetingAssist?.until
  );

  console.log(
    timeWindows,
    ' timeWindows inside generateRecurringMeetingAssists'
  );

  for (let i = 0; i < timeWindows.length; i++) {
    if (i === 0) {
      continue;
    }

    const meetingId = uuid();
    const newRecurringMeetingAssist: MeetingAssistType = {
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
      enableAttendeePreferences:
        originalMeetingAssist?.enableAttendeePreferences,
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

  recurringMeetingAssists?.forEach((a) =>
    console.log(
      a,
      ' recurringMeetingAssist inside generateRecurringMeetingAssists'
    )
  );
  return recurringMeetingAssists;
};

export const insertMeetingAssistAttendees = async (
  attendees: MeetingAssistAttendeeType[]
) => {
  try {
    console.log(
      attendees,
      ' attendees called inside insertMeetingAssistAttendees'
    );
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

    const res: {
      data: {
        insert_Meeting_Assist_Attendee: {
          affected_rows: number;
          returning: MeetingAssistAttendeeType[];
        };
      };
    } = await got
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
  } catch (e) {
    console.log(e, ' unable to insert meeting assist attendees');
  }
};

export const upsertMeetingAssistPreferredTimes = async (
  preferredTimes: MeetingAssistPreferredTimeRangeType[]
) => {
  try {
    console.log(
      preferredTimes,
      ' preferredTimes inside upsertMeetingAssistPreferredTimes'
    );
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

    const res: {
      data: {
        insert_Meeting_Assist_Preferred_Time_Range: {
          affected_rows: number;
          returning: MeetingAssistPreferredTimeRangeType[];
        };
      };
    } = await got
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
  } catch (e) {
    console.log(e, ' unable to upsertMeetingAssistPreferredTimes');
  }
};

export const createRecurringMeetingAssists = async (
  originalMeetingAssist: MeetingAssistType,
  originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[]
) => {
  try {
    console.log('createRecurringMeetingAssists called');
    console.log(
      originalPreferredTimes,
      ' originalPreferredTimes  inside createRecurringMeetingAssists'
    );
    const meetingAssistAttendees =
      await listMeetingAssistAttendeesGivenMeetingId(originalMeetingAssist?.id);

    console.log(
      meetingAssistAttendees,
      ' meetingAssistAttendees inside createRecurringMeetingAssists'
    );
    if (!(meetingAssistAttendees && meetingAssistAttendees?.length > 0)) {
      console.log('no attendees is present');
      return;
    }

    const recurringMeetingAssists = generateRecurringMeetingAssists(
      originalMeetingAssist
    );

    console.log(recurringMeetingAssists, ' recurringMeetingAssists');

    if (!(recurringMeetingAssists && recurringMeetingAssists?.length > 0)) {
      console.log('no recurringMeetingassists generated');
      return;
    }

    await insertMeetingAssists(recurringMeetingAssists);

    const recurringMeetingAssistAttendeesAndRecurringPreferredTimes =
      generateAttendeesAndPreferredTimesForRecurringMeetingAssists(
        meetingAssistAttendees,
        recurringMeetingAssists,
        originalPreferredTimes
      );

    console.log(
      recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringAttendees,
      ' recurringMeetingAssistAttendees'
    );
    console.log(
      recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringPreferredTimes,
      ' recurringPreferredTimes'
    );

    await insertMeetingAssistAttendees(
      recurringMeetingAssistAttendeesAndRecurringPreferredTimes.recurringAttendees
    );

    if (
      recurringMeetingAssistAttendeesAndRecurringPreferredTimes
        ?.recurringPreferredTimes?.length > 0
    ) {
      await upsertMeetingAssistPreferredTimes(
        recurringMeetingAssistAttendeesAndRecurringPreferredTimes?.recurringPreferredTimes
      );
    }
  } catch (e) {
    console.log(e, ' unable to create recurring meeting assist');
  }
};
