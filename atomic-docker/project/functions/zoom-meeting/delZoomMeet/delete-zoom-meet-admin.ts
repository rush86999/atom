import { Request, Response } from 'express';
import {
  deleteZoomMeeting,
  getZoomAPIToken,
} from '@zoom_meeting/_libs/api-helper';
import { DeleteZoomMeetObjectType } from '@zoom_meeting/_libs/types';

const publisher = async (req: Request, res: Response) => {
  try {
    const eventItem: DeleteZoomMeetObjectType = req.body;

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

    await deleteZoomMeeting(
      zoomToken,
      eventItem?.meetingId,
      eventItem?.scheduleForReminder,
      eventItem?.cancelMeetingReminder
    );

    res.status(202).json('del zoom meeting successfully');
  } catch (e) {
    console.log(e, ' unable to process message');

    res.status(400).json({
      message: `error processing queue mesages: message: ${e?.message}, code: ${e?.statusCode}`,
      event: e,
    });
  }
};

export default publisher;
