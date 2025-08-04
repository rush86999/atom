// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import {
  getMeetingAssist,
  getMeetingAssistAttendee,
  googleCalendarSync,
} from '@lib/api-helper';
import { MeetingAssistAttendeeType, MeetingAssistType } from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';

type RequestData = {
  method: 'getMeetingAssist' | 'getMeetingAssistAttendee';
  variables: { id: string };
};

type RequestData2 = {
  method: 'googleCalendarSync';
  variables: {
    token: string;
    windowStartDate: string;
    windowEndDate: string;
    attendeeId: string;
    hostTimezone: string;
  };
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<
    MeetingAssistType | MeetingAssistAttendeeType | undefined
  >
) {
  try {
    const body: RequestData | RequestData2 = req.body;

    if (body?.method === 'getMeetingAssist') {
      const id = (body as RequestData)?.variables?.id;
      const meetingAssist = await getMeetingAssist(id);
      if (meetingAssist?.id) {
        return res.status(200).json(meetingAssist);
      }
    }

    if (body?.method === 'getMeetingAssistAttendee') {
      const id = (body as RequestData)?.variables?.id;
      const meetingAssistAttendee = await getMeetingAssistAttendee(id);

      return res.status(200).json(meetingAssistAttendee);
    }

    if (body?.method === 'googleCalendarSync') {
      const {
        token,
        windowStartDate,
        windowEndDate,
        attendeeId,
        hostTimezone,
      } = (body as RequestData2).variables;

      await googleCalendarSync(
        token,
        windowStartDate,
        windowEndDate,
        attendeeId,
        hostTimezone
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
