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
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/zendesk/auth/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code: req.query.code,
        user_id: userId,
        redirect_uri: `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/zendesk/oauth/callback`,
      }),
    });

    if (response.ok) {
      const data = await response.json();

      // Redirect to Zendesk integration page with success message
      res.redirect('/integrations/zendesk?success=true');
    } else {
      const errorData = await response.json();
      return res.status(400).json({
        error: 'Failed to complete Zendesk OAuth',
        message: errorData.message || 'Unknown OAuth error',
      });
    }
  } catch (error) {
    console.error('Zendesk OAuth callback error:', error);
    return res.status(500).json({
      error: 'Failed to complete Zendesk OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}