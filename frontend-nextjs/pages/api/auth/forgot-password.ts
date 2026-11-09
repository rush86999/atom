import { NextApiRequest, NextApiResponse } from 'next';

const API_BASE_URL = process.env.PYTHON_API_SERVICE_BASE_URL ||
    process.env.API_BASE_URL ||
    process.env.PYTHON_BACKEND_URL ||
    'http://127.0.0.1:8000';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { email } = req.body || {};

    if (typeof email !== 'string' || !email.trim()) {
        return res.status(400).json({ error: 'Email is required' });
    }

    try {
        const forgotResponse = await fetch(`${API_BASE_URL}/api/auth/forgot-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
        });

        let data: any;
        try {
            data = await forgotResponse.json();
        } catch {
            return res.status(502).json({ error: 'Password reset service returned an invalid response' });
        }

        if (!data || typeof data !== 'object' || Array.isArray(data)) {
            return res.status(502).json({ error: 'Password reset service returned an invalid response' });
        }

        const retryAfter = forgotResponse.headers.get('Retry-After');
        if (retryAfter) {
            res.setHeader('Retry-After', retryAfter);
        }

        return res.status(forgotResponse.status).json(data);
    } catch (error: any) {
        console.error('Forgot password proxy failed', { stage: 'backend-request' });
        return res.status(502).json({ error: 'Password reset service is unreachable' });
    }
}
