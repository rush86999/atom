import { NextApiRequest, NextApiResponse } from 'next';
import PocketAPI from 'pocket-api';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const consumerKey = process.env.POCKET_CONSUMER_KEY;
  const redirectUri = process.env.POCKET_REDIRECT_URI;

  if (!consumerKey || !redirectUri) {
    return res
      .status(500)
      .json({ message: 'Pocket environment variables not configured.' });
  }

  const pocket = new PocketAPI({
    consumer_key: consumerKey,
    redirect_uri: redirectUri,
  });

  try {
    const { code } = await pocket.getRequestToken();
    // In a real app, you would save this request token in the user's session
    // or a temporary store to verify it on callback.
    const authorizationUrl = pocket.getAuthorizationURL({
      request_token: code,
    });

    res.redirect(authorizationUrl);
  } catch (error) {
    console.error('Error getting Pocket request token:', error);
    return res
      .status(500)
      .json({ message: 'Failed to start Pocket authentication' });
  }
}
