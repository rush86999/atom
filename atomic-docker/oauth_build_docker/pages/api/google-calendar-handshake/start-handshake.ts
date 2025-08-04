import type { NextApiRequest, NextApiResponse } from 'next';
import qs from 'qs';
import Cors from 'cors';
import { generateGoogleAuthUrl } from '@lib/api-helper';

// Initializing the cors middleware
// You can read more about the available options here: https://github.com/expressjs/cors#configuration-options
const cors = Cors({
  methods: ['POST', 'GET', 'HEAD'],
  origin: ['https://atomiclife.app', /\.atomiclife\.app$/],
});

// Helper method to wait for a middleware to execute before continuing
// And to throw an error when an error happens in a middleware
function runMiddleware(
  req: NextApiRequest,
  res: NextApiResponse,
  fn: Function
) {
  return new Promise((resolve, reject) => {
    fn(req, res, (result: any) => {
      if (result instanceof Error) {
        return reject(result);
      }

      return resolve(result);
    });
  });
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    // Run the middleware
    await runMiddleware(req, res, cors);

    // attendeeId, meetingId
    const attendeeId = req?.query?.attendeeId;
    const meetingId = req?.query?.meetingId;
    console.log(attendeeId, ' ateendeeId');
    console.log(meetingId, ' meetingId');

    const state = `${meetingId}#${attendeeId}`;

    const authorizationUrl = generateGoogleAuthUrl(state);

    // return res.writeHead(301, { "Location": authorizationUrl });
    return res.redirect(authorizationUrl);
  } catch (e) {
    console.log(e, ' unable to auth');
    return res.status(404).json(e);
  }
}
