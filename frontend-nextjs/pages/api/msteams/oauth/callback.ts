import { NextApiRequest, NextApiResponse } from "next";
import { getServerSession } from "next-auth/next";
import { authOptions } from "../../auth/[...nextauth]";
import { executeGraphQLMutation } from '../../../../lib/graphqlClient';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const session = await getServerSession(req, res, authOptions);

  if (!session || !session.user) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.user.id;
  const { code, state } = req.query;

  // In a real app, you should validate the 'state' parameter here

  const msTeamsClientId = process.env.MSTEAMS_CLIENT_ID;
  const msTeamsClientSecret = process.env.MSTEAMS_CLIENT_SECRET;
  const redirectUri = process.env.MSTEAMS_REDIRECT_URI;

  if (!msTeamsClientId || !msTeamsClientSecret || !redirectUri) {
    return res.status(500).json({
      message: "Microsoft Teams environment variables not configured.",
    });
  }

  try {
    const response = await fetch(
      "https://login.microsoftonline.com/common/oauth2/v2.0/token",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          client_id: msTeamsClientId,
          client_secret: msTeamsClientSecret,
          code: code as string,
          redirect_uri: redirectUri,
          grant_type: "authorization_code",
          scope: "offline_access User.Read Mail.ReadWrite Calendars.ReadWrite",
        }),
      },
    );

    const data = await response.json();

    if (response.ok) {
      const accessToken = data.access_token;
      const refreshToken = data.refresh_token;
      const expiresIn = data.expires_in;
      const expiresAt = new Date(Date.now() + expiresIn * 1000).toISOString();

      // Save the tokens to the user_tokens table
      const mutation = `
        mutation SaveTokens($userId: String!, $service: String!, $accessToken: String!, $refreshToken: String!, $expiresAt: timestamptz!) {
          insert_user_tokens_one(
            object: {
              user_id: $userId,
              service: $service,
              access_token: $accessToken,
              refresh_token: $refreshToken,
              expires_at: $expiresAt,
              updated_at: "now()"
            },
            on_conflict: {
              constraint: user_tokens_pkey,
              update_columns: [access_token, refresh_token, expires_at, updated_at]
            }
          ) {
            id
          }
        }
      `;

      try {
        await executeGraphQLMutation(mutation, {
          userId,
          service: 'msteams',
          accessToken,
          refreshToken,
          expiresAt,
        });
      } catch (error) {
        console.error("Failed to save tokens:", error);
        // Continue anyway to redirect user, but log the error
      }

      return res.redirect("/Settings/UserViewSettings");
    } else {
      return res.status(500).json({
        message: `Microsoft Teams OAuth error: ${data.error_description}`,
      });
    }
  } catch (error) {
    console.error("Error during Microsoft Teams OAuth callback:", error);
    return res
      .status(500)
      .json({ message: "Failed to complete Microsoft Teams OAuth flow" });
  }
}
