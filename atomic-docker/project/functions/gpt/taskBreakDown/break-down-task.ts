import { Request, Response } from 'express';
import { BreakDownTaskRequestBodyType } from '../_libs/types';
import { breakDownTask } from '../_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const reqBody: BreakDownTaskRequestBodyType = req?.body;
    console.log('breakDownTaskHandler called');
    // validate
    if (!reqBody?.userId) {
      console.log('!reqBody?.userId');
      return res.status(400).json({
        message: 'no userId present',
        event: reqBody,
      });
    }

    if (!reqBody?.startDate) {
      console.log('!reqBody?.startDate');
      return res.status(400).json({
        message: 'no startDate present',
        event: reqBody,
      });
    }

    if (!reqBody?.endDate) {
      console.log('!reqBody?.endDate');
      return res.status(400).json({
        message: 'no endDate present',
        event: reqBody,
      });
    }

    if (!reqBody?.timezone) {
      console.log('!reqBody?.timezone');
      return res.status(400).json({
        message: 'no timezone present',
        event: reqBody,
      });
    }

    if (!reqBody?.task) {
      console.log('!reqBody?.task');
      return res.status(400).json({
        message: 'no task present',
        event: reqBody,
      });
    }

    await breakDownTask(
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

    res.status(200).send('succesfully created task break down');
  } catch (e) {
    console.log(e, ' unable to create task break down');
    res.status(400).json(e);
  }
};

export default handler;
