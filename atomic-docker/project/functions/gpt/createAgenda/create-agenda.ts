import { Request, Response } from 'express';
import { CreateAgendaRequestBodyType } from '../_libs/types';
import { createAgenda } from '../_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const reqBody: CreateAgendaRequestBodyType = req.body;
    console.log(reqBody, ' reqBody');
    // validate

    if (!reqBody?.userId) {
      console.log('no userId');
      return res.status(400).json({
        message: 'no userId present',
        event: reqBody,
      });
    }

    if (!reqBody?.timezone) {
      console.log('no timezone');
      return res.status(400).json({
        message: 'no timezone present',
        event: reqBody,
      });
    }

    if (!reqBody?.startDate) {
      console.log('no startDate');
      return res.status(400).json({
        message: 'no startDate present',
        event: reqBody,
      });
    }

    if (!reqBody?.endDate) {
      console.log('no endDate');
      return res.status(400).json({
        message: 'no endDate present',
        event: reqBody,
      });
    }

    if (!reqBody?.mainTopic) {
      console.log('no mainTopic');
      return res.status(400).json({
        message: 'no mainTopic present',
        event: reqBody,
      });
    }

    await createAgenda(
      reqBody?.userId,
      reqBody?.isAllDay,
      reqBody?.timezone,
      reqBody?.startDate,
      reqBody?.endDate,
      reqBody?.mainTopic,
      reqBody?.email,
      reqBody?.name,
      reqBody?.relevantPoints,
      reqBody?.goals,
      reqBody?.location,
      reqBody?.isTwo
    );

    res.status(200).send('succesfully created agenda');
  } catch (e) {
    console.log(e, ' unable to create agenda');
    res.status(400).json(e);
  }
};

export default handler;
