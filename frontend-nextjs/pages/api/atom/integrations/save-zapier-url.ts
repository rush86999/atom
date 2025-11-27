import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]";
import { executeGraphQLMutation } from "@lib/graphqlClient";

async function saveZapierUrl(userId: string, url: string) {
  const mutation = `
        mutation InsertUserSetting($userId: String!, $key: String!, $value: String!) {
            insert_user_settings_one(object: {user_id: $userId, key: $key, value: $value}, on_conflict: {constraint: user_settings_user_id_key_key, update_columns: value}) {
                user_id
                key
                value
            }
        }
    `;
  const variables = {
    userId,
    key: "zapier_webhook_url",
    value: url,
  };
  await executeGraphQLMutation(
    mutation,
    variables,
    "InsertUserSetting",
    userId,
  );
}

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
    const { url } = req.body;
    if (!url) {
      return res.status(400).json({ message: "URL is required" });
    }
    try {
      await saveZapierUrl(userId, url);
      return res.status(200).json({ message: "Zapier URL saved successfully" });
    } catch (error) {
      console.error("Error saving Zapier URL:", error);
      return res.status(500).json({ message: "Failed to save Zapier URL" });
    }
  } else {
    res.setHeader("Allow", ["POST"]);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
