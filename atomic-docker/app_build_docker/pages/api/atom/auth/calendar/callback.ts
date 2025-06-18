import type { NextApiRequest, NextApiResponse } from 'next';
import { google } from 'googleapis';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
  ATOM_GOOGLE_CALENDAR_REDIRECT_URI,
  // GOOGLE_TOKEN_URL is implicitly used by oauth2Client.getToken()
} from '../../../../../../project/functions/atom-agent/_libs/constants'; // Adjusted path
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';

// Define an interface for storing tokens (conceptual)
export interface UserGoogleCalendarTokens {
  userId: string;
  accessToken: string;
  refreshToken?: string; // Refresh tokens are not always returned on every auth flow
  expiryDate: number; // Store as a timestamp (Date.now() + expires_in * 1000)
  scope: string;
  tokenType: string;
}

import { saveAtomGoogleCalendarTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils'; // Adjusted path


// Placeholder for state verification
async function verifyState(req: NextApiRequest, receivedState: string): Promise<boolean> {
  // TODO: Retrieve the state stored in the user's session during the initiate step
  // and compare it with receivedState.
  console.log(`TODO: Implement state verification. Received state: ${receivedState}. Stored state should be retrieved from session.`);
  // For now, always return true for mock purposes. In production, this must be a real check.
  return true;
}

export default async function handler(
async function handleGoogleCalendarCallback(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    const { code, state, error: googleError } = req.query;

    if (googleError) {
      console.error(`Error from Google OAuth callback for Atom Agent (userId: ${userId}):`, googleError);
      return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(googleError as string)}&atom_agent=true`);
    }

    const isStateValid = await verifyState(req, state as string); // verifyState still uses placeholder logic
    if (!isStateValid) {
      console.error(`Invalid OAuth state parameter for Atom Agent (userId: ${userId}).`);
      return res.redirect('/Settings/UserViewSettings?calendar_auth_error=invalid_state&atom_agent=true');
    }

    if (!code) {
      console.error(`No authorization code received from Google for Atom Agent (userId: ${userId}).`);
      return res.redirect('/Settings/UserViewSettings?calendar_auth_error=no_code&atom_agent=true');
    }

    if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET || !ATOM_GOOGLE_CALENDAR_REDIRECT_URI) {
      console.error(`Google Calendar OAuth environment variables not set for Atom Agent (callback, userId: ${userId}).`);
      return res.status(500).json({ error: 'OAuth configuration error for Atom Agent (callback).' });
    }

    const oauth2Client = new google.auth.OAuth2(
      ATOM_GOOGLE_CALENDAR_CLIENT_ID,
      ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
      ATOM_GOOGLE_CALENDAR_REDIRECT_URI
    );

    const { tokens } = await oauth2Client.getToken(code as string);
    console.log(`Received tokens from Google for Atom Agent (userId: ${userId}):`, tokens);

    let userGoogleEmail: string | null | undefined = null;
    if (tokens.access_token) {
        // No need to set credentials again if getToken worked, it often configures the client instance.
        // However, explicitly setting ensures it for the next specific API call.
        oauth2Client.setCredentials(tokens);
        try {
            const oauth2 = google.oauth2({ version: 'v2', auth: oauth2Client });
            const userInfoResponse = await oauth2.userinfo.get();
            userGoogleEmail = userInfoResponse.data.email;
            console.log(`Fetched user's Google email for Atom Agent (userId: ${userId}): ${userGoogleEmail}`);
        } catch (error) {
            console.error(`Error fetching Google user info for Atom Agent (userId: ${userId}):`, error);
            // Decide if this error is critical. For now, we'll proceed without email if it fails.
        }
    }

    if (tokens.access_token && tokens.expiry_date) { // Scope and token_type are good to have but access_token and expiry are crucial
      // No need to define userTokens separately if directly passing to saveAtomGoogleCalendarTokens
      await saveAtomGoogleCalendarTokens(userId, {
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token || null,
        expiry_date: tokens.expiry_date,
        scope: tokens.scope || null,
        token_type: tokens.token_type || null,
      }, userGoogleEmail); // Pass the fetched email
      console.log(`Atom Google Calendar tokens (and potentially email: ${userGoogleEmail}) stored for userId: ${userId}`);
    } else {
        console.error(`Essential token information (access_token or expiry_date) missing from Google's response for Atom Agent (userId: ${userId})`, tokens);
        return res.redirect('/Settings/UserViewSettings?calendar_auth_error=token_missing_info&atom_agent=true');
    }

    // Redirect to a success page (e.g., settings page)
    console.log('Successfully processed Google Calendar OAuth callback for Atom Agent.');
    res.redirect('/Settings/UserViewSettings?calendar_auth_success=true&atom_agent=true');

  } catch (error: any) {
    console.error(`Error in Google Calendar OAuth callback for Atom Agent (userId: ${userId}):`, error.message);
    let errorQueryParam = 'callback_failed';
    if (error.message.includes('Failed to save tokens') || error.message.includes('Invalid token data')) {
        errorQueryParam = 'token_storage_failed';
    } else if (error.response?.data?.error_description) { // Use optional chaining
        errorQueryParam = encodeURIComponent(error.response.data.error_description);
    } else if (error.response?.data?.error) { // Fallback to error if error_description is not available
        errorQueryParam = encodeURIComponent(error.response.data.error);
    }
    res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${errorQueryParam}&atom_agent=true`);
  }
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  await superTokensNextWrapper(
    async (next) => {
      // User needs to be authenticated to hit this callback with a code
      return await verifySession()(req, res, next);
    },
    req,
    res
  );
  if (res.writableEnded) {
      return;
  }
  return await handleGoogleCalendarCallback(req, res);
}
