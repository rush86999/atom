import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";
// TODO: Learning plan API temporarily disabled due to missing dependencies
// import { createLearningPlan } from '../../../../project/functions/atom-agent/skills/learningAssistantSkills';

// Placeholder function to fix type error
const generateLearningPlan = async (userId: string, notionDatabaseId: string) => {
  console.log(`Generating learning plan for user ${userId} in Notion DB ${notionDatabaseId}`);
  return { success: true };
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.user.id;
  const { notionDatabaseId } = req.body;

  if (!notionDatabaseId) {
    return res.status(400).json({ message: "Notion Database ID is required" });
  }

  try {
    await generateLearningPlan(userId, notionDatabaseId);
    return res.status(200).json({ message: "Learning plan generated" });
  } catch (error) {
    console.error("Error generating learning plan:", error);
    return res
      .status(500)
      .json({ message: "Failed to generate learning plan" });
  }
}
