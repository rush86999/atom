import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]";

export default async function handler(
    req: NextApiRequest,
    res: NextApiResponse,
) {
    const session = await getServerSession(req, res, authOptions);

    if (!session || !session.user) {
        return res.status(401).json({ message: "Unauthorized" });
    }

    const userId = session.user.id;

    try {
        // Exchange authorization code for tokens
        const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${backendUrl}/api/dropbox/callback?code=${req.query.code}&state=${req.query.state || ''}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
            const data = await response.json();

            // Redirect to Dropbox integration page with success message
            res.redirect('/integrations/dropbox?success=true');
        } else {
            const errorData = await response.json();
            return res.status(400).json({
                error: 'Failed to complete Dropbox OAuth',
                message: errorData.message || 'Unknown OAuth error',
            });
        }
    } catch (error) {
        console.error('Dropbox OAuth callback error:', error);
        return res.status(500).json({
            error: 'Failed to complete Dropbox OAuth flow',
            message: error instanceof Error ? error.message : 'Unknown error',
        });
    }
}
