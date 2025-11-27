import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";
// TODO: Competitor analysis API temporarily disabled due to missing dependencies
// import { analyzeCompetitors } from "../../../../project/functions/atom-agent/skills/competitorAnalysisSkills";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.user.id;
  const { competitors, notionDatabaseId } = req.body;

  if (!competitors || !notionDatabaseId) {
    return res
      .status(400)
      .json({ message: "Competitors and Notion Database ID are required" });
  }

  try {
    await runCompetitorAnalysis(userId, competitors, notionDatabaseId);
    return res.status(200).json({ message: "Competitor analysis complete" });
  } catch (error) {
    console.error("Error running competitor analysis:", error);
    return res
      .status(500)
      .json({ message: "Failed to run competitor analysis" });
  }
}
