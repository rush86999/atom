import { Request, Response } from 'express';

import { googleCalendarWebRefreshToken } from '@google_api_auth/_libs/api-helper';

const handler = async (req: Request, res: Response) => {
  try {
    const refreshToken = req.body.refreshToken;

    if (!refreshToken) {
      return res.status(400).json({
        message: 'missing refreshToken',
        event: req.body,
      });
    }

    const tokens = await googleCalendarWebRefreshToken(refreshToken);

    return res.status(200).json({
      message: 'retrieved token successfully',
      event: tokens,
    });
  } catch (e) {
    console.log(e, ' unable to retrieve token successfully');
    return res.status(400).json({
      message: 'something went wrong with getting token',
      event: e,
    });
  }
};

export default handler;
