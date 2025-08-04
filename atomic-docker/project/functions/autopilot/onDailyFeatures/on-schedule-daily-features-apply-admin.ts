import { Request, Response } from 'express';
import { HasuraTriggerBodyType } from '@autopilot/_libs/types';
import { onScheduleDailyFeaturesApply7DayWindowToEventTrigger } from '@autopilot/_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const eventItem: HasuraTriggerBodyType = req.body;

    const payload = eventItem.payload;
    console.log(payload, ' parsed payload');
    // validate
    if (!payload?.body?.userId) {
      return res.status(400).json({
        message: 'no userId present',
        event: eventItem,
      });
    }

    if (!payload?.body?.windowStartDate) {
      return res.status(400).json({
        message: 'no startDate',
        event: eventItem,
      });
    }

    if (!payload?.body?.windowEndDate) {
      return res.status(400).json({
        message: 'no endDate',
        event: eventItem,
      });
    }

    if (!payload?.body?.timezone) {
      return res.status(400).json({
        message: 'no timezone present',
        event: eventItem,
      });
    }

    if (!payload?.autopilot?.userId) {
      return res.status(400).json({
        message: 'no autopilot userId present',
        event: eventItem,
      });
    }

    if (!payload?.autopilot?.scheduleAt) {
      return res.status(400).json({
        message: 'no autopilot scheduleAt present',
        event: eventItem,
      });
    }

    if (!payload?.autopilot?.timezone) {
      return res.status(400).json({
        message: 'no timezone present',
        event: eventItem,
      });
    }

    if (!payload?.autopilot?.payload) {
      return res.status(400).json({
        message: 'no payload present',
        event: eventItem,
      });
    }

    await onScheduleDailyFeaturesApply7DayWindowToEventTrigger(
      payload?.autopilot,
      payload?.body
    );

    res
      .status(200)
      .json('successfully triggered on schedule daily features apply to event');
  } catch (e) {
    console.log(e, ' unable to on schedule daily features apply auth');
    res.status(400).json(e);
  }
};

export default handler;
