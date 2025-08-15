import { Request, Response } from 'express';
import { createNotionTask } from '../../atom-agent/skills/notionAndResearchSkills';

const handler = async (req: Request, res: Response) => {
  try {
    const { session_variables, input } = req.body;
    const userId = session_variables['x-hasura-user-id'];
    const { notion_db_id, description, properties } = input;

    if (!userId || !notion_db_id || !description) {
      return res.status(400).json({ message: 'Missing required parameters' });
    }

    const params = {
      notionTasksDbId: notion_db_id,
      description: description,
      ...properties,
    };

    const result = await createNotionTask(userId, params, {});

    return res.status(200).json(result);
  } catch (e) {
    console.error(e, ' unable to create notion task');
    return res.status(500).json({ message: 'Internal Server Error' });
  }
};

export default handler;
