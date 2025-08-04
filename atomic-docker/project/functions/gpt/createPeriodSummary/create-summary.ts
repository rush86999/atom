import { Request, Response } from 'express';
import { CreatePeriodSummaryRequestBodyType } from '../_libs/types';
import { createSummaryOfTimePeriod } from '../_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const reqBody: CreatePeriodSummaryRequestBodyType = req?.body;

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

    await createSummaryOfTimePeriod(
      reqBody?.userId,
      reqBody?.startDate,
      reqBody?.endDate,
      reqBody?.timezone,
      reqBody?.email,
      reqBody?.name
    );

    res.status(200).send('succesfully created summary of time period');
  } catch (e) {
    console.log(e, ' unable to create summary');
    res.status(400).json(e);
  }
};

export default handler;
