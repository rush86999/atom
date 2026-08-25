import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../../auth/[...nextauth]";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Round 80: forward the caller's Authorization header to the backend
  const fwdAuth = req.headers.authorization
    ? { Authorization: req.headers.authorization as string }
    : {};

  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }
  const backendToken = (session as any).backendToken;
  if (!backendToken) {
    return res.status(401).json({ error: 'Missing authentication token' });
  }

  const userId = session.user.id;

  try {
    // Start OAuth flow
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendUrl}/api/salesforce/auth/url`, {
      headers: { ...fwdAuth,
        'Authorization': `Bearer ${backendToken}`
      }
    });

    if (response.ok) {
      const data = await response.json();
      // Redirect to Salesforce authorization URL
      if (data.url) {
        res.redirect(data.url);
      } else {
        res.status(500).json({
          error: 'Failed to get Salesforce authorization URL',
          message: 'No authorization URL returned from backend',
        });
      }
    } else {
      res.status(500).json({
        error: 'Backend Salesforce service error',
        message: 'Failed to contact Salesforce authentication service',
      });
    }
  } catch (error) {
    console.error('Salesforce OAuth start error:', error);
    return res.status(500).json({
      error: 'Failed to start Salesforce OAuth flow',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}