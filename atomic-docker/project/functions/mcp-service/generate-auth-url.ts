import { Request, Response } from 'express';
import { google } from 'googleapis';
// Adjust the path based on the final location of mcp-service relative to google-api-auth
import {
  googleClientIdMcp,
  googleClientSecretMcp,
  googleMcpRedirectUrl,
  googleMcpScopes,
} from '../google-api-auth/_libs/constants';

interface GenerateMcpAuthUrlRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: {
    // clientRedirectUri?: string; // If you need to support multiple redirect URIs from different clients
  };
}

const handler = async (
  req: Request<{}, {}, GenerateMcpAuthUrlRequestBody>,
  res: Response
) => {
  try {
    // const userId = req.body.session_variables['x-hasura-user-id'];

    const redirectUri = googleMcpRedirectUrl;
    if (!redirectUri) {
      console.error(
        'GOOGLE_MCP_REDIRECT_URL environment variable is not configured.'
      );
      return res
        .status(500)
        .json({
          message:
            'Server configuration error: Missing redirect URL for Mcp integration.',
        });
    }

    if (!googleClientIdMcp) {
      console.error(
        'GOOGLE_CLIENT_ID_MCP environment variable is not configured.'
      );
      return res
        .status(500)
        .json({
          message:
            'Server configuration error: Missing Client ID for Mcp integration.',
        });
    }
    // googleClientSecretMcp is not strictly required to generate the auth URL but the oauth2Client expects it.
    // It will be used in the callback handler.
    if (!googleClientSecretMcp) {
      console.error(
        'GOOGLE_CLIENT_SECRET_MCP environment variable is not configured.'
      );
      return res
        .status(500)
        .json({
          message:
            'Server configuration error: Missing Client Secret for Mcp integration.',
        });
    }

    const oauth2Client = new google.auth.OAuth2(
      googleClientIdMcp,
      googleClientSecretMcp,
      redirectUri
    );

    const authorizationUrl = oauth2Client.generateAuthUrl({
      access_type: 'offline', // Request a refresh token
      scope: googleMcpScopes,
      prompt: 'consent', // Important to ensure the user is prompted for consent and a refresh token is issued,
      // especially if they've authorized before with fewer scopes or for a different app version.
    });

    return res.status(200).json({
      authorizationUrl: authorizationUrl,
    });
  } catch (e: any) {
    console.error('Error generating Mcp auth URL:', e);
    return res.status(500).json({
      message:
        'Error generating Mcp authorization URL: ' +
        (e.message || 'Unknown error'),
    });
  }
};

export default handler;
