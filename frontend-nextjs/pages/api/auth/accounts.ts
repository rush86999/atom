import { NextApiRequest, NextApiResponse } from 'next';
import { getServerSession } from 'next-auth';
import { authOptions } from './[...nextauth]';
import { query } from '../../../lib/db';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    // Get authenticated user session
    const session = await getServerSession(req, res, authOptions);

    if (!session?.user?.email) {
        return res.status(401).json({ error: 'Unauthorized' });
    }

    if (req.method === 'GET') {
        try {
            // Get user ID
            const userResult = await query(
                'SELECT id FROM users WHERE email = $1',
                [session.user.email]
            );

            if (userResult.rows.length === 0) {
                return res.status(404).json({ error: 'User not found' });
            }

            const userId = userResult.rows[0].id;

            // Get all linked accounts
            const accountsResult = await query(
                `SELECT 
                    id,
                    provider,
                    provider_account_id,
                    created_at,
                    expires_at
                FROM user_accounts 
                WHERE user_id = $1
                ORDER BY created_at DESC`,
                [userId]
            );

            // Get user info
            const user = await query(
                'SELECT email, name, email_verified, image, created_at FROM users WHERE id = $1',
                [userId]
            );

            return res.status(200).json({
                user: user.rows[0],
                accounts: accountsResult.rows,
            });
        } catch (error) {
            console.error('Get accounts error:', error);
            return res.status(500).json({ error: 'Internal server error' });
        }
    }

    if (req.method === 'DELETE') {
        try {
            const { accountId } = req.body;

            if (!accountId) {
                return res.status(400).json({ error: 'Account ID is required' });
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

            // Check how many accounts the user has
            const accountCount = await query(
                'SELECT COUNT(*) as count FROM user_accounts WHERE user_id = $1',
                [userId]
            );

            if (parseInt(accountCount.rows[0].count) <= 1) {
                return res.status(400).json({
                    error: 'Cannot remove last authentication method. Add another method first.'
                });
            }

            // Delete the account (only if it belongs to this user)
            const deleteResult = await query(
                'DELETE FROM user_accounts WHERE id = $1 AND user_id = $2 RETURNING provider',
                [accountId, userId]
            );

            if (deleteResult.rows.length === 0) {
                return res.status(404).json({ error: 'Account not found or unauthorized' });
            }

            return res.status(200).json({
                message: `${deleteResult.rows[0].provider} account unlinked successfully`,
            });
        } catch (error) {
            console.error('Delete account error:', error);
            return res.status(500).json({ error: 'Internal server error' });
        }
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
