import { NextApiRequest, NextApiResponse } from 'next';
import {
  handleMessage,
  HandleMessageResponse,
} from '../../../../project/functions/atom-agent/handler';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';

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
    const { message, settings } = req.body;
    if (!message) {
      return res.status(400).json({ message: 'Message is required' });
    }
    try {
      // Pass the settings from the desktop app to the handler
      const atomResponse: HandleMessageResponse = await handleMessage(
        message,
        settings
      );
      return res.status(200).json(atomResponse);
    } catch (error) {
      console.error('Error in desktop proxy:', error);
      return res
        .status(500)
        .json({ message: 'Failed to process message via desktop proxy' });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
