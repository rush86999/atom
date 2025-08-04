import { Request, Response } from 'express';
import { HowToTaskRequestBodyType } from '../_libs/types';
import { howToTask } from '../_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const reqBody: HowToTaskRequestBodyType = req?.body;

    // validate
    if (!reqBody?.userId) {
      return res.status(400).json({
        message: 'no userId present',
        event: reqBody,
      });
    }

    if (!reqBody?.startDate) {
      return res.status(400).json({
        message: 'no startDate present',
        event: reqBody,
      });
    }

    if (!reqBody?.endDate) {
      return res.status(400).json({
        message: 'no endDate present',
        event: reqBody,
      });
    }

    if (!reqBody?.timezone) {
      return res.status(400).json({
        message: 'no timezone present',
        event: reqBody,
      });
    }

    if (!reqBody?.task) {
      return res.status(400).json({
        message: 'no task present',
        event: reqBody,
      });
    }

    await howToTask(
      reqBody?.userId,
      reqBody?.task,
      reqBody?.isAllDay,
      reqBody?.timezone,
      reqBody?.startDate,
      reqBody?.endDate,
      reqBody?.email,
      reqBody?.name,
      reqBody?.isTwo
    );

    res.status(200).send('succesfully created summary of time period');
  } catch (e) {
    console.log(e, ' unable to do how to task');
    res.status(400).json(e);
  }
};

export default handler;
