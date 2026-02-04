import { NextApiRequest, NextApiResponse } from 'next';
import { query } from '../../../lib/db';
import { USE_BACKEND_API } from '../../../lib/api';
import bcrypt from 'bcryptjs';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { token, password } = req.body;

        if (!token || !password) {
            return res.status(400).json({ error: 'Token and password are required' });
        }

        // Import password validator
        const { validatePassword } = await import('../../../lib/password-validator');
        const passwordStrength = validatePassword(password);

        if (!passwordStrength.isValid) {
            return res.status(400).json({
                error: 'Password does not meet security requirements',
                details: passwordStrength.feedback
            });
        }

        // Use backend API if feature flag is enabled
        if (USE_BACKEND_API) {
            try {
                const resetResponse = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token, password })
                });

                if (resetResponse.ok) {
                    const data = await resetResponse.json();
                    return res.status(200).json(data);
                } else if (resetResponse.status === 400) {
                    const error = await resetResponse.json();
                    return res.status(400).json(error);
                }
            } catch (error: any) {
                // Log error but fall back to direct DB query
                console.error('Backend API error, falling back to direct DB:', error.message);
            }
        }

        // Direct DB query (original implementation)
        // Validate token
        const tokenResult = await query(
            'SELECT user_id, expires_at, is_used FROM password_reset_tokens WHERE token_hash = $1',
            [token]
        );

        if (tokenResult.rows.length === 0) {
            return res.status(400).json({ error: 'Invalid or expired reset token' });
        }

        const resetToken = tokenResult.rows[0];

        // Check if token is expired
        if (new Date() > new Date(resetToken.expires_at)) {
            return res.status(400).json({ error: 'Reset token has expired' });
        }

        // Check if token was already used
        if (resetToken.is_used) {
            return res.status(400).json({ error: 'Reset token has already been used' });
        }

        // Hash new password
        const passwordHash = await bcrypt.hash(password, 10);

        // Update user password
        await query(
            'UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2',
            [passwordHash, resetToken.user_id]
        );

        // Mark token as used
        await query(
            'UPDATE password_reset_tokens SET is_used = TRUE WHERE token_hash = $1',
            [token]
        );

        return res.status(200).json({
            message: 'Password has been reset successfully. You can now log in with your new password.'
        });
    } catch (error) {
        console.error('Reset password error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}
