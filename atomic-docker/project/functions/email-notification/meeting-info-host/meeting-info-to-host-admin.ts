import { Request, Response } from 'express';
import { sendMeetingInviteDetailsToHost } from '@email_notification/_libs/api-helpter';
import { MeetingInviteDetailsToHostType } from '@email_notification/_libs/types';

const handler = async (req: Request, res: Response) => {
  try {
    const eventItem: MeetingInviteDetailsToHostType = req.body;

    await sendMeetingInviteDetailsToHost(eventItem);

    res.status(202).send('email for meeting invite sent to hostl');
  } catch (e) {
    console.log(e, ' unable to process message');

    res.status(400).json(e);
  }
};

export default handler;
