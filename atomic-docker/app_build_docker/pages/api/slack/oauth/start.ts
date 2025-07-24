import { NextApiRequest, NextApiResponse } from 'next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
    const slackClientId = process.env.SLACK_CLIENT_ID;
    const redirectUri = process.env.SLACK_REDIRECT_URI;
    const scope = 'chat:write,commands,users:read,users:read.email';
    const state = 'some-random-state'; // Should be a random, unguessable string

    if (!slackClientId || !redirectUri) {
        return res.status(500).json({ message: 'Slack environment variables not configured.' });
    }

    const authorizationUrl = `https://slack.com/oauth/v2/authorize?client_id=${slackClientId}&scope=${scope}&redirect_uri=${redirectUri}&state=${state}`;
    
    res.redirect(authorizationUrl);
}
