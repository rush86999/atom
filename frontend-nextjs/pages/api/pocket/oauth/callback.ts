import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';
import { executeGraphQLQuery } from '../../../../../project/functions/_libs/graphqlClient';
import PocketAPI from 'pocket-api';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  let session: SessionContainer;
  try {
    session = await getSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: 'Unauthorized' });
  }

  const userId = session.getUserId();
  const { code } = req.query;

  const consumerKey = process.env.POCKET_CONSUMER_KEY;
  if (!consumerKey) {
    return res
      .status(500)
      .json({ message: 'Pocket consumer key not configured.' });
  }

  const pocket = new PocketAPI({ consumer_key: consumerKey });

  try {
    const { access_token } = await pocket.getAccessToken({
      request_token: code as string,
    });

    // Save the token to the user_tokens table
    const mutation = `
            mutation InsertUserToken($userId: String!, $service: String!, $accessToken: String!) {
                insert_user_tokens_one(object: {user_id: $userId, service: $service, access_token: $accessToken}) {
                    id
                }
            }
        `;
    const variables = {
      userId,
      service: 'pocket',
      accessToken: access_token,
    };
    await executeGraphQLQuery(mutation, variables, 'InsertUserToken', userId);

    return res.redirect('/Settings/UserViewSettings');
  } catch (error) {
    console.error('Error during Pocket OAuth callback:', error);
    return res
      .status(500)
      .json({ message: 'Failed to complete Pocket OAuth flow' });
  }
}
