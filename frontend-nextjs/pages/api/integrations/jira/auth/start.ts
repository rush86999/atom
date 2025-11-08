import { NextApiRequest, NextApiResponse } from "next";
import { getSession } from "supertokens-node/nextjs";
import { SessionContainer } from "supertokens-node/recipe/session";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  let session: SessionContainer;
  try {
    session = await getSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.getUserId();

  try {
    // Start OAuth flow
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
    const response = await fetch(`${backendUrl}/api/auth/jira/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        redirect_uri: `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/integrations/jira/auth/callback`,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      // Redirect to Jira authorization URL
      if (data.authorization_url) {
        res.redirect(data.authorization_url);
      } else {
        res.status(500).json({
          error: 'Failed to get Jira authorization URL',
          message: 'No authorization URL returned from backend',
        });
      }
    } else {
      res.status(500).json({
        error: 'Backend Jira service error',
        message: 'Failed to contact Jira authentication service',
      });
    }
  } catch (error) {
    console.error('Jira OAuth start error:', error);
    return res.status(500).json({
      error: 'Failed to start Jira OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}