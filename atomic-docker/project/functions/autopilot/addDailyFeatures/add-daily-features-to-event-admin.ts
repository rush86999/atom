import { Request, Response } from 'express';
import { AddDailyFeaturesApplyEventTriggerType } from '@autopilot/_libs/types';
import { createInitialFeaturesApplyToEventTrigger } from '@autopilot/_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const eventItem: AddDailyFeaturesApplyEventTriggerType = req.body;

    // validate
    if (!eventItem?.body?.userId) {
      return res.status(400).json({
        message: 'no userId present',
        event: eventItem,
      });
    }

    if (!eventItem?.body?.windowStartDate) {
      return res.status(400).json({
        message: 'no startDate',
        event: eventItem,
      });
    }

    if (!eventItem?.body?.windowEndDate) {
      return res.status(400).json({
        message: 'no endDate',
        event: eventItem,
      });
    }

    if (!eventItem?.body?.timezone) {
      return res.status(400).json({
        message: 'no timezone present',
        event: eventItem,
      });
    }

    if (!eventItem?.autopilot?.userId) {
      return res.status(400).json({
        message: 'no timezone present',
        event: eventItem,
      });
    }

    if (!eventItem?.autopilot?.scheduleAt) {
      return res.status(400).json({
        message: 'no autopilot scheduleAt present',
        event: eventItem,
      });
    }

    if (!eventItem?.autopilot?.timezone) {
      return res.status(400).json({
        message: 'no timezone present',
        event: eventItem,
      });
    }

    if (!eventItem?.autopilot?.payload) {
      return res.status(400).json({
        message: 'no payload present',
        event: eventItem,
      });
    }

    await createInitialFeaturesApplyToEventTrigger(
      eventItem?.autopilot,
      eventItem?.body
    );

    res.status(200).json('successfully started add daily features to event');
  } catch (e) {
    console.log(e, ' unable to add daily features to event');
    res.status(400).json(e);
  }
};

export default handler;
