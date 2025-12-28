import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    // For callback, if session is missing, we might want to redirect to login with callback,
    // but for now let's just error or redirect to error page
    return res.redirect('/auth/signin?callbackUrl=/integrations/salesforce');
  }
  const backendToken = (session as any).backendToken;
  if (!backendToken) {
    return res.redirect('/auth/signin?error=missing_token&callbackUrl=/integrations/salesforce');
  }

  try {
    const { code, state, error } = req.query;

    if (error) {
      return res.redirect(`/integrations/salesforce?error=${error}`);
    }

    if (!code) {
      return res.redirect(`/integrations/salesforce?error=missing_code`);
    }

    // Exchange authorization code for tokens
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:8000';
    // Backend expects GET /api/salesforce/callback?code=...
    const response = await fetch(`${backendUrl}/api/salesforce/callback?code=${code}${state ? `&state=${state}` : ''}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${backendToken}`
      }
    });

    if (response.ok) {
      // Redirect to Salesforce integration page with success message
      res.redirect('/integrations/salesforce?success=true&connected=true');
    } else {
      const errorData = await response.json().catch(() => ({}));
      return res.redirect(`/integrations/salesforce?error=exchange_failed&details=${errorData.detail || 'unknown'}`);
    }
  } catch (error) {
    console.error('Salesforce OAuth callback error:', error);
    return res.redirect('/integrations/salesforce?error=server_error');
  }
}