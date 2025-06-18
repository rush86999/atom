import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';
import { getAtomMicrosoftGraphTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils';

// Assuming supertokens.init is called globally

type Data = {
  isConnected: boolean;
  email?: string | null; // Email associated with the connected Microsoft account
  error?: string;
};

async function getMicrosoftConnectionStatus(req: NextApiRequest, res: NextApiResponse<Data>) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    console.log(`Fetching Atom Microsoft Graph token status for userId: ${userId}`);
    const tokens = await getAtomMicrosoftGraphTokens(userId);

    if (tokens && tokens.access_token) {
      // TODO: Consider a lightweight API call to Microsoft Graph to verify token validity if needed.
      console.log(`Microsoft Graph tokens found for userId: ${userId}. Reporting as connected. Email: ${tokens.appEmail}`);
      return res.status(200).json({ isConnected: true, email: tokens.appEmail || null });
    } else {
      console.log(`No valid Microsoft Graph tokens found for userId: ${userId}. Reporting as not connected.`);
      return res.status(200).json({ isConnected: false });
    }
  } catch (error: any) {
    console.error(`Error fetching Atom Microsoft Graph token status for userId: ${userId}:`, error.message);
    return res.status(500).json({ isConnected: false, error: 'Failed to retrieve Microsoft Graph connection status.' });
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
  return await getMicrosoftConnectionStatus(req, res);
}
