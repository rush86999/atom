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
        const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';
        const response = await fetch(`${backendUrl}/api/slack/callback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Include auth cookie for backend authentication
                // @ts-ignore - cookie header is allowed in server-side requests
                'cookie': req.headers.cookie || ''
            },
            body: JSON.stringify({
                code,
                state: state.toString()
            })
        });

        if (response.ok) {
            return res.redirect('/integrations?success=true&provider=slack');
        } else {
            const errorText = await response.text();
            console.error('Token exchange failed:', errorText);
            return res.redirect(`/integrations?error=token_exchange_failed&detail=${encodeURIComponent(errorText.substring(0, 100))}`);
        }
    } catch (err) {
        console.error('OAuth callback error:', err);
        return res.redirect('/integrations?error=callback_exception');
    }
}
