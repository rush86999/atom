import { Request, Response } from 'express';
import {
  getZoomAPIToken,
  updateZoomMeeting,
} from '@zoom_meeting/_libs/api-helper';
import { UpdateZoomMeetObjectType } from '@zoom_meeting/_libs/types';

const publisher = async (req: Request, res: Response) => {
  try {
    const eventItem: UpdateZoomMeetObjectType = req.body;

    // validate
    if (!eventItem?.meetingId) {
      return res.status(400).json({
        message: 'no meetingId present',
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

    await updateZoomMeeting(
      zoomToken,
      eventItem?.meetingId,
      eventItem?.startDate,
      eventItem?.timezone,
      eventItem?.agenda,
      eventItem?.duration,
      eventItem?.contactName,
      eventItem?.contactEmail,
      eventItem?.meetingInvitees,
      eventItem?.privateMeeting
    );

    res.status(202).json(eventItem);
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
