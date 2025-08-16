import { Client } from "twitter-api-sdk";
import { SkillResponse } from "../../atomic-docker/project/functions/atom-agent/types";
import { getTwitterCredentials } from "../services/authService";

export async function postToTwitter(
  userId: string,
  text: string
): Promise<SkillResponse<{ success: boolean }>> {
  const credentials = await getTwitterCredentials(userId);

  if (!credentials) {
    return {
      ok: false,
      error: {
        code: "UNAUTHORIZED",
        message: "Twitter credentials not found for this user.",
      },
    };
  }

  try {
    const client = new Client(credentials.bearerToken);
    await client.tweets.createTweet({ text });
    return { ok: true, data: { success: true } };
  } catch (error: any) {
    return {
      ok: false,
      error: {
        code: "TWITTER_API_ERROR",
        message: error.message,
      },
    };
  }
}
