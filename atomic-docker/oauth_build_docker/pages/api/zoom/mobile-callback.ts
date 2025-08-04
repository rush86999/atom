// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import {
  getMinimalCalendarIntegration,
  updateZoomIntegration,
} from '@lib/api-helper';
import { CalendarIntegrationType } from '@lib/types';
import type { NextApiRequest, NextApiResponse } from 'next';

// type RequestMinimalCalendarIntegrationType = {
//     method: 'getMinimalCalendarIntegration',
//     variables: {
//         userId: string,
//         resource: string,
//     }
// }

type RequestUpdateZoomIntegrationType = {
  method: 'updateZoomIntegration';
  variables: {
    id: string;
    appAccountId: string;
    appEmail: string;
    appId: string;
    token: string | null;
    expiresIn: number | null;
    refreshToken?: string;
    contactFirstName?: string;
    contactLastName?: string;
    phoneCountry?: string; // 'US'
    phoneNumber?: string; // '+1 1234567891'
    enabled?: boolean;
  };
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<CalendarIntegrationType | undefined>
) {
  try {
    const body: RequestUpdateZoomIntegrationType = req.body;

    if (body?.method === 'updateZoomIntegration') {
      const {
        id,
        appAccountId,
        appEmail,
        appId,
        token,
        refreshToken,
        expiresIn,
        contactFirstName,
        contactLastName,
        phoneCountry, // 'US'
        phoneNumber, // '+1 1234567891'
        enabled,
      } = body?.variables;
      await updateZoomIntegration(
        id,
        appAccountId,
        appEmail,
        appId,
        token,
        expiresIn,
        refreshToken,
        contactFirstName,
        contactLastName,
        phoneCountry, // 'US'
        phoneNumber, // '+1 1234567891'
        enabled
      );

      return res.status(204).end();
    }

    return res.status(404).end();
  } catch (e) {
    console.log(e, ' unable to process');
    res.status(404).end();
  }
}
