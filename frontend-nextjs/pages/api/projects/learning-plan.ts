import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';
import { generateLearningPlan } from '../../../../project/functions/atom-agent/skills/learningAssistantSkills';

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
  const { notionDatabaseId } = req.body;

  if (!notionDatabaseId) {
    return res.status(400).json({ message: 'Notion Database ID is required' });
  }

  try {
    await generateLearningPlan(userId, notionDatabaseId);
    return res.status(200).json({ message: 'Learning plan generated' });
  } catch (error) {
    console.error('Error generating learning plan:', error);
    return res
      .status(500)
      .json({ message: 'Failed to generate learning plan' });
  }
}
