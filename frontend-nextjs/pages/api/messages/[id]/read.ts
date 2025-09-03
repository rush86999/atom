import { NextApiRequest, NextApiResponse } from "next";
import { getSession } from "supertokens-node/nextjs";
import { SessionContainer } from "supertokens-node/recipe/session";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  if (req.method !== "POST") {
    return res.status(405).json({ message: "Method not allowed" });
  }

  let session: SessionContainer;
  try {
    session = await getSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.getUserId();
  const messageId = req.query.id as string;

  if (!messageId) {
    return res.status(400).json({ message: "Message ID is required" });
  }

  try {
    // In a real implementation, you would update the message status in your database
    // For now, we'll simulate a successful update
    console.log(`User ${userId} marked message ${messageId} as read`);

    // Simulate database update
    // await markMessageAsRead(messageId, userId);

    res.status(200).json({
      success: true,
      message: "Message marked as read",
      messageId,
    });
  } catch (error) {
    console.error("Error marking message as read:", error);
    res.status(500).json({ message: "Internal server error" });
  }
}
