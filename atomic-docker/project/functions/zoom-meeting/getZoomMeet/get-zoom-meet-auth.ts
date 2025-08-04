import { Request, Response } from 'express';
import {
  getZoomAPIToken,
  getZoomMeeting,
} from '@zoom_meeting/_libs/api-helper';
import { GetZoomMeetObjectType } from '@zoom_meeting/_libs/types';

const publisher = async (req: Request, res: Response) => {
  try {
    const eventItem: GetZoomMeetObjectType = req.body;

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

    const response = await getZoomMeeting(zoomToken, eventItem?.meetingId);

    res.status(200).json(response);
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
