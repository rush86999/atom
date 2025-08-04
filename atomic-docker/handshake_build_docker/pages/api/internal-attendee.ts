// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import {
  cancelMeetingAssist,
  deleteMeetingAssistAttendee,
  getMeetingAssist,
  getMeetingAssistAttendee,
  getUserContactInfo,
  updateMeetingAssistAttendanceCount,
  updateMeetingAssistInviteResponse,
  upsertOneMeetingAssistAttendee,
} from '@lib/api-helper';
import {
  MeetingAssistAttendeeType,
  MeetingAssistType,
  UserContactInfoType,
} from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';

type RequestDataForGetUserContactInfoType = {
  method: 'getUserContactInfo';
  variables: { id: string };
};

type RequestDataForCancelMeetingAssistType = {
  method: 'cancelMeetingAssist';
  variables: { id: string };
};

type RequestDataForDeleteMeetingAssistAttendeeType = {
  method: 'deleteMeetingAssistAttendee';
  variables: { id: string };
};

type RequestDataForGetMeetingAssistType = {
  method: 'getMeetingAssist';
  variables: { id: string };
};

type RequestDataForGetMeetingAssistAttendeeType = {
  method: 'getMeetingAssistAttendee';
  variables: { id: string };
};

type RequestDataForUpsertMeetingAssistAttendeeType = {
  method: 'upsertOneMeetingAssistAttendee';
  variables: { attendee: MeetingAssistAttendeeType };
};

type RequestDataForUpdateMeetingAssistAttendanceCountType = {
  method: 'updateMeetingAssistAttendanceCount';
  variables: {
    id: string;
    attendeeCount: number;
    attendeeRespondedCount: number;
  };
};

type RequestDataForUpdateMeetingAssistInviteResponseType = {
  method: 'updateMeetingAssistInviteResponse';
  variables: { id: string; response: 'PENDING' | 'ATTENDING' | 'CANCELLED' };
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<
    | MeetingAssistType
    | MeetingAssistAttendeeType
    | UserContactInfoType
    | undefined
  >
) {
  try {
    const body:
      | RequestDataForCancelMeetingAssistType
      | RequestDataForDeleteMeetingAssistAttendeeType
      | RequestDataForGetMeetingAssistType
      | RequestDataForGetMeetingAssistAttendeeType
      | RequestDataForUpsertMeetingAssistAttendeeType
      | RequestDataForUpdateMeetingAssistAttendanceCountType
      | RequestDataForGetUserContactInfoType
      | RequestDataForUpdateMeetingAssistInviteResponseType = req.body;

    if (body?.method === 'cancelMeetingAssist') {
      const id = (body as RequestDataForCancelMeetingAssistType)?.variables?.id;
      const meetingAssistCancelled = await cancelMeetingAssist(id);
      if (meetingAssistCancelled?.id) {
        return res.status(200).json(meetingAssistCancelled);
      }
    }

    if (body?.method === 'getUserContactInfo') {
      const id = (body as RequestDataForGetUserContactInfoType)?.variables?.id;
      const userContactInfo = await getUserContactInfo(id);

      return res.status(200).json(userContactInfo);
    }

    if (body?.method === 'deleteMeetingAssistAttendee') {
      const id = (body as RequestDataForDeleteMeetingAssistAttendeeType)
        ?.variables?.id;
      const deletedMeetingAssistAttendee =
        await deleteMeetingAssistAttendee(id);
      if (deletedMeetingAssistAttendee?.id) {
        return res.status(200).json(deletedMeetingAssistAttendee);
      }
    }

    if (body?.method === 'getMeetingAssist') {
      const id = (body as RequestDataForGetMeetingAssistType)?.variables?.id;
      const meetingAssist = await getMeetingAssist(id);
      if (meetingAssist?.id) {
        return res.status(200).json(meetingAssist);
      }
    }

    if (body?.method === 'getMeetingAssistAttendee') {
      const id = (body as RequestDataForGetMeetingAssistAttendeeType)?.variables
        ?.id;
      const meetingAssistAttendee = await getMeetingAssistAttendee(id);

      return res.status(200).json(meetingAssistAttendee);
    }

    if (body?.method === 'upsertOneMeetingAssistAttendee') {
      const attendee = (body as RequestDataForUpsertMeetingAssistAttendeeType)
        ?.variables?.attendee;
      const meetingAssistAttendee =
        await upsertOneMeetingAssistAttendee(attendee);
      if (meetingAssistAttendee?.id) {
        return res.status(200).json(meetingAssistAttendee);
      }
    }

    if (body?.method === 'updateMeetingAssistAttendanceCount') {
      const { id, attendeeCount, attendeeRespondedCount } = (
        body as RequestDataForUpdateMeetingAssistAttendanceCountType
      )?.variables;

      const meetingAssistUpdatedCount =
        await updateMeetingAssistAttendanceCount(
          id,
          attendeeCount,
          attendeeRespondedCount
        );
      if (meetingAssistUpdatedCount?.id) {
        return res.status(200).json(meetingAssistUpdatedCount);
      }
    }

    if (body?.method === 'updateMeetingAssistInviteResponse') {
      const { id, response } = (
        body as RequestDataForUpdateMeetingAssistInviteResponseType
      )?.variables;

      await updateMeetingAssistInviteResponse(id, response);
      return res.status(204).end();
    }

    return res.status(404).end();
  } catch (e) {
    console.log(e, ' unable to get meeting assist');
    return res.status(404).end();
  }
  // res.status(200).json({ name: 'John Doe' })
}
