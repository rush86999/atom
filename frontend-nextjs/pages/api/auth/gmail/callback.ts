import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    const { code, state, error } = req.query;

    if (error) {
        return res.redirect(`/integrations?error=${error}`);
    }

    if (!code) {
        return res.redirect('/integrations?error=no_code');
    }

    // State parameter is required for CSRF protection
    if (!state || typeof state !== 'string') {
        return res.redirect('/integrations?error=no_state');
    }

    try {
        // Exchange code for tokens via backend
        const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';
        const response = await fetch(`${backendUrl}/api/gmail/callback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Include auth cookie for backend authentication
                // @ts-ignore - cookie header is allowed in server-side requests
                'cookie': req.headers.cookie || ''
            },
            body: JSON.stringify({
                code,
                state: state.toString(),
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
