import type { NextApiRequest, NextApiResponse } from 'next';
import { google } from 'googleapis';
import {
  ATOM_GMAIL_CLIENT_ID,
  ATOM_GMAIL_CLIENT_SECRET, // CLIENT_SECRET is needed for OAuth2 client instantiation
  ATOM_GMAIL_REDIRECT_URI,
  GMAIL_API_SCOPES,
} from '../../../../../../project/functions/atom-agent/_libs/constants';
import crypto from 'crypto';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';

// Assuming supertokens.init is called globally

async function initiateGmailAuth(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    if (!ATOM_GMAIL_CLIENT_ID || !ATOM_GMAIL_CLIENT_SECRET || !ATOM_GMAIL_REDIRECT_URI) {
      console.error('Gmail OAuth environment variables not set for Atom Agent for userId:', userId);
      return res.status(500).json({ error: 'OAuth configuration error for Atom Agent Gmail.' });
    }

    const oauth2Client = new google.auth.OAuth2(
      ATOM_GMAIL_CLIENT_ID,
      ATOM_GMAIL_CLIENT_SECRET,
      ATOM_GMAIL_REDIRECT_URI
    );

    const state = crypto.randomBytes(16).toString('hex');
    // TODO: Store this 'state' in the user's session to verify it in the callback for Gmail

    const authUrl = oauth2Client.generateAuthUrl({
      access_type: 'offline', // To get a refresh token
      scope: GMAIL_API_SCOPES,
      state: state,
      // prompt: 'consent', // Optional: forces consent screen every time
    });

    console.log(`Generated Gmail OAuth URL for Atom Agent (user: ${userId}): ${authUrl}`);
    res.redirect(authUrl);

  } catch (error: any) {
    console.error(`Error during Gmail OAuth initiation for Atom Agent (userId: ${userId}):`, error);
    res.status(500).json({ error: 'Failed to initiate Gmail authentication for Atom Agent.' });
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
  return await initiateGmailAuth(req, res);
}
