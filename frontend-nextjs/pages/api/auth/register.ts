import { NextApiRequest, NextApiResponse } from 'next';
import { query } from '../../../lib/db';
import bcrypt from 'bcryptjs';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { email, password, name } = req.body;

        // Validation
        if (!email || !password) {
            return res.status(400).json({ error: 'Email and password are required' });
        }

        if (password.length < 8) {
            return res.status(400).json({ error: 'Password must be at least 8 characters' });
        }

        // Check if user already exists
        const existingUser = await query(
            'SELECT id FROM users WHERE email = $1',
            [email]
        );

        if (existingUser.rows.length > 0) {
            return res.status(400).json({ error: 'User already exists with this email' });
        }

        // Hash password
        const passwordHash = await bcrypt.hash(password, 10);

        // Create user
        const result = await query(
            'INSERT INTO users (email, password_hash, name) VALUES ($1, $2, $3) RETURNING id, email, name, created_at',
            [email, passwordHash, name || null]
        );

        const user = result.rows[0];

        // Send verification email
        try {
            const { sendEmail, generateVerificationEmailHTML } = await import('../../../lib/email');
            const crypto = await import('crypto');

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
            await sendEmail({
                to: email,
                subject: 'Verify Your Email Address',
                html: emailHTML,
            });

            console.log('Verification email sent to:', email);
        } catch (emailError) {
            console.error('Failed to send verification email:', emailError);
            // Don't fail registration if email fails - user can resend later
        }

        return res.status(201).json({
            message: 'User created successfully. Please check your email to verify your account.',
            user: {
                id: user.id,
                email: user.email,
                name: user.name,
                createdAt: user.created_at,
            },
            requiresVerification: true,
        });
    } catch (error) {
        console.error('Registration error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}
