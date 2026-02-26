
import { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    const authHeader = req.headers.authorization;
    const { action, type, invoice_id } = req.query;

    try {
        if (req.method === 'GET') {
            if (action === 'download') {
                const response = await fetch(`${BACKEND_URL}/api/apar/${type}/${invoice_id}/download`, {
                    headers: {
                        ...(authHeader ? { 'Authorization': authHeader } : {}),
                    },
                });

                if (!response.ok) {
                    const text = await response.text();
                    return res.status(response.status).json({ error: text });
                }

                const blob = await response.blob();
                const arrayBuffer = await blob.arrayBuffer();
                const buffer = Buffer.from(arrayBuffer);

                res.setHeader('Content-Type', 'text/plain');
                res.setHeader('Content-Disposition', `attachment; filename=invoice_${invoice_id}.txt`);
                return res.status(200).send(buffer);
            }

            // Default: fetch AR summary or invoices
            const response = await fetch(`${BACKEND_URL}/api/apar/ar/overdue`, {
                headers: {
                    ...(authHeader ? { 'Authorization': authHeader } : {}),
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                const text = await response.text();
                return res.status(response.status).json({ error: text });
            }

            const data = await response.json();
            return res.status(200).json(data);
        }

        return res.status(405).json({ error: 'Method not allowed' });
    } catch (error) {
        console.error('Invoice proxy error:', error);
        return res.status(500).json({ error: 'Failed to process invoice request' });
    }
}
