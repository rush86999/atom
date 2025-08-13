import { Request, Response } from 'express';
import { sendEmail } from './service';

const handler = async (req: Request, res: Response) => {
  try {
    const { session_variables, input } = req.body;
    const userId = session_variables['x-hasura-user-id'];
    const { to, subject, body } = input;

    if (!userId || !to || !subject || !body) {
      return res.status(400).json({ message: 'Missing required parameters' });
    }

    const result = await sendEmail(userId, to, subject, body);

    return res.status(200).json(result);
  } catch (e) {
    console.error(e, ' unable to send email');
    return res.status(500).json({ message: 'Internal Server Error' });
  }
};

export default handler;
