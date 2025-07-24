import { NextApiRequest, NextApiResponse } from 'next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
    const zoomClientId = process.env.ZOOM_CLIENT_ID;
    const redirectUri = process.env.ZOOM_REDIRECT_URI;
    const state = 'some-random-state'; // Should be a random, unguessable string

    if (!zoomClientId || !redirectUri) {
        return res.status(500).json({ message: 'Zoom environment variables not configured.' });
    }

    const authorizationUrl = `https://zoom.us/oauth/authorize?response_type=code&client_id=${zoomClientId}&redirect_uri=${redirectUri}&state=${state}`;
    
    res.redirect(authorizationUrl);
}
