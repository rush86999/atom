import { NextApiRequest, NextApiResponse } from 'next';
import { query } from '../../../lib/db';
import { USE_BACKEND_API } from '../../../lib/api';
import { sendEmail } from '../../../lib/email';
import crypto from 'crypto';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
                const forgotResponse = await fetch(`${API_BASE_URL}/api/auth/forgot-password`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email })
                });

                if (forgotResponse.ok) {
                    const data = await forgotResponse.json();
                    return res.status(200).json(data);
                }
            } catch (error: any) {
                // Log error but fall back to direct DB query
                console.error('Backend API error, falling back to direct DB:', error.message);
            }
        }

        // Direct DB query (original implementation)
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
            'INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES ($1, $2, $3)',
            [user.id, token, expiresAt]
        );

        // Send email with reset link
        try {
            const resetLink = `${process.env.NEXTAUTH_URL}/auth/reset-password?token=${token}`;
            const emailHtml = `
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Password Reset Request</h2>
                <p>Hello,</p>
                <p>We received a request to reset your password for Atom Platform. Click the button below to proceed:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="${resetLink}" style="background-color: #0070f3; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">Reset Password</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="color: #666; font-size: 13px; word-break: break-all;">${resetLink}</p>
                <p>This link will expire in 1 hour.</p>
                <hr style="border: 1px solid #eee; margin-top: 30px;" />
                <p style="color: #888; font-size: 12px;">If you didn't request a password reset, you can safely ignore this email.</p>
            </div>
            `;

            await sendEmail({
                to: email,
                subject: 'Reset your Atom Platform password',
                html: emailHtml
            });

            console.log(`Password reset email sent to ${email}`);
        } catch (emailError) {
            console.error('Failed to send password reset email:', emailError);
            // We still return 200 to not leak that the email exists, but we log the error
        }

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
