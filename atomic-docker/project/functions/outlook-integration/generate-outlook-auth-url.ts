import { Request, Response } from 'express';
import { PublicClientApplication } from '@azure/msal-node';
import { getMsalConfig } from '../outlook-service/auth_utils';
import { OUTLOOK_OAUTH_SCOPES } from '../outlook-service/constants';

const handler = async (req: Request, res: Response) => {
  const userId = req.body.session_variables['x-hasura-user-id'];

  if (!userId) {
    return res.status(401).json({ success: false, message: 'User ID is missing. Unauthorized.' });
  }

  const msalConfig = getMsalConfig();
  const pca = new PublicClientApplication(msalConfig);

  const authCodeUrlParameters = {
    scopes: OUTLOOK_OAUTH_SCOPES,
    redirectUri: 'http://localhost:3000/outlook-callback', // This should be a configured redirect URI
    state: userId, // Pass user ID as state to link the callback to the user
  };

  try {
    const authUrl = await pca.getAuthCodeUrl(authCodeUrlParameters);
    return res.status(200).json({ success: true, authUrl });
  } catch (error) {
    console.error('Error generating Outlook auth URL:', error);
    return res.status(500).json({ success: false, message: 'Error generating Outlook auth URL.' });
  }
};

export default handler;
