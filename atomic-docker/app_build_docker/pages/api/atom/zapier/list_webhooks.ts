import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';
import { listZapierWebhooks, ZapierWebhook } from '../../../../../project/functions/atom-agent/_libs/zapier-utils';

type Data = {
  success: boolean;
  webhooks?: ZapierWebhook[];
  error?: string;
};

async function handler(req: NextApiRequest, res: NextApiResponse<Data>) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    const webhooks = await listZapierWebhooks(userId);
    return res.status(200).json({ success: true, webhooks });
  } catch (error: any) {
    console.error(`Error in /api/atom/zapier/list_webhooks for userId ${userId}:`, error.message);
    return res.status(500).json({ success: false, error: error.message || 'Internal server error listing Zapier webhooks.' });
  }
}

export default async function mainHandler(req: NextApiRequest, res: NextApiResponse<Data>) {
  await superTokensNextWrapper(
    async (next) => verifySession()(req as any, res as any, next),
    req,
    res
  );
  if (res.writableEnded) {
    return;
  }
  return handler(req, res);
}
