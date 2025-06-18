import type { NextApiRequest, NextApiResponse } from 'next';
import { handleMessage } from '../../../../project/functions/atom-agent/handler'; // Adjust path as necessary

type Data = {
  response?: string;
  error?: string;
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<Data>
) {
  if (req.method === 'POST') {
    const { message } = req.body;

    if (!message) {
      return res.status(400).json({ error: 'Missing message in request body' });
    }

    try {
      const atomResponse = await handleMessage(message as string);
      return res.status(200).json({ response: atomResponse });
    } catch (error: any) {
      console.error('Error calling Atom agent handleMessage:', error);
      return res.status(500).json({ error: error.message || 'Internal Server Error from Atom agent' });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
