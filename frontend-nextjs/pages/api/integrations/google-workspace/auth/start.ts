import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../../auth/[...nextauth]";

const PYTHON_API_BASE_URL = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

    if (req.method === 'GET') {
        const session = await getServerSession(req, res, authOptions);
        // During development, we might skip session check if needed, but safer to keep it
        if (!session || !session.user) {
            // If No session, redirect to signin
            return res.redirect(`/auth/signin?callbackUrl=${encodeURIComponent(req.url || '')}`);
        }

        try {
            // Redirect directly to the backend OAuth initiation endpoint
            // The backend handler will take it from there
            const backendAuthUrl = `${PYTHON_API_BASE_URL}/api/v1/auth/oauth/google/initiate`;
            res.redirect(backendAuthUrl);
        } catch (error) {
            console.error("Failed to initiate Google OAuth:", error);
            res.status(500).json({ error: "Failed to initiate Google OAuth flow" });
        }
    } else {
        res.status(405).json({ error: 'Method not allowed' });
    }
}
