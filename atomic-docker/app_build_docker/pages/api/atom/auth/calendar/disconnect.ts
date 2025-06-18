import type { NextApiRequest, NextApiResponse } from 'next';

import { deleteAtomGoogleCalendarTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils'; // Adjusted path
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';


async function handleDisconnectGoogleCalendar(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') { // Assuming POST for disconnect
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    // --- TODO: Actual Token Revocation and Deletion Logic ---
    // 1. Retrieve the user's stored access token and refresh token for Google Calendar (Atom specific).
    // 2. If a refresh token exists, try to revoke it with Google:
    //    (This is important to invalidate the grant completely)
    //    Example using 'googleapis':
    //    try {
    //      const oauth2Client = new google.auth.OAuth2(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI);
    //      await oauth2Client.revokeToken(userRefreshToken); // or oauth2Client.revokeCredentials(userRefreshToken)
    //      console.log(`Successfully revoked Google token for user ${userId}`);
    //    } catch (revokeError: any) {
    //      console.error(`Failed to revoke Google token for user ${userId}:`, revokeError.message);
    //      // Decide if this is a hard failure or if you should proceed to delete local tokens anyway.
    //      // It's often good to proceed to ensure local data is cleared.
    //    }
    // --- TODO: Actual Token Revocation with Google (see previous comments in file) ---
    // For this step, we are focusing on deleting from our DB.
    // Actual revocation with Google would be an additional step before or after this.

    await deleteAtomGoogleCalendarTokens(userId);
    console.log(`Atom Google Calendar tokens for Atom Agent (userId: ${userId}) marked for deletion from DB.`);

    return res.status(200).json({ success: true, message: 'Google Calendar disconnected successfully for Atom Agent.' });

  } catch (error: any) {
    console.error(`Error during Google Calendar disconnect for Atom Agent (userId: ${userId}):`, error.message);
    res.status(500).json({ success: false, message: `Failed to disconnect Google Calendar for Atom Agent: ${error.message}` });
  }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  await superTokensNextWrapper(
    async (next) => {
      return await verifySession()(req, res, next);
    },
    req,
    res
  );
  if (res.writableEnded) {
      return;
  }
  return await handleDisconnectGoogleCalendar(req, res);
}
