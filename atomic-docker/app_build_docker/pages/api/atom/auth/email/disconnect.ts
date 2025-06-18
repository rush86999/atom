import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';
import { deleteAtomGmailTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils';

// Assuming supertokens.init is called globally

type Data = {
  success: boolean;
  message: string;
};

async function handleDisconnectGmail(req: NextApiRequest, res: NextApiResponse<Data>) {
  if (req.method !== 'POST') { // Assuming POST for disconnect
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    // TODO: Implement actual token revocation with Google if necessary before deleting from DB.
    // For Gmail, this is less common for server-side flows unless specific security requirements demand it.
    // Typically, deleting the refresh token from storage is sufficient to prevent future access.
    console.log(`Attempting to delete Atom Gmail tokens for userId: ${userId}`);

    await deleteAtomGmailTokens(userId);
    // deleteAtomGmailTokens will throw if there's a major issue.
    // If it completes, we assume success from our DB's perspective.

    console.log(`Atom Gmail tokens for userId: ${userId} marked for deletion from DB.`);
    return res.status(200).json({ success: true, message: 'Gmail account disconnected successfully for Atom Agent.' });

  } catch (error: any) {
    console.error(`Error during Gmail disconnect for Atom Agent (userId: ${userId}):`, error.message);
    res.status(500).json({ success: false, message: `Failed to disconnect Gmail account for Atom Agent: ${error.message}` });
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
  return await handleDisconnectGmail(req, res);
}
