import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';
import { getAtomGoogleCalendarTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils'; // Adjusted path

// Assuming supertokens.init is called globally

type Data = {
  isConnected: boolean;
  email?: string; // Email associated with the connected calendar (mocked for now)
  error?: string;
};

async function getCalendarConnectionStatus(req: NextApiRequest, res: NextApiResponse<Data>) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    console.log(`Fetching Atom Google Calendar token status for userId: ${userId}`);
    const tokens = await getAtomGoogleCalendarTokens(userId);

    if (tokens && tokens.access_token) {
      // TODO: In a real scenario, you might want to verify if the access token is still valid
      // by making a lightweight API call to Google (e.g., userinfo).
      // Also, the email should ideally be fetched from the user's profile or Google's token info.
      console.log(`Tokens found for userId: ${userId}. Reporting as connected.`);
      return res.status(200).json({ isConnected: true, email: "user_from_token@example.com" }); // Mocked email
    } else {
      console.log(`No valid tokens found for userId: ${userId}. Reporting as not connected.`);
      return res.status(200).json({ isConnected: false });
    }
  } catch (error: any) {
    console.error(`Error fetching Atom Google Calendar token status for userId: ${userId}:`, error.message);
    return res.status(500).json({ isConnected: false, error: 'Failed to retrieve calendar connection status.' });
  }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse<Data>) {
  await superTokensNextWrapper(
    async (next) => {
      // Ensure user is authenticated
      return await verifySession()(req, res, next);
    },
    req,
    res
  );
  if (res.writableEnded) {
      return;
  }
  return await getCalendarConnectionStatus(req, res);
}
