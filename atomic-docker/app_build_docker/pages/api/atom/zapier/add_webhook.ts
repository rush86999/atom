import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';
import { addZapierWebhook } from '../../../../../project/functions/atom-agent/_libs/zapier-utils';

type Data = {
  success: boolean;
  message?: string;
  webhook?: { id: string; zap_name: string };
  error?: string;
};

async function handler(req: NextApiRequest, res: NextApiResponse<Data>) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  const { zap_name, webhook_url } = req.body;

  if (!zap_name || !webhook_url) {
    return res.status(400).json({ success: false, error: 'Missing zap_name or webhook_url in request body' });
  }

  // Basic URL validation (can be enhanced)
  try {
    new URL(webhook_url);
  } catch (_) {
    return res.status(400).json({ success: false, error: 'Invalid webhook_url format' });
  }


  try {
    const newWebhook = await addZapierWebhook(userId, zap_name, webhook_url);
    if (newWebhook) {
      return res.status(201).json({ success: true, message: 'Zapier webhook added/updated successfully.', webhook: newWebhook });
    } else {
      // This case might not be reached if addZapierWebhook throws on failure,
      // but included for robustness if it could return null on some specific non-exceptional failures.
      return res.status(500).json({ success: false, error: 'Failed to add/update Zapier webhook.' });
    }
  } catch (error: any) {
    console.error(`Error in /api/atom/zapier/add_webhook for userId ${userId}:`, error.message);
    // Check if it's a known error type, e.g., from unique constraint violation or encryption failure
    if (error.message.toLowerCase().includes('unique constraint') || error.message.toLowerCase().includes('zap_name already exists')) {
        return res.status(409).json({ success: false, error: `A Zap with the name "${zap_name}" already exists. Please use a different name.`});
    }
    if (error.message.toLowerCase().includes('encryption failed')) {
        return res.status(500).json({ success: false, error: 'Failed to secure webhook information.' });
    }
    return res.status(500).json({ success: false, error: error.message || 'Internal server error adding Zapier webhook.' });
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
