import { NextApiRequest, NextApiResponse } from "next";

const PYTHON_API_BASE_URL = process.env.PYTHON_API_SERVICE_BASE_URL || "http://localhost:8000";

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method === 'GET') {
        const { code, state, error } = req.query;

        if (error) {
            console.error("Google OAuth error from provider:", error);
            return res.redirect(`/integrations?error=${encodeURIComponent(error.toString())}`);
        }

        if (!code) {
            return res.status(400).json({ error: "Missing authorization code" });
        }

        try {
            // Forward the callback to the backend
            // The backend is where tokens are exchanged and stored in the database
            const backendCallbackUrl = new URL(`${PYTHON_API_BASE_URL}/api/v1/auth/oauth/google/callback`);
            backendCallbackUrl.searchParams.append("code", code.toString());
            if (state) backendCallbackUrl.searchParams.append("state", state.toString());

            // We redirect the user to the backend callback, which will then redirect back to the frontend success page
            res.redirect(backendCallbackUrl.toString());
        } catch (error) {
            console.error("Failed to process Google OAuth callback:", error);
            res.status(500).json({ error: "Failed to process Google OAuth callback" });
        }
    } else {
        res.status(405).json({ error: 'Method not allowed' });
    }
}
