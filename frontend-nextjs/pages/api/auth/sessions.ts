import { NextApiRequest, NextApiResponse } from 'next';
import { getServerSession } from 'next-auth';
import { authOptions } from './[...nextauth]';
import { query } from '../../../lib/db';
import { USE_BACKEND_API, userManagementAPI } from '../../../lib/api';
import { UAParser } from 'ua-parser-js';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    const session = await getServerSession(req, res, authOptions);

    if (!session?.user?.email) {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    // Get user ID
    const userResult = await query(
        'SELECT id FROM users WHERE email = $1',
        [session.user.email]
    );

    if (userResult.rows.length === 0) {
        return res.status(404).json({ error: 'User not found' });
    }

    const userId = userResult.rows[0].id;

    // GET: List active sessions
    if (req.method === 'GET') {
        if (USE_BACKEND_API) {
            try {
                const token = (session as any).backendToken || (session as any).access_token;
                const response = await fetch(`${API_BASE_URL}/api/users/sessions`, {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    return res.status(200).json({ sessions: data });
                }
            } catch (error: any) {
                console.error('Backend API error, falling back to direct DB:', error.message);
            }
        }

        // Direct DB query (original implementation)
        try {
            const sessions = await query(
                `SELECT
                    id,
                    device_type,
                    browser,
                    os,
                    ip_address,
                    last_active_at,
                    created_at,
                    is_active,
                    CASE WHEN session_token = $2 THEN true ELSE false END as is_current
                FROM user_sessions
                WHERE user_id = $1 AND is_active = true AND expires_at > NOW()
                ORDER BY last_active_at DESC`,
                [userId, (session as any).backendToken || '']
            );

            return res.status(200).json({ sessions: sessions.rows });
        } catch (error) {
            console.error('Get sessions error:', error);
            return res.status(500).json({ error: 'Internal server error' });
        }
    }

    // DELETE: Revoke a session
    if (req.method === 'DELETE') {
        const { sessionId, revokeAll } = req.body;

        if (USE_BACKEND_API) {
            try {
                const token = (session as any).backendToken || (session as any).access_token;

                if (revokeAll) {
                    await fetch(`${API_BASE_URL}/api/users/sessions`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        }
                    });
                    return res.status(200).json({ message: 'All sessions revoked' });
                }

                if (!sessionId) {
                    return res.status(400).json({ error: 'Session ID is required' });
                }

                await fetch(`${API_BASE_URL}/api/users/sessions/${sessionId}`, {
                    method: 'DELETE',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });

                return res.status(200).json({ message: 'Session revoked' });
            } catch (error: any) {
                console.error('Backend API error, falling back to direct DB:', error.message);
            }
        }

        // Direct DB query (original implementation)
        try {
            if (revokeAll) {
                await query(
                    'UPDATE user_sessions SET is_active = false WHERE user_id = $1',
                    [userId]
                );
                return res.status(200).json({ message: 'All sessions revoked' });
            }

            if (!sessionId) {
                return res.status(400).json({ error: 'Session ID is required' });
            }

            await query(
                'UPDATE user_sessions SET is_active = false WHERE id = $1 AND user_id = $2',
                [sessionId, userId]
            );

            return res.status(200).json({ message: 'Session revoked' });
        } catch (error) {
            console.error('Revoke session error:', error);
            return res.status(500).json({ error: 'Internal server error' });
        }
    }

    // POST: Record new session (called from client or sign-in callback)
    if (req.method === 'POST') {
        try {
            const ua = new UAParser(req.headers['user-agent'] || '').getResult();
            const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown';

            // In a real implementation, we'd extract this from the JWT token's JTI
            // For now, we'll generate a tracking ID
            const { token } = req.body;

            if (!token) {
                return res.status(400).json({ error: 'Token required' });
            }

            await query(
                `INSERT INTO user_sessions
                (user_id, session_token, user_agent, ip_address, device_type, browser, os, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW() + INTERVAL '30 days')
                ON CONFLICT (session_token) DO UPDATE SET last_active_at = NOW()`,
                [
                    userId,
                    token,
                    req.headers['user-agent'],
                    Array.isArray(ip) ? ip[0] : ip,
                    ua.device.type || 'desktop',
                    ua.browser.name,
                    ua.os.name
                ]
            );

            return res.status(200).json({ message: 'Session recorded' });
        } catch (error) {
            console.error('Record session error:', error);
            return res.status(500).json({ error: 'Internal server error' });
        }
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
