import { Request, Response } from 'express';
import { createAdminGraphQLClient } from '../_utils/dbService';
import { encrypt, decrypt } from '../_utils/crypto';
import { WebClient } from '@slack/web-api';
import { google } from 'googleapis';
import msal from '@azure/msal-node';

// --- Environment Variables ---
const SLACK_CLIENT_ID = process.env.SLACK_CLIENT_ID;
const SLACK_CLIENT_SECRET = process.env.SLACK_CLIENT_SECRET;
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID_GMAIL;
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET_GMAIL;
const MSGRAPH_CLIENT_ID = process.env.MSGRAPH_DELEGATED_CLIENT_ID;
const MSGRAPH_CLIENT_SECRET = process.env.MSGRAPH_DELEGATED_CLIENT_SECRET;
const MSGRAPH_AUTHORITY = process.env.MSGRAPH_DELEGATED_AUTHORITY;
const TOKEN_ENCRYPTION_KEY = process.env.TOKEN_ENCRYPTION_KEY;

// --- Database Queries ---
const GET_TOKEN_QUERY = `...`; // As defined before
const UPSERT_TOKEN_MUTATION = `...`; // As defined before


// --- Service Logic ---

async function getMicrosoftGraphAccessToken(userId: string): Promise<string | null> {
    const adminClient = createAdminGraphQLClient();
    const response = await adminClient.request(GET_TOKEN_QUERY, { userId, service: 'msteams' }); // or a generic 'microsoft' service name
    const tokenInfo = response.user_tokens[0];

    if (!tokenInfo) return null;

    const expiry = new Date(tokenInfo.token_expiry_timestamp).getTime();
    if (Date.now() >= expiry - 5 * 60 * 1000) { // Refresh if within 5 mins of expiry
        const refreshToken = decrypt(tokenInfo.encrypted_refresh_token, TOKEN_ENCRYPTION_KEY);

        const msalApp = new msal.ConfidentialClientApplication({
            auth: {
                clientId: MSGRAPH_CLIENT_ID!,
                authority: MSGRAPH_AUTHORITY!,
                clientSecret: MSGRAPH_CLIENT_SECRET!,
            }
        });

        const result = await msalApp.acquireTokenByRefreshToken({
            refreshToken,
            scopes: process.env.MSGRAPH_DELEGATED_SCOPES!.split(' '),
        });

        if (result) {
            const encryptedAccessToken = encrypt(result.accessToken, TOKEN_ENCRYPTION_KEY);
            const encryptedRefreshToken = result.refreshToken ? encrypt(result.refreshToken, TOKEN_ENCRYPTION_KEY) : tokenInfo.encrypted_refresh_token;

            await adminClient.request(UPSERT_TOKEN_MUTATION, {
                userId,
                service: 'msteams',
                accessToken: encryptedAccessToken,
                refreshToken: encryptedRefreshToken,
                expiry: result.expiresOn,
                metadata: tokenInfo.metadata
            });
            return result.accessToken;
        }
    }

    return decrypt(tokenInfo.encrypted_access_token, TOKEN_ENCRYPTION_KEY);
}

// ... (getSlackAccessToken function as before) ...


// --- Express Handlers ---

export const handleMicrosoftGraphAuthCallback = async (req: Request, res: Response) => {
    const { code, state } = req.query;
    const userId = state as string;

    const msalApp = new msal.ConfidentialClientApplication({ ... }); // MSAL config
    const tokenResponse = await msalApp.acquireTokenByCode({
        code: code as string,
        scopes: process.env.MSGRAPH_DELEGATED_SCOPES!.split(' '),
        redirectUri: process.env.MSGRAPH_DELEGATED_REDIRECT_URL!,
    });

    if (tokenResponse) {
        const { accessToken, refreshToken, expiresOn, account } = tokenResponse;
        const encryptedAccessToken = encrypt(accessToken, TOKEN_ENCRYPTION_KEY);
        const encryptedRefreshToken = encrypt(refreshToken!, TOKEN_ENCRYPTION_KEY);

        await createAdminGraphQLClient().request(UPSERT_TOKEN_MUTATION, {
            userId,
            service: 'msteams',
            accessToken: encryptedAccessToken,
            refreshToken: encryptedRefreshToken,
            expiry: expiresOn,
            metadata: { account_json: JSON.stringify(account) }
        });
    }

    res.send("Microsoft authentication successful!");
};

// ... (handleSlackAuthCallback function as before) ...

export const getTokenForService = async (req: Request, res: Response) => {
    const { userId, service } = req.params;
    let token = null;

    if (service === 'slack') {
        token = await getSlackAccessToken(userId);
    } else if (service === 'msteams' || service === 'outlook') {
        token = await getMicrosoftGraphAccessToken(userId);
    } // Add other services here

    if (token) {
        res.json({ access_token: token });
    } else {
        res.status(404).send(`${service} token not found for user.`);
    }
};
