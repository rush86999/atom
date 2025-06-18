import type { NextApiRequest, NextApiResponse } from 'next';
import { handleMessage } from '../../../../project/functions/atom-agent/handler'; // Adjust path as necessary
import { superTokensNextWrapper } from 'supertokens-node/nextjs';
import { verifySession } from "supertokens-node/recipe/session/framework/express";
import Session from 'supertokens-node/recipe/session';


type Data = {
  response?: string;
  error?: string;
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<Data>
) {
  await superTokensNextWrapper(
    async (next) => {
      // Protect the route with verifySession
      // verifySession will automatically send a 401 response if the session does not exist.
      return await verifySession()(req as any, res as any, next);
    },
    req,
    res
  );

  // If verifySession fails, it would have already sent a response and possibly ended it.
  // The check below for res.writableEnded is a good practice.
  if (res.writableEnded) {
    return;
  }

  // If verifySession succeeds, req.session should be populated.
  const session = (req as any).session as Session.SessionContainer;
  if (!session) {
    // This case should ideally not be reached if verifySession() correctly ends the response on auth failure.
    // It's a safeguard.
    return res.status(401).json({ error: 'Authentication required (session not found after verify)' });
  }

  const userId = session.getUserId();

  if (req.method === 'POST') {
    const { message } = req.body;

    if (!message) {
      return res.status(400).json({ error: 'Missing message in request body' });
    }

    try {
      // Pass userId to handleMessage
      const atomResponse = await handleMessage(message as string, userId);
      return res.status(200).json({ response: atomResponse });
    } catch (error: any) {
      console.error(`Error calling Atom agent handleMessage for userId ${userId}:`, error);
      return res.status(500).json({ error: error.message || 'Internal Server Error from Atom agent' });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
