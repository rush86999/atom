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
        const { email, password, name } = req.body;

        // Validation
        if (!email || !password) {
            return res.status(400).json({ error: 'Email and password are required' });
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
                // Check if backend has a registration endpoint
                const registerResponse = await fetch(`${API_BASE_URL}/api/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password, name })
                });

                if (registerResponse.ok) {
                    const data = await registerResponse.json();
                    return res.status(201).json(data);
                } else if (registerResponse.status === 400) {
                    const error = await registerResponse.json();
                    return res.status(400).json(error);
                } else {
                    // If endpoint doesn't exist or fails, fall back to direct DB
                    console.log('Backend registration endpoint not available, falling back to direct DB');
                }
            } catch (error: any) {
                // Log error but fall back to direct DB query
                console.error('Backend API error, falling back to direct DB:', error.message);
            }
        }

        // Direct DB query (original implementation)
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
