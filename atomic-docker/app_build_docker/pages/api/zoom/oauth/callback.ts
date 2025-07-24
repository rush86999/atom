import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';
import { executeGraphQLQuery } from '../../../../../project/functions/_libs/graphqlClient';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    let session: SessionContainer;
    try {
        session = await getSession(req, res, { overrideGlobalClaimValidators: () => [] });
    } catch (err) {
        return res.status(401).json({ message: 'Unauthorized' });
    }

    const userId = session.getUserId();
    const { code, state } = req.query;

    // In a real app, you should validate the 'state' parameter here

    const zoomClientId = process.env.ZOOM_CLIENT_ID;
    const zoomClientSecret = process.env.ZOOM_CLIENT_SECRET;
    const redirectUri = process.env.ZOOM_REDIRECT_URI;

    if (!zoomClientId || !zoomClientSecret || !redirectUri) {
        return res.status(500).json({ message: 'Zoom environment variables not configured.' });
    }

    try {
        const response = await fetch('https://zoom.us/oauth/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': `Basic ${Buffer.from(`${zoomClientId}:${zoomClientSecret}`).toString('base64')}`,
            },
            body: new URLSearchParams({
                grant_type: 'authorization_code',
                code: code as string,
                redirect_uri: redirectUri,
            }),
        });

        const data = await response.json();

        if (response.ok) {
            const accessToken = data.access_token;
            const refreshToken = data.refresh_token;
            
            // Save the tokens to the user_tokens table
            const mutation = `
                mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!, $refreshToken: String) {
                    insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken, refresh_token: $refreshToken}) {
                        id
                    }
                }
            `;
            const variables = {
                userId,
                service: 'zoom',
                accessToken,
                refreshToken,
            };
            await executeGraphQLQuery(mutation, variables, 'InsertUserToken', userId);

            return res.redirect('/Settings/UserViewSettings');
        } else {
            return res.status(500).json({ message: `Zoom OAuth error: ${data.reason}` });
        }
    } catch (error) {
        console.error('Error during Zoom OAuth callback:', error);
        return res.status(500).json({ message: 'Failed to complete Zoom OAuth flow' });
    }
}
