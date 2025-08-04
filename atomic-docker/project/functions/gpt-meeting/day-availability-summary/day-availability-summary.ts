import { Request, Response } from 'express';
import { DayAvailabilityType } from '../_libs/types/availabilityTypes';
import { process_day_availibility } from '../_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const body: DayAvailabilityType = req.body;

    // validate values
    if (!body?.userId) {
      return res.status(400).json({
        message: 'no userId present',
        event: body,
      });
    }

    if (!body?.windowStartDate) {
      return res.status(400).json({
        message: 'no window start date present',
        event: body,
      });
    }

    if (!body?.windowEndDate) {
      return res.status(400).json({
        message: 'no window end date present',
        event: body,
      });
    }

    if (!body?.senderTimezone) {
      return res.status(400).json({
        message: 'no sender timezone present',
        event: body,
      });
    }

    if (!body?.receiverTimezone) {
      return res.status(400).json({
        message: 'no receiver time zone present',
        event: body,
      });
    }

    if (!body?.slotDuration) {
      return res.status(400).json({
        message: 'no not slot duration present',
        event: body,
      });
    }

    const response = await process_day_availibility(body);

    console.log(response, ' response');
    res.status(200).json(response);
  } catch (e) {
    console.log(e, ' unable to generate day availability summary');
    res.status(400).json(e);
  }
};

export default handler;
