import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]";

/**
 * Slack OAuth Callback Handler
 *
 * This endpoint handles the callback from Slack's OAuth flow.
 *
 * Flow:
 * 1. User clicks "Connect Slack" in the UI
 * 2. Frontend calls GET /api/integrations/slack/oauth/authorize to get auth URL
 * 3. User is redirected to Slack authorization page
 * 4. After authorization, Slack redirects here with a code
 * 5. This handler forwards the code to the backend
 * 6. Backend exchanges code for tokens and stores them securely
 * 7. User is redirected back to the app with success/error status
 *
 * Environment Variables Required:
 * - NEXT_PUBLIC_API_URL: Backend API URL (e.g., http://localhost:8000)
 * - SLACK_CLIENT_ID, SLACK_CLIENT_SECRET: Set in backend
 *
 * Query Parameters:
 * - code: Authorization code from Slack
 * - state: CSRF protection token
 * - error: OAuth error (if authorization failed)
 * - error_description: Error description
 */

const BACKEND_API_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Only allow POST requests
  if (req.method !== "GET") {
    return res.status(405).json({ message: "Method not allowed" });
  }

  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  try {
    const { code, state, error, error_description } = req.query;

    // Handle OAuth errors from Slack
    if (error) {
      console.error("Slack OAuth error:", error, error_description);
      return res.redirect(
        302,
        `/integrations?status=error&provider=slack&error=${error}&message=${encodeURIComponent(
          error_description as string || "Authorization failed"
        )}`
      );
    }

    // Validate authorization code
    if (!code || typeof code !== "string") {
      return res.redirect(
        302,
        "/integrations?status=error&provider=slack&error=missing_code&message=No+authorization+code+provided"
      );
    }

    // Forward the callback to the backend
    const backendUrl = `${BACKEND_API_URL}/api/v1/integrations/slack/oauth/callback`;

    // Include user identification header
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    // Add user ID from session if available
    if (session.user?.id || session.user?.email) {
      headers["X-User-ID"] = (session.user.id || session.user.email) as string;
    }

    const response = await fetch(backendUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({
        code,
        state: state || null,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("Backend OAuth error:", data);
      return res.redirect(
        302,
        `/integrations?status=error&provider=slack&error=${data.error || "unknown"}&message=${encodeURIComponent(
          data.detail || data.message || "Failed to complete OAuth flow"
        )}`
      );
    }

    // Success! Redirect back to integrations page
    return res.redirect(
      302,
      `/integrations?status=success&provider=slack&message=${encodeURIComponent(
        "Slack integration connected successfully"
      )}`
    );

  } catch (error) {
    console.error("Slack OAuth callback error:", error);
    return res.redirect(
      302,
      `/integrations?status=error&provider=slack&error=server_error&message=${encodeURIComponent(
        error instanceof Error ? error.message : "Unknown error occurred"
      )}`
    );
  }
}
