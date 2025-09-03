import { NextApiRequest, NextApiResponse } from "next";
// TODO: Social post API temporarily disabled due to missing dependencies
// import { runSocialMediaAutoPost } from "../../../src/orchestration/autonomousSystemOrchestrator";
import { getSession } from "supertokens-node/nextjs";
import { SessionContainer } from "supertokens-node/recipe/session";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  let session: SessionContainer;
  try {
    session = await getSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.getUserId();

  if (req.method === "POST") {
    const { text } = req.body;
    if (!text) {
      return res.status(400).json({ message: "Text is required" });
    }
    try {
      // const result = await runSocialMediaAutoPost(userId, text);
      const result = {
        success: false,
        message: "Social media posting temporarily disabled",
      };
      if (result.success) {
        return res.status(200).json({ message: result.message });
      } else {
        return res
          .status(500)
          .json({ message: result.message, errors: result.errors });
      }
    } catch (error: any) {
      console.error("Error in social media auto post:", error);
      return res.status(500).json({
        message: "Failed to post to social media",
        errors: [error.message],
      });
    }
  } else {
    res.setHeader("Allow", ["POST"]);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
