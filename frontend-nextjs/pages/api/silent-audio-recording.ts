import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'POST') {
    const audioData = req.body;
    const filePath = path.join(
      process.cwd(),
      'silent-audio-recordings',
      `${Date.now()}.wav`
    );
    fs.writeFileSync(filePath, audioData);
    res.status(200).json({ message: 'Audio data saved successfully' });
  } else {
    res.status(405).json({ message: 'Method not allowed' });
  }
}
