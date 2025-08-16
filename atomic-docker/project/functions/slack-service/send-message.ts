import { Request, Response } from 'express';
import { sendSlackMessage } from './service';

const handler = async (req: Request, res: Response) => {
  try {
    const { session_variables, input } = req.body;
    const userId = session_variables['x-hasura-user-id'];
    const { channelId, text } = input;

    if (!userId || !channelId || !text) {
      return res.status(400).json({ message: 'Missing required parameters' });
    }

    const result = await sendSlackMessage(userId, channelId, text);

    return res.status(200).json(result);
  } catch (e) {
    console.error(e, ' unable to send slack message');
    return res.status(500).json({ message: 'Internal Server Error' });
  }
};

export default handler;
