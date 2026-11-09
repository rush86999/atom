import { NextApiRequest, NextApiResponse } from 'next';

const API_BASE_URL = process.env.PYTHON_API_SERVICE_BASE_URL ||
    process.env.API_BASE_URL ||
    process.env.PYTHON_BACKEND_URL ||
    'http://127.0.0.1:8000';

// Same policy the backend enforces (core/auth_endpoints.py UserCreate).
function validatePassword(password: string): string | null {
    if (!password || password.length < 8) {
        return 'Password must be at least 8 characters long';
    }
    if (password.length > 128) {
        return 'Password must be at most 128 characters';
    }
    if (new TextEncoder().encode(password).length > 72) {
        return 'Password must be at most 72 bytes when UTF-8 encoded';
    }
    return null;
}

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { token, password } = req.body || {};

    if (typeof token !== 'string' || !token.trim() || typeof password !== 'string' || !password) {
        return res.status(400).json({ error: 'Token and password are required' });
    }

    const passwordError = validatePassword(password);
    if (passwordError) {
        return res.status(400).json({ error: passwordError });
    }

    try {
        const resetResponse = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, password }),
        });

        let data: any;
        try {
            data = await resetResponse.json();
        } catch {
            return res.status(502).json({ error: 'Password reset service returned an invalid response' });
        }

        if (!data || typeof data !== 'object' || Array.isArray(data)) {
            return res.status(502).json({ error: 'Password reset service returned an invalid response' });
        }

        const retryAfter = resetResponse.headers.get('Retry-After');
        if (retryAfter) {
            res.setHeader('Retry-After', retryAfter);
        }

        return res.status(resetResponse.status).json(data);
    } catch (error: any) {
        console.error('Reset password proxy failed', { stage: 'backend-request' });
        return res.status(502).json({ error: 'Password reset service is unreachable' });
    }
}
