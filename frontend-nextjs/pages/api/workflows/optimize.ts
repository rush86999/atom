import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse
) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        // Use environment variable or fallback to 127.0.0.1
        let apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
        // Force IPv4 to avoid Windows ::1 resolution issues
        apiUrl = apiUrl.replace('localhost', '127.0.0.1');

        const response = await fetch(`${apiUrl}/api/v1/analytics/optimize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(req.body),
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error("Optimization Proxy Error:", errorText);
            return res.status(response.status).json({ error: `Backend error: ${response.statusText}` });
        }

        const data = await response.json();
        return res.status(200).json(data);
    } catch (error) {
        console.error('Optimization API Error:', error);
        return res.status(500).json({ error: 'Internal Server Error' });
    }
}
