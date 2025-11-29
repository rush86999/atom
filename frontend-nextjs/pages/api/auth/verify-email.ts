import { NextApiRequest, NextApiResponse } from 'next';
import { query } from '../../../lib/db';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { email, code } = req.body;

        if (!email || !code) {
            return res.status(400).json({ error: 'Email and verification code are required' });
        }

        // Get user
        const userResult = await query(
            'SELECT id, email_verified FROM users WHERE email = $1',
            [email]
        );

        if (userResult.rows.length === 0) {
            return res.status(404).json({ error: 'User not found' });
        }

        const user = userResult.rows[0];

        // Check if already verified
        if (user.email_verified) {
            return res.status(400).json({ error: 'Email already verified' });
        }

        // Validate token
        const tokenResult = await query(
            'SELECT token, expires_at FROM email_verification_tokens WHERE user_id = $1 AND token = $2',
            [user.id, code.trim()]
        );

        if (tokenResult.rows.length === 0) {
            return res.status(400).json({ error: 'Invalid verification code' });
        }

        const tokenData = tokenResult.rows[0];

        // Check if token is expired
        if (new Date() > new Date(tokenData.expires_at)) {
            return res.status(400).json({ error: 'Verification code has expired. Please request a new one.' });
        }

        // Mark email as verified
        await query(
            'UPDATE users SET email_verified = NOW() WHERE id = $1',
            [user.id]
        );

        // Delete used token
        await query(
            'DELETE FROM email_verification_tokens WHERE user_id = $1',
            [user.id]
        );

        return res.status(200).json({
            message: 'Email verified successfully! You can now sign in.',
        });
    } catch (error) {
        console.error('Verify email error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}
