import type { NextApiRequest, NextApiResponse } from 'next';
import qs from 'qs';
import Cors from 'cors';
import {
  deAuthZoomGivenUserId,
  validateZoomWebook,
  verifyZoomWebhook,
} from '@lib/api-helper';
import {
  ZoomWebhookDeAuthRequestType,
  ZoomWebhookRequestType,
  ZoomWebhookValidationRequestType,
} from '@lib/types';

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

    verifyZoomWebhook(req as ZoomWebhookRequestType);

    console.log(req?.body, ' req?.body');

    switch (req?.body?.event) {
      case 'endpoint.url_validation':
        return validateZoomWebook(req as ZoomWebhookValidationRequestType, res);
      case 'app_deauthorized':
        await deAuthZoomGivenUserId(
          (req as ZoomWebhookDeAuthRequestType)?.body?.payload?.user_id
        );
        return res.status(204).end();
      default:
        return res.status(204).end();
    }
  } catch (e) {
    console.log(e, ' unable to handle webhook request');
    return res.status(400).end();
  }
}
