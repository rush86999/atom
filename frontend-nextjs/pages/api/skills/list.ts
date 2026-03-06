import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'next-auth/react';
import { getToken } from 'next-auth/jwt';

// Helper to determine active backend
function getBackendUrl() {
    // Use env var first, fallback to standard local ports
    if (process.env.BACKEND_API_URL) {
        return process.env.BACKEND_API_URL;
    }
    return 'http://127.0.0.1:8000';
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    // Only allow GET requests for listing skills
    if (req.method !== 'GET') {
        return res.status(405).json({ message: 'Method Not Allowed' });
    }

    try {
        const token = await getToken({ req });
        const session = await getSession({ req });
        const accessToken = token?.accessToken || session?.accessToken;

        const backendUrl = getBackendUrl();
        const endpoint = `${backendUrl}/api/skills/list`;

        // Forward the query parameters (e.g., status, skill_type)
        const queryParams = new URLSearchParams(req.query as any).toString();
        const finalUrl = queryParams ? `${endpoint}?${queryParams}` : endpoint;

        console.log(`[API Proxy] Fetching skills from: ${finalUrl}`);

        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };

        if (accessToken) {
            headers['Authorization'] = `Bearer ${accessToken}`;
        }

        const response = await fetch(finalUrl, {
            method: 'GET',
            headers,
        });

        // Check if the response is valid JSON
        const contentType = response.headers.get('content-type');
        let data;
        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            const text = await response.text();
            console.error(`[API Proxy Error] Non-JSON response from backend:`, text.substring(0, 500));
            return res.status(response.status).json({
                error: 'Invalid response from backend',
                details: text.substring(0, 200)
            });
        }

        if (!response.ok) {
            console.error(`[API Proxy Error] Backend returned status ${response.status}:`, data);
            return res.status(response.status).json(data);
        }

        // Set caching headers for a short duration since skills change
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=300');
        return res.status(200).json(data);
    } catch (error) {
        console.error('[API Proxy Exception] Error fetching skills:', error);
        return res.status(500).json({ error: 'Internal Server Error fetching skills' });
    }
}
