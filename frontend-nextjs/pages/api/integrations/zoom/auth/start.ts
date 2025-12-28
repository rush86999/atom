import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../../auth/[...nextauth]";

const PYTHON_API_BASE_URL = process.env.PYTHON_API_SERVICE_BASE_URL || "http://localhost:8000";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method === 'GET') {
        const session = await getServerSession(req, res, authOptions);
        if (!session || !session.user) {
            return res.status(401).json({ error: 'Unauthorized' });
        }
        const backendToken = (session as any).backendToken;
        if (!backendToken) {
            return res.status(401).json({ error: 'Missing authentication token' });
        }
        try {
            const response = await fetch(`${PYTHON_API_BASE_URL}/api/zoom/v1/auth/url`, {
                headers: {
                    'Authorization': `Bearer ${backendToken}`
                }
            });

            if (!response.ok) {
                throw new Error(`Backend responded with status: ${response.status}`);
            }

            const data = await response.json();

            if (data.url) {
                res.redirect(data.url);
            } else {
                res.status(500).json({ error: "No authorization URL returned from backend" });
            }
        } catch (error) {
            console.error("Failed to get Zoom auth URL:", error);
            res.status(500).json({ error: "Failed to initiate Zoom OAuth flow" });
        }
    } else {
        res.status(405).json({ error: 'Method not allowed' });
    }
}
