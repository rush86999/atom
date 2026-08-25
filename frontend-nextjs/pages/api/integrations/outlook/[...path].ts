import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const pathSegments = req.query.path as string[] || [];
    const pathStr = pathSegments.join('/');
    const targetUrl = `${BACKEND_URL}/api/integrations/outlook/${pathStr}`;

    const headers: Record<string, string> = {};

    if (req.headers.authorization) {
        headers['Authorization'] = req.headers.authorization as string;
    }
    if (req.headers['content-type']) {
        headers['Content-Type'] = req.headers['content-type'] as string;
    } else {
        headers['Content-Type'] = 'application/json';
    }

    try {
        const options: RequestInit = {
            method: req.method,
            headers,
        };

        if (req.method !== 'GET' && req.method !== 'HEAD' && req.body) {
            options.body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
        }

        const backendRes = await fetch(targetUrl, options);
        const data = await backendRes.json().catch(() => ({}));
        return res.status(backendRes.status).json(data);
    } catch (error) {
        console.error(`Error proxying /api/integrations/outlook/${pathStr}:`, error);
        return res.status(500).json({ error: 'Failed to proxy request to backend' });
    }
}
