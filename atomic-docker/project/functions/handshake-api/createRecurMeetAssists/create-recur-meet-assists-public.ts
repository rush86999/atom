import { Request, Response } from 'express';
import { CreateRecurringMeetingAssistType } from '@handshake_api/_libs/types';
import { createRecurringMeetingAssists } from '@handshake_api/_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const createRecurringMeetingBody: CreateRecurringMeetingAssistType =
      req.body;

    const originalMeetingAssist =
      createRecurringMeetingBody?.originalMeetingAssist;
    const originalPreferredTimes =
      createRecurringMeetingBody?.originalPreferredTimes;

    if (!originalMeetingAssist?.id) {
      return res.status(400).json({
        message: 'no originalMeetingAssistt present',
        event: req,
      });
    }

    await createRecurringMeetingAssists(
      originalMeetingAssist,
      originalPreferredTimes
    );

    return res.status(200).json({
      message: `successfully created meeting assists`,
      event: req,
    });
  } catch (e) {
    console.log(e, ' unable to create recurringMeetingAssists');
    return res.status(400).json({
      message: 'no originalMeetingAssistt present',
      event: e,
    });
  }
};

export default handler;
