import { NextApiRequest, NextApiResponse } from 'next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const msTeamsClientId = process.env.MSTEAMS_CLIENT_ID;
  const redirectUri = process.env.MSTEAMS_REDIRECT_URI;
  const scope = 'offline_access User.Read Mail.ReadWrite Calendars.ReadWrite';
  const state = 'some-random-state'; // Should be a random, unguessable string

  if (!msTeamsClientId || !redirectUri) {
    return res
      .status(500)
      .json({
        message: 'Microsoft Teams environment variables not configured.',
      });
  }

  const authorizationUrl = `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=${msTeamsClientId}&response_type=code&redirect_uri=${redirectUri}&response_mode=query&scope=${scope}&state=${state}`;

  res.redirect(authorizationUrl);
}
