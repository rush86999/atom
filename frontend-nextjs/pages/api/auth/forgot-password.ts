import { NextApiRequest, NextApiResponse } from 'next';
import { query } from '../../../lib/db';
import crypto from 'crypto';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { email } = req.body;

        if (!email) {
            return res.status(400).json({ error: 'Email is required' });
        }

        // Check if user exists
        const userResult = await query(
            'SELECT id FROM users WHERE email = $1',
            [email]
        );

        // Always return success to prevent email enumeration
        if (userResult.rows.length === 0) {
            return res.status(200).json({
                message: 'If an account exists with that email, a password reset link has been sent.'
            });
        }

        const user = userResult.rows[0];

        // Generate secure random token
        const token = crypto.randomBytes(32).toString('hex');

        // Set expiry to 1 hour from now
        const expiresAt = new Date();
        expiresAt.setHours(expiresAt.getHours() + 1);

        // Store token in database
        await query(
            'INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES ($1, $2, $3)',
            [user.id, token, expiresAt]
        );

        // TODO: Send email with reset link
        // For now, log the token (REMOVE THIS IN PRODUCTION)
        console.log(`Password reset token for ${email}: ${token}`);
        console.log(`Reset link: ${process.env.NEXTAUTH_URL}/auth/reset-password?token=${token}`);

        return res.status(200).json({
            message: 'If an account exists with that email, a password reset link has been sent.',
            // REMOVE THIS IN PRODUCTION - only for development
            ...(process.env.NODE_ENV === 'development' && { resetLink: `/auth/reset-password?token=${token}` })
        });
    } catch (error) {
        console.error('Forgot password error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}
