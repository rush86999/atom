import { NextApiRequest, NextApiResponse } from "next";

/**
 * Zoom Users API endpoint
 * Latest Zoom API version: v2 (as of 2025-12-08)
 * Documentation: https://developers.zoom.us/docs/api/
 */

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    try {
        // Authentication check
        const authHeader = req.headers.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return res.status(401).json({ error: 'Unauthorized: Missing or invalid Authorization header' });
        }
        const token = authHeader.split(' ')[1];

        // Validate token with Zoom API
        try {
            const tokenValidation = await fetch(`https://api.zoom.us/v2/users/me`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!tokenValidation.ok) {
                return res.status(401).json({ error: 'Unauthorized: Invalid or expired Zoom token' });
            }
        } catch (tokenError) {
            return res.status(401).json({ error: 'Unauthorized: Unable to validate token' });
        }

        // Method validation
        if (req.method !== 'POST') {
            return res.status(405).json({ error: 'Method not allowed. Use POST' });
        }

        // Get request parameters
        const { status = 'active', page_size = 30, page_number = 1, role_id } = req.body;

        // Build Zoom API URL with parameters
        const params = new URLSearchParams({
            page_size: page_size.toString(),
            page_number: page_number.toString(),
            status: status
        });

        if (role_id) {
            params.append('role_id', role_id.toString());
        }

        // Call Zoom API
        const zoomResponse = await fetch(`https://api.zoom.us/v2/users?${params}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!zoomResponse.ok) {
            const errorData = await zoomResponse.json().catch(() => ({}));
            return res.status(zoomResponse.status).json({
                error: 'Failed to fetch Zoom users',
                details: errorData.message || 'Unknown error'
            });
        }

        const usersData = await zoomResponse.json();

        return res.status(200).json({
            success: true,
            data: {
                users: usersData.users || [],
                total_records: usersData.total_records || 0
            },
            meta: {
                total: usersData.total_records || 0,
                page: usersData.page_number || page_number,
                page_size: usersData.page_size || page_size,
                total_pages: Math.ceil((usersData.total_records || 0) / (usersData.page_size || page_size)),
                api_version: "v2"
            }
        });

    } catch (error) {
        console.error('Zoom users API error:', error);
        return res.status(500).json({
            error: 'Internal server error',
            details: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}
