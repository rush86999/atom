// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import {
  createRecurringMeetingAssists,
  deleteMeetingAssistPreferredTimesByIds,
  findEventsForUserGivenMeetingId,
  generateAvailableSlotsforTimeWindow,
  getMeetingAssist,
  getUserPreferences,
  listEventsForUserGivenDates,
  listMeetingAssistAttendeesGivenMeetingId,
  listMeetingAssistEventsForAttendeeGivenDates,
  listMeetingAssistPreferredTimeRangesGivenMeetingId,
  startMeetingAssist,
  upsertMeetingAssistPreferredTimes,
} from '@lib/api-helper';
import {
  AvailableSlotsByDate,
  EventType,
  MeetingAssistAttendeeType,
  MeetingAssistEventType,
  MeetingAssistPreferredTimeRangeType,
  ScheduleAssistWithMeetingQueueBodyType,
  MeetingAssistType,
  NotAvailableSlot,
  UserPreferenceType,
} from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';

type RequestDataForDeleteMeetingAssistPreferredTimesType = {
  method: 'deleteMeetingAssistPreferredTimes';
  variables: {
    ids: string[];
  };
};

type RequestDataForFindEventForUserType = {
  method: 'findEventsForUserGivenMeetingId';
  variables: {
    userId: string;
    hostStartDate: string;
    hostEndDate: string;
    userTimezone: string;
    hostTimezone: string;
    meetingId: string;
  };
};

type RequestDataForGenerateAvailableSlotsforTimeWindowType = {
  method: 'generateAvailableSlotsforTimeWindow';
  variables: {
    windowStartDate: string;
    windowEndDate: string;
    slotDuration: number;
    hostPreferences: UserPreferenceType;
    hostTimezone: string;
    userTimezone: string;
    notAvailableSlotsInUserTimezone?: NotAvailableSlot[];
  };
};

type RequestDataForGetMeetingAssistType = {
  method: 'getMeetingAssist';
  variables: {
    id: string;
  };
};

type RequestDataForGetUserPreferencesType = {
  method: 'getUserPreferences';
  variables: {
    userId: string;
  };
};

type RequestDataForListEventsForUserGivenDatesType = {
  method: 'listEventsForUserGivenDates';
  variables: {
    userId: string;
    hostStartDate: string;
    hostEndDate: string;
    userTimezone: string;
    hostTimezone: string;
  };
};

type RequestDataForListMeetingAssistAttendeesType = {
  method: 'listMeetingAssistAttendeesGivenMeetingId';
  variables: {
    meetingId: string;
  };
};

type RequestDataForListMeetingAssistEventsForAttendeeType = {
  method: 'listMeetingAssistEventsForAttendeeGivenDates';
  variables: {
    attendeeId: string;
    hostStartDate: string;
    hostEndDate: string;
    userTimezone: string;
    hostTimezone: string;
  };
};

type RequestDataForListMeetingAssistPreferredTimeRangesType = {
  method: 'listMeetingAssistPreferredTimeRangesGivenMeetingId';
  variables: {
    meetingId: string;
  };
};

type RequestDataForStartMeetingAssistType = {
  method: 'startMeetingAssist';
  variables: {
    body: ScheduleAssistWithMeetingQueueBodyType;
  };
};

type RequestDataUpsertMeetingAsistPreferredTimesType = {
  method: 'upsertMeetingAssistPreferredTimes';
  variables: {
    preferredTimes: MeetingAssistPreferredTimeRangeType[];
  };
};

type RequestDataForDeleteMeetingAssistPreferredTimesByIdsType = {
  method: 'deleteMeetingAssistPreferredTimesByIds';
  variables: {
    ids: string[];
  };
};

