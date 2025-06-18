import type { NextApiRequest, NextApiResponse } from 'next';
import { google } from 'googleapis';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
  ATOM_GOOGLE_CALENDAR_REDIRECT_URI,
  GOOGLE_CALENDAR_API_SCOPE,
} from '../../../../../../project/functions/atom-agent/_libs/constants'; // Adjusted path
import crypto from 'crypto';
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';

// Assuming supertokens.init is called globally, e.g., in pages/api/auth/[[...path]].ts

async function initiateGoogleCalendarAuth(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  // Session verification will handle sending 401 if not authenticated
  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET || !ATOM_GOOGLE_CALENDAR_REDIRECT_URI) {
      console.error('Google Calendar OAuth environment variables not set for Atom Agent for userId:', userId);
      return res.status(500).json({ error: 'OAuth configuration error for Atom Agent.' });
    }

    const oauth2Client = new google.auth.OAuth2(
      ATOM_GOOGLE_CALENDAR_CLIENT_ID,
      ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
      ATOM_GOOGLE_CALENDAR_REDIRECT_URI
    );

    // Generate a random string for CSRF protection
    const state = crypto.randomBytes(16).toString('hex');
    // TODO: Store this 'state' in the user's session to verify it in the callback

    const authUrl = oauth2Client.generateAuthUrl({
      access_type: 'offline', // To get a refresh token
      scope: GOOGLE_CALENDAR_API_SCOPE,
      state: state, // CSRF protection
      // prompt: 'consent', // Optional: forces consent screen every time, useful for dev/testing to ensure refresh token
    });

    console.log(`Generated Google Calendar OAuth URL for Atom Agent (user: ${userId}): ${authUrl}`);
    res.redirect(authUrl);

  } catch (error: any) {
    console.error(`Error during Google Calendar OAuth initiation for Atom Agent (userId: ${userId}):`, error);
    res.status(500).json({ error: 'Failed to initiate Google Calendar authentication for Atom Agent.' });
  }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  await superTokensNextWrapper(
    async (next) => {
      // We want to authenticate the user before allowing them to initiate OAuth
      return await verifySession()(req, res, next);
    },
    req,
    res
  );
  // If verifySession above threw an error or ended the response, this part won't run.
  if (res.writableEnded) {
      return;
  }
  // If session is verified, proceed with the main logic
  return await initiateGoogleCalendarAuth(req, res);
}
