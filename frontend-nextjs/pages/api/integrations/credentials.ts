import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';
import {
  executeGraphQLMutation,
  executeGraphQLQuery,
} from '../../../../project/functions/_libs/graphqlClient';
import { encrypt, decrypt } from '../../../../project/functions/_libs/crypto'; // Assuming crypto utils exist

async function saveCredential(userId: string, service: string, secret: string) {
  const encryptedSecret = encrypt(secret);
  const mutation = `
        mutation InsertUserCredential($userId: String!, $serviceName: String!, $secret: String!) {
            insert_user_credentials_one(object: {user_id: $userId, service_name: $serviceName, encrypted_secret: $secret}, on_conflict: {constraint: user_credentials_pkey, update_columns: encrypted_secret}) {
                user_id
            }
        }
    `;
  const variables = {
    userId,
    serviceName: service,
    secret: encryptedSecret,
  };
  await executeGraphQLMutation(
    mutation,
    variables,
    'InsertUserCredential',
    userId
  );
}

async function getCredential(
  userId: string,
  service: string
): Promise<{ isConnected: boolean; value?: string | null }> {
  const query = `
        query GetUserSetting($userId: String!, $key: String!) {
            user_settings(where: {user_id: {_eq: $userId}, key: {_eq: $key}}) {
                value
            }
        }
    `;
  const variables = {
    userId,
    key: service,
  };
  const response = await executeGraphQLQuery<{
    user_settings: { value: string }[];
  }>(query, variables, 'GetUserSetting', userId);
  if (response.user_settings && response.user_settings.length > 0) {
    return { isConnected: true, value: response.user_settings[0].value };
  }
  return { isConnected: false };
}

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

  if (req.method === 'POST') {
    const { service, secret } = req.body;
    if (!service || !secret) {
      return res
        .status(400)
        .json({ message: 'Service and secret are required' });
    }
    try {
      await saveCredential(userId, service, secret);
      return res
        .status(200)
        .json({ message: `${service} credentials saved successfully` });
    } catch (error) {
      console.error(`Error saving ${service} credentials:`, error);
      return res
        .status(500)
        .json({ message: `Failed to save ${service} credentials` });
    }
  } else if (req.method === 'GET') {
    const { service } = req.query;
    if (!service) {
      return res.status(400).json({ message: 'Service is required' });
    }
    try {
      const credential = await getCredential(userId, service as string);
      return res.status(200).json(credential);
    } catch (error) {
      console.error(`Error checking ${service} credentials:`, error);
      return res
        .status(500)
        .json({ message: `Failed to check ${service} credentials` });
    }
  } else {
    res.setHeader('Allow', ['POST', 'GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
