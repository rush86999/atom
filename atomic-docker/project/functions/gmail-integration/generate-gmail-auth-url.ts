import { Request, Response } from 'express';
import { google } from 'googleapis';
// Adjust the path based on the final location of gmail-integration relative to google-api-auth
import { googleClientIdGmail, googleClientSecretGmail, googleGmailRedirectUrl, googleGmailScopes } from '../google-api-auth/_libs/constants';

interface GenerateGmailAuthUrlRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: {
    // clientRedirectUri?: string; // If you need to support multiple redirect URIs from different clients
  };
}

const handler = async (req: Request<{}, {}, GenerateGmailAuthUrlRequestBody>, res: Response) => {
  try {
    // const userId = req.body.session_variables['x-hasura-user-id'];

    const redirectUri = googleGmailRedirectUrl;
    if (!redirectUri) {
        console.error('GOOGLE_GMAIL_REDIRECT_URL environment variable is not configured.');
        return res.status(500).json({ message: 'Server configuration error: Missing redirect URL for Gmail integration.' });
    }

    if (!googleClientIdGmail) {
        console.error('GOOGLE_CLIENT_ID_GMAIL environment variable is not configured.');
        return res.status(500).json({ message: 'Server configuration error: Missing Client ID for Gmail integration.' });
    }
    // googleClientSecretGmail is not strictly required to generate the auth URL but the oauth2Client expects it.
    // It will be used in the callback handler.
    if (!googleClientSecretGmail) {
        console.error('GOOGLE_CLIENT_SECRET_GMAIL environment variable is not configured.');
        return res.status(500).json({ message: 'Server configuration error: Missing Client Secret for Gmail integration.' });
    }

    const oauth2Client = new google.auth.OAuth2(
      googleClientIdGmail,
      googleClientSecretGmail,
      redirectUri
    );

    const authorizationUrl = oauth2Client.generateAuthUrl({
      access_type: 'offline', // Request a refresh token
      scope: googleGmailScopes,
      prompt: 'consent', // Important to ensure the user is prompted for consent and a refresh token is issued,
                        // especially if they've authorized before with fewer scopes or for a different app version.
    });

    return res.status(200).json({
      authorizationUrl: authorizationUrl,
    });

  } catch (e: any) {
    console.error('Error generating Gmail auth URL:', e);
    return res.status(500).json({
      message: 'Error generating Gmail authorization URL: ' + (e.message || 'Unknown error'),
    });
  }
};

export default handler;
