import { NextApiRequest, NextApiResponse } from 'next';
import { query } from '../../../lib/db';
import { USE_BACKEND_API, emailVerificationAPI } from '../../../lib/api';
import { sendEmail, generateVerificationEmailHTML } from '../../../lib/email';
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

        // Use backend API if feature flag is enabled
        if (USE_BACKEND_API) {
            try {
                const result = await emailVerificationAPI.sendVerificationEmail(email);
                return res.status(200).json({
                    message: 'Verification email sent successfully',
                    email: email,
                });
            } catch (error: any) {
                // Log error but fall back to direct DB query
                console.error('Backend API error, falling back to direct DB:', error.message);
            }
        }

        // Direct DB query (original implementation)
        // Check if user exists
        const userResult = await query(
            'SELECT id, name, email_verified FROM users WHERE email = $1',
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

        // Delete any existing verification tokens for this user
        await query(
            'DELETE FROM email_verification_tokens WHERE user_id = $1',
            [user.id]
        );

        // Generate 6-digit verification code
        const verificationCode = crypto.randomInt(100000, 999999).toString();

        // Store token in database (expires in 24 hours)
        const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000);
        await query(
            'INSERT INTO email_verification_tokens (user_id, token, expires_at) VALUES ($1, $2, $3)',
            [user.id, verificationCode, expiresAt]
        );

        // Send verification email
        const emailHTML = generateVerificationEmailHTML(verificationCode, user.name);
        const emailSent = await sendEmail({
            to: email,
            subject: 'Verify Your Email Address',
            html: emailHTML,
        });

        if (!emailSent) {
            return res.status(500).json({
                error: 'Failed to send verification email. Please try again later.'
            });
        }

        return res.status(200).json({
            message: 'Verification email sent successfully',
            email: email,
        });
    } catch (error) {
        console.error('Send verification error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}
