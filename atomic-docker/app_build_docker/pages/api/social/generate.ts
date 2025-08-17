import { NextApiRequest, NextApiResponse } from 'next';
import { generateSocialMediaPost } from '../../../../../src/orchestration/socialMediaOrchestrator';
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
    const { topic } = req.body;
    if (!topic) {
      return res.status(400).json({ message: 'Topic is required' });
    }

    try {
      const result = await generateSocialMediaPost(userId, topic);

      if (result.ok) {
        return res.status(200).json({ content: result.data.content });
      } else {
        return res.status(500).json({ message: result.error.message, errors: [result.error.message] });
      }
    } catch (error: any) {
      console.error('Error in social media post generation:', error);
      return res
        .status(500)
        .json({ message: 'Failed to generate social media post', errors: [error.message] });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
