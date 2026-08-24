import { NextApiRequest, NextApiResponse } from 'next';

const API_BASE_URL = process.env.PYTHON_API_SERVICE_BASE_URL ||
    process.env.API_BASE_URL ||
    process.env.PYTHON_BACKEND_URL ||
    'http://127.0.0.1:8000';

// Same policy the backend enforces (core/auth_endpoints.py UserCreate).
// One policy everywhere — the old 12-char complexity gate here contradicted
// both UIs and the backend, rejecting passwords the backend would accept.
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

    const { email, password, name, first_name, last_name } = req.body || {};

    if (!email || !password) {
        return res.status(400).json({ error: 'Email and password are required' });
    }

    const passwordError = validatePassword(password);
    if (passwordError) {
        return res.status(400).json({ error: passwordError });
    }

    // Accept either explicit first/last or a single full name (which we split).
    let firstName = (first_name || '').trim();
    let lastName = (last_name || '').trim();
    if ((!firstName || !lastName) && name) {
        const parts = String(name).trim().split(/\s+/).filter(Boolean);
        firstName = firstName || parts[0] || '';
        lastName = lastName || parts.slice(1).join(' ');
    }
    if (!firstName || !lastName) {
        return res.status(400).json({ error: 'First and last name are required' });
    }

    try {
        const registerResponse = await fetch(`${API_BASE_URL}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email,
                password,
                first_name: firstName,
                last_name: lastName,
            }),
        });

        const data = await registerResponse.json().catch(() => ({}));

        // Pass the backend's status and error through verbatim — including
        // FastAPI 422 validation arrays and 429 rate limits with Retry-After.
        // (The old direct-Postgres fallback here wrote to a `users` table the
        // Python backend never reads, so it only produced divergent ghosts.)
        if (!registerResponse.ok) {
            const retryAfter = registerResponse.headers.get('Retry-After');
            if (retryAfter) {
                res.setHeader('Retry-After', retryAfter);
            }
            return res.status(registerResponse.status).json(data);
        }

        return res.status(201).json(data);
    } catch (error: any) {
        console.error('Registration proxy error:', error.message);
        return res.status(502).json({ error: 'Registration service is unreachable' });
    }
}
