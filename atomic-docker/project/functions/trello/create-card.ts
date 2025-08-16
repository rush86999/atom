import { Request, Response } from 'express';
import { handleCreateTrelloCard } from '../../atom-agent/skills/trello';

const handler = async (req: Request, res: Response) => {
  try {
    const { session_variables, input } = req.body;
    const userId = session_variables['x-hasura-user-id'];
    const { list_id, card_name } = input;

    if (!userId || !list_id || !card_name) {
      return res.status(400).json({ message: 'Missing required parameters' });
    }

    const result = await handleCreateTrelloCard(userId, { list_id, card_name });

    return res.status(200).json({ result });
  } catch (e) {
    console.error(e, ' unable to create trello card');
    return res.status(500).json({ message: 'Internal Server Error' });
  }
};

export default handler;
