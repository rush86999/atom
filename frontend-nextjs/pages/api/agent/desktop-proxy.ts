import { NextApiRequest, NextApiResponse } from "next";
import { handleMessage, HandleMessageResponse } from "./handler";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../auth/[...nextauth]";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.user.id;

  if (req.method === "POST") {
    const { message, settings } = req.body;
    if (!message) {
      return res.status(400).json({ message: "Message is required" });
    }
    try {
      // Pass the settings from the desktop app to the handler
      const atomResponse: HandleMessageResponse = await handleMessage(
        message,
        settings,
      );
      return res.status(200).json(atomResponse);
    } catch (error) {
      console.error("Error in desktop proxy:", error);
      return res
        .status(500)
        .json({ message: "Failed to process message via desktop proxy" });
    }
  } else {
    res.setHeader("Allow", ["POST"]);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
