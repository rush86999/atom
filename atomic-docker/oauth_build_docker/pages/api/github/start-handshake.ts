import type { NextApiRequest, NextApiResponse } from 'next';
import { generateGithubAuthUrl } from '@lib/api-helper';
import Cors from 'cors';

const cors = Cors({
  methods: ['POST', 'GET', 'HEAD'],
});

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
    await runMiddleware(req, res, cors);

    const state = req.query.state as string || 'no_state_provided';
    const authorizationUrl = generateGithubAuthUrl(state);
    res.redirect(authorizationUrl);
  } catch (e) {
    console.log(e, ' unable to auth');
    res.status(500).json({ error: 'Unable to authorize' });
  }
}
