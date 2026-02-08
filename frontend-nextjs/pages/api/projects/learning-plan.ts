import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";

/**
 * Learning Plan Handler
 *
 * This endpoint handles AI-generated learning plan requests.
 *
 * Flow:
 * 1. User submits topic and learning preferences
 * 2. Frontend forwards request to backend
 * 3. Backend generates structured learning plan using AI
 * 4. Returns modules, resources, milestones, and assessments
 *
 * Environment Variables Required:
 * - BACKEND_URL or NEXT_PUBLIC_API_URL: Backend API URL
 *
 * Request Body:
 * - topic: Topic to learn about (required)
 * - current_skill_level: beginner | intermediate | advanced
 * - learning_goals: Array of specific objectives
 * - time_commitment: low | medium | high (hours per week)
 * - duration_weeks: Plan duration (1-52 weeks)
 * - preferred_format: Learning formats (articles, videos, exercises)
 * - notion_database_id: Optional Notion database ID
 *
 * Response:
 * - plan_id: Unique identifier
 * - modules: Array of weekly learning modules
 * - milestones: Key learning milestones
 * - assessment_criteria: Success criteria
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
      topic,
      current_skill_level,
      learning_goals,
      time_commitment,
      duration_weeks,
      preferred_format,
      notionDatabaseId
    } = req.body;

    // Validate required fields
    if (!topic || typeof topic !== "string" || topic.trim().length === 0) {
      return res.status(400).json({ message: "Topic is required" });
    }

    // Validate skill level
    const validLevels = ["beginner", "intermediate", "advanced"];
    const skillLevel = current_skill_level || "beginner";

    if (!validLevels.includes(skillLevel)) {
      return res.status(400).json({
        message: `Invalid skill level. Must be one of: ${validLevels.join(", ")}`
      });
    }

    // Validate time commitment
    const validCommitments = ["low", "medium", "high"];
    const commitment = time_commitment || "medium";

    if (!validCommitments.includes(commitment)) {
      return res.status(400).json({
        message: `Invalid time commitment. Must be one of: ${validCommitments.join(", ")}`
      });
    }

    // Validate duration
    const duration = duration_weeks || 4;
    if (duration < 1 || duration > 52) {
      return res.status(400).json({
        message: "Duration must be between 1 and 52 weeks"
      });
    }

    // Default preferred formats
    const formats = preferred_format || ["articles", "videos", "exercises"];

    // Forward the request to the backend
    const backendUrl = `${BACKEND_API_URL}/api/v1/learning/plans`;

    // Include user identification header
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    // Add user ID from session if available
    if (session.user?.id || session.user?.email) {
      headers["X-User-ID"] = (session.user.id || session.user.email) as string;
    }

    const requestBody: any = {
      topic: topic.trim(),
      current_skill_level: skillLevel,
      learning_goals: learning_goals || [],
      time_commitment: commitment,
      duration_weeks: duration,
      preferred_format: formats,
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
      console.error("Backend learning plan error:", data);

      if (response.status === 400) {
        return res.status(400).json({
          message: data.detail || "Invalid request",
          errors: [data.detail || data.message],
        });
      }

      return res.status(500).json({
        message: data.detail || data.message || "Failed to generate learning plan",
        errors: [data.detail || data.message || "Unknown error"],
      });
    }

    // Success!
    return res.status(200).json({
      plan_id: data.plan_id,
      topic: data.topic,
      current_skill_level: data.current_skill_level,
      target_skill_level: data.target_skill_level,
      duration_weeks: data.duration_weeks,
      modules: data.modules,
      milestones: data.milestones,
      assessment_criteria: data.assessment_criteria,
      created_at: data.created_at,
      message: "Learning plan generated successfully",
    });

  } catch (error) {
    console.error("Error generating learning plan:", error);
    return res.status(500).json({
      message: "Failed to generate learning plan",
      errors: [error instanceof Error ? error.message : "Unknown error occurred"],
    });
  }
}
