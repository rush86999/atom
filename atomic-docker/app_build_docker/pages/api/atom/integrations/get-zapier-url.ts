import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';
import { executeGraphQLQuery } from '../../../../project/functions/_libs/graphqlClient';

async function getZapierUrl(userId: string): Promise<string | null> {
    const query = `
        query GetUserSetting($userId: String!, $key: String!) {
            user_settings(where: {user_id: {_eq: $userId}, key: {_eq: $key}}) {
                value
            }
        }
    `;
    const variables = {
        userId,
        key: 'zapier_webhook_url',
    };
    const response = await executeGraphQLQuery<{ user_settings: { value: string }[] }>(query, variables, 'GetUserSetting', userId);
    if (response.user_settings && response.user_settings.length > 0) {
        return response.user_settings[0].value;
    }
    return null;
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    let session: SessionContainer;
    try {
        session = await getSession(req, res, { overrideGlobalClaimValidators: () => [] });
    } catch (err) {
        return res.status(401).json({ message: 'Unauthorized' });
    }

    const userId = session.getUserId();

    if (req.method === 'GET') {
        try {
            const url = await getZapierUrl(userId);
            return res.status(200).json({ url });
        } catch (error) {
            console.error('Error fetching Zapier URL:', error);
            return res.status(500).json({ message: 'Failed to fetch Zapier URL' });
        }
    } else {
        res.setHeader('Allow', ['GET']);
        res.status(405).end(`Method ${req.method} Not Allowed`);
    }
}
