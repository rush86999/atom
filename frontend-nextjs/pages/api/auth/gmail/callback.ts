import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    const { code, error } = req.query;

    if (error) {
        return res.redirect(`/integrations?error=${error}`);
    }

    if (!code) {
        return res.redirect('/integrations?error=no_code');
    }

    try {
        // Exchange code for tokens via backend
        const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';
        const response = await fetch(`${backendUrl}/api/auth/google/callback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code,
                redirect_uri: 'http://localhost:3000/api/auth/gmail/callback'
            })
        });

        if (response.ok) {
            const data = await response.json();
            // In a real app, you might store tokens in a session or cookie here
            // For now, the backend handles storage/logging
            return res.redirect('/integrations?success=true&provider=google');
        } else {
            console.error('Token exchange failed:', await response.text());
            return res.redirect('/integrations?error=token_exchange_failed');
        }
    } catch (err) {
        console.error('OAuth callback error:', err);
        return res.redirect('/integrations?error=callback_exception');
    }
}
