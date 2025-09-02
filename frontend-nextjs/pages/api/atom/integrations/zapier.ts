import { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'POST') {
    try {
      // For now, we'll just log the incoming data.
      // In a real application, you would process this data to trigger actions.
      console.log('Received data from Zapier:', req.body);
      res.status(200).json({ message: 'Data received successfully.' });
    } catch (error) {
      console.error('Error handling Zapier webhook:', error);
      res.status(500).json({ message: 'Failed to process webhook.' });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
