import type { NextApiRequest, NextApiResponse } from 'next';
import { google } from 'googleapis';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET, // CLIENT_SECRET is needed for OAuth2 client instantiation
  ATOM_GOOGLE_CALENDAR_REDIRECT_URI,
  GOOGLE_CALENDAR_API_SCOPE,
} from '../../../../../../project/functions/atom-agent/_libs/constants'; // Adjusted path
import crypto from 'crypto';

// Placeholder for actual user ID retrieval
async function getUserIdFromRequest(req: NextApiRequest): Promise<string | null> {
  // TODO: Implement real user ID retrieval from session/token (e.g., SuperTokens, NextAuth.js)
  console.log('TODO: Implement actual user ID retrieval in getUserIdFromRequest');
  return "mock_user_id_from_initiate"; // Replace with actual user ID logic
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  try {
    const userId = await getUserIdFromRequest(req);
    if (!userId) {
      return res.status(401).json({ error: 'User not authenticated' });
    }

    if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET || !ATOM_GOOGLE_CALENDAR_REDIRECT_URI) {
      console.error('Google Calendar OAuth environment variables not set for Atom Agent.');
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
    console.error('Error during Google Calendar OAuth initiation for Atom Agent:', error);
    res.status(500).json({ error: 'Failed to initiate Google Calendar authentication for Atom Agent.' });
  }
}
