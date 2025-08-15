import type { NextApiRequest, NextApiResponse } from 'next';
import { exchangeCodeForGithubTokens } from '@lib/api-helper';
import Cors from 'cors';
import supertokensNode from 'supertokens-node';
import { backendConfig } from '../../../../../config/backendConfig';
import Session from 'supertokens-node/recipe/session';
import { appUrl } from '@lib/constants';

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

supertokensNode.init(backendConfig());

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    await runMiddleware(req, res, cors);

    const session = await Session.getSession(req, res, {
      overrideGlobalClaimValidators: async function () {
        return [];
      },
    });
    const userId = session.getUserId();

    const thisUrl = new URL(req.url as string, `https://${req.headers.host}`);

    if (thisUrl.searchParams.get('error')) {
      return res.redirect(`${appUrl}?error=${thisUrl.searchParams.get('error')}`);
    }

    const code = thisUrl.searchParams.get('code') as string;
    await exchangeCodeForGithubTokens(code, userId);

    return res.redirect(`${appUrl}/Settings/UserViewCalendarAndContactIntegrations`);
  } catch (e) {
    console.log(e, ' unable to auth');
    if (e.type === Session.Error.TRY_REFRESH_TOKEN) {
      return res.status(401).send('Refresh token expired');
    } else if (e.type === Session.Error.UNAUTHORISED) {
      return res.status(401).send('Unauthorized');
    }
    return res.status(500).send('Internal server error');
  }
}
