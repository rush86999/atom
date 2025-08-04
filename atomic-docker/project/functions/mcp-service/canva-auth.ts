import { Request, Response } from 'express';
import { AuthorizationCode } from 'simple-oauth2';

const canvaClientId = process.env.CANVA_CLIENT_ID;
const canvaClientSecret = process.env.CANVA_CLIENT_SECRET;
const canvaRedirectUrl = process.env.CANVA_REDIRECT_URL;
const canvaScopes = ['design:content:write', 'profile:read'];

interface GenerateCanvaAuthUrlRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: {};
}

const handler = async (
  req: Request<{}, {}, GenerateCanvaAuthUrlRequestBody>,
  res: Response
) => {
  try {
    if (!canvaClientId || !canvaClientSecret || !canvaRedirectUrl) {
      console.error('Canva environment variables are not configured.');
      return res
        .status(500)
        .json({
          message:
            'Server configuration error: Missing Canva integration credentials.',
        });
    }

    const client = new AuthorizationCode({
      client: {
        id: canvaClientId,
        secret: canvaClientSecret,
      },
      auth: {
        tokenHost: 'https://api.canva.com',
        tokenPath: '/rest/v1/oauth/token',
        authorizeHost: 'https://www.canva.com',
        authorizePath: '/api/oauth/authorize',
      },
    });

    const authorizationUrl = client.authorizeURL({
      redirect_uri: canvaRedirectUrl,
      scope: canvaScopes.join(' '),
    });

    return res.status(200).json({
      authorizationUrl: authorizationUrl,
    });
  } catch (e: any) {
    console.error('Error generating Canva auth URL:', e);
    return res.status(500).json({
      message:
        'Error generating Canva authorization URL: ' +
        (e.message || 'Unknown error'),
    });
  }
};

export default handler;
