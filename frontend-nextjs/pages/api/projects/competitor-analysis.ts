import { NextApiRequest, NextApiResponse } from 'next';
import { getSession } from 'supertokens-node/nextjs';
import { SessionContainer } from 'supertokens-node/recipe/session';
import { runCompetitorAnalysis } from '../../../../project/functions/atom-agent/skills/competitorAnalysisSkills';

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
  const { competitors, notionDatabaseId } = req.body;

  if (!competitors || !notionDatabaseId) {
    return res
      .status(400)
      .json({ message: 'Competitors and Notion Database ID are required' });
  }

  try {
    await runCompetitorAnalysis(userId, competitors, notionDatabaseId);
    return res.status(200).json({ message: 'Competitor analysis complete' });
  } catch (error) {
    console.error('Error running competitor analysis:', error);
    return res
      .status(500)
      .json({ message: 'Failed to run competitor analysis' });
  }
}
