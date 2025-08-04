import { Request, Response } from 'express';
import { sendBulkCancelToMeetingEmail } from '@email_notification/_libs/api-helpter';
import { BulkMeetingCancelledDetailsToAttendeeType } from '@email_notification/_libs/types';

const handler = async (req: Request, res: Response) => {
  try {
    const eventItem: BulkMeetingCancelledDetailsToAttendeeType = req.body;
    // validate

    if (!(eventItem?.attendees?.length > 0)) {
      return res.status(400).json({
        message: 'missing attendees',
        event: eventItem,
      });
    }

    if (!eventItem?.hostName) {
      return res.status(400).json({
        message: 'missing hostName',
        event: eventItem,
      });
    }

    if (!eventItem?.hostEmail) {
      return res.status(400).json({
        message: 'missing hostEmail',
        event: eventItem,
      });
    }

    await sendBulkCancelToMeetingEmail(eventItem);

    res.status(200).send('successfully sendBulkCancelToMeetingEmail');
  } catch (e) {
    console.log(e, ' unable to process message');

    console.log(
      res.status(400).json({
        message: `error processing queue mesages: message: ${e?.message}, code: ${e?.statusCode}`,
      })
    );

    res.status(400).json(e);
  }
};

export default handler;
