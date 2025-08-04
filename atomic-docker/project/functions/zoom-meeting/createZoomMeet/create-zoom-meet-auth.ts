import { Request, Response } from 'express';
import {
  createZoomMeeting,
  getZoomAPIToken,
} from '@zoom_meeting/_libs/api-helper';
import { CreateZoomMeetObjectType } from '@zoom_meeting/_libs/types';

const publisher = async (req: Request, res: Response) => {
  try {
    const eventItem: CreateZoomMeetObjectType = req.body;

    // validate
    if (!eventItem?.startDate) {
      return res.status(400).json({
        message: 'no startDate present',
        event: eventItem,
      });
    }

    if (!eventItem?.timezone) {
      return res.status(400).json({
        message: 'no timezone',
        event: eventItem,
      });
    }

    if (!eventItem?.agenda) {
      return res.status(400).json({
        message: 'no agenda',
        event: eventItem,
      });
    }

    if (!eventItem?.duration) {
      return res.status(400).json({
        message: 'no duration',
        event: eventItem,
      });
    }

    if (!eventItem?.userId) {
      return res.status(400).json({
        message: 'no userId',
        event: eventItem,
      });
    }

    const zoomToken = await getZoomAPIToken(eventItem?.userId);

    const response = await createZoomMeeting(
      zoomToken,
      eventItem?.startDate,
      eventItem?.timezone,
      eventItem?.agenda,
      eventItem?.duration,
      eventItem?.contactName,
      eventItem?.contactEmail,
      eventItem?.meetingInvitees,
      eventItem?.privateMeeting
    );

    res.status(202).json(response);
  } catch (e) {
    console.log(e, ' unable to process message');

    console.log(
      res.status(400).json({
        message: `error processing queue mesages: message: ${e?.message}, code: ${e?.statusCode}`,
        event: e,
      })
    );
  }
};

export default publisher;
