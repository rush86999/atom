import type { NextApiRequest, NextApiResponse } from 'next';
import { google } from 'googleapis';
import {
  ATOM_GMAIL_CLIENT_ID,
  ATOM_GMAIL_CLIENT_SECRET,
  ATOM_GMAIL_REDIRECT_URI,
} from '../../../../../../project/functions/atom-agent/_libs/constants';
import { saveAtomGmailTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils'; // To be created
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';

// Placeholder for state verification (should be shared or a common utility if more complex)
async function verifyState(req: NextApiRequest, receivedState: string): Promise<boolean> {
  console.log(`TODO: Implement state verification for Gmail. Received state: ${receivedState}.`);
  return true; // Mocked
}

async function handleGmailCallback(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    const { code, state, error: googleError } = req.query;

    if (googleError) {
      console.error(`Error from Google OAuth callback for Atom Agent Gmail (userId: ${userId}):`, googleError);
      return res.redirect(`/Settings/UserViewSettings?email_auth_error=${encodeURIComponent(googleError as string)}&atom_agent_email=true`);
    }

    const isStateValid = await verifyState(req, state as string);
    if (!isStateValid) {
      console.error(`Invalid OAuth state parameter for Atom Agent Gmail (userId: ${userId}).`);
      return res.redirect('/Settings/UserViewSettings?email_auth_error=invalid_state&atom_agent_email=true');
    }

    if (!code) {
      console.error(`No authorization code received from Google for Atom Agent Gmail (userId: ${userId}).`);
      return res.redirect('/Settings/UserViewSettings?email_auth_error=no_code&atom_agent_email=true');
    }

    if (!ATOM_GMAIL_CLIENT_ID || !ATOM_GMAIL_CLIENT_SECRET || !ATOM_GMAIL_REDIRECT_URI) {
      console.error(`Gmail OAuth environment variables not set for Atom Agent (callback, userId: ${userId}).`);
      return res.status(500).json({ error: 'OAuth configuration error for Atom Agent Gmail (callback).' });
    }

    const oauth2Client = new google.auth.OAuth2(
      ATOM_GMAIL_CLIENT_ID,
      ATOM_GMAIL_CLIENT_SECRET,
      ATOM_GMAIL_REDIRECT_URI
    );

    const { tokens } = await oauth2Client.getToken(code as string);
    console.log(`Received tokens from Google for Atom Agent Gmail (userId: ${userId}):`, tokens);

    let userGoogleEmail: string | null | undefined = null;
    if (tokens.access_token) {
        oauth2Client.setCredentials(tokens);
        try {
            const oauth2 = google.oauth2({ version: 'v2', auth: oauth2Client });
            const userInfoResponse = await oauth2.userinfo.get();
            userGoogleEmail = userInfoResponse.data.email;
            console.log(`Fetched user's Google email for Atom Agent Gmail (userId: ${userId}): ${userGoogleEmail}`);
        } catch (error) {
            console.error(`Error fetching Google user info for Atom Agent Gmail (userId: ${userId}):`, error);
        }
    }

    if (tokens.access_token && tokens.expiry_date) {
      await saveAtomGmailTokens(userId, { // This function needs to be created in token-utils
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token || null,
        expiry_date: tokens.expiry_date,
        scope: tokens.scope || null,
        token_type: tokens.token_type || null,
      }, userGoogleEmail);
      console.log(`Atom Gmail tokens (and email: ${userGoogleEmail}) stored for userId: ${userId}`);
    } else {
        console.error(`Essential token information missing from Google's response for Atom Agent Gmail (userId: ${userId})`, tokens);
        return res.redirect('/Settings/UserViewSettings?email_auth_error=token_missing_info&atom_agent_email=true');
    }

    console.log('Successfully processed Google Gmail OAuth callback for Atom Agent.');
    res.redirect('/Settings/UserViewSettings?email_auth_success=true&atom_agent_email=true');

  } catch (error: any) {
    console.error(`Error in Google Gmail OAuth callback for Atom Agent (userId: ${userId}):`, error.message);
    let errorQueryParam = 'callback_failed';
    if (error.message.includes('Failed to save tokens') || error.message.includes('Invalid token data')) {
        errorQueryParam = 'token_storage_failed';
    } else if (error.response?.data?.error_description) {
        errorQueryParam = encodeURIComponent(error.response.data.error_description);
    } else if (error.response?.data?.error) {
        errorQueryParam = encodeURIComponent(error.response.data.error);
    }
    res.redirect(`/Settings/UserViewSettings?email_auth_error=${errorQueryParam}&atom_agent_email=true`);
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
  return await handleGmailCallback(req, res);
}
