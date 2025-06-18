import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';
import { getAtomGmailTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils';

// Assuming supertokens.init is called globally

type Data = {
  isConnected: boolean;
  email?: string | null; // Email associated with the connected Gmail account
  error?: string;
};

async function getGmailConnectionStatus(req: NextApiRequest, res: NextApiResponse<Data>) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    console.log(`Fetching Atom Gmail token status for userId: ${userId}`);
    const tokens = await getAtomGmailTokens(userId);

    if (tokens && tokens.access_token) {
      // TODO: Consider a lightweight API call to Google to verify token validity if needed.
      console.log(`Gmail tokens found for userId: ${userId}. Reporting as connected. Email: ${tokens.appEmail}`);
      return res.status(200).json({ isConnected: true, email: tokens.appEmail || null });
    } else {
      console.log(`No valid Gmail tokens found for userId: ${userId}. Reporting as not connected.`);
      return res.status(200).json({ isConnected: false });
    }
  } catch (error: any) {
    console.error(`Error fetching Atom Gmail token status for userId: ${userId}:`, error.message);
    return res.status(500).json({ isConnected: false, error: 'Failed to retrieve Gmail connection status.' });
  }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse<Data>) {
  await superTokensNextWrapper(
    async (next) => {
      return await verifySession()(req as any, res as any, next);
    },
    req,
    res
  );
  if (res.writableEnded) {
      return;
  }
  return await getGmailConnectionStatus(req, res);
}
