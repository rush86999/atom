import { Request, Response } from 'express';
import { handleCreateAsanaTask } from '../../atom-agent/skills/asana';

const handler = async (req: Request, res: Response) => {
  try {
    const { session_variables, input } = req.body;
    const userId = session_variables['x-hasura-user-id'];
    const { project_id, task_name } = input;

    if (!userId || !project_id || !task_name) {
      return res.status(400).json({ message: 'Missing required parameters' });
    }

    const result = await handleCreateAsanaTask(userId, { project_id, task_name });

    return res.status(200).json({ result });
  } catch (e) {
    console.error(e, ' unable to create asana task');
    return res.status(500).json({ message: 'Internal Server Error' });
  }
};

export default handler;
