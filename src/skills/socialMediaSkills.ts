import { Client as TwitterClient } from "twitter-api-sdk";
import { RestliClient } from "linkedin-api-client";
import { SkillResponse } from "../../atomic-docker/project/functions/atom-agent/types";
import { getTwitterCredentials, getLinkedInCredentials } from "../services/authService";

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
    const client = new TwitterClient(credentials.bearerToken);
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

export async function postToLinkedIn(
  userId: string,
  text: string
): Promise<SkillResponse<{ success: boolean }>> {
  const credentials = await getLinkedInCredentials(userId);

  if (!credentials) {
    return {
      ok: false,
      error: {
        code: "UNAUTHORIZED",
        message: "LinkedIn credentials not found for this user.",
      },
    };
  }

  try {
    const restliClient = new RestliClient();
    const response = await restliClient.create({
        resourcePath: '/ugcPosts',
        entity: {
            "author": `urn:li:person:${credentials.personId}`,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "CONNECTIONS"
            }
        },
        accessToken: credentials.accessToken
    });

    if (response.status === 201) {
        return { ok: true, data: { success: true } };
    } else {
        return {
            ok: false,
            error: {
                code: "LINKEDIN_API_ERROR",
                message: `LinkedIn API returned status ${response.status}`,
            },
        };
    }
  } catch (error: any) {
    return {
      ok: false,
      error: {
        code: "LINKEDIN_API_ERROR",
        message: error.message,
      },
    };
  }
}
