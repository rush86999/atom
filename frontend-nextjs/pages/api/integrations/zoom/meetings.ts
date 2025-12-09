import { NextApiRequest, NextApiResponse } from "next";

/**
 * Zoom Meetings API endpoint
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

        // Request body validation (if needed)
        // Example: const { userId, startDate, endDate } = req.body;
        // Add validation as needed

        // Get request parameters
        const { userId = 'me', startDate, endDate, page_size = 30, page_number = 1 } = req.body;

        // Build Zoom API URL with parameters
        const params = new URLSearchParams({
            type: 'scheduled', // Get scheduled meetings
            page_size: page_size.toString(),
            page_number: page_number.toString()
        });

        if (startDate) {
            params.append('from', startDate);
        }
        if (endDate) {
            params.append('to', endDate);
        }

        // Call Zoom API
        const zoomResponse = await fetch(`https://api.zoom.us/v2/users/${encodeURIComponent(userId)}/meetings?${params}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!zoomResponse.ok) {
            const errorData = await zoomResponse.json().catch(() => ({}));
            return res.status(zoomResponse.status).json({
                error: 'Failed to fetch Zoom meetings',
                details: errorData.message || 'Unknown error'
            });
        }

        const meetingsData = await zoomResponse.json();

        return res.status(200).json({
            success: true,
            data: {
                meetings: meetingsData.meetings || [],
                total_records: meetingsData.total_records || 0
            },
            meta: {
                total: meetingsData.total_records || 0,
                page: meetingsData.page_number || page_number,
                page_size: meetingsData.page_size || page_size,
                api_version: "v2"
            }
        });

    } catch (error) {
        console.error('Zoom meetings API error:', error);
        return res.status(500).json({
            error: 'Internal server error',
            details: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}
