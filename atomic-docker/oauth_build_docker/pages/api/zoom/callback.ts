import type { NextApiRequest, NextApiResponse } from 'next';
import qs from 'qs';
import Cors from 'cors';
import { appUrl } from '@lib/constants';

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
  // Run the middleware
  await runMiddleware(req, res, cors);

  const { code, state } = req.query;

  if (!code) {
    console.log(' no code present');
    return;
  }

  let params: any = { code };

  if (state && state?.length > 0) {
    params = { ...params, state };
  }

  return res.redirect(`${appUrl}?${qs.stringify(params)}`);
}
