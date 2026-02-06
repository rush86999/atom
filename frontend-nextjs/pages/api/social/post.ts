import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";

/**
 * Social Media Post Handler
 *
 * This endpoint handles posting to social media platforms.
 *
 * Supported Platforms:
 * - Twitter/X
 * - LinkedIn
 * - Facebook
 *
 * Flow:
 * 1. User submits post with content and target platforms
 * 2. Frontend forwards request to backend
 * 3. Backend validates content and checks rate limits
 * 4. Backend posts to each platform using stored OAuth tokens
 * 5. Returns results for each platform
 *
 * Environment Variables Required:
 * - BACKEND_URL or NEXT_PUBLIC_API_URL: Backend API URL
 *
 * Request Body:
 * - text: Post content (string, 1-5000 chars)
 * - platforms: Array of platform names (["twitter", "linkedin"])
 * - scheduled_for: Optional datetime for scheduled posts
 * - media_urls: Optional array of media URLs
 * - link_url: Optional link to include
 *
 * Rate Limits:
 * - 10 posts per hour per user (across all platforms)
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
    const { text, platforms, scheduled_for, media_urls, link_url } = req.body;

    // Validate required fields
    if (!text) {
      return res.status(400).json({ message: "Text is required" });
    }

    if (!platforms || !Array.isArray(platforms) || platforms.length === 0) {
      return res.status(400).json({ message: "At least one platform must be specified" });
    }

    // Validate text length
    if (typeof text !== "string" || text.length < 1) {
      return res.status(400).json({ message: "Text must be at least 1 character" });
    }

    if (text.length > 5000) {
      return res.status(400).json({ message: "Text cannot exceed 5000 characters" });
    }

    // Validate platforms
    const validPlatforms = ["twitter", "linkedin", "facebook"];
    const invalidPlatforms = platforms.filter((p: string) => !validPlatforms.includes(p.toLowerCase()));

    if (invalidPlatforms.length > 0) {
      return res.status(400).json({
        message: `Invalid platforms: ${invalidPlatforms.join(", ")}. Supported: ${validPlatforms.join(", ")}`
      });
    }

    // Forward the request to the backend
    const backendUrl = `${BACKEND_API_URL}/api/v1/social/post`;

    // Include user identification header
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    // Add user ID from session if available
    if (session.user?.id || session.user?.email) {
      headers["X-User-ID"] = (session.user.id || session.user.email) as string;
    }

    const requestBody: any = {
      text,
      platforms,
    };

    // Add optional fields
    if (scheduled_for) {
      requestBody.scheduled_for = scheduled_for;
    }

    if (media_urls && Array.isArray(media_urls)) {
      requestBody.media_urls = media_urls;
    }

    if (link_url) {
      requestBody.link_url = link_url;
    }

    const response = await fetch(backendUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(requestBody),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error("Backend social post error:", data);

      // Handle specific error codes
      if (response.status === 429) {
        return res.status(429).json({
          message: "Rate limit exceeded. You can post 10 times per hour. Please try again later.",
          errors: [data.detail || data.message],
        });
      }

      if (response.status === 400) {
        return res.status(400).json({
          message: data.detail || "Invalid request",
          errors: [data.detail || data.message],
        });
      }

      return res.status(500).json({
        message: data.detail || data.message || "Failed to post to social media",
        errors: [data.detail || data.message || "Unknown error"],
      });
    }

    // Success!
    return res.status(200).json({
      success: data.success,
      post_id: data.post_id,
      platform_results: data.platform_results,
      scheduled: data.scheduled || false,
      scheduled_for: data.scheduled_for,
      message: generateSuccessMessage(data.platform_results, data.scheduled),
    });

  } catch (error) {
    console.error("Error in social media post:", error);
    return res.status(500).json({
      message: "Failed to post to social media",
      errors: [error instanceof Error ? error.message : "Unknown error occurred"],
    });
  }
}

function generateSuccessMessage(platformResults: any, scheduled: boolean): string {
  if (scheduled) {
    return "Post scheduled successfully";
  }

  const platforms = Object.keys(platformResults);
  const successful = platforms.filter(p => platformResults[p].success);
  const failed = platforms.filter(p => !platformResults[p].success);

  if (successful.length === platforms.length) {
    return `Successfully posted to ${successful.length} platform${successful.length > 1 ? "s" : ""}`;
  }

  if (successful.length > 0) {
    return `Partially successful: Posted to ${successful.join(", ")}. Failed: ${failed.join(", ")}`;
  }

  return "Failed to post to any platform";
}
