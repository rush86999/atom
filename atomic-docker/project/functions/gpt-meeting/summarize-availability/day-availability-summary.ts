import { Request, Response } from 'express';
import { SummarizeDayAvailabilityType } from '../_libs/types/availabilityTypes';
import { process_summarize_availability } from '../_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const body: SummarizeDayAvailabilityType = req.body;

    // validate values
    if (!body?.userId) {
      return res.status(400).json({
        message: 'no userId present',
        event: body,
      });
    }

    if (!body?.dayAvailabilityList) {
      return res.status(400).json({
        message: 'no dayAvailabilityList present',
        event: body,
      });
    }

    const response = await process_summarize_availability(body);

    console.log(response, ' response');

    res.status(200).json(response);
  } catch (e) {
    console.log(e, ' unable to summarized overall availability');
    res.status(400).json(e);
  }
};

export default handler;
