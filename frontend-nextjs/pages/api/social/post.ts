import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";

interface SocialPostRequest {
  text: string;
  platform?: 'twitter' | 'linkedin' | 'facebook' | 'instagram';
  media_urls?: string[];
  scheduled_time?: string;
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  if (req.method !== "POST") {
    res.setHeader("Allow", ["POST"]);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user?.email) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  try {
    const { text, platform = 'twitter', media_urls = [], scheduled_time }: SocialPostRequest = req.body;

    // Validate required fields
    if (!text || text.trim().length === 0) {
      return res.status(400).json({
        error: "Bad Request",
        message: "Text content is required"
      });
    }

    if (text.length > 280) {
      return res.status(400).json({
        error: "Bad Request",
        message: "Text content exceeds maximum length (280 characters)"
      });
    }

    // Validate platform
    const validPlatforms = ['twitter', 'linkedin', 'facebook', 'instagram'];
    if (!validPlatforms.includes(platform)) {
      return res.status(400).json({
        error: "Bad Request",
        message: `Invalid platform. Must be one of: ${validPlatforms.join(', ')}`
      });
    }

    // Get backend URL
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

    // Forward request to backend for actual posting
    const response = await fetch(`${backendUrl}/api/social/post`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': session.user.email,
        'X-User-ID': session.user.id || 'unknown',
      },
      body: JSON.stringify({
        text: text.trim(),
        platform,
        media_urls,
        scheduled_time,
        user_email: session.user.email,
        user_id: session.user.id,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      return res.status(200).json({
        success: true,
        message: `Successfully posted to ${platform}`,
        post_id: data.post_id,
        platform: platform,
        posted_at: data.posted_at || new Date().toISOString()
      });
    } else {
      return res.status(response.status).json({
        success: false,
        error: data.error || 'Failed to post to social media',
        message: data.message || 'Unknown error occurred',
        details: data.details || null
      });
    }

  } catch (error: any) {
    console.error("Error in social media post API:", error);
    return res.status(500).json({
      success: false,
      error: "Internal Server Error",
      message: "Failed to process social media post request",
      details: process.env.NODE_ENV === 'development' ? error.message : undefined
    });
  }
}