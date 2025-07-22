import { NextApiRequest, NextApiResponse } from 'next';
import { updateElevenLabsApiKey, getElevenLabsApiKey } from 'lib/atom-safe-storage';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'GET') {
    try {
      const apiKey = await getElevenLabsApiKey();
      res.status(200).json({ apiKey });
    } catch (error) {
      console.error('Error fetching ElevenLabs API key:', error);
      res.status(500).json({ message: 'Failed to fetch API key.' });
    }
  } else if (req.method === 'POST') {
    try {
      const { apiKey } = req.body;
      await updateElevenLabsApiKey(apiKey);
      res.status(200).json({ message: 'API key updated successfully.' });
    } catch (error) {
      console.error('Error updating ElevenLabs API key:', error);
      res.status(500).json({ message: 'Failed to update API key.' });
    }
  } else {
    res.setHeader('Allow', ['GET', 'POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
