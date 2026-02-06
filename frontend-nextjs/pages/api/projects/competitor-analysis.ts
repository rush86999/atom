import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";

/**
 * Competitor Analysis Handler
 *
 * This endpoint handles AI-powered competitor analysis requests.
 *
 * Flow:
 * 1. User submits competitor list and analysis preferences
 * 2. Frontend forwards request to backend
 * 3. Backend fetches competitor data using web scraping
 * 4. Backend analyzes data using LLM
 * 5. Returns insights, comparison matrix, and recommendations
 *
 * Environment Variables Required:
 * - BACKEND_URL or NEXT_PUBLIC_API_URL: Backend API URL
 *
 * Request Body:
 * - competitors: Array of competitor names/URLs (max 10)
 * - analysis_depth: "basic" | "standard" | "comprehensive"
 * - focus_areas: Array of areas to analyze (products, pricing, marketing, etc.)
 * - notion_database_id: Optional Notion database ID for results export
 *
 * Response:
 * - analysis_id: Unique identifier for this analysis
 * - insights: Detailed analysis for each competitor
 * - comparison_matrix: Comparison across competitors
 * - recommendations: Strategic recommendations
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
    const { competitors, analysis_depth, focus_areas, notionDatabaseId } = req.body;

    // Validate required fields
    if (!competitors || !Array.isArray(competitors) || competitors.length === 0) {
      return res.status(400).json({
        message: "At least one competitor must be specified"
      });
    }

    if (competitors.length > 10) {
      return res.status(400).json({
        message: "Maximum 10 competitors allowed per analysis"
      });
    }

    // Validate analysis depth
    const validDepths = ["basic", "standard", "comprehensive"];
    const depth = analysis_depth || "standard";

    if (!validDepths.includes(depth)) {
      return res.status(400).json({
        message: `Invalid analysis depth. Must be one of: ${validDepths.join(", ")}`
      });
    }

    // Default focus areas if not provided
    const areas = focus_areas || ["products", "pricing", "marketing", "strengths", "weaknesses"];

    // Forward the request to the backend
    const backendUrl = `${BACKEND_API_URL}/api/v1/analysis/competitors`;

    // Include user identification header
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    // Add user ID from session if available
    if (session.user?.id || session.user?.email) {
      headers["X-User-ID"] = (session.user.id || session.user.email) as string;
    }

    const requestBody: any = {
      competitors,
      analysis_depth: depth,
      focus_areas: areas,
    };

    // Add optional Notion database ID
    if (notionDatabaseId) {
      requestBody.notion_database_id = notionDatabaseId;
    }

    const response = await fetch(backendUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(requestBody),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("Backend competitor analysis error:", data);

      if (response.status === 400) {
        return res.status(400).json({
          message: data.detail || "Invalid request",
          errors: [data.detail || data.message],
        });
      }

      return res.status(500).json({
        message: data.detail || data.message || "Failed to analyze competitors",
        errors: [data.detail || data.message || "Unknown error"],
      });
    }

    // Success!
    return res.status(200).json({
      analysis_id: data.analysis_id,
      status: data.status,
      insights: data.insights,
      comparison_matrix: data.comparison_matrix,
      recommendations: data.recommendations,
      created_at: data.created_at,
      message: "Competitor analysis completed successfully",
    });

  } catch (error) {
    console.error("Error in competitor analysis:", error);
    return res.status(500).json({
      message: "Failed to run competitor analysis",
      errors: [error instanceof Error ? error.message : "Unknown error occurred"],
    });
  }
}
