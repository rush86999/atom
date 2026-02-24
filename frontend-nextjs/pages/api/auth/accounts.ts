import { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    // Get token from Authorization header
    const authHeader = req.headers.authorization;
    const token = authHeader?.replace('Bearer ', '');

    if (!token) {
        return res.status(401).json({ error: 'Unauthorized - no token provided' });
    }

    if (req.method === 'GET') {
        try {
            // Proxy to backend /api/auth/me to get user info
            const meResponse = await fetch(`${BACKEND_URL}/api/auth/me`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
            });

            if (!meResponse.ok) {
                const errorText = await meResponse.text();
                console.error('Backend /api/auth/me error:', meResponse.status, errorText);
                return res.status(meResponse.status).json({
                    error: `Backend auth error: ${meResponse.status}`
                });
            }

            const userData = await meResponse.json();

            // Transform backend response to match the expected AccountData format
            return res.status(200).json({
                user: {
                    email: userData.email || '',
                    name: userData.name || userData.first_name
                        ? `${userData.first_name || ''} ${userData.last_name || ''}`.trim()
                        : userData.email || '',
                    email_verified: userData.email_verified || null,
                    image: userData.image || userData.avatar || null,
                    created_at: userData.created_at || new Date().toISOString(),
                },
                accounts: [
                    {
                        id: userData.id || 'credentials-account',
                        provider: 'credentials',
                        provider_account_id: userData.email || '',
                        created_at: userData.created_at || new Date().toISOString(),
                        expires_at: null,
                    }
                ],
            });
        } catch (error) {
            console.error('Get accounts error:', error);
            return res.status(500).json({ error: 'Failed to fetch account information' });
        }
    }

    if (req.method === 'DELETE') {
        // Account unlinking not supported in simplified auth mode
        return res.status(400).json({
            error: 'Cannot remove the only authentication method.'
        });
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
