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

    const slackClientId = process.env.SLACK_CLIENT_ID;
    const slackClientSecret = process.env.SLACK_CLIENT_SECRET;
    const redirectUri = process.env.SLACK_REDIRECT_URI;

    if (!slackClientId || !slackClientSecret || !redirectUri) {
        return res.status(500).json({ message: 'Slack environment variables not configured.' });
    }

    try {
        const response = await fetch('https://slack.com/api/oauth.v2.access', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                client_id: slackClientId,
                client_secret: slackClientSecret,
                code: code as string,
                redirect_uri: redirectUri,
            }),
        });

        const data = await response.json();

        if (data.ok) {
            const accessToken = data.authed_user.access_token;
            
            // Save the token to the user_tokens table
            const mutation = `
                mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!) {
                    insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken}) {
                        id
                    }
                }
            `;
            const variables = {
                userId,
                service: 'slack',
                accessToken,
            };
            await executeGraphQLQuery(mutation, variables, 'InsertUserToken', userId);

            return res.redirect('/Settings/UserViewSettings');
        } else {
            return res.status(500).json({ message: `Slack OAuth error: ${data.error}` });
        }
    } catch (error) {
        console.error('Error during Slack OAuth callback:', error);
        return res.status(500).json({ message: 'Failed to complete Slack OAuth flow' });
    }
}
