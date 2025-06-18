import type { NextApiRequest, NextApiResponse } from 'next';
import {
  ATOM_MSGRAPH_CLIENT_ID,
  ATOM_MSGRAPH_REDIRECT_URI,
  MSGRAPH_API_SCOPES,
  ATOM_MSGRAPH_TENANT_ID,
  MSGRAPH_OAUTH_AUTHORITY_BASE,
} from '../../../../../../project/functions/atom-agent/_libs/constants';
import crypto from 'crypto';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';

// Assuming supertokens.init is called globally

async function initiateMicrosoftAuth(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    if (!ATOM_MSGRAPH_CLIENT_ID || !ATOM_MSGRAPH_REDIRECT_URI || !ATOM_MSGRAPH_TENANT_ID) {
      console.error('Microsoft Graph OAuth environment variables not set for Atom Agent for userId:', userId);
      return res.status(500).json({ error: 'OAuth configuration error for Atom Agent Microsoft Graph.' });
    }

    const state = crypto.randomBytes(16).toString('hex');
    // TODO: Store this 'state' in the user's session to verify it in the callback for Microsoft Graph

    const scope = MSGRAPH_API_SCOPES.join(' ');
    const authorizeEndpoint = `${MSGRAPH_OAUTH_AUTHORITY_BASE}${ATOM_MSGRAPH_TENANT_ID}/oauth2/v2.0/authorize`;

    const params = new URLSearchParams({
        client_id: ATOM_MSGRAPH_CLIENT_ID,
        response_type: 'code',
        redirect_uri: ATOM_MSGRAPH_REDIRECT_URI,
        response_mode: 'query',
        scope: scope,
        state: state,
    });

    const authUrl = `${authorizeEndpoint}?${params.toString()}`;

    console.log(`Generated Microsoft Graph OAuth URL for Atom Agent (user: ${userId}): ${authUrl}`);
    res.redirect(authUrl);

  } catch (error: any) {
    console.error(`Error during Microsoft Graph OAuth initiation for Atom Agent (userId: ${userId}):`, error);
    res.status(500).json({ error: 'Failed to initiate Microsoft Graph authentication for Atom Agent.' });
  }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
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
  return await initiateMicrosoftAuth(req, res);
}
