import { NextApiRequest, NextApiResponse } from "next";

/**
 * Zoom Recordings API endpoint
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
        const { userId = 'me', startDate, endDate, pageSize = 30, nextPageToken, from, to } = req.body;

        // Build Zoom API URL with parameters
        const params = new URLSearchParams({
            page_size: pageSize.toString()
        });

        if (nextPageToken) {
            params.append('next_page_token', nextPageToken);
        }

        // Set date range if not provided
        const fromParam = from || startDate || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
        const toParam = to || endDate || new Date().toISOString().split('T')[0];

        params.append('from', fromParam);
        params.append('to', toParam);

        // Call Zoom API
        const zoomResponse = await fetch(`https://api.zoom.us/v2/users/${encodeURIComponent(userId)}/recordings?${params}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!zoomResponse.ok) {
            const errorData = await zoomResponse.json().catch(() => ({}));
            return res.status(zoomResponse.status).json({
                error: 'Failed to fetch Zoom recordings',
                details: errorData.message || 'Unknown error'
            });
        }

        const recordingsData = await zoomResponse.json();

        return res.status(200).json({
            success: true,
            data: {
                recordings: recordingsData.meetings || [],
                next_page_token: recordingsData.next_page_token,
                total_records: recordingsData.total_records || 0
            },
            meta: {
                total: recordingsData.total_records || 0,
                next_page_token: recordingsData.next_page_token,
                from: fromParam,
                to: toParam,
                page_size: pageSize,
                api_version: "v2"
            }
        });

    } catch (error) {
        console.error('Zoom recordings API error:', error);
        return res.status(500).json({
            error: 'Internal server error',
            details: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}
