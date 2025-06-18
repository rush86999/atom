import type { NextApiRequest, NextApiResponse } from 'next';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';
import { deleteAtomMicrosoftGraphTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils';

// Assuming supertokens.init is called globally

type Data = {
  success: boolean;
  message: string;
};

async function handleDisconnectMicrosoftGraph(req: NextApiRequest, res: NextApiResponse<Data>) {
  if (req.method !== 'POST') { // Assuming POST for disconnect
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    // TODO: Implement actual token revocation with Microsoft Graph if necessary before deleting from DB.
    // This usually involves calling:
    // `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/revoke?token={refresh_token}&token_type_hint=refresh_token`
    // Or, if only access token needs invalidation (less common for full disconnect):
    // `https://graph.microsoft.com/v1.0/me/invalidateAllRefreshTokens` (requires specific admin consent)
    // For now, deleting from our DB is the primary step.
    console.log(`Attempting to delete Atom Microsoft Graph tokens for userId: ${userId}`);

    await deleteAtomMicrosoftGraphTokens(userId);

    console.log(`Atom Microsoft Graph tokens for userId: ${userId} marked for deletion from DB.`);
    return res.status(200).json({ success: true, message: 'Microsoft Account disconnected successfully for Atom Agent.' });

  } catch (error: any) {
    console.error(`Error during Microsoft Graph disconnect for Atom Agent (userId: ${userId}):`, error.message);
    res.status(500).json({ success: false, message: `Failed to disconnect Microsoft Account for Atom Agent: ${error.message}` });
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
  return await handleDisconnectMicrosoftGraph(req, res);
}
