import type { NextApiRequest, NextApiResponse } from 'next';
import got from 'got';
import {
  ATOM_MSGRAPH_CLIENT_ID,
  ATOM_MSGRAPH_CLIENT_SECRET,
  ATOM_MSGRAPH_REDIRECT_URI,
  ATOM_MSGRAPH_TENANT_ID,
  MSGRAPH_OAUTH_AUTHORITY_BASE,
  MSGRAPH_API_SCOPES, // Used for token request as well
} from '../../../../../../project/functions/atom-agent/_libs/constants';
import { saveAtomMicrosoftGraphTokens } from '../../../../../../project/functions/atom-agent/_libs/token-utils'; // To be created
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';

// Placeholder for state verification
async function verifyState(req: NextApiRequest, receivedState: string): Promise<boolean> {
  console.log(`TODO: Implement state verification for Microsoft Graph. Received state: ${receivedState}.`);
  return true; // Mocked
}

async function handleMicrosoftCallback(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = (req as any).session as Session.SessionContainer;
  const userId = session.getUserId();

  try {
    const { code, state, error: msError, error_description: msErrorDescription } = req.query;

    if (msError) {
      console.error(`Error from Microsoft OAuth callback for Atom Agent (userId: ${userId}): ${msError} - ${msErrorDescription}`);
      return res.redirect(`/Settings/UserViewSettings?mgraph_auth_error=${encodeURIComponent(msError as string)}&mgraph_error_desc=${encodeURIComponent(msErrorDescription as string || '')}&atom_agent_mgraph=true`);
    }

    const isStateValid = await verifyState(req, state as string);
    if (!isStateValid) {
      console.error(`Invalid OAuth state parameter for Atom Agent Microsoft Graph (userId: ${userId}).`);
      return res.redirect('/Settings/UserViewSettings?mgraph_auth_error=invalid_state&atom_agent_mgraph=true');
    }

    if (!code) {
      console.error(`No authorization code received from Microsoft for Atom Agent (userId: ${userId}).`);
      return res.redirect('/Settings/UserViewSettings?mgraph_auth_error=no_code&atom_agent_mgraph=true');
    }

    if (!ATOM_MSGRAPH_CLIENT_ID || !ATOM_MSGRAPH_CLIENT_SECRET || !ATOM_MSGRAPH_REDIRECT_URI || !ATOM_MSGRAPH_TENANT_ID) {
      console.error(`Microsoft Graph OAuth environment variables not set for Atom Agent (callback, userId: ${userId}).`);
      return res.status(500).json({ error: 'OAuth configuration error for Atom Agent Microsoft Graph (callback).' });
    }

    const tokenEndpoint = `${MSGRAPH_OAUTH_AUTHORITY_BASE}${ATOM_MSGRAPH_TENANT_ID}/oauth2/v2.0/token`;

    const tokenResponse = await got.post(tokenEndpoint, {
        form: {
            client_id: ATOM_MSGRAPH_CLIENT_ID,
            scope: MSGRAPH_API_SCOPES.join(' '),
            code: code as string,
            redirect_uri: ATOM_MSGRAPH_REDIRECT_URI,
            grant_type: 'authorization_code',
            client_secret: ATOM_MSGRAPH_CLIENT_SECRET,
        },
        responseType: 'json'
    });

    const tokens: any = tokenResponse.body; // Type properly based on Microsoft's token response
    console.log(`Received tokens from Microsoft Graph for Atom Agent (userId: ${userId}):`, {token_type: tokens.token_type, scope: tokens.scope, expires_in: tokens.expires_in});


    let userMicrosoftEmail: string | null | undefined = null;
    if (tokens.access_token) {
        try {
            const graphResponse: any = await got.get('https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName', {
                headers: {
                    'Authorization': `Bearer ${tokens.access_token}`
                },
                responseType: 'json'
            });
            userMicrosoftEmail = graphResponse.body.mail || graphResponse.body.userPrincipalName;
            console.log(`Fetched user's Microsoft Graph email for Atom Agent (userId: ${userId}): ${userMicrosoftEmail}`);
        } catch (err: any) {
            console.error(`Error fetching Microsoft Graph user info for Atom Agent (userId: ${userId}):`, err.message);
            if (err.response?.body) console.error("MS Graph userinfo error response:", err.response.body);
        }
    }

    if (tokens.access_token && tokens.expires_in) {
      const expiryDate = Date.now() + (Number(tokens.expires_in) * 1000);
      await saveAtomMicrosoftGraphTokens(userId, { // This function needs to be created in token-utils
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token || null,
        expiry_date: expiryDate,
        scope: tokens.scope || null, // Scope might be returned differently or be a fixed value based on request
        token_type: tokens.token_type || 'Bearer',
      }, userMicrosoftEmail);
      console.log(`Atom Microsoft Graph tokens (and email: ${userMicrosoftEmail}) stored for userId: ${userId}`);
    } else {
        console.error(`Essential token information missing from Microsoft's response for Atom Agent (userId: ${userId})`, tokens);
        return res.redirect('/Settings/UserViewSettings?mgraph_auth_error=token_missing_info&atom_agent_mgraph=true');
    }

    console.log('Successfully processed Microsoft Graph OAuth callback for Atom Agent.');
    res.redirect('/Settings/UserViewSettings?mgraph_auth_success=true&atom_agent_mgraph=true');

  } catch (error: any) {
    console.error(`Error in Microsoft Graph OAuth callback for Atom Agent (userId: ${userId}):`, error.message);
    let errorQueryParam = 'mgraph_callback_failed';
     if (error.response?.body) { // got error
        const bodyError = error.response.body as any;
        errorQueryParam = encodeURIComponent(bodyError.error_description || bodyError.error || 'mgraph_token_exchange_error');
    } else if (error.message.includes('Failed to save tokens')) {
        errorQueryParam = 'token_storage_failed';
    }
    res.redirect(`/Settings/UserViewSettings?mgraph_auth_error=${errorQueryParam}&atom_agent_mgraph=true`);
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
  return await handleMicrosoftCallback(req, res);
}
