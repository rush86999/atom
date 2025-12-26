import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const consumerKey = process.env.POCKET_CONSUMER_KEY;
  const redirectUri = process.env.POCKET_REDIRECT_URI;

  if (!consumerKey || !redirectUri) {
    return res
      .status(500)
      .json({ message: "Pocket environment variables not configured." });
  }

  try {
    const response = await fetch("https://getpocket.com/v3/oauth/request", {
      method: "POST",
      headers: {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Accept": "application/json",
      },
      body: JSON.stringify({
        consumer_key: consumerKey,
        redirect_uri: redirectUri,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Pocket request token failed: ${response.status} ${errorText}`);
    }

    const { code } = await response.json();

    // In a real app, you would save this request token in the user's session
    // or a temporary store to verify it on callback.
    const authorizationUrl = `https://getpocket.com/auth/authorize?request_token=${code}&redirect_uri=${encodeURIComponent(redirectUri)}`;

    res.redirect(authorizationUrl);
  } catch (error) {
    console.error("Error getting Pocket request token:", error);
    return res
      .status(500)
      .json({ message: "Failed to start Pocket authentication" });
  }
}
