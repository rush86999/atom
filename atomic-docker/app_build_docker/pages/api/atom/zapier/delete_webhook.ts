import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';
import { deleteZapierWebhook } from '../../../../../project/functions/atom-agent/_libs/zapier-utils';

type Data = {
  success: boolean;
  message?: string;
  error?: string;
  affected_rows?: number;
};

async function handler(req: NextApiRequest, res: NextApiResponse<Data>) {
  if (req.method !== 'POST') { // Using POST for delete to allow sending zap_id in body
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  const { zap_id } = req.body;

  if (!zap_id) {
    return res.status(400).json({ success: false, error: 'Missing zap_id in request body' });
  }

  try {
    const result = await deleteZapierWebhook(userId, zap_id);
    if (result.affected_rows > 0) {
      return res.status(200).json({ success: true, message: 'Zapier webhook deleted successfully.', affected_rows: result.affected_rows });
    } else {
      return res.status(404).json({ success: false, error: 'Zapier webhook not found or already deleted.', affected_rows: 0 });
    }
  } catch (error: any) {
    console.error(`Error in /api/atom/zapier/delete_webhook for userId ${userId}, zapId ${zap_id}:`, error.message);
    return res.status(500).json({ success: false, error: error.message || 'Internal server error deleting Zapier webhook.' });
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
