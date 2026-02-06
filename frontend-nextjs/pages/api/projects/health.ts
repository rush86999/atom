import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";

/**
 * Project Health Handler
 *
 * This endpoint handles project health metric calculations.
 *
 * Flow:
 * 1. User submits integration credentials and preferences
 * 2. Frontend forwards request to backend
 * 3. Backend calculates health metrics across multiple dimensions
 * 4. Returns overall score, individual metrics, and recommendations
 *
 * Environment Variables Required:
 * - BACKEND_URL or NEXT_PUBLIC_API_URL: Backend API URL
 *
 * Request Body:
 * - notion_api_key: Notion API key (optional)
 * - notion_database_id: Notion database ID (optional)
 * - github_owner: GitHub repository owner (optional)
 * - github_repo: GitHub repository name (optional)
 * - slack_channel_id: Slack channel ID (optional)
 * - time_range_days: Time range for analysis (1-90 days, default 7)
 *
 * Response:
 * - overall_score: 0-100 overall health score
 * - overall_status: excellent | good | warning | critical
 * - metrics: Individual health metrics by category
 * - recommendations: Actionable recommendations
 */

const BACKEND_API_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  // Only allow POST requests
  if (req.method !== "POST") {
    res.setHeader("Allow", ["POST"]);
    return res.status(405).json({ message: `Method ${req.method} Not Allowed` });
  }

  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  try {
    const {
      notion_api_key,
      notion_database_id,
      github_owner,
      github_repo,
      slack_channel_id,
      time_range_days
    } = req.body;

    // Validate time range
    const timeRange = time_range_days || 7;
    if (timeRange < 1 || timeRange > 90) {
      return res.status(400).json({
        message: "Time range must be between 1 and 90 days"
      });
    }

    // Check that at least one integration is provided
    const hasNotion = notion_api_key && notion_database_id;
    const hasGitHub = github_owner && github_repo;
    const hasSlack = slack_channel_id;

    if (!hasNotion && !hasGitHub && !hasSlack) {
      return res.status(400).json({
        message: "At least one integration (Notion, GitHub, or Slack) must be provided",
        hint: "Provide credentials for the services you want to analyze"
      });
    }

    // Forward the request to the backend
    const backendUrl = `${BACKEND_API_URL}/api/v1/projects/health`;

    // Include user identification header
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    // Add user ID from session if available
    if (session.user?.id || session.user?.email) {
      headers["X-User-ID"] = (session.user.id || session.user.email) as string;
    }

    const requestBody: any = {
      time_range_days: timeRange,
    };

    // Add optional integration credentials
    if (hasNotion) {
      requestBody.notion_api_key = notion_api_key;
      requestBody.notion_database_id = notion_database_id;
    }

    if (hasGitHub) {
      requestBody.github_owner = github_owner;
      requestBody.github_repo = github_repo;
    }

    if (hasSlack) {
      requestBody.slack_channel_id = slack_channel_id;
    }

    const response = await fetch(backendUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(requestBody),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("Backend project health error:", data);

      if (response.status === 400) {
        return res.status(400).json({
          message: data.detail || "Invalid request",
          errors: [data.detail || data.message],
        });
      }

      return res.status(500).json({
        message: data.detail || data.message || "Failed to check project health",
        errors: [data.detail || data.message || "Unknown error"],
      });
    }

    // Success!
    return res.status(200).json({
      check_id: data.check_id,
      overall_score: data.overall_score,
      overall_status: data.overall_status,
      metrics: data.metrics,
      recommendations: data.recommendations,
      checked_at: data.checked_at,
      time_range_days: data.time_range_days,
      message: "Project health check completed successfully",
    });

  } catch (error) {
    console.error("Error checking project health:", error);
    return res.status(500).json({
      message: "Failed to check project health",
      errors: [error instanceof Error ? error.message : "Unknown error occurred"],
    });
  }
}
