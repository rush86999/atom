/**
 * Agent Governance API Proxy
 * Routes frontend requests to backend agent-governance endpoints
 */

import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const { method, query, body } = req;

    // Extract the path segments after /api/agent-governance/
    const pathSegments = query.path as string[] || [];
    const path = pathSegments.join('/');

    try {
        let backendUrl = `${BACKEND_URL}/api/agent-governance`;

        // Build the full URL
        if (path) {
            backendUrl += `/${path}`;
        }

        // Add query parameters
        const queryParams = new URLSearchParams();
        Object.entries(query).forEach(([key, value]) => {
            if (key !== 'path' && value) {
                queryParams.append(key, Array.isArray(value) ? value[0] : value);
            }
        });

        if (queryParams.toString()) {
            backendUrl += `?${queryParams.toString()}`;
        }

        const fetchOptions: RequestInit = {
            method: method || 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        };

        // Add body for POST/PUT/PATCH requests
        if (['POST', 'PUT', 'PATCH'].includes(method || '') && body) {
            fetchOptions.body = JSON.stringify(body);
        }

        const response = await fetch(backendUrl, fetchOptions);
        const data = await response.json();

        res.status(response.status).json(data);

    } catch (error) {
        console.error('Agent governance proxy error:', error);
        res.status(500).json({
            error: 'Failed to proxy request to backend',
            message: error instanceof Error ? error.message : 'Unknown error'
        });
    }
}
