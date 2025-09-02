import { NextApiRequest, NextApiResponse } from 'next';
import { understandMessage } from '../../../../project/functions/atom-agent/skills/nluService';
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
    const { message } = req.body;
    if (!message) {
      return res.status(400).json({ message: 'Message is required' });
    }
    try {
      const nluResponse = await understandMessage(
        message,
        undefined,
        undefined,
        { service: 'openai', apiKey: process.env.OPENAI_API_KEY || '' }
      );
      return res.status(200).json(nluResponse);
    } catch (error) {
      console.error('Error in NLU service:', error);
      return res
        .status(500)
        .json({ message: 'Failed to process message with NLU service' });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
