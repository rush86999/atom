import { NextApiRequest, NextApiResponse } from 'next';
import { query } from '../../../lib/db';
import crypto from 'crypto';
import { sendEmail, generatePasswordResetEmailHTML } from '../../../lib/email';

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
            'SELECT id, name FROM users WHERE email = $1',
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

        // Send password reset email
        const resetLink = `${process.env.NEXTAUTH_URL}/auth/reset-password?token=${token}`;
        const userName = user.name || '';

        try {
            const emailHTML = generatePasswordResetEmailHTML(resetLink, userName);
            await sendEmail({
                to: email,
                subject: 'Reset Your Password',
                html: emailHTML,
            });
        } catch (emailError) {
            console.error('Failed to send password reset email:', emailError);
            // Continue - don't expose email failure to user
        }

        return res.status(200).json({
            message: 'If an account exists with that email, a password reset link has been sent.',
            // REMOVE THIS IN PRODUCTION - only for development
            ...(process.env.NODE_ENV === 'development' && { resetLink })
        });
    } catch (error) {
        console.error('Forgot password error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}
