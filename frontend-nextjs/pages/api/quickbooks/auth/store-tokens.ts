import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  if (req.method !== 'POST') {
    return res.status(405).json({
      error: 'Method not allowed',
      message: 'Only POST method is allowed for storing tokens',
    });
  }

  try {
    const { user_id, access_token, refresh_token, expires_at, realm_id } = req.body;

    if (!user_id || !access_token || !realm_id) {
      return res.status(400).json({
        error: 'Missing required fields',
        message: 'user_id, access_token, and realm_id are required',
      });
    }

    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';
    const url = `${backendUrl}/api/quickbooks/auth/store-tokens`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id,
        access_token,
        refresh_token,
        expires_at,
        realm_id,
      }),
    });

    if (response.ok) {
      return res.status(200).json({
        message: 'QuickBooks tokens stored successfully',
      });
    } else {
      const errorData = await response.json();
      return res.status(response.status).json({
        error: 'Failed to store tokens in backend',
        message: errorData.message || 'Unknown backend error',
      });
    }
  } catch (error) {
    console.error('QuickBooks token storage error:', error);
    return res.status(500).json({
      error: 'Failed to store QuickBooks tokens',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}