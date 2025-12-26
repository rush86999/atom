import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]";
import { executeGraphQLQuery } from '@/lib/graphqlClient';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.user.id;
  const { code } = req.query;

  const consumerKey = process.env.POCKET_CONSUMER_KEY;
  if (!consumerKey) {
    return res
      .status(500)
      .json({ message: "Pocket consumer key not configured." });
  }

  try {
    const response = await fetch("https://getpocket.com/v3/oauth/authorize", {
      method: "POST",
      headers: {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Accept": "application/json",
      },
      body: JSON.stringify({
        consumer_key: consumerKey,
        code: code as string,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Pocket access token failed: ${response.status} ${errorText}`);
    }

    const { access_token } = await response.json();

    // Save the token to the user_tokens table
    const mutation = `
            mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!) {
                insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken}) {
                    id
                }
            }
        `;
    const variables = {
      userId,
      service: "pocket",
      accessToken: access_token,
    };
    await executeGraphQLQuery(mutation, variables, "InsertUserToken", userId);

    return res.redirect("/Settings/UserViewSettings");
  } catch (error) {
    console.error("Error during Pocket OAuth callback:", error);
    return res
      .status(500)
      .json({ message: "Failed to complete Pocket OAuth flow" });
  }
}
