import type { NextApiRequest, NextApiResponse } from 'next';
import { google } from 'googleapis';
import {
  ATOM_GOOGLE_CALENDAR_CLIENT_ID,
  ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
  ATOM_GOOGLE_CALENDAR_REDIRECT_URI,
  // GOOGLE_TOKEN_URL is implicitly used by oauth2Client.getToken()
} from '../../../../../../project/functions/atom-agent/_libs/constants'; // Adjusted path

// Define an interface for storing tokens (conceptual)
export interface UserGoogleCalendarTokens {
  userId: string;
  accessToken: string;
  refreshToken?: string; // Refresh tokens are not always returned on every auth flow
  expiryDate: number; // Store as a timestamp (Date.now() + expires_in * 1000)
  scope: string;
  tokenType: string;
}

// Placeholder for actual user ID retrieval
async function getUserIdFromRequest(req: NextApiRequest): Promise<string | null> {
  // TODO: Implement real user ID retrieval from session/token (e.g., SuperTokens, NextAuth.js)
  console.log('TODO: Implement actual user ID retrieval in getUserIdFromRequest (callback)');
  return "mock_user_id_from_callback"; // Replace with actual user ID logic
}

// Placeholder for state verification
async function verifyState(req: NextApiRequest, receivedState: string): Promise<boolean> {
  // TODO: Retrieve the state stored in the user's session during the initiate step
  // and compare it with receivedState.
  console.log(`TODO: Implement state verification. Received state: ${receivedState}. Stored state should be retrieved from session.`);
  // For now, always return true for mock purposes. In production, this must be a real check.
  return true;
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
    const { code, state, error: googleError } = req.query;

    if (googleError) {
      console.error('Error from Google OAuth callback for Atom Agent:', googleError);
      // Redirect to settings page with an error
      return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(googleError as string)}`);
    }

    // Verify the state parameter for CSRF protection
    const isStateValid = await verifyState(req, state as string);
    if (!isStateValid) {
      console.error('Invalid OAuth state parameter for Atom Agent.');
      return res.redirect('/Settings/UserViewSettings?calendar_auth_error=invalid_state');
    }

    if (!code) {
      console.error('No authorization code received from Google for Atom Agent.');
      return res.redirect('/Settings/UserViewSettings?calendar_auth_error=no_code');
    }

    if (!ATOM_GOOGLE_CALENDAR_CLIENT_ID || !ATOM_GOOGLE_CALENDAR_CLIENT_SECRET || !ATOM_GOOGLE_CALENDAR_REDIRECT_URI) {
      console.error('Google Calendar OAuth environment variables not set for Atom Agent (callback).');
      return res.status(500).json({ error: 'OAuth configuration error for Atom Agent (callback).' });
    }

    const oauth2Client = new google.auth.OAuth2(
      ATOM_GOOGLE_CALENDAR_CLIENT_ID,
      ATOM_GOOGLE_CALENDAR_CLIENT_SECRET,
      ATOM_GOOGLE_CALENDAR_REDIRECT_URI
    );

    const { tokens } = await oauth2Client.getToken(code as string);
    console.log('Received tokens from Google for Atom Agent:', tokens);

    const userId = await getUserIdFromRequest(req);
    if (!userId) {
      // This case should ideally be handled before this point by session middleware,
      // but as a safeguard:
      console.error('User not authenticated during OAuth callback for Atom Agent.');
      return res.redirect('/User/Login/UserLogin?error=unauthenticated_oauth_callback');
    }

    if (tokens.access_token && tokens.expiry_date && tokens.scope && tokens.token_type) {
      const userTokens: UserGoogleCalendarTokens = {
        userId: userId,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token || undefined, // refresh_token is not always sent
        expiryDate: tokens.expiry_date,
        scope: tokens.scope,
        tokenType: tokens.token_type
      };

      // TODO: Securely store these tokens for the user.
      // This could be in a database, associated with the userId.
      // Ensure refreshToken is stored very securely.
      console.log(`TODO: Securely store these tokens for Atom Agent (userId: ${userId}):`, JSON.stringify(userTokens));

      // For example, you might call a service here:
      // await saveUserGoogleTokens(userId, userTokens);

    } else {
        console.error("Essential token information missing from Google's response for Atom Agent", tokens);
        return res.redirect('/Settings/UserViewSettings?calendar_auth_error=token_missing_info');
    }

    // Redirect to a success page (e.g., settings page)
    console.log('Successfully processed Google Calendar OAuth callback for Atom Agent.');
    res.redirect('/Settings/UserViewSettings?calendar_auth_success=true&atom_agent=true');

  } catch (error: any) {
    console.error('Error in Google Calendar OAuth callback for Atom Agent:', error);
    // Check if the error is from getToken (e.g., invalid code)
    if (error.response && error.response.data) {
        console.error('Google API error details:', error.response.data);
        return res.redirect(`/Settings/UserViewSettings?calendar_auth_error=${encodeURIComponent(error.response.data.error_description || 'google_api_error')}`);
    }
    res.redirect('/Settings/UserViewSettings?calendar_auth_error=callback_failed');
  }
}
