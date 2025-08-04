// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import { getCustomAvailableTimes } from '@lib/api-helper';
import { CustomAvailableTimeType, UserPreferenceType } from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';

type RequestData = {
  method: 'getCustomAvailableTimes';
  variables: {
    slotDuration: number;
    hostStartDate: string;
    hostPreferences: UserPreferenceType;
    hostTimezone: string;
    userTimezone: string;
    isFirstDay?: boolean;
    isLastDay?: boolean;
  };
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<CustomAvailableTimeType>
) {
  try {
    const body: RequestData = req.body;

    if (body?.method === 'getCustomAvailableTimes') {
      const {
        slotDuration,
        hostStartDate,
        hostPreferences,
        hostTimezone,
        userTimezone,
        isFirstDay,
        isLastDay,
      } = (body as RequestData)?.variables;
      const customAvailableTimeForDay = await getCustomAvailableTimes(
        slotDuration,
        hostStartDate,
        hostPreferences,
        hostTimezone,
        userTimezone,
        isFirstDay,
        isLastDay
      );
      if (customAvailableTimeForDay) {
        return res.status(200).json(customAvailableTimeForDay);
      }
    }

    return res.status(404).end();
  } catch (e) {
    console.log(e, ' unable to get meeting assist');
    return res.status(404).end();
  }
  // res.status(200).json({ name: 'John Doe' })
}
