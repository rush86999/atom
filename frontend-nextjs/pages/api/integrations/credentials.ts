import { NextApiRequest, NextApiResponse } from "next";
import { getSession } from "supertokens-node/recipe/session";
import { SessionContainer } from "supertokens-node/recipe/session";
import {
  executeGraphQLMutation,
  executeGraphQLQuery,
} from '../../../lib/graphqlClient';
import { encrypt, decrypt } from '../../../lib/crypto';

async function saveCredential(userId: string, service: string, secret: string) {
  const encryptedSecret = encrypt(secret);

  const mutation = `
    mutation SaveCredential($userId: String!, $service: String!, $secret: String!) {
      insert_user_credentials_one(
        object: {
          user_id: $userId, 
          service: $service, 
          encrypted_secret: $secret,
          updated_at: "now()"
        }, 
        on_conflict: {
          constraint: user_credentials_pkey, 
          update_columns: [encrypted_secret, updated_at]
        }
      ) {
        id
      }
    }
  `;

  await executeGraphQLMutation(mutation, {
    userId,
    service,
    secret: encryptedSecret,
  });
}

async function getCredential(userId: string, service: string) {
  const query = `
    query GetCredential($userId: String!, $service: String!) {
      user_credentials_by_pk(user_id: $userId, service: $service) {
        encrypted_secret
      }
    }
  `;

  const response = await executeGraphQLQuery(query, { userId, service });

  if (response.data?.user_credentials_by_pk?.encrypted_secret) {
    return {
      isConnected: true,
      value: decrypt(response.data.user_credentials_by_pk.encrypted_secret)
    };
  }

  return { isConnected: false };
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  let session: SessionContainer;
  try {
    session = await getSSRSession(req, res, {
      overrideGlobalClaimValidators: () => [],
    });
  } catch (err) {
    return res.status(401).json({ message: "Unauthorized" });
  }

  const userId = session.getUserId();

  if (req.method === "POST") {
    const { service, secret } = req.body;
    if (!service || !secret) {
      return res
        .status(400)
        .json({ message: "Service and secret are required" });
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
  } else if (req.method === "GET") {
    const { service } = req.query;
    if (!service) {
      return res.status(400).json({ message: "Service is required" });
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
    res.setHeader("Allow", ["POST", "GET"]);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
