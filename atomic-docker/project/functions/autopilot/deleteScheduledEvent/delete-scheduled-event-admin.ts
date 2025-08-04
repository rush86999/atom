import { Request, Response } from 'express';
import { DeleteScheduledEventBody } from '@autopilot/_libs/types';
import { deleteScheduledEventForAutopilot } from '@autopilot/_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const eventItem: DeleteScheduledEventBody = req.body;

    // validate
    if (!eventItem) {
      return res.status(400).json({
        message: 'eventId missing',
        event: eventItem,
      });
    }

    await deleteScheduledEventForAutopilot(eventItem);

    res
      .status(200)
      .json('successfully deleted scheduled event for autopilot to event');
  } catch (e) {
    console.log(e, ' error');
    res.status(400).json(e);
  }
};

export default handler;
