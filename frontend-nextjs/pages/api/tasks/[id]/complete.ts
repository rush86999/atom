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
  const taskId = req.query.id as string;

  if (!taskId) {
    return res.status(400).json({ message: "Task ID is required" });
  }

  try {
    // In a real implementation, you would update the task in your database
    // For now, we'll simulate a successful update
    console.log(`User ${userId} completed task ${taskId}`);

    // Simulate database update
    // await updateTaskStatus(taskId, userId, 'completed');

    res.status(200).json({
      success: true,
      message: "Task marked as completed",
      taskId,
    });
  } catch (error) {
    console.error("Error completing task:", error);
    res.status(500).json({ message: "Internal server error" });
  }
}