type RequestDataForCreateRecurringMeetingAssistsType = {
  method: 'createRecurringMeetingAssists';
  variables: {
    originalMeetingAssist: MeetingAssistType;
    originalPreferredTimes?: MeetingAssistPreferredTimeRangeType[];
  };
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<
    | EventType[]
    | AvailableSlotsByDate
    | MeetingAssistType
    | UserPreferenceType
    | MeetingAssistAttendeeType[]
    | MeetingAssistEventType[]
    | MeetingAssistPreferredTimeRangeType[]
    | undefined
    | number
  >
) {
  try {
    const body:
      | RequestDataForDeleteMeetingAssistPreferredTimesType
      | RequestDataForFindEventForUserType
      | RequestDataForGenerateAvailableSlotsforTimeWindowType
      | RequestDataForGetMeetingAssistType
      | RequestDataForGetUserPreferencesType
      | RequestDataForListEventsForUserGivenDatesType
      | RequestDataForListMeetingAssistAttendeesType
      | RequestDataForListMeetingAssistEventsForAttendeeType
      | RequestDataForListMeetingAssistPreferredTimeRangesType
      | RequestDataForStartMeetingAssistType
      | RequestDataUpsertMeetingAsistPreferredTimesType
      | RequestDataForDeleteMeetingAssistPreferredTimesByIdsType
      | RequestDataForCreateRecurringMeetingAssistsType = req.body;

    if (body?.method === 'findEventsForUserGivenMeetingId') {
      const {
        userId,
        hostStartDate,
        hostEndDate,
        userTimezone,
        hostTimezone,
        meetingId,
      } = (body as RequestDataForFindEventForUserType)?.variables;
      const events = await findEventsForUserGivenMeetingId(
        userId,
        hostStartDate,
        hostEndDate,
        userTimezone,
        hostTimezone,
        meetingId
      );

      return res.status(200).json(events);
    }

    if (body?.method === 'generateAvailableSlotsforTimeWindow') {
      const {
        windowStartDate,
        windowEndDate,
        slotDuration,
        hostPreferences,
        hostTimezone,
        userTimezone,
        notAvailableSlotsInUserTimezone,
      } = (body as RequestDataForGenerateAvailableSlotsforTimeWindowType)
        ?.variables;
      const { availableSlotsByDate } =
        await generateAvailableSlotsforTimeWindow(
          windowStartDate,
          windowEndDate,
          slotDuration,
          hostPreferences,
          hostTimezone,
          userTimezone,
          notAvailableSlotsInUserTimezone
        );

      return res.status(200).json(availableSlotsByDate);
    }

    if (body?.method === 'getMeetingAssist') {
      const { id } = (body as RequestDataForGetMeetingAssistType)?.variables;
      const meetingAssist = await getMeetingAssist(id);

      if (meetingAssist) {
        return res.status(200).json(meetingAssist);
      }
    }

    if (body?.method === 'getUserPreferences') {
      const { userId } = (body as RequestDataForGetUserPreferencesType)
        ?.variables;
      const userPreferences = await getUserPreferences(userId);

      if (userPreferences) {
        return res.status(200).json(userPreferences);
      }
    }

    if (body?.method === 'listEventsForUserGivenDates') {
      const { userId, hostStartDate, hostEndDate, userTimezone, hostTimezone } =
        (body as RequestDataForListEventsForUserGivenDatesType)?.variables;
      const events = await listEventsForUserGivenDates(
        userId,
        hostStartDate,
        hostEndDate,
        userTimezone,
        hostTimezone
      );

      return res.status(200).json(events);
    }

    if (body?.method === 'listMeetingAssistAttendeesGivenMeetingId') {
      const { meetingId } = (
        body as RequestDataForListMeetingAssistAttendeesType
      )?.variables;
      const attendees =
        await listMeetingAssistAttendeesGivenMeetingId(meetingId);

      if (attendees) {
        return res.status(200).json(attendees);
      }
    }

    if (body?.method === 'listMeetingAssistEventsForAttendeeGivenDates') {
      const {
        attendeeId,
        hostStartDate,
        hostEndDate,
        userTimezone,
        hostTimezone,
      } = (body as RequestDataForListMeetingAssistEventsForAttendeeType)
        ?.variables;
      const meetingAssistEvents =
        await listMeetingAssistEventsForAttendeeGivenDates(
          attendeeId,
          hostStartDate,
          hostEndDate,
          userTimezone,
          hostTimezone
        );

      return res.status(200).json(meetingAssistEvents);
    }

    if (body?.method === 'listMeetingAssistPreferredTimeRangesGivenMeetingId') {
      const { meetingId } = (
        body as RequestDataForListMeetingAssistPreferredTimeRangesType
      )?.variables;
      const meetingAssistPreferredTimeRanges =
        await listMeetingAssistPreferredTimeRangesGivenMeetingId(meetingId);

      return res.status(200).json(meetingAssistPreferredTimeRanges);
    }

    if (body?.method === 'startMeetingAssist') {
      const { body: subBody } = (body as RequestDataForStartMeetingAssistType)
        ?.variables;
      await startMeetingAssist(subBody);

      return res.status(204).end();
    }

    if (body?.method === 'upsertMeetingAssistPreferredTimes') {
      const { preferredTimes } = (
        body as RequestDataUpsertMeetingAsistPreferredTimesType
      )?.variables;
      const meetingAssistPreferredTimesAffectedRows =
        await upsertMeetingAssistPreferredTimes(preferredTimes);

      if (
        typeof meetingAssistPreferredTimesAffectedRows === 'number' &&
        meetingAssistPreferredTimesAffectedRows > -1
      ) {
        return res.status(200).json(meetingAssistPreferredTimesAffectedRows);
      }
    }

    if (body?.method === 'deleteMeetingAssistPreferredTimesByIds') {
      const { ids } = (
        body as RequestDataForDeleteMeetingAssistPreferredTimesByIdsType
      )?.variables;
      await deleteMeetingAssistPreferredTimesByIds(ids);

      return res.status(204).end();
    }

    if (body?.method === 'createRecurringMeetingAssists') {
      const { originalMeetingAssist, originalPreferredTimes } = (
        body as RequestDataForCreateRecurringMeetingAssistsType
      )?.variables;
      console.log('inside api createRecurringMeetingAssists');
      await createRecurringMeetingAssists(
        originalMeetingAssist,
        originalPreferredTimes
      );

      return res.status(204).end();
    }

    return res.status(404).end();
  } catch (e) {
    console.log(e, ' unable to get meeting assist');
    return res.status(404).end();
  }
  // res.status(200).json({ name: 'John Doe' })
}
